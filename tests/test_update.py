from pathlib import Path, PurePosixPath

import pytest

from mcflow import manifest, scaffold, update
from mcflow.project import ProjectConfig

CONFIG = ProjectConfig(
    name="Shiny Swords",
    paper_version="1.21.11",
    java_minimum=21,
    knowledge_repo="LadonON/mcflow-knowledge",
)
SKILL = ".claude/skills/knowledge/SKILL.md"


@pytest.fixture
def ws(tmp_path) -> Path:
    scaffold.create(tmp_path, CONFIG)
    return tmp_path


def test_init_records_only_managed_files(ws):
    recorded = manifest.load(ws)
    assert SKILL in recorded and "CLAUDE.md" in recorded and ".mcp.json" in recorded
    assert not any(p.startswith(("plugins/", "knowledge/", "server/")) for p in recorded)
    assert "mcflow.toml" not in recorded and ".gitignore" not in recorded


@pytest.mark.parametrize(
    ("path", "managed"),
    [
        (".claude/agents/indexer.md", True),
        (".ctags.d/yaml-keys.ctags", True),
        ("AGENTS.md", True),
        ("knowledge/README.md", False),
        ("plugins/menu/build.gradle", False),
        (".claude/settings.json", False),
    ],
)
def test_is_managed(path, managed):
    assert manifest.is_managed(PurePosixPath(path)) is managed


def test_fresh_workspace_is_up_to_date(ws):
    result = update.run(ws, CONFIG)
    assert result.changes == 0 and result.edited == []
    assert SKILL in result.unchanged


def test_unedited_old_files_are_replaced(ws, monkeypatch):
    real_plan = scaffold.plan

    def newer(config):
        return [
            scaffold.PlannedFile(f.path, f.content + b"\nNew rule.\n")
            if f.path.as_posix() == SKILL
            else f
            for f in real_plan(config)
        ]

    monkeypatch.setattr(scaffold, "plan", newer)
    result = update.run(ws, CONFIG)
    assert result.updated == [SKILL]
    assert (ws / SKILL).read_text(encoding="utf-8").endswith("New rule.\n")
    assert update.run(ws, CONFIG).changes == 0


def test_edited_files_are_left_alone_and_diffed(ws, monkeypatch):
    path = ws / SKILL
    path.write_text(path.read_text(encoding="utf-8") + "\nMy own note.\n", encoding="utf-8")
    result = update.run(ws, CONFIG)
    [edited] = result.edited
    assert edited.path == SKILL
    assert "-My own note." in edited.diff
    assert "My own note." in path.read_text(encoding="utf-8")
    # the record still holds what mcflow wrote, so the file stays "edited" next time too
    assert update.run(ws, CONFIG).edited[0].path == SKILL


def test_take_replaces_an_edited_file(ws):
    path = ws / SKILL
    path.write_text("mine", encoding="utf-8")
    result = update.run(ws, CONFIG, take={SKILL})
    assert result.taken == [SKILL]
    assert path.read_text(encoding="utf-8") != "mine"
    assert update.run(ws, CONFIG).edited == []


def test_deleted_files_stay_deleted_unless_taken(ws):
    (ws / SKILL).unlink()
    assert update.run(ws, CONFIG).deleted_by_user == [SKILL]
    assert not (ws / SKILL).exists()
    assert update.run(ws, CONFIG, take={SKILL}).added == [SKILL]
    assert (ws / SKILL).exists()


def test_new_template_files_are_added(ws, monkeypatch):
    real_plan = scaffold.plan
    extra = scaffold.PlannedFile(PurePosixPath(".claude/skills/new/SKILL.md"), b"new skill")
    monkeypatch.setattr(scaffold, "plan", lambda config: [*real_plan(config), extra])
    assert update.run(ws, CONFIG).added == [".claude/skills/new/SKILL.md"]
    assert (ws / ".claude/skills/new/SKILL.md").read_bytes() == b"new skill"


def test_files_no_longer_shipped_are_removed_only_if_unedited(ws, monkeypatch):
    real_plan = scaffold.plan
    gone = {SKILL, ".claude/agents/indexer.md"}
    monkeypatch.setattr(
        scaffold,
        "plan",
        lambda config: [f for f in real_plan(config) if f.path.as_posix() not in gone],
    )
    (ws / ".claude/agents/indexer.md").write_text("edited", encoding="utf-8")
    result = update.run(ws, CONFIG)
    assert result.removed == [SKILL]
    assert result.kept_removed == [".claude/agents/indexer.md"]
    assert not (ws / SKILL).exists()


def test_user_files_are_never_touched(ws, monkeypatch):
    (ws / "knowledge" / "README.md").write_text("my notes", encoding="utf-8")
    (ws / "plugins" / "menu.txt").write_text("code", encoding="utf-8")
    update.run(ws, CONFIG)
    assert (ws / "knowledge" / "README.md").read_text(encoding="utf-8") == "my notes"
    assert (ws / "plugins" / "menu.txt").read_text(encoding="utf-8") == "code"


def test_dry_run_writes_nothing(ws):
    (ws / SKILL).unlink()
    (ws / manifest.MANIFEST_FILE).unlink()
    result = update.run(ws, CONFIG, dry_run=True)
    assert result.added == [SKILL]
    assert not (ws / SKILL).exists()
    assert not (ws / manifest.MANIFEST_FILE).exists()


def test_workspaces_without_a_record_treat_differences_as_edits(ws):
    (ws / manifest.MANIFEST_FILE).unlink()
    (ws / SKILL).write_text("old version or edited, can't tell", encoding="utf-8")
    result = update.run(ws, CONFIG)
    assert [e.path for e in result.edited] == [SKILL]
    assert SKILL not in manifest.load(ws)  # still unknown, so still protected next time
    assert "CLAUDE.md" in manifest.load(ws)


def test_crlf_checkouts_count_as_unedited(ws):
    path = ws / SKILL
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    result = update.run(ws, CONFIG)
    assert result.edited == []
