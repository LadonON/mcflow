import json

from typer.testing import CliRunner

from mcflow import __version__
from mcflow.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_init_with_flags(tmp_path):
    target = tmp_path / "shiny"
    result = runner.invoke(app, ["init", str(target), "-p", "1.21.11", "--offline"])
    assert result.exit_code == 0, result.output
    assert "Paper 1.21.11, Java 21+" in result.output
    assert (target / "CLAUDE.md").is_file()
    assert 'name = "shiny"' in (target / "mcflow.toml").read_text()


def test_init_prompts_until_version_is_valid(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path), "--offline"], input="1.16.5\n1.20.4\n")
    assert result.exit_code == 0, result.output
    assert "1.17 and newer" in result.output
    assert 'paper_version = "1.20.4"' in (tmp_path / "mcflow.toml").read_text()


def test_init_rejects_old_version_flag(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path), "-p", "1.16.5", "--offline"])
    assert result.exit_code == 1
    assert not (tmp_path / "mcflow.toml").exists()


def test_init_twice_is_refused(tmp_path):
    runner.invoke(app, ["init", str(tmp_path), "-p", "latest", "--offline"])
    result = runner.invoke(app, ["init", str(tmp_path), "-p", "latest", "--offline"])
    assert result.exit_code == 1
    assert "already an mcflow workspace" in result.output


def test_init_conflict_lists_files(tmp_path):
    (tmp_path / "AGENTS.md").write_text("mine")
    result = runner.invoke(app, ["init", str(tmp_path), "-p", "latest", "--offline"])
    assert result.exit_code == 1
    assert "AGENTS.md" in result.output
    assert (tmp_path / "AGENTS.md").read_text() == "mine"


def test_doctor_json_uses_project_version(tmp_path, monkeypatch):
    runner.invoke(app, ["init", str(tmp_path), "-p", "1.20.4", "--offline"])
    monkeypatch.chdir(tmp_path / "plugins")
    result = runner.invoke(app, ["doctor", "--json", "--offline"])
    checks = {c["name"]: c for c in json.loads(result.stdout)}
    assert "Paper 1.20.4" in checks["Paper version"]["summary"]
    assert {c["status"] for c in checks.values()} <= {"ok", "warn", "fail"}
    assert result.exit_code in (0, 1)


def test_doctor_rejects_old_version(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["doctor", "-p", "1.16.5", "--offline"])
    assert result.exit_code == 2


def _workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init", ".", "-p", "1.21.11", "--offline"]).exit_code == 0


ENTRY = """---
title: "A"
minecraft_versions: ["1.21.11"]
paper_api_version: "1.21"
verified_by: "T"
sources: ["https://docs.papermc.io/"]
date: 2026-11-15
---

Body
"""


def test_kb_validate_and_list(tmp_path, monkeypatch):
    _workspace(tmp_path, monkeypatch)
    (tmp_path / "knowledge" / "a.md").write_text(ENTRY, encoding="utf-8")
    (tmp_path / "knowledge" / "b.md").write_text(ENTRY.replace('"1.21.11"', '"26.3"'), "utf-8")
    assert runner.invoke(app, ["kb", "validate"]).exit_code == 0
    listed = json.loads(runner.invoke(app, ["kb", "list", "--json"]).output)
    assert [(r["file"], r["applies"]) for r in listed] == [("a.md", True), ("b.md", False)]
    (tmp_path / "knowledge" / "c.md").write_text("broken", encoding="utf-8")
    result = runner.invoke(app, ["kb", "validate"])
    assert result.exit_code == 1 and "c.md: error" in result.output


def test_update_in_a_fresh_workspace_changes_nothing(tmp_path, monkeypatch):
    _workspace(tmp_path, monkeypatch)
    result = runner.invoke(app, ["update", "--no-kb"])
    assert result.exit_code == 0, result.output
    assert "0 change(s)" in result.output


def test_kb_push_needs_a_github_repo(tmp_path, monkeypatch):
    _workspace(tmp_path, monkeypatch)
    toml = tmp_path / "mcflow.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace("LadonON/mcflow-knowledge", "/a/path"), "utf-8"
    )
    result = runner.invoke(app, ["kb", "push", "--dry-run"])
    assert result.exit_code == 1 and "GitHub repo" in result.output
