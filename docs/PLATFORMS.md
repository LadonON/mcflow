# Platforms

mcflow runs on Windows, macOS and Linux. `mcflow doctor` starts with a **Platform** check that names this machine's OS and CPU, says whether CI tests it, and lists any limits below that apply.

## Tested in CI

Every push runs the unit tests and an end-to-end integration job on three GitHub Actions runners:

| Runner | OS and CPU |
|---|---|
| `windows-latest` | Windows, x86_64 |
| `macos-latest` | macOS, Apple Silicon (aarch64) |
| `ubuntu-latest` | Linux, x86_64 |

The integration job installs the wheel with pipx, runs `mcflow tools install`, `init`, `doctor`, `server setup` on a real Paper jar, `update` and `kb validate`, then drives the server through mcflow-server: start, status, RCON, logs, a test bot joining and chatting, restart and stop. Other platforms (macOS on Intel, Linux on ARM) should work, but nothing tests them.

## Limits by platform

| | Windows x86_64 | Windows ARM64 | macOS (Intel, Apple Silicon) | Linux x86_64, aarch64, armv7 | Other Linux CPUs |
|---|---|---|---|---|---|
| TokToken (code indexing) | ✓ | ✗ no build | ✓ | ✓ | ✗ no build |
| universal-ctags | `mcflow tools install` | `mcflow tools install` (x86_64 build, needs Windows 11's x64 emulation) | `brew install universal-ctags` | package manager | package manager |
| Test server, bots, gates | ✓ | ✓ | ✓ | ✓ | ✓ |
| Client mod | ✓ | ✓ where Minecraft runs | ✓ | ✓ | ✓ where Minecraft runs |

Without TokToken, code search isn't available to the AI. Everything else, including `mcflow tags` (which only needs universal-ctags), still works.

## Things that differ by OS

- **universal-ctags.** macOS ships BSD `ctags` and some Windows toolchains (Strawberry Perl, Git for Windows add-ons) bundle Exuberant Ctags. Neither works: `doctor` and `mcflow tags` say so, and universal-ctags has to come first on `PATH`.
- **The official launcher's game folder.** `mcflow client install` defaults to `%APPDATA%\.minecraft` on Windows, `~/Library/Application Support/minecraft` on macOS and `~/.minecraft` on Linux. Prism and MultiMC instances work everywhere; pass the instance folder.
- **Tool folder.** `mcflow tools install` writes to `~/.local/bin` (`%USERPROFILE%\.local\bin` on Windows). Add it to `PATH` if it isn't already there.
- **Gradle.** mcflow-server runs `gradlew.bat` on Windows and `./gradlew` elsewhere. Paths with spaces are quoted.
- **Line endings.** Workspace files are written with LF. `mcflow update` and `kb pull` ignore CRLF versus LF when they decide whether you've edited a file, so a Windows checkout with `core.autocrlf` doesn't count as an edit.
