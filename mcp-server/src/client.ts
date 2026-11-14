// Talks to mcflow's Fabric client mod over its loopback bridge (see client-mod/.../Bridge.java).
// The mod writes <game dir>/mcflow/bridge.json with a port and token when Minecraft starts.

import { existsSync, readFileSync } from "node:fs";
import { connect, Socket } from "node:net";
import { join } from "node:path";
import { parse } from "smol-toml";
import { McflowError, Workspace } from "./workspace.js";

export interface ClientState {
  gameDir: string;
  layout: string;
  minecraftVersion: string;
}

export interface BridgeInfo {
  port: number;
  token: string;
  pid: number;
  minecraft: string;
  mod: string;
}

export interface ClientStatus {
  minecraft: string;
  inWorld: boolean;
  // Older mod builds leave null fields out, so treat missing as null.
  server?: string | null;
  player?: string | null;
  screen?: string | null;
  screenTitle?: string | null;
  windowWidth: number;
  windowHeight: number;
}

export function loadClientState(ws: Workspace): ClientState {
  const path = join(ws.stateDir, "client.toml");
  if (!existsSync(path)) {
    throw new McflowError(
      "mcflow's client mod isn't installed. It's required for in-game checks: ask the user to close Minecraft " +
        "and run `mcflow client install` (with their instance folder if they don't use the official launcher).",
    );
  }
  const c = (parse(readFileSync(path, "utf8")) as { client: Record<string, string> }).client;
  return { gameDir: String(c.game_dir), layout: String(c.layout), minecraftVersion: String(c.minecraft_version) };
}

export function readBridgeInfo(state: ClientState): BridgeInfo | undefined {
  const path = join(state.gameDir, "mcflow", "bridge.json");
  if (!existsSync(path)) return undefined;
  try {
    return JSON.parse(readFileSync(path, "utf8")) as BridgeInfo;
  } catch {
    return undefined; // being written right now
  }
}

export class BridgeClient {
  private buffer = "";
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private nextId = 1;

  private constructor(
    private readonly socket: Socket,
    private readonly token: string,
  ) {
    socket.setEncoding("utf8");
    socket.on("data", (chunk: string) => {
      this.buffer += chunk;
      let newline: number;
      while ((newline = this.buffer.indexOf("\n")) >= 0) {
        const line = this.buffer.slice(0, newline);
        this.buffer = this.buffer.slice(newline + 1);
        const reply = JSON.parse(line) as { id: number; ok: boolean; result?: unknown; error?: string };
        const waiter = this.pending.get(reply.id);
        this.pending.delete(reply.id);
        if (reply.ok) waiter?.resolve(reply.result);
        else waiter?.reject(new McflowError(`Minecraft: ${reply.error}`));
      }
    });
    socket.on("close", () => {
      for (const w of this.pending.values()) w.reject(new McflowError("Minecraft closed the connection."));
      this.pending.clear();
    });
  }

  static async open(info: BridgeInfo, timeoutMs = 3000): Promise<BridgeClient> {
    const socket = await new Promise<Socket>((resolve, reject) => {
      const s = connect({ host: "127.0.0.1", port: info.port });
      const timer = setTimeout(() => {
        s.destroy();
        reject(new McflowError("Minecraft's mcflow bridge didn't answer."));
      }, timeoutMs);
      s.once("connect", () => {
        clearTimeout(timer);
        resolve(s);
      });
      s.once("error", () => {
        clearTimeout(timer);
        reject(new McflowError("Minecraft isn't running (or was started without mcflow's mod)."));
      });
    });
    return new BridgeClient(socket, info.token);
  }

  call<T = unknown>(command: string, args: Record<string, unknown> = {}, timeoutMs = 35_000): Promise<T> {
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new McflowError(`Minecraft didn't answer "${command}" within ${timeoutMs / 1000}s.`));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (v) => {
          clearTimeout(timer);
          resolve(v as T);
        },
        reject: (e) => {
          clearTimeout(timer);
          reject(e);
        },
      });
      this.socket.write(JSON.stringify({ token: this.token, id, command, args }) + "\n");
    });
  }

  close(): void {
    this.socket.destroy();
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Connect to the running game, optionally waiting for the user to start it. */
export async function attach(state: ClientState, waitMs: number): Promise<BridgeClient> {
  const deadline = Date.now() + waitMs;
  let lastError: unknown;
  do {
    const info = readBridgeInfo(state);
    if (info) {
      try {
        return await BridgeClient.open(info);
      } catch (e) {
        lastError = e; // a stale bridge.json from a crashed game; keep waiting for a fresh one
      }
    }
    if (Date.now() >= deadline) break;
    await sleep(1000);
  } while (Date.now() < deadline);
  throw lastError instanceof McflowError
    ? lastError
    : new McflowError(
        `Minecraft isn't running with mcflow's mod. Ask the user to start Minecraft ${state.minecraftVersion} ` +
          `(the Fabric installation) and sign in, then try again.`,
      );
}

export async function waitFor(
  bridge: BridgeClient,
  done: (s: ClientStatus) => boolean,
  timeoutMs: number,
  what: string,
): Promise<ClientStatus> {
  const deadline = Date.now() + timeoutMs;
  let status = await bridge.call<ClientStatus>("status");
  while (!done(status)) {
    if (Date.now() > deadline) {
      throw new McflowError(`Timed out waiting for ${what}. Client is on screen ${status.screen ?? "(none)"}.`);
    }
    await sleep(500);
    status = await bridge.call<ClientStatus>("status");
  }
  return status;
}

/** server/screenshots/<task>/<label>.png, with names reduced to safe characters. */
export function screenshotPath(ws: Workspace, task: string, label: string): string {
  const clean = (s: string) => s.trim().replace(/[^\w.-]+/g, "-").replace(/^-+|-+$/g, "") || "untitled";
  return join(ws.serverDir, "screenshots", clean(task), `${clean(label)}.png`);
}
