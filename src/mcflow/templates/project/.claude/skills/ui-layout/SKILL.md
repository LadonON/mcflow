---
name: ui-layout
description: Get a player-facing UI's layout approved before building it - the user's sketch or image in layouts/, or a mockup you render from original assets, turned into a written spec the visual verifier checks against. Use whenever a task involves inventories, GUIs, HUD or font-glyph UIs, scoreboards, boss bars or chat formatting.
---

# UI layout flow

Never build player-facing UI from a guess. The approved layout is the spec: the **verifier-visual** agent compares in-game screenshots against it.

## 1. Ask for the layout

Ask the user for a sketch, an image or a description, saved in `layouts/`. Ask what each part should do (what's clickable, what's live data, what closes it). Wait for it; don't propose your own first.

If they have none, say you'll propose one, and use anything relevant in `assets/` (logos, colours, icons).

## 2. Turn it into a spec

Write `layouts/<feature>.layout.md`:

- **How it's drawn** (chest GUI, font glyphs in the title or action bar, boss bar, scoreboard…), and the GUI scale or GUI height it must fit (the smallest supported is 240 GUI px: 1280×720 at "Auto").
- **Every element** with a box in GUI pixels, colours, fonts and text sizes.
- **States:** closed, open, hover, selected, disabled, empty, error.
- **Input:** what opens and closes it and what each click does.
- **Where it differs from the reference and why** (an engine limit, a version rule). Say so plainly; don't hide it.

Check the constraints against `knowledge/` and the **resource-packs** skill first. Font-glyph UIs, for example, place glyphs on a 4 px grid in a title, and a player's face can't be moved off the title's text line.

## 3. Render a mockup

Draw the mockup **with the same code and assets the build will use** (a generator script in the plugin's `tools/`), so the mockup and the game can't disagree. Save:

- `layouts/<feature>-mockup-<state>.png`: the UI at real size on a plain background, for each important state
- `layouts/<feature>-mockup-compare.png`: the reference beside the mockup

All art must be original or from `assets/`. Never copy textures, fonts or art from Minecraft or a paid resource, even when the reference shows them.

## 4. Get approval

Show the mockups and the spec's main points, including the differences. Ask for approval or changes. Repeat until the user approves. Record the approval date and any decisions (what tiles do, where data comes from) at the top of the spec.

## 5. After the build

The in-game screenshots must match the approved mockup. Measure positions in the screenshot rather than eyeballing them. A mismatch is a defect in the build, or, if the game draws it differently, in the mockup; fix whichever is wrong and say which.
