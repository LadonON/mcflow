import json
import subprocess
from pathlib import Path

import pytest

from mcflow import tags

SHADER = """#version 150
#define PANEL_ALPHA 0.84
uniform sampler2D Sampler0;
uniform vec4 ColorModulator;
in vec4 vertexColor;
flat in int glyphKind;
out vec4 fragColor;
struct Glyph { vec2 uv; };
vec4 tint(vec4 c) { return c * vertexColor; }
void main() {
    fragColor = tint(texture(Sampler0, vec2(0.0)));
}
"""

FONT = """{
  "providers": [
    {"type": "bitmap", "file": "demo:font/panel.png", "height": 40, "ascent": 11, "chars": ["a"]}
  ]
}
"""
MCMETA = '{"pack": {"description": "demo", "min_format": 97, "max_format": 97}}\n'
CONFIG = 'menu:\n  title: "Shop"\n  rows: 3\nmessages:\n  opened: "Opened"\n'


def universal_ctags() -> bool:
    try:
        tags.find_ctags()
    except tags.TagsError:
        return False
    return True


def workspace(tmp_path: Path) -> Path:
    files = {
        "resourcepacks/demo/pack.mcmeta": MCMETA,
        "resourcepacks/demo/assets/demo/font/ui.json": FONT,
        "resourcepacks/demo/assets/minecraft/shaders/core/rendertype_text.fsh": SHADER,
        "plugins/shop/src/main/resources/config.yml": CONFIG,
        "plugins/shop/src/main/java/Shop.java": "class Shop {}",  # not ours: TokToken indexes Java
    }
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def test_ships_the_three_definitions():
    assert tags.optlib_files() == [
        "minecraft-glsl.ctags",
        "minecraft-json.ctags",
        "yaml-keys.ctags",
    ]


def test_collects_only_the_file_types_toktoken_skips(tmp_path):
    root = workspace(tmp_path)
    names = sorted(p.name for p in tags.collect_paths(root, []))
    assert names == ["config.yml", "pack.mcmeta", "rendertype_text.fsh", "ui.json"]


def test_parses_ctags_json_and_drops_array_indexes(tmp_path):
    out = "\n".join(
        json.dumps(t)
        for t in [
            {
                "_type": "tag",
                "name": "ascent",
                "path": "a/ui.json",
                "line": 3,
                "kind": "number",
                "scope": "providers.0",
            },
            {
                "_type": "tag",
                "name": "0",
                "path": "a/ui.json",
                "line": 3,
                "kind": "object",
                "scope": "providers",
            },
            {"_type": "ptag", "name": "JSON_OUTPUT_VERSION"},
        ]
    )
    assert tags.parse(out, tmp_path) == [
        tags.Tag("ascent", "number", "a/ui.json", 3, "providers.0")
    ]


def test_reports_ctags_failures(tmp_path, monkeypatch):
    root = workspace(tmp_path)
    monkeypatch.setattr(tags, "find_ctags", lambda: "ctags")

    def broken(cmd, cwd):
        return subprocess.CompletedProcess(cmd, 1, "", "ctags: Unknown option")

    with pytest.raises(tags.TagsError, match="Unknown option"):
        tags.run(root, [], runner=broken)


@pytest.mark.skipif(not universal_ctags(), reason="universal-ctags not installed")
def test_real_ctags_reads_shaders_mcmeta_json_and_yaml(tmp_path):
    root = workspace(tmp_path)
    found = {(t.name, t.kind) for t in tags.run(root, [])}
    assert {
        ("main", "function"),
        ("tint", "function"),
        ("Sampler0", "uniform"),
        ("ColorModulator", "uniform"),
    } <= found
    assert {("vertexColor", "input"), ("glyphKind", "input"), ("fragColor", "output")} <= found
    assert {("PANEL_ALPHA", "define"), ("Glyph", "struct")} <= found
    assert {("min_format", "number"), ("ascent", "number"), ("providers", "array")} <= found
    assert {("menu", "key"), ("title", "key"), ("opened", "key")} <= found
    assert not any(name.isdigit() for name, _ in found)


@pytest.mark.skipif(not universal_ctags(), reason="universal-ctags not installed")
def test_real_ctags_query_matches_names_and_scopes(tmp_path):
    root = workspace(tmp_path)
    hits = tags.run(root, ["resourcepacks"], query="providers")
    assert hits and all("providers" in (t.name + (t.scope or "")) for t in hits)
    assert all(t.path.startswith("resourcepacks/") for t in hits)


@pytest.mark.parametrize(
    ("output", "ok"),
    [
        ("Universal Ctags 6.2.0, Copyright (C) 2015-2025 Universal Ctags Team", True),
        ("Exuberant Ctags 5.8, Copyright (C) 1996-2009 Darren Hiebert", False),
        ("ctags: illegal option -- -\nusage: ctags [-BFadtuwvx] file ...", False),
    ],
)
def test_find_ctags_accepts_only_universal_ctags(monkeypatch, output, ok):
    monkeypatch.setattr(tags.shutil, "which", lambda name: "/usr/bin/ctags")
    monkeypatch.setattr(
        tags.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0 if ok else 1, output, ""),
    )
    if ok:
        assert tags.find_ctags() == "/usr/bin/ctags"
    else:
        with pytest.raises(tags.TagsError, match="isn't universal-ctags"):
            tags.find_ctags()
