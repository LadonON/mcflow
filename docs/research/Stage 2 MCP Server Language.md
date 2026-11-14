---
title: Stage 2: MCP server language (TypeScript vs Python)
date: 2026-11-14
---

# MCP server language

## Facts (from the npm registry and PyPI, 2026-11-14)

| Package | Version | Requires | Unpacked size |
|---|---|---|---|
| `@modelcontextprotocol/sdk` (official TypeScript SDK) | 1.32.2 | Node >= 18 | 4.5 MB |
| `mcp` (official Python SDK) | 2.3.0 | Python >= 3.10 | (n/a) |
| `mineflayer` | 4.39.0 | **Node >= 22** | 1.3 MB |
| `minecraft-protocol` | 1.68.0 | **Node >= 22** | (n/a) |
| `minecraft-data` (a mineflayer dependency) | 3.119.0 | (n/a) | **519.5 MB** |
| `rcon-client` | 4.2.5 | (n/a) | (n/a) |

- mineflayer's README says it supports Minecraft **1.8 to 26.1**, and minecraft-data's newest PC entry is `26.1`. Paper 26.2 and 26.3 are newer than that.
- Python has no maintained equivalent of mineflayer.

## What this means

- The bot subsystem (section 4B) has to be mineflayer, so a Node runtime is needed whatever we choose. Writing the server in Python would mean a Python MCP server driving a Node child process for the bots, which is two languages and an extra IPC layer in one server.
- TypeScript keeps the whole server in one language, uses the official SDK, and calls mineflayer directly.
- **Distribution:** minecraft-data alone is 520 MB, so the server can't ship inside the Python wheel (PyPI's file limit is far below that). The server has to be installed with npm, either as a published package or from the git repo, with its version pinned in `versions.toml`. `mcflow init` or `mcflow update` runs the install.
- **The spec's "Node.js 18+" is out of date.** mineflayer and minecraft-protocol both require **Node 22 or later**, so `doctor`'s minimum has to go up to 22.
- **Bots on 26.2 and 26.3:** mineflayer stops at 26.1. A 26.1 bot can only join a newer server through ViaBackwards (which lets older clients join newer servers), not ViaVersion. This needs handling in Stage 4.

## Recommendation

**TypeScript** for `mcflow-server`, installed through npm and pinned. Python stays the language of the `mcflow` CLI and installer.
