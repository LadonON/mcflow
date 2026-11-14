import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseEntries, readLog } from "../src/logs.js";

const SAMPLE = [
  "[12:00:01 INFO]: Starting minecraft server version 1.21.11",
  "[12:00:05 INFO]: [ShinySwords] Enabling ShinySwords v1.0",
  "[12:00:05 ERROR]: Error occurred while enabling ShinySwords v1.0 (Is it up to date?)",
  "java.lang.NullPointerException: Cannot invoke \"String.length()\" because \"name\" is null",
  "\tat com.example.shiny.Shiny.onEnable(Shiny.java:42) ~[ShinySwords.jar:?]",
  "\tat org.bukkit.plugin.java.JavaPlugin.setEnabled(JavaPlugin.java:288) ~[paper-api.jar:?]",
  "[12:00:06 WARN]: Can't keep up! Is the server overloaded?",
  "[12:00:07 INFO]: Done (6.123s)! For help, type \"help\"",
];

describe("parseEntries", () => {
  it("groups stack traces with the line that logged them", () => {
    const entries = parseEntries(SAMPLE);
    expect(entries).toHaveLength(5);
    const error = entries[2]!;
    expect(error.level).toBe("ERROR");
    expect(error.hasStackTrace).toBe(true);
    expect(error.text).toContain("Shiny.java:42");
  });

  it("understands thread-prefixed levels", () => {
    const [entry] = parseEntries(["[12:00:01 Server thread/WARN]: something"]);
    expect(entry?.level).toBe("WARN");
  });
});

describe("readLog", () => {
  const dir = mkdtempSync(join(tmpdir(), "mcflow-logs-"));
  const path = join(dir, "latest.log");
  writeFileSync(path, SAMPLE.join("\n") + "\n");

  it("flags exceptions but not ordinary warnings", () => {
    const log = readLog(path);
    expect(log.problems).toHaveLength(1);
    expect(log.problems[0]?.text).toContain("NullPointerException");
    expect(log.nextLine).toBe(SAMPLE.length + 1);
  });

  it("reads only new lines from a cursor", () => {
    const log = readLog(path, 7);
    expect(log.entries.map((e) => e.level)).toEqual(["WARN", "INFO"]);
  });

  it("restarts from the top when the log was rotated", () => {
    expect(readLog(path, 500).entries).toHaveLength(5);
  });

  it("filters by regex", () => {
    expect(readLog(path, 1, "shiny").entries).toHaveLength(2);
  });

  it("returns nothing for a missing log", () => {
    expect(readLog(join(dir, "nope.log")).entries).toEqual([]);
  });
});
