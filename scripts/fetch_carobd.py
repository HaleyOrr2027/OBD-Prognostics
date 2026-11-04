"""Download the public carOBD dataset into data/raw/carOBD/ (raw data is not committed).

Usage:
    python scripts/fetch_carobd.py

Source: https://github.com/eron93br/carOBD (obdiidata/*.csv). Existing files
are never overwritten, because raw data is immutable (plan.md Execution Rule 1).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = "https://github.com/eron93br/carOBD.git"
TARGET = Path(__file__).resolve().parents[1] / "data" / "raw" / "carOBD"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "clone", "--depth", "1", REPO, tmp], check=True)
        copied = skipped = 0
        for src in sorted((Path(tmp) / "obdiidata").glob("*.csv")):
            dest = TARGET / src.name
            if dest.exists():
                skipped += 1
                continue
            shutil.copy2(src, dest)
            copied += 1
    print(f"carOBD: {copied} files copied, {skipped} already present -> {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
