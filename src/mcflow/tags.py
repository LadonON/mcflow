"""`mcflow tags`: symbols from files TokToken can't index, via universal-ctags and mcflow's optlibs.

TokToken 0.5.0 only indexes file extensions on its own list, so resource-pack JSON and .mcmeta, GLSL
shaders (.fsh/.vsh/.glsl) and YAML configs never reach its ctags step, and `extra_extensions` can't
add them (checked 2026-11-15). This runs universal-ctags directly with the definitions mcflow ships
in templates/project/.ctags.d/ and returns the symbols as JSON.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

Runner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]

# What `mcflow tags` looks at when given no paths: packs, plugin configs, shaders.
DEFAULT_GLOBS = ("resourcepacks/**/*", "plugins/*/src/main/resources/**/*")
EXTENSIONS = {".json", ".mcmeta", ".fsh", ".vsh", ".glsl", ".yml", ".yaml"}


class TagsError(Exception):
    pass


@dataclass
class Tag:
    name: str
    kind: str
    path: str
    line: int
    scope: str | None = None


def optlib_files() -> list[str]:
    """The optlib definitions shipped in the package (copied into each workspace's .ctags.d/)."""
    folder = files("mcflow").joinpath("templates/project/.ctags.d")
    return sorted(child.name for child in folder.iterdir() if child.name.endswith(".ctags"))


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def find_ctags() -> str:
    exe = shutil.which("ctags")
    if not exe:
        raise TagsError(
            "universal-ctags isn't on PATH. Run `mcflow doctor` for the install command."
        )
    return exe


def collect_paths(root: Path, given: list[str]) -> list[Path]:
    if given:
        found: list[Path] = []
        for g in given:
            p = (root / g).resolve()
            found += sorted(p.rglob("*")) if p.is_dir() else [p]
    else:
        found = [p for pattern in DEFAULT_GLOBS for p in sorted(root.glob(pattern))]
    return [p for p in found if p.is_file() and p.suffix.lower() in EXTENSIONS]


def parse(output: str, root: Path) -> list[Tag]:
    tags: list[Tag] = []
    for line in output.splitlines():
        if not line.startswith("{"):
            continue
        t = json.loads(line)
        if t.get("_type") != "tag" or str(t["name"]).isdigit():
            continue  # array indexes ("0", "1") are noise
        path = Path(t["path"])
        rel = path.resolve().relative_to(root.resolve()) if path.is_absolute() else path
        tags.append(
            Tag(t["name"], t.get("kind", ""), rel.as_posix(), int(t.get("line", 0)), t.get("scope"))
        )
    return tags


def run(root: Path, paths: list[str], query: str | None = None, runner: Runner = _run) -> list[Tag]:
    targets = collect_paths(root, paths)
    if not targets:
        return []
    with as_file(files("mcflow").joinpath("templates/project/.ctags.d")) as optdir:
        options = [f"--options={Path(optdir) / name}" for name in optlib_files()]
        cmd = [
            find_ctags(),
            "--options=NONE",
            *options,
            "--output-format=json",
            "--fields=+nKZ",
            "-f",
            "-",
        ]
        result = runner(
            cmd + [str(t.relative_to(root)) if t.is_relative_to(root) else str(t) for t in targets],
            root,
        )
    if result.returncode != 0 and not result.stdout:
        raise TagsError(f"ctags failed: {result.stderr.strip()[:500]}")
    tags = parse(result.stdout, root)
    if query:
        q = query.lower()
        tags = [t for t in tags if q in t.name.lower() or (t.scope and q in t.scope.lower())]
    return tags
