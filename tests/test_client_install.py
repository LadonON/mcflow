import json
import zipfile
from pathlib import Path

import pytest

from mcflow.client import install
from mcflow.doctor import checks
from mcflow.doctor.checks import DoctorContext, Status
from mcflow.paper import PaperVersion


def make_mod_jar(path: Path, minecraft: str, mod_id: str = "mcflow") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "fabric.mod.json", json.dumps({"id": mod_id, "depends": {"minecraft": minecraft}})
        )
    return path


def official_dir(root: Path) -> Path:
    game = root / ".minecraft"
    (game / "versions").mkdir(parents=True)
    (game / "launcher_profiles.json").write_text("{}")
    return game


def prism_instance(root: Path, minecraft: str, with_fabric: bool) -> Path:
    inst = root / "MyInstance"
    (inst / "minecraft").mkdir(parents=True)
    components = [{"uid": "net.minecraft", "version": minecraft}]
    if with_fabric:
        components.append({"uid": "net.fabricmc.fabric-loader", "version": "0.20.1"})
    (inst / "mmc-pack.json").write_text(json.dumps({"components": components}))
    (inst / "instance.cfg").write_text("")
    return inst


class FakeInstaller:
    def __init__(self):
        self.calls = []

    def __call__(self, game_dir, minecraft, java):
        self.calls.append((game_dir, minecraft, java))
        (game_dir / "versions" / f"fabric-loader-0.20.1-{minecraft}").mkdir()


# --- layout detection ---


def test_detects_official_launcher(tmp_path):
    assert install.detect(official_dir(tmp_path)).kind == "official"


def test_detects_prism_instance_and_its_game_folder(tmp_path):
    inst = prism_instance(tmp_path, "1.21.11", with_fabric=True)
    layout = install.detect(inst)
    assert layout.kind == "prism"
    assert layout.game_dir == inst / "minecraft"
    assert install.detect(inst / "minecraft").instance_dir == inst


def test_missing_folder_is_explained(tmp_path):
    with pytest.raises(install.InstallError, match="doesn't exist"):
        install.detect(tmp_path / "nope")


# --- installing ---


def test_official_install_copies_mod_and_runs_fabric_installer(tmp_path):
    game = official_dir(tmp_path)
    (game / "mods").mkdir()
    (game / "mods" / "mcflow-client-0.0.9+1.21.11.jar").write_text("old")
    jar = make_mod_jar(tmp_path / "build" / "mcflow-client-0.1.0+1.21.11.jar", "1.21.11")
    fake = FakeInstaller()

    result = install.install(game, "1.21.11", Path("/java"), local_jar=jar, installer=fake)

    assert [p.name for p in (game / "mods").iterdir()] == ["mcflow-client-0.1.0+1.21.11.jar"]
    assert result.fabric == "installed"
    assert fake.calls == [(game, "1.21.11", Path("/java"))]
    assert any("fabric-loader-0.20.1-1.21.11" in s for s in result.steps_for_user)


def test_official_install_skips_fabric_when_present(tmp_path):
    game = official_dir(tmp_path)
    (game / "versions" / "fabric-loader-0.19.0-26.3").mkdir()
    jar = make_mod_jar(tmp_path / "m.jar", "26.3")
    fake = FakeInstaller()
    result = install.install(game, "26.3", Path("/java"), local_jar=jar, installer=fake)
    assert result.fabric == "already installed"
    assert fake.calls == []


def test_prism_without_fabric_tells_user_how_to_add_it(tmp_path):
    inst = prism_instance(tmp_path, "1.21.11", with_fabric=False)
    jar = make_mod_jar(tmp_path / "m.jar", "1.21.11")
    result = install.install(inst, "1.21.11", None, local_jar=jar, installer=FakeInstaller())
    assert result.fabric == "add in launcher"
    assert (inst / "minecraft" / "mods" / "mcflow-client-0.1.0+1.21.11.jar").is_file()
    assert "Install Loader, Fabric" in result.steps_for_user[0]


def test_prism_instance_for_wrong_version_is_refused(tmp_path):
    inst = prism_instance(tmp_path, "1.21.4", with_fabric=True)
    jar = make_mod_jar(tmp_path / "m.jar", "1.21.11")
    with pytest.raises(install.InstallError, match=r"runs Minecraft 1\.21\.4"):
        install.install(inst, "1.21.11", None, local_jar=jar)


def test_unsupported_minecraft_version_lists_supported_ones(tmp_path):
    with pytest.raises(install.InstallError, match=r"Supported: 1\.21\.11, 26\.3"):
        install.install(official_dir(tmp_path), "1.20.6", None, local_jar=None)


def test_jar_for_other_version_is_refused(tmp_path):
    jar = make_mod_jar(tmp_path / "m.jar", "26.3")
    with pytest.raises(install.InstallError, match=r"built for Minecraft 26\.3"):
        install.install(official_dir(tmp_path), "1.21.11", None, local_jar=jar)


def test_jar_that_isnt_ours_is_refused(tmp_path):
    jar = make_mod_jar(tmp_path / "other.jar", "1.21.11", mod_id="sodium")
    with pytest.raises(install.InstallError, match="isn't mcflow's client mod"):
        install.install(official_dir(tmp_path), "1.21.11", None, local_jar=jar)


def test_unreleased_mod_needs_a_local_jar(tmp_path):
    with pytest.raises(install.InstallError, match="pass --jar"):
        install.install(official_dir(tmp_path), "1.21.11", None, local_jar=None)


# --- doctor ---


def test_doctor_fails_until_the_mod_is_installed(tmp_path, fake_env):
    paper = PaperVersion("1.21.11", 21, False)
    ctx = DoctorContext(paper=paper, project_root=tmp_path)
    result = checks.check_client_mod(fake_env, ctx)
    assert result.status is Status.FAIL
    assert "mcflow client install" in result.fix

    game = official_dir(tmp_path / "mc")
    jar = make_mod_jar(tmp_path / "m.jar", "1.21.11")
    done = install.install(game, "1.21.11", Path("/java"), local_jar=jar, installer=FakeInstaller())
    install.save_state(tmp_path, done.layout, "1.21.11")
    assert checks.check_client_mod(fake_env, ctx).status is Status.OK

    other = DoctorContext(paper=PaperVersion("26.3", 25, True), project_root=tmp_path)
    assert "targets 26.3" in checks.check_client_mod(fake_env, other).summary
