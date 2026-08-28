"""Non-blocking JSON fetches for the GTK main loop.

Every network call in this app goes through here. urllib runs on a worker
thread and the result is handed back on the GTK thread via GLib.idle_add --
doing it inline would freeze the whole panel for the length of the request.
"""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Sequence

from gi.repository import GLib

USER_AGENT = "claude-status/2 (+https://github.com/; Linux tray indicator)"
DEFAULT_TIMEOUT = 12

Callback = Callable[[object, "str | None"], None]


def build_url(base: str, params: dict) -> str:
    return f"{base}?{urllib.parse.urlencode(params)}" if params else base


def describe(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return str(getattr(exc, "reason", exc)) or "network error"
    if isinstance(exc, socket.timeout):
        return "timeout"
    if isinstance(exc, ValueError):
        return "bad response"
    return exc.__class__.__name__


def _deliver(callback: Callback, data, error) -> bool:
    callback(data, error)
    return GLib.SOURCE_REMOVE


def fetch_json(url: str, callback: Callback, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Fetch and decode ``url``; ``callback(data, error)`` runs on the GTK thread.

    Exactly one of ``data`` / ``error`` is set. ``error`` is a short human
    string ("HTTP 451", "timeout") meant to be shown in a menu.
    """

    def work() -> None:
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
            data, error = json.loads(payload.decode("utf-8", "replace")), None
        except Exception as exc:  # noqa: BLE001 - every failure becomes a label
            data, error = None, describe(exc)
        GLib.idle_add(_deliver, callback, data, error)

    threading.Thread(target=work, daemon=True).start()


def fetch_first(urls: Sequence[str], accept, callback: Callback, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Try each URL in order, stopping at the first response ``accept`` likes.

    ``accept(data)`` returns a normalised value or None. Used for IP
    geolocation, where the free providers rate-limit independently.
    """
    urls = list(urls)

    def step(index: int) -> None:
        if index >= len(urls):
            callback(None, last[0] or "no provider answered")
            return

        def done(data, error) -> None:
            value = accept(data) if error is None else None
            if value is not None:
                callback(value, None)
                return
            last[0] = error or "unusable response"
            step(index + 1)

        fetch_json(urls[index], done, timeout=timeout)

    last: list[str | None] = [None]
    step(0)
