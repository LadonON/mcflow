import { describe, expect, it } from "vitest";
import { classifyMovementWarnings, parseTps, runSwarm, swarmNames, type Clock, type SwarmBot, type SwarmBots, type SwarmOptions } from "../src/swarm.js";

/** Virtual time: sleeping advances the clock at once, so a 30 s swarm runs in milliseconds. */
function virtualClock(seed = 1): Clock {
  let t = 0;
  let x = seed;
  return {
    now: () => t,
    sleep: async (ms) => {
      t += ms;
      await Promise.resolve();
    },
    random: () => ((x = (x * 16807) % 2147483647) - 1) / 2147483646,
  };
}

class FakeBot implements SwarmBot {
  chats: string[] = [];
  controls = { forward: false, jump: false, sneak: false };
  presses = { forward: 0, jump: 0, sneak: 0 };
  looks = 0;
  entity = { yaw: 1, pitch: 0 };
  chat(message: string) {
    this.chats.push(message);
  }
  setControlState(c: "forward" | "jump" | "sneak", on: boolean) {
    this.controls[c] = on;
    if (on) this.presses[c]++;
  }
  async look() {
    this.looks++;
  }
}

class FakeBots implements SwarmBots {
  bots = new Map<string, { bot: FakeBot; online: boolean; lastKick?: string }>();
  joins: string[] = [];
  leaves: string[] = [];
  failNames = new Set<string>();
  kickAfterJoin = new Set<string>();
  async join(name: string) {
    if (this.failNames.has(name)) throw new Error("kicked: Server full");
    this.joins.push(name);
    const entry = { bot: this.bots.get(name)?.bot ?? new FakeBot(), online: true };
    this.bots.set(name, entry);
    if (this.kickAfterJoin.has(name)) Object.assign(entry, { online: false, lastKick: "Kicked for flying" });
    return { joinMs: 300 };
  }
  leave(name: string) {
    this.leaves.push(name);
    this.bots.get(name)!.online = false;
  }
  find(name: string) {
    return this.bots.get(name);
  }
}

const base: SwarmOptions = {
  count: 4,
  behavior: "idle",
  durationMs: 10_000,
  staggerMs: 100,
  namePrefix: "Swarm",
  featureCommand: "/menu",
  featureClose: "sneak",
  featureHoldMs: 1000,
};

describe("swarmNames", () => {
  it("numbers bots after the prefix", () => {
    expect(swarmNames("Swarm", 3)).toEqual(["Swarm0", "Swarm1", "Swarm2"]);
  });
  it("keeps names within 16 characters and valid", () => {
    expect(swarmNames("ABCDEFGHIJKLMNO", 10)[9]).toBe("ABCDEFGHIJKLMNO9"); // exactly 16
    expect(() => swarmNames("ABCDEFGHIJKLMNO", 11)).toThrow(/16 characters/); // "…10" would be 17
    expect(() => swarmNames("bad name", 2)).toThrow(/letters, digits or _/);
  });
});

describe("runSwarm", () => {
  it("idle: joins everyone, then disconnects everyone", async () => {
    const bots = new FakeBots();
    const r = await runSwarm(bots, base, virtualClock());
    expect(r.joined).toBe(4);
    expect(bots.leaves.sort()).toEqual(["Swarm0", "Swarm1", "Swarm2", "Swarm3"]);
    expect(r.actions).toEqual({ join: 4, leave: 4 });
    expect(r.joinMs).toEqual({ min: 300, median: 300, max: 300 });
    expect(r.kicked).toEqual([]);
  });

  it("wander: walks and turns, and leaves no key held", async () => {
    const bots = new FakeBots();
    const r = await runSwarm(bots, { ...base, behavior: "wander" }, virtualClock());
    expect(r.actions.wander).toBeGreaterThan(4);
    for (const { bot } of bots.bots.values()) {
      expect(bot.presses.forward).toBeGreaterThan(0);
      expect(bot.looks).toBeGreaterThan(0);
      expect(bot.controls).toEqual({ forward: false, jump: false, sneak: false });
    }
  });

  it("use_feature: opens with the command and closes with sneak, repeatedly", async () => {
    const bots = new FakeBots();
    const r = await runSwarm(bots, { ...base, behavior: "use_feature" }, virtualClock());
    for (const { bot } of bots.bots.values()) {
      expect(bot.chats.length).toBeGreaterThan(1);
      expect(new Set(bot.chats)).toEqual(new Set(["/menu"]));
      expect(bot.presses.sneak).toBeGreaterThanOrEqual(bot.chats.length - 1);
      expect(bot.controls.sneak).toBe(false);
    }
    expect(r.actions.feature_open).toBeGreaterThanOrEqual(r.actions.feature_close!);
  });

  it("use_feature: can close with a command instead", async () => {
    const bots = new FakeBots();
    await runSwarm(bots, { ...base, behavior: "use_feature", featureCommand: "/shop", featureClose: "/shop close" }, virtualClock());
    const chats = bots.bots.get("Swarm0")!.bot.chats;
    expect(chats[0]).toBe("/shop");
    expect(chats[1]).toBe("/shop close");
  });

  it("join_leave: every bot joins and leaves more than once", async () => {
    const bots = new FakeBots();
    const r = await runSwarm(bots, { ...base, behavior: "join_leave", durationMs: 20_000 }, virtualClock());
    for (const name of ["Swarm0", "Swarm1", "Swarm2", "Swarm3"]) {
      expect(bots.joins.filter((n) => n === name).length).toBeGreaterThan(1);
    }
    expect(r.actions.join).toBe(r.actions.leave);
    expect(r.joined).toBe(4);
  });

  it("reports failed joins and kicked bots, and doesn't leave a kicked bot", async () => {
    const bots = new FakeBots();
    bots.failNames.add("Swarm1");
    bots.kickAfterJoin.add("Swarm2");
    const r = await runSwarm(bots, base, virtualClock());
    expect(r.failedJoins).toEqual([{ name: "Swarm1", reason: "kicked: Server full" }]);
    expect(r.kicked).toEqual([{ name: "Swarm2", reason: "Kicked for flying" }]);
    expect(r.joined).toBe(3);
    expect(bots.leaves.sort()).toEqual(["Swarm0", "Swarm3"]);
  });
});

describe("parseTps", () => {
  it("reads Paper's tps output, with colour codes and the * cap marker", () => {
    expect(parseTps("§6TPS from last 1m, 5m, 15m: §a*20.0, §a19.98, §a19.5")).toEqual([20, 19.98, 19.5]);
  });
  it("returns undefined for anything else", () => {
    expect(parseTps("Unknown command")).toBeUndefined();
  });
});

describe("classifyMovementWarnings", () => {
  const log = [
    "[18:44:10] [Server thread/INFO]: System chat: Menu0 joined the game",
    "[18:44:10] [Server thread/WARN]: Menu0 moved too quickly! -181.5,64.0,-180.5",
    "[18:44:12] [Server thread/WARN]: Menu0 moved too quickly! -181.5,64.0,-180.5",
    "[18:44:20] [Server thread/WARN]: Menu0 moved too quickly! -170.2,64.0,-180.5",
    "[18:44:21] [Server thread/WARN]: Ghost moved wrongly!",
  ];
  it("counts warnings within the grace period after a join as join-time", () => {
    const r = classifyMovementWarnings(log);
    expect(r.atJoin).toBe(2);
    expect(r.later).toEqual([log[3], log[4]]); // 10 s after joining, and a player we never saw join
  });
  it("works however far the world is from 0,0", () => {
    expect(classifyMovementWarnings(log, 0).atJoin).toBe(1);
  });
});
