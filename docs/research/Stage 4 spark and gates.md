# Stage 4: spark, tick times and the gates' measurements

Task 4.4. Written 2026-11-15, on `mcflow-demo`'s Paper 26.3 (build 251) test server, Windows 11, JDK 25.0.2.

## spark is built into Paper

Paper 26.3 bundles spark 1.10.191 (`server/libraries/me/lucko/spark-paper/`); no plugin to install. Its config is in `server/plugins/spark/config.json` (`backgroundProfiler: true`). On Windows the async-profiler engine isn't supported, so spark uses its built-in Java sampler (less detailed, still usable).

## Uploads: what's safe and what isn't

**spark uploads to spark.lucko.me by default, and some commands always upload.** mcflow must never send a user's server data to a third party without asking, so the gates use only local-only commands.

| Command | Where the result goes |
|---|---|
| `spark profiler start` (no `--timeout`) then `spark profiler stop --save-to-file` | **local**: `plugins/spark/*.sparkprofile` |
| `spark heapsummary --save-to-file` | **local**: `plugins/spark/heapsummary-*.sparkheap` |
| `spark profiler start --timeout N` | **uploads** when the timer ends |
| `spark profiler stop` (without `--save-to-file`) | **uploads** |
| `spark health` | **always uploads** (there's no local form) |
| `spark heapsummary` (without `--save-to-file`) | **uploads** |

spark logs every upload or save in `plugins/spark/activity.json` (type `url` or `file`). That's how this was checked.

**Incident (2026-11-15):** while researching this, `spark health` was run once on the test server and uploaded a health report (`https://spark.lucko.me/fiDd164jJI`, recorded in `activity.json`). The user was told. It can't be deleted from here; spark's paste service expires uploads. The rule above came out of it.

## Tick times (MSPT)

- **Paper's `mspt` replies over RCON:** `Server tick times (avg/min/max) from last 5s, 10s, 1m:` followed by three `avg/min/max` triples. This is what the performance gate samples, every 5 s.
- **`spark tps` replies asynchronously** to the command sender. Over RCON the connection has already closed, so nothing arrives, not even in the log. It's not usable for automation.
- `tps` (Paper) gives 1m/5m/15m TPS; `bot_swarm` already reports it.

## Heap and object counts

- `jcmd <pid> GC.class_histogram` (from the JDK that runs the server, `local.toml`'s `java` with `jcmd` beside it) forces a full GC and lists instances per class. On the idle server it showed `dev.mcflow.menu.MenuPlugin` ×1, `org.bukkit.plugin.RegisteredListener` ×16 and `org.bukkit.craftbukkit.scheduler.CraftTask` ×4, so it can see a plugin's own objects, its listeners and its scheduled tasks.
- `jcmd <pid> GC.heap_info` gives the used heap.
- Both are local, need no plugin, and work while the server runs. The server's PID is in `.mcflow/server.pid`.

## Consequences for the gates

- **Performance (4.5):** sample `mspt` while a bot swarm runs the feature, then compare with a saved baseline and an absolute limit. Optionally save a spark profile locally for the slow case.
- **Memory (4.6):** class histograms at three points (after a warm-up, after N join/use/leave cycles, after 2N). A count of plugin objects, listeners or tasks that keeps growing with the cycles, or with no bots online, is a leak.
- **Thread safety (4.7):** Paper's async catcher logs or throws ("Asynchronous … !") when some Bukkit calls happen off the main thread. Scan the server log from the load run, plus a static scan of the plugin's source.

## The gates on the /menu slice (task 4.9, 2026-11-15)

`scripts/gates-live.mjs` ran the slice (`mcflow-demo/plugins/menu`, `resourcepacks/menu`) through every gate on the live server: **6/6 passed**.

| Gate | Result |
|---|---|
| Resource pack | 7 fonts, 228 references, all present; `minecraft:` references checked against the 26.3 client jar; no font-rule problems |
| Performance (baseline run) | 10 bots, 60 s, 130 `/menu` opens and closes, 1757 head turns. Idle median 1.1 ms; under load median 5.8 ms, p95 15.3 ms, one 137.8 ms tick (the joins). A spark profile was saved locally |
| Performance (compared) | Same scenario: median 5.2 ms, p95 8.7 ms, −0.6 ms (−10%) against the baseline |
| Memory | 7 cycles of 5 bots. `MenuPlugin` 1/1/1, `CraftTask` 4/4/4, `RegisteredListener` 16/16/16, no `MenuSession` left with no bots online; heap 354/354/355 MB. No leaks |
| Thread safety | 5 source files, no findings (the click hook only hands off to the main thread); 1490 log lines, no async catches |
| No uploads | `plugins/spark/activity.json` gained no `url` entries |

The gates' failure paths are covered by unit tests (`test/gates.test.ts`): a growing class at both steps, a regression above the threshold, an absolute tick-time breach, an async `teleport` and a Netty `setGameMode`, and the Stage 3 font bug (ascent above height), missing textures, models and fonts, uneven `chars` rows and a texture that doesn't fit its grid. None of them was triggered live, because the slice has none of these problems.
