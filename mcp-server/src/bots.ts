// Test bots (mineflayer) for the local server: join, act, and report what happened to them.

import mineflayer, { type Bot } from "mineflayer";
import { McflowError } from "./workspace.js";

/** A bot's state as the tools report it. Angles use Minecraft's convention (degrees, yaw 0 = south). */
export interface BotStatus {
  name: string;
  online: boolean;
  version: string;
  position?: { x: number; y: number; z: number };
  yaw?: number;
  pitch?: number;
  health?: number;
  food?: number;
  gameMode?: string;
  dimension?: string;
  window?: { id: number; title: string; slots: number };
  lastKick?: string;
  lastError?: string;
}

export interface Managed {
  name: string;
  bot: Bot;
  version: string;
  online: boolean;
  messages: string[];
  lastKick?: string;
  lastError?: string;
}

const MESSAGE_HISTORY = 50;

/** Compares dotted versions numerically ("26.3" > "26.1", "1.21.11" > "1.21.4"). */
export function compareVersions(a: string, b: string): number {
  const pa = a.split(".").map(Number), pb = b.split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (d !== 0) return Math.sign(d);
  }
  return 0;
}

/**
 * The protocol version bots should speak. If mineflayer supports the server's version, use it; if the server is
 * newer, use mineflayer's newest and rely on ViaBackwards on the server to translate.
 */
export function botVersion(serverVersion: string, tested: string[], latest: string): { version: string; translated: boolean } {
  if (tested.includes(serverVersion)) return { version: serverVersion, translated: false };
  if (compareVersions(serverVersion, latest) > 0) return { version: latest, translated: true };
  // Older than the newest but not in the tested list (e.g. 1.21.10): the nearest tested version at or below it.
  const below = tested.filter((v) => compareVersions(v, serverVersion) <= 0).sort(compareVersions);
  const pick = below.at(-1);
  if (!pick) throw new McflowError(`mineflayer can't speak Minecraft ${serverVersion} (oldest supported: ${tested[0]}).`);
  return { version: pick, translated: pick !== serverVersion };
}

type Write = (name: string, params: Record<string, unknown>) => void;

/**
 * Works around two mineflayer 4.39.0 bugs (docs/research/Stage 4 Bots.md):
 * 1. It writes the resource-pack reply's UUID as an object, so the server never receives the reply and holds the
 *    bot in the configuration phase forever. The UUID is sent as a string instead.
 * 2. It never sends tick_end. Since 1.21.2 the server allows one position packet per client tick and kicks for a
 *    second one ("Invalid move player packet"), so a tick_end follows every movement packet.
 */
export function patchClient(client: { write: Write; state: string }): void {
  const write = client.write.bind(client) as Write;
  client.write = (name, params) => {
    if (name === "resource_pack_receive" && params.uuid !== null && typeof params.uuid === "object") {
      params = { ...params, uuid: String(params.uuid) };
    }
    write(name, params);
    if (client.state === "play" && MOVEMENT.has(name)) write("tick_end", {});
  };
}
const MOVEMENT = new Set(["position", "position_look", "look", "flying"]);

/** Minecraft yaw/pitch (degrees) to mineflayer's (radians, its own yaw origin). */
export function toMineflayerAngles(yaw: number, pitch: number): { yaw: number; pitch: number } {
  const twoPi = Math.PI * 2;
  return { yaw: (((Math.PI - (yaw * Math.PI) / 180) % twoPi) + twoPi) % twoPi, pitch: (-pitch * Math.PI) / 180 };
}

/** mineflayer yaw/pitch (radians) to Minecraft's (degrees, yaw in -180..180). */
export function toMinecraftAngles(yaw: number, pitch: number): { yaw: number; pitch: number } {
  let y = ((Math.PI - yaw) * 180) / Math.PI;
  y = ((((y + 180) % 360) + 360) % 360) - 180;
  return { yaw: round(y), pitch: round((-pitch * 180) / Math.PI) };
}

const round = (n: number, places = 2) => Math.round(n * 10 ** places) / 10 ** places;

/** Readable text from a kick reason, which arrives as a string, chat JSON or NBT-shaped JSON. */
export function reasonText(reason: unknown): string {
  if (typeof reason === "string") {
    try {
      return reasonText(JSON.parse(reason));
    } catch {
      return reason;
    }
  }
  // 26.x sends NBT-shaped text: a bare string arrives as {type: "string", value: "..."}.
  if (reason && typeof reason === "object" && "type" in reason && "value" in reason && typeof reason.value === "string") {
    return reason.value;
  }
  const found: string[] = [];
  const walk = (v: unknown) => {
    if (v && typeof v === "object") {
      for (const [k, x] of Object.entries(v)) {
        if ((k === "text" || k === "translate") && typeof x === "string") found.push(x);
        else if ((k === "text" || k === "translate") && x && typeof x === "object" && "value" in x) found.push(String(x.value));
        else walk(x);
      }
    }
  };
  walk(reason);
  return found.join(" ").trim() || JSON.stringify(reason);
}

export class BotManager {
  private readonly bots = new Map<string, Managed>();

  constructor(private readonly target: () => { host: string; port: number; serverVersion: string }) {}

  get(name: string): Managed {
    const m = this.bots.get(name);
    if (!m) throw new McflowError(`No bot named "${name}". Running bots: ${[...this.bots.keys()].join(", ") || "none"}.`);
    if (!m.online) throw new McflowError(`Bot "${name}" isn't connected${m.lastKick ? ` (kicked: ${m.lastKick})` : ""}.`);
    return m;
  }

  /** The bot, connected or not, or undefined if there's none by that name. */
  find(name: string): Managed | undefined {
    return this.bots.get(name);
  }

  names(): string[] {
    return [...this.bots.keys()];
  }

  /** Connects a bot and resolves once it has spawned, or rejects with the reason it didn't. */
  async join(name: string, timeoutMs: number): Promise<{ status: BotStatus; joinMs: number; translated: boolean }> {
    if (!/^[A-Za-z0-9_]{3,16}$/.test(name)) throw new McflowError(`"${name}" isn't a valid Minecraft name (3-16 letters, digits or _).`);
    if (this.bots.get(name)?.online) throw new McflowError(`Bot "${name}" is already connected.`);
    const { host, port, serverVersion } = this.target();
    const { version, translated } = botVersion(serverVersion, mineflayer.testedVersions, mineflayer.latestSupportedVersion);
    const started = Date.now();
    const bot = mineflayer.createBot({ host, port, username: name, version, auth: "offline", hideErrors: true });
    patchClient(bot._client as unknown as { write: Write; state: string });
    if (process.env.MCFLOW_BOT_TRACE) trace(name, bot);
    const m: Managed = { name, bot, version, online: false, messages: [] };
    this.bots.set(name, m);
    bot.on("messagestr", (text) => {
      m.messages.push(text);
      if (m.messages.length > MESSAGE_HISTORY) m.messages.shift();
    });
    bot.on("kicked", (reason) => {
      m.lastKick = reasonText(reason);
    });
    bot.on("error", (err) => {
      m.lastError = err.message;
    });
    bot.on("end", () => {
      m.online = false;
    });

    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => fail(`didn't spawn within ${timeoutMs / 1000} s`), timeoutMs);
      const fail = (why: string) => {
        clearTimeout(timer);
        bot.end();
        reject(new McflowError(`Bot "${name}" couldn't join: ${why}.${translated ? ` (Joined as ${version} through ViaBackwards; is it installed on the server?)` : ""}`));
      };
      bot.once("spawn", () => {
        clearTimeout(timer);
        m.online = true;
        resolve();
      });
      bot.once("kicked", (reason) => fail(`kicked: ${reasonText(reason)}`));
      bot.once("error", (err) => fail(err.message));
      bot.once("end", (reason) => fail(`disconnected (${reason})`));
    });
    return { status: this.status(name), joinMs: Date.now() - started, translated };
  }

  leave(name: string): void {
    const m = this.bots.get(name);
    if (!m) throw new McflowError(`No bot named "${name}".`);
    if (m.online) m.bot.quit();
    this.bots.delete(name);
  }

  leaveAll(): string[] {
    const names = this.names();
    for (const n of names) this.leave(n);
    return names;
  }

  status(name: string): BotStatus {
    const m = this.bots.get(name);
    if (!m) throw new McflowError(`No bot named "${name}".`);
    const { bot } = m;
    const s: BotStatus = { name, online: m.online, version: m.version, lastKick: m.lastKick, lastError: m.lastError };
    if (!m.online || !bot.entity) return s;
    const p = bot.entity.position;
    const angles = toMinecraftAngles(bot.entity.yaw, bot.entity.pitch);
    const window = bot.currentWindow;
    return {
      ...s,
      position: { x: round(p.x), y: round(p.y), z: round(p.z) },
      yaw: angles.yaw,
      pitch: angles.pitch,
      health: bot.health,
      food: bot.food,
      gameMode: bot.game?.gameMode,
      dimension: bot.game?.dimension,
      window: window ? { id: window.id, title: reasonText(window.title), slots: window.slots.length } : undefined,
    };
  }
}

/** MCFLOW_BOT_TRACE=1: log a bot's non-routine packets to stderr (stdout carries MCP messages). */
function trace(name: string, bot: Bot): void {
  const quiet = /^(keep_alive|tick_end|position|position_look|look|flying|ping|pong|bundle_delimiter|.*entity.*|.*chunk.*|.*light.*|.*block_change|block_action|update_time|.*sound.*|player_info|world_event|set_ticking_state|step_tick|particle|map)$/;
  const show = (v: unknown) => JSON.stringify(v, (_k, x) => (typeof x === "bigint" ? String(x) : x))?.slice(0, 200);
  const c = bot._client as unknown as { write: Write; on: (e: string, f: (d: unknown, m: { name: string }) => void) => void };
  const write = c.write.bind(c);
  c.write = (packet, params) => {
    if (!quiet.test(packet)) process.stderr.write(`[bot ${name}] OUT ${packet} ${show(params)}
`);
    write(packet, params);
  };
  c.on("packet", (data, meta) => {
    if (!quiet.test(meta.name)) process.stderr.write(`[bot ${name}] IN  ${meta.name} ${show(data)}
`);
  });
}

/**
 * Whether a block is inside vanilla spawn protection: within `radius` blocks of the world spawn on x and z.
 * Non-operators can't use or change blocks there, so a bot's click does nothing.
 */
export function inSpawnProtection(block: { x: number; z: number }, spawn: { x: number; z: number } | undefined, radius: number): boolean {
  if (!spawn || radius <= 0) return false;
  return Math.max(Math.abs(block.x - spawn.x), Math.abs(block.z - spawn.z)) <= radius;
}
