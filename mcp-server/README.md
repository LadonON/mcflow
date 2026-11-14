# mcflow-server

The MCP server that lets Claude Code (or any MCP client) run a local Paper test server for an mcflow workspace. TypeScript, Node 22+.

**Stage 2 status:** the server-control tools work. Bot tools (Stage 4) and the real-client tools (Stage 2, after the Fabric mod) are still to come.

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
