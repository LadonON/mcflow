import { describe, expect, it } from "vitest";
import { botVersion, compareVersions, inSpawnProtection, patchClient, reasonText, toMinecraftAngles, toMineflayerAngles } from "../src/bots.js";

const TESTED = ["1.8.8", "1.20.4", "1.21.9", "1.21.11", "26.1"];

describe("botVersion", () => {
  it("speaks the server's version natively when mineflayer supports it", () => {
    expect(botVersion("1.21.11", TESTED, "26.1")).toEqual({ version: "1.21.11", translated: false });
  });

  it("falls back to mineflayer's newest version for newer servers (ViaBackwards translates)", () => {
    expect(botVersion("26.3", TESTED, "26.1")).toEqual({ version: "26.1", translated: true });
  });

  it("uses the nearest older tested version for an untested release in between", () => {
    expect(botVersion("1.21.10", TESTED, "26.1")).toEqual({ version: "1.21.9", translated: true });
  });

  it("refuses servers older than anything mineflayer speaks", () => {
    expect(() => botVersion("1.7.10", TESTED, "26.1")).toThrow(/can't speak Minecraft 1.7.10/);
  });
});

describe("compareVersions", () => {
  it("compares numerically, not as text", () => {
    expect(compareVersions("1.21.11", "1.21.4")).toBe(1);
    expect(compareVersions("26.1", "1.21.11")).toBe(1);
    expect(compareVersions("26.1", "26.1.0")).toBe(0);
  });
});

function fakeClient(state: string) {
  const sent: Array<[string, Record<string, unknown>]> = [];
  const client = { state, write: (name: string, params: Record<string, unknown>) => void sent.push([name, params]) };
  patchClient(client);
  return { client, sent };
}

describe("patchClient", () => {
  it("sends the resource-pack reply's UUID as a string", () => {
    const { client, sent } = fakeClient("configuration");
    const uuid = { toString: () => "a9086344-9c04-480c-9992-c63dc5e9f14e" };
    client.write("resource_pack_receive", { uuid, result: 3 });
    expect(sent).toEqual([["resource_pack_receive", { uuid: "a9086344-9c04-480c-9992-c63dc5e9f14e", result: 3 }]]);
  });

  it("follows every movement packet with tick_end in play", () => {
    const { client, sent } = fakeClient("play");
    for (const name of ["position", "position_look", "look", "flying"]) client.write(name, {});
    client.write("chat_message", {});
    expect(sent.map(([n]) => n)).toEqual([
      "position", "tick_end", "position_look", "tick_end", "look", "tick_end", "flying", "tick_end", "chat_message",
    ]);
  });

  it("sends no tick_end outside play", () => {
    const { client, sent } = fakeClient("configuration");
    client.write("position", {});
    expect(sent.map(([n]) => n)).toEqual(["position"]);
  });
});

describe("angles", () => {
  it("maps Minecraft's compass to mineflayer's", () => {
    expect(toMineflayerAngles(0, 0).yaw).toBeCloseTo(Math.PI); // south
    expect(toMineflayerAngles(180, 0).yaw).toBeCloseTo(0); // north
    expect(toMineflayerAngles(0, 90).pitch).toBeCloseTo(-Math.PI / 2); // looking down
  });

  it("round-trips", () => {
    for (const [yaw, pitch] of [[0, 0], [90, -30], [-90, 45], [179, 10], [-135.5, -89]] as const) {
      const m = toMineflayerAngles(yaw, pitch);
      expect(toMinecraftAngles(m.yaw, m.pitch)).toEqual({ yaw, pitch });
    }
  });
});

describe("reasonText", () => {
  it("reads the NBT-shaped kick reason 26.x sends", () => {
    const kick = { type: "compound", value: { translate: { type: "string", value: "multiplayer.disconnect.invalid_player_movement" } } };
    expect(reasonText(kick)).toBe("multiplayer.disconnect.invalid_player_movement");
  });

  it("reads a bare NBT string (what /kick sends)", () => {
    expect(reasonText({ type: "string", value: "Testing kicks" })).toBe("Testing kicks");
  });

  it("reads chat JSON and plain strings", () => {
    expect(reasonText('{"text":"Server closed"}')).toBe("Server closed");
    expect(reasonText("You are banned")).toBe("You are banned");
  });
});

describe("inSpawnProtection", () => {
  const spawn = { x: -192, z: -176 };
  it("covers a square of the given radius around spawn", () => {
    expect(inSpawnProtection({ x: -199, z: -188 }, spawn, 16)).toBe(true); // where a bot's chest click failed
    expect(inSpawnProtection({ x: -199, z: -196 }, spawn, 16)).toBe(false); // 20 blocks out on z
    expect(inSpawnProtection({ x: -176, z: -160 }, spawn, 16)).toBe(true); // the corner
  });
  it("is off when the radius is 0 or the spawn is unknown", () => {
    expect(inSpawnProtection({ x: -192, z: -176 }, spawn, 0)).toBe(false);
    expect(inSpawnProtection({ x: -192, z: -176 }, undefined, 16)).toBe(false);
  });
});
