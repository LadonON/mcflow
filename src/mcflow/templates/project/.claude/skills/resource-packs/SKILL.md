---
name: resource-packs
description: Build and check resource packs in resourcepacks/<name>/ for this project's Minecraft version - pack.mcmeta and pack formats, item models (custom model data or item model definitions, depending on the version), fonts and font-glyph UIs, sounds, .mcmeta texture animations and shaders. Use whenever creating or changing a resource pack, or when glyphs, models or textures don't show up in game.
---

# Resource packs

Resource-pack formats change in almost every Minecraft release. **Never rely on memory for a version's rules.** Use what's proven in `knowledge/`, and run the **research** skill for anything else. This skill says where the version boundaries are and which facts are proven.

## Build, serve, gate

- `gate_resource_pack <pack>` checks pack.mcmeta and the pack format against the server's own jar, all JSON, every texture, model and font reference (`minecraft:` ones against the client jar), and the bitmap-font rules. It must pass.
- `resourcepack_build_and_serve <pack>` zips the pack deterministically, computes its SHA-1, serves it on `127.0.0.1:<pack_port>` and points `server.properties` at it. The mcflow client mod accepts packs only from localhost; bots accept them automatically.

## Pack format

- **Don't hardcode it.** The right value is in the server jar's `version.json` (`pack_version.resource_major`). `gate_resource_pack` reads it from there and reports the expected value. Proven: 26.3 → **97**.
- From 1.21.9 onward, pack.mcmeta uses `min_format`/`max_format`; older versions use a single `pack_format` (and optionally `supported_formats`). Research the exact form for older targets.

```json
{"pack": {"description": "…", "min_format": 97, "max_format": 97}}
```

## Assets must be original

Never copy Mojang textures, models, fonts or sounds, or art from paid resources, into a pack. Reference vanilla files by id when you need them (`minecraft:font/ascii.png`), or draw your own. Generate textures in code (a script in the plugin's `tools/`) so layouts and mockups stay reproducible.

## Custom items: depends on the version (research before use)

| Server version | How a custom item model is chosen | Status here |
|---|---|---|
| up to 1.21.1 | `CustomModelData` (an integer) on the item, plus `overrides` with a `custom_model_data` predicate in the vanilla item's model JSON | not proven in this workflow |
| 1.21.2 – 1.21.3 | the `item_model` component can name a model directly; `CustomModelData` overrides still work | not proven |
| 1.21.4 and later | item model definitions in `assets/<ns>/items/<id>.json`; `custom_model_data` becomes lists of floats, flags, strings and colours read by `select`/`condition`/`range_dispatch` models | not proven |

Before using any row: check `knowledge/`, then research the exact JSON for the target version, then prove it in game (a screenshot) and record it.

## Fonts and font-glyph UIs (proven on 26.3)

Custom UIs are bitmap glyphs in a custom font (`assets/<ns>/font/<font>.json`), sent as text with `"font": "<ns>:<font>"`. See `knowledge/font-glyph-title-ui.md` and `knowledge/player-head-text-object.md` for the full geometry.

- **Bitmap provider:** `{"type": "bitmap", "file": "<ns>:font/x.png", "height": H, "ascent": A, "chars": [...]}`. The texture is split evenly into the `chars` grid; all rows the same length.
- **The ascent can't exceed the height.** Otherwise the game rejects the provider and draws missing-glyph boxes. To place a glyph high, give it a tall cell with transparent padding below. (The gate catches this.)
- **Vertical position:** glyph top = `textY + 7 - ascent` (font units).
- **Advance:** `(int)(0.5 + actualWidth × height / textureHeight) + 1` units; `actualWidth` = rightmost opaque column + 1. Measure it from the image.
- **Horizontal placement:** a `space` provider (`{"type": "space", "advances": {"\uF000": 0.25, "\uF010": -0.25}}`). Advances are floats and can be negative; power-of-two spaces both ways reach any offset.
- **Title line:** drawn at the screen centre, ×4 (1 unit = 4 GUI px), at `x = -width/2` (integer division in units: an odd width sits 2 GUI px right) and `y = -10`. Give textures 4 texels per unit so 1 texel = 1 GUI pixel. End every update at the same total advance, or the panel shifts.
- Tint by colouring white glyphs; turn off the shadow with `shadow_color` 0.
- Subtitle, action bar and boss bar anchors aren't proven yet: read them from the client (`javap -c` on the unobfuscated 26.x jar) before use.

## Sounds (research before use)

`assets/<ns>/sounds.json` maps event names to `.ogg` files in `assets/<ns>/sounds/`. Plugins play them by name (`player.playSound(loc, "<ns>:<event>", …)`). Formats (mono for positional sound, Ogg Vorbis) and the `sounds.json` fields: research for the target version.

## Texture animation (research before use)

A `<texture>.png.mcmeta` next to a texture with an `animation` object (`frametime`, `frames`, `interpolate`) animates a vertically stacked strip. Confirm the rules for the target version and prove it in game.

## Shaders (research before use; avoid if possible)

Core shaders (`assets/minecraft/shaders/core/`) change between versions more than anything else in a pack, and a broken one can make the game unusable. Prefer a font, model or texture solution. If a shader is the only way, research the exact target version, keep it minimal, and test it at several GUI scales and on the user's GPU.

## Checking a UI

1. Render a mockup from the same generator the pack uses, and get it approved (**ui-layout**).
2. `client_screenshot` at the smallest supported GUI height (240 = 1280×720 at "Auto"). Measure positions in the screenshot.
3. Missing-glyph boxes mean an invalid provider (usually ascent > height) or a char missing from the font. Run `gate_resource_pack` first.
