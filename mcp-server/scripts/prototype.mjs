// The Stage 2 live prototype: one MCP session that starts the server, waits for the user's Minecraft,
// joins, runs commands, opens the inventory and takes screenshots. Usage: node scripts/prototype.mjs <workspace>

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { fileURLToPath } from "node:url";

const [workspace] = process.argv.slice(2);
const entry = fileURLToPath(new URL("../dist/index.js", import.meta.url));
const client = new Client({ name: "mcflow-prototype", version: "0" });
await client.connect(new StdioClientTransport({ command: process.execPath, args: [entry], cwd: workspace, stderr: "inherit" }));

const stamp = () => new Date().toLocaleTimeString();
async function tool(name, args = {}, { allowError = false } = {}) {
  console.log(`\n[${stamp()}] >>> ${name} ${JSON.stringify(args)}`);
  const result = await client.callTool({ name, arguments: args }, undefined, { timeout: 15 * 60_000 });
  for (const c of result.content) {
    if (c.type === "text") console.log(c.text);
    else console.log(`(${c.type} content, ${c.mimeType}, ${c.data.length} base64 chars)`);
  }
  if (result.isError && !allowError) throw new Error(`${name} failed`);
  return result;
}
const text = (r) => r.content.find((c) => c.type === "text")?.text ?? "";

try {
  await tool("server_start");
  await tool("server_status");
  console.log(`\n[${stamp()}] Waiting for Minecraft: start "mcflow 26.3 (Fabric)" in the launcher.`);
  const launched = JSON.parse(text(await tool("client_launch", { waitSeconds: 600 })));
  const joined = JSON.parse(text(await tool("client_join", { timeoutSeconds: 180 })));
  const player = joined.player ?? launched.player;
  await tool("server_command", { cmd: `op ${player}` });
  await tool("server_command", { cmd: "time set day" });
  await tool("client_run", { command: "/say Hello from mcflow's real client" });
  await tool("client_run", { command: "/give @s minecraft:diamond_sword" });
  await tool("client_run", { command: "/give @s minecraft:golden_apple 5" });
  await new Promise((r) => setTimeout(r, 1500));
  await tool("client_screenshot", { task: "stage2-prototype", label: "in-world" });
  await tool("client_open_inventory");
  await new Promise((r) => setTimeout(r, 1000));
  await tool("client_screenshot", { task: "stage2-prototype", label: "inventory" });
  await tool("client_close_screen");
  await tool("server_logs", { filter: "Exception|ERROR|mcflow|joined|issued", maxEntries: 30 });
} finally {
  await tool("server_stop", {}, { allowError: true });
  await client.close();
}
