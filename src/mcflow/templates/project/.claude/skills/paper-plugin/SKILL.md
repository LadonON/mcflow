---
name: paper-plugin
description: Build, structure and test Paper server plugins in plugins/<name>/ - Gradle setup, plugin.yml, commands, listeners, schedulers and thread safety, configs, persistence, per-player state, MockBukkit tests and deploying to the test server. Use whenever writing or changing plugin code or its build.
---

# Paper plugins

The target is a production server with 500+ players. Code that works for one tester can still lag, leak or race under that load, which is why the **verify** skill's gates exist. Check `knowledge/` before relying on any API for this project's Paper version, and research anything not there.

## Project layout

```
plugins/<name>/
  build.gradle            Groovy DSL (the Kotlin DSL script cache broke on Windows)
  settings.gradle
  gradlew, gradlew.bat, gradle/wrapper/   always commit the wrapper; plugin_deploy runs it
  src/main/java/...       the plugin
  src/main/resources/plugin.yml
  src/test/java/...       MockBukkit tests
  tools/                  generators (textures, glyph tables, mockups), if any
```

`plugin_deploy` builds with the wrapper, copies the one jar in `build/libs/` (ignoring `-sources`, `-javadoc`, `-plain` and `-dev`) to `server/plugins/<name>.jar`, and restarts the server. **Never `/reload`.**

## Gradle

```groovy
plugins { id 'java' }
repositories {
    mavenCentral()
    maven { url = 'https://repo.papermc.io/repository/maven-public/' }
}
dependencies {
    compileOnly 'io.papermc.paper:paper-api:<version>.build.<build>-stable'
    testImplementation 'io.papermc.paper:paper-api:<same>'
    testImplementation 'org.mockbukkit.mockbukkit:mockbukkit-v<version>:<latest>'
    testImplementation 'org.junit.jupiter:junit-jupiter:<latest>'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}
java { toolchain.languageVersion = JavaLanguageVersion.of(<java minimum from mcflow.toml>) }
test { useJUnitPlatform() }
```

- Take the exact paper-api build from `server/libraries/io/papermc/paper/paper-api/`, so you compile against what the test server runs.
- MockBukkit publishes one artifact per Minecraft version (`mockbukkit-v1.21`, `-v26.1.2`, `-v26.2`, `-v26.3`). Find the latest release in Maven Central's `maven-metadata.xml`.
- `plugin.yml` `api-version` accepts the 26.x form (`'26.3'`).

## Threads: the rule that matters most

- **The Bukkit API is main-thread only.** Event handlers and `runTask` callbacks run there.
- **Nothing slow on the main thread:** no file, database or network I/O, no `Thread.sleep`, no heavy loops in events that fire often (`PlayerMoveEvent` fires for every movement packet of every player). At 20 TPS a tick has 50 ms for everything on the server.
- **Slow work goes async and comes back:**

```java
getServer().getScheduler().runTaskAsynchronously(this, () -> {
    Data data = storage.load(uuid);                              // off the main thread
    getServer().getScheduler().runTask(this, () -> apply(player, data)); // back on it
});
```

- Netty handlers, `CompletableFuture` callbacks, HTTP clients and async events (`AsyncChatEvent`, `AsyncPlayerPreLoginEvent`) run off the main thread too. Hop back with `runTask` before touching players or the world.
- State shared between threads is a `ConcurrentHashMap` or similar; state only touched on the main thread can be a plain map.
- `gate_thread_safety` scans for violations; Paper also throws "Asynchronous …!" for some.

## State and cleanup

- **Per-player state** lives in a map keyed by UUID, created when needed and **removed on quit**. Close or clean everything on plugin disable. `gate_memory` catches entries, listeners or tasks that survive.
- **Anything the player would lose if the server crashed** (a game mode, items, a location the plugin changed) is written to the player's `PersistentDataContainer` and restored on join.
- **React to events instead of polling.** Use repeating tasks only for values with no event, and keep them cheap.

## Commands

- Declare them in `plugin.yml` with a description and a permission node (`<plugin>.<feature>`) and its default; Bukkit checks it before `onCommand`.
- Check `sender instanceof Player` before treating the sender as a player; console and RCON send commands too.
- For tab completion and typed arguments, Paper's Brigadier command API (registered in the plugin's lifecycle events) is the modern route: research it for the target version before use.

## Configs and persistence

- `saveDefaultConfig()` in `onEnable`, then read values into fields once. Don't read the config inside hot event handlers.
- Load and save player data asynchronously (the pattern above). Save on quit and periodically; never block shutdown for long.
- Databases: a connection pool, prepared statements, every query off the main thread.

## Server internals (only when the API can't)

Reach CraftBukkit, `net.minecraft` or Netty by reflection behind one small class that **fails soft** (falls back to something that still works). Say in the code and in `knowledge/` which version it was checked on. Proven on 26.3: `CraftPlayer.getHandle()` → `ServerPlayer.connection` → `.connection` → `Connection.channel`, with a handler added before `packet_handler`.

## Verified on Paper 26.3

- `PlayerInputEvent` (`org.bukkit.Input`) reports the raw movement, jump, sneak and sprint keys, including for spectators; spectators fly down when sneaking, so `PlayerToggleSneakEvent` isn't reliable for them.
- A spectator's left click fires no Bukkit event (it's a `ServerboundSpectatorActionPacket`).
- `setSpectatorTarget` stops the client sending position and rotation.
- Within `spawn-protection` (16 blocks by default), non-operators can't use or change blocks.

## Tests

- MockBukkit: `MockBukkit.mock()` in `@BeforeEach`, `MockBukkit.unmock()` in `@AfterEach`, `MockBukkit.load(MyPlugin.class)`, `server.addPlayer()`, then `player.performCommand(...)` and assertions. Fire events directly with `server.getPluginManager().callEvent(...)`.
- Keep logic that needs no server (maths, parsing, layout) in plain classes and test it directly.
- **The main plugin class can't be `final`** (MockBukkit subclasses it).
- Some `PlayerMock` methods throw `UnimplementedOperationException` (`resetTitle()`, for example); prefer explicit forms such as `sendTitlePart(TitlePart.TIMES, Title.DEFAULT_TIMES)`.
- **Exceptions in event handlers are only logged,** and one in `onDisable` during `unmock()` makes every later test fail with "Already mocking". Read the test report's stderr, not just the pass count.
- MockBukkit runs no Netty; anything reached through server internals is tested in game.
