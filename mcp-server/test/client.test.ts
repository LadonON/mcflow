import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { createServer, Server } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { attach, BridgeClient, loadClientState, screenshotPath } from "../src/client.js";
import type { Workspace } from "../src/workspace.js";

/** Speaks the mod's protocol (Bridge.java): one JSON object per line, token checked on every request. */
function fakeMod(token: string): Promise<{ server: Server; port: number }> {
  return new Promise((resolve) => {
    const server = createServer((socket) => {
      let buffer = "";
      socket.setEncoding("utf8");
      socket.on("data", (chunk: string) => {
        buffer += chunk;
        let i: number;
        while ((i = buffer.indexOf("\n")) >= 0) {
          const req = JSON.parse(buffer.slice(0, i));
          buffer = buffer.slice(i + 1);
          let reply: object;
          if (req.token !== token) reply = { id: req.id, ok: false, error: "bad token" };
          else if (req.command === "status") reply = { id: req.id, ok: true, result: { minecraft: "26.3", inWorld: true } };
          else reply = { id: req.id, ok: false, error: `unknown command: ${req.command}` };
          socket.write(JSON.stringify(reply) + "\n");
        }
      });
    });
    server.listen(0, "127.0.0.1", () => {
      const a = server.address();
      resolve({ server, port: typeof a === "object" && a ? a.port : 0 });
    });
  });
}

function workspaceWithClient(gameDir: string): Workspace {
  const root = mkdtempSync(join(tmpdir(), "mcflow-client-"));
  mkdirSync(join(root, ".mcflow"));
  writeFileSync(
    join(root, ".mcflow", "client.toml"),
    `[client]\ngame_dir = "${gameDir.replace(/\\/g, "\\\\")}"\nlayout = "official"\nminecraft_version = "26.3"\n`,
  );
  return { root, serverDir: join(root, "server"), stateDir: join(root, ".mcflow"), paperVersion: "26.3", javaMinimum: 25 };
}

describe("BridgeClient", () => {
  let server: Server | undefined;
  afterEach(() => server?.close());

  it("sends the token and reads replies", async () => {
    const fake = await fakeMod("secret");
    server = fake.server;
    const client = await BridgeClient.open({ port: fake.port, token: "secret", pid: 1, minecraft: "26.3", mod: "0.1.0" });
    expect(await client.call("status")).toEqual({ minecraft: "26.3", inWorld: true });
    await expect(client.call("teleport")).rejects.toThrow("Minecraft: unknown command: teleport");
    client.close();
  });

  it("surfaces a wrong token as an error", async () => {
    const fake = await fakeMod("secret");
    server = fake.server;
    const client = await BridgeClient.open({ port: fake.port, token: "wrong", pid: 1, minecraft: "26.3", mod: "0.1.0" });
    await expect(client.call("status")).rejects.toThrow("bad token");
    client.close();
  });

  it("finds the running game through bridge.json", async () => {
    const fake = await fakeMod("secret");
    server = fake.server;
    const gameDir = mkdtempSync(join(tmpdir(), "mcflow-game-"));
    mkdirSync(join(gameDir, "mcflow"));
    writeFileSync(join(gameDir, "mcflow", "bridge.json"), JSON.stringify({ port: fake.port, token: "secret" }));
    const ws = workspaceWithClient(gameDir);
    const client = await attach(loadClientState(ws), 0);
    expect(await client.call("status")).toMatchObject({ inWorld: true });
    client.close();
  });

  it("explains a game that isn't running", async () => {
    const ws = workspaceWithClient(mkdtempSync(join(tmpdir(), "mcflow-game-")));
    await expect(attach(loadClientState(ws), 0)).rejects.toThrow(/Ask the user to start Minecraft 26\.3/);
  });

  it("explains a missing install", () => {
    const root = mkdtempSync(join(tmpdir(), "mcflow-noclient-"));
    const ws = { root, serverDir: join(root, "server"), stateDir: join(root, ".mcflow"), paperVersion: "26.3", javaMinimum: 25 };
    expect(() => loadClientState(ws)).toThrow(/mcflow client install/);
  });
});

describe("screenshotPath", () => {
  it("keeps names safe and inside server/screenshots", () => {
    const ws = workspaceWithClient(tmpdir());
    const p = screenshotPath(ws, "../../etc", "Shop GUI: open!");
    expect(p).toBe(join(ws.serverDir, "screenshots", "..-..-etc", "Shop-GUI-open.png"));
  });
});
