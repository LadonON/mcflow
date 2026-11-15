import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { gradleCommand } from "../src/deploy.js";

describe("gradleCommand", () => {
  const dir = join("C:\\Users\\Some One", "plugins", "menu");

  it("quotes the Windows wrapper, whose path may contain spaces", () => {
    expect(gradleCommand(dir, "win32", () => true)).toBe(`"${join(dir, "gradlew.bat")}"`);
  });

  it("uses the plain wrapper path elsewhere (spawned without a shell)", () => {
    expect(gradleCommand(dir, "linux", () => true)).toBe(join(dir, "gradlew"));
  });

  it("falls back to gradle on PATH without a wrapper", () => {
    expect(gradleCommand(dir, "win32", () => false)).toBe("gradle");
  });

  // Regression: the user's home folder has spaces, and cmd.exe ran "C:\Users\Some" as the command.
  it.runIf(process.platform === "win32")("runs a wrapper inside a folder with spaces through cmd.exe", () => {
    const root = join(mkdtempSync(join(tmpdir(), "mcflow-")), "folder with spaces");
    mkdirSync(root);
    writeFileSync(join(root, "gradlew.bat"), "@echo wrapper ran %1\r\n");
    const cmd = gradleCommand(root, "win32", () => true);
    const r = spawnSync(cmd, ["build", "--console=plain"], { cwd: root, shell: true, encoding: "utf8" });
    expect(r.status).toBe(0);
    expect(r.stdout).toContain("wrapper ran build");
  });
});
