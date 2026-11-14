// Starts dist/index.js over stdio, lists its tools and calls one, the way an MCP client would.
// Usage: node scripts/smoke.mjs <workspace-dir> [tool-name]

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { fileURLToPath } from "node:url";

const [workspace, tool = "server_status"] = process.argv.slice(2);
const entry = fileURLToPath(new URL("../dist/index.js", import.meta.url));

const client = new Client({ name: "mcflow-smoke", version: "0" });
await client.connect(
  new StdioClientTransport({ command: process.execPath, args: [entry], cwd: workspace, stderr: "inherit" }),
);
const { tools } = await client.listTools();
console.log("tools:", tools.map((t) => t.name).join(", "));
const result = await client.callTool({ name: tool, arguments: {} });
console.log(`${tool}:`, result.isError ? "(error)" : "", result.content[0]?.text);
await client.close();
