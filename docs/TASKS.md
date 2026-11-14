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
- [ ] 2.1 **[research]** Compare TypeScript and Python for the MCP server against the current MCP SDKs and the mineflayer ecosystem, then write the case for the choice
- [ ] 2.2 **[research]** Real-client options: HeadlessMC, a Fabric mod with a local control socket, a virtual display (Xvfb) on Linux, and others. For each, check whether it supports Microsoft sign-in, whether it can run without a screen, how screenshots are taken, the range of Minecraft versions it covers (including 26.x), how it behaves on Windows, macOS and Linux, and its license
- [ ] 2.3 **[you]** Choose the language and the real-client approach once the trade-offs have been presented

### 2B. Test-server setup (section 3)
- [ ] 2.4 First-run flow: ask for the Paper version, then ask the user to put a Paper jar in `server/`
- [ ] 2.5 Paper jar check: inspect the manifest or the classes inside the jar, and read its version
- [ ] 2.6 **[research]** ViaVersion: its official distribution, the API to download it, and version compatibility
- [ ] 2.7 Install ViaVersion
- [ ] 2.8 Generate `server.properties`: localhost only, offline mode, RCON with a random password in a git-ignored file, `require-resource-pack`, and accept the EULA only after the user explicitly agrees
- [ ] 2.9 Choose the Java version for the server (this reuses `doctor`'s Java detection)

### 2C. Server-control tools
- [ ] 2.10 MCP server skeleton, registered in the `.mcp.json` template
- [ ] 2.11 `server_start`, `server_stop`, `server_restart` and `server_status` (process management that works on every OS)
- [ ] 2.12 `server_command`, using an RCON client
- [ ] 2.13 `server_logs(since, filter)`, which also detects exceptions and stack traces
- [ ] 2.14 `plugin_deploy(project)`: Gradle build, copy the jar, then a clean restart (never `/reload`)
- [ ] 2.15 **[research]** Resource-pack zip rules, the SHA-1 requirement, and how `pack_format` maps to versions
- [ ] 2.16 `resourcepack_build_and_serve(pack)`: validate, zip, compute the SHA-1, serve it over local HTTP and update `server.properties`
- [ ] 2.17 Tests for each tool, plus a README

### 2D. Real-client prototype
- [ ] 2.18 Prototype the chosen client: Microsoft sign-in, launch, join the local server, accept the resource pack, take a screenshot
- [ ] 2.19 `client_launch`, `client_join`, `client_run`, `client_screenshot`, `client_open_inventory`, `client_quit`
- [ ] 2.20 Save screenshots to `server/screenshots/<task>/<label>.png`
- [ ] 2.21 Write down the limits per OS and how they show up in `doctor`
- [ ] 2.22 **Checkpoint:** show the results and wait for the go-ahead

## Stage 3: Vertical slice (section 11, end to end)

- [ ] 3.1 **[you]** Choose the slice's Paper version (or accept the latest)
- [ ] 3.2 Write a first draft of the paper-plugin skill and the resource-packs skill, enough for the slice
- [ ] 3.3 Knowledge-base lookup, then research: custom item models and custom GUIs for that version
- [ ] 3.4 Sample Gradle plugin project in `plugins/`
- [ ] 3.5 One custom item model in `resourcepacks/`
- [ ] 3.6 UI layout flow: propose a mockup in `layouts/` and **[you]** approve it
- [ ] 3.7 Implement the custom GUI (inventory plus font glyphs, as the version allows)
- [ ] 3.8 MockBukkit unit tests
- [ ] 3.9 Verify: build, tests, deploy, logs, command output, and screenshots against the layout
- [ ] 3.10 Run the code-humanizer (first draft) over the slice's code
- [ ] 3.11 Re-verify
- [ ] 3.12 Re-index (TokToken by hand at this point)
- [ ] 3.13 Write the first verified entries in `knowledge/`
- [ ] 3.14 Present screenshots, test results and the open gaps (performance and memory checks arrive in Stage 4)
- [ ] 3.15 **Checkpoint:** show the results and wait for the go-ahead

## Stage 4: Bots, swarm load tests, spark

- [ ] 4.1 **[research]** mineflayer: which versions it supports (including 26.x), and how it behaves in offline mode
- [ ] 4.2 `bot_join`, `bot_leave`, `bot_chat`, `bot_move`, `bot_look`, `bot_use_item`, `bot_inventory`, `bot_click_window_slot`, `bot_status`
- [ ] 4.3 `bot_swarm(count, behavior)`, with defined behaviors (idle, wander, use-feature, join-leave loop)
- [ ] 4.4 **[research]** spark: installation, profiler commands, and reading MSPT and its reports from the command line or RCON
- [ ] 4.5 Performance gate: record MSPT before and after, and flag regressions against a threshold
- [ ] 4.6 Memory gate: repeated join, leave and use cycles, then check for leaked listeners, tasks and per-player maps (heap and object counts)
- [ ] 4.7 Thread-safety gate: static checks plus runtime detection of async access to the Bukkit API
- [ ] 4.8 Resource-pack gate: `pack_format`, and that every model, texture and font it references is present
- [ ] 4.9 Run the slice through every gate
- [ ] 4.10 **Checkpoint:** show the results and wait for the go-ahead

## Stage 5: Skills, agents, TokToken, unsupported languages

- [ ] 5.1 Skill: research
- [ ] 5.2 Skill: knowledge
- [ ] 5.3 Skill: verify
- [ ] 5.4 Skill: code-humanizer (final), with tests that check it leaves behavior unchanged
- [ ] 5.5 Install the humanizer (prose) skill from the pinned blader/humanizer commit
- [ ] 5.6 Skill: resource-packs (final, aware of each version)
- [ ] 5.7 Skill: paper-plugin (final)
- [ ] 5.8 Skill: ui-layout
- [ ] 5.9 Agent: researcher (Sonnet)
- [ ] 5.10 Agent: indexer (Haiku)
- [ ] 5.11 Agent: verifier-visual (Sonnet)
- [ ] 5.12 Agent: verifier-output (Sonnet)
- [ ] 5.13 Finalise `CLAUDE.md` and `AGENTS.md`
- [ ] 5.14 Make the installer download TokToken from its official release and check its SHA-256
- [ ] 5.15 Check TokToken coverage for JSON, `.mcmeta`, GLSL and YAML
- [ ] 5.16 Unsupported-language flow: ask the user, research, then try a universal-ctags optlib through TokToken
- [ ] 5.17 Ship the optlib definitions inside the mcflow package, with tests
- [ ] 5.18 **Checkpoint:** show the results and wait for the go-ahead

## Stage 6: Knowledge base, cloud sync, `update`

- [ ] 6.1 Validate knowledge-base entry frontmatter (title, minecraft_versions, pack_format, paper_api_version, verified_by, sources, date)
- [ ] 6.2 Version matching: decide when an entry applies to the project's version
- [ ] 6.3 **[you]** Confirm the knowledge-base repo name
- [ ] 6.4 Create the `mcflow-knowledge` repo
- [ ] 6.5 `mcflow kb push`: branch, commit the new entries and open a **pull request** through gh (never push directly)
- [ ] 6.6 `mcflow kb pull`: merge entries that have been approved without overwriting local edits, and report conflicts
- [ ] 6.7 CI in the knowledge-base repo that validates entries on every PR
- [ ] 6.8 `mcflow update`: update skills, agents and the knowledge base without touching the user's project files. Detect files the user has edited and show diffs
- [ ] 6.9 Tests, plus READMEs
- [ ] 6.10 **Checkpoint:** show the results and wait for the go-ahead

## Stage 7: Cross-platform, docs, release

- [ ] 7.1 Extend CI to integration tests (`init`, `doctor`, server control) on all three OSes
- [ ] 7.2 Write down each platform's limits in `doctor` and the docs
- [ ] 7.3 Getting-started guide
- [ ] 7.4 Humanize every README and guide with the prose humanizer
- [ ] 7.5 Set up a trusted publisher for the PyPI release (GitHub Actions OIDC)
- [ ] 7.6 **[you]** Approve publishing `mcflow-cli` to PyPI
- [ ] 7.7 Release v0.1.0
- [ ] 7.8 **Final checkpoint**
