"""Finds installed JDKs and works out which one a Paper version can use."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from mcflow.doctor.env import SystemEnv

_RELEASE_VERSION = re.compile(r'^JAVA_VERSION="([^"]+)"', re.MULTILINE)
_JAVA_HOME_PROPERTY = re.compile(r"^\s*java\.home = (.+)$", re.MULTILINE)


@dataclass
class Jdk:
    home: Path
    version: str
    origins: list[str] = field(default_factory=list)  # "JAVA_HOME", "PATH", "scan"

    @property
    def major(self) -> int:
        return java_major(self.version)


def java_major(version: str) -> int:
    """'25.0.2' -> 25, '1.8.0_382' -> 8, '17' -> 17."""
    parts = re.split(r"[._+-]", version)
    if parts[0] == "1" and len(parts) > 1:
        return int(parts[1])
    return int(parts[0])


def read_release(env: SystemEnv, home: Path) -> str | None:
    """Version from the `release` file every JDK ships in its home directory."""
    text = env.read_text(home / "release")
    if text is None:
        return None
    match = _RELEASE_VERSION.search(text)
    return match.group(1) if match else None


def scan_roots(env: SystemEnv) -> list[Path]:
    home = env.home
    common = [home / ".jdks", home / ".sdkman" / "candidates" / "java"]
    if env.os_name == "windows":
        vendors = [
            "Java",
            "Eclipse Adoptium",
            "Microsoft",
            "Zulu",
            "Amazon Corretto",
            "BellSoft",
            "Semeru",
        ]
        # Machine-wide installs, plus per-user installs (Temurin's "just for me" option)
        bases = [Path(env.environ.get("ProgramFiles", r"C:\Program Files"))]
        if local := env.environ.get("LOCALAPPDATA"):
            bases.append(Path(local) / "Programs")
        return [base / v for base in bases for v in vendors] + common
    if env.os_name == "macos":
        return [
            Path("/Library/Java/JavaVirtualMachines"),
            home / "Library" / "Java" / "JavaVirtualMachines",
            *common,
        ]
    return [Path("/usr/lib/jvm"), Path("/usr/java"), Path("/opt/java"), *common]


def _jdk_home_candidates(env: SystemEnv, root: Path) -> list[Path]:
    homes = []
    for d in env.subdirs(root):
        # macOS bundles keep the real home under Contents/Home
        mac_home = d / "Contents" / "Home"
        homes.append(mac_home if env.read_text(mac_home / "release") is not None else d)
    return homes


def path_java_home(env: SystemEnv) -> Path | None:
    """Ask the `java` on PATH where it lives. This sees through shims like Oracle's javapath."""
    if env.which("java") is None:
        return None
    code, out = env.run(["java", "-XshowSettings:properties", "-version"])
    if code != 0:
        return None
    match = _JAVA_HOME_PROPERTY.search(out)
    return Path(match.group(1).strip()) if match else None


def find_jdks(env: SystemEnv) -> list[Jdk]:
    found: dict[str, Jdk] = {}

    def add(home: Path, origin: str) -> None:
        version = read_release(env, home)
        if version is None:
            return
        key = str(home).rstrip("\\/").lower() if env.os_name == "windows" else str(home)
        if key in found:
            if origin not in found[key].origins:
                found[key].origins.append(origin)
        else:
            found[key] = Jdk(home=home, version=version, origins=[origin])

    if java_home := env.environ.get("JAVA_HOME"):
        add(Path(java_home), "JAVA_HOME")
    if home := path_java_home(env):
        add(home, "PATH")
    for root in scan_roots(env):
        for home in _jdk_home_candidates(env, root):
            add(home, "scan")
    return sorted(found.values(), key=lambda j: j.major, reverse=True)


def active_jdk(jdks: list[Jdk]) -> Jdk | None:
    """The JDK tools will pick up by default: JAVA_HOME first, then PATH."""
    for origin in ("JAVA_HOME", "PATH"):
        for jdk in jdks:
            if origin in jdk.origins:
                return jdk
    return None
