import importlib.util
import json
import tomllib
from pathlib import Path

from mcflow import scaffold
from mcflow.project import ProjectConfig

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "pin_runtime.py"
spec = importlib.util.spec_from_file_location("pin_runtime", SCRIPT)
pin_runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin_runtime)

SUMS = {
    "mcflow-client-0.1.0+1.21.11.jar": "a" * 64,
    "mcflow-client-0.1.0+26.3.jar": "b" * 64,
    "mcflow-client-0.1.0+1.17.jar": "c" * 64,
    "mcflow-server-0.1.0.tgz": "d" * 64,
}


def test_pins_render_sorted_versions_and_urls():
    client, server = pin_runtime.render("runtime-v0.1.0", SUMS)
    data = tomllib.loads(client + "\n" + server)
    mod = data["client_mod"]
    assert mod["minecraft_versions"] == ["1.17", "1.21.11", "26.3"]
    assert mod["sha256"]["26.3"] == "b" * 64
    assert (
        mod["release_url"] == "https://github.com/LadonON/mcflow/releases/download/runtime-v0.1.0/"
    )
    assert data["mcflow_server"]["tarball_url"].endswith("/runtime-v0.1.0/mcflow-server-0.1.0.tgz")


def test_replace_section_keeps_the_rest_of_versions_toml():
    real = (Path(__file__).resolve().parent.parent / "src" / "mcflow" / "versions.toml").read_text()
    client, server = pin_runtime.render("runtime-v0.1.0", SUMS)
    out = pin_runtime.replace_section(real, "client_mod", client)
    out = pin_runtime.replace_section(out, "mcflow_server", server)
    parsed = tomllib.loads(out)
    assert parsed["client_mod"]["sha256"]["1.17"] == "c" * 64
    assert parsed["mcflow_server"]["sha256"] == "d" * 64
    for kept in ("paper", "toktoken", "viaversion", "fabric", "humanizer", "knowledge"):
        assert kept in parsed, f"[{kept}] was lost"


def test_mcp_json_leaves_out_unreleased_server(tmp_path):
    config = ProjectConfig("p", "26.3", 25, "LadonON/mcflow-knowledge")
    scaffold.create(tmp_path, config)
    servers = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert set(servers) == {"toktoken"}


def test_mcp_json_registers_released_server(tmp_path, monkeypatch):
    real = scaffold.pins()
    url = (
        "https://github.com/LadonON/mcflow/releases/download/runtime-v0.1.0/mcflow-server-0.1.0.tgz"
    )
    monkeypatch.setattr(scaffold, "pins", lambda: {**real, "mcflow_server": {"tarball_url": url}})
    scaffold.create(tmp_path, ProjectConfig("p", "26.3", 25, "LadonON/mcflow-knowledge"))
    servers = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert servers["mcflow"] == {"command": "mcflow", "args": ["server", "mcp"]}


def test_vendored_humanizer_matches_its_pin():
    """The prose humanizer is a copy of blader/humanizer at the pinned commit; keep them equal."""
    import hashlib
    from importlib.resources import files

    from mcflow.versions import pins

    pin = pins()["humanizer"]
    skill = files("mcflow").joinpath("templates/project/.claude/skills/humanizer")
    assert (
        hashlib.sha256(skill.joinpath("SKILL.md").read_bytes()).hexdigest() == pin["skill_sha256"]
    )
    assert (
        hashlib.sha256(skill.joinpath("LICENSE").read_bytes()).hexdigest() == pin["license_sha256"]
    )
