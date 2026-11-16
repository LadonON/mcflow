# mcflow task list

Every task needed to finish the project, in order. The spec is [BUILD_SPEC.md](BUILD_SPEC.md) (section numbers below refer to it), and status and decisions are in [PROGRESS.md](PROGRESS.md).

Rules for this list:
- Tick a task (`[x]`) only once it's done **and** tested.
- Each stage ends with a **checkpoint**: show the user what works, then wait for their go-ahead.
- If a task turns out infeasible as written, stop, propose the closest alternative and ask before substituting it.
- When doing a task reveals new work, add it here in the right place rather than doing it silently.

Labels: **[you]** is a task the user has to do. **[research]** means check the current docs and write the findings to `docs/research/` before writing code.

---

## Stage 0: Project setup

- [x] 0.1 Copy the spec to `docs/BUILD_SPEC.md`
- [x] 0.2 Create `docs/PROGRESS.md`
- [x] 0.3 Collect the Stage 1 answers (name, OS, Python, Java policy, CI, license, PyPI name)
- [x] 0.4 Create this task list
- [x] 0.5 **[you]** Choose the folder for the repo, then move the session there
- [x] 0.6 **[you]** Sign the GitHub CLI in (`gh auth login`): signed in as LadonON
- [x] 0.7 **[you]** Set the supported version range: Paper 1.17 and later
- [x] 0.8 **[you]** Approve the Stage 1 plan
- [x] 0.9 Run `git init`, add the first `.gitignore`, and create the GitHub repo `mcflow` on the user's personal account
- [x] 0.10 Install pipx locally (`python -m pip install --user pipx`, then `pipx ensurepath`)

## Stage 1: Package skeleton, `init`, `doctor`, templates

### 1A. Package
- [x] 1.1 **[research]** Check the current versions of hatchling, Typer, Rich, pytest and ruff, and confirm that pipx installs a src-layout package correctly
- [x] 1.2 Write `pyproject.toml`: distribution name `mcflow-cli`, import package `mcflow`, `mcflow` console command, `requires-python >=3.11`, MIT license
- [x] 1.3 Set up the `src/mcflow/` layout with `__init__.py` (version) and `__main__.py`
- [x] 1.4 Add the MIT `LICENSE` and a top-level `README.md` (draft)
- [x] 1.5 Set up the ruff config and the pytest config, and add a `tests/` folder

### 1B. Version pins
- [x] 1.6 **[research]** Check TokToken v0.5.0: release assets, SHA-256 sums, CLI flags (`serve`, index commands) and its universal-ctags requirement
- [x] 1.7 **[research]** Check universal-ctags: official distribution per OS, how to recognise it (`--version` output) and how to tell it apart from Exuberant ctags
- [x] 1.8 **[research]** Check the minimum Node version and how to detect Claude Code (`claude --version`)
- [x] 1.9 **[research]** Pin the blader/humanizer commit
- [x] 1.10 Write `src/mcflow/versions.toml` with every pin, plus a loader module and its tests

### 1C. Paper and Java lookup
- [x] 1.11 **[research]** Paper's Fill v3 API: version list, minimum Java and support status. Also find out which Java versions are too new for which Paper versions from 1.17 on, since the API gives no maximum
- [x] 1.12 Write `mcflow/paper.py`: version lookup with a cached copy shipped for offline use and a timeout. It rejects versions older than 1.17 with a clear message. Tests run against recorded responses, including the 1.16.5 rejection
- [x] 1.13 Maximum-Java table: none pinned, because PaperMC publishes no maximum and nothing could be verified (see the research doc)

### 1D. `doctor`
- [x] 1.14 Build the check framework: each check returns ok / warn / fail, plus a fix-it message for each OS
- [x] 1.15 Java check: find every JDK (via `JAVA_HOME`, `PATH` and the usual install folders on each OS), compare them against the project's Paper version, and say exactly which JDK to install or which `JAVA_HOME` to set
- [x] 1.16 Node.js check (version 18 or later)
- [x] 1.17 universal-ctags check (fails on Exuberant ctags)
- [x] 1.18 TokToken check (binary present, version matches the pin), and say clearly which platforms it supports
- [x] 1.19 Claude Code check
- [x] 1.20 gh check (installed and signed in; needed for `kb push`)
- [x] 1.21 Output as a Rich table, with an exit code other than 0 when anything fails, and a `--json` flag for Claude to read
- [x] 1.22 Unit tests for every check, faking the command output

### 1E. `init` and the project template
- [x] 1.23 Template tree under `src/mcflow/templates/project/` matching section 2 exactly
- [x] 1.24 `mcflow.toml` schema (Paper version, project name, kb repo) and `init`'s prompt for the Paper version
- [x] 1.25 Write `assets/README.md`: what to drop in, the formats it accepts and how each is used
- [x] 1.26 Write the project `.gitignore`, which covers the RCON secret file, `server/` runtime files, screenshots and build output
- [x] 1.27 Draft `CLAUDE.md`: the section 11 pipeline, the knowledge-base lookup rule, the "always use the indexer" rule, the UI layout flow, and when to run `doctor`. Mark it as a draft wherever it refers to later stages
- [x] 1.28 Draft `AGENTS.md` with the same rules, with the agent steps done inline
- [x] 1.29 Draft `.mcp.json` with TokToken only. `mcflow-server` is added in Stage 2, since a placeholder entry would show up as a failed server
- [x] 1.30 Make `init` refuse to overwrite existing files, then test the full file tree
- [x] 1.31 Stub `update`, `kb pull` and `kb push` so they print which stage they arrive in

### 1F. CI and checks
- [x] 1.32 GitHub Actions: Windows, macOS and Ubuntu on Python 3.11 and 3.13, running ruff and pytest
- [x] 1.33 Manual test on Windows: `pipx install .`, `mcflow init` in a temporary folder, then `mcflow doctor`
- [x] 1.34 Write a README for each component (package, doctor, templates)
- [x] 1.35 Update PROGRESS.md
- [ ] 1.36 **Checkpoint:** show the results and wait for the go-ahead

## Stage 2: `mcflow-server` server control and the real-client prototype

### 2A. Decisions first
- [x] 2.1 **[research]** Compare TypeScript and Python for the MCP server against the current MCP SDKs and the mineflayer ecosystem, then write the case for the choice
- [x] 2.2 **[research]** Real-client options: HeadlessMC, a Fabric mod with a local control socket, a virtual display (Xvfb) on Linux, and others. For each, check whether it supports Microsoft sign-in, whether it can run without a screen, how screenshots are taken, the range of Minecraft versions it covers (including 26.x), how it behaves on Windows, macOS and Linux, and its license
- [x] 2.3 **[you]** Real client: our own Fabric mod (user decision). Language: TypeScript. Node 22+

### 2B. Test-server setup (section 3)
- [x] 2.4 First-run flow: ask for the Paper version, then ask the user to put a Paper jar in `server/`
- [x] 2.5 Paper jar check: inspect the manifest or the classes inside the jar, and read its version
- [x] 2.6 **[research]** ViaVersion: its official distribution, the API to download it, and version compatibility
- [x] 2.7 Install ViaVersion
- [x] 2.8 Generate `server.properties`: localhost only, offline mode, RCON with a random password in a git-ignored file, `require-resource-pack`, and accept the EULA only after the user explicitly agrees
- [x] 2.9 Choose the Java version for the server (this reuses `doctor`'s Java detection)

### 2C. Server-control tools
- [x] 2.10 MCP server skeleton, registered in the `.mcp.json` template
- [x] 2.11 `server_start`, `server_stop`, `server_restart` and `server_status` (process management that works on every OS)
- [x] 2.12 `server_command`, using an RCON client
- [x] 2.13 `server_logs(since, filter)`, which also detects exceptions and stack traces
- [x] 2.14 `plugin_deploy(project)`: Gradle build, copy the jar, then a clean restart (never `/reload`)
- [x] 2.15 **[research]** Resource-pack zip rules, the SHA-1 requirement, and how `pack_format` maps to versions
- [x] 2.16 `resourcepack_build_and_serve(pack)`: validate, zip, compute the SHA-1, serve it over local HTTP and update `server.properties`
- [x] 2.17 Tests for each tool, plus a README

### 2D. Real client: mcflow's Fabric mod
- [x] 2.18 Set up the `client-mod/` Gradle project with Stonecutter, building **1.21.11 (obfuscated) and 26.3 (unobfuscated)** first, with no Fabric API dependency
- [x] 2.19 Shared core: loopback TCP control socket (127.0.0.1, random token, line-delimited JSON), plus a token and port file in the game folder
- [x] 2.20 Version-specific commands: join (localhost only), run a chat command, screenshot to a path, open the inventory, list the screen's widgets, accept the localhost resource pack, quit
- [x] 2.21 MCP tools `client_launch` (wait for the game, or launch through Prism if available), `client_join`, `client_run`, `client_screenshot`, `client_open_inventory`, `client_quit`, saving to `server/screenshots/<task>/<label>.png`
- [x] 2.22 `mcflow client install <instance-dir>`: detect the launcher layout, copy the matching mod jar, and install Fabric Loader for the official launcher. The workflow (CLAUDE.md, `doctor`) says the mod is **required**
- [x] 2.23 Release pipeline: `release-runtime.yml` builds all 31 mod jars and the mcflow-server tarball with SHA256SUMS, creating a draft release on a `runtime-v*` tag. `scripts/pin_runtime.py` pins the checksums. `mcflow init` registers mcflow-server once pinned. Dry run passed 2026-11-14. **The first real release waits until the repo goes public (user decision).**
- [x] 2.24 **[you]** Prototype on your machine: sign in through your launcher, join the local server, take a screenshot. Done 2026-11-14 on Paper 26.3: joined in about 6 s, ran player commands, opened the inventory (slots read back), took two screenshots
- [x] 2.24a Clean screenshots: toasts cleared before capture, tutorial and first-join notices off, `client_join` sets 1280×720. Verified live 2026-11-14 on 26.3
- [x] 2.25 Per-OS limits written in `client-mod/README.md` (Windows verified; macOS and Linux not yet tested; headless Linux not supported yet)
- [x] 2.26 The mod builds for all 31 supported versions (1.17 to 26.3) in CI. Only 26.3 has been run in a real game; the others compile against their real APIs. In-game testing of older versions belongs in Stage 7's cross-platform and version testing
- [ ] 2.27 **Checkpoint:** show the results and wait for the go-ahead

## Stage 3: Vertical slice: a command-opened on-screen UI (section 11, end to end)

**Changed by the user (2026-11-14)** from the spec's "one custom item model and one custom GUI". The slice is a custom UI element that appears on the player's screen when they run a command, in the style of BuiltByBit's "Ultimate UI" (https://builtbybit.com/resources/ultimate-ui.105345/), and it must resemble a reference image the user provides.

What's known about Ultimate UI (only from search snippets, because BuiltByBit blocks automated access): it's a **server plugin**, described as a UI *cursor* editor, that shows custom on-screen UIs and works alongside the ItemsAdder, Nexo and CraftEngine resource-pack plugins. How it draws the UI and moves the cursor is not confirmed, and is part of 3.3.

All art and code are **original**. The reference image and the listing guide the look and the behaviour, but nothing is copied from the paid resource.

- [x] 3.1 **[you]** Ask for the reference image (received 2026-11-15: `mcflow-demo/layouts/9a745e86-….png`, a card with the player's head, name, level and XP bar, and a 3×2 icon grid): the user drops it in `layouts/` (any image format), with a note on what each part should do. Wait for it. Don't propose a layout before it arrives
- [x] 3.2 **[you]** Ask for anything else the build depends on. **Answered 2026-11-15:** Paper **26.3**; command **`/menu`**, permission `mcflow.ui.menu` granted to everyone by default; **interactive** (cursor and clickable buttons); closed by **sneaking (Shift)**. Listing text not provided yet (optional). The questions were:
  - the slice's Paper version (or the latest)
  - the command name and who can run it (a permission node)
  - what closes the UI
  - whether the UI is display-only or interactive (a cursor and clickable buttons, like Ultimate UI)
  - optionally, the Ultimate UI listing's text or screenshots, pasted in, since the page can't be fetched automatically
- [x] 3.3 Knowledge-base lookup, then **[research]**: how to draw a full-screen or overlay UI from a server plugin on that version. Candidates: font glyphs with negative-space shifts in the action bar, title or boss bar; `text_display` entities in front of the camera; core shaders; a cursor driven by the player's camera or mouse movement. Compare each against the reference image, and present the trade-offs before choosing
- [x] 3.3a Spike for option A (user's choice, 2026-11-15): panel, text, face, XP bar, hover and a view-driven cursor, verified in the real 26.3 client. Results in `docs/research/Stage 3 On-screen UI.md`
- [ ] 3.3b **[you]** Try the spike by hand: left click to select, sneak to close, and how the cursor feels with the mouse
  - Round 1 (2026-11-15): the hand and hotbar were visible, and the cursor wasn't smooth. Now spectator mode while the menu is open, a click packet hook (the user's choice) with Space as a fallback, and a redraw on every rotation packet. Round 2 hasn't been confirmed
- [x] 3.4 Write a first draft of the paper-plugin skill and the resource-packs skill, enough for the slice
  - Done 2026-11-15: `.claude/skills/paper-plugin/SKILL.md` and `.claude/skills/resource-packs/SKILL.md` in the project template (copied into mcflow-demo). Both hold only facts verified on 26.3 and mark the rest as unverified
- [x] 3.5 UI layout flow: turn the reference image into a spec in `layouts/` (sizes, positions, states), propose a rendered mockup made from original assets, and **[you]** approve it. Repeat until approved
  - Round 1 proposed 2026-11-15: `mcflow-demo/layouts/menu.layout.md` and three mockups rendered by `plugins/menu-spike/tools/render_mockup.py`. A 160×168 panel (the face is pinned to the title line, so not the reference's 3:4), a 2× name, spectator mode hides the HUD. **Approved 2026-11-15**, with chat placeholders for tile actions and vanilla XP
- [x] 3.6 Sample Gradle plugin project in `plugins/`: the command, opening and closing, per-player state cleaned up on quit, and no blocking work on the main thread
  - Done 2026-11-15: `mcflow-demo/plugins/menu/`. `tools/generate_assets.py` is the single source of the layout, writing the pack and `Glyphs.java`. `tools/render_mockup.py` draws the mockups from the same values
- [x] 3.7 Resource pack in `resourcepacks/`: the UI textures and font, built and served with `resourcepack_build_and_serve`
  - Done 2026-11-15: `mcflow-demo/resourcepacks/menu/` (format 97), all art original, including a 5×7 pixel font at 1× and 2×
- [x] 3.8 MockBukkit unit tests (the command, permissions, open and close state, cleanup on quit)
  - Done 2026-11-15: 16 tests pass on `mockbukkit-v26.3` 4.120.0. 8 cover layout and cursor maths (title advance always equals the panel's, tile hits, clamping, yaw wrap, name fallback). 8 run on MockBukkit (open into spectator, permission, default permission, sneak closes and restores the game mode, jump doesn't close, a second /menu keeps the original mode, quit, plugin disable). Spectator clicks go through Netty, which MockBukkit doesn't run, so they're covered in game only
- [x] 3.9 Verify: build, tests, deploy, logs, the command run through `client_run`, and screenshots (`client_screenshot`) compared against the approved layout and the reference image
  - Done 2026-11-15 at 1280×720 (GUI scale 3), screenshots in `mcflow-demo/server/screenshots/stage3-menu/`. 5/5 checks passed: no problems on /menu, spectator while open, click hook installed (no warning), game mode restored after a restart with the menu open, no exceptions in the log. The panel's top edge matches the approved mockup to the pixel. The mockup was 2 GUI px off horizontally (the client centres titles with integer maths); it's now fixed and matches. **Not verified automatically:** a real left click and sneak (the client mod can't press keys), so 3.3b stays open
- [x] 3.10 Run the code-humanizer (first draft) over the slice's code
  - Done 2026-11-15: first-draft `code-humanizer` skill added to the template. On the slice, it removed an unused method, a duplicate sneak handler, task and map cleanup that Bukkit already does, and `Math.max` guards that hid an initialisation-order gap (stats are now read before the first draw). Tests: 16/16 before and after
- [x] 3.11 Re-verify
  - Done 2026-11-15: build, tests (now 18) and two in-game runs pass, 5/5 checks each, screenshots in `server/screenshots/stage3-menu-reverify/`. The face rendered in the first verify run but was blank, then black, in the re-runs. That's the offline test server: the client looks the skin up by name. The plugin now passes the player's signed skin (the `textures` profile property), which online-mode servers always have; this is unit-tested but can't be seen on the offline test server
- [x] 3.12 Re-index (TokToken by hand at this point)
  - Done 2026-11-15: TokToken 0.5.0 (SHA-256 matches the pin) and universal-ctags p6.2.20261011.0 (matches GitHub's digest) installed under `~/.local/mcflow-tools/` with the user's OK. **TokToken's default filter skipped every plugin**, so the workspace indexed only Markdown (the cause is any folder with a `build.gradle` counting as vendored, not the folder name; see `docs/research/Stage 5 TokToken coverage.md`). `--full` indexes all 38 files (426 symbols: Java, Python, Markdown). The CLAUDE.md and AGENTS.md templates now say to index in full mode. Resource-pack JSON still isn't indexed (Stage 5, task 5.15)
- [x] 3.13 Write the first verified entries in `knowledge/`
  - Done 2026-11-15: five entries in `mcflow-demo/knowledge/`: font-glyph-title-ui, player-head-text-object, view-driven-cursor, spectator-menu-input, mockbukkit-26-3. Each names the test or screenshot that proves it, and marks what isn't proven yet (a real left click; the signed-skin face in game)
- [x] 3.14 Present the screenshots next to the reference image, with the test results and the open gaps (performance and memory checks arrive in Stage 4)
  - Done 2026-11-15: `mcflow-demo/server/screenshots/stage3-result-compare.png` shows the reference, the approved mockup and two in-game shots. Open gaps: a real left click and sneak by a person (3.3b); the face is unreliable on the offline test server; the world turns behind the panel; the panel is squarer than the reference (pinned by the face); resource-pack JSON isn't indexed. Performance and memory checks arrive in Stage 4
- [x] 3.15 **Checkpoint:** show the results and wait for the go-ahead
  - Go-ahead given 2026-11-15 ("Go to Stage 4"). Task 3.3b stays open

## Stage 4: Bots, swarm load tests, spark

- [x] 4.1 **[research]** mineflayer: which versions it supports (including 26.x), and how it behaves in offline mode
  - Done 2026-11-15: `docs/research/Stage 4 Bots.md`. mineflayer 4.39.0 tops out at 26.1, so bots join the 26.3 server through **ViaBackwards 5.12.2** (installed with the user's OK, hash checked). Two mineflayer bugs needed workarounds: the resource-pack reply's UUID, and the missing `tick_end` packet. With both, a probe passed 10/10 (join, chat, look, walk, /menu, sneak closing it, five bots at once)
- [x] 4.1a `mcflow server setup` installs ViaBackwards (pinned SHA-256) when the server is newer than mineflayer supports; `doctor` reports it
  - Done 2026-11-15: `versions.toml` pins ViaBackwards 5.12.2 and records mineflayer's newest version (`[bots]`); setup installs it only when needed, and `doctor`'s new "Test bots" check says how bots join (ok on the demo: 26.1 through ViaBackwards). 3 new tests
- [ ] 4.1b **[you]** Approve reporting the two mineflayer bugs upstream (the UUID in the resource-pack reply, and the missing `tick_end`). Nothing is posted without approval
- [x] 4.2 `bot_join`, `bot_leave`, `bot_chat`, `bot_move`, `bot_look`, `bot_use_item`, `bot_inventory`, `bot_click_window_slot`, `bot_status`
  - Done 2026-11-15: `mcp-server/src/bots.ts` plus the nine tools in `src/index.ts`. 49 unit tests pass (15 new), and a live run through the MCP server passed 30/30 (details in `docs/research/Stage 4 Bots.md`). Bots join the 26.3 server as 26.1 through ViaBackwards, with both mineflayer workarounds. `MCFLOW_BOT_TRACE=1` logs packets. Inside spawn protection, non-operator bots can't use blocks, and the tool says so
- [x] 4.3 `bot_swarm(count, behavior)`, with defined behaviors (idle, wander, use-feature, join-leave loop)
  - Done 2026-11-15: `mcp-server/src/swarm.ts` plus the `bot_swarm` tool. 61 unit tests pass (12 new), and the live run passed 8/8 (`scripts/swarm-live.mjs`): idle ×10 and ×50, wander ×10, `/menu` ×10, join_leave ×10. The "moved too quickly!" warnings are a harmless join-time artefact, reported separately. The test server's `max-players` (20) refused bots 21–50; setup now sets 200
- [x] 4.4 **[research]** spark: installation, profiler commands, and reading MSPT and its reports from the command line or RCON
  - Done 2026-11-15: `docs/research/Stage 4 spark and gates.md`. Paper 26.3 bundles spark 1.10.191. **Some spark commands upload to spark.lucko.me** (`spark health` always; timed profiles; stops without `--save-to-file`), and one health report was uploaded during the research (the user was told). The gates use only local-only commands and Paper's `mspt`, which, unlike `spark tps`, replies over RCON
- [x] 4.5 Performance gate: record MSPT before and after, and flag regressions against a threshold
  - Done 2026-11-15: `gate_performance`. It samples `mspt` every 5 s during a swarm; fails on p95 over 50 ms or a median regression over 25% (and 1 ms) against a saved baseline; optional local spark profile
- [x] 4.6 Memory gate: repeated join, leave and use cycles, then check for leaked listeners, tasks and per-player maps (heap and object counts)
  - Done 2026-11-15: `gate_memory`. `jcmd` class histograms after a warm-up, N cycles and 2N cycles; a plugin class, listener registration or scheduled task that grows at both steps is a leak. Heap reported
- [x] 4.7 Thread-safety gate: static checks plus runtime detection of async access to the Bukkit API
  - Done 2026-11-15: `gate_thread_safety`. A static scan for main-thread-only Bukkit calls in async tasks, futures, threads, Netty handlers and async events (a heuristic over source text), plus Paper's async catches in the server log
- [x] 4.8 Resource-pack gate: `pack_format`, and that every model, texture and font it references is present
  - Done 2026-11-15: `gate_resource_pack`. Pack format, JSON, every texture, model and font reference (`minecraft:` ones against the client jar), and bitmap-font rules: ascent no greater than height, equal `chars` rows, a texture that fits the grid. It would have caught the Stage 3 missing-glyph bug
- [x] 4.9 Run the slice through every gate
  - Done 2026-11-15: the /menu slice passed every gate live, 6/6 (`scripts/gates-live.mjs`; results in the research doc), with no spark uploads. 81 mcflow-server tests (20 new) and 111 Python tests pass
- [x] 4.10 **Checkpoint:** show the results and wait for the go-ahead
  - Go-ahead given 2026-11-15 ("Go to Stage 5"). Task 4.1b stays open

## Stage 5: Skills, agents, TokToken, unsupported languages

- [x] 5.1 Skill: research
  - Done 2026-11-15: `.claude/skills/research/SKILL.md`. Primary sources first (the server and client jars, published artifacts), one doc per topic, researcher agents in parallel, no uploads
- [x] 5.2 Skill: knowledge
  - Done 2026-11-15: `.claude/skills/knowledge/SKILL.md`. Lookup with version and pack-format matching, entries only after proof, `mcflow kb push` as a pull request
- [x] 5.3 Skill: verify
  - Done 2026-11-15: `.claude/skills/verify/SKILL.md`. Build and tests (stderr too), resource-pack gate, deploy, logs, in-game checks with both verifier agents and bots, then the performance, memory and thread-safety gates; spark stays local
- [x] 5.4 Skill: code-humanizer (final), with tests that check it leaves behavior unchanged
  - Done 2026-11-15: final skill plus a behaviour guard. `mcflow humanize snapshot|check <project>` builds, tests and records passing tests and the public API (`javap -public`), then fails on a broken or missing test or any public-signature change. 10 unit tests; on the real menu plugin it reported unchanged, caught a renamed public handler (exit 1), and passed again after the revert
- [x] 5.5 Install the humanizer (prose) skill from the pinned blader/humanizer commit
  - Done 2026-11-15: blader/humanizer 4.0.0 at the pinned commit `b48c832` (downloaded with the user's OK and read in full: a writing guide, no fetch or exec instructions, MIT). Vendored with its LICENSE in `templates/project/.claude/skills/humanizer/`; `versions.toml` pins both SHA-256 sums and a test checks the copies
- [x] 5.6 Skill: resource-packs (final, aware of each version)
  - Done 2026-11-15: version-aware. The pack format is read from the server jar, never hardcoded; the custom-item model system is shown per version range; sounds, `.mcmeta` animation and shaders are marked research-before-use; the proven 26.3 font rules are kept
- [x] 5.7 Skill: paper-plugin (final)
  - Done 2026-11-15: adds threads (the async-then-`runTask` pattern), state and cleanup, commands, configs and persistence, the internals rule, and the 26.3 and MockBukkit facts
- [x] 5.8 Skill: ui-layout
  - Done 2026-11-15: `.claude/skills/ui-layout/SKILL.md`, the flow used in Stage 3: ask, spec in GUI pixels, mockup from the build's own generator, approval, measured comparison
- [x] 5.9 Agent: researcher (Sonnet)
  - Done 2026-11-15: `.claude/agents/researcher.md` (Sonnet). Read-only tools plus Bash for inspecting jars and registries; writes `research/`; reports downloads back instead of making them
- [x] 5.10 Agent: indexer (Haiku)
  - Done 2026-11-15: `.claude/agents/indexer.md` (Haiku). Updates the index, checks `plugins/` is in it, reports unparsed languages
- [x] 5.11 Agent: verifier-visual (Sonnet)
  - Done 2026-11-15: `.claude/agents/verifier-visual.md` (Sonnet). Measures screenshots against the spec and mockups; known variable areas excluded
- [x] 5.12 Agent: verifier-output (Sonnet)
  - Done 2026-11-15: `.claude/agents/verifier-output.md` (Sonnet). Correctness, errors, formatting; knows the test server's harmless noise. A scaffold test checks every agent's model and tools
- [x] 5.13 Finalise `CLAUDE.md` and `AGENTS.md`
  - Done 2026-11-15: no more draft notes. Both list the real tools, skills and agents, the humanize guard, `.toktoken.json` and `mcflow tags`, the unsupported-language flow, and a never-upload rule (spark)
- [x] 5.14 Make the installer download TokToken from its official release and check its SHA-256
  - Done 2026-11-15: `mcflow tools install`. TokToken's pinned asset for the OS and CPU (and universal-ctags' pinned official build on Windows, licence files included), each SHA-256-checked before writing, into `~/.local/bin`. 6 unit tests; checked with the real pinned files (both run). `doctor` now points at it
- [x] 5.15 Check TokToken coverage for JSON, `.mcmeta`, GLSL and YAML
  - Done 2026-11-15: TokToken 0.5.0 indexes Java, Gradle, Python and Markdown, but not pack `.json`, `.mcmeta` or GLSL, and YAML only as text. Also found the real cause of skipped plugins (any folder with a `build.gradle` counts as vendored); the template now ships `.toktoken.json` with the smart filter off. Details: `docs/research/Stage 5 TokToken coverage.md`
- [x] 5.16 Unsupported-language flow: ask the user, research, then try a universal-ctags optlib through TokToken
  - Done 2026-11-15: the flow is in CLAUDE.md and AGENTS.md (ask, research, optlib, check with `mcflow tags`). Tried for GLSL, `.mcmeta` and YAML: ctags parses them with optlibs, but TokToken 0.5.0 never sends those extensions to ctags (`extra_extensions` can't add discovery). So `mcflow tags` covers them for now; a TokToken change is a proposal that needs the user's approval (5.16a)
- [ ] 5.16a **[you]** Decide whether to propose a TokToken change upstream (a configurable source-extension list, or honouring ctags' `--list-maps`) so pack JSON, `.mcmeta`, GLSL and YAML reach its index. Nothing is filed without approval
- [x] 5.17 Ship the optlib definitions inside the mcflow package, with tests
  - Done 2026-11-15: `templates/project/.ctags.d/` (`minecraft-glsl.ctags`, `minecraft-json.ctags`, `yaml-keys.ctags`), used by `mcflow tags`. 6 tests, including real ctags runs on a shader, `.mcmeta`, a font and a config
- [ ] 5.18 **Checkpoint:** show the results and wait for the go-ahead

## Stage 6: Knowledge base, cloud sync, `update`

- [x] 6.1 Validate knowledge-base entry frontmatter (title, minecraft_versions, pack_format, paper_api_version, verified_by, sources, date)
  - Done 2026-11-16: `mcflow/knowledge/entry.py`, standard library only. `mcflow kb validate` checks required fields, quoted release versions, pack format, proof, sources, a real non-future date, a body and a kebab-case file name
- [x] 6.2 Version matching: decide when an entry applies to the project's version
  - Done 2026-11-16: an entry applies only to versions it lists (exact) and, if it has one, the same pack format. `mcflow kb list` shows applies or lead only. Decision in PROGRESS.md
- [x] 6.3 **[you]** Confirm the knowledge-base repo name
  - Confirmed 2026-11-16: `LadonON/mcflow-knowledge`
- [x] 6.4 Create the `mcflow-knowledge` repo
  - Done 2026-11-16: https://github.com/LadonON/mcflow-knowledge (public since 2026-11-16), started from `knowledge-repo/`. A real `kb pull` and `kb push --dry-run` from a fresh workspace worked through gh's credentials
- [x] 6.4a **[you]** Decide whether to protect `main` there so changes arrive only through pull requests
  - Done 2026-11-16 (user's yes): GitHub allows protection on a private repo only with Pro, so at the user's request the repo was made public first. `main` now needs a pull request and a passing `validate` check, also for admins; no force pushes or deletion; 0 approvals required so the owner can merge their own
- [x] 6.5 `mcflow kb push`: branch, commit the new entries and open a **pull request** through gh (never push directly)
  - Done 2026-11-16: validates first, asks (or `--yes`), pushes a new `kb/...` branch (through a fork without write access) and runs `gh pr create`. Skips entries already proposed or behind. Tested with real git on a local repo and a fake gh; not yet run against GitHub (needs 6.4)
- [x] 6.6 `mcflow kb pull`: merge entries that have been approved without overwriting local edits, and report conflicts
  - Done 2026-11-16: adds new entries, updates unedited ones, keeps local edits, reports conflicts with the shared copy in `.mcflow/kb-conflicts/`, leaves locally deleted entries deleted, skips invalid shared entries. Tested against a local repo; not yet against GitHub
- [ ] 6.7 CI in the knowledge-base repo that validates entries on every PR
  - Written 2026-11-16: `knowledge-repo/.github/workflows/validate.yml` validates `entries/` and fails a `kb/` PR that touches anything else. Ran on the first push to `main` 2026-11-16 and passed. Ticked once it has also run on a real `kb push` pull request
- [x] 6.8 `mcflow update`: update skills, agents and the knowledge base without touching the user's project files. Detect files the user has edited and show diffs
  - Done 2026-11-16: `.mcflow/managed.json` from `init`. Replaces only unedited managed files, shows diffs for edited ones (`--take` accepts the new version), adds new ones, removes dropped unedited ones, has `--dry-run`, then runs `kb pull` (`--no-kb` skips it)
- [x] 6.9 Tests, plus READMEs
  - Done 2026-11-16: 66 new tests (201 total). README section, knowledge skill, workspace knowledge README, CLAUDE.md and AGENTS.md updated; `knowledge-repo/README.md` written
- [x] 6.10 **Checkpoint:** show the results and wait for the go-ahead
  - Go-ahead 2026-11-16 ("Move on to the next phase")

## Stage 7: Cross-platform, docs, release

- [ ] 7.1 Extend CI to integration tests (`init`, `doctor`, server control) on all three OSes
  - Built 2026-11-16: an `integration` job per OS (pipx-installed wheel, `tools install`, `init`, Paper from PaperMC's API with its SHA-256 checked, `server setup`, `doctor`, `update`, `kb validate`, then `mcp-server/scripts/integration.mjs`: 13 checks of server control and a bot). Passed 13/13 locally on Windows. Also fixed the red `main` CI from Stage 5 (real-ctags tests ran against BSD and Exuberant ctags; the smoke test looked for a removed `.gitkeep`). Ticked once CI passes on GitHub
- [x] 7.2 Write down each platform's limits in `doctor` and the docs
  - Done 2026-11-16: a **Platform** check (OS, CPU, tested in CI or not, limits from the pinned assets) and `docs/PLATFORMS.md`. `mcflow tags` now refuses a ctags that isn't universal-ctags
- [x] 7.3 Getting-started guide
  - Done 2026-11-16: `docs/GETTING_STARTED.md`, linked from the README
- [ ] 7.4 Humanize every README and guide with the prose humanizer
  - 2026-11-16: full pass on the new guide, PLATFORMS.md and the README sections written this stage; every other README scanned for the mechanical tells (dashes, curly quotes, stock phrases), with none found. A full pass on all of them is left for just before the release, once the install instructions change
- [ ] 7.5 Set up a trusted publisher for the PyPI release (GitHub Actions OIDC)
  - Built 2026-11-16: `.github/workflows/release-pypi.yml` (a `v*` tag builds, runs `twine check` and `scripts/check_release.py`, then publishes through OIDC in the `pypi` environment). `check_release.py` refuses a dev version, a tag that doesn't match, or an unpinned runtime release; today it reports both runtime pins missing
- [ ] 7.5a **[you]** On pypi.org, add a pending trusted publisher: project `mcflow-cli`, owner LadonON, repository mcflow, workflow `release-pypi.yml`, environment `pypi`. Then decide whether the `pypi` GitHub environment should require your approval
- [ ] 7.5b Before 7.7: publish a runtime release (`runtime-v0.1.0`), pin it with `scripts/pin_runtime.py`, and make `LadonON/mcflow` public, since `npx` and `client install` can't download from a private repo's releases
- [ ] 7.6 **[you]** Approve publishing `mcflow-cli` to PyPI
- [ ] 7.7 Release v0.1.0
- [ ] 7.8 **Final checkpoint**
