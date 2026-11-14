// Update server.properties in place, keeping comments, order and keys we don't manage.

import { existsSync, readFileSync, writeFileSync } from "node:fs";

export function updateProperties(path: string, changes: Record<string, string>): void {
  const lines = existsSync(path) ? readFileSync(path, "utf8").split(/\r?\n/) : [];
  if (lines[lines.length - 1] === "") lines.pop();
  const remaining = new Map(Object.entries(changes));
  const out = lines.map((line) => {
    const trimmed = line.trimStart();
    if (trimmed.startsWith("#") || trimmed.startsWith("!") || !line.includes("=")) return line;
    const key = line.slice(0, line.indexOf("=")).trim();
    if (!remaining.has(key)) return line;
    const value = remaining.get(key)!;
    remaining.delete(key);
    return `${key}=${escape(value)}`;
  });
  for (const [key, value] of remaining) out.push(`${key}=${escape(value)}`);
  writeFileSync(path, out.join("\n") + "\n", "utf8");
}

export function readProperties(path: string): Record<string, string> {
  const result: Record<string, string> = {};
  if (!existsSync(path)) return result;
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("!") || !trimmed.includes("=")) continue;
    const i = trimmed.indexOf("=");
    result[trimmed.slice(0, i).trim()] = trimmed.slice(i + 1).trim().replace(/\\(.)/g, "$1");
  }
  return result;
}

// Java .properties escaping, matching how Minecraft writes the file (and src/mcflow/testserver/properties.py).
function escape(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/:/g, "\\:").replace(/=/g, "\\=");
}
