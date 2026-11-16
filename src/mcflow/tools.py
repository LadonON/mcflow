"""`mcflow tools install`: TokToken (all platforms) and universal-ctags (Windows), official builds.

Each download is checked against the SHA-256 pinned in versions.toml before anything is written.
On macOS and Linux, universal-ctags comes from the system package manager (`mcflow doctor` prints
the command), so only TokToken is installed there.
"""

from __future__ import annotations

import hashlib
import io
import os
import stat
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from mcflow import __version__
from mcflow.versions import pins

Fetch = Callable[[str], bytes]


class ToolsError(Exception):
    pass


@dataclass
class InstallResult:
    installed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"mcflow/{__version__}"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def default_dir() -> Path:
    return Path.home() / ".local" / "bin"


def _verified(name: str, url: str, sha256: str, fetch: Fetch) -> bytes:
    data = fetch(url)
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise ToolsError(
            f"{name} download failed its checksum (got {digest}, expected {sha256}). "
            "Nothing was installed."
        )
    return data


def _write(path: Path, data: bytes, executable: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    if executable:
        tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(tmp, path)  # atomic, and replaces an older version


def install_toktoken(dest: Path, os_name: str, machine: str, fetch: Fetch = _fetch) -> Path:
    pin = pins()["toktoken"]
    asset = pin["assets"].get(f"{os_name}-{machine}")
    if asset is None:
        supported = ", ".join(pin["assets"])
        raise ToolsError(f"TokToken has no build for {os_name}-{machine}. Supported: {supported}.")
    data = _verified("TokToken", pin["release_url"] + asset["file"], asset["sha256"], fetch)
    target = dest / ("toktoken.exe" if os_name == "windows" else "toktoken")
    _write(target, data, executable=os_name != "windows")
    return target


def install_ctags_windows(dest: Path, fetch: Fetch = _fetch) -> Path:
    pin = pins()["universal_ctags"]["windows"]
    data = _verified("universal-ctags", pin["url"], pin["sha256"], fetch)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if "ctags.exe" not in names:
            raise ToolsError("The universal-ctags archive has no ctags.exe at its root.")
        _write(dest / "ctags.exe", archive.read("ctags.exe"), executable=False)
        # Its licence (GPL-2.0) travels with the binary.
        for name in names:
            if name.startswith("license/") and not name.endswith("/"):
                _write(
                    dest / "universal-ctags-license" / Path(name).name, archive.read(name), False
                )
    return dest / "ctags.exe"


def install(
    dest: Path, os_name: str, machine: str, fetch: Fetch = _fetch, path_env: str | None = None
) -> InstallResult:
    result = InstallResult()
    result.installed.append(str(install_toktoken(dest, os_name, machine, fetch)))
    if os_name == "windows":
        result.installed.append(str(install_ctags_windows(dest, fetch)))
    else:
        result.skipped.append(
            "universal-ctags (install it with your package manager: see `mcflow doctor`)"
        )
    on_path = path_env if path_env is not None else os.environ.get("PATH", "")
    entries = {os.path.normcase(os.path.normpath(p)) for p in on_path.split(os.pathsep) if p}
    if os.path.normcase(os.path.normpath(str(dest))) not in entries:
        result.notes.append(
            f"{dest} isn't on PATH yet. Add it (pipx ensurepath does this), "
            "then open a new terminal."
        )
    return result
