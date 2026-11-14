# mcflow client mod

A small Fabric mod that lets mcflow drive a real, signed-in Minecraft client on a **local** test server: join, run player commands, open the inventory, read what's on screen and take screenshots. Only a real client renders resource-pack models, fonts, GUIs and shaders, which is why this exists.

**Every mcflow user must install it.** `mcflow client install` does that for you, and `mcflow doctor` fails until it's installed.

## Safety

- It listens on `127.0.0.1` only, on a random port, and every request needs a random token. The port and token are written to `<game dir>/mcflow/bridge.json` (owner-only on macOS and Linux) and deleted when the game exits.
- It only joins servers on this computer. Every in-game command, and screenshots, refuse to run unless the client is connected to such a server.
- The automatic resource-pack acceptance only applies to the local servers it joins.
- No Fabric API and no mixins: just a client entrypoint. Commands run on Minecraft's own client thread.

## Commands (line-delimited JSON over the bridge)

| Command | Args | Result |
|---|---|---|
| `status` | (n/a) | version, in world, server, player, current screen, window size |
| `connect` | `address` (`127.0.0.1:<port>`) | starts joining, with the server pack accepted |
| `command` / `chat` | `command` / `message` | sends as the player |
| `open_inventory` | (n/a) | opens it, and returns `screen` |
| `screen` | (n/a) | screen type and title, widgets with positions, container slots with item ids and counts |
| `close_screen` | (n/a) | (n/a) |
| `screenshot` | `path` (absolute, `.png`) | saves the last frame, and returns the path and size |
| `quit` | (n/a) | closes the game |

mcflow-server's `client_*` tools wrap these.

## Versions

Stonecutter builds one jar per Minecraft version from the same source. Minecraft 26.1 was the first unobfuscated release, so:

| Version | Loom plugin | Names |
|---|---|---|
| up to 1.21.11 | `net.fabricmc.fabric-loom-remap` | Mojang names in source, remapped in the jar |
| 26.1 and later | `net.fabricmc.fabric-loom` | Mojang names, no remapping |

All version differences live in `Compat.java`, behind Stonecutter comments (`//? if >=26.1 {`):

| API | Changed at |
|---|---|
| Screenshots: `takeScreenshot(width, height, target)` → `(target)` → callback | 1.17.1, 1.21.5 |
| Chat: `player.chat` → `player.chatSigned(msg, null)` → `connection.sendChat` | 1.19.1, 1.19.3 |
| Commands: `player.chat("/…")` → `player.command` → `player.commandSigned(cmd, null)` → `connection.sendCommand` | 1.19, 1.19.1, 1.19.3 |
| Fullscreen option (field → `OptionInstance`) | 1.19 |
| Widget position, item registry | 1.19.3 |
| Accessibility onboarding screen | 1.19.4 |
| `ServerData` constructor (boolean "lan" → `Type`) | 1.20.2 |
| `ConnectScreen.startConnecting` (+quickPlay, then +TransferState) | 1.20, 1.20.5 |
| Toasts (`getToasts()` → `getToastManager()`) | 1.21.2 |
| Screen, toasts and render target move to `Minecraft.gui` / `gameRenderer` | **26.2** (26.1.x still uses `Minecraft`) |

Each boundary was read from the real classes with `javap`. CI builds every version, so a wrong boundary fails the build.

**Built for every Paper version mcflow supports**, from 1.17 to 26.3: one jar per version, generated from `src/mcflow/data/paper_versions.json`. Adding a version means adding it to `settings.gradle` and creating `versions/<v>/gradle.properties`.

## Platform notes

The user starts the game from their own launcher, signed in with their own Microsoft account. mcflow never launches Minecraft or handles accounts.

| | Status | What to know |
|---|---|---|
| **Windows** | **Verified** (2026-11-14, Windows 11, Minecraft 26.3, official launcher) | A normal game window opens. It can sit behind other windows, since mcflow turns off pause-on-focus-loss. Don't minimise it: a minimised game may stop rendering, which would give blank or stale screenshots (not yet tested). |
| **macOS** | Not yet tested | Same as Windows. macOS may also slow down apps that are fully hidden (App Nap), so keep the window at least partly visible during checks. |
| **Linux (desktop)** | Not yet tested | Same as Windows. |
| **Linux (no screen, e.g. CI)** | Not supported yet | The game needs a display. Running the launcher under a virtual display (Xvfb with Mesa's software renderer) should work but hasn't been tried. |

Screenshots are taken at the window's size. `client_join` sets 1280×720 unless asked otherwise, so screenshots from different runs line up.

## Build

```bash
./gradlew collectJars      # JDK 25; jars land in build/libs/
```
