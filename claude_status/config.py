"""Persisted settings for every indicator, with change notification.

One JSON file at ~/.config/claude-status/config.json. Unknown keys in the file
are kept, missing ones fall back to DEFAULTS, so an old config from before the
weather/crypto panels existed still loads.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Callable

CONFIG_PATH = Path(
    os.environ.get("CLAUDE_STATUS_CONFIG", str(Path.home() / ".config/claude-status/config.json"))
)

# Panels each own a top-level section; anything else counts as "general".
SECTIONS = ("claude", "weather", "crypto", "system")

DEFAULTS: dict = {
    "lang": None,
    "notify": True,
    "animate": True,
    "claude": {
        "enabled": True,
        "show_label": True,
        # Reads message.usage out of each session's transcript; see tokens.py.
        "show_tokens": True,
    },
    "weather": {
        "enabled": False,
        # "auto" = geolocate by IP, "manual" = use the coordinates below
        "mode": "auto",
        "latitude": None,
        "longitude": None,
        "place": "",
        "unit": "celsius",  # celsius | fahrenheit
        "refresh_minutes": 30,
        "show_label": True,
        # cache of the last IP lookup so restarts don't hammer the geo API
        "detected": None,  # {"latitude", "longitude", "place", "at"}
    },
    "system": {
        "enabled": False,
        "refresh_seconds": 3,
        "show_label": True,
        # any of: cpu, temp, ram, gpu, gpu_temp, net
        "bar_metrics": ["cpu", "temp"],
        "temp_sensor": "",  # "" = auto-pick the most CPU-ish sensor
        "warn_celsius": 85,
        "hot_celsius": 95,
        "net_unit": "bytes",  # bytes | bits
        "interfaces": [],  # [] = follow the default route
        "gpu": True,
    },
    "crypto": {
        "enabled": False,
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "bar_symbol": "BTCUSDT",
        "refresh_seconds": 60,
        "show_change": True,
        "show_label": True,
        # Binance geo-blocks some networks; this lets the user point elsewhere
        # (api.binance.us, a mirror, ...) without editing code.
        "endpoint": "https://api.binance.com",
    },
}


def merged(defaults: dict, override) -> dict:
    """Deep-merge ``override`` onto a copy of ``defaults``."""
    out = copy.deepcopy(defaults)
    if not isinstance(override, dict):
        return out
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merged(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def assign(data: dict, path: str, value) -> None:
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = node[part] = {}
        node = nxt
    node[parts[-1]] = value


class Config:
    """Dotted-path access over the settings dict.

    ``set`` only records the change; ``save`` re-reads the file, replays just
    the paths this instance touched, writes the result, and tells the listeners
    which sections moved.

    Replaying instead of dumping the in-memory snapshot matters: the systemd
    service and any second instance (a test run, `claude-status` from a
    terminal) each hold their own copy, and a blind overwrite silently reverts
    whatever the other one changed -- e.g. the language flipping back on its
    own after the tray menu set it.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else CONFIG_PATH
        self.data = merged(DEFAULTS, self._read())
        self._changed: dict[str, object] = {}
        self._dirty: set[str] = set()
        self._listeners: list[Callable[[set[str]], None]] = []

    def _read(self) -> dict:
        try:
            raw = json.loads(self.path.read_text())
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    # ------------------------------------------------------------- access

    def get(self, path: str, default=None):
        node = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, path: str, value) -> bool:
        """Returns True when the value actually changed."""
        parts = path.split(".")
        node = self.data
        for part in parts[:-1]:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                nxt = node[part] = {}
            node = nxt
        if node.get(parts[-1]) == value:
            return False
        node[parts[-1]] = value
        self._changed[path] = value
        head = parts[0]
        self._dirty.add(head if head in SECTIONS else "general")
        return True

    # -------------------------------------------------------------- store

    def subscribe(self, fn: Callable[[set[str]], None]) -> None:
        self._listeners.append(fn)

    def save(self) -> None:
        # Rebase onto whatever is on disk now, then replay only our own edits.
        fresh = merged(DEFAULTS, self._read())
        for path, value in self._changed.items():
            assign(fresh, path, value)
        self.data = fresh
        self._changed = {}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n")
            tmp.replace(self.path)
        except Exception:
            pass
        changed, self._dirty = self._dirty, set()
        if changed:
            for fn in list(self._listeners):
                fn(changed)
