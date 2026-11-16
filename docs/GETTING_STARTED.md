# Getting started

From a fresh machine to Claude Code building a Paper plugin that's tested on a real server and in a real game client.

## 1. What you need

- **Minecraft: Java Edition**, bought and signed in. mcflow checks its work in a real game client, so this isn't optional.
- **Python 3.11 or newer**, and [pipx](https://pipx.pypa.io/) (`python -m pip install --user pipx`, then `python -m pipx ensurepath`).
- **Claude Code**, signed in.

Java, Node.js, universal-ctags, TokToken, git and the GitHub CLI come next. `mcflow doctor` tells you exactly which ones are missing.

## 2. Install mcflow

```bash
pipx install git+https://github.com/LadonON/mcflow.git@v0.1.0
```

That installs the 0.1.0 release. Leave off `@v0.1.0` to get the newest code on `main` instead. mcflow isn't on PyPI.

To update later, reinstall: `pipx install --force git+https://github.com/LadonON/mcflow.git` (with `@<tag>` for a release). pipx lists the package as `mcflow-cli`; the command you run is `mcflow`.

## 3. Create a workspace

```bash
mcflow init my-plugin
cd my-plugin
```

It asks which Paper version your server runs (1.17 or newer, or `latest`). That choice decides which Java you need and which docs and techniques apply, so pick the version your production server actually uses. It's saved in `mcflow.toml`.

## 4. Check your machine

```bash
mcflow tools install
mcflow doctor
```

`tools install` downloads TokToken (and universal-ctags on Windows) from their official releases and checks their SHA-256. On macOS and Linux, install universal-ctags with your package manager; `doctor` shows the command.

`doctor` lists every tool with **ok**, **warn** or **fail**, and a fix for anything that isn't ok. Work through the fails. The **Platform** line tells you whether anything doesn't work on your OS; see [PLATFORMS.md](PLATFORMS.md). One fail is expected at this point: the client mod, which you install in step 6. If your Paper version is newer than the test bots speak, **Test bots** fails too, and step 5 fixes it.

## 5. Set up the test server

1. Download Paper for your version from https://papermc.io/downloads/paper and put the jar in `server/`. mcflow never downloads Paper for you.
2. Read the Minecraft EULA at https://aka.ms/MinecraftEULA. If you accept it:

```bash
mcflow server setup --accept-eula
```

This checks the jar, picks the right Java, and sets the server up for local testing only: it listens on `127.0.0.1`, runs in offline mode, and has RCON with a random password. It also serves your resource pack from your own machine and installs ViaVersion (and ViaBackwards if the test bots need it). Machine-specific settings go in `.mcflow/local.toml`, which git ignores.

## 6. Install the client mod

Close Minecraft first, then:

```bash
mcflow client install
```

This installs Fabric and mcflow's client mod into a separate game folder for the official launcher, so your own mods are never touched. For a Prism or MultiMC instance, pass its folder: `mcflow client install path/to/instance`. Follow the steps it prints, then start that installation from your launcher and sign in.

The mod only joins servers on your own computer, and only acts while it's connected to one.

## 7. Start working

```bash
claude
```

Describe what you want, for example *"a /warp menu with six tiles, opened by a command"*. Claude follows the workflow in `CLAUDE.md` for every task:

1. Looks the technique up in `knowledge/`, and researches current docs if nothing there applies to your version.
2. Plans. For anything players see, it asks you for a layout (or proposes a mockup in `layouts/`) and waits for your approval.
3. Writes the plugin in `plugins/` and the pack in `resourcepacks/`.
4. Verifies it: build, unit tests, deploy to the test server, logs, in-game checks with screenshots, then bots under load for tick time, memory and thread safety.
5. Cleans up the code and proves it changed nothing (same tests, same public API), then checks again.
6. Re-indexes, writes what it proved to `knowledge/`, and only then shows you the result with screenshots and numbers.
7. Asks whether to share the new knowledge.

Drop logos, textures, sounds and models into `assets/` whenever you like. Claude looks there when a task needs them.

## 8. Share and update

- `mcflow kb push` opens a pull request on the shared knowledge base (`LadonON/mcflow-knowledge` unless you change `mcflow.toml`). It never pushes directly. Claude only runs it after you say yes.
- `mcflow kb pull` brings in approved entries. It never overwrites one you've edited.
- `pipx install --force git+https://github.com/LadonON/mcflow.git`, then `mcflow update`, gets newer skills, agents and workflow files. Files you've edited stay as they are, and it shows you the diff.

## If something goes wrong

- **Run `mcflow doctor` first.** Most problems are a missing or wrong-version tool.
- **The server won't start:** check that the EULA is accepted (step 5), and that `server/` has exactly one Paper jar for your version.
- **Claude can't take screenshots:** the client mod isn't installed for this version, or the game isn't running. Rerun `mcflow client install` and start the game from your launcher.
- **Bots can't join a new Paper version:** run `mcflow server setup` again; it adds ViaBackwards when the bots need it.
