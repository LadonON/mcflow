---
name: verify
description: Prove a change works before it's presented - build, unit tests, deploy, logs, in-game checks with the real client and the verifier agents, then the performance, memory, thread-safety and resource-pack gates. Use at step 4 (and again, shorter, at step 6) of every development task, or whenever asked to test or check a plugin or pack.
---

# Verify

A change is done only when every applicable step passes. Run them in order: a failure early makes later results meaningless. Fix the failure, then restart from the build.

## 1. Build and unit tests

- `plugin_deploy` builds with the project's Gradle wrapper. Treat new compiler warnings as failures unless you can say why they're harmless.
- Run the tests (`gradlew test`). Read the test report's **stderr** too: exceptions inside event handlers are logged, not thrown, so a green count can hide them.

## 2. Resource pack (if the task touched one)

- `gate_resource_pack <pack>`: pack format, JSON, every texture, model and font reference, and the bitmap-font rules (an ascent above the height draws missing-glyph boxes). Must pass.
- `resourcepack_build_and_serve <pack>` to serve it.

## 3. Deploy and logs

- `plugin_deploy <project>` restarts the server (never `/reload`). Its report includes exceptions logged on restart: there must be none.
- `server_logs` with a filter on the plugin's name and on `Exception|ERROR` after each in-game step.

## 4. In game

- `client_launch`, then `client_join` (sets a fixed window size so screenshots compare).
- Run the feature as a player with `client_run`; save `client_screenshot` images under the task's name.
- Give the screenshots and the approved layout (`layouts/`) to the **verifier-visual** agent, and the command output and log excerpts to the **verifier-output** agent. Both return pass or fail with specific defects. Fix every defect they report.
- Interactions the client can't perform (key presses, clicks) are done by bots (`bot_join`, `bot_chat`, `bot_move`, `bot_use_item`, `bot_click_window_slot`), or by asking the user to try them. Say which ones weren't verified.
- Blocks within the server's spawn protection can't be used by non-operator bots; test further from spawn.

## 5. Gates under load

| Gate | Tool | Passes when |
|---|---|---|
| Performance | `gate_performance` (baseline the first time, compare after) | p95 of 5-second average tick times ≤ 50 ms, and no median regression over the baseline |
| Memory | `gate_memory <project>` | no plugin class, listener registration or scheduled task grows over join/use/leave cycles |
| Thread safety | `gate_thread_safety <project>` (after a load run) | no Bukkit calls off the main thread in the source scan or the server log |

- Use the same scenario (bot count, behavior, duration) as the baseline, or the comparison is meaningless.
- **spark stays local.** The gates only use local spark commands. Never run `spark health` (it always uploads to spark.lucko.me), a profile with `--timeout`, or `profiler stop` without `--save-to-file`.

## 6. Report

For each step: passed, failed (with the defect), or not run (with why). Include tick times (idle, under load, against the baseline), the memory gate's table, and the screenshots. Don't call anything done that has a failed or skipped step without saying so.

The quick re-verify after humanizing (pipeline step 6) is steps 1, 3 and one in-game check from step 4.
