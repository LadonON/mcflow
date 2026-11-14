#!/usr/bin/env node
// mcflow-server: MCP tools for a local Paper test server (and, in later stages, bots and a real client).

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { join } from "node:path";
import { z } from "zod";
import { buildPlugin } from "./deploy.js";
import { readLog } from "./logs.js";
import { buildPack } from "./pack.js";
import { PackServer } from "./packServer.js";
import { updateProperties } from "./properties.js";
import { runCommand } from "./rcon.js";
import { ServerController } from "./serverProcess.js";
import { loadLocal, loadWorkspace, McflowError, type Workspace } from "./workspace.js";

const VERSION = "0.1.0-dev.0";

// Loaded lazily: outside a workspace the server still starts, and each tool explains what's missing.
let cached: { ws: Workspace; server: ServerController } | undefined;
function context() {
  if (!cached) {
    const ws = loadWorkspace();
    cached = { ws, server: new ServerController(ws, () => loadLocal(ws)) };
  }
  return { ...cached, local: () => loadLocal(cached!.ws) };
}
let packServer: PackServer | undefined;

type ToolResult = { content: { type: "text"; text: string }[]; isError?: boolean };

function ok(value: unknown): ToolResult {
  return { content: [{ type: "text", text: typeof value === "string" ? value : JSON.stringify(value, null, 2) }] };
}

/** Turn expected failures into readable tool errors instead of protocol errors. */
async function guard(fn: () => Promise<ToolResult>): Promise<ToolResult> {
  try {
    return await fn();
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return { content: [{ type: "text", text: message }], isError: true };
  }
}

function summariseProblems(problems: ReturnType<typeof readLog>["problems"]) {
  return problems.slice(0, 20).map((p) => ({ line: p.line, level: p.level, text: p.text.slice(0, 4000) }));
}

const mcp = new McpServer({ name: "mcflow-server", version: VERSION });

mcp.registerTool(
  "server_start",
  {
    title: "Start the test server",
    description:
      "Start the local Paper test server and wait until it has finished loading. Reports startup time and any exceptions logged during startup.",
  },
  () =>
    guard(async () => {
      const { server } = context();
      const r = await server.start();
      return ok({ ...r, problems: summariseProblems(server.startupProblems()) });
    }),
);

mcp.registerTool(
  "server_stop",
  { title: "Stop the test server", description: "Stop the test server cleanly (RCON `stop`), forcing it only after 60 s." },
  () => guard(async () => ok(await context().server.stop())),
);

mcp.registerTool(
  "server_restart",
  {
    title: "Restart the test server",
    description: "Stop and start the test server. Use this instead of /reload, which mcflow never uses.",
  },
  () =>
    guard(async () => {
      const { server } = context();
      const r = await server.restart();
      return ok({ ...r, problems: summariseProblems(server.startupProblems()) });
    }),
);

mcp.registerTool(
  "server_status",
  { title: "Test server status", description: "Whether the server is running, whether RCON answers, and who is online." },
  () => guard(async () => ok(await context().server.status())),
);

mcp.registerTool(
  "server_command",
  {
    title: "Run a server command",
    description: "Run a console command through RCON and return its output, e.g. `list` or `give Steve diamond`.",
    inputSchema: { cmd: z.string().min(1).describe("The command, with or without a leading slash") },
  },
  ({ cmd }) =>
    guard(async () => {
      if (/^\/?(reload|rl)(\s|$)/i.test(cmd)) {
        throw new McflowError("mcflow never uses /reload. Use plugin_deploy or server_restart instead.");
      }
      const s = context().local();
      return ok((await runCommand(s.rconPort, s.rconPassword, cmd)) || "(no output)");
    }),
);

mcp.registerTool(
  "server_logs",
  {
    title: "Read the server log",
    description:
      "Read server/logs/latest.log. Pass back `nextLine` as `sinceLine` to get only new lines. Exceptions, stack traces and ERROR lines are listed under `problems`.",
    inputSchema: {
      sinceLine: z.number().int().min(1).optional().describe("Line to start from (from a previous call's nextLine)"),
      filter: z.string().optional().describe("Case-insensitive regex; only matching entries are returned"),
      maxEntries: z.number().int().min(1).max(500).default(100),
    },
  },
  ({ sinceLine, filter, maxEntries }) =>
    guard(async () => {
      const { ws } = context();
      const log = readLog(join(ws.serverDir, "logs", "latest.log"), sinceLine ?? 1, filter);
      return ok({
        nextLine: log.nextLine,
        problems: summariseProblems(log.problems),
        entries: log.entries.slice(-maxEntries).map((e) => e.text),
        truncated: log.entries.length > maxEntries,
      });
    }),
);

mcp.registerTool(
  "plugin_deploy",
  {
    title: "Build and deploy a plugin",
    description:
      "Build plugins/<project> with Gradle, copy the jar to server/plugins/, and restart the server if it's running (never /reload). Returns build time and any exceptions logged on restart.",
    inputSchema: { project: z.string().min(1).describe("Folder name under plugins/") },
  },
  ({ project }) =>
    guard(async () => {
      const { ws, server, local } = context();
      const build = await buildPlugin(ws, project, local().java);
      const wasRunning = server.livePid() !== undefined;
      const restart = wasRunning ? await server.restart() : undefined;
      return ok({
        built: build.jar,
        deployedAs: build.deployedAs,
        buildSeconds: build.seconds,
        restarted: wasRunning,
        restartSeconds: restart?.seconds,
        problems: wasRunning ? summariseProblems(server.startupProblems()) : [],
      });
    }),
);

mcp.registerTool(
  "resourcepack_build_and_serve",
  {
    title: "Build and serve a resource pack",
    description:
      "Validate and zip resourcepacks/<pack>, compute its SHA-1, serve it on the local pack server, and point server.properties at it (restarting the server if it's running so players get the new pack).",
    inputSchema: {
      pack: z.string().min(1).describe("Folder name under resourcepacks/"),
      restart: z.boolean().default(true).describe("Restart a running server so the new pack takes effect"),
    },
  },
  ({ pack, restart }) =>
    guard(async () => {
      const { ws, server, local } = context();
      const built = buildPack(ws, pack);
      const s = local();
      packServer ??= new PackServer(join(ws.stateDir, "packs"), s.packPort);
      await packServer.ensureRunning();
      const url = packServer.url(built.name, built.sha1);
      updateProperties(join(ws.serverDir, "server.properties"), {
        "resource-pack": url,
        "resource-pack-sha1": built.sha1,
        "require-resource-pack": "true",
      });
      const running = server.livePid() !== undefined;
      const restarted = running && restart ? await server.restart() : undefined;
      return ok({
        url,
        sha1: built.sha1,
        bytes: built.bytes,
        files: built.files,
        packFormat: built.packFormat,
        expectedPackFormat: built.expectedPackFormat ?? "unknown until the server has started once",
        issues: built.issues,
        valid: built.issues.length === 0,
        restarted: Boolean(restarted),
        note:
          running && !restart
            ? "server.properties is updated, but the running server only picks up the new pack after a restart."
            : undefined,
      });
    }),
);

async function shutdown() {
  packServer?.close();
  try {
    await cached?.server.stop(30_000);
  } finally {
    process.exit(0);
  }
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
process.stdin.on("close", shutdown);

// If packs were built in an earlier session, keep serving them so a running server's URL stays valid.
try {
  const { ws, local } = context();
  const s = local();
  packServer = new PackServer(join(ws.stateDir, "packs"), s.packPort);
  await packServer.ensureRunning();
} catch {
  packServer = undefined; // not set up yet, or the port is busy; resourcepack_build_and_serve retries
}

await mcp.connect(new StdioServerTransport());
