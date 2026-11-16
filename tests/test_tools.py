import hashlib
import io
import os
import zipfile

import pytest

from mcflow import tools

TOKTOKEN = b"pretend this is toktoken"


def ctags_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ctags.exe", b"pretend ctags")
        z.writestr("readtags.exe", b"pretend readtags")
        z.writestr("license/COPYING", b"GPL-2.0 text")
        z.writestr("docs/README.md", b"docs")
    return buf.getvalue()


@pytest.fixture
def fake_pins(monkeypatch):
    real = tools.pins()
    zipped = ctags_zip()
    patched = {
        **real,
        "toktoken": {
            **real["toktoken"],
            "assets": {
                key: {**a, "sha256": hashlib.sha256(TOKTOKEN).hexdigest()}
                for key, a in real["toktoken"]["assets"].items()
            },
        },
        "universal_ctags": {
            **real["universal_ctags"],
            "windows": {
                **real["universal_ctags"]["windows"],
                "sha256": hashlib.sha256(zipped).hexdigest(),
            },
        },
    }
    monkeypatch.setattr(tools, "pins", lambda: patched)
    fetched = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return zipped if url.endswith(".zip") else TOKTOKEN

    return fetch, fetched


def test_installs_toktoken_and_ctags_on_windows(tmp_path, fake_pins):
    fetch, fetched = fake_pins
    result = tools.install(tmp_path, "windows", "x86_64", fetch, path_env=str(tmp_path))
    assert (tmp_path / "toktoken.exe").read_bytes() == TOKTOKEN
    assert (tmp_path / "ctags.exe").read_bytes() == b"pretend ctags"
    assert (tmp_path / "universal-ctags-license" / "COPYING").read_bytes() == b"GPL-2.0 text"
    assert not (tmp_path / "readtags.exe").exists()
    assert fetched[0].endswith("toktoken-win-x86_64.exe") and fetched[1].endswith("-x64.zip")
    assert result.notes == []


def test_installs_only_toktoken_elsewhere_and_makes_it_executable(tmp_path, fake_pins):
    fetch, _ = fake_pins
    result = tools.install(tmp_path, "linux", "x86_64", fetch, path_env=str(tmp_path))
    target = tmp_path / "toktoken"
    assert target.read_bytes() == TOKTOKEN
    if os.name != "nt":
        assert os.access(target, os.X_OK)
    assert not (tmp_path / "ctags.exe").exists()
    assert "package manager" in result.skipped[0]


def test_a_bad_checksum_installs_nothing(tmp_path, fake_pins):
    with pytest.raises(tools.ToolsError, match="failed its checksum"):
        tools.install(tmp_path, "windows", "x86_64", lambda url: b"tampered", path_env="")
    assert list(tmp_path.iterdir()) == []


def test_unsupported_platform_says_which_are(tmp_path, fake_pins):
    fetch, _ = fake_pins
    with pytest.raises(tools.ToolsError, match="no build for windows-aarch64"):
        tools.install(tmp_path, "windows", "aarch64", fetch)


def test_warns_when_the_folder_is_not_on_path(tmp_path, fake_pins):
    fetch, _ = fake_pins
    result = tools.install(tmp_path, "linux", "x86_64", fetch, path_env="/usr/bin")
    assert "isn't on PATH" in result.notes[0]


def test_reinstall_replaces_the_old_binary(tmp_path, fake_pins):
    fetch, _ = fake_pins
    (tmp_path / "toktoken").write_bytes(b"old")
    tools.install(tmp_path, "linux", "x86_64", fetch, path_env=str(tmp_path))
    assert (tmp_path / "toktoken").read_bytes() == TOKTOKEN
    assert not list(tmp_path.glob("*.part"))
