import json
import tomllib
from pathlib import PurePosixPath

import pytest

from mcflow import project, scaffold
from mcflow.project import ProjectConfig

CONFIG = ProjectConfig(
    name="Shiny Swords",
    paper_version="1.21.11",
    java_minimum=21,
    knowledge_repo="LadonON/mcflow-knowledge",
)

EXPECTED_FILES = {
    "mcflow.toml",
    "CLAUDE.md",
    "AGENTS.md",
    ".mcp.json",
    ".toktoken.json",
    ".ctags.d/minecraft-glsl.ctags",
    ".ctags.d/minecraft-json.ctags",
    ".ctags.d/yaml-keys.ctags",
    ".gitignore",
    ".claude/skills/code-humanizer/SKILL.md",
    ".claude/skills/humanizer/LICENSE",
    ".claude/skills/humanizer/SKILL.md",
    ".claude/skills/knowledge/SKILL.md",
    ".claude/skills/paper-plugin/SKILL.md",
    ".claude/skills/research/SKILL.md",
    ".claude/skills/resource-packs/SKILL.md",
    ".claude/skills/ui-layout/SKILL.md",
    ".claude/skills/verify/SKILL.md",
    ".claude/agents/indexer.md",
    ".claude/agents/researcher.md",
    ".claude/agents/verifier-output.md",
    ".claude/agents/verifier-visual.md",
    "assets/README.md",
    "research/README.md",
    "knowledge/README.md",
    "plugins/.gitkeep",
    "resourcepacks/.gitkeep",
    "layouts/README.md",
    "server/README.md",
}


def test_creates_exactly_the_spec_layout(tmp_path):
    scaffold.create(tmp_path, CONFIG)
    written = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert written == EXPECTED_FILES


def test_templates_are_rendered(tmp_path):
    scaffold.create(tmp_path, CONFIG)
    claude_md = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude_md.startswith("# Shiny Swords")
    assert "Paper 1.21.11" in claude_md and "Java 21+" in claude_md
    assert "${" not in claude_md
    for name in ("AGENTS.md", "server/README.md"):
        assert "${" not in (tmp_path / name).read_text(encoding="utf-8")


def test_mcp_json_registers_toktoken(tmp_path):
    scaffold.create(tmp_path, CONFIG)
    servers = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert servers["toktoken"] == {"command": "toktoken", "args": ["serve"]}


def test_gitignore_hides_secrets_and_server_runtime(tmp_path):
    scaffold.create(tmp_path, CONFIG)
    lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert ".mcflow/" in lines
    assert "server/*" in lines and "!server/README.md" in lines


def test_config_round_trips(tmp_path):
    scaffold.create(tmp_path, CONFIG)
    assert project.load(tmp_path) == CONFIG
    assert project.find_project_root(tmp_path / "plugins") == tmp_path


def test_config_escapes_quotes_in_name(tmp_path):
    odd = ProjectConfig('My "Best" Plugin \\ v2', "26.3", 25, "LadonON/mcflow-knowledge")
    scaffold.create(tmp_path, odd)
    assert tomllib.loads((tmp_path / "mcflow.toml").read_text())["project"]["name"] == odd.name


def test_refuses_to_overwrite_anything(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("my own notes")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "README.md").write_text("mine")

    with pytest.raises(scaffold.WorkspaceConflict) as caught:
        scaffold.create(tmp_path, CONFIG)

    assert set(caught.value.existing) == {
        PurePosixPath("CLAUDE.md"),
        PurePosixPath("assets/README.md"),
    }
    assert (tmp_path / "CLAUDE.md").read_text() == "my own notes"
    assert not (tmp_path / "mcflow.toml").exists(), "nothing should be written on conflict"


def test_unrelated_existing_files_are_fine(tmp_path):
    (tmp_path / "notes.txt").write_text("keep me")
    scaffold.create(tmp_path, CONFIG)
    assert (tmp_path / "notes.txt").read_text() == "keep me"


def test_templates_have_no_invisible_characters():
    """Private-use characters (font-glyph codepoints) must appear in docs as backslash-u escapes.

    Twice a writer turned an escape example into the real, invisible character.
    """
    from importlib.resources import files

    def walk(node):
        for child in node.iterdir():
            if child.is_dir():
                yield from walk(child)
            elif child.name.endswith((".md", ".tmpl", ".json")):
                yield child

    for f in walk(files("mcflow").joinpath("templates/project")):
        text = f.read_text(encoding="utf-8")
        bad = [hex(ord(c)) for c in text if 0xE000 <= ord(c) <= 0xF8FF or c == "�"]
        assert not bad, f"{f.name}: {bad[:3]}"


def test_agents_use_smaller_models_and_name_their_tools():
    from importlib.resources import files

    agents = files("mcflow").joinpath("templates/project/.claude/agents")
    models = {}
    for f in agents.iterdir():
        head = f.read_text(encoding="utf-8").split("---")[1]
        fields = dict(line.split(": ", 1) for line in head.strip().splitlines())
        assert fields["name"] == f.name.removesuffix(".md")
        assert fields["tools"] and fields["description"]
        models[fields["name"]] = fields["model"]
    assert models == {
        "researcher": "sonnet",
        "indexer": "haiku",
        "verifier-visual": "sonnet",
        "verifier-output": "sonnet",
    }


def test_toktoken_config_indexes_plugins_and_skips_the_server(tmp_path):
    """TokToken's smart filter treats any folder with a build.gradle as vendored; turn it off."""
    scaffold.create(tmp_path, CONFIG)
    index = json.loads((tmp_path / ".toktoken.json").read_text())["index"]
    assert index["smart_filter"] is False
    assert "server/" in index["extra_ignore_patterns"]
