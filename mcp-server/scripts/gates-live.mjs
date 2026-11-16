// Task 4.9: run a workspace's plugin and pack through every gate on the live test server.
// Usage: node scripts/gates-live.mjs <workspace> <plugin project> <pack>
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const [workspace, project = "menu", pack = "menu"] = process.argv.slice(2);
const entry = fileURLToPath(new URL("../dist/index.js", import.meta.url));
const mcp = new Client({ name: "mcflow-gates-live", version: "0" });
await mcp.connect(new StdioClientTransport({ command: process.execPath, args: [entry], cwd: workspace, stderr: "ignore" }));

async function call(name, args = {}) {
  const r = await mcp.callTool({ name, arguments: args }, undefined, { timeout: 20 * 60_000 });
  const text = r.content.map((c) => c.text ?? "").join("\n");
  let json;
  try { json = JSON.parse(text); } catch { json = undefined; }
  return { error: !!r.isError, text, json };
}
const results = [];
const check = (name, ok, detail = "") => { results.push({ name, ok }); console.log(`CHECK ${ok ? "PASS" : "FAIL"} ${name}: ${String(detail).slice(0, 600)}`); };
const sparkLog = join(workspace, "server", "plugins", "spark", "activity.json");
const uploads = () => (existsSync(sparkLog) ? JSON.parse(readFileSync(sparkLog, "utf8")).filter((a) => a.data?.type === "url").length : 0);

const uploadsBefore = uploads();
try {
  const rp = await call("gate_resource_pack", { pack });
  check("resource-pack gate", !rp.error && rp.json.pass, rp.error ? rp.text : JSON.stringify({ issues: rp.json.issues, checked: rp.json.checked, vanilla: rp.json.vanillaReferences }));

  await call("server_start");
  const logStart = JSON.parse((await call("server_logs", { filter: "zzzz", maxEntries: 1 })).text).nextLine;

  const perf1 = await call("gate_performance", { baseline: "menu-gates", saveBaseline: true, count: 10, durationSeconds: 60, profile: true });
  check("performance gate (baseline run, with a local profile)", !perf1.error && perf1.json.pass,
    perf1.error ? perf1.text : JSON.stringify({ idle: perf1.json.idle, load: perf1.json.load, note: perf1.json.baselineNote, actions: perf1.json.swarm.actions, profile: perf1.json.profile, failures: perf1.json.failures }));
  const perf2 = await call("gate_performance", { baseline: "menu-gates", count: 10, durationSeconds: 60 });
  check("performance gate (compared with the baseline)", !perf2.error && perf2.json.pass && perf2.json.baselineNote.startsWith("compared"),
    perf2.error ? perf2.text : JSON.stringify({ load: perf2.json.load, regression: perf2.json.regression, note: perf2.json.baselineNote, failures: perf2.json.failures }));

  const mem = await call("gate_memory", { project, botsPerCycle: 5, cyclesPerStep: 3, cycleSeconds: 10 });
  check("memory gate", !mem.error && mem.json.pass,
    mem.error ? mem.text : JSON.stringify({ leaks: mem.json.leaks, heap: mem.json.heapUsedMb, cycles: mem.json.cycles, classes: mem.json.classes, problems: mem.json.problems }));

  const ts = await call("gate_thread_safety", { project, sinceLine: logStart });
  check("thread-safety gate", !ts.error && ts.json.pass, ts.error ? ts.text : JSON.stringify(ts.json));
} finally {
  await call("server_stop");
  await mcp.close();
  const newUploads = uploads() - uploadsBefore;
  check("nothing uploaded to spark.lucko.me", newUploads === 0, `${newUploads} new upload(s) in plugins/spark/activity.json`);
  const failed = results.filter((r) => !r.ok).map((r) => r.name);
  console.log(`SUMMARY ${results.length - failed.length}/${results.length} passed${failed.length ? "; failed: " + failed.join(", ") : ""}`);
  process.exit(0);
}
