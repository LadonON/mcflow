import { createServer, Server } from "node:net";
import { afterEach, describe, expect, it } from "vitest";
import { decode, encode, RconClient, RconError } from "../src/rcon.js";

describe("packet framing", () => {
  it("round-trips a packet", () => {
    const { packets, rest } = decode(encode(7, 2, "list"));
    expect(packets).toEqual([{ id: 7, type: 2, body: "list" }]);
    expect(rest.length).toBe(0);
  });

  it("waits for a packet split across chunks", () => {
    const whole = encode(1, 0, "There are 0 of a max of 20 players online");
    const first = decode(whole.subarray(0, 9));
    expect(first.packets).toEqual([]);
    const second = decode(Buffer.concat([first.rest, whole.subarray(9)]));
    expect(second.packets[0]?.body).toContain("0 of a max");
  });

  it("handles UTF-8 bodies", () => {
    expect(decode(encode(1, 0, "§aGrüße")).packets[0]?.body).toBe("§aGrüße");
  });
});

/** A tiny RCON server that behaves like Minecraft's for auth and one command. */
function fakeMinecraft(password: string): Promise<{ server: Server; port: number }> {
  return new Promise((resolve) => {
    const server = createServer((socket) => {
      let buffer = Buffer.alloc(0);
      socket.on("data", (chunk) => {
        const { packets, rest } = decode(Buffer.concat([buffer, chunk]));
        buffer = rest;
        for (const p of packets) {
          if (p.type === 3) socket.write(encode(p.body === password ? p.id : -1, 2, ""));
          else socket.write(encode(p.id, 0, p.body === "list" ? "There are 1 of a max of 20 players online: Steve" : ""));
        }
      });
    });
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      resolve({ server, port: typeof address === "object" && address ? address.port : 0 });
    });
  });
}

describe("RconClient", () => {
  let server: Server | undefined;
  afterEach(() => server?.close());

  it("authenticates and runs a command, stripping a leading slash", async () => {
    const fake = await fakeMinecraft("hunter2");
    server = fake.server;
    const client = await RconClient.connect(fake.port, "hunter2");
    expect(await client.command("/list")).toContain("Steve");
    client.close();
  });

  it("reports a wrong password clearly", async () => {
    const fake = await fakeMinecraft("hunter2");
    server = fake.server;
    await expect(RconClient.connect(fake.port, "wrong")).rejects.toThrow(/rejected the password/);
  });

  it("reports an unreachable server", async () => {
    await expect(RconClient.connect(1, "x", 1000)).rejects.toBeInstanceOf(RconError);
  });
});
