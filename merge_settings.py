#!/usr/bin/env python3
"""Merge the status-indicator hooks into ~/.claude/settings.json.

Existing hooks are preserved: entries are appended to each event's list, and
re-running is a no-op because entries are matched on the command string.
"""

import json
import shutil
import time
from pathlib import Path

SETTINGS = Path.home() / ".claude/settings.json"
HOOK = str(Path(__file__).resolve().parent / "hooks/emit.sh")

# event -> matcher (None means "no matcher", i.e. every occurrence)
EVENTS = {
    "SessionStart": None,
    "SessionEnd": None,
    "UserPromptSubmit": None,
    "PreToolUse": "*",
    "PostToolUse": "*",
    "PermissionRequest": "*",
    "Stop": None,
    "StopFailure": None,
    "SubagentStart": "*",
    "SubagentStop": None,
    "Notification": None,
}

# Keep this small: it runs synchronously on every tool call.
TIMEOUT = 5


def entry() -> dict:
    return {"type": "command", "command": HOOK, "timeout": TIMEOUT}


def main() -> None:
    settings = {}
    if SETTINGS.exists():
        settings = json.loads(SETTINGS.read_text())
        backup = SETTINGS.with_suffix(f".json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(SETTINGS, backup)
        print(f"    backup: {backup}")

    hooks = settings.setdefault("hooks", {})
    added = 0

    for event, matcher in EVENTS.items():
        groups = hooks.setdefault(event, [])

        # Already installed for this event?
        if any(h.get("command") == HOOK for g in groups for h in g.get("hooks", [])):
            continue

        # Reuse a group with the same matcher when one exists, otherwise add one.
        target = None
        for group in groups:
            if group.get("matcher") == matcher or (matcher is None and "matcher" not in group):
                target = group
                break
        if target is None:
            target = {"hooks": []} if matcher is None else {"matcher": matcher, "hooks": []}
            groups.append(target)
        target.setdefault("hooks", []).append(entry())
        added += 1

    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"    thêm {added} hook entry vào {len(EVENTS)} event")


if __name__ == "__main__":
    main()
