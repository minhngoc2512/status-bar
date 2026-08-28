"""Where the app finds its own files.

The same relative layout works from a git checkout and from /usr/lib/claude-status
installed by the .deb, so nothing here needs to know which one it is.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

APP_ID = "claude-status"

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = Path(os.environ.get("CLAUDE_STATUS_ICONS", str(ROOT / "icons")))

FALLBACK_ICON = "claude-idle"


# `apt upgrade` replaces the files on disk but cannot restart a *user* systemd
# service -- dpkg runs as root and has no handle on a login session. So the old
# code keeps running, silently, until the next logout. Comparing what is loaded
# against what is installed is the only way the user finds out.
_upgrade_probe: tuple[float, str] = (0.0, "")
UPGRADE_TTL = 60.0

VERSION_RE = re.compile(r'__version__ = "([^"]+)"')


def installed_version() -> str:
    """Version of the code on disk, which may be newer than the one running."""
    try:
        found = VERSION_RE.search((ROOT / "claude_status" / "__init__.py").read_text())
    except OSError:
        return ""
    return found.group(1) if found else ""


def pending_upgrade(running: str) -> str:
    """The newer version waiting for a restart, or "" when there is none."""
    global _upgrade_probe
    now = time.time()
    stamp, cached = _upgrade_probe
    if now - stamp < UPGRADE_TTL:
        return cached
    on_disk = installed_version()
    _upgrade_probe = (now, on_disk if on_disk and on_disk != running else "")
    return _upgrade_probe[1]


def icon_path(name: str) -> str:
    """Absolute path of an SVG icon, falling back to the idle dot if missing."""
    candidate = ICON_DIR / f"{name}.svg"
    if not candidate.exists():
        candidate = ICON_DIR / f"{FALLBACK_ICON}.svg"
    return str(candidate)
