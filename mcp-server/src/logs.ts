// Reads server/logs/latest.log and groups lines into entries, flagging exceptions and stack traces.

import { existsSync, readFileSync } from "node:fs";

// Two formats start an entry:
//   logs/latest.log (file):   "[14:15:13] [Server thread/INFO]: ..."
//   console (stdout):         "[14:15:13 INFO]: ..."
const ENTRY_START = /^\[(\d\d:\d\d:\d\d)(?:\s+([A-Z]+))?\](?:\s*\[[^\]]*\/([A-Z]+)\])?/;
const STACK_LINE = /^\s+at |^Caused by: |^\s+\.\.\. \d+ more|^[\w$.]+(?:Exception|Error)(?::|$)/;

export interface LogEntry {
  line: number; // 1-based line where the entry starts
  time: string;
  level: string;
  text: string; // first line plus any continuation lines
  hasStackTrace: boolean;
}

export interface LogRead {
  entries: LogEntry[];
  problems: LogEntry[];
  nextLine: number; // pass back as `sinceLine` to read only what's new
  totalLines: number;
}

export function parseEntries(lines: string[], firstLineNumber = 1): LogEntry[] {
  const entries: LogEntry[] = [];
  lines.forEach((raw, i) => {
    const line = raw.replace(/\r$/, "");
    const match = ENTRY_START.exec(line);
    const last = entries[entries.length - 1];
    if (match && (match[2] ?? match[3])) {
      entries.push({
        line: firstLineNumber + i,
        time: match[1] ?? "",
        level: match[2] ?? match[3] ?? "",
        text: line,
        hasStackTrace: false,
      });
    } else if (last && line.length > 0) {
      last.text += "\n" + line;
      if (STACK_LINE.test(line)) last.hasStackTrace = true;
    }
  });
  return entries;
}

export function isProblem(entry: LogEntry): boolean {
  if (entry.hasStackTrace) return true;
  if (entry.level === "ERROR" || entry.level === "FATAL" || entry.level === "SEVERE") return true;
  return /\bException\b|\bError:/.test(entry.text) && entry.level !== "INFO";
}

export function readLog(path: string, sinceLine = 1, filter?: string): LogRead {
  if (!existsSync(path)) return { entries: [], problems: [], nextLine: 1, totalLines: 0 };
  const all = readFileSync(path, "utf8").split("\n");
  if (all[all.length - 1] === "") all.pop();
  // The server rotates latest.log on start; a cursor past the end means a fresh file.
  const start = sinceLine > all.length + 1 ? 1 : Math.max(1, sinceLine);
  let entries = parseEntries(all.slice(start - 1), start);
  if (filter) {
    const re = new RegExp(filter, "i");
    entries = entries.filter((e) => re.test(e.text));
  }
  return { entries, problems: entries.filter(isProblem), nextLine: all.length + 1, totalLines: all.length };
}
