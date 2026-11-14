# mcflow

mcflow sets up Claude Code (and other AI coding tools) to build Paper plugins and resource packs that are ready for a busy production server. It gives the AI a fixed way of working: research before guessing, test on a real server, check the result in-game, and only then show you the change.

> **Status: early development (Stage 1 of 7).** `init` and `doctor` work. The test-server tools, skills, helper agents and knowledge-base sync come in later stages. See [docs/TASKS.md](docs/TASKS.md).

## Install

You need Python 3.11 or newer and [pipx](https://pipx.pypa.io/).

```bash
pipx install mcflow-cli
```

Until the first PyPI release, install from GitHub:

```bash
pipx install git+https://github.com/LadonON/mcflow.git
```

The package is called `mcflow-cli` on PyPI (the name `mcflow` was taken). The command you run is `mcflow`.

## Use

```bash
mcflow init my-plugin          # asks which Paper version you target (1.17 or newer)
cd my-plugin
mcflow doctor                  # checks Java, Node, universal-ctags, TokToken, Claude Code, git, gh
claude
```

`mcflow init` creates the workspace:

```
my-plugin/
├── mcflow.toml       # target Paper version and the Java it needs
├── CLAUDE.md         # the workflow rules Claude Code follows
├── AGENTS.md         # the same rules for other AI tools
├── .mcp.json         # MCP servers (TokToken for code search)
├── .claude/          # skills and helper agents
├── assets/           # drop logos, images, sounds and models here
├── research/         # one doc per researched topic
├── knowledge/        # techniques proven in tests or in-game
├── plugins/          # Gradle plugin projects
├── resourcepacks/    # resource pack sources
├── layouts/          # approved UI layouts
└── server/           # local test server (you supply the Paper jar)
```

It never overwrites files. If anything it would create already exists, it stops and lists the files.

`mcflow doctor` looks up which Java your Paper version needs (from PaperMC, or a built-in list when offline). It finds the JDKs you have installed and tells you exactly what to install or set for anything missing. Add `--json` for machine-readable output.

## Requirements

| Tool | Why |
|---|---|
| Java (the version your Paper version needs) | Building and running plugins |
| Node.js 22+ | The test-server tools (later stages) |
| universal-ctags | Required by TokToken. Exuberant ctags won't work. |
| [TokToken](https://github.com/mauriziofonte/toktoken) | Code search for the AI. AGPL-3.0, downloaded from its official releases and never bundled. |
| Claude Code | The main AI tool mcflow targets |
| git, GitHub CLI | Sharing knowledge entries through pull requests |

TokToken has builds for Windows x64, macOS (Intel and Apple Silicon) and Linux (x64, ARM64, ARMv7). On any other platform, `doctor` reports that code indexing isn't available.

## Develop

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv\Scripts\pip
pytest
ruff check src tests scripts && ruff format --check src tests scripts
```

To refresh the built-in Paper version list, run `python scripts/refresh_paper_cache.py`. Every third-party version mcflow depends on is pinned in [src/mcflow/versions.toml](src/mcflow/versions.toml), and the evidence for each pin is in [docs/research/](docs/research/).

## License

MIT. See [LICENSE](LICENSE).
