"""Claude Code session table: hook events in, one state row per session out."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from .i18n import Lang

BASE_DIR = Path(os.environ.get("CLAUDE_STATUS_DIR", str(Path.home() / ".cache/claude-status")))
EVENTS_DIR = BASE_DIR / "events"

# Drop a session that has been silent for this long (crash, kill -9, closed tab).
SESSION_TTL = 6 * 3600
# Refuse to let the spool grow without bound if the indicator was off for a while.
MAX_SPOOL_FILES = 5000

CONFIRM, ERROR, WORKING, BACKGROUND, IDLE = "confirm", "error", "working", "background", "idle"
# Worst state first: this is what the tray icon shows.
PRIORITY = [CONFIRM, ERROR, WORKING, BACKGROUND, IDLE]

DOT = {CONFIRM: "🟠", ERROR: "🔴", WORKING: "🔵", BACKGROUND: "🟢", IDLE: "⚪"}


CLAUDE_DIR = Path.home() / ".claude"
CLAUDE_SETTINGS = CLAUDE_DIR / "settings.json"

# Nothing here is expensive, but it runs from a menu rebuilt every few seconds,
# so the answer is cached briefly.
PROBE_TTL = 30.0
_probe: tuple[float, str] = (0.0, "")

OK, NO_HOOKS, NOT_FOUND = "ok", "no_hooks", "not_found"


def hook_installed(settings: dict) -> bool:
    """Is any claude-status hook wired into a Claude Code settings dict?

    Matched on the script name rather than a full path: the checkout install and
    the .deb put emit.sh in different places, and both count.
    """
    for groups in (settings.get("hooks") or {}).values():
        for group in groups or []:
            for entry in group.get("hooks") or []:
                if str(entry.get("command", "")).endswith("emit.sh"):
                    return True
    return False


def claude_code_status(now: float | None = None) -> str:
    """One of OK / NO_HOOKS / NOT_FOUND.

    The Claude panel is useless without Claude Code, and just as useless when
    Claude Code is there but nobody ran claude-status-hooks -- in both cases the
    menu would sit empty with no hint why.
    """
    global _probe
    now = time.time() if now is None else now
    stamp, cached = _probe
    if cached and now - stamp < PROBE_TTL:
        return cached

    if shutil.which("claude") is None and not CLAUDE_DIR.is_dir():
        state = NOT_FOUND
    else:
        try:
            settings = json.loads(CLAUDE_SETTINGS.read_text())
        except Exception:
            settings = {}
        state = OK if hook_installed(settings) else NO_HOOKS

    _probe = (now, state)
    return state


def human_age(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}"


class Session:
    """One Claude Code session's current state.

    ``detail`` is a (kind, value) pair rather than a rendered string so the
    menu can be re-rendered in another language without replaying events.
    ``kind`` is either "raw" (value is a tool or agent name, never translated)
    or a STRINGS key suffix under ``detail.``.
    """

    def __init__(self, sid: str) -> None:
        self.sid = sid
        self.cwd = ""
        self.state = IDLE
        self.detail: tuple[str, object] = ("raw", "")
        self.since = time.time()
        self.last_seen = time.time()
        self.permission_mode = ""
        self.subagents = 0
        self.ppid = 0
        # Handed to us by every hook payload; see claude_status/tokens.py.
        self.transcript = ""

    @property
    def project(self) -> str:
        return os.path.basename(self.cwd.rstrip("/")) or self.cwd or self.sid[:8]

    def set_state(self, state: str, detail: tuple[str, object] = ("raw", "")) -> None:
        if state != self.state or detail != self.detail:
            self.since = time.time()
        self.state = state
        self.detail = detail

    def render_detail(self, t: Lang) -> str:
        kind, value = self.detail
        if kind == "raw":
            return str(value)
        if kind == "tasks":
            return t("detail.tasks", n=value)
        return t(f"detail.{kind}")

    def summary(self, t: Lang) -> str:
        state_text = t(f"state.{self.state}")
        detail = self.render_detail(t)
        bits = [self.project, f"{state_text}: {detail}" if detail else state_text]
        if self.subagents:
            bits.append(t("detail.subagents", n=self.subagents))
        bits.append(human_age(time.time() - self.since))
        return f"{DOT[self.state]}  " + " · ".join(bits)


class Store:
    """Applies hook events to the session table."""

    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    def apply(self, ev: dict, ppid: int) -> str | None:
        """Returns the session id touched, or None if the event was ignored."""
        sid = ev.get("session_id")
        if not sid:
            return None
        name = ev.get("hook_event_name", "")

        if name == "SessionEnd":
            self.sessions.pop(sid, None)
            return sid

        sess = self.sessions.get(sid)
        if sess is None:
            sess = self.sessions[sid] = Session(sid)
        sess.last_seen = time.time()
        sess.ppid = ppid or sess.ppid
        if ev.get("cwd"):
            sess.cwd = ev["cwd"]
        if ev.get("permission_mode"):
            sess.permission_mode = ev["permission_mode"]
        if ev.get("transcript_path"):
            sess.transcript = ev["transcript_path"]

        if name == "SessionStart":
            sess.subagents = 0
            sess.set_state(IDLE)
        elif name == "UserPromptSubmit":
            sess.set_state(WORKING, ("processing", None))
        elif name == "PreToolUse":
            sess.set_state(WORKING, ("raw", ev.get("tool_name", "tool")))
        elif name in ("PostToolUse", "PostToolUseFailure"):
            sess.set_state(WORKING, ("processing", None))
        elif name == "PermissionRequest":
            sess.set_state(CONFIRM, ("raw", ev.get("tool_name", "")))
        elif name == "Stop":
            tasks = ev.get("background_tasks") or []
            sess.set_state(BACKGROUND, ("tasks", len(tasks))) if tasks else sess.set_state(IDLE)
        elif name == "StopFailure":
            sess.set_state(ERROR, ("api", None))
        elif name == "SubagentStart":
            sess.subagents += 1
            sess.set_state(WORKING, ("raw", ev.get("agent_type", "subagent")))
        elif name == "SubagentStop":
            sess.subagents = max(0, sess.subagents - 1)
        elif name == "Notification":
            kind = ev.get("notification_type", "")
            if kind in ("permission_prompt", "agent_needs_input"):
                sess.set_state(CONFIRM, ("raw", ev.get("title", "")))
            elif kind in ("elicitation_dialog", "elicitation_url_dialog"):
                sess.set_state(CONFIRM, ("mcp", None))
            elif kind == "elicitation_complete":
                sess.set_state(WORKING, ("processing", None))
            elif kind == "idle_prompt":
                sess.set_state(IDLE)
        else:
            return None
        return sid

    def prune(self) -> bool:
        cutoff = time.time() - SESSION_TTL
        stale = [s for s, v in self.sessions.items() if v.last_seen < cutoff]
        for s in stale:
            del self.sessions[s]
        return bool(stale)

    def worst(self) -> str:
        present = {s.state for s in self.sessions.values()}
        for state in PRIORITY:
            if state in present:
                return state
        return IDLE

    def count(self, state: str) -> int:
        return sum(1 for s in self.sessions.values() if s.state == state)

    def ordered(self) -> list[Session]:
        rank = {s: i for i, s in enumerate(PRIORITY)}
        return sorted(self.sessions.values(), key=lambda s: (rank[s.state], -s.since))
