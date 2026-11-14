"""The mcflow.toml file at the root of every workspace made by `mcflow init`."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = "mcflow.toml"


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    paper_version: str
    java_minimum: int
    knowledge_repo: str

    def to_toml(self) -> str:
        return (
            "# mcflow workspace settings. Change paper_version with care: "
            "run `mcflow doctor` afterwards.\n\n"
            "[project]\n"
            f'name = "{_escape(self.name)}"\n\n'
            "[minecraft]\n"
            f'paper_version = "{self.paper_version}"\n'
            f"java_minimum = {self.java_minimum}\n\n"
            "[knowledge]\n"
            f'repo = "{self.knowledge_repo}"\n'
        )


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def find_project_root(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        if (directory / CONFIG_NAME).is_file():
            return directory
    return None


def load(root: Path) -> ProjectConfig:
    data = tomllib.loads((root / CONFIG_NAME).read_text(encoding="utf-8"))
    return ProjectConfig(
        name=data["project"]["name"],
        paper_version=data["minecraft"]["paper_version"],
        java_minimum=int(data["minecraft"]["java_minimum"]),
        knowledge_repo=data["knowledge"]["repo"],
    )
