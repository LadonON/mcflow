"""`mcflow server mcp`: run the pinned mcflow-server release, checked against its SHA-256.

Workspaces register mcflow-server in `.mcp.json` as `mcflow server mcp`, not as `npx -y <url>`,
because npx can't check a download against a checksum. This downloads the tarball from the pinned
runtime release once, keeps it in mcflow's cache folder only if its SHA-256 matches
`versions.toml`, then runs it with npx. The tarball's npm-shrinkwrap.json locks every dependency.

stdout belongs to the MCP protocol, so everything this prints goes to stderr.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

from mcflow import __version__
from mcflow.platforms import current_os
from mcflow.versions import pins

Fetch = Callable[[str], bytes]


class RuntimeMissing(Exception):
    pass


def cache_dir() -> Path:
    os_name = current_os()
    if os_name == "windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "mcflow" / "cache"
    if os_name == "macos":
        return Path.home() / "Library" / "Caches" / "mcflow"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mcflow"


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"mcflow/{__version__}"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_tarball(
    pin: dict | None = None, cache: Path | None = None, fetch: Fetch = _fetch
) -> Path:
    """The pinned tarball in the cache, downloading and checking it first if needed."""
    pin = pins()["mcflow_server"] if pin is None else pin
    url, expected = pin.get("tarball_url", ""), pin.get("sha256", "")
    if not url or not expected:
        raise RuntimeMissing(
            "mcflow-server hasn't been released yet, so there's nothing pinned to run."
        )
    target = (cache or cache_dir()) / "mcflow-server" / url.rsplit("/", 1)[-1]
    if target.is_file() and _sha256(target.read_bytes()) == expected:
        return target
    print(f"mcflow: downloading {url}", file=sys.stderr)
    data = fetch(url)
    if _sha256(data) != expected:
        raise RuntimeMissing(
            f"The mcflow-server download from {url} failed its checksum. Nothing was run."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    partial.write_bytes(data)
    partial.replace(target)
    return target


def npx_command(tarball: Path, npx: str) -> list[str]:
    # A relative path, run from the cache folder: on Windows npx is a .cmd file, and cmd.exe
    # mangles a quoted program path followed by a quoted argument (paths with spaces).
    return [npx, "-y", f"./{tarball.name}"]


def run(project_root: Path, pin: dict | None = None, fetch: Fetch = _fetch) -> int:
    npx = shutil.which("npx")
    if npx is None:
        raise RuntimeMissing("npx isn't on PATH. Install Node.js 22 or newer (`mcflow doctor`).")
    tarball = ensure_tarball(pin, fetch=fetch)
    env = {**os.environ, "MCFLOW_PROJECT": str(project_root)}
    return subprocess.run(npx_command(tarball, npx), cwd=tarball.parent, env=env).returncode
