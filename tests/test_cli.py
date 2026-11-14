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


def test_unbuilt_commands_say_when_they_arrive():
    for args in (["update"], ["kb", "pull"], ["kb", "push"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 3
        assert "Stage 6" in result.output
