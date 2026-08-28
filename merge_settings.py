#!/usr/bin/env python3
"""Merge the status-indicator hooks into ~/.claude/settings.json.

Other tools' hooks are preserved: entries are appended to each event's list, and
re-running is a no-op because entries are matched on the command string.

Hooks from a *different* copy of this tool are removed rather than kept. Both
install routes exist -- the .deb at /usr/lib/claude-status and a git checkout --
and leaving both wired up makes every Claude Code event write two spool files,
which is pure waste and makes the settings file look like it has been through a
fight. Whichever copy runs this script wins.
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


def claude_code_present() -> bool:
    return shutil.which("claude") is not None or SETTINGS.parent.is_dir()


def is_our_hook(command) -> bool:
    """Any claude-status hook, wherever it was installed from."""
    return str(command).endswith("emit.sh")


def prune_foreign(settings: dict, keep: str) -> list[str]:
    """Drop our hooks that point somewhere other than ``keep``.

    Returns the removed command strings so the caller can say what it did.
    Mutates ``settings`` in place, and takes empty groups and events with it --
    leaving {"hooks": []} behind would be valid but is just litter.
    """
    removed = []
    hooks = settings.get("hooks") or {}
    for event in list(hooks):
        groups = hooks[event] or []
        for group in groups:
            entries = group.get("hooks") or []
            kept = []
            for entry in entries:
                command = entry.get("command", "")
                if is_our_hook(command) and command != keep:
                    removed.append(command)
                else:
                    kept.append(entry)
            group["hooks"] = kept
        hooks[event] = [g for g in groups if g.get("hooks")]
        if not hooks[event]:
            del hooks[event]
    return removed


def main() -> None:
    if not claude_code_present():
        # Not an error: wiring the hooks up in advance is harmless and they will
        # work the moment Claude Code is installed. Just do not let it look like
        # the indicator is broken afterwards.
        print("    LƯU Ý: không tìm thấy Claude Code trên máy này.")
        print("    Hook vẫn được cài và sẽ hoạt động ngay khi bạn cài Claude Code.")
        print("    Trong lúc đó, chỉ báo Claude sẽ rỗng — thời tiết, crypto và")
        print("    theo dõi hệ thống vẫn chạy bình thường.")

    settings = {}
    if SETTINGS.exists():
        settings = json.loads(SETTINGS.read_text())
        backup = SETTINGS.with_suffix(f".json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(SETTINGS, backup)
        print(f"    backup: {backup}")

    stale = prune_foreign(settings, HOOK)
    if stale:
        where = sorted(set(stale))
        print(f"    gỡ {len(stale)} hook entry của bản cài khác:")
        for path in where:
            print(f"      {path}")

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
