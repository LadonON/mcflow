# knowledge

Proven techniques, one Markdown file each. Every entry starts with this frontmatter:

```yaml
---
title: <technique, e.g. "Animated item textures with .mcmeta">
minecraft_versions: [<every Minecraft version it was proven on>]
pack_format: <number>       # resource-pack techniques only
paper_api_version: "<e.g. 1.21>"
verified_by: "<test name, or a path like server/screenshots/<task>/<label>.png>"
sources:
  - <URL of each official doc used>
date: <YYYY-MM-DD>
---
```

Only add an entry after the technique has been proven. Entries can be shared through `mcflow kb push`, which opens a pull request on the shared knowledge base, and new ones fetched with `mcflow kb pull`.
