"""Recognise a Paper (Paperclip) jar and read which Minecraft version it runs."""

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

_VERSIONS_LIST = "META-INF/versions.list"
_PAPERCLIP_PREFIX = "io/papermc/paperclip/"
_PAPER_JAR_NAME = re.compile(r"paper-(\d+(?:\.\d+)+)\.jar$")


class NotAPaperJar(ValueError):
    pass


@dataclass(frozen=True)
class PaperJar:
    path: Path
    minecraft_version: str


def inspect(path: Path) -> PaperJar:
    try:
        with zipfile.ZipFile(path) as jar:
            names = jar.namelist()
            if not any(n.startswith(_PAPERCLIP_PREFIX) for n in names):
                raise NotAPaperJar(f"{path.name} isn't a Paper jar (no Paperclip launcher inside).")
            if _VERSIONS_LIST not in names:
                raise NotAPaperJar(f"{path.name} looks like Paperclip but has no {_VERSIONS_LIST}.")
            listing = jar.read(_VERSIONS_LIST).decode("utf-8", errors="replace")
    except zipfile.BadZipFile:
        raise NotAPaperJar(f"{path.name} isn't a valid jar file.") from None

    for line in listing.splitlines():
        parts = line.strip().split("\t")
        if len(parts) == 3 and (match := _PAPER_JAR_NAME.search(parts[2])):
            return PaperJar(path, match.group(1))
    raise NotAPaperJar(f"Couldn't find the Minecraft version inside {path.name}.")


def find_in(server_dir: Path) -> list[Path]:
    """Jars directly in server/ that could be the Paper jar (plugins live in server/plugins/)."""
    return sorted(p for p in server_dir.glob("*.jar") if p.is_file())
