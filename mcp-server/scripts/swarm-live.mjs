// Task 4.3 live test: bot_swarm with every behavior against a workspace's test server.
// Usage: node scripts/swarm-live.mjs <workspace>   (the workspace's server must be set up; the menu plugin is used)
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { fileURLToPath } from "node:url";

const [workspace] = process.argv.slice(2);
const entry = fileURLToPath(new URL("../dist/index.js", import.meta.url));
const mcp = new Client({ name: "mcflow-swarm-live", version: "0" });
await mcp.connect(new StdioClientTransport({ command: process.execPath, args: [entry], cwd: workspace, stderr: "ignore" }));

async function call(name, args = {}) {
  const r = await mcp.callTool({ name, arguments: args }, undefined, { timeout: 15 * 60_000 });
  const text = r.content.map((c) => c.text ?? "").join("\n");
  let json;
  try { json = JSON.parse(text); } catch { json = undefined; }
  return { error: !!r.isError, text, json };
}
const results = [];
const check = (name, ok, detail = "") => { results.push({ name, ok }); console.log(`CHECK ${ok ? "PASS" : "FAIL"} ${name}: ${String(detail).slice(0, 300)}`); };
const summary = (r) => r.json
  ? `joined ${r.json.joined}/${r.json.requested}, failed ${r.json.failedJoins.length}, kicked ${r.json.kicked.length}, joinMs ${JSON.stringify(r.json.joinMs)}, ` +
    `actions ${JSON.stringify(r.json.actions)}, tps ${JSON.stringify(r.json.tps)}, problems ${r.json.serverLog.problems.length}, ` +
    `moves corrected ${r.json.serverLog.movementCorrections} (+${r.json.serverLog.joinTimeCorrections} at join), cantKeepUp ${r.json.serverLog.cantKeepUp}, closed-connection deliveries ${r.json.serverLog.deliveryToClosedConnections}, errors ${r.json.errors.length}${r.json.hint ? ", HINT " + r.json.hint : ""}`
  : r.text;
const clean = (r) => !r.error && r.json.failedJoins.length === 0 && r.json.kicked.length === 0 && r.json.errors.length === 0 && r.json.serverLog.problems.length === 0;

try {
  await call("server_start");

  const idle = await call("bot_swarm", { count: 10, behavior: "idle", durationSeconds: 10 });
  check("idle x10", clean(idle) && idle.json.joined === 10, summary(idle));

  const wander = await call("bot_swarm", { count: 10, behavior: "wander", durationSeconds: 30, namePrefix: "Wander" });
  check("wander x10", clean(wander) && wander.json.actions.wander >= 50, summary(wander));
  check("wander: no movement corrections after join", wander.json?.serverLog.movementCorrections === 0, JSON.stringify(wander.json?.serverLog.examples));

  const feature = await call("bot_swarm", { count: 10, behavior: "use_feature", durationSeconds: 30, namePrefix: "Menu", featureCommand: "/menu" });
  check("use_feature /menu x10", clean(feature) && feature.json.actions.feature_open >= 30, summary(feature));
  // Some bots were inside the menu when the run ended; the plugin must have restored their game mode on quit.
  const back = await call("bot_join", { name: "Menu3" });
  const mode = back.json?.status?.gameMode;
  check("a swarm bot rejoins in survival (menu closed on quit)", mode === "survival", mode);
  await call("bot_leave");

  const jl = await call("bot_swarm", { count: 10, behavior: "join_leave", durationSeconds: 30, namePrefix: "Churn" });
  check("join_leave x10", clean(jl) && jl.json.actions.join >= 40 && jl.json.actions.join === jl.json.actions.leave, summary(jl));

  const big = await call("bot_swarm", { count: 50, behavior: "idle", durationSeconds: 15, staggerMs: 100, namePrefix: "Big" });
  check("idle x50", clean(big) && big.json.joined === 50, summary(big));

  const status = await call("bot_status");
  check("no bots left connected", Array.isArray(status.json) && status.json.every((b) => !b.online), JSON.stringify(status.json?.length));
} finally {
  await call("server_stop");
  await mcp.close();
  const failed = results.filter((r) => !r.ok).map((r) => r.name);
  console.log(`SUMMARY ${results.length - failed.length}/${results.length} passed${failed.length ? "; failed: " + failed.join(", ") : ""}`);
  process.exit(0);
}
