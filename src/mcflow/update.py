"""`mcflow update`: bring a workspace's skills, agents and workflow files up to this mcflow's.

Per managed file (see mcflow.manifest):
- unchanged since mcflow wrote it  -> replaced with the new version
- edited by the user               -> left alone; the diff to the new version is shown
- deleted by the user              -> stays deleted
- new in this mcflow               -> added
- dropped from this mcflow         -> removed if unedited, otherwise kept and reported

Workspaces made before the manifest existed have no record, so any file that differs from the
new version counts as edited. `--take` accepts the new version of a named file anyway.
"""

import difflib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from mcflow import manifest, scaffold
from mcflow.project import ProjectConfig


@dataclass
class Edited:
    path: str
    diff: str


@dataclass
class UpdateResult:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    edited: list[Edited] = field(default_factory=list)
    taken: list[str] = field(default_factory=list)
    deleted_by_user: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    kept_removed: list[str] = field(default_factory=list)

    @property
    def changes(self) -> int:
        return len(self.added) + len(self.updated) + len(self.taken) + len(self.removed)


def _diff(path: str, old: bytes, new: bytes) -> str:
    def lines(data: bytes) -> list[str]:
        return data.decode("utf-8", errors="replace").replace("\r\n", "\n").splitlines(True)

    return "".join(
        difflib.unified_diff(
            lines(old), lines(new), f"{path} (yours)", f"{path} (mcflow's new version)"
        )
    )


def run(
    root: Path, config: ProjectConfig, take: set[str] | None = None, dry_run: bool = False
) -> UpdateResult:
    take = {PurePosixPath(t.replace("\\", "/")).as_posix() for t in (take or set())}
    recorded = manifest.load(root)
    new_record: dict[str, str] = {}
    result = UpdateResult()
    planned = {
        f.path.as_posix(): f.content for f in scaffold.plan(config) if manifest.is_managed(f.path)
    }

    def write(rel: str, content: bytes) -> None:
        if not dry_run:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    for rel, content in sorted(planned.items()):
        target = root / rel
        new_hash = manifest.digest(content)
        base = recorded.get(rel)
        if not target.exists():
            if base is not None and rel not in take:
                result.deleted_by_user.append(rel)
                new_record[rel] = base
                continue
            write(rel, content)
            result.added.append(rel)
            new_record[rel] = new_hash
            continue
        current = target.read_bytes()
        current_hash = manifest.digest(current)
        if current_hash == new_hash:
            result.unchanged.append(rel)
            new_record[rel] = new_hash
        elif current_hash == base:
            write(rel, content)
            result.updated.append(rel)
            new_record[rel] = new_hash
        elif rel in take:
            write(rel, content)
            result.taken.append(rel)
            new_record[rel] = new_hash
        else:
            result.edited.append(Edited(rel, _diff(rel, current, content)))
            if base is not None:
                new_record[rel] = base

    for rel, base in sorted(recorded.items()):
        if rel in planned:
            continue
        target = root / rel
        if not target.exists():
            continue
        if manifest.digest(target.read_bytes()) == base or rel in take:
            if not dry_run:
                target.unlink()
            result.removed.append(rel)
        else:
            result.kept_removed.append(rel)

    if not dry_run:
        manifest.save(root, new_record)
    return result
