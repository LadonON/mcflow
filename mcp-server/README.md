# mcflow-server

The MCP server that lets Claude Code (or any MCP client) run a local Paper test server for an mcflow workspace. TypeScript, Node 22+.

**Status (2026-11-15):** the server-control tools, the real-client tools (`client_*`, which drive mcflow's Fabric mod) and the bot tools (`bot_*`) work. Swarms and the performance, memory and thread-safety gates are still to come (Stage 4).

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

**Versions.** If mineflayer supports the server's Minecraft version, bots speak it natively. If the server is newer (Paper 26.3 while mineflayer stops at 26.1), bots join as mineflayer's newest version, and the server needs **ViaBackwards** to translate.

**mineflayer workarounds.** mineflayer 4.39.0 has two bugs that stop bots from joining a 26.x server, and `src/bots.ts` works around both: it sends the resource-pack reply's UUID as a string, and it sends `tick_end` after every movement packet. Details: `docs/research/Stage 4 Bots.md`.

**Spawn protection.** Inside `spawn-protection` (16 blocks around the world spawn by default), non-operator bots can't use or change blocks. `activate_block` says so when that's why a container didn't open. Op the bot, or test further from spawn.

**Debugging.** Set `MCFLOW_BOT_TRACE=1` in mcflow-server's environment to log each bot's non-routine packets to stderr.

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
