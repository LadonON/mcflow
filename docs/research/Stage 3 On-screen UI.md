# Stage 3: drawing an interactive on-screen UI from a Paper 26.3 plugin

Task 3.3. Written 2026-11-15.

## The reference image

`mcflow-demo/layouts/9a745e86-1696-47f4-a47e-19e758017c2e.png` (2048×2048, AI-generated, with a Higgsfield watermark in the corner). The checkerboard is a baked-in transparency pattern. It means "see-through", not a texture. The image shows:

- a **dark, semi-transparent rounded card** in portrait orientation, centred, with a soft drop shadow
- a **header**: the player's own skin face in a bracketed frame, their name, "Lvl 10", and a blue **XP bar** filled to 100/150 with the numbers on it
- an empty band, then a **3×2 grid of square icon tiles**, each with a label underneath: Store, Market, Auction, TP, Dungeons, Settings

Every icon will be redrawn as original pixel art. Nothing from the image is used as an asset.

## Knowledge-base lookup

`mcflow-demo/knowledge/` has no entries yet, so there was nothing to reuse.

## What the 26.3 API gives us (checked in the real jars)

These were read with `javap` and `unzip -l` from `server/libraries/` (paper-api `26.3.build.251-stable`, adventure-api `5.2.0`):

| Need | API | Present |
|---|---|---|
| Player's face as text | `net.kyori.adventure.text.object.PlayerHeadObjectContents` (object text component) | yes |
| Atlas sprite as text | `SpriteObjectContents` | yes |
| Real clickable screen | `io.papermc.paper.dialog.Dialog`, `MultiActionType(actions, exitAction, columns)`, `ActionButton(label, tooltip, width, action)` | yes |
| Sneak detection | `PlayerInputEvent` with `org.bukkit.Input.isSneak()`, plus `PlayerToggleSneakEvent` | yes |

Dialog buttons can set **only the label, tooltip and width**. The height is the vanilla 20 px, and the vanilla button texture is always drawn behind the label. `DialogBase` sets the title, `canCloseWithEscape`, `pause`, `afterAction`, the body (plain text or an item) and inputs. There is no free positioning.

## Options

### A. Font-glyph HUD with a server-driven cursor (recommended)

The panel, tiles and cursor are bitmap font glyphs placed with negative-space advances and sent as a **title** (or action bar) that's refreshed while the menu is open. The name, level and XP-bar fill are text components rebuilt for each player. The face is a `PlayerHeadObjectContents` component.

- **Cursor:** while the menu is open, the plugin reads the player's yaw and pitch changes from movement and maps them to a cursor position on the panel. Hover highlights a tile, and **left click** (arm swing) selects it.
- **Locking the player:** cancel movement (or mount them on an invisible seat), and re-centre the view when the cursor reaches an edge so the cursor stays usable.
- **Close:** sneak, through `PlayerInputEvent`. This matches your choice.
- **Fit with the reference:** best. We control every pixel: the rounded card, the transparency, the shadow, the 3×2 tile grid with labels under the tiles, and the XP bar.
- **Risks:** the world stays visible and the camera still moves a little behind the panel. The cursor only updates at the rate of movement packets (up to 20 per second), so it can feel less smooth than a real mouse. Title glyph positions depend on the GUI scale, so the layout has to be checked at each scale. Of the three options, this needs the most code (the cursor logic). These risks aren't confirmed yet; a short spike measures them.

### B. Native Dialog screen

`/menu` opens a Paper `Dialog` with a `MultiActionType` of six buttons in 3 columns. The header is a plain-message body using glyphs and the head component.

- **Pros:** a real mouse cursor, real clicks and tooltips for free, and the least code.
- **Fit with the reference:** poor. Buttons are fixed 20 px vanilla-textured rectangles, so we can't draw 32 px icon tiles with labels underneath. The card shape is lost to the dialog's full-screen background and title. Retexturing the button sprite in the resource pack would change **every** button in the game, including the main menu.
- **Close:** the player can't sneak while a screen is open, so it would close with Escape or an exit button instead. That conflicts with your choice.

### C. Text displays in front of the camera

Draw the panel as `text_display` entities in the world, and point with the player's crosshair.

- It jitters whenever the player moves, other players can see it, and it gets clipped by blocks. It's worse than A at everything the reference needs. **Not recommended.**

Core shaders aren't needed for A and are fragile between versions, so they're left out.

## Recommendation

**Option A.** It's the only one that can look like the reference and close on sneak, and it fits the "UI cursor" description of Ultimate UI. Before building the full slice, run a **short spike**: one panel glyph, one tile and a cursor driven by camera movement, screenshotted through `client_screenshot` at GUI scales 2 and 3. That checks whether the cursor feels good enough before the layout is finalised.

## Open questions for the user

- What should each tile do in the slice: real actions, or placeholders that send a chat message?
- Should "Lvl" and XP come from vanilla experience, or be fake demo data?

## Decision and spike results (2026-11-15)

**The user chose option A.** A spike in `mcflow-demo` (`plugins/menu-spike/`, `resourcepacks/menu-spike/`, generated by `plugins/menu-spike/tools/generate_assets.py`) was run in the real 26.3 client through mcflow-server. Screenshots are in `mcflow-demo/server/screenshots/stage3-menu-spike/`.

**Verified in game** (GUI scale 4, 1920×991 window): the rounded see-through panel, original icons, the player's face (player-head object component), name, level, a live XP bar ("20/27"), tile labels, hover highlight, and the cursor. Driving the view to known angles put the cursor exactly where the maths predicts: Store hovered at (30,88), Settings at (130,131), clamped at the top-right corner (152,0), and turning back moved it at once to (27,149). No exceptions in the server log.

**Rendering facts read from the 26.3 client** (javap on the unobfuscated jar):
- The title is drawn at the screen centre, scaled ×4, at `x = -width/2`, `y = -10` (`Hud.extractTitle`). One font unit is 4 GUI px.
- A bitmap glyph's top edge is `y + 7 - ascent` (`GlyphBitmap.getTop`), and its advance is `(int)(0.5 + width × height/textureHeight) + 1` units.
- The player-head object is 8 units wide, drawn from the text line down. It can't take a font, so **it pins the panel's vertical position**: the head's top is always 40 GUI px above the screen centre.
- **A bitmap provider's ascent can't exceed its height.** The vanilla ASCII sheet (8 px cells) therefore can't be raised above the text line, and the first run drew missing-glyph boxes. The fix is an original 5×7 pixel font in 32 px-tall cells, which also keeps every asset original.
- Space-provider advances are floats, so horizontal placement is exact to 1 GUI px. Vertical placement is in 4 px steps; the cursor gets 1 px steps from four pre-shifted textures.

**Open issues for the layout step (3.5):**
- The panel spans 56 px above to 104 px below the screen centre. At small GUI heights (247 px here), the bottom row of labels overlaps the hearts and hotbar. The layout needs to be shorter, or arranged so that less of it sits below the centre.
- In offline mode the client resolves the face by name, so the skin it shows can differ between sessions.
- The crosshair stays visible in the gap between the header and the tiles.

**Not verified yet (needs a person at the keyboard):** left-click selection, sneak to close, and how the cursor *feels* with a real mouse (it updates up to 20 times a second). GUI scales 2 and 3 weren't captured either, because the window was maximised.

**Test-harness note:** `/tp` with *relative* rotation (`~-20`) was applied once by the server and differently by the client, so the cursor first jumped and then settled somewhere unexpected. Tests should turn the player to absolute angles.

## Hands-on round 1 (2026-11-15)

The user tried the spike and reported two problems: **the hand and hotbar were visible**, and **the cursor wasn't smooth**.

**Hiding the hand and hotbar.** Spectator mode is the only server-side way to hide them, and it also hides the hearts and (usually) the crosshair. Two things checked in the 26.3 client and server:
- **Locking the camera onto an entity can't be used.** `LocalPlayer.sendPosition` only sends position and rotation when `isControlledCamera()`, which means the camera is the player. With `setSpectatorTarget`, the server would stop receiving the view and the cursor would freeze. So the player is in spectator mode with their own camera, and the world still turns behind the panel.
- **A spectator's left click reaches no plugin event.** The client sends `ServerboundSpectatorActionPacket` (`MultiPlayerGameMode.spectatorNoAction`). It's empty when it hits nothing and carries an entity id when it hits an entity. `ServerGamePacketListenerImpl.handleSpectatorAction` ignores the empty form and fires no Bukkit event for either. Offered three options, **the user chose "spectator + packet hook"**: while the menu is open, a Netty handler (inserted before `packet_handler`, reached by reflection through `CraftPlayer.getHandle()` → `connection` → `connection` → `channel`) swallows that packet and reports a click. It relies on Paper internals, so it fails soft: if the hook can't be installed, Space (jump, from `PlayerInputEvent`) selects instead. `PlayerStartSpectatingEntityEvent` is cancelled while the menu is open.
- The previous game mode is kept in the player's persistent data. It's restored on close and quit, and on the next join if the server stopped while the menu was open. Sneak is read from `PlayerInputEvent`, because spectators fly down rather than toggling sneak.

**Smoothness.** The cursor was redrawn once per tick, but rotation packets don't arrive one per tick, so some were drawn a tick late and others were merged. The cursor now redraws in `PlayerMoveEvent` as each packet arrives, and the per-tick task only handles XP and server-set rotations. The client sends rotation at most once per client tick (20 per second), and no server plugin can go above that.

**Verification status:** the plugin builds, and the user joined and opened `/menu` with it at 15:43. An automated in-game check of this version timed out because the game wasn't running, and the user didn't report back on clicks, closing or smoothness ("never mind"). These are **not verified** and stay in task 3.3b.
