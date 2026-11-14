---
title: Stage 2: test-server setup (Paper jar, server.properties, ViaVersion)
date: 2026-11-14
---

# Test-server setup

## Recognising a Paper jar (PaperMC/Paperclip source, `java17/.../Paperclip.java`)

Paper downloads are Paperclip jars. Paperclip reads these entries from its own jar:

- `META-INF/versions.list` and `META-INF/libraries.list` (tab-separated `hash  id  path` lines)
- `META-INF/patches.list`, `META-INF/download-context`, `META-INF/main-class`
- its classes in `io/papermc/paperclip/`

mcflow treats a jar as Paper when it has `io/papermc/paperclip/` classes **and** `META-INF/versions.list`. It reads the Minecraft version from the versions.list entry's path (`paper-<version>.jar`).

To verify against a real jar: the user's own jar, during the Stage 2 prototype.

## server.properties keys (docs.papermc.io/paper/reference/server-properties, plus hosting guides)

| Key | mcflow sets | Why |
|---|---|---|
| `server-ip` | `127.0.0.1` | localhost only |
| `server-port` | a free port, 25565 if it's free | (n/a) |
| `online-mode` | `false` | so offline-mode test bots can join. This is only safe because the server binds to localhost. |
| `enable-rcon`, `rcon.port`, `rcon.password` | `true`, a free port, a random password | RCON is off by default and always needs a password |
| `broadcast-rcon-to-ops` | `false` | keeps RCON noise out of the game chat |
| `resource-pack`, `resource-pack-sha1` | the local pack URL and its lowercase hex SHA-1 | updated on every pack rebuild |
| `require-resource-pack` | `true` | players who decline are disconnected |
| `resource-pack-prompt` | a short message | (n/a) |
| `resource-pack-id` | a UUID | optional, newer versions only. Older servers drop unknown keys when they rewrite the file. |

## ViaVersion (Hangar, PaperMC's official plugin repository)

- API: `https://hangar.papermc.io/api/v1/projects/ViaVersion/versions?channel=Release`
- Latest release: **5.12.2** (2026-10-27). It lists Paper **1.10 to 26.3**.
- Download: `https://hangarcdn.papermc.io/plugins/ViaVersion/ViaVersion/versions/5.12.2/PAPER/ViaVersion-5.12.2.jar`
- SHA-256: `c0b63badcb0f7d38f4443e06820f2b8142dd4f0d3b0511f9330ff1050430e6b2`
- ViaVersion 5 needs **Java 17**. Paper 1.17's own minimum is Java 16, so mcflow runs the server on Java 17 or later, which is also the recommended LTS. This is still to be confirmed against ViaVersion's own docs during the prototype.

## EULA

The server won't start until `eula.txt` says `eula=true`. mcflow never accepts it on the user's behalf. `mcflow server setup` writes it only when run with `--accept-eula`, and Claude has to ask the user before passing that flag.
