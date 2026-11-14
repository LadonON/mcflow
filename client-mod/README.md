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

All version differences live in `Compat.java`, behind Stonecutter comments (`//? if >=26.1 {`).

Currently built: **1.21.11** and **26.3**. Other versions are added in `settings.gradle` and `versions/<v>/gradle.properties`.

## Build

```bash
./gradlew collectJars      # JDK 25; jars land in build/libs/
```
