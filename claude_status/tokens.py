"""Token counts for a Claude Code session, tailed from its transcript.

Where this comes from, and what it deliberately is not:

  * Every hook payload carries ``transcript_path``, so the file is handed to us
    rather than guessed. No hook payload carries token counts -- checked against
    real PreToolUse, PostToolUse, PermissionRequest and Notification events.
  * The transcript records ``message.usage`` per API call, which is where the
    numbers below come from.
  * Nothing on disk records the *limit*. There is no usage, quota or rate-limit
    file anywhere under ~/.claude; Claude Code learns its remaining quota from
    response headers at request time and does not persist it. So this reports
    what has been spent, and cannot report what is left.

Only ``message.usage`` is read. Lines without the substring "usage" are skipped
without being parsed at all, which both halves the work and means most of the
conversation is never decoded: measured on a 7.6 MB, 2115-line transcript, a
full parse costs 39 ms against 21.8 ms prefiltered. After the first pass only
newly appended bytes are read, which costs microseconds.
"""

from __future__ import annotations

import json
import os
import time

FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")

NEEDLE = b'"usage"'


def format_count(value) -> str:
    """1342 -> "1.3K", 1172193 -> "1.2M", 265422863 -> "265M"."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if number >= limit:
            scaled = number / limit
            return f"{scaled:.1f}{suffix}" if scaled < 100 else f"{scaled:.0f}{suffix}"
    return f"{number:.0f}"


def remaining(used_percentage) -> float:
    """Share of a plan window still available.

    Claude Code reports how much has been *used*; the indicator shows what is
    left, so the bar and the menu never disagree by being two sides of the same
    number. Clamped: a window can report slightly over 100.
    """
    try:
        return max(0.0, min(100.0, 100.0 - float(used_percentage)))
    except (TypeError, ValueError):
        return 0.0


def cache_hit(totals: dict) -> float | None:
    """Share of prompt tokens served from cache, as a percentage.

    Formula checked against CodeBurn's own display: it reports 96.6% for
    37.9M cached, 1.3M written and 1.5K in, and cached/(cached+written+in)
    gives 96.7%.
    """
    read = totals.get("cache_read_input_tokens", 0)
    denominator = read + totals.get("cache_creation_input_tokens", 0) + totals.get("input_tokens", 0)
    return 100.0 * read / denominator if denominator else None


class TokenMeter:
    """Running totals for one transcript, updated from the bytes appended since
    the last look."""

    def __init__(self) -> None:
        self.path = ""
        self.offset = 0
        self.key: tuple | None = None  # (st_dev, st_ino) of the file being read
        self.partial = b""
        self.calls = 0
        self.totals = dict.fromkeys(FIELDS, 0)
        self.seen = False

    def reset(self, path: str) -> None:
        self.__init__()
        self.path = path

    @property
    def output(self) -> int:
        return self.totals["output_tokens"]

    @property
    def cached(self) -> int:
        return self.totals["cache_read_input_tokens"]

    def update(self, path: str) -> bool:
        """Read what is new. Returns True when anything was added."""
        if not path:
            return False
        if path != self.path:
            self.reset(path)
        try:
            stat = os.stat(path)
        except OSError:
            return False

        key = (stat.st_dev, stat.st_ino)
        # A different file behind the same name, or one that shrank, means the
        # offset is meaningless -- start over rather than read from the middle
        # of a line.
        if self.key is not None and (key != self.key or stat.st_size < self.offset):
            self.reset(path)
        self.key = key

        if stat.st_size == self.offset:
            self.seen = True
            return False

        try:
            with open(path, "rb") as handle:
                handle.seek(self.offset)
                chunk = handle.read()
                self.offset = handle.tell()
        except OSError:
            return False

        data = self.partial + chunk
        lines = data.split(b"\n")
        # The last piece may be half a line if the file is being written.
        self.partial = lines.pop()

        added = False
        for line in lines:
            if NEEDLE not in line:
                continue
            try:
                record = json.loads(line)
            except Exception:  # noqa: BLE001 - a torn line is not worth a traceback
                continue
            usage = (record.get("message") or {}).get("usage")
            if not isinstance(usage, dict):
                continue
            self.calls += 1
            added = True
            for field in FIELDS:
                value = usage.get(field)
                if isinstance(value, int):
                    self.totals[field] += value
        self.seen = True
        return added


class DailyUsage:
    """Totals across every transcript touched recently, not just live sessions.

    Scanning is not cheap the first time -- measured over 32 transcripts
    totalling 112 MB, a full pass is ~390 ms -- so it belongs on a worker thread
    at a slow cadence. Every file keeps its own offset, so later passes read only
    what was appended and cost almost nothing.
    """

    def __init__(self, hours: int = 24) -> None:
        self.hours = hours
        self.meters: dict[str, TokenMeter] = {}
        # Published as one object so the GTK thread cannot read a half-updated
        # set of numbers while the worker is partway through a scan.
        self.snapshot = {"totals": dict.fromkeys(FIELDS, 0), "calls": 0, "sessions": 0, "at": 0.0}

    def transcripts(self, root=None) -> list[str]:
        base = root or (os.path.expanduser("~") + "/.claude/projects")
        cutoff = time.time() - self.hours * 3600
        found = []
        try:
            for project in os.scandir(base):
                if not project.is_dir():
                    continue
                for entry in os.scandir(project.path):
                    if not entry.name.endswith(".jsonl"):
                        continue
                    try:
                        if entry.stat().st_mtime >= cutoff:
                            found.append(entry.path)
                    except OSError:
                        continue
        except OSError:
            return []
        return found

    def scan(self, root=None) -> None:
        """Blocking. Call from a worker thread."""
        live = self.transcripts(root)
        # Drop meters for transcripts that fell out of the window, so the
        # totals describe the window rather than everything ever seen.
        for path in list(self.meters):
            if path not in live:
                del self.meters[path]
        for path in live:
            meter = self.meters.get(path)
            if meter is None:
                self.meters[path] = meter = TokenMeter()
            meter.update(path)

        totals = dict.fromkeys(FIELDS, 0)
        calls = 0
        sessions = 0
        for meter in self.meters.values():
            if not meter.calls:
                continue
            sessions += 1
            calls += meter.calls
            for field in FIELDS:
                totals[field] += meter.totals[field]
        self.snapshot = {"totals": totals, "calls": calls, "sessions": sessions, "at": time.time()}
