"""`mcflow kb pull` and `mcflow kb push`: sync knowledge/ with the shared GitHub repo.

The shared repo keeps one entry per file in `entries/`. Its default branch holds only approved
entries: everything reaches it through a reviewed pull request, never a direct push.

`.mcflow/kb.json` remembers, per entry, the content hash last seen on the shared default branch
(`base`) and the hash last sent in a pull request (`pushed`). That's what lets a pull tell "you
edited this" from "they updated this", and stops a push from proposing the same change twice.
"""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from mcflow.knowledge import entry as kb_entry

STATE_FILE = Path(".mcflow") / "kb.json"
CONFLICT_DIR = Path(".mcflow") / "kb-conflicts"
KNOWLEDGE_DIR = "knowledge"
REMOTE_DIR = "entries"
SLUG_RE = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
GH_CREDENTIALS = [
    "-c",
    "credential.https://github.com.helper=",
    "-c",
    "credential.https://github.com.helper=!gh auth git-credential",
]


class KbError(Exception):
    pass


def _hash(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


# --- state -------------------------------------------------------------------------------------


@dataclass
class State:
    base: dict[str, str] = field(default_factory=dict)
    pushed: dict[str, str] = field(default_factory=dict)


def load_state(root: Path) -> State:
    path = root / STATE_FILE
    if not path.is_file():
        return State()
    data = json.loads(path.read_text(encoding="utf-8"))
    return State(base=dict(data.get("base", {})), pushed=dict(data.get("pushed", {})))


def save_state(root: Path, state: State) -> None:
    path = root / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base": dict(sorted(state.base.items())),
        "pushed": dict(sorted(state.pushed.items())),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# --- git and the remote ------------------------------------------------------------------------


def resolve_remote(repo: str) -> tuple[str, str | None]:
    """`owner/name` -> (GitHub clone URL, slug). Anything else (path, git URL) -> (repo, None)."""
    if SLUG_RE.match(repo):
        return f"https://github.com/{repo}.git", repo
    return repo, None


def _git(args: list[str], cwd: Path | None = None, github: bool = False) -> str:
    cmd = ["git", *(GH_CREDENTIALS if github else []), *args]
    try:
        done = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=180
        )
    except FileNotFoundError:
        raise KbError("git isn't installed. Run `mcflow doctor` for how to install it.") from None
    except subprocess.TimeoutExpired:
        raise KbError(f"`git {args[0]}` took longer than 3 minutes and was stopped.") from None
    if done.returncode != 0:
        raise KbError(f"`git {' '.join(args[:2])}` failed: {(done.stderr or done.stdout).strip()}")
    return done.stdout.strip()


def clone(url: str, dest: Path) -> str:
    """Shallow-clone the shared repo's default branch into `dest`. Returns the branch name."""
    _git(["clone", "--depth", "1", url, str(dest)], github=url.startswith("https://github.com/"))
    return _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=dest)


def _local_entries(root: Path) -> dict[str, Path]:
    return {p.name: p for p in kb_entry.entry_files(root / KNOWLEDGE_DIR)}


def _remote_entries(checkout: Path) -> dict[str, Path]:
    return {p.name: p for p in kb_entry.entry_files(checkout / REMOTE_DIR)}


# --- pull --------------------------------------------------------------------------------------


@dataclass
class PullResult:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    kept_local: list[str] = field(default_factory=list)  # edited here; the shared copy didn't move
    conflicts: list[tuple[str, Path]] = field(default_factory=list)  # (entry, shared copy saved at)
    deleted_here: list[str] = field(default_factory=list)  # removed locally; not brought back
    removed_upstream: list[str] = field(default_factory=list)  # gone from the shared repo; kept
    invalid_upstream: list[tuple[str, list[str]]] = field(default_factory=list)


def merge(root: Path, checkout: Path) -> PullResult:
    """Bring approved entries from a checkout of the shared repo into knowledge/."""
    state = load_state(root)
    local = _local_entries(root)
    remote = _remote_entries(checkout)
    result = PullResult()
    knowledge = root / KNOWLEDGE_DIR
    knowledge.mkdir(exist_ok=True)

    for name, path in sorted(remote.items()):
        parsed = kb_entry.load(path)
        if not parsed.ok:
            result.invalid_upstream.append((name, parsed.errors))
            continue
        theirs = path.read_bytes()
        their_hash = _hash(theirs)
        base = state.base.get(name)
        if name not in local:
            if base is not None:
                result.deleted_here.append(name)
                continue
            (knowledge / name).write_bytes(theirs)
            result.added.append(name)
        else:
            mine_hash = _hash(local[name].read_bytes())
            if mine_hash == their_hash:
                result.unchanged.append(name)
            elif base is not None and mine_hash == base:
                local[name].write_bytes(theirs)
                result.updated.append(name)
            elif base is not None and their_hash == base:
                result.kept_local.append(name)
                continue
            else:
                saved = root / CONFLICT_DIR / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(theirs)
                result.conflicts.append((name, saved))
                continue
        state.base[name] = their_hash
        if state.pushed.get(name) == their_hash:
            del state.pushed[name]

    result.removed_upstream = sorted(n for n in local if n in state.base and n not in remote)
    save_state(root, state)
    return result


def pull(root: Path, repo: str) -> PullResult:
    url, _ = resolve_remote(repo)
    with tempfile.TemporaryDirectory(prefix="mcflow-kb-") as tmp:
        checkout = Path(tmp) / "kb"
        clone(url, checkout)
        return merge(root, checkout)


# --- push --------------------------------------------------------------------------------------


@dataclass
class PushPlan:
    new: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    invalid: dict[str, list[str]] = field(default_factory=dict)
    already_proposed: list[str] = field(default_factory=list)
    behind: list[str] = field(default_factory=list)  # unchanged here, newer upstream: pull first
    unknown: list[str] = field(default_factory=list)  # names asked for that aren't in knowledge/

    @property
    def to_send(self) -> list[str]:
        return sorted(self.new + self.changed)


def plan_push(root: Path, checkout: Path, only: list[str] | None = None) -> PushPlan:
    state = load_state(root)
    local = _local_entries(root)
    remote = _remote_entries(checkout)
    plan = PushPlan()
    wanted = {n if n.endswith(".md") else f"{n}.md" for n in only} if only else None
    if wanted:
        plan.unknown = sorted(wanted - local.keys())

    for name, path in sorted(local.items()):
        if wanted is not None and name not in wanted:
            continue
        mine = _hash(path.read_bytes())
        theirs = _hash(remote[name].read_bytes()) if name in remote else None
        if mine == theirs:
            continue
        if state.pushed.get(name) == mine:
            plan.already_proposed.append(name)
            continue
        if theirs is not None and state.base.get(name) == mine:
            plan.behind.append(name)
            continue
        parsed = kb_entry.load(path)
        if not parsed.ok:
            plan.invalid[name] = parsed.errors
        elif theirs is None:
            plan.new.append(name)
        else:
            plan.changed.append(name)
    return plan


class GitHub:
    """The gh calls `kb push` makes. Tests swap in a fake."""

    def _gh(self, args: list[str]) -> str:
        try:
            done = subprocess.run(
                ["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=120
            )
        except FileNotFoundError:
            raise KbError(
                "The GitHub CLI (gh) isn't installed. `mcflow doctor` says how."
            ) from None
        if done.returncode != 0:
            raise KbError(
                f"`gh {' '.join(args[:2])}` failed: {(done.stderr or done.stdout).strip()}"
            )
        return done.stdout.strip()

    def can_push(self, slug: str) -> bool:
        return self._gh(["api", f"repos/{slug}", "--jq", ".permissions.push"]) == "true"

    def fork(self, slug: str) -> str:
        """Fork `slug` (a no-op if the fork exists) and return the fork's slug."""
        self._gh(["repo", "fork", slug, "--clone=false", "--remote=false"])
        login = self._gh(["api", "user", "--jq", ".login"])
        return f"{login}/{slug.split('/', 1)[1]}"

    def create_pr(self, slug: str, head: str, base: str, title: str, body: str) -> str:
        args = ["pr", "create", "--repo", slug, "--head", head, "--base", base]
        return self._gh([*args, "--title", title, "--body", body])


@dataclass
class PushResult:
    plan: PushPlan
    url: str | None = None
    branch: str | None = None


def _pr_text(root: Path, names: list[str], plan: PushPlan, project: str) -> tuple[str, str]:
    entries = [kb_entry.load(root / KNOWLEDGE_DIR / n) for n in names]
    title = (
        f"Knowledge: {entries[0].title}"
        if len(entries) == 1
        else f"Knowledge: {len(entries)} entries from {project}"
    )
    lines = [
        "Entries proposed by `mcflow kb push`. Each was validated before this PR was opened.",
        "",
    ]
    for e in entries:
        status = "new" if e.path.name in plan.new else "updated"
        verified = e.fields.get("verified_by")
        verified = ", ".join(verified) if isinstance(verified, list) else verified
        lines.append(f"- **{e.title}** (`{e.path.name}`, {status})")
        lines.append(f"  - Minecraft: {', '.join(e.minecraft_versions)}")
        if e.pack_format is not None:
            lines.append(f"  - Pack format: {e.pack_format}")
        lines.append(f"  - Verified by: {verified}")
    lines += [
        "",
        "Please check the proof before merging: merged entries reach every mcflow install.",
    ]
    return title, "\n".join(lines)


def push(
    root: Path,
    url: str,
    slug: str,
    project: str,
    only: list[str] | None = None,
    github: GitHub | None = None,
    confirm: Callable[[PushPlan], bool] = lambda _plan: True,
    now: datetime | None = None,
) -> PushResult:
    """Open a pull request with the new and changed entries. Never pushes to the default branch."""
    gh = github or GitHub()
    on_github = url.startswith("https://github.com/")
    with tempfile.TemporaryDirectory(prefix="mcflow-kb-") as tmp:
        checkout = Path(tmp) / "kb"
        default = clone(url, checkout)
        plan = plan_push(root, checkout, only)
        if plan.unknown:
            raise KbError(f"Not in knowledge/: {', '.join(plan.unknown)}")
        if plan.invalid:
            problems = "\n".join(f"  {n}: {'; '.join(errs)}" for n, errs in plan.invalid.items())
            raise KbError(f"Fix these entries first (nothing was sent):\n{problems}")
        names = plan.to_send
        if not names or not confirm(plan):
            return PushResult(plan)

        stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        project_slug = re.sub(r"[^a-z0-9]+", "-", project.lower()).strip("-") or "project"
        branch = f"kb/{project_slug}-{stamp}"
        if branch == default:
            raise KbError("Refusing to push to the shared repo's default branch.")

        _git(["checkout", "-b", branch], cwd=checkout)
        (checkout / REMOTE_DIR).mkdir(exist_ok=True)
        for name in names:
            shutil.copyfile(root / KNOWLEDGE_DIR / name, checkout / REMOTE_DIR / name)
        _git(["add", "--", *(f"{REMOTE_DIR}/{n}" for n in names)], cwd=checkout)
        title, body = _pr_text(root, names, plan, project)
        _git(["commit", "-m", title, "-m", body], cwd=checkout)

        head = branch
        target = url
        if on_github and not gh.can_push(slug):
            fork = gh.fork(slug)
            target = f"https://github.com/{fork}.git"
            head = f"{fork.split('/')[0]}:{branch}"
        _git(["push", target, f"HEAD:refs/heads/{branch}"], cwd=checkout, github=on_github)
        pr_url = gh.create_pr(slug, head, default, title, body)

    state = load_state(root)
    for name in names:
        state.pushed[name] = _hash((root / KNOWLEDGE_DIR / name).read_bytes())
    save_state(root, state)
    return PushResult(plan, url=pr_url, branch=branch)
