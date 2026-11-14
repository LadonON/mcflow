"""`.mcflow/local.toml`: machine-specific settings and secrets, git-ignored.

mcflow-server (the MCP server) reads this file to find Java, the ports and the RCON password.
"""

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

LOCAL_DIR = ".mcflow"
LOCAL_FILE = "local.toml"


@dataclass(frozen=True)
class LocalSettings:
    java: str  # absolute path to the java executable that runs the server
    paper_jar: str  # file name inside server/
    server_port: int
    rcon_port: int
    rcon_password: str
    pack_port: int  # local HTTP server for the resource pack

    def to_toml(self) -> str:
        lines = [
            "# Written by `mcflow server setup`. Machine-specific; never commit this file.",
            "[server]",
        ]
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, int):
                lines.append(f"{f.name} = {value}")
            else:
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{f.name} = "{escaped}"')
        return "\n".join(lines) + "\n"


def path_for(root: Path) -> Path:
    return root / LOCAL_DIR / LOCAL_FILE


def load(root: Path) -> LocalSettings | None:
    path = path_for(root)
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))["server"]
    return LocalSettings(**{f.name: data[f.name] for f in fields(LocalSettings)})


def save(root: Path, settings: LocalSettings) -> Path:
    path = path_for(root)
    path.parent.mkdir(exist_ok=True)
    path.write_text(settings.to_toml(), encoding="utf-8")
    return path
