"""`mcflow client install`: put mcflow's Fabric mod, and Fabric Loader where we can, into Minecraft.

Layouts we recognise:
  official launcher  .minecraft with launcher_profiles.json. We run Fabric's official installer.
  Prism / MultiMC    an instance folder with mmc-pack.json; the game folder is .minecraft/ or
                     minecraft/ inside it. Fabric is added in the launcher (we check and explain).
  anything else      a game folder. We copy the mod and say what's left to do.
"""

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from mcflow import __version__
from mcflow.platforms import current_os
from mcflow.versions import pins

MOD_PREFIX = "mcflow-client-"
CLIENT_STATE = "client.toml"


class InstallError(Exception):
    pass


@dataclass
class Layout:
    kind: str  # "official", "prism", "other"
    game_dir: Path  # where mods/ lives and where the mod writes mcflow/bridge.json
    instance_dir: Path | None = None  # Prism/MultiMC instance folder


@dataclass
class InstallResult:
    layout: Layout
    mod_jar: Path
    fabric: str  # "installed", "already installed", "add in launcher", "unknown"
    steps_for_user: list[str] = field(default_factory=list)


def default_game_dir() -> Path:
    os_name = current_os()
    if os_name == "windows":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / ".minecraft"
    if os_name == "macos":
        return Path.home() / "Library" / "Application Support" / "minecraft"
    return Path.home() / ".minecraft"


def detect(path: Path) -> Layout:
    if not path.is_dir():
        raise InstallError(
            f"{path} doesn't exist. Pass the folder of your Minecraft install or instance."
        )
    if (path / "mmc-pack.json").is_file() or (path / "instance.cfg").is_file():
        for name in (".minecraft", "minecraft"):
            if (path / name).is_dir():
                return Layout("prism", path / name, instance_dir=path)
        return Layout("prism", path / ".minecraft", instance_dir=path)
    if path.name in (".minecraft", "minecraft") and (path.parent / "mmc-pack.json").is_file():
        return Layout("prism", path, instance_dir=path.parent)
    if (path / "launcher_profiles.json").is_file() or (path / "versions").is_dir():
        return Layout("official", path)
    return Layout("other", path)


def official_has_fabric(game_dir: Path, minecraft: str) -> bool:
    versions = game_dir / "versions"
    return versions.is_dir() and any(
        d.name.startswith("fabric-loader-") and d.name.endswith(f"-{minecraft}")
        for d in versions.iterdir()
    )


def prism_has_fabric(instance_dir: Path) -> bool:
    pack = instance_dir / "mmc-pack.json"
    if not pack.is_file():
        return False
    components = json.loads(pack.read_text(encoding="utf-8")).get("components", [])
    return any(c.get("uid") == "net.fabricmc.fabric-loader" for c in components)


def prism_minecraft_version(instance_dir: Path) -> str | None:
    pack = instance_dir / "mmc-pack.json"
    if not pack.is_file():
        return None
    for c in json.loads(pack.read_text(encoding="utf-8")).get("components", []):
        if c.get("uid") == "net.minecraft":
            return c.get("version")
    return None


def mod_jar_for(minecraft: str, local_jar: Path | None) -> Path:
    pin = pins()["client_mod"]
    if minecraft not in pin["minecraft_versions"]:
        supported = ", ".join(pin["minecraft_versions"])
        raise InstallError(
            f"mcflow's client mod doesn't support Minecraft {minecraft} yet. "
            f"Supported: {supported}."
        )
    if local_jar is not None:
        if not local_jar.is_file():
            raise InstallError(f"{local_jar} doesn't exist.")
        meta = _read_fabric_mod_json(local_jar)
        if meta.get("id") != "mcflow":
            raise InstallError(f"{local_jar.name} isn't mcflow's client mod.")
        if meta.get("depends", {}).get("minecraft") != minecraft:
            raise InstallError(
                f"{local_jar.name} is built for Minecraft "
                f"{meta.get('depends', {}).get('minecraft')}, "
                f"not {minecraft}."
            )
        return local_jar
    if not pin["release_url"]:
        raise InstallError(
            "The client mod hasn't been released yet. Build it (client-mod/) and pass --jar."
        )
    return _download_release(minecraft)


def _read_fabric_mod_json(jar: Path) -> dict:
    import zipfile

    try:
        with zipfile.ZipFile(jar) as z:
            return json.loads(z.read("fabric.mod.json"))
    except (KeyError, zipfile.BadZipFile, json.JSONDecodeError):
        return {}


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"mcflow/{__version__}"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _download_release(minecraft: str) -> Path:
    pin = pins()["client_mod"]
    name = f"{MOD_PREFIX}{pin['version']}+{minecraft}.jar"
    expected = pin["sha256"].get(minecraft)
    if not expected:
        raise InstallError(f"No pinned checksum for the {minecraft} build of the client mod.")
    data = _fetch(pin["release_url"] + name)
    if hashlib.sha256(data).hexdigest() != expected:
        raise InstallError("The client mod download failed its checksum. Nothing was installed.")
    target = Path(tempfile.mkdtemp(prefix="mcflow-")) / name
    target.write_bytes(data)
    return target


def run_fabric_installer(game_dir: Path, minecraft: str, java: Path, fetch=_fetch) -> None:
    pin = pins()["fabric"]
    data = fetch(pin["installer_url"])
    if hashlib.sha256(data).hexdigest() != pin["installer_sha256"]:
        raise InstallError(
            "The Fabric installer download failed its checksum. Nothing was installed."
        )
    with tempfile.TemporaryDirectory(prefix="mcflow-fabric-") as tmp:
        installer = Path(tmp) / "fabric-installer.jar"
        installer.write_bytes(data)
        done = subprocess.run(
            [
                str(java),
                "-jar",
                str(installer),
                "client",
                "-dir",
                str(game_dir),
                "-mcversion",
                minecraft,
                "-loader",
                pin["loader_version"],
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
    if done.returncode != 0:
        raise InstallError(f"Fabric's installer failed:\n{(done.stdout + done.stderr)[-2000:]}")


def install(
    path: Path,
    minecraft: str,
    java: Path | None,
    local_jar: Path | None = None,
    installer=run_fabric_installer,
) -> InstallResult:
    layout = detect(path)
    if layout.kind == "prism" and layout.instance_dir is not None:
        instance_version = prism_minecraft_version(layout.instance_dir)
        if instance_version and instance_version != minecraft:
            raise InstallError(
                f"That instance runs Minecraft {instance_version}, "
                f"but the project targets {minecraft}. "
                "Pick (or create) an instance for the project's version."
            )

    jar = mod_jar_for(minecraft, local_jar)
    mods = layout.game_dir / "mods"
    mods.mkdir(parents=True, exist_ok=True)
    for old in mods.glob(f"{MOD_PREFIX}*.jar"):
        old.unlink()
    # Always the canonical name, so doctor and the next install can find (and replace) it.
    # The mod's version already carries the Minecraft version, e.g. "0.1.0+1.21.11".
    fallback = f"{pins()['client_mod']['version']}+{minecraft}"
    mod_version = _read_fabric_mod_json(jar).get("version", fallback)
    target = mods / f"{MOD_PREFIX}{mod_version}.jar"
    target.write_bytes(jar.read_bytes())

    result = InstallResult(layout, target, fabric="unknown")
    if layout.kind == "official":
        if official_has_fabric(layout.game_dir, minecraft):
            result.fabric = "already installed"
        elif java is None:
            raise InstallError(
                "Installing Fabric needs Java. Run `mcflow doctor` for the install command."
            )
        else:
            installer(layout.game_dir, minecraft, java)
            result.fabric = "installed"
        result.steps_for_user.append(
            f"In the Minecraft Launcher, pick the "
            f'"fabric-loader-{pins()["fabric"]["loader_version"]}-{minecraft}" '
            "installation and press Play."
        )
        if layout.game_dir != default_game_dir():
            result.steps_for_user.append(
                f"Point that installation's game directory at {layout.game_dir} "
                "(Installations, Edit, More options)."
            )
    elif layout.kind == "prism":
        if layout.instance_dir is not None and prism_has_fabric(layout.instance_dir):
            result.fabric = "already installed"
            result.steps_for_user.append("Launch the instance from Prism.")
        else:
            result.fabric = "add in launcher"
            result.steps_for_user.append(
                "In Prism: right-click the instance, Edit, Version, Install Loader, Fabric. "
                "Then launch it."
            )
    else:
        result.steps_for_user.append(
            f"Make sure this folder is the game directory of a Fabric {minecraft} install, "
            "then launch it."
        )
    return result


def save_state(project_root: Path, layout: Layout, minecraft: str) -> Path:
    path = project_root / ".mcflow" / CLIENT_STATE
    path.parent.mkdir(exist_ok=True)
    game = str(layout.game_dir).replace("\\", "\\\\").replace('"', '\\"')
    path.write_text(
        "# Written by `mcflow client install`. Machine-specific; never commit this file.\n"
        "[client]\n"
        f'game_dir = "{game}"\n'
        f'layout = "{layout.kind}"\n'
        f'minecraft_version = "{minecraft}"\n',
        encoding="utf-8",
    )
    return path
