// Finds the mcflow workspace and reads mcflow.toml plus the machine-local .mcflow/local.toml.

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { parse } from "smol-toml";

export class McflowError extends Error {}

export interface LocalSettings {
  java: string;
  paperJar: string;
  serverPort: number;
  rconPort: number;
  rconPassword: string;
  packPort: number;
}

export interface Workspace {
  root: string;
  serverDir: string;
  stateDir: string; // .mcflow/, git-ignored
  paperVersion: string;
  javaMinimum: number;
}

export function findRoot(start: string): string | undefined {
  let dir = resolve(start);
  for (;;) {
    if (existsSync(join(dir, "mcflow.toml"))) return dir;
    const parent = dirname(dir);
    if (parent === dir) return undefined;
    dir = parent;
  }
}

export function loadWorkspace(start: string = process.env.MCFLOW_PROJECT ?? process.cwd()): Workspace {
  const root = findRoot(start);
  if (!root) {
    throw new McflowError(
      `No mcflow workspace found at or above ${start}. Run mcflow-server from a folder made by \`mcflow init\`.`,
    );
  }
  const config = parse(readFileSync(join(root, "mcflow.toml"), "utf8")) as {
    minecraft: { paper_version: string; java_minimum: number };
  };
  return {
    root,
    serverDir: join(root, "server"),
    stateDir: join(root, ".mcflow"),
    paperVersion: config.minecraft.paper_version,
    javaMinimum: Number(config.minecraft.java_minimum),
  };
}

export function loadLocal(ws: Workspace): LocalSettings {
  const path = join(ws.stateDir, "local.toml");
  if (!existsSync(path)) {
    throw new McflowError("The test server isn't set up yet. Run `mcflow server setup` in the workspace first.");
  }
  const s = (parse(readFileSync(path, "utf8")) as { server: Record<string, string | number> }).server;
  return {
    java: String(s.java),
    paperJar: String(s.paper_jar),
    serverPort: Number(s.server_port),
    rconPort: Number(s.rcon_port),
    rconPassword: String(s.rcon_password),
    packPort: Number(s.pack_port),
  };
}
