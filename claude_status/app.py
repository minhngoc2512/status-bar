"""Wires the panels, the config and the settings window into one GTK app."""

from __future__ import annotations

import fcntl
import shutil
import subprocess

from gi.repository import GLib, Gtk

from .claude_panel import ClaudePanel
from .config import Config
from .crypto import CryptoPanel
from .i18n import Lang, default_lang
from .panel import Panel, install_font_metrics
from .prefs import Preferences
from .system_panel import SystemPanel
from .sessions import BASE_DIR
from .weather import WeatherPanel

# How often the weather/crypto menus are rebuilt so their "updated N ago" line
# does not go stale between network refreshes.
AGE_TICK_SECONDS = 20


class FallbackPanel(Panel):
    """Escape hatch shown when every real indicator is switched off.

    Without it the user would have no way back into Settings or Quit.
    """

    section = "fallback"
    default_icon = "claude-idle"

    def refresh(self) -> None:
        menu = Gtk.Menu()
        menu.append(self.info_item(self.t("menu.alloff")))
        self.append_tail(menu)
        self.set_menu(menu)


class App:
    def __init__(self) -> None:
        install_font_metrics()
        self.cfg = Config()
        self.t = Lang(self.cfg.get("lang") or default_lang())
        self.prefs: Preferences | None = None

        self.panels: list[Panel] = [
            ClaudePanel(self),
            WeatherPanel(self),
            CryptoPanel(self),
            SystemPanel(self),
        ]
        self.fallback = FallbackPanel(self)

        self.cfg.subscribe(self.on_config)
        for panel in self.panels:
            panel.apply_config()
        self.sync_fallback()

        GLib.timeout_add_seconds(AGE_TICK_SECONDS, self.on_age_tick)

    # ----------------------------------------------------------------- config

    def on_config(self, changed: set[str]) -> None:
        for panel in self.panels:
            if panel.section in changed:
                panel.apply_config()
            elif "general" in changed:
                # Language / notify / animate: re-render, don't re-fetch.
                panel.set_visible(panel.enabled())
                panel.refresh()
        self.sync_fallback()
        if self.prefs is not None:
            self.prefs.on_config_changed(changed)

    def sync_fallback(self) -> None:
        alone = not any(panel.visible for panel in self.panels)
        self.fallback.set_visible(alone)
        if alone:
            self.fallback.refresh()

    def on_age_tick(self) -> bool:
        for panel in self.panels:
            # The system panel drives its own faster timer; these two only
            # need a nudge so their "updated N ago" line does not go stale.
            if panel.section in ("weather", "crypto") and panel.visible:
                panel.refresh()
        return True

    # ------------------------------------------------------------------- ui

    def open_settings(self) -> None:
        if self.prefs is None:
            self.prefs = Preferences(self)
        else:
            self.prefs.load_values()
        self.prefs.show_all()
        self.prefs.present()

    def set_language(self, code: str) -> None:
        if code == self.t.code:
            return
        stale, self.prefs = self.prefs, None
        self.t = Lang(code)
        self.cfg.set("lang", code)
        self.cfg.save()  # fans out to every panel as a "general" change
        self.fallback.refresh()
        if stale is not None:
            # The window is built with the old strings; swap it out once we are
            # back out of the widget's own signal handler.
            GLib.idle_add(self.rebuild_prefs, stale, stale.get_visible())

    def rebuild_prefs(self, stale: Preferences, reopen: bool) -> bool:
        stale.destroy()
        if reopen:
            self.open_settings()
        return GLib.SOURCE_REMOVE

    def quit(self) -> None:
        for panel in self.panels:
            panel.shutdown()
        Gtk.main_quit()


LOCK_PATH = BASE_DIR / "indicator.lock"


def acquire_lock():
    """Take the single-instance lock, or return None if another copy holds it.

    Two copies are easy to end up with -- the systemd user service plus a click
    on the desktop entry -- and they do real damage rather than merely showing
    two icons: drain() unlinks each event file as it reads it, so the two split
    the spool between them. Measured with three sessions and twelve events, each
    copy lost a whole session and one of them was left showing "working" for a
    session that had already asked for confirmation. A permission prompt can go
    unseen that way.

    flock is released by the kernel when the process dies, so a killed indicator
    leaves nothing stale behind.
    """
    try:
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        handle = open(LOCK_PATH, "w")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return handle


def report_already_running() -> None:
    """Say so where it will be seen: the journal, and the desktop if possible.

    Launching from the app grid while the service is running would otherwise
    look like the click did nothing at all.
    """
    print("claude-status is already running; leaving the existing one alone.")
    if shutil.which("notify-send"):
        try:
            subprocess.Popen(
                ["notify-send", "-a", "Claude Status", "Claude Status",
                 "Đã có một bản đang chạy."],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass


def main() -> None:
    lock = acquire_lock()
    if lock is None:
        report_already_running()
        return
    app = App()
    app.lock = lock  # keep the descriptor alive for the life of the process
    Gtk.main()
