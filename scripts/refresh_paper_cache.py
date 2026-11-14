"""Regenerate src/mcflow/data/paper_versions.json from PaperMC's Fill API.

Run from the repo root:  python scripts/refresh_paper_cache.py
"""

import dataclasses
import datetime
import json
from pathlib import Path

from mcflow.paper import fetch_live

TARGET = Path(__file__).resolve().parent.parent / "src" / "mcflow" / "data" / "paper_versions.json"


def main() -> None:
    versions = fetch_live(timeout=30)
    data = {
        "fetched": datetime.date.today().isoformat(),
        "source": "https://fill.papermc.io/v3/projects/paper/versions",
        "versions": [dataclasses.asdict(v) for v in versions],
    }
    TARGET.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(versions)} versions to {TARGET}")


if __name__ == "__main__":
    main()
