import hashlib
from pathlib import Path

import pytest

from mcflow import runtime

DATA = b"fake mcflow-server tarball"
PIN = {
    "version": "0.1.0",
    "tarball_url": "https://example.invalid/runtime-v0.1.0/mcflow-server-0.1.0.tgz",
    "sha256": hashlib.sha256(DATA).hexdigest(),
}


class Fetcher:
    def __init__(self, data: bytes = DATA):
        self.data = data
        self.calls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        return self.data


def test_downloads_checks_and_caches(tmp_path):
    fetch = Fetcher()
    path = runtime.ensure_tarball(PIN, tmp_path, fetch)
    assert path == tmp_path / "mcflow-server" / "mcflow-server-0.1.0.tgz"
    assert path.read_bytes() == DATA
    assert runtime.ensure_tarball(PIN, tmp_path, fetch) == path
    assert fetch.calls == [PIN["tarball_url"]]  # the second call used the cache


def test_a_bad_download_is_refused_and_not_kept(tmp_path):
    with pytest.raises(runtime.RuntimeMissing, match="checksum"):
        runtime.ensure_tarball(PIN, tmp_path, Fetcher(b"tampered"))
    assert not (tmp_path / "mcflow-server").exists()


def test_a_corrupted_cache_is_downloaded_again(tmp_path):
    cached = tmp_path / "mcflow-server" / "mcflow-server-0.1.0.tgz"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"truncated")
    fetch = Fetcher()
    assert runtime.ensure_tarball(PIN, tmp_path, fetch).read_bytes() == DATA
    assert len(fetch.calls) == 1


@pytest.mark.parametrize("missing", ["tarball_url", "sha256"])
def test_an_unpinned_server_is_a_clear_error(tmp_path, missing):
    with pytest.raises(runtime.RuntimeMissing, match="hasn't been released"):
        runtime.ensure_tarball({**PIN, missing: ""}, tmp_path, Fetcher())


def test_npx_gets_a_relative_path_with_no_spaces():
    tarball = Path("C:/Users/Some One/AppData/Local/mcflow/cache/mcflow-server/x-0.1.0.tgz")
    cmd = runtime.npx_command(tarball, "C:/Program Files/nodejs/npx.cmd")
    assert cmd[1:] == ["-y", "./x-0.1.0.tgz"]


def test_run_passes_the_workspace_and_runs_from_the_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(runtime.shutil, "which", lambda name: "/usr/bin/npx")
    seen = {}

    def fake_run(cmd, cwd, env):
        seen.update(cmd=cmd, cwd=cwd, project=env["MCFLOW_PROJECT"])

        class Done:
            returncode = 0

        return Done()

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)
    assert runtime.run(tmp_path / "ws", PIN, Fetcher()) == 0
    assert seen["cmd"] == ["/usr/bin/npx", "-y", "./mcflow-server-0.1.0.tgz"]
    assert seen["cwd"] == tmp_path / "cache" / "mcflow-server"
    assert seen["project"] == str(tmp_path / "ws")


def test_run_without_npx_says_what_to_install(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime.shutil, "which", lambda name: None)
    with pytest.raises(runtime.RuntimeMissing, match=r"Node.js"):
        runtime.run(tmp_path, PIN, Fetcher())
