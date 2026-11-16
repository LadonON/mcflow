---
name: research
description: Research an API, file format, library version or game mechanic before relying on it, and write the findings to research/<Topic>.md. Use automatically, without asking, whenever knowledge/ has no entry for something you're about to use (or the entry doesn't cover this project's Minecraft version), or whenever you're unsure how something works on this version.
---

# Research

Your memory of Minecraft formats, Paper APIs and library versions is often out of date: formats change every release (pack formats, item models, font rules, protocol details). Research is how this workspace avoids building on stale facts. It needs no permission from the user; just do it and say what you found.

## When

- The **knowledge** skill found no entry, or none that matches this project's Paper version and pack format.
- You're about to use an API, file format, resource-pack feature, plugin or tool version you haven't verified on this version.
- A test or in-game check behaves differently from what you expected.

## How

1. **Split the question into topics.** One topic = one thing that can be answered and verified ("Bitmap font provider rules in 26.3", "MockBukkit for 26.3"). For a broad question, send one **researcher** agent per topic in parallel (Agent tool, `subagent_type: researcher`), each with the topic, the project's Paper version and pack format, and what decision depends on it.
2. **Prefer primary sources, in this order:**
   1. The thing itself: the server or client jar (`javap -c` on the unobfuscated 26.x jars in `server/` and the launcher's `versions/` folder), the library's published artifacts (Maven Central `maven-metadata.xml`, npm `npm view`), a plugin's own classes.
   2. Official docs: PaperMC docs and Javadoc, the Minecraft Wiki for formats, the library's README and changelog.
   3. Issues and pull requests in the official repositories (they show what's broken or not released yet).
   4. Anything else, marked as unconfirmed.
3. **Never send the user's data anywhere** while researching (no uploads, no pastes, no profilers that publish results). Downloading a tool or library to inspect it is a download: ask first.
4. **Write one doc per topic** to `research/<Topic Being Researched>.md`:

```markdown
# <Topic>

Researched <YYYY-MM-DD> for Paper <version>, pack format <n>.

## Answer
<the facts the decision needs, each with where it came from>

## Sources
- <URL, or "26.3 client jar: net.minecraft.client.gui.Hud.extractTitle (javap)">

## Not confirmed
<anything you couldn't verify, and how it could be>
```

5. **Research isn't proof.** Findings stay in `research/` until a test or an in-game check proves them. Then the **knowledge** skill turns them into an entry.

## Report

Tell the user in a few lines what you looked up, what you found, which decision it changes, and what's still unconfirmed.
