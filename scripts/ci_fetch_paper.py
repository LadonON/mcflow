"""CI only: download a Paper server jar from PaperMC's Fill API and check its SHA-256.

Workspaces never download Paper (the user supplies the jar); this is for the integration tests.

    python scripts/ci_fetch_paper.py 1.21.11 <workspace>/server
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

API = "https://fill.papermc.io/v3/projects/paper/versions/{version}/builds/latest"
HEADERS = {"User-Agent": "mcflow-ci"}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as r:
        return r.read()


def main(version: str, dest: Path) -> None:
    build = json.loads(get(API.format(version=version)))
    download = build["downloads"]["server:default"]
    data = get(download["url"])
    digest = hashlib.sha256(data).hexdigest()
    if digest != download["checksums"]["sha256"]:
        sys.exit(f"SHA-256 mismatch for {download['name']}: got {digest}")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / download["name"]).write_bytes(data)
    print(f"{download['name']} (build {build['id']}, {len(data)} bytes, sha256 {digest})")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
