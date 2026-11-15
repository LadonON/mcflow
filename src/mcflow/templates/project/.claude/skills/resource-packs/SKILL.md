---
name: resource-packs
description: Build and check resource packs in resourcepacks/<name>/ - pack.mcmeta and pack formats, fonts and custom GUI glyphs, HUD and title layouts, textures. Use whenever creating or changing a resource pack, drawing UI with font glyphs, or debugging missing or misplaced glyphs.
---

# Resource packs

First draft (Stage 3). It covers what the first vertical slice needed, and every fact marked "26.3" was read from the 26.3 client or checked in game. Item models, sounds, `.mcmeta` animations and shaders aren't covered yet: research them before use, and check `knowledge/` first.

## Build and serve

`resourcepack_build_and_serve <pack>` validates the JSON and `pack.mcmeta`, compares the pack format with the server's Minecraft version, zips the pack deterministically, computes its SHA-1, serves it on `127.0.0.1:<pack_port>`, and points `server.properties` at it. The mcflow client mod accepts packs only from localhost.

## pack.mcmeta

The pack format comes from the game's `version.json` (`pack_version.resource_major`); 26.3 is **97**. From 1.21.9 onward, use `min_format`/`max_format`:

```json
{"pack": {"description": "…", "min_format": 97, "max_format": 97}}
```

## Assets must be original

Never copy Mojang textures or font sheets into a pack. Reference vanilla files by id when you need them (`minecraft:font/ascii.png`), or draw your own. Generate textures in code (a `tools/` script) so layouts stay reproducible.

## Font glyph UIs (26.3)

Custom UIs are bitmap glyphs in a custom font (`assets/<ns>/font/<font>.json`), sent as text with `"font": "<ns>:<font>"`.

- **Bitmap provider:** `{"type": "bitmap", "file": "<ns>:font/x.png", "height": H, "ascent": A, "chars": [...]}`. The texture is split evenly into the `chars` grid.
- **The ascent can't exceed the height.** The game rejects the provider and draws missing-glyph boxes instead. To place a glyph high up, give it a tall cell with transparent padding below it.
- **Vertical position:** the glyph's top is `textY + 7 - ascent` (in font units).
- **Advance (width):** `(int)(0.5 + actualWidth × height / textureHeight) + 1` units, where `actualWidth` is the rightmost opaque column + 1. Measure it from the image; don't guess.
- **Horizontal placement:** a `space` provider (`{"type": "space", "advances": {"\uF000": 0.25, "\uF010": -0.25}}`) moves the pen. Advances are floats and can be negative. A set of power-of-two spaces in both directions reaches any offset.
- **Text colour** multiplies the glyph, so draw textures white where you want to tint them. Turn off the drop shadow with `shadow_color` 0 (Adventure `ShadowColor.none()`).
- **Player faces:** the player-head object component (Adventure `ObjectContents.playerHead(name)`) is 8 units wide and drawn from the text line down. It can't take a font or an ascent, so it pins the layout's vertical position. Offline-mode servers get the skin the client looks up by name.

### Where each HUD text line is drawn (26.3, `Hud`)

| Line | Anchor | Scale |
|---|---|---|
| Title | screen centre, `x = -width/2` (integer division in font units, so an odd width shifts it 2 GUI px right), `y = -10` | ×4 (1 unit = 4 GUI px) |

In the title, give textures 4 texels per unit (height = texture height / 4), so that 1 texel = 1 GUI pixel. The title is centred on its total advance, so end every update at the same total width (add a closing space), or the panel will shift as its contents change.

Subtitle, action bar and boss bar anchors haven't been verified yet. Read them from the client (`javap -c` on the unobfuscated 26.x jar) before using them.

## Checking a UI

- Render a mockup from the same generator the pack uses, and get it approved (the ui-layout flow).
- Then check it in game with `client_screenshot` at the smallest GUI height you support (240 = 1280×720 at "Auto").
- Missing-glyph boxes mean an invalid provider (most often ascent > height) or a char missing from the font.
