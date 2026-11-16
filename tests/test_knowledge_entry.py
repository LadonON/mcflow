import datetime as dt
from pathlib import Path

import pytest

from mcflow.knowledge import entry

TODAY = dt.date(2026, 11, 16)

GOOD = """---
title: "Font glyph title UI"   # a comment
minecraft_versions: ["26.3", '1.21.11']
pack_format: 75
paper_api_version: "26.3"
verified_by: "MenuTest, server/screenshots/menu/open.png"
sources:
  - "https://docs.papermc.io/paper/dev/"
  - paper-26.3.jar net/minecraft/client/gui/Font.class
date: 2026-11-15
---

# Font glyph title UI

Body text.
"""


def write(tmp_path: Path, text: str, name: str = "font-glyph-title-ui.md") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_good_entry_parses_and_validates(tmp_path):
    e = entry.load(write(tmp_path, GOOD), TODAY)
    assert e.ok, e.errors
    assert e.warnings == []
    assert e.title == "Font glyph title UI"
    assert e.minecraft_versions == ["26.3", "1.21.11"]
    assert e.pack_format == 75
    assert e.fields["sources"] == [
        "https://docs.papermc.io/paper/dev/",
        "paper-26.3.jar net/minecraft/client/gui/Font.class",
    ]


def test_crlf_and_bom_are_accepted(tmp_path):
    path = tmp_path / "x.md"
    path.write_bytes(("﻿" + GOOD).replace("\n", "\r\n").encode("utf-8"))
    assert entry.load(path, TODAY).ok


def test_the_skill_template_example_shape_parses():
    fields, _ = entry.parse_frontmatter(
        '---\npack_format: 12            # resource-pack techniques only\ntitle: "a # b"\n---\nx'
    )
    assert fields == {"pack_format": 12, "title": "a # b"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (('title: "Font glyph title UI"   # a comment\n', ""), "title is missing"),
        (("minecraft_versions: [\"26.3\", '1.21.11']", "minecraft_versions: []"), "missing"),
        (("minecraft_versions: [\"26.3\", '1.21.11']", 'minecraft_versions: "26.3"'), "a list"),
        (("[\"26.3\", '1.21.11']", '["26.3", "latest"]'), "isn't a release version"),
        (("[\"26.3\", '1.21.11']", '["26.3", "26.3"]'), "twice"),
        (("pack_format: 75", "pack_format: big"), "whole number"),
        (('paper_api_version: "26.3"', "paper_api_version: soon"), "quoted version"),
        (("date: 2026-11-15", "date: 2026-13-40"), "YYYY-MM-DD"),
        (("date: 2026-11-15", "date: 2027-01-01"), "future"),
        (("\n# Font glyph title UI\n\nBody text.\n", "\n"), "no body"),
    ],
)
def test_bad_fields_are_reported(tmp_path, change, message):
    old, new = change
    assert old in GOOD
    e = entry.load(write(tmp_path, GOOD.replace(old, new)), TODAY)
    assert not e.ok
    assert any(message in err for err in e.errors), e.errors


def test_unknown_fields_warn_but_pass(tmp_path):
    e = entry.load(write(tmp_path, GOOD.replace("date:", "tags: [ui]\ndate:")), TODAY)
    assert e.ok
    assert "unknown field tags" in e.warnings[0]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("no frontmatter", "must start"),
        ("---\ntitle: x\n", "never closed"),
        ("---\ntitle: x\ntitle: y\n---\nbody", "twice"),
        ("---\n- orphan\n---\nbody", "without a key"),
        ("---\njust words\n---\nbody", "key: value"),
        ('---\ntitle: "open\n---\nbody', "unterminated"),
    ],
)
def test_malformed_frontmatter(tmp_path, text, message):
    e = entry.load(write(tmp_path, text), TODAY)
    assert not e.ok
    assert message in e.errors[0]


def test_file_names_must_be_kebab_case(tmp_path):
    e = entry.load(write(tmp_path, GOOD, "Font Glyph.md"), TODAY)
    assert any("file name" in err for err in e.errors)


def test_entry_files_skip_readme_and_other_files(tmp_path):
    for name in ("README.md", "a.md", "b.txt"):
        (tmp_path / name).write_text("x")
    assert [p.name for p in entry.entry_files(tmp_path)] == ["a.md"]


def test_applies_only_to_proven_versions_and_matching_pack_format(tmp_path):
    e = entry.load(write(tmp_path, GOOD), TODAY)
    assert entry.applies(e, "26.3").applies
    assert entry.applies(e, "1.21.11", pack_format=75).applies
    newer = entry.applies(e, "26.4")
    assert not newer.applies and "not 26.4" in newer.reason
    assert not entry.applies(e, "1.21.10").applies
    pack = entry.applies(e, "26.3", pack_format=80)
    assert not pack.applies and "pack format 75" in pack.reason


def test_entries_without_pack_format_ignore_it(tmp_path):
    e = entry.load(write(tmp_path, GOOD.replace("pack_format: 75\n", "")), TODAY)
    assert entry.applies(e, "26.3", pack_format=80).applies


def test_invalid_entries_never_apply(tmp_path):
    e = entry.load(write(tmp_path, GOOD.replace("date: 2026-11-15\n", "")), TODAY)
    assert not entry.applies(e, "26.3").applies


def test_main_exit_codes(tmp_path, capsys):
    write(tmp_path, GOOD)
    assert entry.main([str(tmp_path)]) == 0
    write(tmp_path, "nope", "broken.md")
    assert entry.main([str(tmp_path)]) == 1
    assert "broken.md: error" in capsys.readouterr().out


def test_knowledge_repo_validator_is_an_exact_copy():
    root = Path(__file__).parent.parent
    copy = root / "knowledge-repo" / "scripts" / "validate_entries.py"
    assert copy.read_bytes() == (root / "src" / "mcflow" / "knowledge" / "entry.py").read_bytes()
