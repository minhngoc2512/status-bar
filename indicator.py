#!/usr/bin/env python3
"""Entry point for the Claude Status tray indicators.

The implementation lives in the ``claude_status`` package; the names re-exported
here are the ones test_store.py and older scripts import from this module.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from claude_status.app import App, main  # noqa: E402,F401
from claude_status.claude_panel import ANIM  # noqa: E402,F401
from claude_status.config import CONFIG_PATH, DEFAULTS, Config  # noqa: E402,F401
from claude_status.i18n import LANGUAGES, STRINGS, Lang, default_lang  # noqa: E402,F401
from claude_status.paths import APP_ID, ICON_DIR, icon_path  # noqa: E402,F401
from claude_status.sessions import (  # noqa: E402,F401
    BACKGROUND,
    BASE_DIR,
    CONFIRM,
    DOT,
    ERROR,
    EVENTS_DIR,
    IDLE,
    MAX_SPOOL_FILES,
    PRIORITY,
    SESSION_TTL,
    WORKING,
    Session,
    Store,
    human_age,
)

if __name__ == "__main__":
    main()
