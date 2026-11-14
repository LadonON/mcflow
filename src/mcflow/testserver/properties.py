"""Read and update server.properties without disturbing keys mcflow doesn't manage.

Values use Java .properties escaping: Minecraft writes URLs as `http\\://...`. mcflow-server
(TypeScript, mcp-server/src/properties.ts) follows the same rules.
"""

import re
from pathlib import Path

_ESCAPED = re.compile(r"\\(.)")


def parse(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!")) or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = _ESCAPED.sub(r"\1", value.strip())
    return values


def update(path: Path, changes: dict[str, str]) -> None:
    """Set the given keys in place, keeping comments, order and every other key."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(changes)
    out = []
    for line in lines:
        key = line.partition("=")[0].strip()
        if "=" in line and not line.lstrip().startswith(("#", "!")) and key in remaining:
            out.append(f"{key}={_escape(remaining.pop(key))}")
        else:
            out.append(line)
    out.extend(f"{k}={_escape(v)}" for k, v in remaining.items())
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("=", "\\=")
