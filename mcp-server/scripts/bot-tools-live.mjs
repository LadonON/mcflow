// Task 4.2 live test: every bot tool through mcflow-server against a running workspace (30 checks).
import { pathToFileURL } from "node:url";
import { join } from "node:path";

const [repo, workspace] = process.argv.slice(2);
const sdk = join(repo, "mcp-server", "node_modules", "@modelcontextprotocol", "sdk", "dist", "esm");
const { Client } = await import(pathToFileURL(join(sdk, "client", "index.js")).href);
const { StdioClientTransport } = await import(pathToFileURL(join(sdk, "client", "stdio.js")).href);
const mcp = new Client({ name: "mcflow-bot-tools-live", version: "0" });
await mcp.connect(new StdioClientTransport({ command: process.execPath, args: [join(repo, "mcp-server", "dist", "index.js")], cwd: workspace, stderr: "inherit" }));

async function call(name, args = {}) {
  const r = await mcp.callTool({ name, arguments: args }, undefined, { timeout: 600_000 });
  const text = r.content.map((c) => c.text ?? "").join("\n");
  let json;
  try { json = JSON.parse(text); } catch { json = undefined; }
  return { error: !!r.isError, text, json };
}
const cmd = (c) => call("server_command", { cmd: c });
const results = [];
const check = (name, ok, detail = "") => { results.push({ name, ok }); console.log(`CHECK ${ok ? "PASS" : "FAIL"} ${name}: ${String(detail).slice(0, 260)}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  await call("resourcepack_build_and_serve", { pack: "menu", restart: false });
  await call("server_start");
  const tools = (await mcp.listTools()).tools.map((t) => t.name).filter((n) => n.startsWith("bot_"));
  check("nine bot tools registered", tools.length === 9, tools.join(", "));

  const j = await call("bot_join", { name: "Alpha" });
  check("bot_join", !j.error && j.json?.status?.online, j.error ? j.text : `${j.json.joinMs} ms, ${j.json.status.version}, translated=${j.json.translated}`);
  const dup = await call("bot_join", { name: "Alpha" });
  check("bot_join refuses a duplicate", dup.error && /already connected/.test(dup.text), dup.text);
  const bad = await call("bot_join", { name: "no spaces" });
  check("bot_join rejects invalid names", bad.error, bad.text);
  const j2 = await call("bot_join", { name: "Bravo" });
  check("second bot joins", !j2.error, j2.error ? j2.text : `${j2.json.joinMs} ms`);

  const chat = await call("bot_chat", { name: "Alpha", message: "hello from Alpha" });
  check("bot_chat: message echoed to the bot", chat.json?.received?.some((l) => l.includes("hello from Alpha")), JSON.stringify(chat.json?.received));
  check("bot_chat: server logged it", chat.json?.serverLog?.some((l) => l.includes("hello from Alpha")), JSON.stringify(chat.json?.serverLog));
  const menu = await call("bot_chat", { name: "Alpha", message: "/menu" });
  check("bot_chat runs commands (/menu)", menu.json?.serverLog?.some((l) => l.includes("issued server command: /menu")), JSON.stringify(menu.json?.serverLog));
  check("…and /menu put Alpha in spectator", (await call("bot_status", { name: "Alpha" })).json?.gameMode === "spectator");
  const close = await call("bot_move", { name: "Alpha", controls: ["sneak"], durationMs: 400 });
  check("bot_move sneak closes the menu", close.json?.status?.gameMode === "survival", close.json?.status?.gameMode);

  // Clear the lane first: earlier runs leave chests on the platform, and the bot walks into them.
  await cmd("fill -200 200 -200 -198 203 -170 minecraft:air");
  await cmd("fill -200 199 -200 -198 199 -170 minecraft:stone");
  await cmd("tp Alpha -199 200 -199 0 0");
  await sleep(1200);
  const look = await call("bot_look", { name: "Alpha", yaw: 0, pitch: 0 });
  check("bot_look sets yaw/pitch", Math.abs(look.json?.yaw) < 1 && Math.abs(look.json?.pitch) < 1, `${look.json?.yaw}, ${look.json?.pitch}`);
  const srvRot = (await cmd("data get entity Alpha Rotation")).text;
  check("…and the server sees it", /\[0\.0f, 0\.0f\]|\[-?0\.\d+f, -?0\.\d+f\]/.test(srvRot), srvRot.trim());
  const walk = await call("bot_move", { name: "Alpha", controls: ["forward"], durationMs: 2000 });
  check("bot_move forward walks south", walk.json?.moved > 4 && walk.json.to.z > walk.json.from.z, `moved ${walk.json?.moved}, z ${walk.json?.from?.z} -> ${walk.json?.to?.z}`);
  const srvPos = (await cmd("data get entity Alpha Pos")).text;
  const sz = parseFloat(srvPos.match(/, (-?[\d.]+)d\]/)?.[1]);
  check("…and the server agrees", Math.abs(sz - walk.json?.to?.z) < 0.2, `server z ${sz}`);
  const lookAt = await call("bot_look", { name: "Alpha", at: { x: -199, y: 199, z: walk.json.to.z } });
  check("bot_look at a block", lookAt.json?.pitch > 45, `pitch ${lookAt.json?.pitch}`);

  await cmd("clear Alpha");
  await cmd("give Alpha minecraft:bread 5");
  await cmd("item replace entity Alpha hotbar.2 with minecraft:diamond_sword");
  await sleep(500);
  const inv = await call("bot_inventory", { name: "Alpha" });
  const items = inv.json?.inventory?.map((i) => `${i.item}x${i.count}@${i.slot}`) ?? [];
  check("bot_inventory lists items", items.includes("breadx5@36") && items.includes("diamond_swordx1@38"), items.join(" "));
  const use = await call("bot_use_item", { name: "Alpha", action: "use", hotbarSlot: 2 });
  check("bot_use_item switches slot", use.json?.held === "diamond_sword", use.json?.held);
  const atk = await call("bot_use_item", { name: "Alpha", action: "attack" });
  check("bot_use_item attack", !atk.error, atk.text.slice(0, 150));
  await cmd("effect give Alpha minecraft:hunger 3 255");
  await sleep(3500);
  const before = (await call("bot_status", { name: "Alpha" })).json?.food;
  const eat = await call("bot_use_item", { name: "Alpha", action: "use", hotbarSlot: 0, durationMs: 2200 });
  const after = (await call("bot_status", { name: "Alpha" })).json?.food;
  check("bot_use_item use eats bread", after > before, `food ${before} -> ${after}`);

  // Inside spawn protection (16 blocks around the world spawn), a non-operator bot can't open a chest.
  const z = Math.round(walk.json.to.z) + 2;
  await cmd(`setblock -199 200 ${z} minecraft:chest`);
  await call("bot_look", { name: "Alpha", at: { x: -198.5, y: 200.5, z: z + 0.5 } });
  const protectedClick = await call("bot_use_item", { name: "Alpha", action: "activate_block" });
  check("activate_block explains spawn protection", protectedClick.error && /spawn protection/.test(protectedClick.text), protectedClick.text);

  // Outside it, on a second platform 40 blocks west, a chest with an item in it.
  await cmd("fill -240 200 -200 -238 203 -190 minecraft:air");
  await cmd("fill -240 199 -200 -238 199 -190 minecraft:stone");
  await cmd("tp Alpha -239 200 -199 0 0");
  await sleep(1500);
  await cmd("setblock -239 200 -196 minecraft:chest");
  await cmd("item replace block -239 200 -196 container.4 with minecraft:emerald 7");
  await sleep(300);
  await call("bot_look", { name: "Alpha", at: { x: -238.5, y: 200.5, z: -195.5 } });
  const open = await call("bot_use_item", { name: "Alpha", action: "activate_block" });
  check("bot_use_item activate_block opens a chest", /chest/.test(open.json?.target ?? "") && open.json?.status?.window, open.text.slice(0, 200));
  const winInv = await call("bot_inventory", { name: "Alpha" });
  check("bot_inventory shows the open window", winInv.json?.window?.items?.some((i) => i.item === "emerald" && i.slot === 4), JSON.stringify(winInv.json?.window).slice(0, 200));
  const take = await call("bot_click_window_slot", { name: "Alpha", slot: 4, mode: 1 });
  const chestSlot4 = take.json?.window?.items?.find((i) => i.slot === 4);
  const movedTo = take.json?.window?.items?.find((i) => i.item === "emerald");
  check("bot_click_window_slot shift-clicks the emerald out", !take.error && !chestSlot4 && movedTo?.slot >= 27, `chest slot 4 now ${chestSlot4?.item ?? "empty"}; emerald in window slot ${movedTo?.slot}`);
  const out = await call("bot_click_window_slot", { name: "Alpha", slot: 999 });
  check("bot_click_window_slot rejects a slot outside the window", out.error, out.text);
  const chestNow = (await cmd("data get block -239 200 -196 Items")).text;
  check("…and the server's chest is empty", !/emerald/.test(chestNow), chestNow.trim());

  const all = await call("bot_status");
  check("bot_status lists every bot", Array.isArray(all.json) && all.json.length === 2, all.json?.map((b) => `${b.name}:${b.online}`).join(" "));

  await cmd("kick Bravo Testing kicks");
  await sleep(800);
  const kicked = await call("bot_status", { name: "Bravo" });
  check("bot_status reports a kick", kicked.json?.online === false && kicked.json?.lastKick === "Testing kicks", JSON.stringify(kicked.json));
  const useKicked = await call("bot_chat", { name: "Bravo", message: "hi" });
  check("tools refuse a disconnected bot", useKicked.error && /isn't connected/.test(useKicked.text), useKicked.text);

  const left = await call("bot_leave");
  check("bot_leave with no name disconnects all", left.json?.left?.length === 2, JSON.stringify(left.json));
  await sleep(1000);
  const logs = JSON.parse((await call("server_logs", { filter: "Exception|ERROR|moved too quickly|moved wrongly", maxEntries: 50 })).text);
  check("no exceptions or errors in the server log", logs.problems.filter((p) => !/resource pack prompt/.test(p.text)).length === 0,
    logs.problems.map((p) => p.text.slice(0, 120)).join(" | ") || "none");
  console.log("MOVEMENT WARNINGS: " + (logs.entries.filter((e) => /moved/.test(e)).join(" | ") || "none"));
} finally {
  await call("server_stop");
  await mcp.close();
  const failed = results.filter((r) => !r.ok).map((r) => r.name);
  console.log(`SUMMARY ${results.length - failed.length}/${results.length} passed${failed.length ? "; failed: " + failed.join(", ") : ""}`);
  process.exit(0);
}
