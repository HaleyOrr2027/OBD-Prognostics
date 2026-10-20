"""Make src/ importable for scripts until packaging is decided in Step 00."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def raw_sessions(raw_dir: Path) -> dict[str, Path]:
    """Map session ID (file stem) to path for every raw CSV under data/raw."""
    sessions: dict[str, Path] = {}
    for path in sorted(raw_dir.rglob("*.csv")):
        if path.stem in sessions:
            raise ValueError(f"Duplicate session ID {path.stem}: {sessions[path.stem]} and {path}")
        sessions[path.stem] = path
    return sessions
