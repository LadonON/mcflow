# Build Prompt: Minecraft Plugin AI Workflow

> Paste this into Claude Code from an empty folder. Replace `mcflow` with your chosen name everywhere (package, CLI and folder names) before you start, or tell Claude the name in your first message.

---

## Role and goal

You are building **mcflow**: an installable AI development workflow for building advanced Paper (Minecraft) plugins that use custom resource packs. The workflow is a bundle of MCP servers, skills, helper-agent definitions and built-in instructions. Claude Code is the main target, and other AI coding tools should still be able to use it.

The workflow has to produce code fit for a production server with more than 500 concurrent players. Above everything else, put ease of use for the end user and the quality of the output first.

Build this in stages, following the **Build order** below. Prove the vertical slice end to end before you add breadth. At the end of each stage, stop, show me what works, and wait for my go-ahead.

---

## Ground rules for you while building this

- Before you use any library, API, file format or tool version, check its current documentation. Do not rely on memory for Minecraft resource-pack formats, Paper APIs, MCP SDKs or the tools listed below.
- Pin versions you've verified in a single `versions.toml` (or similar) that the installer reads.
- Each component gets its own README and tests.
- If a requirement below is technically infeasible as written, say so, propose the closest alternative and ask me before you substitute it.

---

## 1. Installation (Python)

- Ship as a Python package that installs with `pipx install mcflow` (from a local path or git URL during development).
- CLI commands:
  - `mcflow init [path]`: create a new project workspace (see section 2).
  - `mcflow doctor`: check dependencies and print exact fix-it instructions for anything missing: Java (with the version that matches the chosen Paper version), Node.js 18+, universal-ctags (**not** exuberant-ctags), the TokToken binary and Claude Code.
  - `mcflow update`: pull the latest skills, agents and knowledge base without overwriting the user's project files.
  - `mcflow kb pull` / `mcflow kb push`: sync the knowledge base (see section 7).
- The installer should download third-party tools from their official release sources. Don't vendor or modify them. This matters for TokToken in particular, which is AGPL-3.0.
- Support macOS, Linux and Windows. Where a tool doesn't support one of them, `doctor` must say so clearly.

## 2. Project workspace created by `mcflow init`

```
<project>/
├── CLAUDE.md            # Claude Code instructions (full workflow rules)
├── AGENTS.md            # Same core rules for non-Claude tools
├── .mcp.json            # Registers mcflow MCP servers + TokToken
├── .claude/
│   ├── skills/          # Workflow skills (section 8)
│   └── agents/          # Helper agent definitions (section 9)
├── assets/              # User drag-and-drop folder: logos, images, videos, sounds, models
│   └── README.md        # Explains what to drop here and how it's used
├── research/            # All research docs, one per topic, titled by subject
├── knowledge/           # Local knowledge base (section 7)
├── plugins/             # Plugin source projects (Gradle, Java)
├── resourcepacks/       # Resource pack sources
├── layouts/             # UI layouts: user-provided or Claude-proposed (section 10)
└── server/              # Local test server (section 3)
```

## 3. Test server setup (first run)

When development starts in a new project:

1. Ask the user which Minecraft/Paper version the plugin targets.
2. **Do not download Paper jars.** Ask the user to provide the Paper jar for that version and put it in `server/`. Wait for it, then verify it's actually a Paper jar.
3. Install **ViaVersion** (from its official distribution) so newer clients can join.
4. Configure the server for local development:
   - Bind to localhost only.
   - Offline mode, so the bot can join (localhost only).
   - Enable RCON with a randomly generated password stored in a git-ignored local file.
   - Set the resource pack to be served by the local file server (section 4), with a correct SHA-1 hash that updates on every rebuild, and `require-resource-pack` enabled.
5. Pick the correct Java version for that Paper version, or tell the user exactly what to install.

## 4. MCP server: `mcflow-server` (build this yourself)

Don't depend on `arjunkmrm/mcp-minecraft`. It's tied to Minecraft 1.21 and has no screenshots. Build one MCP server (TypeScript or Python, your choice; justify it) with three subsystems:

**A. Server control**
- `server_start`, `server_stop`, `server_restart`, `server_status`
- `server_command(cmd)` runs through RCON and returns the output
- `server_logs(since, filter)` tails `latest.log` and flags exceptions or stack traces
- `plugin_deploy(project)` builds with Gradle, copies the jar and restarts or reloads cleanly (no `/reload`)
- `resourcepack_build_and_serve(pack)` validates and zips the pack, computes SHA-1, serves it over a local HTTP server and updates `server.properties`

**B. Bot player (mineflayer)**
- `bot_join`, `bot_leave`, `bot_chat` (including player commands), `bot_move`, `bot_look`, `bot_use_item`, `bot_inventory`, `bot_click_window_slot` (for GUI testing), `bot_status`
- `bot_swarm(count, behavior)` for load tests (section 6)

**C. Real client for visual verification**
- A scripted, real Minecraft Java client that joins the test server, accepts the resource pack and takes screenshots. Only a real client renders resource-pack models, fonts, GUIs, shaders and animations, so a bot isn't enough here.
- Tools: `client_launch`, `client_join`, `client_run(command)`, `client_screenshot(label)`, `client_open_inventory`, `client_quit`
- Look into options (for example HeadlessMC, a Fabric client mod that exposes a local control socket, or a virtual display on Linux) and present the trade-offs to me before you commit to one. **This is the riskiest part of the project, so prototype it in Stage 2.**
- Save screenshots to `server/screenshots/<task>/<label>.png`.

## 5. Code indexing: TokToken

- Register TokToken as an MCP server (`toktoken serve`, STDIO) in `.mcp.json`.
- **Always use the indexer to search the codebase.** Don't fall back to grep or whole-file reads unless the indexer can't answer.
- Re-index after every code change. A helper agent does this (section 9).
- **Unsupported languages:** when files in a language TokToken can't parse show up (likely candidates: resource-pack JSON and `.mcmeta`, GLSL `.fsh`/`.vsh`/`.glsl`, YAML configs):
  1. Ask the user for permission to build a parser for that language.
  2. If they agree, research the language deeply first (writing to `research/`).
  3. Prefer the lightest working option. First, check whether a universal-ctags language definition (optlib `.ctags` file) works through TokToken. Only if it doesn't, propose a deeper parser contribution.
  4. Keep custom parser definitions inside the mcflow package. Don't modify the TokToken source.

## 6. Production-quality gates (500+ players)

No change is "done" until it passes all of these:

- **Build:** compiles with no warnings that matter.
- **Unit tests:** MockBukkit tests for the new logic.
- **Thread safety:** no blocking file, network or database work on the main thread. Use Paper's schedulers correctly, and don't touch the Bukkit API from async threads.
- **Runtime:** deploys to the test server with no exceptions in the logs.
- **Performance:** a bot swarm (`bot_swarm`) under load, profiled with spark. Report tick time (MSPT) before and after. Flag regressions.
- **Memory:** players repeatedly join, leave and use the feature; check for leaked listeners, tasks or per-player maps.
- **Resource pack:** valid for the target version's `pack_format`, with every referenced model, texture and font present.

## 7. Knowledge base

- `knowledge/` holds Markdown entries, one per learned technique (for example "Animated item textures with .mcmeta").
- Each entry has frontmatter with: `title`, `minecraft_versions`, `pack_format` (if relevant), `paper_api_version`, `verified_by` (how it was proven: test name, screenshot path), `sources` and `date`.
- **When to add entries:** whenever Claude learns something it didn't know during development and **verifies it works in-game or in tests**. Unverified findings stay in `research/` only.
- **Mandatory lookup rule:** before using any API, file format or resource-pack feature, check `knowledge/`. If there's no entry, or the entry doesn't match the project's Minecraft version or pack format, trigger research (section 8).
- **Cloud sync:** the cloud knowledge base is a GitHub repo. When a task finishes, Claude asks the user whether to upload new entries. If they say yes, `mcflow kb push` opens a **pull request** (never a direct push) so a human reviews it before it reaches other installs. `mcflow kb pull` merges approved entries into the local knowledge base.

## 8. Skills (`.claude/skills/`)

Write each one as a proper `SKILL.md` with a clear trigger description:

- **research:** automatic, no user interaction needed. Triggered by the knowledge-base lookup rule or any uncertainty about an API or format. Sends out researcher agents and writes **one Markdown doc per topic** to `research/<Topic Being Researched>.md`, with sources and the date.
- **knowledge:** the read, write and version-match rules from section 7.
- **verify:** runs the section 6 gates and the in-game checks, then gathers the verifier agents' reports.
- **code-humanizer:** written by you. `blader/humanizer` only handles prose and leaves code alone, so this is a separate skill. It removes signs of AI-written code: comments that restate the code, needless defensive checks, generic names, inconsistent style, leftover scaffolding. It matches the project's existing conventions and never changes behavior.
- **humanizer (prose):** install `blader/humanizer` and use it on READMEs, changelogs, commit messages and anything written for the user.
- **resource-packs:** pack structure, `pack_format` per version, item models and custom model data or item model components (based on the version), fonts and custom GUI glyphs, sounds, `.mcmeta` animations and shaders. Check each against current docs first.
- **paper-plugin:** project layout, Gradle setup, Paper API patterns, commands, configs, persistence and async-safety rules.
- **ui-layout:** the flow in section 10.

## 9. Helper agents (`.claude/agents/`)

Use a smaller, cheaper model than the main session for each:

- **researcher:** carries out research tasks and writes to `research/`. The main session sends several in parallel for broad topics.
- **indexer:** re-indexes the codebase with TokToken after every change and reports problems.
- **verifier-visual:** gets screenshots plus the expected layout or spec and judges how the UI looks, whether it's aligned, whether textures load and whether it matches the approved layout. Returns pass/fail with specific defects.
- **verifier-output:** gets command output and log excerpts and judges correctness, error messages and formatting.

Also write `AGENTS.md` with the same rules for tools that don't support subagents (they do these steps inline).

## 10. UI design flow

Whenever a task involves player-facing UI (inventories, GUIs, HUD/fonts, scoreboards, boss bars, chat formatting):

1. Ask the user for their layout: a sketch, image or description in `layouts/`.
2. If they don't have one, propose a layout (a rendered mockup image saved to `layouts/`), using any relevant files in `assets/`.
3. The user approves it, asks for changes or uploads their own. Repeat until it's approved.
4. The approved layout becomes the spec the visual verifier checks against.

## 11. Mandatory task pipeline (put this in CLAUDE.md)

For every development task, in this order:

1. Check the knowledge base, then research if needed.
2. Plan the work. For UI, run the layout flow.
3. Implement.
4. **Verify:** build, tests, deploy, logs, then the verifier agents check in-game command output and screenshots, then the performance and memory gates.
5. Run code-humanizer on this task's changed code.
6. **Re-verify:** rebuild, run the tests and repeat a quick in-game check. Humanizing must not break anything.
7. Re-index (indexer agent).
8. Write verified learnings to `knowledge/`.
9. **Only now** present the change to the user, with screenshots, test results and the performance numbers.
10. Ask the user whether to upload new knowledge to the cloud knowledge base.

Never show the user unverified, un-humanized or un-indexed work as finished.

## Build order

- **Stage 1:** Python package skeleton, `init`, `doctor`, project template, `CLAUDE.md` and `AGENTS.md` drafts.
- **Stage 2:** `mcflow-server` server control plus a **real-client screenshot prototype** (present the options first).
- **Stage 3, vertical slice:** a sample plugin with one custom item model and one custom GUI, taken through the full section 11 pipeline end to end.
  - *Amended by the user on 2026-11-14:* the slice is a custom on-screen UI element opened by a command, in the style of BuiltByBit's "Ultimate UI" and resembling a reference image the user provides (the stage asks for it first). See `docs/TASKS.md`, Stage 3.
- **Stage 4:** bot subsystem, swarm load testing, spark integration.
- **Stage 5:** all skills and helper agents, TokToken integration, unsupported-language flow.
- **Stage 6:** knowledge base and cloud sync with pull requests, then `mcflow update`.
- **Stage 7:** cross-platform testing, docs and a getting-started guide.

Start with Stage 1. Ask me for anything you need first, such as the workflow name, a GitHub repo for the cloud knowledge base, or my OS.
