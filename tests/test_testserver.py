import hashlib
import zipfile
from pathlib import Path

import pytest

from mcflow import scaffold
from mcflow.project import ProjectConfig
from mcflow.testserver import local, paperjar, properties, setup
from mcflow.versions import pins

CONFIG = ProjectConfig("Shiny", "1.21.11", 21, "LadonON/mcflow-knowledge")


def make_paper_jar(path: Path, version: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as jar:
        jar.writestr("io/papermc/paperclip/Main.class", b"\xca\xfe\xba\xbe")
        jar.writestr(
            "META-INF/versions.list",
            f"abc123\tpaper-{version}\tpaper-{version}.jar\n",
        )
    return path


def fake_viaversion(url: str) -> bytes:
    return b"pretend this is ViaVersion"


@pytest.fixture
def via_pin(monkeypatch):
    """Point the ViaVersion pin at our fake download so checksum verification passes."""
    real = pins()
    patched = {
        **real,
        "viaversion": {
            **real["viaversion"],
            "sha256": hashlib.sha256(fake_viaversion("")).hexdigest(),
        },
    }
    monkeypatch.setattr(setup, "pins", lambda: patched)
    return patched


# --- Paper jar detection ---


def test_reads_version_from_paper_jar(tmp_path):
    jar = paperjar.inspect(make_paper_jar(tmp_path / "paper.jar", "1.21.11"))
    assert jar.minecraft_version == "1.21.11"


def test_rejects_a_plain_jar(tmp_path):
    plain = tmp_path / "vanilla.jar"
    with zipfile.ZipFile(plain, "w") as jar:
        jar.writestr("net/minecraft/server/Main.class", b"")
    with pytest.raises(paperjar.NotAPaperJar, match="no Paperclip"):
        paperjar.inspect(plain)


def test_rejects_a_non_zip(tmp_path):
    bogus = tmp_path / "paper.jar"
    bogus.write_text("not a jar")
    with pytest.raises(paperjar.NotAPaperJar, match="valid jar"):
        paperjar.inspect(bogus)


def test_version_mismatch_is_explained(tmp_path):
    make_paper_jar(tmp_path / "paper-26.3.jar", "26.3")
    with pytest.raises(setup.SetupError, match=r"targets Paper 1\.21\.11.*26\.3"):
        setup.find_paper_jar(tmp_path, "1.21.11")


def test_missing_jar_tells_user_where_to_get_it(tmp_path):
    with pytest.raises(setup.SetupError, match=r"papermc.io/downloads/paper"):
        setup.find_paper_jar(tmp_path, "1.21.11")


# --- server.properties ---


def test_properties_update_keeps_other_keys_and_comments(tmp_path):
    props = tmp_path / "server.properties"
    props.write_text("#Minecraft server properties\nmotd=Hello\nonline-mode=true\n")
    properties.update(props, {"online-mode": "false", "enable-rcon": "true"})
    text = props.read_text()
    assert text.startswith("#Minecraft server properties\nmotd=Hello\nonline-mode=false\n")
    assert properties.parse(text) == {
        "motd": "Hello",
        "online-mode": "false",
        "enable-rcon": "true",
    }


def test_properties_round_trip_minecraft_escaped_urls(tmp_path):
    props = tmp_path / "server.properties"
    props.write_text("resource-pack=http\\://127.0.0.1\\:8765/pack.zip\n")
    url = properties.parse(props.read_text())["resource-pack"]
    assert url == "http://127.0.0.1:8765/pack.zip"
    properties.update(props, {"resource-pack": url})
    assert props.read_text() == "resource-pack=http\\://127.0.0.1\\:8765/pack.zip\n"


# --- full setup ---


@pytest.fixture
def workspace(tmp_path, fake_env):
    root = tmp_path / "proj"
    scaffold.create(root, CONFIG)
    make_paper_jar(root / "server" / "paper-1.21.11.jar", "1.21.11")
    fake_env.add_jdk(fake_env.home / ".jdks" / "jdk-17", "17.0.13")
    fake_env.add_jdk(fake_env.home / ".jdks" / "jdk-21", "21.0.5")
    fake_env.add_jdk(fake_env.home / ".jdks" / "jdk-25", "25.0.2")
    return root


def test_setup_configures_a_local_only_server(workspace, fake_env, via_pin):
    result = setup.run(workspace, CONFIG, accept_eula=False, env=fake_env, fetch=fake_viaversion)

    props = properties.parse((workspace / "server" / "server.properties").read_text())
    assert props["server-ip"] == "127.0.0.1"
    assert props["online-mode"] == "false"
    assert props["enable-rcon"] == "true"
    assert props["rcon.password"] == result.settings.rcon_password
    assert len(result.settings.rcon_password) >= 24
    assert props["require-resource-pack"] == "true"
    assert props["rcon.port"] == str(result.settings.rcon_port)

    assert "jdk-21" in result.settings.java, "lowest JDK meeting both Paper and ViaVersion"
    assert (
        workspace / "server" / "plugins" / f"ViaVersion-{via_pin['viaversion']['version']}.jar"
    ).is_file()
    assert result.viaversion == "installed"
    assert not result.eula_accepted
    assert not (workspace / "server" / "eula.txt").exists()


def test_secrets_stay_out_of_git(workspace, fake_env, via_pin):
    setup.run(workspace, CONFIG, accept_eula=False, env=fake_env, fetch=fake_viaversion)
    gitignore = (workspace / ".gitignore").read_text().splitlines()
    assert ".mcflow/" in gitignore
    assert local.path_for(workspace).is_file()


def test_rerun_keeps_password_and_ports(workspace, fake_env, via_pin):
    first = setup.run(workspace, CONFIG, accept_eula=False, env=fake_env, fetch=fake_viaversion)
    second = setup.run(workspace, CONFIG, accept_eula=True, env=fake_env, fetch=fake_viaversion)
    assert first.settings == second.settings
    assert second.viaversion == "already installed"
    assert second.eula_accepted
    assert "eula=true" in (workspace / "server" / "eula.txt").read_text()


def test_bad_viaversion_checksum_installs_nothing(workspace, fake_env):
    with pytest.raises(setup.SetupError, match="checksum"):
        setup.run(workspace, CONFIG, accept_eula=False, env=fake_env, fetch=fake_viaversion)
    assert not list((workspace / "server").glob("plugins/ViaVersion-*.jar"))


def test_paper_1_17_runs_on_java_17_for_viaversion(tmp_path, fake_env, via_pin):
    old = ProjectConfig("Old", "1.17.1", 16, "LadonON/mcflow-knowledge")
    root = tmp_path / "old"
    scaffold.create(root, old)
    make_paper_jar(root / "server" / "paper.jar", "1.17.1")
    fake_env.add_jdk(fake_env.home / ".jdks" / "jdk-16", "16.0.2")
    fake_env.add_jdk(fake_env.home / ".jdks" / "jdk-17", "17.0.13")
    result = setup.run(root, old, accept_eula=False, env=fake_env, fetch=fake_viaversion)
    assert "jdk-17" in result.settings.java
    assert result.notes


def test_no_suitable_java_fails_clearly(tmp_path, fake_env, via_pin):
    root = tmp_path / "p"
    scaffold.create(root, CONFIG)
    make_paper_jar(root / "server" / "paper.jar", "1.21.11")
    fake_env.add_jdk(fake_env.home / ".jdks" / "jdk-17", "17.0.13")
    with pytest.raises(setup.SetupError, match="Java 21 or newer"):
        setup.run(root, CONFIG, accept_eula=False, env=fake_env, fetch=fake_viaversion)
