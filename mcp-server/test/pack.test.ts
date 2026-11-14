import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { unzipSync, zipSync } from "fflate";
import { describe, expect, it } from "vitest";
import { buildPack, expectedPackFormat, validate } from "../src/pack.js";
import { pickJar } from "../src/deploy.js";
import { readProperties, updateProperties } from "../src/properties.js";
import type { Workspace } from "../src/workspace.js";

function workspace(): Workspace {
  const root = mkdtempSync(join(tmpdir(), "mcflow-ws-"));
  return {
    root,
    serverDir: join(root, "server"),
    stateDir: join(root, ".mcflow"),
    paperVersion: "1.21.11",
    javaMinimum: 21,
  };
}

function writePack(ws: Workspace, name: string, files: Record<string, string>) {
  for (const [rel, content] of Object.entries(files)) {
    const path = join(ws.root, "resourcepacks", name, rel);
    mkdirSync(join(path, ".."), { recursive: true });
    writeFileSync(path, content);
  }
}

const GOOD = {
  "pack.mcmeta": JSON.stringify({ pack: { pack_format: 99, description: "test" } }),
  "assets/shiny/models/item/sword.json": JSON.stringify({ parent: "item/handheld" }),
  "assets/shiny/textures/item/sword.png": "png bytes",
};

describe("resource pack build", () => {
  it("zips deterministically and reports the zip's SHA-1", () => {
    const ws = workspace();
    writePack(ws, "shiny", GOOD);
    const first = buildPack(ws, "shiny");
    const second = buildPack(ws, "shiny");
    expect(first.sha1).toBe(second.sha1);
    expect(first.sha1).toBe(createHash("sha1").update(readFileSync(first.zipPath)).digest("hex"));
    expect(Object.keys(unzipSync(readFileSync(first.zipPath))).sort()).toEqual(Object.keys(GOOD).sort());
    expect(first.issues).toEqual([]);
  });

  it("changes hash when content changes", () => {
    const ws = workspace();
    writePack(ws, "shiny", GOOD);
    const before = buildPack(ws, "shiny").sha1;
    writePack(ws, "shiny", { "assets/shiny/textures/item/sword.png": "new bytes" });
    expect(buildPack(ws, "shiny").sha1).not.toBe(before);
  });

  it("reports a missing pack.mcmeta and broken JSON", () => {
    const ws = workspace();
    writePack(ws, "broken", { "assets/x/models/item/a.json": "{ nope" });
    const issues = validate(join(ws.root, "resourcepacks", "broken")).issues;
    expect(issues.map((i) => i.file)).toEqual(["pack.mcmeta", "assets/x/models/item/a.json"]);
  });

  it("compares pack_format with the server's vanilla jar once it exists", () => {
    const ws = workspace();
    writePack(ws, "shiny", GOOD);
    mkdirSync(join(ws.serverDir, "cache"), { recursive: true });
    const versionJson = JSON.stringify({ id: "1.21.11", pack_version: { resource: 75, data: 94 } });
    writeFileSync(join(ws.serverDir, "cache", "mojang_1.21.11.jar"), zipSync({ "version.json": Buffer.from(versionJson) }));
    expect(expectedPackFormat(ws)).toBe(75);
    const built = buildPack(ws, "shiny");
    expect(built.issues).toEqual([{ file: "pack.mcmeta", problem: "pack_format is 99, but Minecraft 1.21.11 expects 75" }]);
  });

  it("refuses path tricks in the pack name", () => {
    expect(() => buildPack(workspace(), "../etc")).toThrow(/isn't a valid pack folder name/);
  });
});

describe("server.properties", () => {
  it("updates in place and round-trips Minecraft-escaped URLs", () => {
    const dir = mkdtempSync(join(tmpdir(), "mcflow-props-"));
    const path = join(dir, "server.properties");
    writeFileSync(path, "#Minecraft server properties\nmotd=Hi\nresource-pack=\n");
    updateProperties(path, { "resource-pack": "http://127.0.0.1:8765/p.zip?sha1=ab", "resource-pack-sha1": "ab" });
    expect(readFileSync(path, "utf8")).toBe(
      "#Minecraft server properties\nmotd=Hi\nresource-pack=http\\://127.0.0.1\\:8765/p.zip?sha1\\=ab\nresource-pack-sha1=ab\n",
    );
    expect(readProperties(path)["resource-pack"]).toBe("http://127.0.0.1:8765/p.zip?sha1=ab");
  });
});

describe("pickJar", () => {
  it("ignores sources, javadoc and dev jars", () => {
    expect(pickJar(["shiny-1.0.jar", "shiny-1.0-sources.jar", "shiny-1.0-javadoc.jar"])).toBe("shiny-1.0.jar");
  });
  it("prefers the shaded jar when there are two", () => {
    expect(pickJar(["shiny-1.0.jar", "shiny-1.0-all.jar"])).toBe("shiny-1.0-all.jar");
  });
  it("explains ambiguity", () => {
    expect(() => pickJar(["a.jar", "b.jar"])).toThrow(/Can't tell which jar/);
  });
});
