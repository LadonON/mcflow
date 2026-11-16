// Resource-pack gate: every file a pack references exists, and font providers obey the rules the game enforces.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { unzipSync } from "fflate";

export interface PackIssue {
  file: string;
  problem: string;
}

export interface PackCheck {
  issues: PackIssue[];
  checked: { fonts: number; models: number; itemDefinitions: number; blockstates: number; references: number };
  /** minecraft: references that couldn't be checked because no client jar was found. */
  unverifiedVanilla: number;
}

function walk(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

/** Width and height from a PNG's IHDR chunk, or undefined if it isn't a PNG. */
export function pngSize(bytes: Uint8Array): { width: number; height: number } | undefined {
  const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  if (bytes.length < 24 || sig.some((b, i) => bytes[i] !== b)) return undefined;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return { width: view.getUint32(16), height: view.getUint32(20) };
}

/** "ns:path" (or "path", meaning minecraft:) → [namespace, path]. */
function splitId(id: string): [string, string] {
  const i = id.indexOf(":");
  return i === -1 ? ["minecraft", id] : [id.slice(0, i), id.slice(i + 1)];
}

/** Asset names inside a client jar ("assets/minecraft/textures/…"), for checking minecraft: references. */
export function listJarAssets(jarPath: string): Set<string> {
  const names = new Set<string>();
  unzipSync(readFileSync(jarPath), {
    filter: (f) => {
      if (f.name.startsWith("assets/")) names.add(f.name);
      return false; // list only; don't inflate anything
    },
  });
  return names;
}

/**
 * Checks a pack folder. `vanilla` is the client jar's asset list; without it, minecraft: references that the pack
 * doesn't override are counted as unverified instead of checked.
 */
export function checkPack(dir: string, vanilla?: Set<string>): PackCheck {
  const issues: PackIssue[] = [];
  const checked = { fonts: 0, models: 0, itemDefinitions: 0, blockstates: 0, references: 0 };
  let unverifiedVanilla = 0;
  const rel = (p: string) => relative(dir, p).split(sep).join("/");
  const read = (p: string): unknown => {
    try {
      return JSON.parse(readFileSync(p, "utf8"));
    } catch {
      return undefined; // invalid JSON is reported by validate()
    }
  };

  /** Does assets/<ns>/<kind>/<path><ext> exist in the pack, or in vanilla? */
  const exists = (from: string, id: string, kind: string, ext: string, what: string): boolean => {
    checked.references++;
    const [ns, path] = splitId(id);
    const asset = `assets/${ns}/${kind}/${path}${ext}`;
    if (existsSync(join(dir, ...asset.split("/")))) return true;
    if (ns === "minecraft") {
      if (!vanilla) {
        unverifiedVanilla++;
        return true;
      }
      if (vanilla.has(asset)) return true;
    }
    issues.push({ file: from, problem: `${what} "${id}" not found (expected ${asset})` });
    return false;
  };

  const assets = join(dir, "assets");
  const namespaces = existsSync(assets) ? readdirSync(assets).filter((n) => statSync(join(assets, n)).isDirectory()) : [];
  for (const ns of namespaces) {
    for (const file of walk(join(assets, ns, "font")).filter((f) => f.endsWith(".json"))) {
      checked.fonts++;
      const font = read(file) as { providers?: Record<string, unknown>[] } | undefined;
      for (const [i, p] of (font?.providers ?? []).entries()) {
        const where = `${rel(file)} provider ${i}`;
        if (p.type === "bitmap" && typeof p.file === "string") {
          const height = typeof p.height === "number" ? p.height : 8;
          const ascent = Number(p.ascent);
          if (ascent > height) {
            issues.push({ file: where, problem: `ascent ${ascent} is greater than height ${height}; the game rejects the provider and draws missing-glyph boxes` });
          }
          const rows = Array.isArray(p.chars) ? (p.chars as string[]) : [];
          const widths = new Set(rows.map((r) => [...r].length));
          if (rows.length === 0) issues.push({ file: where, problem: "no chars" });
          if (widths.size > 1) issues.push({ file: where, problem: `chars rows have different lengths (${[...widths].join(", ")})` });
          if (exists(where, p.file, "textures", "", "texture")) {
            const [tns, tpath] = splitId(p.file);
            const png = join(dir, "assets", tns, "textures", ...tpath.split("/"));
            const size = existsSync(png) ? pngSize(readFileSync(png)) : undefined;
            const cols = [...widths][0] ?? 0;
            if (size && rows.length && cols && (size.width % cols !== 0 || size.height % rows.length !== 0)) {
              issues.push({ file: where, problem: `texture ${size.width}x${size.height} doesn't divide into ${cols}x${rows.length} glyph cells` });
            }
          }
        } else if (p.type === "reference" && typeof p.id === "string") {
          exists(where, p.id, "font", ".json", "font");
        } else if ((p.type === "ttf" || p.type === "unihex") && typeof p.file === "string") {
          checked.references++; // ttf/unihex paths are full file names under the namespace
          const [fns, fpath] = splitId(p.file);
          if (!existsSync(join(dir, "assets", fns, ...fpath.split("/"))) && fns !== "minecraft") {
            issues.push({ file: where, problem: `font file "${p.file}" not found` });
          }
        }
      }
    }

    for (const file of walk(join(assets, ns, "models")).filter((f) => f.endsWith(".json"))) {
      checked.models++;
      const model = read(file) as { parent?: unknown; textures?: Record<string, unknown> } | undefined;
      if (typeof model?.parent === "string" && !model.parent.startsWith("builtin/")) exists(rel(file), model.parent, "models", ".json", "parent model");
      for (const [key, t] of Object.entries(model?.textures ?? {})) {
        if (typeof t === "string" && !t.startsWith("#")) exists(rel(file), t, "textures", ".png", `texture "${key}"`);
      }
    }

    // 1.21.4+ item definitions and blockstates: every "model" string names a model.
    const modelRefs = (v: unknown, from: string) => {
      if (Array.isArray(v)) v.forEach((x) => modelRefs(x, from));
      else if (v && typeof v === "object") {
        for (const [k, x] of Object.entries(v)) {
          if (k === "model" && typeof x === "string") exists(from, x, "models", ".json", "model");
          else modelRefs(x, from);
        }
      }
    };
    for (const file of walk(join(assets, ns, "items")).filter((f) => f.endsWith(".json"))) {
      checked.itemDefinitions++;
      modelRefs(read(file), rel(file));
    }
    for (const file of walk(join(assets, ns, "blockstates")).filter((f) => f.endsWith(".json"))) {
      checked.blockstates++;
      modelRefs(read(file), rel(file));
    }
  }
  return { issues, checked, unverifiedVanilla };
}
