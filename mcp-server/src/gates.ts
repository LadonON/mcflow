// The quality gates' logic: tick-time comparison, leak detection, thread-safety scans. Pure functions; the MCP
// tools in index.ts collect the data (RCON, jcmd, logs, source files) and pass it in.

// ---- Performance -------------------------------------------------------------------------------------------

export interface Window {
  avg: number;
  min: number;
  max: number;
}

/** Paper's `mspt`: "Server tick times (avg/min/max) from last 5s, 10s, 1m:" then three avg/min/max triples. */
export function parseMspt(output: string): { s5: Window; s10: Window; m1: Window } | undefined {
  const plain = output.replace(/§./g, "");
  const triples = [...plain.matchAll(/([\d.]+)\/([\d.]+)\/([\d.]+)/g)].map((m) => ({ avg: +m[1]!, min: +m[2]!, max: +m[3]! }));
  if (!/tick times/i.test(plain) || triples.length < 3) return undefined;
  return { s5: triples[0]!, s10: triples[1]!, m1: triples[2]! };
}

export interface MsptSummary {
  samples: number;
  /** Median of the 5-second average tick times. */
  medianAvg: number;
  /** 95th percentile of the 5-second averages. */
  p95Avg: number;
  /** The longest single tick seen in any 5-second window. */
  worstTick: number;
}

const percentile = (values: number[], p: number) => {
  const s = [...values].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.max(0, Math.ceil((p / 100) * s.length) - 1))]!;
};
const round2 = (n: number) => Math.round(n * 100) / 100;

export function summariseMspt(windows: Window[]): MsptSummary {
  if (windows.length === 0) throw new Error("No tick-time samples were collected.");
  const avgs = windows.map((w) => w.avg);
  return {
    samples: windows.length,
    medianAvg: round2(percentile(avgs, 50)),
    p95Avg: round2(percentile(avgs, 95)),
    worstTick: round2(Math.max(...windows.map((w) => w.max))),
  };
}

export interface PerfLimits {
  /** A 5-second average above this fails, whatever the baseline (50 ms = the server can't hold 20 TPS). */
  maxAvgMs: number;
  /** Allowed rise of the median average over the baseline, in percent... */
  maxRegressionPct: number;
  /** ...ignored while the rise is below this many ms (idle servers tick in ~1 ms, where % is noise). */
  minRegressionMs: number;
}

export function judgePerformance(current: MsptSummary, baseline: MsptSummary | undefined, limits: PerfLimits) {
  const failures: string[] = [];
  if (current.p95Avg > limits.maxAvgMs) {
    failures.push(`p95 of the 5-second average tick time is ${current.p95Avg} ms, over the ${limits.maxAvgMs} ms limit`);
  }
  let regression: { ms: number; pct: number } | undefined;
  if (baseline) {
    const ms = round2(current.medianAvg - baseline.medianAvg);
    const pct = baseline.medianAvg > 0 ? round2((ms / baseline.medianAvg) * 100) : 0;
    regression = { ms, pct };
    if (ms > limits.minRegressionMs && pct > limits.maxRegressionPct) {
      failures.push(`median tick time rose ${ms} ms (${pct}%) over the baseline (${baseline.medianAvg} → ${current.medianAvg} ms)`);
    }
  }
  return { pass: failures.length === 0, failures, regression };
}

// ---- Memory ------------------------------------------------------------------------------------------------

/** `jcmd <pid> GC.class_histogram` → class name → instance count. */
export function parseHistogram(text: string): Map<string, number> {
  const counts = new Map<string, number>();
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^\s*\d+:\s+(\d+)\s+\d+\s+(\S+)/);
    if (m) counts.set(m[2]!, (counts.get(m[2]!) ?? 0) + Number(m[1]));
  }
  return counts;
}

/** Bukkit bookkeeping that a leaking plugin grows: listener registrations and scheduled tasks. */
export const TRACKED_SERVER_CLASSES = ["org.bukkit.plugin.RegisteredListener", "org.bukkit.craftbukkit.scheduler.CraftTask"];

export interface LeakFinding {
  className: string;
  counts: [number, number, number];
}

/**
 * Compares three histograms taken with no bots online: after a warm-up, after N cycles and after 2N cycles. A class
 * from the plugin's package, or a tracked server class, whose count rises at both steps is a leak: something is
 * kept per cycle and never released. A rise at only one step is noise (lazy init, a cache filling once).
 */
export function findLeaks(a: Map<string, number>, b: Map<string, number>, c: Map<string, number>, pluginPackage: string): LeakFinding[] {
  const names = new Set([...a.keys(), ...b.keys(), ...c.keys()].filter((n) => n.startsWith(pluginPackage + ".") || TRACKED_SERVER_CLASSES.includes(n)));
  const out: LeakFinding[] = [];
  for (const n of names) {
    const counts: [number, number, number] = [a.get(n) ?? 0, b.get(n) ?? 0, c.get(n) ?? 0];
    if (counts[1] > counts[0] && counts[2] > counts[1]) out.push({ className: n, counts });
  }
  return out.sort((x, y) => y.counts[2] - y.counts[0] - (x.counts[2] - x.counts[0]));
}

/** `jcmd <pid> GC.heap_info` → used heap in MB (G1: "garbage-first heap total …, used 285901K"). */
export function parseHeapUsedMb(text: string): number | undefined {
  const m = text.match(/used\s+(\d+)K/);
  return m ? Math.round(Number(m[1]) / 1024) : undefined;
}

// ---- Thread safety -----------------------------------------------------------------------------------------

export interface ThreadFinding {
  file: string;
  line: number;
  call: string;
  context: string;
}

/** Code that runs off the main thread: async scheduler tasks, futures, threads, Netty handlers, async events. */
const ASYNC_CONTEXT =
  /\b(runTaskAsynchronously|runTaskLaterAsynchronously|runTaskTimerAsynchronously|runAsync|supplyAsync|thenAcceptAsync|thenApplyAsync|thenRunAsync|new\s+Thread|\.execute|\.submit)\s*\(|\b(?:public|protected|private)?\s*void\s+(channelRead0?|channelActive|channelInactive|userEventTriggered|write)\s*\(|@EventHandler[^{]*\{?[^)]*\(\s*(?:final\s+)?(AsyncChatEvent|AsyncPlayerChatEvent|AsyncPlayerPreLoginEvent|AsyncTabCompleteEvent)\b/g;

/** Bukkit calls that must happen on the main thread (not exhaustive; the common ones). */
const MAIN_THREAD_ONLY =
  /\.(teleport|setGameMode|setHealth|damage|setType|setBlockData|getBlockAt|getBlock|spawnEntity|spawn|dropItem|dropItemNaturally|openInventory|closeInventory|setItem|setItemInMainHand|addPotionEffect|removePotionEffect|setVelocity|kickPlayer|kick|setOp|addPassenger|remove|registerEvents|unregisterAll|playSound|sendTitlePart|showTitle|clearTitle|setPlayerProfile|getNearbyEntities|getEntities|createExplosion|setTime|setStorm)\s*\(/g;

/** The end of the block that opens at or after `from` (first "{"), or the end of the statement for lambdas without braces. */
function blockEnd(text: string, from: number): number {
  let i = text.indexOf("{", from);
  const semi = text.indexOf(";", from);
  if (i === -1 || (semi !== -1 && semi < i)) return semi === -1 ? text.length : semi;
  let depth = 0;
  for (; i < text.length; i++) {
    if (text[i] === "{") depth++;
    else if (text[i] === "}" && --depth === 0) return i;
  }
  return text.length;
}

/** Hops back to the main thread inside an async block; calls after these are fine. */
const SYNC_HOP = /\b(runTask|runTaskLater|callSyncMethod|getGlobalRegionScheduler|getScheduler\(\)\.run|execute\(\s*plugin)\s*\(/g;

/**
 * Finds main-thread-only Bukkit calls inside code that runs on another thread. A heuristic: it reads source text,
 * not types, so it can miss calls through helper methods and flags calls on non-Bukkit objects with the same name.
 * Calls inside a nested runTask(...) are not flagged.
 */
export function scanThreadSafety(files: { path: string; text: string }[]): ThreadFinding[] {
  const out: ThreadFinding[] = [];
  for (const { path, text } of files) {
    const code = text.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " ")).replace(/\/\/[^\n]*/g, (m) => " ".repeat(m.length));
    for (const ctx of code.matchAll(ASYNC_CONTEXT)) {
      const start = ctx.index!;
      const end = blockEnd(code, start);
      const body = code.slice(start, end);
      const hops = [...body.matchAll(SYNC_HOP)].map((h) => [start + h.index!, blockEnd(code, start + h.index!)] as const);
      for (const call of body.matchAll(MAIN_THREAD_ONLY)) {
        const at = start + call.index!;
        if (hops.some(([s, e]) => at > s && at < e)) continue;
        out.push({
          file: path,
          line: code.slice(0, at).split("\n").length,
          call: call[1]!,
          context: (ctx[1] ?? ctx[2] ?? ctx[3] ?? "async").trim(),
        });
      }
    }
  }
  // One finding per file:line:call (overlapping contexts can match the same call).
  return out.filter((f, i) => out.findIndex((g) => g.file === f.file && g.line === f.line && g.call === f.call) === i);
}

/** Server-log lines where Paper caught a Bukkit call off the main thread, or a plugin's stack trace says so. */
export function scanAsyncLog(lines: string[]): string[] {
  return lines.filter((l) => /Asynchronous [\w ]+!|AsyncCatcher|may only be (?:triggered|called|used) synchronously|accessed? (?:from |off )?(?:an? )?async|not on the main thread/i.test(l));
}
