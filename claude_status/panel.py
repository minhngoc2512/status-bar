"""Shared plumbing for one tray indicator.

Each feature (Claude sessions, weather, crypto) is its own AppIndicator living
in the same process and GTK main loop. Turning a feature off sets its indicator
PASSIVE, which removes it from the top bar without tearing anything down.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):  # older systems ship the unprefixed one
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator

from gi.repository import Gtk  # noqa: E402

from .paths import APP_ID, icon_path

ACTIVE = AppIndicator.IndicatorStatus.ACTIVE
PASSIVE = AppIndicator.IndicatorStatus.PASSIVE


class Panel:
    """Base class: one indicator, one config section, one menu."""

    #: config section name; also the suffix of the AppIndicator id
    section = "panel"
    #: icon shown before the first refresh
    default_icon = "claude-idle"

    def __init__(self, app) -> None:
        self.app = app
        self.visible = False
        # The Claude panel keeps the original id so an existing panel layout
        # (position in the tray) survives the upgrade.
        ident = APP_ID if self.section == "claude" else f"{APP_ID}-{self.section}"
        self.ind = AppIndicator.Indicator.new(
            ident, icon_path(self.default_icon), AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.ind.set_status(PASSIVE)
        self.menu = Gtk.Menu()
        self.ind.set_menu(self.menu)

    # ------------------------------------------------------------- helpers

    @property
    def t(self):
        return self.app.t

    @property
    def cfg(self):
        return self.app.cfg

    def enabled(self) -> bool:
        return bool(self.cfg.get(f"{self.section}.enabled", False))

    def set_visible(self, on: bool) -> None:
        if on == self.visible:
            return
        self.visible = on
        self.ind.set_status(ACTIVE if on else PASSIVE)

    def set_icon(self, name: str, description: str = "") -> None:
        self.ind.set_icon_full(icon_path(name), description or name)

    def set_menu(self, menu: Gtk.Menu) -> None:
        menu.show_all()
        self.menu = menu  # keep a reference: GTK does not own it
        self.ind.set_menu(menu)

    @staticmethod
    def info_item(label: str) -> Gtk.MenuItem:
        item = Gtk.MenuItem(label=label)
        item.set_sensitive(False)
        return item

    @staticmethod
    def action_item(label: str, handler, *args) -> Gtk.MenuItem:
        item = Gtk.MenuItem(label=label)
        item.connect("activate", handler, *args)
        return item

    def append_tail(self, menu: Gtk.Menu, refresh: bool = False) -> None:
        """Settings / Quit block that every panel ends with."""
        menu.append(Gtk.SeparatorMenuItem())
        if refresh:
            menu.append(self.action_item(self.t("menu.refresh"), self.on_refresh_clicked))
        menu.append(self.action_item(self.t("menu.settings"), self.on_settings_clicked))
        menu.append(self.action_item(self.t("menu.quit"), self.on_quit_clicked))

    # ------------------------------------------------------------- actions

    def on_settings_clicked(self, _item) -> None:
        self.app.open_settings()

    def on_quit_clicked(self, _item) -> None:
        self.app.quit()

    def on_refresh_clicked(self, _item) -> None:
        self.reload()

    # -------------------------------------------------- subclass interface

    def reload(self) -> None:
        """Re-fetch remote data, if the panel has any."""

    def apply_config(self) -> None:
        """React to a settings change; called once at startup too."""
        self.set_visible(self.enabled())
        self.refresh()

    def refresh(self) -> None:
        """Re-render icon, label and menu from local state."""

    def shutdown(self) -> None:
        """Stop timers before the main loop ends."""
