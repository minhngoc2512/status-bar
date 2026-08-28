"""Crypto panel, backed by Binance's public REST API (no key required).

One /api/v3/ticker/24hr call covers every tracked symbol at once. Binance
geo-blocks some networks with HTTP 451; that is surfaced in the menu rather
than retried, and the endpoint is configurable so a mirror can be used.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse

from gi.repository import Gdk, GLib, Gtk

from . import labels
from .net import fetch_json
from .panel import Panel
from .sessions import human_age

# Longest first so BTCUSDT splits as BTC/USDT, not BTCU/SDT.
QUOTES = ("FDUSD", "USDT", "USDC", "BUSD", "TUSD", "TRY", "BRL", "EUR", "BTC", "ETH", "BNB", "DAI")

UP, DOWN, FLAT = "up", "down", "flat"
ARROW = {UP: "▲", DOWN: "▼", FLAT: "·"}
DOT = {UP: "🟢", DOWN: "🔴", FLAT: "⚪"}


def normalise_symbol(text: str) -> str:
    """Turn what a person types into what Binance accepts.

    Binance pairs are written closed up ("BNBUSDT") and the API rejects any
    other character outright: symbol=BNB/USDT comes back as -1100 "Illegal
    characters found in parameter 'symbol'". So "BNB/USDT", "bnb-usdt" and
    "BNB USDT" all have to collapse to the same thing.
    """
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def split_symbol(symbol: str) -> tuple[str, str]:
    symbol = (symbol or "").upper()
    for quote in QUOTES:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[: -len(quote)], quote
    return symbol, ""


def direction(change) -> str:
    try:
        value = float(change)
    except (TypeError, ValueError):
        return FLAT
    if value > 0:
        return UP
    if value < 0:
        return DOWN
    return FLAT


def format_price(value, compact: bool = False) -> str:
    """Decimals scaled to the magnitude: 79,697.28 but 0.00004312."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    size = abs(number)
    if size >= 1000:
        return f"{number:,.0f}" if compact else f"{number:,.2f}"
    if size >= 1:
        return f"{number:,.2f}"
    if size >= 0.01:
        return f"{number:.4f}"
    return f"{number:.8f}".rstrip("0").rstrip(".") or "0"


def format_percent(value, signed: bool = True) -> str:
    """Unsigned form is for places where the arrow glyph already shows direction."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number:+.2f}%" if signed else f"{abs(number):.2f}%"


def format_volume(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if number >= limit:
            return f"{number / limit:.2f}{suffix}"
    return f"{number:.0f}"


# Quotes people actually mean when they type a bare coin name, best first.
QUOTE_RANK = {"USDT": 0, "USDC": 1, "FDUSD": 2, "BTC": 3, "ETH": 4, "BNB": 5}


def fetch_catalogue(endpoint: str, callback) -> None:
    """Fetch every pair Binance quotes; ``callback(symbols, error)``.

    /api/v3/ticker/price is ~150 KB for the whole exchange. exchangeInfo would
    be the "proper" source but it is ~17 MB, so this is the one worth caching
    and filtering locally instead of hitting the API on every keystroke.
    """

    def done(data, error) -> None:
        if error is not None:
            callback([], error)
        elif not isinstance(data, list):
            callback([], "bad response")
        else:
            callback(
                sorted({r["symbol"] for r in data if isinstance(r, dict) and r.get("symbol")}), None
            )

    fetch_json(f"{endpoint.rstrip('/')}/api/v3/ticker/price", done, timeout=25)


def search_catalogue(catalogue, query: str, limit: int = 40) -> list[str]:
    """Pairs matching ``query``, most obvious first.

    Typing "BNB" should put BNBUSDT at the top, not BNBUSDC or SOLBNB.
    """
    wanted = normalise_symbol(query)
    if not wanted:
        return []
    hits = [s for s in catalogue if wanted in s]

    def rank(symbol: str):
        place = 0 if symbol == wanted else 1 if symbol.startswith(wanted) else 2
        return place, QUOTE_RANK.get(split_symbol(symbol)[1], 9), len(symbol), symbol

    return sorted(hits, key=rank)[:limit]


def ticker_url(endpoint: str, symbols: list[str]) -> str:
    query = urllib.parse.urlencode({"symbols": json.dumps(symbols, separators=(",", ":"))})
    return f"{endpoint.rstrip('/')}/api/v3/ticker/24hr?{query}"


def price_url(endpoint: str, symbol: str) -> str:
    query = urllib.parse.urlencode({"symbol": symbol.upper()})
    return f"{endpoint.rstrip('/')}/api/v3/ticker/price?{query}"


def check_symbol(endpoint: str, symbol: str, callback) -> None:
    """``callback(ok, error)`` -- does Binance know this pair?

    ``error`` is None when the pair exists, "unknown" when Binance answered but
    rejected the symbol (any 4xx), and the transport error otherwise -- the
    caller has to tell "no such coin" apart from "no network".
    """

    def done(data, error) -> None:
        if error is None and isinstance(data, dict) and "price" in data:
            callback(True, None)
        elif error is None or error.startswith("HTTP 4"):
            callback(False, "unknown")
        else:
            callback(False, error)

    fetch_json(price_url(endpoint, normalise_symbol(symbol)), done, timeout=8)


class CryptoPanel(Panel):
    section = "crypto"
    default_icon = "crypto-flat"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.tickers: dict[str, dict] = {}
        self.error: str | None = None
        self.updated_at = 0.0
        self.timer: int | None = None
        self.generation = 0

    # ------------------------------------------------------------ lifecycle

    def apply_config(self) -> None:
        self.set_visible(self.enabled())
        self.stop_timer()
        if not self.enabled():
            self.refresh()
            return
        seconds = max(15, int(self.cfg.get("crypto.refresh_seconds", 60) or 60))
        self.timer = GLib.timeout_add_seconds(seconds, self.on_timer)
        self.reload()

    def stop_timer(self) -> None:
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None

    def shutdown(self) -> None:
        self.stop_timer()

    def on_timer(self) -> bool:
        self.reload()
        return True

    # --------------------------------------------------------------- fetch

    def symbols(self) -> list[str]:
        # Normalise on read too: one malformed entry in a hand-edited config
        # makes Binance reject the whole batch, blanking every other coin.
        raw = self.cfg.get("crypto.symbols") or []
        seen, out = set(), []
        for item in raw:
            symbol = normalise_symbol(item) if isinstance(item, str) else ""
            if symbol and symbol not in seen:
                seen.add(symbol)
                out.append(symbol)
        return out

    def bar_symbol(self) -> str:
        symbols = self.symbols()
        wanted = normalise_symbol(self.cfg.get("crypto.bar_symbol") or "")
        if wanted in symbols:
            return wanted
        return symbols[0] if symbols else ""

    def reload(self) -> None:
        if not self.enabled():
            return
        symbols = self.symbols()
        if not symbols:
            self.tickers = {}
            self.error = None
            self.refresh()
            return

        self.generation += 1
        generation = self.generation
        endpoint = self.cfg.get("crypto.endpoint") or "https://api.binance.com"

        def done(data, error) -> None:
            if generation != self.generation:
                return
            if error is not None:
                self.error = error
            elif not isinstance(data, list):
                self.error = "bad response"
            else:
                self.error = None
                self.tickers = {
                    row["symbol"]: row for row in data if isinstance(row, dict) and row.get("symbol")
                }
                self.updated_at = time.time()
            self.refresh()

        fetch_json(ticker_url(endpoint, symbols), done)

    # ------------------------------------------------------------------ ui

    def refresh(self) -> None:
        if not self.visible:
            return
        t = self.t
        symbol = self.bar_symbol()
        row = self.tickers.get(symbol)

        if self.error is not None:
            self.set_icon("crypto-error", t("crypto.title"))
            self.ind.set_label("", "crypto")
        elif row:
            way = direction(row.get("priceChangePercent"))
            base = split_symbol(symbol)[0]
            label = f"{base} {format_price(row.get('lastPrice'), compact=True)}"
            if self.cfg.get("crypto.show_change", True):
                # Padded for the same reason as the system panel: 9.9% -> 10.1%
                # would otherwise nudge every indicator to the left.
                change = labels.pad(format_percent(row.get("priceChangePercent"), signed=False), 6)
                label = f"{label} {ARROW[way]}{change}"
            if not self.cfg.get("crypto.show_label", True):
                label = ""
            self.set_icon(f"crypto-{way}", t("crypto.title"))
            self.ind.set_label(label, "crypto")
            self.ind.set_title(f"{symbol} {format_price(row.get('lastPrice'))}")
        else:
            self.set_icon("crypto-flat", t("crypto.title"))
            self.ind.set_label("", "crypto")

        self.build_menu()

    def build_menu(self) -> None:
        t = self.t
        menu = Gtk.Menu()
        symbols = self.symbols()

        if not symbols:
            menu.append(self.info_item(t("crypto.empty")))
        elif self.error is not None:
            reason = t("crypto.blocked") if self.error == "HTTP 451" else t("crypto.error", reason=self.error)
            menu.append(self.info_item(reason))
        elif not self.tickers:
            menu.append(self.info_item(t("crypto.loading")))
        else:
            bar = self.bar_symbol()
            for symbol in symbols:
                row = self.tickers.get(symbol)
                base, quote = split_symbol(symbol)
                pair = f"{base}/{quote}" if quote else base
                if not row:
                    menu.append(self.info_item(f"⚪  {pair} · —"))
                    continue
                way = direction(row.get("priceChangePercent"))
                mark = "  ◀" if symbol == bar else ""
                item = Gtk.MenuItem(
                    label=f"{DOT[way]}  {pair} · {format_price(row.get('lastPrice'))} · "
                    f"{ARROW[way]} {format_percent(row.get('priceChangePercent'), signed=False)}{mark}"
                )

                sub = Gtk.Menu()
                sub.append(self.info_item(t("crypto.high", v=format_price(row.get("highPrice")))))
                sub.append(self.info_item(t("crypto.low", v=format_price(row.get("lowPrice")))))
                sub.append(self.info_item(t("crypto.volume", v=format_volume(row.get("quoteVolume")))))
                sub.append(Gtk.SeparatorMenuItem())
                sub.append(self.action_item(t("crypto.setbar"), self.on_set_bar, symbol))
                sub.append(self.action_item(t("crypto.copy"), self.on_copy, str(row.get("lastPrice", ""))))
                sub.append(self.action_item(t("crypto.remove"), self.on_remove, symbol))
                item.set_submenu(sub)
                menu.append(item)

            menu.append(Gtk.SeparatorMenuItem())
            menu.append(self.info_item(t("crypto.updated", age=human_age(time.time() - self.updated_at))))

        self.append_tail(menu, refresh=True)
        self.set_menu(menu)

    # -------------------------------------------------------------- actions

    def on_set_bar(self, _item, symbol: str) -> None:
        if self.cfg.set("crypto.bar_symbol", symbol):
            self.cfg.save()

    def on_copy(self, _item, text: str) -> None:
        if not text:
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        clipboard.store()

    def on_remove(self, _item, symbol: str) -> None:
        remaining = [s for s in self.symbols() if s != symbol]
        if not remaining:
            return  # keep at least one, otherwise the panel has nothing to show
        self.cfg.set("crypto.symbols", remaining)
        if self.cfg.get("crypto.bar_symbol") == symbol:
            self.cfg.set("crypto.bar_symbol", remaining[0])
        self.cfg.save()
