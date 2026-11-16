# Stage 5: what TokToken indexes, and the unsupported-language flow

Tasks 5.14–5.17. Written 2026-11-15 with TokToken 0.5.0 and Universal Ctags 6.2.0 (p6.2.20261011.0) on Windows 11. Sources: TokToken's `README.md`, `docs/CONFIGURATION.md` and `docs/LANGUAGES.md` at tag v0.5.0, and probes on sample files.

## Correction: why plugins weren't indexed

Stage 3 recorded that TokToken skips "a folder named `plugins/`". **That was wrong.** TokToken's smart filter prunes **any non-root folder containing a package manifest** (`build.gradle`, `pom.xml`, `package.json`, `pyproject.toml`, …) as vendored code. Every plugin project has a `build.gradle`, so every plugin was skipped. With no config, a workspace with one plugin and one YAML file indexed **nothing** (`no_files`).

**Fix:** the workspace template now ships `.toktoken.json`:

```json
{"index": {"smart_filter": false,
           "extra_ignore_patterns": ["server/", "build/", ".gradle/", "gradle/", "out/", ".mcflow/"]}}
```

On `mcflow-demo` a plain `toktoken index:create .` (no `--full`) then indexed 39 files and 427 symbols, all of `plugins/`, and nothing from the test server. `--full` does the same per run; the config makes it the default for every tool and agent.

## Coverage of the formats mcflow workspaces contain (task 5.15)

| Files | Indexed by TokToken 0.5.0? |
|---|---|
| Java, Groovy/Gradle, Python, Markdown | yes |
| resource-pack `.json` (fonts, models, item definitions, `sounds.json`) | **no**: `.json` isn't on its source list (only OpenAPI files are, by name) |
| `.mcmeta` | **no** |
| GLSL `.fsh` / `.vsh` / `.glsl` | **no** |
| YAML (`plugin.yml`, `config.yml`) | the file is listed (with the smart filter off), but **no symbols**: YAML only goes to its OpenAPI parser |

## The optlib route (task 5.16)

The spec says to try a universal-ctags optlib through TokToken before anything deeper. Result: **ctags parses these files with optlibs, but TokToken never sends them to ctags.**

- `extra_extensions` (in `.toktoken.json` or `TOKTOKEN_EXTRA_EXTENSIONS`) only changes language detection. Its docs: "the mapped extension must already be in TokToken's source extension list for the file to be discovered". Tested anyway: mapping `fsh`, `json` and `mcmeta` to `glsl`, `c` or `javascript` found nothing.
- ctags with mcflow's optlibs, run directly, gives good symbols:
  - **GLSL** (universal-ctags has no GLSL parser; mcflow defines one): functions, uniforms, `in`/`out` variables, `#define`s, structs.
  - **`.mcmeta`** mapped onto ctags' JSON parser: keys with their nesting (`pack.min_format`).
  - **pack JSON** with ctags' own JSON parser: keys with scopes (`providers.0.ascent`).
  - **YAML** with an extra regex kind: every key (`menu`, `title`, `rows`). The built-in Yaml parser only tags anchors.

### What mcflow does now (task 5.17)

- The definitions ship in the package and in every workspace: `templates/project/.ctags.d/` (`minecraft-glsl.ctags`, `minecraft-json.ctags`, `yaml-keys.ctags`). universal-ctags loads `./.ctags.d/*.ctags` automatically when run in the workspace.
- **`mcflow tags [paths] [-q text] [--json]`** runs ctags with them (and `--options=NONE`, so user configs can't interfere) over packs and plugin resources, and returns symbols with file, line and scope. On `mcflow-demo`, `mcflow tags -q ascent` found 447 entries across the menu font's providers.
- Tests: `tests/test_tags.py` runs the definitions through a real ctags when one is installed (it was here: 6/6).

### The deeper fix needs the user's decision

Getting these files into TokToken itself needs a TokToken change: a configurable source-extension list, or honouring ctags' own `--list-maps` (which already includes the optlib maps). The spec forbids modifying TokToken's source in mcflow, so the route is a proposal or pull request to `mauriziofonte/toktoken`. **Nothing has been filed; it needs the user's approval** (task 5.16 asks the user before building a parser).

## Installing the tools (task 5.14)

`mcflow tools install` downloads TokToken's pinned release asset for the OS and CPU (`versions.toml [toktoken.assets]`), and on Windows the pinned official universal-ctags build (`[universal_ctags.windows]`, from `universal-ctags/ctags-win32`, GPL-2.0, licence files copied next to it). It checks each SHA-256 before writing anything, then installs into `~/.local/bin` (on PATH via pipx). On macOS and Linux, ctags comes from the package manager (`mcflow doctor` prints the command). Checked with the real pinned files: both binaries installed, matched their sums and ran (`TokToken (beta release) 0.5.0`, `Universal Ctags 6.2.0`).
