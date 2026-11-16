// Bot swarms: many test bots running one behavior at once, for load testing a feature.

import { McflowError } from "./workspace.js";

export const BEHAVIORS = ["idle", "wander", "use_feature", "join_leave"] as const;
export type Behavior = (typeof BEHAVIORS)[number];

export interface SwarmOptions {
  count: number;
  behavior: Behavior;
  durationMs: number;
  staggerMs: number;
  namePrefix: string;
  /** use_feature: what each bot runs, e.g. "/menu". */
  featureCommand: string;
  /** use_feature: how each bot ends the feature: sneak, nothing, or a command to run. */
  featureClose: string;
  /** use_feature: how long each bot stays in the feature, turning its head, before closing it. */
  featureHoldMs: number;
}

/** The parts of a mineflayer bot a swarm drives. */
export interface SwarmBot {
  chat(message: string): void;
  setControlState(control: "forward" | "jump" | "sneak", state: boolean): void;
  look(yaw: number, pitch: number, force?: boolean): Promise<void>;
  entity?: { yaw: number; pitch: number };
}

/** The parts of BotManager a swarm needs (a fake in tests). */
export interface SwarmBots {
  join(name: string, timeoutMs: number): Promise<{ joinMs: number }>;
  leave(name: string): void;
  /** The bot, or undefined if it isn't known (unlike BotManager.get, this doesn't throw for a kicked bot). */
  find(name: string): { bot: SwarmBot; online: boolean; lastKick?: string } | undefined;
}

export interface SwarmReport {
  behavior: Behavior;
  requested: number;
  joined: number;
  failedJoins: { name: string; reason: string }[];
  joinMs?: { min: number; median: number; max: number };
  ranForMs: number;
  actions: Record<string, number>;
  kicked: { name: string; reason: string }[];
  errors: string[];
}

export interface Clock {
  sleep(ms: number): Promise<void>;
  now(): number;
  random(): number;
}

export const realClock: Clock = {
  sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
  now: () => Date.now(),
  random: Math.random,
};

/** Bot names for a swarm: prefix + index, within Minecraft's 16-character limit. */
export function swarmNames(prefix: string, count: number): string[] {
  const width = String(count - 1).length;
  if (!/^[A-Za-z0-9_]+$/.test(prefix) || prefix.length + width > 16) {
    throw new McflowError(`namePrefix "${prefix}" must be letters, digits or _, and short enough for ${count} bots (16 characters with the number).`);
  }
  return Array.from({ length: count }, (_, i) => `${prefix}${i}`);
}

function median(values: number[]): number {
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid]! : Math.round((s[mid - 1]! + s[mid]!) / 2);
}

/**
 * Joins the swarm (staggered), runs the behavior on every bot until the time is up, then disconnects them all.
 * Bots that get kicked stop and are reported; join_leave bots keep cycling.
 */
export async function runSwarm(bots: SwarmBots, o: SwarmOptions, clock: Clock = realClock): Promise<SwarmReport> {
  const names = swarmNames(o.namePrefix, o.count);
  const actions: Record<string, number> = {};
  const count = (what: string) => (actions[what] = (actions[what] ?? 0) + 1);
  const failedJoins: SwarmReport["failedJoins"] = [];
  const errors: string[] = [];
  const joinTimes: number[] = [];
  const online = new Set<string>();

  const join = async (name: string) => {
    try {
      const r = await bots.join(name, 60_000);
      joinTimes.push(r.joinMs);
      online.add(name);
      count("join");
      return true;
    } catch (e) {
      failedJoins.push({ name, reason: e instanceof Error ? e.message : String(e) });
      return false;
    }
  };
  const leave = (name: string) => {
    if (!online.delete(name)) return;
    try {
      bots.leave(name);
      count("leave");
    } catch (e) {
      errors.push(`${name}: ${e instanceof Error ? e.message : String(e)}`);
    }
  };
  const alive = (name: string) => online.has(name) && bots.find(name)?.online === true;
  const botOf = (name: string) => bots.find(name)!.bot; // only called while alive(name)
  const pick = (min: number, max: number) => min + clock.random() * (max - min);

  // join_leave bots join inside their own loop; everyone else joins up front, staggered.
  const started = clock.now();
  if (o.behavior !== "join_leave") {
    const pending: Promise<boolean>[] = [];
    for (const name of names) {
      pending.push(join(name));
      if (o.staggerMs > 0) await clock.sleep(o.staggerMs);
    }
    await Promise.all(pending);
  }
  const runFrom = clock.now();
  const deadline = runFrom + o.durationMs;
  const timeLeft = () => deadline - clock.now();

  const loops: Record<Behavior, (name: string) => Promise<void>> = {
    idle: async (name) => {
      while (timeLeft() > 0 && alive(name)) await clock.sleep(Math.min(500, timeLeft()));
    },
    wander: async (name) => {
      while (timeLeft() > 0 && alive(name)) {
        const bot = botOf(name);
        await bot.look(pick(0, Math.PI * 2), pick(-0.3, 0.3), true);
        const jump = clock.random() < 0.3;
        bot.setControlState("forward", true);
        if (jump) bot.setControlState("jump", true);
        await clock.sleep(Math.min(pick(500, 2000), Math.max(timeLeft(), 0)));
        bot.setControlState("forward", false);
        bot.setControlState("jump", false);
        count("wander");
        await clock.sleep(Math.min(pick(500, 1500), Math.max(timeLeft(), 0)));
      }
    },
    use_feature: async (name) => {
      while (timeLeft() > 0 && alive(name)) {
        const bot = botOf(name);
        bot.chat(o.featureCommand);
        count("feature_open");
        const base = { yaw: bot.entity?.yaw ?? 0, pitch: bot.entity?.pitch ?? 0 };
        const until = Math.min(clock.now() + o.featureHoldMs, deadline);
        while (clock.now() < until && alive(name)) {
          await bot.look(base.yaw + pick(-0.6, 0.6), base.pitch + pick(-0.4, 0.4), true); // small turns, as if aiming at the UI
          count("look");
          await clock.sleep(200);
        }
        if (!alive(name)) break;
        if (o.featureClose === "sneak") {
          bot.setControlState("sneak", true);
          await clock.sleep(300);
          bot.setControlState("sneak", false);
        } else if (o.featureClose !== "none") {
          bot.chat(o.featureClose);
        }
        count("feature_close");
        await clock.sleep(Math.min(pick(500, 1500), Math.max(timeLeft(), 0)));
      }
    },
    join_leave: async (name) => {
      await clock.sleep(names.indexOf(name) * o.staggerMs);
      while (timeLeft() > 0) {
        if (!(await join(name))) {
          await clock.sleep(1000); // a failed join is reported; don't hammer the server
          continue;
        }
        await clock.sleep(Math.min(pick(1000, 3000), Math.max(timeLeft(), 0)));
        leave(name);
        await clock.sleep(Math.min(pick(500, 1000), Math.max(timeLeft(), 0)));
      }
    },
  };

  await Promise.all(
    names.map((name) =>
      loops[o.behavior](name).catch((e) => {
        errors.push(`${name}: ${e instanceof Error ? e.message : String(e)}`);
      }),
    ),
  );

  const kicked: SwarmReport["kicked"] = [];
  for (const name of names) {
    if (!online.has(name)) continue;
    const m = bots.find(name);
    if (m && !m.online) {
      kicked.push({ name, reason: m.lastKick ?? "disconnected" });
      online.delete(name);
    }
  }
  for (const name of [...online]) leave(name);

  return {
    behavior: o.behavior,
    requested: o.count,
    joined: o.behavior === "join_leave" ? new Set(names.filter((n) => !failedJoins.some((f) => f.name === n))).size : joinTimes.length,
    failedJoins,
    joinMs: joinTimes.length ? { min: Math.min(...joinTimes), median: median(joinTimes), max: Math.max(...joinTimes) } : undefined,
    ranForMs: clock.now() - started,
    actions,
    kicked,
    errors,
  };
}

/** Paper's `tps` output ("TPS from last 1m, 5m, 15m: 20.0, 20.0, 20.0") as numbers, or undefined. */
export function parseTps(output: string): number[] | undefined {
  const plain = output.replace(/§./g, "");
  const m = plain.match(/TPS from last[^:]*:\s*([\d.*]+),\s*([\d.*]+),\s*([\d.*]+)/);
  return m ? m.slice(1, 4).map((v) => Number(v.replace("*", ""))) : undefined;
}

/**
 * Splits Paper's "moved too quickly/wrongly" warnings into those within `graceSeconds` of the player joining
 * (a harmless race: many bots joining at once each get a few, at their spawn point) and later ones, which are real
 * movement corrections. Works on log lines in order, using their [HH:MM:SS] timestamps.
 */
export function classifyMovementWarnings(lines: string[], graceSeconds = 3): { atJoin: number; later: string[] } {
  const seconds = (line: string) => {
    const m = line.match(/^\[(\d\d):(\d\d):(\d\d)\]/);
    return m ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) : undefined;
  };
  const joinedAt = new Map<string, number>();
  let atJoin = 0;
  const later: string[] = [];
  for (const line of lines) {
    const t = seconds(line);
    const joined = line.match(/: (?:System chat: )?(\w{1,16}) joined the game/);
    if (joined && t !== undefined) joinedAt.set(joined[1]!, t);
    const moved = line.match(/: (\w{1,16}) moved (?:too quickly|wrongly)!/);
    if (!moved) continue;
    const j = joinedAt.get(moved[1]!);
    if (t !== undefined && j !== undefined && t - j >= 0 && t - j <= graceSeconds) atJoin++;
    else later.push(line);
  }
  return { atJoin, later };
}
