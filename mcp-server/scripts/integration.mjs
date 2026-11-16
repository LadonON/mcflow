// Task 7.1 integration test: server control and a test bot through mcflow-server, as an MCP client
// would use it. Needs a workspace where `mcflow server setup --accept-eula` has run.
// Usage: node scripts/integration.mjs <workspace-dir>    (exits 1 if any check fails)

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { fileURLToPath } from "node:url";

const [workspace] = process.argv.slice(2);
if (!workspace) {
  console.error("Usage: node scripts/integration.mjs <workspace-dir>");
  process.exit(2);
}
const entry = fileURLToPath(new URL("../dist/index.js", import.meta.url));
const mcp = new Client({ name: "mcflow-integration", version: "0" });
await mcp.connect(
  new StdioClientTransport({ command: process.execPath, args: [entry], cwd: workspace, stderr: "inherit" }),
);

async function call(name, args = {}) {
  const r = await mcp.callTool({ name, arguments: args }, undefined, { timeout: 600_000 });
  const text = r.content.map((c) => c.text ?? "").join("\n");
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    json = undefined;
  }
  return { error: !!r.isError, text, json };
}
const results = [];
function check(name, ok, detail = "") {
  results.push(ok);
  console.log(`CHECK ${ok ? "PASS" : "FAIL"} ${name}: ${String(detail).slice(0, 300)}`);
}

try {
  const tools = (await mcp.listTools()).tools.map((t) => t.name);
  check("server tools registered", ["server_start", "server_stop", "server_status", "server_logs"].every((t) => tools.includes(t)), tools.length);

  const start = await call("server_start");
  check("server_start", !start.error && start.json?.alreadyRunning === false, start.error ? start.text : `${start.json.seconds} s`);
  check("no exceptions at startup", !start.error && start.json.problems.length === 0, JSON.stringify(start.json?.problems));

  const status = await call("server_status");
  check("server_status: running, RCON answers", status.json?.running && status.json?.rconReachable, status.text);

  const list = await call("server_command", { cmd: "list" });
  check("server_command over RCON", !list.error && /players online/i.test(list.text), list.text);
  const reload = await call("server_command", { cmd: "reload confirm" });
  check("server_command refuses /reload", reload.error && /never uses \/reload/.test(reload.text), reload.text);

  const logs = await call("server_logs", { filter: "Done \\(" });
  check("server_logs finds the Done line", logs.json?.entries?.length === 1, JSON.stringify(logs.json?.entries));

  const join = await call("bot_join", { name: "CiBot" });
  check("bot_join", !join.error && join.json?.status?.online, join.error ? join.text : `${join.json.joinMs} ms`);
  const chat = await call("bot_chat", { name: "CiBot", message: "hello from ci" });
  check("bot_chat reaches the server log", chat.json?.serverLog?.some((l) => l.includes("hello from ci")), JSON.stringify(chat.json?.serverLog));
  const leave = await call("bot_leave", { name: "CiBot" });
  check("bot_leave", !leave.error, leave.text);

  const restart = await call("server_restart");
  check("server_restart", !restart.error && restart.json?.problems?.length === 0, restart.error ? restart.text : `${restart.json.seconds} s`);

  const stop = await call("server_stop");
  check("server_stop is clean", !stop.error && stop.json?.wasRunning && !stop.json?.forced, stop.text);
  const after = await call("server_status");
  check("server_status after stop", after.json?.running === false, after.text);
} catch (e) {
  check("no unexpected errors", false, e?.stack ?? e);
  await call("server_stop").catch(() => undefined);
} finally {
  await mcp.close();
}

const failed = results.filter((ok) => !ok).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
