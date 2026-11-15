---
name: paper-plugin
description: Build, structure and test Paper server plugins in this workspace (plugins/<name>/). Use whenever writing or changing plugin code, Gradle builds, commands, listeners, per-player state, persistence, or MockBukkit tests, or when deploying a plugin to the test server.
---

# Paper plugins

First draft (Stage 3). It covers what the first vertical slice needed and what was verified on Paper 26.3. Check `knowledge/` before relying on anything here for another version, and run the research skill when an entry is missing.

## Project layout

```
plugins/<name>/
  build.gradle            Groovy DSL (the Kotlin DSL script cache broke on the dev machine)
  settings.gradle
  gradlew, gradlew.bat, gradle/wrapper/   always commit the wrapper; plugin_deploy runs it
  src/main/java/...       the plugin
  src/main/resources/plugin.yml
  src/test/java/...       MockBukkit tests
  tools/                  generators (textures, glyph tables), if any
```

`plugin_deploy` builds with the wrapper, copies the one jar in `build/libs/` (ignoring `-sources`, `-javadoc`, `-plain` and `-dev` jars) to `server/plugins/<name>.jar`, and restarts the server. Never use `/reload`.

## Gradle

```groovy
plugins { id 'java' }
repositories {
    mavenCentral()
    maven { url = 'https://repo.papermc.io/repository/maven-public/' }
}
dependencies {
    compileOnly 'io.papermc.paper:paper-api:<paper version>.build.<build>-stable'
    testImplementation 'io.papermc.paper:paper-api:<same>'
    testImplementation 'org.mockbukkit.mockbukkit:mockbukkit-v<paper version>:<version>'
    testImplementation 'org.junit.jupiter:junit-jupiter:<version>'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}
java { toolchain.languageVersion = JavaLanguageVersion.of(<java minimum from mcflow.toml>) }
test { useJUnitPlatform() }
```

- Take the exact paper-api build from `server/libraries/io/papermc/paper/paper-api/`, so that you compile against what the test server runs.
- MockBukkit publishes one artifact per Minecraft version (`mockbukkit-v1.21`, `mockbukkit-v26.1.2`, `mockbukkit-v26.2`, `mockbukkit-v26.3`, …). Look up the latest release in Maven Central's `maven-metadata.xml`.
- `plugin.yml` `api-version` accepts the 26.x form (`'26.3'`).

## Rules

- **Main thread only** for Bukkit API calls. Netty handlers, async tasks and HTTP callbacks must hop back with `getServer().getScheduler().runTask(...)` before touching players or the world.
- **No blocking work on the main thread:** no file or network I/O, no `Thread.sleep`, nothing heavy in move events.
- **Per-player state** lives in a map keyed by UUID. It's cleared on quit and on plugin disable, and if it's touched off the main thread it's a `ConcurrentHashMap`.
- **State that must survive a crash** (anything the player could lose, like a game mode the plugin changed) goes in the player's `PersistentDataContainer` and is restored on join.
- **React to events instead of polling.** `PlayerMoveEvent` fires as each movement packet arrives; a per-tick task samples late and merges updates. Keep repeating tasks for values with no event (for example XP).
- **Commands:** declare them in `plugin.yml` with a permission node (`<plugin>.<feature>`) and its default.
- **Paper internals** (CraftBukkit, `net.minecraft`, Netty) only when the API truly can't do it. Reach them by reflection behind one small class that fails soft, and say in the code and in `knowledge/` which version it was checked on.

## Verified on Paper 26.3

- `PlayerInputEvent` (with `org.bukkit.Input`) reports the raw movement, jump, sneak and sprint keys, including for spectators. Spectators fly down when sneaking, so `PlayerToggleSneakEvent` isn't a reliable close signal.
- A spectator's left click sends `ServerboundSpectatorActionPacket`, which fires **no** Bukkit event. Reading it needs a Netty handler before `packet_handler` (`CraftPlayer.getHandle()` → `connection` → `connection` → `channel`, all public in 26.3).
- `setSpectatorTarget` stops the client sending position and rotation (`LocalPlayer.isControlledCamera`), so anything driven by the player's view stops working.
- Relative-rotation `/tp ~yaw` is applied differently by the server and client. In tests, turn the player to absolute angles.

## Tests

MockBukkit: `MockBukkit.mock()` in `@BeforeEach`, `MockBukkit.unmock()` in `@AfterEach`, `MockBukkit.load(MyPlugin.class)`, `server.addPlayer()`, then `player.performCommand(...)` and assertions on state. Keep logic that doesn't need a server (layout maths, parsing) in plain classes and test those directly. MockBukkit doesn't run Netty, so anything reached through server internals is tested in game.

Verified with `mockbukkit-v26.3` 4.120.0:
- **The main plugin class can't be `final`.** MockBukkit subclasses it, so a final class fails with "Cannot subclass … final types".
- **Some `PlayerMock` methods throw `UnimplementedOperationException`** (`resetTitle()`, for example). Prefer the explicit form (`sendTitlePart(TitlePart.TIMES, Title.DEFAULT_TIMES)`).
- **An exception inside an event handler is logged, not thrown,** and one in `onDisable` during `unmock()` makes every later test fail with "Already mocking". Check the test report's stderr for exceptions, not just the pass count.
