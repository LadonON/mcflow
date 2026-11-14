// Builds a plugin with Gradle and copies the jar into server/plugins/.

import { spawn } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { McflowError, Workspace } from "./workspace.js";

const NOT_THE_PLUGIN = /-(sources|javadoc|plain|dev|dev-all)\.jar$/;

export interface BuildResult {
  jar: string;
  deployedAs: string;
  seconds: number;
  outputTail: string;
}

export function pickJar(names: string[]): string {
  const candidates = names.filter((n) => n.endsWith(".jar") && !NOT_THE_PLUGIN.test(n));
  if (candidates.length === 1) return candidates[0]!;
  const shaded = candidates.filter((n) => n.endsWith("-all.jar"));
  if (shaded.length === 1) return shaded[0]!;
  throw new McflowError(
    candidates.length === 0
      ? "The build produced no plugin jar in build/libs/."
      : `Can't tell which jar is the plugin: ${candidates.join(", ")}.`,
  );
}

function run(cmd: string, args: string[], cwd: string, env: NodeJS.ProcessEnv, timeoutMs: number) {
  return new Promise<{ code: number | null; output: string }>((resolve) => {
    const child = spawn(cmd, args, { cwd, env, shell: process.platform === "win32", windowsHide: true });
    let output = "";
    const collect = (b: Buffer) => {
      output += b.toString("utf8");
      if (output.length > 200_000) output = output.slice(-100_000);
    };
    child.stdout.on("data", collect);
    child.stderr.on("data", collect);
    const timer = setTimeout(() => child.kill(), timeoutMs);
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({ code, output });
    });
  });
}

export async function buildPlugin(ws: Workspace, project: string, java: string): Promise<BuildResult> {
  if (!/^[\w.-]+$/.test(project)) throw new McflowError(`"${project}" isn't a valid project folder name.`);
  const dir = join(ws.root, "plugins", project);
  if (!existsSync(dir)) throw new McflowError(`No plugin project at plugins/${project}/.`);

  const wrapper = join(dir, process.platform === "win32" ? "gradlew.bat" : "gradlew");
  const cmd = existsSync(wrapper) ? wrapper : "gradle";
  // Build with the same JDK that runs the server unless the project's toolchain says otherwise.
  const env = { ...process.env, JAVA_HOME: dirname(dirname(java)) };

  const started = Date.now();
  const { code, output } = await run(cmd, ["build", "--console=plain"], dir, env, 10 * 60_000);
  const tail = output.split(/\r?\n/).slice(-60).join("\n");
  if (code !== 0) throw new McflowError(`Gradle build failed (exit ${code}):\n${tail}`);

  const libs = join(dir, "build", "libs");
  const jar = pickJar(existsSync(libs) ? readdirSync(libs) : []);
  const pluginsDir = join(ws.serverDir, "plugins");
  mkdirSync(pluginsDir, { recursive: true });
  const deployedAs = join(pluginsDir, `${project}.jar`);
  copyFileSync(join(libs, jar), deployedAs);

  return { jar, deployedAs, seconds: Math.round((Date.now() - started) / 100) / 10, outputTail: tail };
}
