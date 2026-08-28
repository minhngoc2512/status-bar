"""Where the app finds its own files.

The same relative layout works from a git checkout and from /usr/lib/claude-status
installed by the .deb, so nothing here needs to know which one it is.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_ID = "claude-status"

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = Path(os.environ.get("CLAUDE_STATUS_ICONS", str(ROOT / "icons")))

FALLBACK_ICON = "claude-idle"


def icon_path(name: str) -> str:
    """Absolute path of an SVG icon, falling back to the idle dot if missing."""
    candidate = ICON_DIR / f"{name}.svg"
    if not candidate.exists():
        candidate = ICON_DIR / f"{FALLBACK_ICON}.svg"
    return str(candidate)
