"""`mcflow server setup`: turn server/ into a local-only test server (spec section 3)."""

import hashlib
import secrets
import socket
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from mcflow import __version__
from mcflow.doctor import java
from mcflow.doctor.env import SystemEnv
from mcflow.project import ProjectConfig
from mcflow.testserver import local, paperjar, properties
from mcflow.versions import pins

Fetch = Callable[[str], bytes]


class SetupError(Exception):
    pass


@dataclass
class SetupResult:
    settings: local.LocalSettings
    jar: paperjar.PaperJar
    java_version: str
    viaversion: str  # "installed", "already installed"
    eula_accepted: bool
    notes: list[str] = field(default_factory=list)


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"mcflow/{__version__}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def free_port(preferred: int) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return s.getsockname()[1]
    raise SetupError("No free local port available.")


def find_paper_jar(server_dir: Path, expected_version: str) -> paperjar.PaperJar:
    candidates = paperjar.find_in(server_dir)
    if not candidates:
        raise SetupError(
            f"No jar in {server_dir}. Download Paper {expected_version} from "
            "https://papermc.io/downloads/paper and put it in that folder."
        )
    problems, found = [], []
    for path in candidates:
        try:
            found.append(paperjar.inspect(path))
        except paperjar.NotAPaperJar as e:
            problems.append(str(e))
    matching = [j for j in found if j.minecraft_version == expected_version]
    if len(matching) == 1:
        return matching[0]
    if len(matching) > 1:
        names = ", ".join(j.path.name for j in matching)
        raise SetupError(
            f"More than one Paper {expected_version} jar in server/: {names}. Keep one."
        )
    if found:
        others = ", ".join(f"{j.path.name} ({j.minecraft_version})" for j in found)
        raise SetupError(
            f"The project targets Paper {expected_version}, but server/ has {others}. "
            f"Replace it with a Paper {expected_version} jar."
        )
    raise SetupError("No Paper jar found in server/. " + " ".join(problems))


def choose_java(env: SystemEnv, minimum: int) -> java.Jdk:
    jdks = [j for j in java.find_jdks(env) if j.major >= minimum]
    if not jdks:
        raise SetupError(
            f"The test server needs Java {minimum} or newer and none is installed. "
            "Run `mcflow doctor` for the install command."
        )
    return min(jdks, key=lambda j: j.major)


def java_executable(env: SystemEnv, jdk: java.Jdk) -> Path:
    return jdk.home / "bin" / ("java.exe" if env.os_name == "windows" else "java")


def install_viaversion(plugins_dir: Path, fetch: Fetch) -> str:
    pin = pins()["viaversion"]
    target = plugins_dir / f"ViaVersion-{pin['version']}.jar"
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == pin["sha256"]:
        return "already installed"
    data = fetch(pin["url"])
    digest = hashlib.sha256(data).hexdigest()
    if digest != pin["sha256"]:
        raise SetupError(
            f"ViaVersion download failed its checksum (got {digest}, expected {pin['sha256']}). "
            "Nothing was installed."
        )
    plugins_dir.mkdir(parents=True, exist_ok=True)
    for old in plugins_dir.glob("ViaVersion-*.jar"):
        old.unlink()
    target.write_bytes(data)
    return "installed"


def run(
    root: Path,
    config: ProjectConfig,
    accept_eula: bool,
    env: SystemEnv | None = None,
    fetch: Fetch = _fetch,
) -> SetupResult:
    env = env or SystemEnv()
    server_dir = root / "server"
    jar = find_paper_jar(server_dir, config.paper_version)

    minimum = max(config.java_minimum, pins()["viaversion"]["minimum_java"])
    jdk = choose_java(env, minimum)

    previous = local.load(root)
    settings = local.LocalSettings(
        java=str(java_executable(env, jdk)),
        paper_jar=jar.path.name,
        server_port=previous.server_port if previous else free_port(25565),
        rcon_port=previous.rcon_port if previous else free_port(25575),
        rcon_password=previous.rcon_password if previous else secrets.token_urlsafe(24),
        pack_port=previous.pack_port if previous else free_port(8765),
    )
    local.save(root, settings)

    props = server_dir / "server.properties"
    existing = properties.parse(props.read_text(encoding="utf-8")) if props.exists() else {}
    properties.update(
        props,
        {
            "server-ip": "127.0.0.1",
            "server-port": str(settings.server_port),
            "online-mode": "false",
            "enforce-secure-profile": "false",
            "enable-rcon": "true",
            "rcon.port": str(settings.rcon_port),
            "rcon.password": settings.rcon_password,
            "broadcast-rcon-to-ops": "false",
            "require-resource-pack": "true",
            "resource-pack-prompt": f"{config.name} test pack (built by mcflow)",
            "resource-pack-id": existing.get("resource-pack-id") or str(uuid.uuid4()),
            # Filled in by resourcepack_build_and_serve on every pack build
            "resource-pack": existing.get("resource-pack", ""),
            "resource-pack-sha1": existing.get("resource-pack-sha1", ""),
        },
    )

    via = install_viaversion(server_dir / "plugins", fetch)

    eula = server_dir / "eula.txt"
    eula_accepted = eula.is_file() and "eula=true" in eula.read_text(encoding="utf-8")
    if accept_eula and not eula_accepted:
        eula.write_text(
            "# Accepted through `mcflow server setup --accept-eula` "
            "(https://aka.ms/MinecraftEULA)\neula=true\n",
            encoding="utf-8",
        )
        eula_accepted = True

    result = SetupResult(settings, jar, jdk.version, via, eula_accepted)
    if jdk.major > config.java_minimum and config.java_minimum < minimum:
        result.notes.append(
            f"Using Java {jdk.major}: Paper needs {config.java_minimum}+, "
            f"ViaVersion needs {minimum}+."
        )
    return result
