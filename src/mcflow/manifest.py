"""Which workspace files mcflow owns, and what it last wrote to each.

`mcflow init` records a hash of every managed file in `.mcflow/managed.json`; `mcflow update` uses
it to tell files the user edited (left alone) from files still as mcflow wrote them (safe to
replace). Everything else in a workspace (plugins, packs, research, knowledge, layouts, assets,
server, mcflow.toml, .gitignore) belongs to the user and is never touched by `update`.
"""

import hashlib
import json
from pathlib import Path, PurePosixPath

from mcflow import __version__

MANIFEST_FILE = Path(".mcflow") / "managed.json"
MANAGED_DIRS = (".claude/skills/", ".claude/agents/", ".ctags.d/")
MANAGED_FILES = {"CLAUDE.md", "AGENTS.md", ".mcp.json", ".toktoken.json"}


def is_managed(path: PurePosixPath) -> bool:
    text = path.as_posix()
    return text in MANAGED_FILES or text.startswith(MANAGED_DIRS)


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def load(root: Path) -> dict[str, str]:
    path = root / MANIFEST_FILE
    if not path.is_file():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("files", {}))


def save(root: Path, files: dict[str, str]) -> None:
    path = root / MANIFEST_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"mcflow_version": __version__, "files": dict(sorted(files.items()))}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
