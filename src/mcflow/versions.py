"""Loads the pinned versions in versions.toml."""

import tomllib
from functools import cache
from importlib.resources import files
from typing import Any


@cache
def pins() -> dict[str, Any]:
    return tomllib.loads(files("mcflow").joinpath("versions.toml").read_text(encoding="utf-8"))


def parse_version(text: str) -> tuple[int, ...]:
    """'1.21.11' -> (1, 21, 11). Raises ValueError for anything that isn't dotted integers."""
    parts = text.strip().split(".")
    if not all(p.isdigit() for p in parts):
        raise ValueError(f"not a release version: {text!r}")
    return tuple(int(p) for p in parts)
