// Serves built packs from .mcflow/packs/ over HTTP on 127.0.0.1 so the client can download them.

import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer, Server } from "node:http";
import { join } from "node:path";

export class PackServer {
  private server?: Server;

  constructor(
    private readonly packsDir: string,
    private readonly port: number,
  ) {}

  url(name: string, sha1: string): string {
    // The query string changes with every build, so the client never reuses a stale download.
    return `http://127.0.0.1:${this.port}/${encodeURIComponent(name)}.zip?sha1=${sha1}`;
  }

  async ensureRunning(): Promise<void> {
    if (this.server) return;
    const server = createServer((req, res) => {
      const name = decodeURIComponent((req.url ?? "/").split("?")[0]!.slice(1));
      const file = join(this.packsDir, name);
      if (!/^[\w.-]+\.zip$/.test(name) || !existsSync(file)) {
        res.writeHead(404).end("not found");
        return;
      }
      res.writeHead(200, { "Content-Type": "application/zip", "Content-Length": statSync(file).size });
      createReadStream(file).pipe(res);
    });
    await new Promise<void>((resolve, reject) => {
      server.once("error", reject);
      server.listen(this.port, "127.0.0.1", () => resolve());
    });
    this.server = server;
  }

  close(): void {
    this.server?.close();
    this.server = undefined;
  }
}
