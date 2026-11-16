import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { findLeaks, judgePerformance, parseHeapUsedMb, parseHistogram, parseMspt, scanAsyncLog, scanThreadSafety, summariseMspt } from "../src/gates.js";
import { checkPack, pngSize } from "../src/packcheck.js";

describe("parseMspt", () => {
  it("reads Paper 26.3's mspt reply", () => {
    const out = "Server tick times (avg/min/max) from last 5s, 10s, 1m:\n◴ 1.0/0.6/2.0, 1.4/0.4/50.8, 1.4/0.4/50.8";
    expect(parseMspt(out)).toEqual({ s5: { avg: 1, min: 0.6, max: 2 }, s10: { avg: 1.4, min: 0.4, max: 50.8 }, m1: { avg: 1.4, min: 0.4, max: 50.8 } });
  });
  it("strips colour codes and rejects other output", () => {
    expect(parseMspt("§6Server tick times (avg/min/max) from last 5s, 10s, 1m:\n§a2.0/1.0/3.0, §a2.0/1.0/3.0, §a2.0/1.0/3.0")?.s5.avg).toBe(2);
    expect(parseMspt("Unknown command")).toBeUndefined();
  });
});

describe("performance verdict", () => {
  const w = (avg: number, max = avg * 2) => ({ avg, min: avg / 2, max });
  const limits = { maxAvgMs: 50, maxRegressionPct: 25, minRegressionMs: 1 };

  it("summarises 5-second windows", () => {
    expect(summariseMspt([w(2), w(3), w(4), w(40, 120)])).toEqual({ samples: 4, medianAvg: 3, p95Avg: 40, worstTick: 120 });
  });

  it("fails over the absolute limit even without a baseline", () => {
    const r = judgePerformance(summariseMspt([w(30), w(55), w(60)]), undefined, limits);
    expect(r.pass).toBe(false);
    expect(r.failures[0]).toMatch(/over the 50 ms limit/);
  });

  it("fails a real regression over the baseline", () => {
    const base = summariseMspt([w(4), w(4), w(4)]);
    const r = judgePerformance(summariseMspt([w(6), w(6), w(6)]), base, limits);
    expect(r.pass).toBe(false);
    expect(r.regression).toEqual({ ms: 2, pct: 50 });
  });

  it("ignores large percentages of tiny times (idle-server noise)", () => {
    const base = summariseMspt([w(0.8), w(0.8), w(0.8)]);
    const r = judgePerformance(summariseMspt([w(1.4), w(1.4), w(1.4)]), base, limits);
    expect(r.pass).toBe(true); // +75%, but only 0.6 ms
  });
});

const HIST = (menu: number, sessions: number, listeners: number) => ` num     #instances         #bytes  class name (module)
-------------------------------------------------------
   1:        292295       36694640  [Ljava.lang.Object; (java.base@25.0.2)
1876:            ${listeners}            512  org.bukkit.plugin.RegisteredListener
2629:             4            224  org.bukkit.craftbukkit.scheduler.CraftTask
4471:             ${menu}             72  dev.mcflow.menu.MenuPlugin
4500:             ${sessions}             40  dev.mcflow.menu.MenuSession
Total       1000000      100000000
`;

describe("memory gate", () => {
  it("parses a jcmd class histogram", () => {
    const h = parseHistogram(HIST(1, 0, 16));
    expect(h.get("dev.mcflow.menu.MenuPlugin")).toBe(1);
    expect(h.get("org.bukkit.plugin.RegisteredListener")).toBe(16);
    expect(h.get("[Ljava.lang.Object;")).toBe(292295);
  });

  it("flags plugin classes and listeners that grow at both steps", () => {
    const leaks = findLeaks(parseHistogram(HIST(1, 0, 16)), parseHistogram(HIST(1, 15, 19)), parseHistogram(HIST(1, 30, 22)), "dev.mcflow.menu");
    expect(leaks.map((l) => l.className)).toEqual(["dev.mcflow.menu.MenuSession", "org.bukkit.plugin.RegisteredListener"]);
    expect(leaks[0]!.counts).toEqual([0, 15, 30]);
  });

  it("ignores growth at one step only, and other packages", () => {
    expect(findLeaks(parseHistogram(HIST(1, 0, 16)), parseHistogram(HIST(1, 3, 16)), parseHistogram(HIST(1, 3, 16)), "dev.mcflow.menu")).toEqual([]);
    expect(findLeaks(parseHistogram(HIST(1, 0, 16)), parseHistogram(HIST(1, 5, 16)), parseHistogram(HIST(1, 9, 16)), "com.other")).toEqual([]);
  });

  it("reads used heap from GC.heap_info", () => {
    expect(parseHeapUsedMb(" garbage-first heap   total reserved 2097152K, committed 1048576K, used 285901K [0x0…")).toBe(279);
  });
});

describe("thread-safety scan", () => {
  const file = (text: string) => [{ path: "Plugin.java", text }];

  it("flags a main-thread call inside an async task", () => {
    const f = scanThreadSafety(file(`
      void go(Player p) {
        getServer().getScheduler().runTaskAsynchronously(this, () -> {
          String data = load();
          p.teleport(spawn);
        });
      }`));
    expect(f).toEqual([{ file: "Plugin.java", line: 5, call: "teleport", context: "runTaskAsynchronously" }]);
  });

  it("accepts the same call after hopping back with runTask", () => {
    expect(scanThreadSafety(file(`
      getServer().getScheduler().runTaskAsynchronously(this, () -> {
        String data = load();
        getServer().getScheduler().runTask(this, () -> p.teleport(spawn));
      });`))).toEqual([]);
  });

  it("flags Bukkit calls in a Netty handler", () => {
    const f = scanThreadSafety(file(`
      class Hook extends ChannelInboundHandlerAdapter {
        public void channelRead(ChannelHandlerContext ctx, Object msg) {
          player.setGameMode(GameMode.SURVIVAL);
        }
      }`));
    expect(f.map((x) => [x.call, x.context])).toEqual([["setGameMode", "channelRead"]]);
  });

  it("passes the menu plugin's pattern: the Netty handler only hands off", () => {
    expect(scanThreadSafety(file(`
      public void channelRead(ChannelHandlerContext ctx, Object msg) throws Exception {
        if (msg.getClass().getSimpleName().equals(PACKET)) {
          onClick.accept(player); // runs on the Netty thread; the callback hops to the main thread
          return;
        }
        super.channelRead(ctx, msg);
      }`))).toEqual([]);
  });

  it("ignores calls in comments", () => {
    expect(scanThreadSafety(file(`runTaskAsynchronously(this, () -> { /* p.teleport(x) */ // p.kick()
      log(); });`))).toEqual([]);
  });

  it("finds Paper's async catches in the log", () => {
    const lines = ["[12:00:00] [Craft Scheduler Thread - 3/WARN]: java.lang.IllegalStateException: Asynchronous entity teleport!", "[12:00:01] [Server thread/INFO]: Done"];
    expect(scanAsyncLog(lines)).toEqual([lines[0]]);
  });
});

function png(width: number, height: number): Buffer {
  const b = Buffer.alloc(33);
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]).copy(b, 0);
  b.writeUInt32BE(13, 8);
  b.write("IHDR", 12, "ascii");
  b.writeUInt32BE(width, 16);
  b.writeUInt32BE(height, 20);
  return b;
}

function pack(files: Record<string, string | Buffer>) {
  const dir = mkdtempSync(join(tmpdir(), "mcflow-pack-"));
  for (const [rel, content] of Object.entries(files)) {
    const p = join(dir, ...rel.split("/"));
    mkdirSync(join(p, ".."), { recursive: true });
    writeFileSync(p, content);
  }
  return dir;
}

describe("resource-pack reference check", () => {
  it("reads PNG sizes", () => {
    expect(pngSize(png(160, 168))).toEqual({ width: 160, height: 168 });
    expect(pngSize(Buffer.from("not a png"))).toBeUndefined();
  });

  it("passes a valid font, model and item definition", () => {
    const dir = pack({
      "assets/ui/font/menu.json": JSON.stringify({ providers: [
        { type: "bitmap", file: "ui:font/panel.png", height: 40, ascent: 11, chars: ["\ue000"] },
        { type: "space", advances: { "\uf000": 0.25 } },
        { type: "reference", id: "ui:other" },
      ] }),
      "assets/ui/font/other.json": JSON.stringify({ providers: [] }),
      "assets/ui/textures/font/panel.png": png(160, 160),
      "assets/ui/models/item/gem.json": JSON.stringify({ parent: "minecraft:item/generated", textures: { layer0: "ui:item/gem" } }),
      "assets/ui/textures/item/gem.png": png(16, 16),
      "assets/ui/items/gem.json": JSON.stringify({ model: { type: "minecraft:model", model: "ui:item/gem" } }),
    });
    const r = checkPack(dir, new Set(["assets/minecraft/models/item/generated.json"]));
    expect(r.issues).toEqual([]);
    expect(r.checked).toMatchObject({ fonts: 2, models: 1, itemDefinitions: 1 });
  });

  it("catches the Stage 3 bug: ascent above height", () => {
    const dir = pack({
      "assets/ui/font/name.json": JSON.stringify({ providers: [{ type: "bitmap", file: "minecraft:font/ascii.png", height: 2, ascent: 7, chars: ["ab"] }] }),
    });
    const r = checkPack(dir);
    expect(r.issues.map((i) => i.problem)).toEqual([expect.stringMatching(/ascent 7 is greater than height 2/)]);
    expect(r.unverifiedVanilla).toBe(1);
  });

  it("reports missing files, uneven chars rows and a texture that doesn't fit the grid", () => {
    const dir = pack({
      "assets/ui/font/a.json": JSON.stringify({ providers: [
        { type: "bitmap", file: "ui:font/missing.png", ascent: 7, chars: ["a"] },
        { type: "bitmap", file: "ui:font/grid.png", ascent: 7, chars: ["abc", "de"] },
        { type: "bitmap", file: "ui:font/odd.png", ascent: 7, chars: ["abc"] },
      ] }),
      "assets/ui/textures/font/grid.png": png(24, 16),
      "assets/ui/textures/font/odd.png": png(25, 8),
      "assets/ui/models/item/x.json": JSON.stringify({ textures: { layer0: "ui:item/none" } }),
      "assets/ui/items/y.json": JSON.stringify({ model: { type: "minecraft:select", cases: [{ model: { type: "minecraft:model", model: "ui:item/gone" } }] } }),
      "assets/ui/font/r.json": JSON.stringify({ providers: [{ type: "reference", id: "minecraft:nope" }] }),
    });
    const problems = checkPack(dir, new Set()).issues.map((i) => `${i.file}: ${i.problem}`);
    expect(problems).toEqual(expect.arrayContaining([
      expect.stringMatching(/a\.json provider 0: texture "ui:font\/missing\.png" not found/),
      expect.stringMatching(/a\.json provider 1: chars rows have different lengths/),
      expect.stringMatching(/a\.json provider 2: texture 25x8 doesn't divide into 3x1 glyph cells/),
      expect.stringMatching(/models\/item\/x\.json: texture "layer0" "ui:item\/none" not found/),
      expect.stringMatching(/items\/y\.json: model "ui:item\/gone" not found/),
      expect.stringMatching(/r\.json provider 0: font "minecraft:nope" not found/),
    ]));
  });
});
