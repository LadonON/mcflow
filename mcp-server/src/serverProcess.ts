// Starts and stops the local Paper server. One server per workspace; its PID lives in .mcflow/server.pid
// so a restarted MCP server can still find (and stop) a server it didn't launch itself.

import { ChildProcess, spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { readLog } from "./logs.js";
import { RconClient } from "./rcon.js";
import { LocalSettings, McflowError, Workspace } from "./workspace.js";

const READY = /Done \(\d+[.,]\d+s\)!/;
const EULA_MISSING = /You need to agree to the EULA/;

export interface ServerStatus {
  running: boolean;
  pid?: number;
  rconReachable: boolean;
  onlinePlayers?: string;
}

function pidFile(ws: Workspace): string {
  return join(ws.stateDir, "server.pid");
}

function readPid(ws: Workspace): number | undefined {
  if (!existsSync(pidFile(ws))) return undefined;
  const pid = Number(readFileSync(pidFile(ws), "utf8").trim());
  return Number.isInteger(pid) && pid > 0 ? pid : undefined;
}

function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return (e as NodeJS.ErrnoException).code === "EPERM";
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export class ServerController {
  private child?: ChildProcess;
  private consoleTail: string[] = [];

  constructor(
    private readonly ws: Workspace,
    private readonly local: () => LocalSettings,
  ) {}

  livePid(): number | undefined {
    const pid = readPid(this.ws);
    if (pid && isAlive(pid)) return pid;
    if (pid) rmSync(pidFile(this.ws), { force: true });
    return undefined;
  }

  async status(): Promise<ServerStatus> {
    const pid = this.livePid();
    if (!pid) return { running: false, rconReachable: false };
    const s = this.local();
    try {
      const rcon = await RconClient.connect(s.rconPort, s.rconPassword, 2000);
      try {
        return { running: true, pid, rconReachable: true, onlinePlayers: await rcon.command("list") };
      } finally {
        rcon.close();
      }
    } catch {
      return { running: true, pid, rconReachable: false };
    }
  }

  async start(timeoutMs = 300_000): Promise<{ alreadyRunning: boolean; seconds: number; logLine: number }> {
    const existing = this.livePid();
    if (existing) return { alreadyRunning: true, seconds: 0, logLine: 1 };

    const s = this.local();
    const jar = join(this.ws.serverDir, s.paperJar);
    if (!existsSync(jar)) throw new McflowError(`Paper jar ${jar} is missing. Rerun \`mcflow server setup\`.`);
    if (!existsSync(s.java)) throw new McflowError(`Java not found at ${s.java}. Rerun \`mcflow server setup\`.`);

    mkdirSync(this.ws.stateDir, { recursive: true });
    this.consoleTail = [];
    const started = Date.now();
    const child = spawn(s.java, ["-Xms1G", "-Xmx2G", "-jar", s.paperJar, "--nogui"], {
      cwd: this.ws.serverDir,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    this.child = child;
    writeFileSync(pidFile(this.ws), String(child.pid));

    const ready = new Promise<void>((resolve, reject) => {
      const onData = (chunk: Buffer) => {
        for (const line of chunk.toString("utf8").split(/\r?\n/)) {
          if (!line) continue;
          this.consoleTail.push(line);
          if (this.consoleTail.length > 200) this.consoleTail.shift();
          if (READY.test(line)) resolve();
          if (EULA_MISSING.test(line)) {
            reject(new McflowError("The Minecraft EULA isn't accepted. Ask the user, then run `mcflow server setup --accept-eula`."));
          }
        }
      };
      child.stdout?.on("data", onData);
      child.stderr?.on("data", onData);
      child.once("exit", (code) => {
        rmSync(pidFile(this.ws), { force: true });
        reject(new McflowError(`The server exited during startup (code ${code}). Last output:\n${this.consoleTail.slice(-20).join("\n")}`));
      });
    });
    const timeout = sleep(timeoutMs).then(() => {
      throw new McflowError(`The server didn't finish starting within ${timeoutMs / 1000}s.`);
    });

    await Promise.race([ready, timeout]);
    return { alreadyRunning: false, seconds: Math.round((Date.now() - started) / 100) / 10, logLine: 1 };
  }

  async stop(timeoutMs = 60_000): Promise<{ wasRunning: boolean; forced: boolean }> {
    const pid = this.livePid();
    if (!pid) return { wasRunning: false, forced: false };
    const s = this.local();
    try {
      const rcon = await RconClient.connect(s.rconPort, s.rconPassword, 3000);
      await rcon.command("stop").catch(() => undefined); // the connection drops as the server shuts down
      rcon.close();
    } catch {
      this.child?.stdin?.write("stop\n");
    }
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (!isAlive(pid)) {
        rmSync(pidFile(this.ws), { force: true });
        return { wasRunning: true, forced: false };
      }
      await sleep(500);
    }
    process.kill(pid, "SIGKILL");
    rmSync(pidFile(this.ws), { force: true });
    return { wasRunning: true, forced: true };
  }

  async restart(): Promise<{ seconds: number }> {
    await this.stop();
    const { seconds } = await this.start();
    return { seconds };
  }

  /** Problems logged since the server last started (latest.log is rotated at startup). */
  startupProblems() {
    return readLog(join(this.ws.serverDir, "logs", "latest.log")).problems;
  }
}
