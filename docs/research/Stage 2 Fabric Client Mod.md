---
title: Stage 2: mcflow's own Fabric client mod
date: 2026-11-14
---

# mcflow's own Fabric client mod

The user's decision (2026-11-14): visual verification uses **our own Fabric client mod**. The workflow tells users they **must** install it, and mcflow installs it automatically when given a Minecraft instance folder.

## Facts

- **Fabric covers the whole mcflow range.** `meta.fabricmc.net/v2/versions/game` lists stable releases from 1.17 to 26.3.
- **26.1 is the first unobfuscated Minecraft** (fabricmc.net, "Fabric for Minecraft 26.1"). Mods for 26.x use the non-remapping Loom plugin `net.fabricmc.fabric-loom` (Loom 1.15+, Gradle 9.4+), with `implementation` instead of `modImplementation` and `jar` instead of `remapJar`. Nothing built for 1.21.11 or earlier runs on 26.x without at least a recompile. Fabric now uses Mojang's official names, and Yarn is no longer officially supported.
- **Older (obfuscated) versions** still build with the remapping Loom plugin. Loom can use Mojang's official mappings (`loom.officialMojangMappings()`), so the source uses the same class and method names on both sides of the 26.1 boundary.
- **Latest Loom:** 1.19 (2026-10-23).
- **Stonecutter** (`dev.kikugie.stonecutter`, 0.9.7 on the Gradle plugin portal, now hosted on Codeberg) builds one source tree against many Minecraft versions, with version-conditional comments. Public templates already cover 1.21 to 26.3 across the obfuscation boundary (OddHero/minecraft-mod-template, multicutter with "Loom Backwards Compatibility"). **None we found reaches back to 1.17**, so supporting 1.17–1.20.x in the same tree still has to be proven.
- **Fabric installer CLI:** `java -jar fabric-installer.jar client -dir <.minecraft> -mcversion <v> [-loader <v>] [-noprofile]` (wiki.fabricmc.net/install). It adds a Fabric profile to the official Minecraft Launcher.

## Design implications

- **Signing in stays with the user's own launcher** (the Minecraft Launcher, Prism and so on). mcflow never handles Microsoft accounts, which avoids Mojang's Azure-app approval process entirely.
- **No Fabric API dependency.** Using only Fabric Loader plus our own mixins keeps installs to one jar and one less version to match.
- **Control channel:** a loopback TCP socket (`java.net`, always available in every Java runtime Minecraft ships) speaking line-delimited JSON. It binds to 127.0.0.1 only, uses a random token, and writes its port and token to a file in the game folder, where mcflow-server can find them because it knows the instance folder.
- **Safety:** the mod controls the user's real game, so it only accepts commands while connected to a **localhost** server. It auto-accepts server resource packs only from localhost, and does nothing until mcflow's token file exists.
- **Small version-specific surface:** client tick hook, screenshot capture, sending chat and commands (the API changed in 1.19), connecting to a server, opening the inventory, accepting the resource-pack prompt, and listing the current screen's widgets. Everything else (socket, JSON, auth) is plain Java shared by every version.
- **Distribution:** the mod lives in the mcflow repo (`client-mod/`). GitHub Actions builds one jar per supported Minecraft version and attaches them to a release. mcflow downloads the right jar and checks its SHA-256, which is pinned in `versions.toml`.

## Auto-install by launcher type

| Instance type | How it's detected | Mod jar | Fabric Loader |
|---|---|---|---|
| Official launcher (`.minecraft`) | `launcher_profiles.json` + `versions/` | copy into `mods/` | run the official Fabric installer CLI (needs Java, which `doctor` already checks) |
| Prism / MultiMC instance | `instance.cfg` + `mmc-pack.json` | copy into `.minecraft/mods` or `minecraft/mods` | ask the user to add Fabric in the launcher (one click), or edit `mmc-pack.json` (still to research) |
| Anything else with a `mods/` folder | (n/a) | copy | the user's responsibility |

## Risks

1. **Range 1.17–1.20.x** in one Stonecutter tree with 26.x is unproven. Prototype on two versions across the boundary first.
2. **Per-version API drift** in the small surface above. Each new Minecraft release means checking the mod still builds and works, which CI can do.
3. **Windows and macOS show a real game window** while checks run. Linux can use Xvfb.
