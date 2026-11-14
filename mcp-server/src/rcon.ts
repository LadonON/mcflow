// Minimal Source RCON client, which is the protocol Minecraft speaks on rcon.port.
// Packet: int32 length | int32 id | int32 type | body (UTF-8) | 0x00 0x00, all little-endian.

import { Socket, connect } from "node:net";

const TYPE_AUTH = 3;
const TYPE_COMMAND = 2;
const AUTH_FAILED_ID = -1;

interface Packet {
  id: number;
  type: number;
  body: string;
}

export function encode(id: number, type: number, body: string): Buffer {
  const payload = Buffer.from(body, "utf8");
  const packet = Buffer.alloc(14 + payload.length);
  packet.writeInt32LE(10 + payload.length, 0);
  packet.writeInt32LE(id, 4);
  packet.writeInt32LE(type, 8);
  payload.copy(packet, 12);
  return packet; // the trailing two bytes are already zero
}

/** Pull complete packets off the front of `buffer`; returns them plus the unread remainder. */
export function decode(buffer: Buffer): { packets: Packet[]; rest: Buffer } {
  const packets: Packet[] = [];
  let offset = 0;
  while (buffer.length - offset >= 4) {
    const length = buffer.readInt32LE(offset);
    if (buffer.length - offset - 4 < length) break;
    const start = offset + 4;
    packets.push({
      id: buffer.readInt32LE(start),
      type: buffer.readInt32LE(start + 4),
      body: buffer.toString("utf8", start + 8, start + length - 2),
    });
    offset = start + length;
  }
  return { packets, rest: buffer.subarray(offset) };
}

export class RconError extends Error {}

export class RconClient {
  private buffer: Buffer = Buffer.alloc(0);
  private waiters: ((p: Packet) => void)[] = [];
  private nextId = 1;

  private constructor(private readonly socket: Socket) {
    socket.on("data", (chunk: Buffer) => {
      const { packets, rest } = decode(Buffer.concat([this.buffer, chunk]));
      this.buffer = rest;
      for (const p of packets) this.waiters.shift()?.(p);
    });
  }

  static async connect(port: number, password: string, timeoutMs = 5000): Promise<RconClient> {
    const socket = await new Promise<Socket>((resolve, reject) => {
      const s = connect({ host: "127.0.0.1", port });
      const timer = setTimeout(() => {
        s.destroy();
        reject(new RconError(`RCON on port ${port} didn't answer within ${timeoutMs} ms.`));
      }, timeoutMs);
      s.once("connect", () => {
        clearTimeout(timer);
        resolve(s);
      });
      s.once("error", (e) => {
        clearTimeout(timer);
        reject(new RconError(`Can't reach RCON on port ${port}: ${e.message}`));
      });
    });
    const client = new RconClient(socket);
    const reply = await client.send(TYPE_AUTH, password, timeoutMs);
    if (reply.id === AUTH_FAILED_ID) {
      client.close();
      throw new RconError("RCON rejected the password in .mcflow/local.toml. Rerun `mcflow server setup`.");
    }
    return client;
  }

  private send(type: number, body: string, timeoutMs: number): Promise<Packet> {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new RconError(`No RCON reply within ${timeoutMs} ms.`)), timeoutMs);
      this.waiters.push((p) => {
        clearTimeout(timer);
        resolve(p);
      });
      this.socket.write(encode(id, type, body));
    });
  }

  async command(command: string, timeoutMs = 10000): Promise<string> {
    const reply = await this.send(TYPE_COMMAND, command.replace(/^\//, ""), timeoutMs);
    return reply.body;
  }

  close(): void {
    this.socket.destroy();
  }
}

export async function runCommand(port: number, password: string, command: string): Promise<string> {
  const client = await RconClient.connect(port, password);
  try {
    return await client.command(command);
  } finally {
    client.close();
  }
}
