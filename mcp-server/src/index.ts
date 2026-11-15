#!/usr/bin/env node
// mcflow-server: MCP tools for a local Paper test server, a real Minecraft client and test bots.

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { z } from "zod";
import { BotManager, inSpawnProtection, toMineflayerAngles } from "./bots.js";
import { attach, loadClientState, screenshotPath, waitFor, type BridgeClient, type ClientStatus } from "./client.js";
import { buildPlugin } from "./deploy.js";
import { readLog } from "./logs.js";
import { buildPack } from "./pack.js";
import { PackServer } from "./packServer.js";
import { readProperties, updateProperties } from "./properties.js";
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

type Content = { type: "text"; text: string } | { type: "image"; data: string; mimeType: string };
type ToolResult = { content: Content[]; isError?: boolean };

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

// ---------------------------------------------------------------------------------------------------------
// Real client (mcflow's Fabric mod). The user starts Minecraft from their own launcher, signed in.

/** Run `fn` against the running game, closing the bridge connection afterwards. */
async function withClient<T>(fn: (bridge: BridgeClient) => Promise<T>, waitMs = 0): Promise<T> {
  const { ws } = context();
  const bridge = await attach(loadClientState(ws), waitMs);
  try {
    return await fn(bridge);
  } finally {
    bridge.close();
  }
}

function versionNote(status: ClientStatus): string | undefined {
  const { ws } = context();
  return status.minecraft === ws.paperVersion
    ? undefined
    : `The client runs Minecraft ${status.minecraft} but the project targets ${ws.paperVersion}; ` +
        "screenshots may not match what players on the target version see.";
}

mcp.registerTool(
  "client_launch",
  {
    title: "Attach to the Minecraft client",
    description:
      "Wait for Minecraft (started by the user from their launcher with mcflow's Fabric mod, signed in) and attach " +
      "to it. If it isn't running, tell the user to start the Fabric installation for the project's version; this " +
      "tool waits up to waitSeconds for it.",
    inputSchema: { waitSeconds: z.number().int().min(0).max(600).default(180) },
  },
  ({ waitSeconds }) =>
    guard(() =>
      withClient(async (bridge) => {
        const status = await bridge.call<ClientStatus>("status");
        return ok({ ...status, note: versionNote(status) });
      }, waitSeconds * 1000),
    ),
);

mcp.registerTool(
  "client_join",
  {
    title: "Join the test server",
    description:
      "Connect the client to the local test server, accept its resource pack, and wait until the player is in " +
      "the world with no screen open. Sets the window size first so every screenshot has the same size. " +
      "The server must be running.",
    inputSchema: {
      timeoutSeconds: z.number().int().min(10).max(600).default(120),
      windowWidth: z.number().int().min(320).max(7680).default(1280),
      windowHeight: z.number().int().min(240).max(4320).default(720),
    },
  },
  ({ timeoutSeconds, windowWidth, windowHeight }) =>
    guard(() =>
      withClient(async (bridge) => {
        const s = context().local();
        await bridge.call("window_size", { width: windowWidth, height: windowHeight });
        await bridge.call("connect", { address: `127.0.0.1:${s.serverPort}` });
        const status = await waitFor(
          bridge,
          // A pause menu (the window lost focus) counts as joined: the mod closes it before the next command.
          (st) => st.inWorld && (!st.screen || st.screen === "PauseScreen"),
          timeoutSeconds * 1000,
          "the client to join and load the resource pack",
        );
        return ok({ ...status, note: versionNote(status) });
      }),
    ),
);

mcp.registerTool(
  "client_run",
  {
    title: "Run a command as the player",
    description:
      "Send a command (starting with /) or a chat message from the real client, then return what the server " +
      "logged in the next moment. Take a screenshot to see the result on screen.",
    inputSchema: {
      command: z.string().min(1),
      waitMs: z.number().int().min(0).max(10_000).default(1000).describe("How long to collect server log output"),
    },
  },
  ({ command, waitMs }) =>
    guard(() =>
      withClient(async (bridge) => {
        const { ws } = context();
        const logPath = join(ws.serverDir, "logs", "latest.log");
        const before = readLog(logPath).nextLine;
        if (command.startsWith("/")) await bridge.call("command", { command });
        else await bridge.call("chat", { message: command });
        await new Promise((r) => setTimeout(r, waitMs));
        const after = readLog(logPath, before);
        return ok({
          sent: command,
          serverLog: after.entries.map((e) => e.text),
          problems: summariseProblems(after.problems),
        });
      }),
    ),
);

mcp.registerTool(
  "client_screenshot",
  {
    title: "Screenshot the client",
    description:
      "Save what the real client shows (resource-pack models, fonts, GUIs, shaders) to " +
      "server/screenshots/<task>/<label>.png and return the image.",
    inputSchema: {
      label: z.string().min(1).describe("What this shows, e.g. 'shop-gui-open'"),
      task: z.string().min(1).describe("The task this belongs to, e.g. 'custom-sword'"),
    },
  },
  ({ label, task }) =>
    guard(() =>
      withClient(async (bridge) => {
        const path = screenshotPath(context().ws, task, label);
        const shot = await bridge.call<{ path: string; width: number; height: number }>("screenshot", { path });
        return {
          content: [
            { type: "text", text: JSON.stringify(shot) },
            { type: "image", data: readFileSync(path).toString("base64"), mimeType: "image/png" },
          ],
        };
      }),
    ),
);

mcp.registerTool(
  "client_open_inventory",
  {
    title: "Open the player's inventory",
    description: "Open the inventory screen on the real client and return its slots (item ids, counts, names).",
  },
  () => guard(() => withClient(async (bridge) => ok(await bridge.call("open_inventory")))),
);

mcp.registerTool(
  "client_screen",
  {
    title: "Describe the open screen",
    description:
      "The screen the client is showing: its type, title, buttons and other widgets with positions, and for " +
      "container GUIs every non-empty slot. Use it to check a plugin GUI's contents.",
  },
  () => guard(() => withClient(async (bridge) => ok(await bridge.call("screen")))),
);

mcp.registerTool(
  "client_close_screen",
  { title: "Close the open screen", description: "Close the inventory or GUI the client has open." },
  () => guard(() => withClient(async (bridge) => ok((await bridge.call("close_screen")) ?? "closed"))),
);

mcp.registerTool(
  "client_quit",
  { title: "Quit Minecraft", description: "Close the Minecraft client." },
  () =>
    guard(() =>
      withClient(async (bridge) => {
        await bridge.call("quit").catch(() => undefined); // the game closes the connection as it exits
        return ok("Minecraft is shutting down.");
      }),
    ),
);

// ---- Bots (mineflayer) ----------------------------------------------------------------------------------

const bots = new BotManager(() => {
  const { ws, local } = context();
  return { host: "127.0.0.1", port: local().serverPort, serverVersion: ws.paperVersion };
});
const botName = z.string().min(1).describe("The bot's username");
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

mcp.registerTool(
  "bot_join",
  {
    title: "Join a test bot",
    description:
      "Connect a mineflayer bot (offline mode) to the running test server and wait until it spawns. It accepts the " +
      "server's resource pack. If mineflayer doesn't support the server's version yet, the bot joins as the newest " +
      "version it supports and ViaBackwards on the server translates.",
    inputSchema: { name: botName, timeoutSeconds: z.number().int().min(5).max(300).default(60) },
  },
  ({ name, timeoutSeconds }) => guard(async () => ok(await bots.join(name, timeoutSeconds * 1000))),
);

mcp.registerTool(
  "bot_leave",
  {
    title: "Disconnect test bots",
    description: "Disconnect one bot, or every bot when name is omitted.",
    inputSchema: { name: botName.optional() },
  },
  ({ name }) =>
    guard(async () => {
      if (name) {
        bots.leave(name);
        return ok({ left: [name] });
      }
      return ok({ left: bots.leaveAll() });
    }),
);

mcp.registerTool(
  "bot_chat",
  {
    title: "Send chat or a command from a bot",
    description:
      "Send a chat message, or a command starting with /, as the bot. Returns the chat lines the bot received and " +
      "what the server logged during the next waitMs.",
    inputSchema: {
      name: botName,
      message: z.string().min(1).max(256),
      waitMs: z.number().int().min(0).max(10_000).default(1000),
    },
  },
  ({ name, message, waitMs }) =>
    guard(async () => {
      const m = bots.get(name);
      const logPath = join(context().ws.serverDir, "logs", "latest.log");
      const before = readLog(logPath).nextLine;
      const seen = m.messages.length;
      m.bot.chat(message);
      await sleep(waitMs);
      const after = readLog(logPath, before);
      return ok({
        sent: message,
        received: m.messages.slice(Math.min(seen, m.messages.length)),
        serverLog: after.entries.map((e) => e.text),
        problems: summariseProblems(after.problems),
      });
    }),
);

const CONTROLS = ["forward", "back", "left", "right", "jump", "sprint", "sneak"] as const;

mcp.registerTool(
  "bot_move",
  {
    title: "Move a bot",
    description:
      "Hold movement keys (forward, back, left, right, jump, sprint, sneak) for durationMs, then release them. " +
      "Returns the position before and after, as the bot and the server see it.",
    inputSchema: {
      name: botName,
      controls: z.array(z.enum(CONTROLS)).min(1),
      durationMs: z.number().int().min(50).max(30_000).default(1000),
    },
  },
  ({ name, controls, durationMs }) =>
    guard(async () => {
      const m = bots.get(name);
      const from = bots.status(name).position;
      for (const c of controls) m.bot.setControlState(c, true);
      await sleep(durationMs);
      for (const c of controls) m.bot.setControlState(c, false);
      await sleep(300); // let the last movement packets settle
      const to = bots.status(name).position;
      const moved = from && to ? Math.hypot(to.x - from.x, to.y - from.y, to.z - from.z) : undefined;
      return ok({ from, to, moved: moved === undefined ? undefined : Math.round(moved * 100) / 100, status: bots.status(name) });
    }),
);

mcp.registerTool(
  "bot_look",
  {
    title: "Turn a bot",
    description:
      "Turn the bot's head. Give yaw and pitch in Minecraft's convention (degrees; yaw 0 = south, 90 = west; " +
      "pitch -90 = up, 90 = down), or a block position to look at.",
    inputSchema: {
      name: botName,
      yaw: z.number().optional(),
      pitch: z.number().min(-90).max(90).optional(),
      at: z.object({ x: z.number(), y: z.number(), z: z.number() }).optional(),
    },
  },
  ({ name, yaw, pitch, at }) =>
    guard(async () => {
      const m = bots.get(name);
      if (at) {
        const { Vec3 } = await import("vec3");
        await m.bot.lookAt(new Vec3(at.x, at.y, at.z), true);
      } else {
        const now = bots.status(name);
        const a = toMineflayerAngles(yaw ?? now.yaw ?? 0, pitch ?? now.pitch ?? 0);
        await m.bot.look(a.yaw, a.pitch, true);
      }
      await sleep(150); // the look goes out with the next physics tick
      return ok(bots.status(name));
    }),
);

mcp.registerTool(
  "bot_use_item",
  {
    title: "Use an item or click with a bot",
    description:
      "Choose a hotbar slot (0-8) if given, then act: 'use' right-clicks with the held item (holding it for " +
      "durationMs), 'activate_block' right-clicks the block the bot is looking at, 'attack' left-clicks (swings, and " +
      "hits the entity in front of the bot if there is one).",
    inputSchema: {
      name: botName,
      action: z.enum(["use", "activate_block", "attack"]).default("use"),
      hotbarSlot: z.number().int().min(0).max(8).optional(),
      offhand: z.boolean().default(false),
      durationMs: z.number().int().min(0).max(10_000).default(0),
    },
  },
  ({ name, action, hotbarSlot, offhand, durationMs }) =>
    guard(async () => {
      const m = bots.get(name);
      const { bot } = m;
      if (hotbarSlot !== undefined) bot.setQuickBarSlot(hotbarSlot);
      let target: string | undefined;
      if (action === "use") {
        bot.activateItem(offhand);
        await sleep(durationMs);
        bot.deactivateItem();
      } else if (action === "activate_block") {
        const block = bot.blockAtCursor(5);
        if (!block) throw new McflowError(`Bot "${name}" isn't looking at a block within 5 blocks.`);
        // Containers answer with a window a moment later; wait for it rather than a fixed delay.
        const opened = new Promise<boolean>((resolve) => {
          const t = setTimeout(() => resolve(false), 2000);
          bot.once("windowOpen", () => {
            clearTimeout(t);
            resolve(true);
          });
        });
        await bot.activateBlock(block);
        target = `${block.name} at ${block.position}`;
        if (/chest|barrel|shulker_box|furnace|hopper|dispenser|dropper|crafter/.test(block.name)) {
          if (!(await opened)) {
            const radius = Number(readProperties(join(context().ws.serverDir, "server.properties"))["spawn-protection"] ?? 16);
            const hint = inSpawnProtection(block.position, bot.spawnPoint, radius)
              ? ` It's inside spawn protection (${radius} blocks around the world spawn), where only operators can use blocks: ` +
                `op the bot, or test further from spawn.`
              : "";
            throw new McflowError(`Bot "${name}" clicked the ${block.name}, but no window opened within 2 s.${hint}`);
          }
        }
      } else {
        const entity = bot.entityAtCursor?.(3.5);
        if (entity) {
          bot.attack(entity);
          target = `${entity.name ?? entity.type} #${entity.id}`;
        } else {
          bot.swingArm("right");
        }
      }
      await sleep(300);
      return ok({ action, target, held: bot.heldItem?.name ?? null, status: bots.status(name) });
    }),
);

function describeSlots(slots: ReadonlyArray<{ slot: number; name: string; count: number; customName?: string | null } | null>) {
  return slots
    .filter((s): s is NonNullable<typeof s> => s !== null)
    .map((s) => ({ slot: s.slot, item: s.name, count: s.count, ...(s.customName ? { customName: s.customName } : {}) }));
}

mcp.registerTool(
  "bot_inventory",
  {
    title: "Read a bot's inventory",
    description:
      "List the items in the bot's inventory (slot numbers as in its inventory window: 36-44 is the hotbar), " +
      "and, if a container or GUI window is open, that window's title and items.",
    inputSchema: { name: botName },
  },
  ({ name }) =>
    guard(async () => {
      const { bot } = bots.get(name);
      const window = bot.currentWindow;
      return ok({
        heldSlot: bot.quickBarSlot,
        inventory: describeSlots(bot.inventory.slots),
        window: window
          ? { id: window.id, title: bots.status(name).window?.title, type: window.type, items: describeSlots(window.slots) }
          : null,
      });
    }),
);

mcp.registerTool(
  "bot_click_window_slot",
  {
    title: "Click a slot in a bot's open window",
    description:
      "Click a slot in the open window (a chest or plugin GUI), or in the inventory when none is open. button 0 = " +
      "left, 1 = right; mode 0 = normal click, 1 = shift-click, 2 = number key, 4 = drop. Returns the window afterwards.",
    inputSchema: {
      name: botName,
      slot: z.number().int().min(-999),
      button: z.number().int().min(0).max(40).default(0),
      mode: z.number().int().min(0).max(6).default(0),
    },
  },
  ({ name, slot, button, mode }) =>
    guard(async () => {
      const { bot } = bots.get(name);
      const window = bot.currentWindow ?? bot.inventory;
      if (slot >= window.slots.length) throw new McflowError(`Slot ${slot} is outside the window (it has ${window.slots.length} slots).`);
      await bot.clickWindow(slot, button, mode);
      await sleep(300);
      const after = bot.currentWindow;
      return ok({
        clicked: { slot, button, mode },
        window: after ? { id: after.id, title: bots.status(name).window?.title, items: describeSlots(after.slots) } : null,
        cursor: (after ?? bot.inventory).selectedItem?.name ?? null,
      });
    }),
);

mcp.registerTool(
  "bot_status",
  {
    title: "Report test bots",
    description: "Position, view, health, food, game mode, open window and last kick or error for one bot, or every bot.",
    inputSchema: { name: botName.optional() },
  },
  ({ name }) => guard(async () => ok(name ? bots.status(name) : bots.names().map((n) => bots.status(n)))),
);

async function shutdown() {
  bots.leaveAll();
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
