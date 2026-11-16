"""Refuse to tag a release of the Python package that can't work for users.

    python scripts/check_release.py v0.1.0     # in the release workflow, with the pushed tag
    python scripts/check_release.py            # anywhere: the checks that don't need a tag

Checks: the tag matches mcflow's version, the version isn't a dev release, and the runtime release
(client mod and mcflow-server) is pinned, since without those pins `init` can't register
mcflow-server and `client install` has nothing it may download.
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def problems(tag: str) -> list[str]:
    found = []
    init = (ROOT / "src" / "mcflow" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r'__version__ = "([^"]+)"', init).group(1)
    if tag and tag != f"v{version}":
        found.append(f"tag {tag} doesn't match mcflow's version {version}")
    if tag and ("dev" in version or not re.fullmatch(r"\d+\.\d+\.\d+((a|b|rc)\d+)?", version)):
        found.append(f"version {version} isn't a release version")
    pins = tomllib.loads((ROOT / "src" / "mcflow" / "versions.toml").read_text(encoding="utf-8"))
    server = pins.get("mcflow_server", {})
    if not (server.get("tarball_url") and server.get("sha256")):
        found.append("mcflow-server isn't pinned: run scripts/pin_runtime.py runtime-v<version>")
    mod = pins.get("client_mod", {})
    unpinned = set(mod.get("minecraft_versions", [])) - set(mod.get("sha256", {}))
    if not mod.get("release_url") or unpinned:
        found.append(
            f"the client mod isn't pinned for {len(unpinned)} Minecraft versions: "
            "run scripts/pin_runtime.py"
        )
    return found


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else ""
    issues = problems(tag)
    for issue in issues:
        print(f"release check: {issue}")
    if issues and tag:
        sys.exit(1)
    print("release checks passed" if not issues else "(not a release run, so not failing)")
