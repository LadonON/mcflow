# Progress

Source of truth: [BUILD_SPEC.md](BUILD_SPEC.md). Re-read it at the start of every stage. The ordered task list is [TASKS.md](TASKS.md).

## Current stage

**Stage 2: done, and waiting for the user's go-ahead at the checkpoint.** The final live run (2026-11-14 15:03) produced clean 1280×720 screenshots, and each `client_run` returned its server log lines. Server control, the client tools and the Fabric mod are built. The mod is live-tested on 26.3 and compiles for all 31 versions from 1.17 to 26.3. The runtime release pipeline has passed a dry run. Stage 3 doesn't start until the user says so.

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

- **Server setup lives in Python, runtime in TypeScript (2026-11-14):** `mcflow server setup` reuses the JDK detection and writes `.mcflow/local.toml`. mcflow-server only reads it.
- **Client mod has no Fabric API and no mixins (2026-11-14):** fewer things break per version. The only per-version code is `Compat.java` (screen getter/setter, main render target).
- **Client mod safety (2026-11-14):** it only joins loopback servers, and acts and takes screenshots only while connected to one. Resource packs are auto-accepted only from those servers.

- **Official-launcher installs get their own game folder (2026-11-14):** `.minecraft/mcflow/<version>/`, set as the launcher profile's gameDir. The first real install found about 100 Forge 1.19.2 mods in the user's `.minecraft/mods`, which must never be mixed with mcflow's Fabric install.

- **Repo visibility (2026-11-14):** stays private until the first release, then goes public (user decision).
- **mcflow-server distribution (2026-11-14):** a tarball on the GitHub runtime release, run with `npx -y <pinned URL>`. No npm account.
- **Runtime releases are separate from Python releases (2026-11-14):** `runtime-v*` tags build the mod and server and make a draft release. Their checksums are pinned into `versions.toml` before the Python package is released, so the package only installs files it has checksums for.
- **Local mod builds configure two versions by default (2026-11-14):** Loom prepares Minecraft for every configured version on each Gradle run. Configuring all 31 filled the dev machine's disk, so CI builds the full range in slices of six.

- **Stage 3 redefined (user, 2026-11-14):** instead of "one custom item model and one custom GUI", the vertical slice is a custom UI element that appears on screen when a command is run, in the style of BuiltByBit's "Ultimate UI" and resembling a reference image the user provides. The stage starts by asking for that image. All assets and code are original. Not started; it waits for the user's go-ahead. Details are in TASKS.md, Stage 3.
- **Stage 3 parameters (user, 2026-11-15):** Paper 26.3, `/menu` open to everyone (`mcflow.ui.menu`), interactive with a cursor and clickable buttons, closed by sneaking. Reference image received 2026-11-15.
- **Stage 3 rendering (user, 2026-11-15):** option A, a font-glyph HUD in the title with a cursor driven by head rotation. The spike works in the real 26.3 client (see `docs/research/Stage 3 On-screen UI.md`).
- **Menu input (user, 2026-11-15):** while the menu is open the player is in spectator mode (hides the hand and hotbar), and left clicks are read by a Netty packet hook, because Paper fires no event for spectator clicks. This relies on Paper internals; Space is the fallback. Locking the camera onto an entity was ruled out because the client then stops sending its view direction.

## Findings

- **Paper's Fill v3 API** gives each version's minimum Java and support status, but no maximum Java, so mcflow pins no maximum.
- **TokToken's smart filter skips YAML, XML, TOML, CSS, HTML and SVG by default.** This matters for the unsupported-language flow in Stage 5.
- **TokToken has no Windows ARM64 build.** `doctor` reports this.
- **Minecraft 26.3 API changes vs 1.21.11** (checked with javap): the screen getter and setter moved to `Minecraft.gui` (`gui.screen()`, `gui.setScreen()`), and the main render target moved to `gameRenderer.mainRenderTarget()`. `ConnectScreen.startConnecting`, `ServerData`, `Screenshot.takeScreenshot`, `ClientPacketListener.sendCommand/sendChat`, `InventoryScreen` and the container and slot APIs are unchanged.
- **Bugs the live prototype found (all fixed, with regression tests):**
  1. Paper 26.3 defaults to `white-list=true`, which kicked the user's own client. Setup now turns the whitelist off (the server is localhost-only).
  2. Minecraft's Gson drops null fields, so `"screen": null` arrived as a missing field and `client_join` never saw "no screen". The mod now serialises nulls, and the server treats missing as null.
  3. Minecraft pauses when its window loses focus, which is most of the time while mcflow drives it. The mod turns `pauseOnLostFocus` off (in mcflow's own game folder) and closes the pause menu before any command.
  4. **`latest.log` uses a different line format from the console** (`[14:15:13] [Server thread/INFO]:` vs `[14:15:13 INFO]:`). The parser only knew the console format, so every log read came back empty, and the "no exceptions" gate would have passed silently. Tests now use lines copied from a real log.
- **Client API boundaries** (all read from the real classes with javap; full table in `client-mod/README.md`): the screen, toasts and render target moved to `Minecraft.gui`/`gameRenderer` in **26.2** (not 26.1). Chat and commands went through three APIs (1.19, 1.19.1, 1.19.3). 1.17.0 takes screenshots with width and height arguments. The accessibility onboarding option arrived in 1.19.4.
- **Disk:** the dev machine ran out of space during the first full local mod build. Only this session's Loom caches were removed (about 4.7 GB freed). Caches from before today were left alone.
- **BuiltByBit blocks automated access (HTTP 403)**, so the Ultimate UI listing can't be read by tools. Search snippets say it's a server plugin ("UI cursor editor") that works with ItemsAdder, Nexo and CraftEngine. Its rendering technique is unconfirmed; Stage 3 research covers it, using the user's reference image and any listing text they paste.
- **The wiki's server.properties page sits behind a bot check**, which we don't try to get around. Paper's own reference covers the keys we need.

- **Spike bugs fixed in mcflow (2026-11-15):**
  1. `plugin_deploy` failed whenever the workspace path had a space in it (the user's home folder does). cmd.exe split the unquoted `gradlew.bat` path. The path is now quoted, with a Windows regression test.
  2. `mcflow server setup` wrote `resource-pack-prompt` as plain text, and 26.3 logs a JSON parse error for that at every start. It's now a JSON text component.

## Open questions


- Should `LadonON/mcflow` stay private until the first release? Private repos use paid GitHub Actions minutes, and macOS runners count 10×.
