"""Creates a project workspace from templates/project.

Template naming rules:
  name.tmpl   -> rendered with ${project_name}, ${paper_version}, ${java_minimum}; suffix dropped
  _gitignore  -> .gitignore (a real one inside the package would hide template files from git)
"""

import json
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from string import Template

from mcflow import manifest
from mcflow.project import CONFIG_NAME, ProjectConfig
from mcflow.versions import pins

RENAMES = {"_gitignore": ".gitignore"}


@dataclass(frozen=True)
class PlannedFile:
    path: PurePosixPath  # relative to the project root
    content: bytes


class WorkspaceConflict(Exception):
    def __init__(self, existing: list[PurePosixPath]):
        self.existing = existing
        super().__init__(f"{len(existing)} file(s) already exist")


def _walk(node: Traversable, prefix: PurePosixPath) -> list[tuple[PurePosixPath, Traversable]]:
    out = []
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        rel = prefix / child.name
        if child.is_dir():
            out.extend(_walk(child, rel))
        elif child.name != "__pycache__":
            out.append((rel, child))
    return out


def plan(config: ProjectConfig) -> list[PlannedFile]:
    values = {
        "project_name": config.name,
        "paper_version": config.paper_version,
        "java_minimum": str(config.java_minimum),
    }
    planned = [PlannedFile(PurePosixPath(CONFIG_NAME), config.to_toml().encode("utf-8"))]
    for rel, resource in _walk(files("mcflow").joinpath("templates/project"), PurePosixPath()):
        name = RENAMES.get(rel.name, rel.name)
        if name.endswith(".tmpl"):
            text = Template(resource.read_text(encoding="utf-8")).safe_substitute(values)
            planned.append(
                PlannedFile(rel.with_name(name.removesuffix(".tmpl")), text.encode("utf-8"))
            )
        elif name == ".mcp.json":
            planned.append(PlannedFile(rel.with_name(name), _mcp_json(resource.read_text("utf-8"))))
        else:
            planned.append(PlannedFile(rel.with_name(name), resource.read_bytes()))
    return planned


def _mcp_json(template: str) -> bytes:
    """Add mcflow-server once a release is pinned. `mcflow server mcp` checks the tarball's
    SHA-256 before running it (see mcflow.runtime); npx alone can't."""
    config = json.loads(template)
    server = pins().get("mcflow_server", {})
    if server.get("tarball_url"):
        config["mcpServers"]["mcflow"] = {"command": "mcflow", "args": ["server", "mcp"]}
    return (json.dumps(config, indent=2) + "\n").encode("utf-8")


def create(root: Path, config: ProjectConfig) -> list[PlannedFile]:
    """Write the workspace. Refuses to touch anything if even one target file exists."""
    planned = plan(config)
    existing = [f.path for f in planned if (root / f.path).exists()]
    if existing:
        raise WorkspaceConflict(existing)
    for f in planned:
        target = root / f.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f.content)
    manifest.save(
        root,
        {
            f.path.as_posix(): manifest.digest(f.content)
            for f in planned
            if manifest.is_managed(f.path)
        },
    )
    return planned
