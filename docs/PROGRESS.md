# Progress

Source of truth: [BUILD_SPEC.md](BUILD_SPEC.md). Re-read it at the start of every stage. The ordered task list is [TASKS.md](TASKS.md).

## Current stage

**Stage 2: in progress.** Research is done for 2.1 (server language) and 2.2 (real-client options). Decisions are made (see below). Building the server control tools, then the Fabric mod.

## Session log

### 2026-11-14: setup and Stage 1

- Copied the spec, created PROGRESS.md and TASKS.md, and collected the Stage 1 answers.
- Repo at `C:\Users\Some One\mcflow`. GitHub: `LadonON/mcflow` (private for now).
- Installed pipx 1.18.16 locally.
- Built the Stage 1 package:
  - `mcflow init`
  - `mcflow doctor`
  - `update` and `kb` stubs
  - `versions.toml`
  - the Paper/Java lookup, with a built-in offline cache
  - the project template
  - draft `CLAUDE.md` and `AGENTS.md`
  - CI
- 76 tests pass on Windows, and ruff is clean.
- Manual test: built the wheel, installed it with `pipx install <wheel>`, ran `mcflow init` with Paper 1.21.11, then `mcflow doctor`. The result was correct.
- CI: the first run failed on Ubuntu because Rich hard-wrapped a message that contained a long temp path. Both CLI consoles now use `soft_wrap`. After that, all 9 jobs passed: tests on Windows, macOS and Ubuntu with Python 3.11 and 3.13, plus the pipx smoke test on each OS.
- Research for this stage: [research/Stage 1 Toolchain and Version Pins.md](research/Stage%201%20Toolchain%20and%20Version%20Pins.md).

## Environment (this dev machine, 2026-11-14)

| Tool | Found |
|---|---|
| OS | Windows 11 Home (10.0.26200) |
| Python | 3.13.5 |
| Java | `JAVA_HOME` points to Temurin 23.0.2 (a per-user install). Oracle JDK 25.0.2 is also installed. |
| Node.js | 22.18.0 |
| git | 2.50.1 |
| gh | 2.96.0, signed in as LadonON |
| Claude Code | **two installs**: native 2.1.157 (`~/.local/bin`) and an old npm 2.1.37 that PowerShell finds first |
| pipx | 1.18.16 |
| universal-ctags | not installed |
| TokToken | not installed |

## Decisions

- **Name:** **mcflow**, published on PyPI as **`mcflow-cli`** because `mcflow` is taken there. The command and the import package are both `mcflow`.
- **GitHub:** repos live on the personal account `LadonON`. Code is in `LadonON/mcflow`, and the knowledge base will be `LadonON/mcflow-knowledge`, which doesn't exist yet.
- **License:** MIT. TokToken (AGPL-3.0) is only downloaded from its official releases and never bundled.
- **Python:** 3.11 or later.
- **Supported Paper versions:** **1.17 and later.** `init` and `doctor` reject anything older. The newest version allowed is whatever PaperMC's API lists. Each gate and skill declares its own version range within that.
- **Java:** no fixed version. `doctor` reads the minimum for the project's Paper version from PaperMC's API (with a built-in offline cache), finds the installed JDKs, and recommends the lowest LTS release that meets the minimum.
- **Cross-platform testing:** GitHub Actions, with Windows, macOS and Ubuntu on Python 3.11 and 3.13, plus a pipx smoke test on each OS.
- **Minecraft accounts:** every user must own Java Edition and sign in. This affects the real-client work in Stage 2.
- **Helper agents:** Sonnet for the researcher and verifiers, Haiku for the indexer.
- **`.mcp.json` template:** registers only TokToken for now. `mcflow-server` is added in Stage 2, because an entry pointing at a server that doesn't exist yet would show up as a failed server in Claude Code.
- **`gh` missing or signed out** is a warning, not a failure, since only `kb push` needs it.
- **Paper versions PaperMC no longer supports** are a warning, not a failure. PaperMC currently marks only 26.3 as supported.

- **Real client (task 2.3, user decision, 2026-11-14):** **mcflow's own Fabric client mod**, not HeadlessMc. The workflow tells users they **must** install it. mcflow installs it automatically when given a Minecraft instance folder. Users sign in through their own launcher. See [Stage 2 Fabric Client Mod](research/Stage%202%20Fabric%20Client%20Mod.md).

- **mcflow-server language (2026-11-14):** TypeScript, installed through npm and pinned, because minecraft-data is 520 MB and can't ship in the wheel.
- **Node minimum (2026-11-14):** raised from the spec's 18 to **22**, because mineflayer and minecraft-protocol require it.
- **Client mod install (2026-11-14):** defaults to the official launcher's `.minecraft` folder, and the user can point it at any other path.
- **Client mod scope (2026-11-14):** the Stage 2 prototype builds **1.21.11 and 26.3**, one on each side of the 26.1 obfuscation change. The full 1.17+ range is task 2.26.

## Findings

- **Paper's Fill v3 API** gives each version's minimum Java and support status, but no maximum Java, so mcflow pins no maximum.
- **TokToken's smart filter skips YAML, XML, TOML, CSS, HTML and SVG by default.** This matters for the unsupported-language flow in Stage 5.
- **TokToken has no Windows ARM64 build.** `doctor` reports this.

## Open questions


- Should `LadonON/mcflow` stay private until the first release? Private repos use paid GitHub Actions minutes, and macOS runners count 10×.
