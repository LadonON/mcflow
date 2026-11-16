import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_release.py"
spec = importlib.util.spec_from_file_location("check_release", SCRIPT)
check_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_release)

PINNED = """
[mcflow_server]
version = "0.1.0"
tarball_url = "https://example.invalid/mcflow-server-0.1.0.tgz"
sha256 = "d"

[client_mod]
minecraft_versions = ["1.21.11", "26.3"]
release_url = "https://example.invalid/"
sha256 = { "1.21.11" = "a", "26.3" = "b" }
"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "src" / "mcflow").mkdir(parents=True)
    monkeypatch.setattr(check_release, "ROOT", tmp_path)

    def make(version: str, versions_toml: str) -> None:
        (tmp_path / "src/mcflow/__init__.py").write_text(f'__version__ = "{version}"\n')
        (tmp_path / "src/mcflow/versions.toml").write_text(versions_toml)

    return make


def test_a_pinned_release_version_passes(repo):
    repo("0.1.0", PINNED)
    assert check_release.problems("v0.1.0") == []


def test_tag_must_match_and_dev_versions_are_refused(repo):
    repo("0.1.0.dev0", PINNED)
    found = check_release.problems("v0.1.0")
    assert any("doesn't match" in p for p in found)
    assert any("isn't a release version" in p for p in found)


def test_unpinned_runtime_is_refused(repo):
    repo("0.1.0", PINNED.replace('sha256 = "d"', 'sha256 = ""').replace(', "26.3" = "b"', ""))
    found = check_release.problems("v0.1.0")
    assert any("mcflow-server isn't pinned" in p for p in found)
    assert any("1 Minecraft versions" in p for p in found)


def test_the_real_repo_reports_unpinned_runtime_exactly_when_it_is_unpinned():
    import tomllib

    pins = tomllib.loads((check_release.ROOT / "src/mcflow/versions.toml").read_text("utf-8"))
    unpinned = not pins["mcflow_server"]["tarball_url"]
    found = check_release.problems("")
    assert any("mcflow-server isn't pinned" in p for p in found) == unpinned
