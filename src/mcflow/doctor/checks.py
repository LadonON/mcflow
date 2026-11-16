"""Doctor checks. Each returns a CheckResult, with an exact fix when something's wrong."""

import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from mcflow.doctor import java
from mcflow.doctor.env import SystemEnv
from mcflow.paper import PaperVersion, recommended_java
from mcflow.versions import pins


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    name: str
    status: Status
    summary: str
    fix: str | None = None


@dataclass
class DoctorContext:
    paper: PaperVersion | None  # None when doctor runs outside an mcflow project
    paper_source: str = "cached"
    project_root: Path | None = None


Check = Callable[[SystemEnv, DoctorContext], CheckResult]

_VERSION = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def _per_os(env: SystemEnv, windows: str, macos: str, linux: str) -> str:
    return {"windows": windows, "macos": macos}.get(env.os_name, linux)


def java_install_hint(env: SystemEnv, major: int) -> str:
    return _per_os(
        env,
        windows=f"winget install EclipseAdoptium.Temurin.{major}.JDK",
        macos=f"brew install --cask temurin@{major}",
        linux=(
            f"Debian/Ubuntu: sudo apt-get install openjdk-{major}-jdk\n"
            f"Fedora/RHEL:   sudo dnf install java-{major}-openjdk-devel\n"
            "If your distro doesn't package it: https://adoptium.net/installation/linux/"
        ),
    )


def java_home_hint(env: SystemEnv, jdk: java.Jdk) -> str:
    return _per_os(
        env,
        windows=f'setx JAVA_HOME "{jdk.home}"   (then open a new terminal)',
        macos=f'export JAVA_HOME="{jdk.home}"   (add it to ~/.zshrc to keep it)',
        linux=f'export JAVA_HOME="{jdk.home}"   (add it to ~/.bashrc to keep it)',
    )


def check_paper_version(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    name = "Paper version"
    if ctx.paper is None:
        return CheckResult(
            name,
            Status.WARN,
            "Not inside an mcflow project, so there's no target Paper version.",
            "Run doctor from a project made by `mcflow init`, or pass --paper-version.",
        )
    note = "" if ctx.paper_source == "live" else " (offline: using mcflow's cached version list)"
    if ctx.paper.supported:
        return CheckResult(name, Status.OK, f"Paper {ctx.paper.id}, supported by PaperMC{note}")
    return CheckResult(
        name,
        Status.WARN,
        f"Paper {ctx.paper.id} works with mcflow, but PaperMC no longer ships fixes for it{note}.",
    )


def check_java(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    name = "Java"
    jdks = java.find_jdks(env)
    if ctx.paper is None:
        if not jdks:
            return CheckResult(
                name,
                Status.WARN,
                "No JDK found.",
                java_install_hint(env, pins()["paper"]["java_lts"][-1]),
            )
        listing = ", ".join(f"{j.major} ({j.home})" for j in jdks)
        return CheckResult(
            name,
            Status.WARN,
            f"Found JDKs: {listing}. Can't say which one you need without a Paper version.",
        )

    need = ctx.paper.java_minimum
    want = recommended_java(need)
    suitable = [j for j in jdks if j.major >= need]
    active = java.active_jdk(jdks)
    requirement = f"Paper {ctx.paper.id} needs Java {need}+"

    if active and active.major >= need:
        return CheckResult(
            name, Status.OK, f"Java {active.version} at {active.home}. {requirement}."
        )
    if suitable:
        pick = min(suitable, key=lambda j: j.major)
        if active is None:
            current = "no Java is on PATH"
        elif "JAVA_HOME" in active.origins:
            current = f"JAVA_HOME points to Java {active.major}"
        else:
            current = f"the java on PATH is Java {active.major}"
        return CheckResult(
            name,
            Status.WARN,
            f"{requirement}; Java {pick.version} is installed at {pick.home}, but {current}.",
            "Point JAVA_HOME at it:\n" + java_home_hint(env, pick),
        )
    found = ", ".join(str(j.major) for j in jdks) or "none"
    return CheckResult(
        name,
        Status.FAIL,
        f"{requirement}. Installed JDKs: {found}.",
        f"Install Java {want}:\n" + java_install_hint(env, want),
    )


def check_node(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    name = "Node.js"
    minimum = pins()["node"]["minimum_major"]
    fix = _per_os(
        env,
        "winget install OpenJS.NodeJS.LTS",
        "brew install node",
        "Install the LTS release from https://nodejs.org/en/download",
    )
    if env.which("node") is None:
        return CheckResult(name, Status.FAIL, "Not installed.", fix)
    _, out = env.run(["node", "--version"])
    match = _VERSION.search(out)
    if not match:
        return CheckResult(
            name, Status.FAIL, f"Couldn't read the version from {out.strip()!r}.", fix
        )
    if int(match.group(1)) < minimum:
        return CheckResult(
            name, Status.FAIL, f"Node {match.group(0)} is too old; mcflow needs {minimum}+.", fix
        )
    return CheckResult(name, Status.OK, f"Node {match.group(0)}")


def check_ctags(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    name = "universal-ctags"
    pin = pins()["universal_ctags"]
    fix = _per_os(
        env,
        windows="mcflow tools install   (or: winget install UniversalCtags.Ctags)",
        macos="brew install universal-ctags",
        linux=(
            "Debian/Ubuntu: sudo apt-get install -y universal-ctags\n"
            "Fedora/RHEL:   sudo dnf install universal-ctags\n"
            "Arch:          sudo pacman -S ctags"
        ),
    )
    if env.which("ctags") is None:
        return CheckResult(name, Status.FAIL, "Not installed. TokToken needs it.", fix)
    _, out = env.run(["ctags", "--version"])
    first_line = out.strip().splitlines()[0] if out.strip() else ""
    if pin["version_marker"] in first_line:
        return CheckResult(name, Status.OK, first_line)
    if pin["rejected_marker"] in first_line:
        return CheckResult(
            name,
            Status.FAIL,
            "Found Exuberant Ctags, which TokToken can't use.",
            "Uninstall it (or put universal-ctags first on PATH), then:\n" + fix,
        )
    return CheckResult(name, Status.FAIL, f"`ctags` isn't universal-ctags: {first_line!r}", fix)


def check_toktoken(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    name = "TokToken"
    pin = pins()["toktoken"]
    platform_key = f"{env.os_name}-{env.machine}"
    asset = pin["assets"].get(platform_key)
    if asset is None:
        supported = ", ".join(pin["assets"])
        return CheckResult(
            name,
            Status.FAIL,
            f"TokToken has no build for {platform_key}. Supported: {supported}.",
            "Code indexing won't be available on this machine. The rest of mcflow still works.",
        )
    url = pin["release_url"] + asset["file"]
    install_dir = _per_os(env, r"%USERPROFILE%\.local\bin", "~/.local/bin", "~/.local/bin")
    exe = "toktoken.exe" if env.os_name == "windows" else "toktoken (then chmod +x it)"
    fix = (
        "Run: mcflow tools install\n"
        f"(or by hand: download {url}, check its SHA-256 is {asset['sha256']}, "
        f"and save it as {exe} in {install_dir}, on PATH)"
    )
    if env.which("toktoken") is None:
        return CheckResult(name, Status.FAIL, "Not installed.", fix)
    _, out = env.run(["toktoken", "--version"])
    match = _VERSION.search(out)
    if match is None:
        return CheckResult(
            name, Status.FAIL, f"Couldn't read the version from {out.strip()!r}.", fix
        )
    if match.group(0) != pin["version"]:
        return CheckResult(
            name,
            Status.WARN,
            f"TokToken {match.group(0)} is installed; mcflow is tested with {pin['version']}.",
            fix,
        )
    return CheckResult(name, Status.OK, f"TokToken {match.group(0)}")


def check_claude(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    name = "Claude Code"
    fix = _per_os(
        env,
        "irm https://claude.ai/install.ps1 | iex   (in PowerShell)",
        "curl -fsSL https://claude.ai/install.sh | bash",
        "curl -fsSL https://claude.ai/install.sh | bash",
    )
    if env.which("claude") is None:
        return CheckResult(name, Status.FAIL, "Not installed.", fix)
    _, out = env.run(["claude", "--version"])
    return CheckResult(name, Status.OK, out.strip().splitlines()[0] if out.strip() else "installed")


def check_git(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    name = "git"
    fix = _per_os(
        env,
        "winget install Git.Git",
        "xcode-select --install",
        "Install git with your package manager, e.g. sudo apt-get install git",
    )
    if env.which("git") is None:
        return CheckResult(name, Status.FAIL, "Not installed.", fix)
    _, out = env.run(["git", "--version"])
    return CheckResult(name, Status.OK, out.strip())


def check_gh(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    name = "GitHub CLI"
    fix = _per_os(
        env,
        "winget install GitHub.cli",
        "brew install gh",
        "See https://github.com/cli/cli/blob/trunk/docs/install_linux.md",
    )
    if env.which("gh") is None:
        return CheckResult(
            name,
            Status.WARN,
            "Not installed. Only needed to share knowledge (`mcflow kb push`).",
            fix,
        )
    code, _ = env.run(["gh", "auth", "status"])
    if code != 0:
        return CheckResult(
            name,
            Status.WARN,
            "Installed but not signed in. `mcflow kb push` needs this.",
            "gh auth login",
        )
    return CheckResult(name, Status.OK, "Installed and signed in")


def check_client_mod(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    """mcflow's Fabric client mod is required: screenshots and in-game checks depend on it."""
    name = "mcflow client mod"
    if ctx.project_root is None:
        return CheckResult(
            name, Status.WARN, "Not inside an mcflow project; can't check the client mod."
        )
    fix = (
        "Close Minecraft, then run: mcflow client install   "
        "(add a folder for Prism or a custom path)"
    )
    state = ctx.project_root / ".mcflow" / "client.toml"
    if not state.is_file():
        return CheckResult(
            name,
            Status.FAIL,
            "Not installed. The workflow can't check anything in-game without it.",
            fix,
        )
    client = tomllib.loads(state.read_text(encoding="utf-8"))["client"]
    mods = Path(client["game_dir"]) / "mods"
    jars = sorted(mods.glob("mcflow-client-*.jar")) if mods.is_dir() else []
    if not jars:
        return CheckResult(name, Status.FAIL, f"The mod is missing from {mods}.", fix)
    if ctx.paper and client.get("minecraft_version") != ctx.paper.id:
        return CheckResult(
            name,
            Status.FAIL,
            f"Installed for Minecraft {client.get('minecraft_version')}, "
            f"but the project targets {ctx.paper.id}.",
            fix,
        )
    return CheckResult(name, Status.OK, f"{jars[-1].name} in {mods}")


def check_bots(env: SystemEnv, ctx: DoctorContext) -> CheckResult:
    """Test bots (mineflayer) speak up to one Minecraft version; newer servers need ViaBackwards."""
    name = "Test bots"
    bots = pins()["bots"]
    latest = bots["mineflayer_latest"]
    if ctx.paper is None or ctx.project_root is None:
        return CheckResult(name, Status.WARN, "Not inside an mcflow project; can't check.")
    if ctx.paper.key <= tuple(int(x) for x in latest.split(".")):
        return CheckResult(
            name, Status.OK, f"mineflayer {bots['mineflayer']} speaks {ctx.paper.id}"
        )
    plugins = ctx.project_root / "server" / "plugins"
    if any(plugins.glob("ViaBackwards-*.jar")):
        return CheckResult(
            name,
            Status.OK,
            f"Bots join as {latest} (mineflayer's newest); "
            f"ViaBackwards translates for {ctx.paper.id}",
        )
    return CheckResult(
        name,
        Status.FAIL,
        f"Bots speak up to {latest}, and this {ctx.paper.id} server has no ViaBackwards, "
        "so they can't join.",
        "Run: mcflow server setup   (it installs ViaBackwards)",
    )


ALL_CHECKS: list[Check] = [
    check_paper_version,
    check_java,
    check_node,
    check_ctags,
    check_toktoken,
    check_claude,
    check_git,
    check_gh,
    check_client_mod,
    check_bots,
]
