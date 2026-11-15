# Stage 4: mineflayer bots on the 26.3 test server

Task 4.1. Written 2026-11-15. Everything below was run against `mcflow-demo`'s Paper 26.3 (build 251) test server.

## Versions

| Package | Version | Released | Notes |
|---|---|---|---|
| mineflayer | 4.39.0 | 2026-09-06 | `testedVersions` ends at **26.1**. Node >= 22 |
| minecraft-protocol | 1.68.0 | 2026-08-27 | |
| minecraft-data | 3.119.0 | 2026-10-29 | newest `pc` entry is **26.1**. 499 MB installed |
| ViaBackwards | 5.12.2 | 2026-10-27 | Hangar Release channel. Supports Paper 26.1.2, 26.2 and 26.3. Needs ViaVersion (5.12.2 here). SHA-256 `e989440e0aad7e12d4685d7a57df854691b67660966a95ec0450e20ce98e87ab` |

**26.2 and 26.3 support is in progress upstream** but not released: open PRs PrismarineJS/mineflayer#3926, #4121, #4146, #4192 and PrismarineJS/minecraft-data#1300, #1301, #1345, #1346, #1348. Until they ship, bots join as **26.1 clients through ViaBackwards**.

## Offline mode

The test server runs `online-mode=false`, so bots use `auth: "offline"` and any username; no Microsoft account is involved. The server prints its usual offline-mode warnings. The server *requires* its resource pack, and mineflayer accepts packs on its own during configuration.

## Two mineflayer bugs (both need workarounds)

1. **The resource-pack reply never arrives.** For packs with UUIDs (1.20.3+), mineflayer writes `resource_pack_receive` with `uuid` as a `uuid-1345` object, not a string. The server never sees the reply and holds the bot in the configuration phase forever (keep-alives only, no `finish_configuration`). **Workaround:** convert `uuid` to a string before writing.
2. **Kicked for "Invalid move player packet" about a second after spawning.** Since 1.21.2 the server lets a client send one position packet per client tick, and the tick only ends when the client sends `tick_end` (`ServerGamePacketListenerImpl.handleClientTickEnd` resets `receivedPositionThisTick`; `handleMovePlayer` kicks on a second position before it). minecraft-data defines `tick_end` for 26.1 (play `0x0d`, no fields), but **mineflayer never sends it**. **Workaround:** send `tick_end` right after every movement packet (`position`, `position_look`, `look`, `flying`). mineflayer emits `physicsTick` *before* it sends the tick's position, so hooking that event would be in the wrong order.

Both workarounds live in one wrapper around `bot._client.write`. They should be reported upstream.

## Results with the workarounds (`bot-probe.mjs`, 2026-11-15)

10/10 checks passed:

- ViaBackwards loaded next to ViaVersion and the menu plugin.
- One bot joined in 2.2–2.6 s (first join after startup). Five more joined at once in about 0.35 s each.
- Position, chat (sent and echoed back), look (the server saw the new yaw and pitch), walking (8.6 blocks in 2 s on a flat platform; the server's position matched the bot's).
- `/menu` from a bot put it in spectator mode, and the bot's sneak closed the menu and restored survival. So bots can drive the Stage 3 slice through the plugin's real input path (`PlayerInputEvent`).
- No exceptions in the server log.

**Open:** when five bots spawned at the same point at once, the server logged "moved too quickly!" for three of them. No one was disconnected; it looks like bots pushing each other apart on spawn. It's not investigated yet, and it matters for swarms (task 4.3): spread bots out or stagger joins, then check again.

## Consequences for mcflow

- `mcflow server setup` should install ViaBackwards next to ViaVersion (pinned with its SHA-256, like ViaVersion), but only when the server is newer than mineflayer's newest supported version.
- The bot tools (task 4.2) must apply both workarounds and pin `version: "26.1"` (mineflayer's `latestSupportedVersion`) while the server is newer. Once mineflayer ships 26.3, re-test without ViaBackwards and the workarounds.
- `doctor` should report when bots will be translated by ViaBackwards rather than native.

## Building the bot tools (task 4.2, 2026-11-15)

The nine tools are in `mcp-server/src/bots.ts` (module) and `src/index.ts` (tools). Unit tests (`test/bots.test.ts`) cover the version choice, both workarounds, angle conversion, kick-reason parsing and spawn protection. A live run through the real MCP server passed **30/30**: join (3.4 s for the first bot on a fresh server, about 0.3 s after), duplicate and bad names refused, chat both ways, `/menu` and sneak-to-close, look (the server sees it), walking (8.6 blocks in 2 s, server agrees), inventory, hotbar switch, attack, eating (food went up), a protected chest refused with a spawn-protection hint, a chest opened outside protection, a shift-click that emptied it on the server, a kick reported as its readable reason, tools refusing a disconnected bot, leave-all, and no exceptions or movement warnings.

Two things that looked like bot bugs and weren't:
- **"The walk stops after 2 blocks"** was a chest left on the walking lane by an earlier run. Live tests now clear their area first.
- **"The chest won't open"** was vanilla spawn protection: the chest was 12 blocks from the world spawn, and bots aren't operators. The tool now says so.

Also seen: 26.x kick reasons arrive as NBT-shaped text (`{"type":"string","value":"..."}`), so `reasonText` unwraps it. mineflayer's `chat` puts BigInt values in the packet, so any packet logging needs a BigInt-safe `JSON.stringify`.
