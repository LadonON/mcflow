# mcflow-server

The MCP server that lets Claude Code (or any MCP client) run a local Paper test server for an mcflow workspace. TypeScript, Node 22+.

**Status (2026-11-15):** the server-control tools, the real-client tools (`client_*`, which drive mcflow's Fabric mod) and the bot tools (`bot_*`) work. The quality gates (`gate_*`) work too.

## Tools

| Tool | What it does |
|---|---|
| `server_start` | Starts Paper with the Java chosen by `mcflow server setup`, waits for `Done (…)!`, and reports exceptions logged during startup. Fails with a clear message if the EULA isn't accepted. |
| `server_stop` | Sends RCON `stop`, waits up to 60 s, and only then kills the process. |
| `server_restart` | Stop, then start. mcflow never uses `/reload`, and `server_command` refuses it. |
| `server_status` | Whether it's running, whether RCON answers, and the output of `list`. |
| `server_command` | Runs any console command through RCON. |
| `server_logs` | Reads `server/logs/latest.log`. Pass back `nextLine` as `sinceLine` to get only new output. Stack traces are grouped with the line that logged them and listed under `problems`. |
| `plugin_deploy` | Runs `gradlew build` in `plugins/<project>`, copies the plugin jar into `server/plugins/`, and restarts the server if it's running. |
| `resourcepack_build_and_serve` | Validates `resourcepacks/<pack>` (pack.mcmeta, JSON syntax, and `pack_format` against the server's vanilla jar), zips it the same way every time, computes the SHA-1, serves it on `127.0.0.1:<pack_port>`, updates `server.properties`, and restarts the server if needed. |

### Bot tools

Bots are [mineflayer](https://github.com/PrismarineJS/mineflayer) clients that join the test server in offline mode. They need no Minecraft account and no screen.

| Tool | What it does |
|---|---|
| `bot_join` | Connects a bot and waits until it spawns; the bot accepts the server's resource pack. Returns the join time and whether the bot's protocol is being translated (see below). |
| `bot_leave` | Disconnects one bot, or all of them. Bots also leave when mcflow-server shuts down. |
| `bot_chat` | Sends chat or a `/command` as the bot. Returns the chat lines the bot received and what the server logged. |
| `bot_move` | Holds movement keys (`forward`, `back`, `left`, `right`, `jump`, `sprint`, `sneak`) for a time, then reports the position before and after. |
| `bot_look` | Turns the bot: yaw and pitch in Minecraft's convention (degrees; yaw 0 = south), or a point to look at. |
| `bot_use_item` | Picks a hotbar slot, then right-clicks with the held item (`use`, optionally held down), right-clicks the block in view (`activate_block`, which waits for a container's window), or left-clicks (`attack`). |
| `bot_inventory` | The bot's items by slot, and the open window's title and items if there is one. |
| `bot_click_window_slot` | Clicks a slot in the open window (left/right, normal/shift/number-key/drop). |
| `bot_status` | Position, view, health, food, game mode, open window, and the last kick or error, for one bot or all. |
| `bot_swarm` | Joins up to 200 bots (staggered) and runs one behavior on all of them for a set time, then disconnects them: `idle`, `wander` (random walks and jumps), `use_feature` (run a command such as `/menu`, turn the head, close it, repeat) or `join_leave` (each bot keeps joining and leaving). Reports joins (with min, median and max join time), kicks, actions, the server's TPS before and after, server-log problems, and movement corrections, with join-time ones counted apart. |

**Versions.** If mineflayer supports the server's Minecraft version, bots speak it natively. If the server is newer (Paper 26.3 while mineflayer stops at 26.1), bots join as mineflayer's newest version, and the server needs **ViaBackwards** to translate.

**mineflayer workarounds.** mineflayer 4.39.0 has two bugs that stop bots from joining a 26.x server, and `src/bots.ts` works around both: it sends the resource-pack reply's UUID as a string, and it sends `tick_end` after every movement packet. Details: `docs/research/Stage 4 Bots.md`.

**Spawn protection.** Inside `spawn-protection` (16 blocks around the world spawn by default), non-operator bots can't use or change blocks. `activate_block` says so when that's why a container didn't open. Op the bot, or test further from spawn.

**Swarm reports.** Two things show up in every swarm and are reported separately rather than as problems. (1) Paper logs a few "moved too quickly!" warnings for each bot in the first seconds after it joins, at its spawn point; nothing moves. (2) When bots leave quickly, Paper logs "Failed to deliver packet" for messages meant for a connection that just closed. A swarm needs `max-players` at least as high as its bot count; `mcflow server setup` sets 200.

**Debugging.** Set `MCFLOW_BOT_TRACE=1` in mcflow-server's environment to log each bot's non-routine packets to stderr.

### Quality gates

| Tool | Passes when |
|---|---|
| `gate_performance` | A bot swarm (10 bots using `/menu` by default) runs while Paper's `mspt` is sampled every 5 s. The 95th-percentile 5-second average tick time is at most 50 ms, and the median hasn't risen more than 25% (and 1 ms) over the saved baseline in `.mcflow/gates/perf-<name>.json`. The first run records the baseline. `profile: true` saves a spark profile **locally**. |
| `gate_memory` | Cycles of bots joining, using the feature and leaving; class histograms (`jcmd`, after a full GC, no bots online) after a warm-up, after N cycles and after 2N. No class from the plugin's package, and no Bukkit listener registration or scheduled task, grows at both steps. Needs a full JDK (for `jcmd`). |
| `gate_thread_safety` | No main-thread-only Bukkit call inside code that runs on another thread (async tasks, futures, threads, Netty handlers, async events) without a `runTask` hop; and no "Asynchronous …!" catch in the server log since `sinceLine`. The static half is a heuristic over source text. |
| `gate_resource_pack` | `pack.mcmeta` and the pack format match the server, all JSON parses, every referenced texture, model and font exists (in the pack, or in the Minecraft client jar for `minecraft:` references), and bitmap fonts obey the game's rules (ascent no greater than height, equal-length `chars` rows, a texture that divides into the glyph grid). |

**spark stays local.** Paper bundles spark, and some spark commands upload to spark.lucko.me (`spark health` always does; a profile with `--timeout`, or stopped without `--save-to-file`, does too). The gates only ever run `spark profiler start` (no timeout), `spark profiler stop --save-to-file` and Paper's `mspt`. spark records every upload in `server/plugins/spark/activity.json`; `scripts/gates-live.mjs` checks it.

## How it finds things

- **Workspace:** the nearest folder at or above its working directory (or `$MCFLOW_PROJECT`) that contains `mcflow.toml`. Claude Code starts MCP servers in the project folder.
- **Machine settings:** `.mcflow/local.toml`, written by `mcflow server setup` (Python). It holds the Java path, ports and RCON password, and is git-ignored.
- **The server's PID** is kept in `.mcflow/server.pid`, so a restarted MCP server can still stop a running Paper server.

Outside a workspace, the server still starts, and every tool returns an error that says what to do.

## Develop

```bash
npm install
npm test            # vitest, including a fake RCON server
npm run build       # -> dist/
node scripts/smoke.mjs <workspace> server_status   # talk to dist/ over stdio like Claude Code does
```
