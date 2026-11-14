// Validates and zips a resource pack from resourcepacks/<name>/, deterministically, and hashes it.

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { unzipSync, zipSync, type Zippable } from "fflate";
import { McflowError, Workspace } from "./workspace.js";

// Fixed timestamp so the same pack contents always produce the same zip, and so the same SHA-1.
const FIXED_MTIME = new Date("2020-01-01T00:00:00Z");

export interface PackIssue {
  file: string;
  problem: string;
}

export interface BuiltPack {
  name: string;
  zipPath: string;
  sha1: string;
  bytes: number;
  files: number;
  packFormat?: unknown;
  expectedPackFormat?: number;
  issues: PackIssue[];
}

function listFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listFiles(full));
    else if (entry.isFile()) out.push(full);
  }
  return out;
}

/**
 * The resource pack format the server's Minecraft version expects, read from the vanilla jar Paper
 * downloads into server/cache/ on first start (its version.json has `pack_version`).
 */
export function expectedPackFormat(ws: Workspace): number | undefined {
  const jar = join(ws.serverDir, "cache", `mojang_${ws.paperVersion}.jar`);
  if (!existsSync(jar)) return undefined;
  const files = unzipSync(readFileSync(jar), { filter: (f) => f.name === "version.json" });
  const raw = files["version.json"];
  if (!raw) return undefined;
  const version = JSON.parse(Buffer.from(raw).toString("utf8")) as { pack_version?: unknown };
  const pv = version.pack_version;
  if (typeof pv === "number") return pv;
  if (pv && typeof pv === "object") {
    const obj = pv as Record<string, unknown>;
    for (const key of ["resource", "resource_major"]) {
      if (typeof obj[key] === "number") return obj[key] as number;
    }
  }
  return undefined;
}

export function validate(dir: string): { issues: PackIssue[]; packFormat?: unknown } {
  const issues: PackIssue[] = [];
  const mcmeta = join(dir, "pack.mcmeta");
  let packFormat: unknown;
  if (!existsSync(mcmeta)) {
    issues.push({ file: "pack.mcmeta", problem: "missing; every resource pack needs one at its root" });
  } else {
    try {
      const meta = JSON.parse(readFileSync(mcmeta, "utf8")) as { pack?: Record<string, unknown> };
      if (!meta.pack || typeof meta.pack !== "object") {
        issues.push({ file: "pack.mcmeta", problem: 'has no "pack" object' });
      } else {
        packFormat = meta.pack.pack_format ?? meta.pack.min_format;
        if (packFormat === undefined) {
          issues.push({ file: "pack.mcmeta", problem: 'no "pack_format" (or "min_format") in "pack"' });
        }
      }
    } catch (e) {
      issues.push({ file: "pack.mcmeta", problem: `invalid JSON: ${(e as Error).message}` });
    }
  }
  for (const file of listFiles(dir)) {
    if (!/\.(json|mcmeta)$/i.test(file) || file === mcmeta) continue;
    try {
      JSON.parse(readFileSync(file, "utf8"));
    } catch (e) {
      issues.push({ file: relative(dir, file).split(sep).join("/"), problem: `invalid JSON: ${(e as Error).message}` });
    }
  }
  return { issues, packFormat };
}

export function buildPack(ws: Workspace, name: string): BuiltPack {
  if (!/^[\w.-]+$/.test(name)) throw new McflowError(`"${name}" isn't a valid pack folder name.`);
  const dir = join(ws.root, "resourcepacks", name);
  if (!existsSync(dir) || !statSync(dir).isDirectory()) {
    throw new McflowError(`No resource pack folder at resourcepacks/${name}/.`);
  }
  const { issues, packFormat } = validate(dir);
  const expected = expectedPackFormat(ws);
  if (expected !== undefined && typeof packFormat === "number" && packFormat !== expected) {
    issues.push({
      file: "pack.mcmeta",
      problem: `pack_format is ${packFormat}, but Minecraft ${ws.paperVersion} expects ${expected}`,
    });
  }

  const files = listFiles(dir).sort();
  const tree: Zippable = {};
  for (const file of files) {
    const rel = relative(dir, file).split(sep).join("/");
    tree[rel] = [readFileSync(file), { mtime: FIXED_MTIME }];
  }
  const zip = zipSync(tree, { level: 6 });
  const outDir = join(ws.stateDir, "packs");
  mkdirSync(outDir, { recursive: true });
  const zipPath = join(outDir, `${name}.zip`);
  writeFileSync(zipPath, zip);

  return {
    name,
    zipPath,
    sha1: createHash("sha1").update(zip).digest("hex"),
    bytes: zip.length,
    files: files.length,
    packFormat,
    expectedPackFormat: expected,
    issues,
  };
}
