---
title: Stage 1 toolchain and version pins
date: 2026-11-14
---

# Stage 1 toolchain and version pins

These are the facts behind `src/mcflow/versions.toml` and the `doctor` checks. Each one was checked on 2026-11-14 against the source listed with it.

## Python dependencies (from the PyPI JSON API)

| Package | Latest version | requires_python |
|---|---|---|
| hatchling | 1.33.0 | >=3.10 |
| typer | 0.29.1 | >=3.10 |
| rich | 15.0.0 | >=3.9 |
| pytest | 9.2.0 | >=3.10 |
| ruff | 0.17.5 | >=3.7 |

All of them work with the mcflow minimum of Python 3.11. TOML reading uses `tomllib` from the standard library, which exists from 3.11 on. HTTP uses `urllib`, so mcflow has no extra HTTP dependency.

## TokToken (from the GitHub README and the release v0.5.0 page)

- Repo: `mauriziofonte/toktoken`. License: AGPL-3.0. Language: C.
- Release v0.5.0 assets: `toktoken-linux-x86_64`, `toktoken-linux-aarch64`, `toktoken-linux-armv7`, `toktoken-macos-x86_64`, `toktoken-macos-aarch64`, `toktoken-win-x86_64.exe`, and `SHA256SUMS`. There is no Windows ARM64 build.
- The MCP server runs with `toktoken serve` over STDIO. The README's `.mcp.json` entry is `{"command":"toktoken","args":["serve"]}`.
- Print the version with `toktoken --version` (or `-v`).
- **It needs universal-ctags at runtime.** Exuberant ctags is explicitly rejected.
- The index is stored in `~/.cache/toktoken/`, so nothing is written into the project.
- `index:update` re-indexes incrementally using content hashes, and `index:file <file>` re-indexes a single file.
- By default its smart filter **excludes YAML, XML, TOML, CSS, HTML and SVG**, and `--full` turns the filter off. This matters for the unsupported-language flow in Stage 5.
- It has a `--self-update` option. `doctor` warns when the installed binary doesn't match the pinned version.

The SHA-256 sums for v0.5.0 are recorded in `versions.toml`.

## universal-ctags

The install commands come from TokToken's README, and the winget package from `winget search`.

| OS | Command |
|---|---|
| Windows | `winget install UniversalCtags.Ctags` (6.1.0), or `choco install universal-ctags` |
| macOS | `brew install universal-ctags` |
| Debian/Ubuntu | `sudo apt-get install -y universal-ctags` |
| Fedora/RHEL | `sudo dnf install universal-ctags` |
| Arch | `sudo pacman -S ctags` |

To detect it: the first line of `ctags --version` contains `Universal Ctags`. Exuberant ctags prints `Exuberant Ctags`.

## Paper and Java (from the Fill v3 API)

The source is `GET https://fill.papermc.io/v3/projects/paper/versions`. It returns `versions[].version` with `id`, `support.status` and `java.version.minimum`.

Minimum Java for each stable Paper version from 1.17 on:

| Paper | Minimum Java |
|---|---|
| 1.17 – 1.17.1 | 16 |
| 1.18 – 1.20.4 | 17 |
| 1.20.5 – 1.21.11 | 21 |
| 26.1.1 – 26.3 | 25 |

- **Only 26.3 has `support.status = SUPPORTED`.** PaperMC marks every other version UNSUPPORTED. `doctor` shows this as a warning, not a failure.
- **The API gives no maximum Java version.** No maximum is pinned, because none could be verified. `doctor` passes any JDK at or above the minimum, and it recommends the lowest LTS release (17, 21 or 25) that meets the minimum.
- Temurin JDKs on winget are `EclipseAdoptium.Temurin.<N>.JDK`, with N from 11 to 26 available.

## Other tools

| Tool | Detection | Install |
|---|---|---|
| Node.js | `node --version`. The spec requires 18 or later. | `winget install OpenJS.NodeJS.LTS`, `brew install node`, nodejs.org |
| Claude Code | `claude --version` | `irm https://claude.ai/install.ps1 \| iex` (Windows) or `curl -fsSL https://claude.ai/install.sh \| bash` (macOS/Linux), per code.claude.com/docs/en/install |
| GitHub CLI | `gh --version` and `gh auth status` | `winget install GitHub.cli`, `brew install gh`, cli.github.com |

## GitHub Actions

The latest releases are `actions/checkout` v7.0.1 and `actions/setup-python` v7.1.0, so CI uses `@v7` for both.
