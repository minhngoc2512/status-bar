"""The original panel: Claude Code session status from the hook spool."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from gi.repository import Gdk, GLib, Gio, Gtk

from .panel import Panel
from .sessions import (
    CONFIRM,
    EVENTS_DIR,
    IDLE,
    MAX_SPOOL_FILES,
    NO_HOOKS,
    NOT_FOUND,
    Store,
    claude_code_status,
)

# Animation lives in the tray *label*, not the icon. Measured on GNOME 42 with
# ubuntu-appindicators: swapping the icon file repaints at ~1 fps no matter how
# fast it is pushed, while label changes repaint at up to ~4 fps. Pushing the
# label faster than the cap is harmless (it is one string over D-Bus) and keeps
# the spinner near that ceiling.
#
# state -> (frames, milliseconds per push)
ANIM = {
    "working": ("◐◓◑◒", 120),
    "background": ("◐◓◑◒", 300),
    "confirm": ("●○", 500),
}


class ClaudePanel(Panel):
    section = "claude"
    default_icon = "claude-idle"

    def __init__(self, app) -> None:
        super().__init__(app)
        EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.store = Store()
        self.confirming: set[str] = set()
        self.pending_refresh = False
        self.anim_state: str | None = None
        self.anim_frame = 0
        self.anim_timer: int | None = None
        self.base_label = ""

        self.drain()

        monitor = Gio.File.new_for_path(str(EVENTS_DIR)).monitor_directory(
            Gio.FileMonitorFlags.NONE, None
        )
        monitor.connect("changed", self.on_dir_changed)
        self._monitor = monitor  # keep a reference alive

        # Safety net: catches missed inotify events and re-renders the age column.
        self.tick_timer = GLib.timeout_add_seconds(3, self.on_tick)

    # ---------------------------------------------------------------- events

    def on_dir_changed(self, *_args) -> bool:
        if not self.pending_refresh:
            self.pending_refresh = True
            GLib.timeout_add(120, self.on_debounced)
        return True

    def on_debounced(self) -> bool:
        self.pending_refresh = False
        if self.drain():
            self.refresh()
        return False

    def on_tick(self) -> bool:
        self.drain()
        self.store.prune()
        # Always refresh: the menu shows how long each session has been in state.
        self.refresh()
        return True

    def drain(self) -> bool:
        """Consume every spooled event file. Returns True if anything applied."""
        try:
            files = sorted(EVENTS_DIR.glob("*.json"))
        except OSError:
            return False
        if len(files) > MAX_SPOOL_FILES:
            for stale in files[: len(files) - MAX_SPOOL_FILES]:
                stale.unlink(missing_ok=True)
            files = files[len(files) - MAX_SPOOL_FILES :]

        touched = False
        for path in files:
            ppid = 0
            parts = path.name.split(".")
            if len(parts) >= 2 and parts[1].isdigit():
                ppid = int(parts[1])
            try:
                ev = json.loads(path.read_text())
            except Exception:
                path.unlink(missing_ok=True)
                continue
            path.unlink(missing_ok=True)
            if self.store.apply(ev, ppid):
                touched = True
        if touched:
            self.notify_new_confirms()
        return touched

    def notify_new_confirms(self) -> None:
        now = {s.sid for s in self.store.sessions.values() if s.state == CONFIRM}
        fresh = now - self.confirming
        self.confirming = now
        if not fresh or not self.cfg.get("notify", True):
            return
        if not shutil.which("notify-send"):
            return
        for sid in fresh:
            sess = self.store.sessions.get(sid)
            if not sess:
                continue
            detail = sess.render_detail(self.t) or self.t("notif.fallback")
            body = self.t("notif.body", project=sess.project, detail=detail)
            try:
                subprocess.Popen(
                    ["notify-send", "-a", "Claude Code", "-u", "normal", self.t("notif.title"), body],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                pass

    # ------------------------------------------------------------------- ui

    def animating(self, state: str) -> bool:
        return state in ANIM and bool(self.cfg.get("animate", True))

    def stop_anim(self) -> None:
        if self.anim_timer is not None:
            GLib.source_remove(self.anim_timer)
            self.anim_timer = None
        self.anim_state = None

    def apply_label(self) -> None:
        """Compose the tray label from the animation phase and the base text."""
        prefix = ""
        if self.anim_state is not None:
            frames = ANIM[self.anim_state][0]
            prefix = frames[self.anim_frame % len(frames)] + " "
        self.ind.set_label(prefix + self.base_label, "claude-status")

    def on_anim_tick(self) -> bool:
        if self.anim_state is None:
            self.anim_timer = None
            return False
        self.anim_frame += 1
        self.apply_label()
        return True

    def sync_anim(self, state: str) -> None:
        if not self.animating(state):
            self.stop_anim()
            return
        if state == self.anim_state and self.anim_timer is not None:
            return  # already running at the right speed; don't reset the phase
        self.stop_anim()
        self.anim_state = state
        self.anim_frame = 0
        self.anim_timer = GLib.timeout_add(ANIM[state][1], self.on_anim_tick)

    def refresh(self) -> None:
        if not self.visible:
            self.stop_anim()
            return
        state = self.store.worst()
        self.set_icon(f"claude-{state}", self.t(f"state.{state}"))

        label = self.t(f"bar.{state}") if self.cfg.get("claude.show_label", True) else ""
        if label:
            n = self.store.count(state)
            if n > 1:
                label = f"{label} {n}"
        self.base_label = label

        self.sync_anim(state if label else IDLE)
        self.apply_label()

        self.ind.set_title(self.t("title", n=len(self.store.sessions)))
        self.build_menu()

    def build_menu(self) -> None:
        t = self.t
        menu = Gtk.Menu()
        sessions = self.store.ordered()

        if not sessions:
            # An empty list means one of three things; say which.
            state = claude_code_status()
            if state == NOT_FOUND:
                menu.append(self.info_item(t("menu.noclaude")))
            elif state == NO_HOOKS:
                menu.append(self.info_item(t("menu.nohooks")))
                menu.append(self.info_item(t("menu.nohooks.fix")))
            else:
                menu.append(self.info_item(t("menu.empty")))
        else:
            for sess in sessions:
                item = Gtk.MenuItem(label=sess.summary(t))
                sub = Gtk.Menu()

                sub.append(self.info_item(sess.cwd or t("menu.nocwd")))
                if sess.permission_mode:
                    sub.append(self.info_item(t("menu.permission", mode=sess.permission_mode)))
                sub.append(Gtk.SeparatorMenuItem())

                sub.append(self.action_item(t("menu.open"), self.on_open_dir, sess.cwd))
                sub.append(self.action_item(t("menu.copy"), self.on_copy, sess.cwd))
                sub.append(self.action_item(t("menu.forget"), self.on_forget, sess.sid))

                item.set_submenu(sub)
                menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())

        notify = Gtk.CheckMenuItem(label=t("menu.notify"))
        notify.set_active(bool(self.cfg.get("notify", True)))
        notify.connect("toggled", self.on_toggle, "notify")
        menu.append(notify)

        animate = Gtk.CheckMenuItem(label=t("menu.animate"))
        animate.set_active(bool(self.cfg.get("animate", True)))
        animate.connect("toggled", self.on_toggle, "animate")
        menu.append(animate)

        menu.append(self.action_item(t("menu.clear"), self.on_clear))
        self.append_tail(menu)
        self.set_menu(menu)

    # -------------------------------------------------------------- actions

    def on_open_dir(self, _item, cwd: str) -> None:
        if cwd and os.path.isdir(cwd):
            try:
                subprocess.Popen(["xdg-open", cwd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass

    def on_copy(self, _item, text: str) -> None:
        if not text:
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        clipboard.store()

    def on_forget(self, _item, sid: str) -> None:
        self.store.sessions.pop(sid, None)
        self.refresh()

    def on_toggle(self, item: Gtk.CheckMenuItem, key: str) -> None:
        if self.cfg.set(key, item.get_active()):
            self.cfg.save()

    def on_clear(self, _item) -> None:
        self.store.sessions.clear()
        self.confirming.clear()
        self.refresh()

    def shutdown(self) -> None:
        self.stop_anim()
        if self.tick_timer is not None:
            GLib.source_remove(self.tick_timer)
            self.tick_timer = None
