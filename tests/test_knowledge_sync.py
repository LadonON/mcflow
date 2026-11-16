"""kb pull / kb push against a real local git repo standing in for the shared GitHub repo."""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from mcflow.knowledge import sync

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

SLUG = "LadonON/mcflow-knowledge"


def entry_text(title: str, versions: str = '["26.3"]', body: str = "How to do it.") -> str:
    return (
        f'---\ntitle: "{title}"\nminecraft_versions: {versions}\npaper_api_version: "26.3"\n'
        f'verified_by: "SomeTest"\nsources:\n  - "https://docs.papermc.io/"\n'
        f"date: 2026-11-15\n---\n\n# {title}\n\n{body}\n"
    )


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout.strip()


@pytest.fixture(autouse=True)
def git_identity(monkeypatch):
    for key in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(key, "mcflow test")
    for key in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(key, "test@example.invalid")


class SharedRepo:
    """A bare repo plus a working clone used to play the reviewer who merges entries."""

    def __init__(self, base: Path):
        self.bare = base / "shared.git"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.bare)], check=True)
        self.work = base / "reviewer"
        subprocess.run(["git", "clone", str(self.bare), str(self.work)], check=True)
        git(self.work, "checkout", "-b", "main")
        (self.work / "entries").mkdir()
        (self.work / "entries" / ".gitkeep").write_text("")
        self.commit("start")

    @property
    def url(self) -> str:
        return str(self.bare)

    def put(self, name: str, text: str) -> None:
        (self.work / "entries" / name).write_text(text, encoding="utf-8")
        self.commit(f"add {name}")

    def commit(self, message: str) -> None:
        git(self.work, "add", "-A")
        git(self.work, "commit", "-m", message)
        git(self.work, "push", "origin", "HEAD:main")

    def merge_branch(self, branch: str) -> None:
        git(self.work, "fetch", "origin", branch)
        git(self.work, "merge", "--ff-only", "FETCH_HEAD")
        git(self.work, "push", "origin", "HEAD:main")

    def branches(self) -> list[str]:
        out = git(self.bare, "for-each-ref", "--format=%(refname:short)", "refs/heads")
        return out.splitlines()


@pytest.fixture
def shared(tmp_path) -> SharedRepo:
    return SharedRepo(tmp_path)


@pytest.fixture
def workspace(tmp_path) -> Path:
    root = tmp_path / "ws"
    (root / "knowledge").mkdir(parents=True)
    (root / "knowledge" / "README.md").write_text("readme")
    return root


def local(workspace: Path, name: str) -> Path:
    return workspace / "knowledge" / name


class FakeGitHub(sync.GitHub):
    def __init__(self, can_push: bool = True):
        self.push_allowed = can_push
        self.prs: list[dict] = []
        self.forks: list[str] = []

    def can_push(self, slug):
        return self.push_allowed

    def fork(self, slug):
        self.forks.append(slug)
        return "someone/mcflow-knowledge"

    def create_pr(self, slug, head, base, title, body):
        self.prs.append({"slug": slug, "head": head, "base": base, "title": title, "body": body})
        return f"https://github.com/{slug}/pull/{len(self.prs)}"


def push(workspace, shared, gh=None, **kw):
    gh = gh or FakeGitHub()
    now = kw.pop("now", datetime(2026, 11, 16, 9, 0, 0))
    return sync.push(workspace, shared.url, SLUG, "Shiny Swords", github=gh, now=now, **kw), gh


# --- pull --------------------------------------------------------------------------------------


def test_resolve_remote():
    assert sync.resolve_remote(SLUG) == (f"https://github.com/{SLUG}.git", SLUG)
    assert sync.resolve_remote("/some/path.git") == ("/some/path.git", None)


def test_pull_adds_new_entries_and_records_them(workspace, shared):
    shared.put("font-ui.md", entry_text("Font UI"))
    result = sync.pull(workspace, shared.url)
    assert result.added == ["font-ui.md"]
    assert local(workspace, "font-ui.md").read_text(encoding="utf-8") == entry_text("Font UI")
    assert "font-ui.md" in sync.load_state(workspace).base
    assert sync.pull(workspace, shared.url).unchanged == ["font-ui.md"]


def test_pull_updates_entries_you_did_not_edit(workspace, shared):
    shared.put("font-ui.md", entry_text("Font UI"))
    sync.pull(workspace, shared.url)
    shared.put("font-ui.md", entry_text("Font UI", body="Better."))
    result = sync.pull(workspace, shared.url)
    assert result.updated == ["font-ui.md"]
    assert "Better." in local(workspace, "font-ui.md").read_text(encoding="utf-8")


def test_pull_keeps_your_edit_when_the_shared_copy_did_not_move(workspace, shared):
    shared.put("font-ui.md", entry_text("Font UI"))
    sync.pull(workspace, shared.url)
    local(workspace, "font-ui.md").write_text(entry_text("Font UI", body="Mine."), encoding="utf-8")
    result = sync.pull(workspace, shared.url)
    assert result.kept_local == ["font-ui.md"]
    assert "Mine." in local(workspace, "font-ui.md").read_text(encoding="utf-8")


def test_pull_reports_conflicts_without_overwriting(workspace, shared):
    shared.put("font-ui.md", entry_text("Font UI"))
    sync.pull(workspace, shared.url)
    local(workspace, "font-ui.md").write_text(entry_text("Font UI", body="Mine."), encoding="utf-8")
    shared.put("font-ui.md", entry_text("Font UI", body="Theirs."))
    result = sync.pull(workspace, shared.url)
    [(name, saved)] = result.conflicts
    assert name == "font-ui.md"
    assert "Mine." in local(workspace, "font-ui.md").read_text(encoding="utf-8")
    assert "Theirs." in saved.read_text(encoding="utf-8")
    assert saved.is_relative_to(workspace / ".mcflow")


def test_pull_treats_an_unknown_local_file_that_differs_as_a_conflict(workspace, shared):
    local(workspace, "font-ui.md").write_text(entry_text("Font UI", body="Mine."), encoding="utf-8")
    shared.put("font-ui.md", entry_text("Font UI"))
    assert [n for n, _ in sync.pull(workspace, shared.url).conflicts] == ["font-ui.md"]


def test_pull_leaves_entries_you_deleted_deleted(workspace, shared):
    shared.put("font-ui.md", entry_text("Font UI"))
    sync.pull(workspace, shared.url)
    local(workspace, "font-ui.md").unlink()
    result = sync.pull(workspace, shared.url)
    assert result.deleted_here == ["font-ui.md"]
    assert not local(workspace, "font-ui.md").exists()


def test_pull_skips_invalid_shared_entries(workspace, shared):
    shared.put("broken.md", "no frontmatter")
    result = sync.pull(workspace, shared.url)
    assert [n for n, _ in result.invalid_upstream] == ["broken.md"]
    assert not local(workspace, "broken.md").exists()


def test_pull_reports_entries_removed_upstream_but_keeps_them(workspace, shared):
    shared.put("font-ui.md", entry_text("Font UI"))
    sync.pull(workspace, shared.url)
    (shared.work / "entries" / "font-ui.md").unlink()
    shared.commit("remove")
    result = sync.pull(workspace, shared.url)
    assert result.removed_upstream == ["font-ui.md"]
    assert local(workspace, "font-ui.md").exists()


def test_pull_from_a_missing_repo_is_a_clear_error(workspace, tmp_path):
    with pytest.raises(sync.KbError, match="git clone"):
        sync.pull(workspace, str(tmp_path / "nope.git"))


# --- push --------------------------------------------------------------------------------------


def test_push_opens_a_pull_request_from_a_new_branch(workspace, shared):
    local(workspace, "font-ui.md").write_text(entry_text("Font UI"), encoding="utf-8")
    result, gh = push(workspace, shared)
    assert result.url == f"https://github.com/{SLUG}/pull/1"
    assert result.branch == "kb/shiny-swords-20261116-090000"
    [pr] = gh.prs
    assert pr["base"] == "main" and pr["head"] == result.branch
    assert pr["title"] == "Knowledge: Font UI"
    assert "font-ui.md" in pr["body"] and "SomeTest" in pr["body"]
    assert set(shared.branches()) == {"main", result.branch}
    # main is untouched until a reviewer merges
    assert git(shared.bare, "ls-tree", "--name-only", "main", "entries/") == "entries/.gitkeep"
    branch_files = git(shared.bare, "ls-tree", "--name-only", result.branch, "entries/")
    assert "entries/font-ui.md" in branch_files.splitlines()


def test_push_does_not_propose_the_same_change_twice(workspace, shared):
    local(workspace, "font-ui.md").write_text(entry_text("Font UI"), encoding="utf-8")
    push(workspace, shared)
    result, gh = push(workspace, shared, now=datetime(2026, 11, 16, 9, 5))
    assert result.url is None and gh.prs == []
    assert result.plan.already_proposed == ["font-ui.md"]


def test_after_merge_and_pull_nothing_is_pending(workspace, shared):
    local(workspace, "font-ui.md").write_text(entry_text("Font UI"), encoding="utf-8")
    result, _ = push(workspace, shared)
    shared.merge_branch(result.branch)
    assert sync.pull(workspace, shared.url).unchanged == ["font-ui.md"]
    state = sync.load_state(workspace)
    assert state.pushed == {} and "font-ui.md" in state.base
    again, gh = push(workspace, shared, now=datetime(2026, 11, 16, 10, 0))
    assert again.plan.to_send == [] and gh.prs == []


def test_push_sends_edits_but_not_entries_that_are_merely_behind(workspace, shared):
    shared.put("a.md", entry_text("A"))
    shared.put("b.md", entry_text("B"))
    sync.pull(workspace, shared.url)
    local(workspace, "a.md").write_text(entry_text("A", body="Improved."), encoding="utf-8")
    shared.put("b.md", entry_text("B", body="Newer upstream."))
    result, gh = push(workspace, shared)
    assert result.plan.changed == ["a.md"]
    assert result.plan.behind == ["b.md"]
    assert len(gh.prs) == 1


def test_push_refuses_invalid_entries_and_sends_nothing(workspace, shared):
    local(workspace, "good.md").write_text(entry_text("Good"), encoding="utf-8")
    local(workspace, "bad.md").write_text("no frontmatter", encoding="utf-8")
    with pytest.raises(sync.KbError, match=r"bad.md"):
        push(workspace, shared)
    assert shared.branches() == ["main"]


def test_push_only_named_entries(workspace, shared):
    local(workspace, "a.md").write_text(entry_text("A"), encoding="utf-8")
    local(workspace, "b.md").write_text(entry_text("B"), encoding="utf-8")
    result, _ = push(workspace, shared, only=["b"])
    assert result.plan.to_send == ["b.md"]
    with pytest.raises(sync.KbError, match="Not in knowledge"):
        push(workspace, shared, only=["nope"])


def test_push_respects_a_no_from_the_confirm_step(workspace, shared):
    local(workspace, "a.md").write_text(entry_text("A"), encoding="utf-8")
    result, gh = push(workspace, shared, confirm=lambda plan: False)
    assert result.url is None and gh.prs == []
    assert shared.branches() == ["main"]
    assert sync.load_state(workspace).pushed == {}


def test_push_with_several_entries_names_the_project(workspace, shared):
    local(workspace, "a.md").write_text(entry_text("A"), encoding="utf-8")
    local(workspace, "b.md").write_text(entry_text("B"), encoding="utf-8")
    _, gh = push(workspace, shared)
    assert gh.prs[0]["title"] == "Knowledge: 2 entries from Shiny Swords"


def test_push_without_write_access_goes_through_a_fork(workspace, shared, monkeypatch):
    local(workspace, "a.md").write_text(entry_text("A"), encoding="utf-8")
    pushed_to: list[str] = []
    real_git = sync._git

    def spy(args, cwd=None, github=False):
        if args[0] == "push":
            pushed_to.append(args[1])
            args = [args[0], shared.url, *args[2:]]  # the fork stands in for the shared repo here
        return real_git(args, cwd, github)

    monkeypatch.setattr(sync, "_git", spy)
    gh = FakeGitHub(can_push=False)
    # can_push is only asked for GitHub URLs; clone the local stand-in instead of github.com
    real_clone = sync.clone
    monkeypatch.setattr(sync, "clone", lambda url, dest: real_clone(shared.url, dest))
    result = sync.push(
        workspace,
        "https://github.com/" + SLUG + ".git",
        SLUG,
        "Shiny Swords",
        github=gh,
        now=datetime(2026, 11, 16, 9, 0),
    )
    assert gh.forks == [SLUG]
    assert pushed_to == ["https://github.com/someone/mcflow-knowledge.git"]
    assert gh.prs[0]["head"] == f"someone:{result.branch}"
