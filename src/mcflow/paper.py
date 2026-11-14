"""Paper versions: which exist, which Java each needs, and whether PaperMC still supports it.

Live data comes from PaperMC's Fill v3 API. A copy ships in data/paper_versions.json so that
`init` and `doctor` still work offline; refresh it with scripts/refresh_paper_cache.py.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from mcflow import __version__
from mcflow.versions import parse_version, pins

CACHE_RESOURCE = "data/paper_versions.json"


@dataclass(frozen=True)
class PaperVersion:
    id: str
    java_minimum: int
    supported: bool  # PaperMC's own support status, not mcflow's

    @property
    def key(self) -> tuple[int, ...]:
        return parse_version(self.id)


class UnsupportedPaperVersion(ValueError):
    pass


def minimum_version() -> tuple[int, ...]:
    return parse_version(pins()["paper"]["minimum_version"])


def from_fill_response(payload: dict[str, Any]) -> list[PaperVersion]:
    """Keep stable releases at or above mcflow's minimum, newest first."""
    floor = minimum_version()
    versions = []
    for entry in payload["versions"]:
        v = entry["version"]
        try:
            key = parse_version(v["id"])
        except ValueError:  # pre-releases and release candidates, e.g. "26.3-rc-3"
            continue
        if key < floor:
            continue
        versions.append(
            PaperVersion(
                id=v["id"],
                java_minimum=int(v["java"]["version"]["minimum"]),
                supported=v["support"]["status"] == "SUPPORTED",
            )
        )
    return sorted(versions, key=lambda p: p.key, reverse=True)


def fetch_live(timeout: float = 5.0) -> list[PaperVersion]:
    request = urllib.request.Request(
        pins()["paper"]["fill_api"],
        headers={"User-Agent": f"mcflow/{__version__}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return from_fill_response(json.load(response))


def load_cached() -> list[PaperVersion]:
    data = json.loads(files("mcflow").joinpath(CACHE_RESOURCE).read_text(encoding="utf-8"))
    return [PaperVersion(**v) for v in data["versions"]]


def available_versions(online: bool = True) -> tuple[list[PaperVersion], str]:
    """Return (versions, source) where source is "live" or "cached"."""
    if online:
        try:
            return fetch_live(), "live"
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError):
            pass
    return load_cached(), "cached"


def resolve(requested: str, versions: list[PaperVersion]) -> PaperVersion:
    """Turn a user's answer ("latest", "1.21.11") into a known Paper version, or explain why not."""
    requested = requested.strip().lower()
    if requested == "latest":
        return versions[0]
    try:
        key = parse_version(requested)
    except ValueError:
        raise UnsupportedPaperVersion(
            f"'{requested}' isn't a Paper release version. Use something like 1.21.11 or 'latest'."
        ) from None
    if key < minimum_version():
        raise UnsupportedPaperVersion(
            f"mcflow supports Paper {pins()['paper']['minimum_version']} and newer; "
            f"{requested} is too old."
        )
    for v in versions:
        if v.key == key:
            return v
    newest = versions[0].id if versions else "unknown"
    raise UnsupportedPaperVersion(
        f"Paper has no release called {requested}. The newest is {newest}."
    )


def recommended_java(java_minimum: int) -> int:
    """Lowest LTS release that satisfies the minimum (Paper 1.17 needs 16, so recommend 17)."""
    for lts in pins()["paper"]["java_lts"]:
        if lts >= java_minimum:
            return lts
    return java_minimum
