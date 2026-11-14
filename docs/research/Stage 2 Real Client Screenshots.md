---
title: Stage 2: real Minecraft client for screenshots
date: 2026-11-14
---

# Real client for visual verification

Goal (spec section 4C): a scripted, real Java Edition client that joins the local test server, accepts the resource pack, runs commands, opens inventories and saves screenshots to `server/screenshots/<task>/<label>.png`. Every user owns Java Edition and signs in with Microsoft.

## Constraint: Microsoft sign-in

New Azure app registrations must apply to Mojang for Minecraft API access. Until approved, `api.minecraftservices.com` returns 403 (minecraft.wiki, Microsoft Authentication Scheme). That rules out writing our own login flow quickly. **We need a launcher that already has working sign-in.** HeadlessMc and Prism Launcher both have it.

## Candidates

### HeadlessMc (headlesshq/headlessmc)

- MIT, 429 stars, active (pushed 2026-11-14). Version 3.0.0-RC8 (2026-10-15) ships native binaries for Windows x64, Linux x64/arm64 and macOS x64/arm64, plus `headlessmc.jar`.
- A command-line launcher. Microsoft sign-in uses the device code flow (the user opens a link in a browser). It installs vanilla, Fabric, Forge and NeoForge, and can launch a client in a normal window or headless.
- **Headless mode renders nothing, so screenshots are impossible there.** Screenshots need a real window, or Xvfb on Linux (HMC-Specifics README).

### HMC-Specifics (headlesshq/hmc-specifics)

- MIT, active. One small mod per Minecraft version that adds in-game control commands: `gui`, `click`, `text`, `connect`, `disconnect`, `/` (chat command), `msg`, `screenshot <file>`, `metrics`, `quit`, and a `key` command in its API.
- `screenshot` saves the last rendered frame as PNG, and the PNG is encoded off the main thread.
- **Versions supported:** 1.17.1, 1.18.2, 1.19.4, 1.20.6, 1.21–1.21.11, 26.1–26.3 (Fabric for all of them).
- **Gaps within mcflow's 1.17+ range:** 1.17, 1.18–1.18.1, 1.19–1.19.3, 1.20–1.20.5.

### HeadlessMc MCP (headlesshq/headlessmc-mcp)

- MIT, **v0.1.0, marked as a prototype**, 9 stars, released 2026-10-19. It's a ready-made MCP server with the tools `launch_client`, `connect`, `chat`, `get_screen`, `click`, `press_key`, `game_command`, `wait_for`, `instance_log` and more.
- It includes **`hmc-mcp-bridge`**, a single mod jar that works on every Minecraft version. It opens a loopback HTTP server: `GET /health`, `GET /info`, and `POST /command` (runs any HMC-Specifics command line). It authenticates with a Bearer token passed in as `-Dhmc.mcp.token`. That gives any program, including our own MCP server, a clean way to drive the client.
- Native binaries for all three OSes. The jar needs Java 25.

### Our own Fabric mod with a control socket

- Full control, but it would need a separate build for every Minecraft version from 1.17 to 26.x. Mappings change between versions, and 26.x ships unobfuscated. This is the same work HMC-Specifics already does and maintains.
- The Fabric client gametest API has `takeScreenshot`, but it's designed for mod test runs, and a maintainer has said it may be scrapped (FabricMC/fabric issue #4411).

### Vanilla client plus OS automation

- Launch through a launcher, join with `--quickPlayMultiplayer`, then send keystrokes from the OS and capture the window.
- It works on every version without a mod, but it can't read what's on screen, every OS needs its own keystroke and capture code, and it breaks easily (focus, window position, DPI).

### Prism Launcher

- GPL-3.0, 11k stars, very mature. Has `--launch <instance> --server <addr> --profile <account>`.
- Good for signing in, but every instance has to be set up by hand, and it has no control channel of its own. It would still need HMC-Specifics plus the bridge (headlessmc-mcp supports attaching to games launched elsewhere).

## Display (all options)

| OS | Where the client renders |
|---|---|
| Windows, macOS | A real game window appears on the desktop while checks run. If it's minimised, rendering and screenshots may stop. |
| Linux | Xvfb (a virtual display) with Mesa software rendering, so no screen is needed. This also works on CI. |

## Options compared

| | A. Use headlessmc-mcp as-is | **B. mcflow-server drives HeadlessMc + HMC-Specifics + bridge** | C. Our own Fabric mod | D. Vanilla client + OS automation |
|---|---|---|---|---|
| Work for us | Lowest | Medium | Highest (one build per version) | Medium, then ongoing fixes |
| Spec tool names and screenshot paths | No (its own tools) | **Yes** | Yes | Yes |
| Reads what's on screen | Yes | **Yes** | Yes | No |
| Version coverage | HMC-Specifics list | HMC-Specifics list | What we build | All |
| Robustness | Prototype (v0.1.0) | Depends on HeadlessMc 3.0 RC and the bridge | Ours to maintain | Fragile |
| Microsoft sign-in | Device code | Device code | Needs a launcher anyway | Needs a launcher anyway |

## Recommendation

**Option B.** `mcflow-server` gets the spec's `client_*` tools and implements them by:

1. Launching the client with a pinned HeadlessMc binary: Fabric for the project's version, the HMC-Specifics jar and the `hmc-mcp-bridge` jar, and a random token.
2. Sending HMC-Specifics commands over the bridge's loopback HTTP API: `connect`, `/ <command>`, `key`, `gui`/`click` (for the resource-pack prompt), and `screenshot <path>`.

Signing in is a one-time `headlessmc login` through the browser. If the bridge or HeadlessMc changes in a way we can't follow, option A (registering headlessmc-mcp next to ours) is a ready fallback.

**Versions without an HMC-Specifics build** (for example 1.20.4) take the nearest newer supported client (1.20.6). It joins through ViaVersion, which the spec already installs on the server. That's not a pixel-exact match for the target version, so the screenshot report must say so.
