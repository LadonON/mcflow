"""Pin a published runtime release's checksums into src/mcflow/versions.toml.

Usage (from the repo root, after publishing the draft release on GitHub):
    python scripts/pin_runtime.py runtime-v0.1.0

Reads SHA256SUMS from the release with the GitHub CLI and rewrites the [client_mod] and
[mcflow_server] pins. Review the diff and commit it: from then on mcflow only installs files
whose checksums it ships with.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = "LadonON/mcflow"
VERSIONS = Path(__file__).resolve().parent.parent / "src" / "mcflow" / "versions.toml"
MOD_JAR = re.compile(r"^mcflow-client-(?P<mod>[\d.]+)\+(?P<mc>[\d.]+)\.jar$")
SERVER_TGZ = re.compile(r"^mcflow-server-(?P<version>[\w.-]+)\.tgz$")


def read_sums(tag: str) -> dict[str, str]:
    text = subprocess.run(
        [
            "gh",
            "release",
            "download",
            tag,
            "--repo",
            REPO,
            "--pattern",
            "SHA256SUMS",
            "--output",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    sums = {}
    for line in text.splitlines():
        digest, name = line.split(maxsplit=1)
        sums[name.lstrip("*")] = digest
    return sums


def render(tag: str, sums: dict[str, str]) -> tuple[str, str]:
    url = f"https://github.com/{REPO}/releases/download/{tag}/"
    mods = {m.group("mc"): (m.group("mod"), d) for n, d in sums.items() if (m := MOD_JAR.match(n))}
    if not mods:
        raise SystemExit("No mod jars in SHA256SUMS")
    mod_versions = {v for v, _ in mods.values()}
    if len(mod_versions) != 1:
        raise SystemExit(f"Mixed mod versions in one release: {sorted(mod_versions)}")
    servers = [(m.group("version"), n, d) for n, d in sums.items() if (m := SERVER_TGZ.match(n))]
    if len(servers) != 1:
        raise SystemExit("Expected exactly one mcflow-server tarball")

    order = sorted(mods, key=lambda v: tuple(int(x) for x in v.split(".")))
    client = (
        "[client_mod]\n"
        "# mcflow's own Fabric client mod (client-mod/ in this repo). Users must install it.\n"
        f"# Pinned from release {tag} by scripts/pin_runtime.py.\n"
        f'version = "{mod_versions.pop()}"\n'
        "minecraft_versions = [\n" + "".join(f'  "{v}",\n' for v in order) + "]\n"
        f'release_url = "{url}"\n'
        "[client_mod.sha256]\n" + "".join(f'"{v}" = "{mods[v][1]}"\n' for v in order)
    )
    version, name, digest = servers[0]
    server = (
        "[mcflow_server]\n"
        f"# Pinned from release {tag} by scripts/pin_runtime.py.\n"
        f'version = "{version}"\n'
        f'tarball_url = "{url}{name}"\n'
        f'sha256 = "{digest}"\n'
    )
    return client, server


def replace_section(text: str, name: str, new: str) -> str:
    """Replace [name] and its [name.*] subtables, or append if missing."""
    pattern = re.compile(rf"^\[{re.escape(name)}(?:\.[^\]]+)?\]\n(?:(?!^\[).*\n?)*", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return text.rstrip("\n") + "\n\n" + new
    start, end = matches[0].start(), matches[-1].end()
    return text[:start] + new + "\n" + text[end:]


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("runtime-v"):
        raise SystemExit(__doc__)
    tag = sys.argv[1]
    client, server = render(tag, read_sums(tag))
    text = VERSIONS.read_text(encoding="utf-8")
    text = replace_section(text, "client_mod", client)
    text = replace_section(text, "mcflow_server", server)
    VERSIONS.write_bytes(text.encode("utf-8"))  # LF, even on Windows
    print(f"Pinned {tag} into {VERSIONS}. Review with `git diff` and commit.")


if __name__ == "__main__":
    main()
