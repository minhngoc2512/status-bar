"""The settings window: one tab per indicator, changes applied immediately.

There is no OK/Cancel. Every widget writes straight into Config and saves,
which notifies the panels -- the same path the tray checkboxes use.
"""

from __future__ import annotations

from gi.repository import GLib, Gtk

from . import crypto as crypto_mod
from . import gpu as gpu_mod
from . import sessions as sessions_mod
from . import system as sysinfo
from . import weather as weather_mod
from .i18n import LANGUAGES


def frame(title: str) -> tuple[Gtk.Frame, Gtk.Box]:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.set_border_width(10)
    holder = Gtk.Frame(label=title)
    holder.add(box)
    return holder, box


def switch_row(label: str) -> tuple[Gtk.Box, Gtk.Switch]:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    text = Gtk.Label(label=label, xalign=0)
    text.set_hexpand(True)
    switch = Gtk.Switch()
    switch.set_halign(Gtk.Align.END)
    row.pack_start(text, True, True, 0)
    row.pack_start(switch, False, False, 0)
    return row, switch


def control_row(label: str, control: Gtk.Widget) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    text = Gtk.Label(label=label, xalign=0)
    text.set_hexpand(True)
    control.set_halign(Gtk.Align.END)
    row.pack_start(text, True, True, 0)
    row.pack_start(control, False, False, 0)
    return row


def scroller(child: Gtk.Widget, height: int) -> Gtk.ScrolledWindow:
    view = Gtk.ScrolledWindow()
    view.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    view.set_min_content_height(height)
    view.add(child)
    return view


def dim(text: str) -> Gtk.Label:
    label = Gtk.Label(xalign=0)
    label.set_markup(f'<span alpha="70%"><small>{GLib.markup_escape_text(text)}</small></span>')
    label.set_line_wrap(True)
    return label


class Preferences(Gtk.Window):
    def __init__(self, app) -> None:
        super().__init__(title=app.t("prefs.title"))
        self.app = app
        self.t = app.t
        self.cfg = app.cfg
        # Set while load_values() is pushing config into widgets, so the
        # widgets' own signal handlers don't write it straight back.
        self.loading = False
        # Binance's full pair list, fetched once per window and filtered locally.
        self.catalogue: list[str] | None = None
        self.catalogue_error: str | None = None
        self.catalogue_loading = False
        self.search_timer: int | None = None

        self.set_default_size(480, 640)
        self.set_border_width(0)
        self.connect("delete-event", self.on_close_request)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(outer)

        notebook = Gtk.Notebook()
        notebook.set_border_width(8)
        for build, title in (
            (self.build_general, "prefs.tab.general"),
            (self.build_weather, "prefs.tab.weather"),
            (self.build_crypto, "prefs.tab.crypto"),
            (self.build_system, "prefs.tab.system"),
        ):
            notebook.append_page(scroller(build(), 0), Gtk.Label(label=self.t(title)))
        outer.pack_start(notebook, True, True, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.set_border_width(10)
        close = Gtk.Button(label=self.t("prefs.close"))
        close.set_halign(Gtk.Align.END)
        close.connect("clicked", lambda _b: self.hide())
        footer.pack_end(close, False, False, 0)
        outer.pack_start(footer, False, False, 0)

        self.load_values()

    # ------------------------------------------------------------ scaffolding

    @staticmethod
    def page() -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(10)
        return box

    def write(self, path: str, value) -> None:
        if self.loading:
            return
        if self.cfg.set(path, value):
            self.cfg.save()

    def on_close_request(self, *_args) -> bool:
        self.hide()
        return True  # hide instead of destroying: reopening keeps the state

    # ---------------------------------------------------------------- general

    def build_general(self) -> Gtk.Box:
        page = self.page()

        holder, box = frame(self.t("prefs.indicators"))
        row, self.sw_claude = switch_row(self.t("prefs.show.claude"))
        box.pack_start(row, False, False, 0)
        # Same treatment as a machine with no readable GPU: say what is missing
        # instead of offering a switch that cannot do anything.
        self.label_claude = dim("")
        box.pack_start(self.label_claude, False, False, 0)
        row, self.sw_weather = switch_row(self.t("prefs.show.weather"))
        box.pack_start(row, False, False, 0)
        row, self.sw_crypto = switch_row(self.t("prefs.show.crypto"))
        box.pack_start(row, False, False, 0)
        row, self.sw_system = switch_row(self.t("prefs.show.system"))
        box.pack_start(row, False, False, 0)
        for switch, section in (
            (self.sw_claude, "claude"),
            (self.sw_weather, "weather"),
            (self.sw_crypto, "crypto"),
            (self.sw_system, "system"),
        ):
            switch.connect("notify::active", self.on_toggle_section, section)
        page.pack_start(holder, False, False, 0)

        holder, box = frame(self.t("prefs.behaviour"))
        self.combo_lang = Gtk.ComboBoxText()
        for code, name in LANGUAGES:
            self.combo_lang.append(code, name)
        self.combo_lang.connect("changed", self.on_lang_changed)
        box.pack_start(control_row(self.t("menu.language"), self.combo_lang), False, False, 0)

        self.chk_notify = Gtk.CheckButton(label=self.t("menu.notify"))
        self.chk_notify.connect("toggled", lambda w: self.write("notify", w.get_active()))
        box.pack_start(self.chk_notify, False, False, 0)

        self.chk_animate = Gtk.CheckButton(label=self.t("menu.animate"))
        self.chk_animate.connect("toggled", lambda w: self.write("animate", w.get_active()))
        box.pack_start(self.chk_animate, False, False, 0)

        self.chk_claude_label = Gtk.CheckButton(label=self.t("prefs.showlabel.claude"))
        self.chk_claude_label.connect(
            "toggled", lambda w: self.write("claude.show_label", w.get_active())
        )
        box.pack_start(self.chk_claude_label, False, False, 0)

        self.chk_tokens = Gtk.CheckButton(label=self.t("prefs.showtokens"))
        self.chk_tokens.connect("toggled", lambda w: self.write("claude.show_tokens", w.get_active()))
        box.pack_start(self.chk_tokens, False, False, 0)
        box.pack_start(dim(self.t("prefs.showtokens.note")), False, False, 0)
        page.pack_start(holder, False, False, 0)

        return page

    def on_toggle_section(self, switch: Gtk.Switch, _param, section: str) -> None:
        self.write(f"{section}.enabled", switch.get_active())

    def on_lang_changed(self, combo: Gtk.ComboBoxText) -> None:
        code = combo.get_active_id()
        if self.loading or not code or code == self.app.t.code:
            return
        self.app.set_language(code)

    # ---------------------------------------------------------------- weather

    def build_weather(self) -> Gtk.Box:
        page = self.page()

        row, self.sw_weather_on = switch_row(self.t("prefs.show.weather"))
        self.sw_weather_on.connect("notify::active", self.on_toggle_section, "weather")
        page.pack_start(row, False, False, 0)

        holder, box = frame(self.t("prefs.location"))
        self.radio_auto = Gtk.RadioButton.new_with_label_from_widget(None, self.t("prefs.loc.auto"))
        self.radio_manual = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_auto, self.t("prefs.loc.manual")
        )
        self.radio_auto.connect("toggled", self.on_mode_changed)
        box.pack_start(self.radio_auto, False, False, 0)
        box.pack_start(self.radio_manual, False, False, 0)

        search = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry_place = Gtk.Entry()
        self.entry_place.set_placeholder_text(self.t("prefs.search.placeholder"))
        self.entry_place.connect("activate", lambda _e: self.on_search())
        button = Gtk.Button(label=self.t("prefs.search"))
        button.connect("clicked", lambda _b: self.on_search())
        search.pack_start(self.entry_place, True, True, 0)
        search.pack_start(button, False, False, 0)
        box.pack_start(search, False, False, 0)

        self.list_places = Gtk.ListBox()
        self.list_places.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_places.connect("row-activated", self.on_place_chosen)
        box.pack_start(scroller(self.list_places, 130), True, True, 0)

        self.label_search = dim("")
        box.pack_start(self.label_search, False, False, 0)
        self.label_place = Gtk.Label(xalign=0)
        self.label_place.set_line_wrap(True)
        box.pack_start(self.label_place, False, False, 0)
        page.pack_start(holder, True, True, 0)

        holder, box = frame(self.t("prefs.display"))
        self.combo_unit = Gtk.ComboBoxText()
        self.combo_unit.append("celsius", self.t("prefs.unit.c"))
        self.combo_unit.append("fahrenheit", self.t("prefs.unit.f"))
        self.combo_unit.connect(
            "changed", lambda c: self.write("weather.unit", c.get_active_id() or "celsius")
        )
        box.pack_start(control_row(self.t("prefs.unit"), self.combo_unit), False, False, 0)

        self.spin_weather = Gtk.SpinButton.new_with_range(5, 180, 5)
        self.spin_weather.connect(
            "value-changed", lambda s: self.write("weather.refresh_minutes", s.get_value_as_int())
        )
        box.pack_start(control_row(self.t("prefs.refresh.min"), self.spin_weather), False, False, 0)

        self.chk_weather_label = Gtk.CheckButton(label=self.t("prefs.showlabel"))
        self.chk_weather_label.connect(
            "toggled", lambda w: self.write("weather.show_label", w.get_active())
        )
        box.pack_start(self.chk_weather_label, False, False, 0)
        page.pack_start(holder, False, False, 0)

        return page

    def on_mode_changed(self, _button) -> None:
        if self.loading:
            return
        mode = "auto" if self.radio_auto.get_active() else "manual"
        if self.cfg.set("weather.mode", mode):
            # A fresh auto lookup should not reuse a stale cached position.
            if mode == "auto":
                self.cfg.set("weather.detected", None)
            self.cfg.save()

    def on_search(self) -> None:
        query = self.entry_place.get_text().strip()
        if not query:
            return
        self.label_search.set_markup(f"<small>{GLib.markup_escape_text(self.t('prefs.search.busy'))}</small>")
        for child in self.list_places.get_children():
            self.list_places.remove(child)

        def done(results, error) -> None:
            if error is not None:
                self.label_search.set_markup(
                    f"<small>{GLib.markup_escape_text(self.t('prefs.search.failed', reason=error))}</small>"
                )
                return
            if not results:
                self.label_search.set_markup(
                    f"<small>{GLib.markup_escape_text(self.t('prefs.search.empty'))}</small>"
                )
                return
            self.label_search.set_markup("")
            for result in results:
                row = Gtk.ListBoxRow()
                label = Gtk.Label(label=weather_mod.place_label(result), xalign=0)
                label.set_margin_start(6)
                label.set_margin_end(6)
                label.set_margin_top(4)
                label.set_margin_bottom(4)
                row.add(label)
                row.result = result
                self.list_places.add(row)
            self.list_places.show_all()

        weather_mod.geocode(query, self.app.t.code, done)

    def on_place_chosen(self, _list, row: Gtk.ListBoxRow) -> None:
        result = getattr(row, "result", None)
        if not result:
            return
        self.cfg.set("weather.mode", "manual")
        self.cfg.set("weather.latitude", result.get("latitude"))
        self.cfg.set("weather.longitude", result.get("longitude"))
        self.cfg.set("weather.place", weather_mod.place_label(result))
        self.cfg.save()
        self.loading = True
        self.radio_manual.set_active(True)
        self.loading = False
        self.refresh_place_label()

    def refresh_place_label(self) -> None:
        if self.cfg.get("weather.mode") == "manual":
            place = self.cfg.get("weather.place") or ""
        else:
            place = (self.cfg.get("weather.detected") or {}).get("place") or ""
        self.label_place.set_text(
            self.t("prefs.current", place=place) if place else self.t("prefs.current.none")
        )

    # ----------------------------------------------------------------- crypto

    def build_crypto(self) -> Gtk.Box:
        page = self.page()

        row, self.sw_crypto_on = switch_row(self.t("prefs.show.crypto"))
        self.sw_crypto_on.connect("notify::active", self.on_toggle_section, "crypto")
        page.pack_start(row, False, False, 0)

        holder, box = frame(self.t("prefs.symbols"))
        self.list_symbols = Gtk.ListBox()
        self.list_symbols.set_selection_mode(Gtk.SelectionMode.NONE)
        box.pack_start(scroller(self.list_symbols, 108), True, True, 0)
        page.pack_start(holder, True, True, 0)

        holder, box = frame(self.t("prefs.symbol.add"))
        adder = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry_symbol = Gtk.Entry()
        self.entry_symbol.set_placeholder_text(self.t("prefs.symbol.placeholder"))
        self.entry_symbol.connect("changed", self.on_symbol_typed)
        self.entry_symbol.connect("activate", lambda _e: self.on_add_symbol())
        button = Gtk.Button(label=self.t("prefs.add"))
        button.connect("clicked", lambda _b: self.on_add_symbol())
        adder.pack_start(self.entry_symbol, True, True, 0)
        adder.pack_start(button, False, False, 0)
        box.pack_start(adder, False, False, 0)

        self.list_matches = Gtk.ListBox()
        self.list_matches.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_matches.connect("row-activated", self.on_suggestion_chosen)
        box.pack_start(scroller(self.list_matches, 132), True, True, 0)

        self.label_symbol = dim("")
        box.pack_start(self.label_symbol, False, False, 0)
        page.pack_start(holder, True, True, 0)

        holder, box = frame(self.t("prefs.display"))
        self.combo_bar = Gtk.ComboBoxText()
        self.combo_bar.connect("changed", self.on_bar_changed)
        box.pack_start(control_row(self.t("prefs.barsymbol"), self.combo_bar), False, False, 0)

        self.spin_crypto = Gtk.SpinButton.new_with_range(15, 600, 15)
        self.spin_crypto.connect(
            "value-changed", lambda s: self.write("crypto.refresh_seconds", s.get_value_as_int())
        )
        box.pack_start(control_row(self.t("prefs.refresh.sec"), self.spin_crypto), False, False, 0)

        self.chk_crypto_label = Gtk.CheckButton(label=self.t("prefs.showlabel"))
        self.chk_crypto_label.connect(
            "toggled", lambda w: self.write("crypto.show_label", w.get_active())
        )
        box.pack_start(self.chk_crypto_label, False, False, 0)

        self.chk_change = Gtk.CheckButton(label=self.t("prefs.showchange"))
        self.chk_change.connect("toggled", lambda w: self.write("crypto.show_change", w.get_active()))
        box.pack_start(self.chk_change, False, False, 0)

        self.entry_endpoint = Gtk.Entry()
        self.entry_endpoint.set_width_chars(24)
        self.entry_endpoint.connect("activate", self.on_endpoint_set)
        self.entry_endpoint.connect("focus-out-event", self.on_endpoint_set)
        box.pack_start(control_row(self.t("prefs.endpoint"), self.entry_endpoint), False, False, 0)
        page.pack_start(holder, False, False, 0)

        return page

    def on_endpoint_set(self, entry: Gtk.Entry, *_args) -> None:
        if self.write("crypto.endpoint", entry.get_text().strip()):
            # A different endpoint quotes a different set of pairs.
            self.catalogue = None
            self.catalogue_error = None

    def symbol_note(self, text: str) -> None:
        self.label_symbol.set_markup(f"<small>{GLib.markup_escape_text(text)}</small>")

    def endpoint(self) -> str:
        return self.cfg.get("crypto.endpoint") or "https://api.binance.com"

    def tracked(self) -> list[str]:
        return [crypto_mod.normalise_symbol(s) for s in (self.cfg.get("crypto.symbols") or [])]

    # -- suggestions --------------------------------------------------------

    def on_symbol_typed(self, _entry) -> None:
        """Debounce: filtering is local and cheap, but not on every keystroke."""
        if self.loading:
            return
        if self.search_timer is not None:
            GLib.source_remove(self.search_timer)
        self.search_timer = GLib.timeout_add(220, self.run_symbol_search)

    def run_symbol_search(self) -> bool:
        self.search_timer = None
        query = self.entry_symbol.get_text().strip()
        if not query:
            self.clear_suggestions()
            self.symbol_note("")
            return GLib.SOURCE_REMOVE
        if self.catalogue is None:
            self.load_catalogue()
            self.symbol_note(self.t("prefs.symbol.catalogue"))
            return GLib.SOURCE_REMOVE
        self.render_suggestions(query)
        return GLib.SOURCE_REMOVE

    def load_catalogue(self) -> None:
        if self.catalogue_loading:
            return
        self.catalogue_loading = True

        def done(symbols, error) -> None:
            self.catalogue_loading = False
            self.catalogue_error = error
            self.catalogue = symbols if error is None else None
            if error is not None:
                self.symbol_note(self.t("prefs.symbol.failed", reason=error))
                return
            # The user kept typing while this was in flight; use what is there now.
            query = self.entry_symbol.get_text().strip()
            if query:
                self.render_suggestions(query)

        crypto_mod.fetch_catalogue(self.endpoint(), done)

    def clear_suggestions(self) -> None:
        for child in self.list_matches.get_children():
            self.list_matches.remove(child)

    def render_suggestions(self, query: str) -> None:
        self.clear_suggestions()
        matches = crypto_mod.search_catalogue(self.catalogue or [], query)
        if not matches:
            self.symbol_note(self.t("prefs.symbol.nomatch", query=query))
            return
        tracked = set(self.tracked())
        for symbol in matches:
            base, quote = crypto_mod.split_symbol(symbol)
            pair = f"{base}/{quote}" if quote else base
            text = f"{symbol}   ·   {pair}"
            if symbol in tracked:
                text = f"{text}   ✓ {self.t('prefs.symbol.tracked')}"
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=text, xalign=0)
            label.set_margin_start(6)
            label.set_margin_end(6)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            row.add(label)
            row.symbol = symbol
            self.list_matches.add(row)
        self.list_matches.show_all()
        self.symbol_note(self.t("prefs.symbol.hits", n=len(matches), total=len(self.catalogue or [])))

    def on_suggestion_chosen(self, _list, row: Gtk.ListBoxRow) -> None:
        symbol = getattr(row, "symbol", "")
        if symbol:
            self.add_symbol(symbol)

    # -- adding -------------------------------------------------------------

    def add_symbol(self, symbol: str) -> None:
        current = self.tracked()
        if symbol in current:
            self.symbol_note(self.t("prefs.symbol.dupe", symbol=symbol))
            return
        self.cfg.set("crypto.symbols", current + [symbol])
        self.cfg.save()
        self.entry_symbol.set_text("")
        self.clear_suggestions()
        self.symbol_note(self.t("prefs.symbol.added", symbol=symbol))
        self.load_symbols()

    def on_add_symbol(self) -> None:
        symbol = crypto_mod.normalise_symbol(self.entry_symbol.get_text())
        if not symbol:
            return
        if symbol in self.tracked():
            self.symbol_note(self.t("prefs.symbol.dupe", symbol=symbol))
            return
        if self.catalogue and symbol in self.catalogue:
            self.add_symbol(symbol)
            return

        # No catalogue (not fetched yet, or the endpoint refused it): ask about
        # this one symbol instead of blocking the user on the full list.
        self.symbol_note(self.t("prefs.symbol.checking", symbol=symbol))

        def done(ok: bool, error) -> None:
            if ok:
                self.add_symbol(symbol)
            elif error == "unknown":
                self.symbol_note(self.t("prefs.symbol.bad", symbol=symbol))
            else:
                self.symbol_note(self.t("prefs.symbol.failed", reason=error))

        crypto_mod.check_symbol(self.endpoint(), symbol, done)

    def on_remove_symbol(self, _button, symbol: str) -> None:
        remaining = [s for s in self.tracked() if s != symbol]
        if not remaining:
            self.symbol_note(self.t("prefs.symbol.last"))
            return
        self.cfg.set("crypto.symbols", remaining)
        if crypto_mod.normalise_symbol(self.cfg.get("crypto.bar_symbol") or "") == symbol:
            self.cfg.set("crypto.bar_symbol", remaining[0])
        self.cfg.save()
        self.load_symbols()

    def on_bar_changed(self, combo: Gtk.ComboBoxText) -> None:
        value = combo.get_active_id()
        if value:
            self.write("crypto.bar_symbol", value)

    def load_symbols(self) -> None:
        was_loading, self.loading = self.loading, True
        for child in self.list_symbols.get_children():
            self.list_symbols.remove(child)
        symbols = self.tracked()
        for symbol in symbols:
            base, quote = crypto_mod.split_symbol(symbol)
            row = Gtk.ListBoxRow()
            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            line.set_border_width(4)
            label = Gtk.Label(label=f"{symbol}  ({base}/{quote})" if quote else symbol, xalign=0)
            label.set_hexpand(True)
            remove = Gtk.Button(label=self.t("prefs.remove"))
            remove.connect("clicked", self.on_remove_symbol, symbol)
            line.pack_start(label, True, True, 0)
            line.pack_start(remove, False, False, 0)
            row.add(line)
            self.list_symbols.add(row)
        self.list_symbols.show_all()

        self.combo_bar.remove_all()
        for symbol in symbols:
            self.combo_bar.append(symbol, symbol)
        bar = crypto_mod.normalise_symbol(self.cfg.get("crypto.bar_symbol") or "")
        self.combo_bar.set_active_id(bar if bar in symbols else (symbols[0] if symbols else None))
        self.loading = was_loading

    # ----------------------------------------------------------------- system

    METRICS = ("cpu", "temp", "ram", "gpu", "gpu_temp", "net")

    def build_system(self) -> Gtk.Box:
        page = self.page()

        row, self.sw_system_on = switch_row(self.t("prefs.show.system"))
        self.sw_system_on.connect("notify::active", self.on_toggle_section, "system")
        page.pack_start(row, False, False, 0)

        holder, box = frame(self.t("prefs.metrics"))
        self.chk_metric = {}
        for metric in self.METRICS:
            check = Gtk.CheckButton(label=self.t(f"prefs.metric.{metric}"))
            check.connect("toggled", self.on_metric_toggled, metric)
            box.pack_start(check, False, False, 0)
            self.chk_metric[metric] = check

        self.spin_system = Gtk.SpinButton.new_with_range(1, 30, 1)
        self.spin_system.connect(
            "value-changed", lambda s: self.write("system.refresh_seconds", s.get_value_as_int())
        )
        box.pack_start(control_row(self.t("prefs.refresh.sec"), self.spin_system), False, False, 0)

        self.chk_system_label = Gtk.CheckButton(label=self.t("prefs.showlabel"))
        self.chk_system_label.connect(
            "toggled", lambda w: self.write("system.show_label", w.get_active())
        )
        box.pack_start(self.chk_system_label, False, False, 0)
        page.pack_start(holder, False, False, 0)

        holder, box = frame(self.t("prefs.sensor"))
        self.combo_sensor = Gtk.ComboBoxText()
        self.combo_sensor.connect("changed", self.on_sensor_changed)
        box.pack_start(self.combo_sensor, False, False, 0)
        self.label_sensor = dim("")
        box.pack_start(self.label_sensor, False, False, 0)

        self.spin_warn = Gtk.SpinButton.new_with_range(40, 110, 1)
        self.spin_warn.connect(
            "value-changed", lambda s: self.write("system.warn_celsius", s.get_value_as_int())
        )
        box.pack_start(control_row(self.t("prefs.warn"), self.spin_warn), False, False, 0)

        self.spin_hot = Gtk.SpinButton.new_with_range(45, 120, 1)
        self.spin_hot.connect(
            "value-changed", lambda s: self.write("system.hot_celsius", s.get_value_as_int())
        )
        box.pack_start(control_row(self.t("prefs.hot"), self.spin_hot), False, False, 0)
        page.pack_start(holder, False, False, 0)

        holder, box = frame(self.t("prefs.network"))
        self.combo_iface = Gtk.ComboBoxText()
        self.combo_iface.connect("changed", self.on_iface_changed)
        box.pack_start(control_row(self.t("prefs.iface"), self.combo_iface), False, False, 0)
        box.pack_start(dim(self.t("prefs.iface.hint")), False, False, 0)

        self.combo_netunit = Gtk.ComboBoxText()
        self.combo_netunit.append("bytes", self.t("prefs.netunit.bytes"))
        self.combo_netunit.append("bits", self.t("prefs.netunit.bits"))
        self.combo_netunit.connect(
            "changed", lambda c: self.write("system.net_unit", c.get_active_id() or "bytes")
        )
        box.pack_start(control_row(self.t("prefs.netunit"), self.combo_netunit), False, False, 0)
        page.pack_start(holder, False, False, 0)

        holder, box = frame(self.t("prefs.gpu"))
        self.chk_gpu = Gtk.CheckButton(label=self.t("prefs.gpu.enable"))
        self.chk_gpu.connect("toggled", lambda w: self.write("system.gpu", w.get_active()))
        box.pack_start(self.chk_gpu, False, False, 0)
        self.label_gpu = dim("")
        box.pack_start(self.label_gpu, False, False, 0)
        page.pack_start(holder, False, False, 0)

        return page

    def on_metric_toggled(self, check: Gtk.CheckButton, metric: str) -> None:
        if self.loading:
            return
        # Rebuild from the canonical order so the label reads the same however
        # the boxes were ticked.
        chosen = [m for m in self.METRICS if self.chk_metric[m].get_active()]
        self.write("system.bar_metrics", chosen)

    def on_sensor_changed(self, combo: Gtk.ComboBoxText) -> None:
        value = combo.get_active_id()
        if value is not None:
            self.write("system.temp_sensor", "" if value == "auto" else value)

    def on_iface_changed(self, combo: Gtk.ComboBoxText) -> None:
        value = combo.get_active_id()
        if value is not None:
            self.write("system.interfaces", [] if value == "auto" else [value])

    def load_system(self) -> None:
        was_loading, self.loading = self.loading, True
        try:
            enabled = bool(self.cfg.get("system.enabled", False))
            for switch in (self.sw_system, self.sw_system_on):
                switch.set_active(enabled)

            chosen = set(self.cfg.get("system.bar_metrics") or [])
            for metric, check in self.chk_metric.items():
                check.set_active(metric in chosen)
            self.spin_system.set_value(int(self.cfg.get("system.refresh_seconds", 3) or 3))
            self.chk_system_label.set_active(bool(self.cfg.get("system.show_label", True)))

            # -- temperature sensors
            sensors = sysinfo.list_sensors()
            auto = sysinfo.pick_sensor(sensors)
            self.combo_sensor.remove_all()
            self.combo_sensor.append(
                "auto",
                self.t("prefs.sensor.auto", name=auto["key"]) if auto else self.t("prefs.sensor.auto", name="—"),
            )
            for sensor in sensors:
                self.combo_sensor.append(sensor["key"], f"{sensor['key']}   {sensor['celsius']:.0f}°C")
            wanted = self.cfg.get("system.temp_sensor") or ""
            keys = {s["key"] for s in sensors}
            self.combo_sensor.set_active_id(wanted if wanted in keys else "auto")
            self.combo_sensor.set_sensitive(bool(sensors))
            self.label_sensor.set_markup(
                "" if sensors else f"<small>{GLib.markup_escape_text(self.t('prefs.sensor.none'))}</small>"
            )
            self.spin_warn.set_value(int(self.cfg.get("system.warn_celsius", 85) or 85))
            self.spin_hot.set_value(int(self.cfg.get("system.hot_celsius", 95) or 95))

            # -- network interfaces
            self.combo_iface.remove_all()
            auto_ifaces = sysinfo.auto_interfaces()
            self.combo_iface.append(
                "auto",
                self.t("prefs.iface.auto", name=auto_ifaces[0])
                if auto_ifaces
                else self.t("prefs.iface.autonone"),
            )
            names = sysinfo.physical_interfaces()
            for name in names:
                self.combo_iface.append(
                    name,
                    self.t(
                        "prefs.iface.row",
                        name=name,
                        kind=self.t(f"prefs.iface.{sysinfo.interface_kind(name)}"),
                        state=self.t("prefs.iface.up" if sysinfo.interface_up(name) else "prefs.iface.down"),
                    ),
                )
            configured = [n for n in (self.cfg.get("system.interfaces") or []) if n in names]
            self.combo_iface.set_active_id(configured[0] if configured else "auto")
            self.combo_netunit.set_active_id(self.cfg.get("system.net_unit") or "bytes")

            # -- gpu: nothing to configure when there is nothing to read
            backend = gpu_mod.shared()
            self.chk_gpu.set_active(bool(self.cfg.get("system.gpu", True)) and backend is not None)
            self.chk_gpu.set_sensitive(backend is not None)
            for metric in ("gpu", "gpu_temp"):
                self.chk_metric[metric].set_sensitive(backend is not None)
            if backend is not None:
                self.label_gpu.set_markup(
                    f'<span alpha="70%"><small>'
                    f'{GLib.markup_escape_text(self.t("prefs.gpu.found", name=backend.name))}'
                    f"</small></span>"
                )
            else:
                self.label_gpu.set_markup(
                    f'<span foreground="#c85a17"><small>'
                    f'{GLib.markup_escape_text(self.t("prefs.gpu.none"))}</small></span>'
                )
        finally:
            self.loading = was_loading

    # ------------------------------------------------------------------ load

    def load_values(self) -> None:
        self.loading = True
        try:
            self.combo_lang.set_active_id(self.app.t.code)
            self.chk_notify.set_active(bool(self.cfg.get("notify", True)))
            self.chk_animate.set_active(bool(self.cfg.get("animate", True)))
            self.chk_claude_label.set_active(bool(self.cfg.get("claude.show_label", True)))
            self.chk_tokens.set_active(bool(self.cfg.get("claude.show_tokens", True)))
            self.sw_claude.set_active(bool(self.cfg.get("claude.enabled", True)))
            state = sessions_mod.claude_code_status()
            if state == sessions_mod.OK:
                self.label_claude.set_markup("")
            else:
                key = "prefs.claude.missing" if state == sessions_mod.NOT_FOUND else "prefs.claude.nohooks"
                self.label_claude.set_markup(
                    f'<span foreground="#c85a17"><small>'
                    f"{GLib.markup_escape_text(self.t(key))}</small></span>"
                )
            for switch in (self.sw_weather, self.sw_weather_on):
                switch.set_active(bool(self.cfg.get("weather.enabled", False)))
            for switch in (self.sw_crypto, self.sw_crypto_on):
                switch.set_active(bool(self.cfg.get("crypto.enabled", False)))

            manual = self.cfg.get("weather.mode") == "manual"
            (self.radio_manual if manual else self.radio_auto).set_active(True)
            self.combo_unit.set_active_id(self.cfg.get("weather.unit") or "celsius")
            self.spin_weather.set_value(int(self.cfg.get("weather.refresh_minutes", 30) or 30))
            self.chk_weather_label.set_active(bool(self.cfg.get("weather.show_label", True)))
            self.refresh_place_label()

            self.spin_crypto.set_value(int(self.cfg.get("crypto.refresh_seconds", 60) or 60))
            self.chk_crypto_label.set_active(bool(self.cfg.get("crypto.show_label", True)))
            self.chk_change.set_active(bool(self.cfg.get("crypto.show_change", True)))
            self.entry_endpoint.set_text(self.cfg.get("crypto.endpoint") or "")
        finally:
            self.loading = False
        self.load_symbols()
        self.load_system()

    def on_config_changed(self, _sections: set) -> None:
        """Reflect changes made from the tray menus while the window is open."""
        if self.get_visible():
            self.load_values()
