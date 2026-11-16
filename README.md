# mcflow

mcflow sets up Claude Code (and other AI coding tools) to build Paper plugins and resource packs that are ready for a busy production server. It gives the AI a fixed way of working: research before guessing, test on a real server, check the result in-game, and only then show you the change.

> **Status: 0.1.0, the first release.** CI runs the full integration test on Windows, macOS and Linux. Open work is listed in [docs/TASKS.md](docs/TASKS.md).

New here? Start with [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md). What works on which OS and CPU is in [docs/PLATFORMS.md](docs/PLATFORMS.md).

## Install

You need Python 3.11 or newer and [pipx](https://pipx.pypa.io/).

```bash
pipx install git+https://github.com/LadonON/mcflow.git@v0.1.0
```

That installs the 0.1.0 release. Leave off `@v0.1.0` to get the newest code on `main` instead. mcflow isn't on PyPI.

To update later, reinstall: `pipx install --force git+https://github.com/LadonON/mcflow.git` (with `@<tag>` for a release). pipx lists the package as `mcflow-cli`; the command you run is `mcflow`.

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

## Knowledge base and updates

Each workspace keeps proven techniques in `knowledge/`, and can share them through one GitHub repo (`[knowledge] repo` in `mcflow.toml`, `LadonON/mcflow-knowledge` by default).

```bash
mcflow kb list                 # which entries apply to this project's version (and --pack-format N)
mcflow kb validate             # check every entry's frontmatter
mcflow kb pull                 # bring in approved entries; never overwrites ones you've edited
mcflow kb push --dry-run       # see what would be shared
mcflow kb push                 # open a pull request with new and changed entries (never a direct push)
mcflow update                  # newer skills, agents and workflow files, then kb pull
```

An entry applies only to the Minecraft versions it was proven on, and only to the same pack format when it has one. `mcflow update` replaces a skill, agent or workflow file only if you haven't edited it. For a file you have edited it shows the diff, and `--take <file>` accepts the new version. Your plugins, packs, research, layouts, assets and server are never touched. Reinstall mcflow with pipx first (see Install) to get the newest versions.

The shared repo's starting files (README, entry validator and CI) are in [knowledge-repo/](knowledge-repo/).

## Requirements

| Tool | Why |
|---|---|
| Java (the version your Paper version needs) | Building and running plugins |
| Node.js 22+ | mcflow-server (test server, game client, bots and quality gates) |
| universal-ctags | Required by TokToken. Exuberant ctags won't work. |
| [TokToken](https://github.com/mauriziofonte/toktoken) | Code search for the AI. AGPL-3.0, downloaded from its official releases and never bundled. |
| Claude Code | The main AI tool mcflow targets |
| git, GitHub CLI | Sharing knowledge entries through pull requests |

TokToken has builds for Windows x64, macOS (Intel and Apple Silicon) and Linux (x64, ARM64, ARMv7). On any other platform, `doctor` reports that code indexing isn't available. [docs/PLATFORMS.md](docs/PLATFORMS.md) has the full list of limits.

## Develop

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv\Scripts\pip
pytest
ruff check src tests scripts && ruff format --check src tests scripts
```

CI runs the unit tests on Windows, macOS and Ubuntu, plus an integration job on each that installs the wheel with pipx and runs a real Paper server through mcflow-server (`mcp-server/scripts/integration.mjs`).

To refresh the built-in Paper version list, run `python scripts/refresh_paper_cache.py`. Every third-party version mcflow depends on is pinned in [src/mcflow/versions.toml](src/mcflow/versions.toml), and the evidence for each pin is in [docs/research/](docs/research/).

## License

MIT. See [LICENSE](LICENSE).
