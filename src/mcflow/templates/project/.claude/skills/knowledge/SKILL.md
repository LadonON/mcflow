---
name: knowledge
description: Read and write the workspace's knowledge base (knowledge/*.md, proven techniques). Use before using any API, file format or resource-pack feature (look it up), and after a technique is proven in a test or in game (record it). Also covers sharing entries with mcflow kb push.
---

# Knowledge base

`knowledge/` holds techniques that were **proven** in this workflow: one Markdown file each, with frontmatter that says which versions they were proven on and how. It's the first place to look and the last thing you write in a task.

## Look up (before using something)

1. Search `knowledge/` for the API, format or feature: file names, titles, and the body text.
2. An entry **applies** only if:
   - `minecraft_versions` includes this project's Paper version (from `mcflow.toml`), and
   - for resource-pack techniques, `pack_format` matches this version's pack format.
   An entry for another version is a lead, not an answer.
3. No entry that applies → run the **research** skill before writing code.
4. An entry that applies → use it, and say which entry you relied on.

## Record (after proving something)

Write an entry only when the technique was **proven in this workspace**: a passing test, a gate, or an in-game check with a screenshot. Unproven findings stay in `research/`.

```markdown
---
title: "<technique, e.g. Animated item textures with .mcmeta>"
minecraft_versions: ["<every version it was proven on>"]
pack_format: <number>            # resource-pack techniques only
paper_api_version: "<e.g. 26.3>"
verified_by: "<test name, gate run, or server/screenshots/<task>/<label>.png>"
sources:
  - "<URL of each official doc used, or the jar/class it was read from>"
date: <YYYY-MM-DD>
---

# <title>

<How to do it, the exact rules and numbers, and the pitfalls hit on the way.
 Mark anything that's still unproven as such.>
```

- One technique per file, named after it (`font-glyph-title-ui.md`).
- Proven on another version later? Add the version to `minecraft_versions` and the new proof to `verified_by`. Don't create a duplicate.
- An entry turns out wrong on a version? Fix it, or narrow `minecraft_versions`, in the same task.

## Share

At the end of a task with new or updated entries, ask the user whether to share them. Only with their yes, run `mcflow kb push`, which opens a **pull request** on the shared knowledge base for a human to review. It never pushes directly. `mcflow kb pull` brings in approved entries from others.
