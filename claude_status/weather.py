"""Weather panel, backed by Open-Meteo (no API key, no signup).

Location comes either from an IP lookup (three free providers tried in order,
because each of them rate-limits separately) or from a place the user picked in
Settings via Open-Meteo's geocoder.
"""

from __future__ import annotations

import time

from gi.repository import GLib, Gtk

from .net import build_url, fetch_first, fetch_json
from .panel import Panel
from .sessions import human_age

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Free IP-geolocation endpoints, most reliable first. ip-api.com is HTTP-only on
# its free tier, which is why it is last.
IP_PROVIDERS = [
    "https://ipwho.is/",
    "https://ipapi.co/json/",
    "http://ip-api.com/json/",
]

# Re-use a cached IP lookup for this long before asking a provider again.
DETECT_TTL = 12 * 3600

# WMO weather interpretation codes -> a translatable group.
WMO_GROUP = {
    0: "clear",
    1: "mainly_clear",
    2: "partly_cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    56: "freezing_drizzle",
    57: "freezing_drizzle",
    61: "rain",
    63: "rain",
    65: "rain",
    66: "freezing_rain",
    67: "freezing_rain",
    71: "snow",
    73: "snow",
    75: "snow",
    77: "snow_grains",
    80: "showers",
    81: "showers",
    82: "showers",
    85: "snow_showers",
    86: "snow_showers",
    95: "thunder",
    96: "thunder_hail",
    99: "thunder_hail",
}

# group -> icon basename; "clear"/"mainly_clear" also have a night variant.
GROUP_ICON = {
    "clear": "weather-sun",
    "mainly_clear": "weather-sun",
    "partly_cloudy": "weather-cloud-sun",
    "overcast": "weather-cloud",
    "fog": "weather-fog",
    "drizzle": "weather-rain",
    "freezing_drizzle": "weather-rain",
    "rain": "weather-rain",
    "freezing_rain": "weather-rain",
    "snow": "weather-snow",
    "snow_grains": "weather-snow",
    "showers": "weather-rain",
    "snow_showers": "weather-snow",
    "thunder": "weather-storm",
    "thunder_hail": "weather-storm",
    "unknown": "weather-unknown",
}

NIGHT_ICON = {"weather-sun": "weather-moon", "weather-cloud-sun": "weather-cloud-moon"}


def group_for(code) -> str:
    try:
        return WMO_GROUP.get(int(code), "unknown")
    except (TypeError, ValueError):
        return "unknown"


def icon_for(code, is_day: bool = True) -> str:
    icon = GROUP_ICON.get(group_for(code), "weather-unknown")
    return icon if is_day else NIGHT_ICON.get(icon, icon)


def degrees(value, unit: str) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{round(value)}°{'F' if unit == 'fahrenheit' else 'C'}"


def place_label(result: dict) -> str:
    """Human name for one Open-Meteo geocoding hit."""
    bits = [result.get("name") or ""]
    admin = result.get("admin1") or ""
    if admin and admin != result.get("name"):
        bits.append(admin)
    if result.get("country"):
        bits.append(result["country"])
    return ", ".join(b for b in bits if b)


def accept_ip(data) -> dict | None:
    """Normalise whichever of the three IP providers answered."""
    if not isinstance(data, dict):
        return None
    if data.get("error") or data.get("success") is False:
        return None
    if data.get("status") not in (None, "success"):
        return None
    lat = data.get("latitude", data.get("lat"))
    lon = data.get("longitude", data.get("lon"))
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    city = data.get("city") or data.get("regionName") or data.get("region") or ""
    country = data.get("country_name") or data.get("country") or data.get("countryCode") or ""
    place = ", ".join(b for b in (city, country) if b) or f"{lat:.2f}, {lon:.2f}"
    return {"latitude": float(lat), "longitude": float(lon), "place": place}


def geocode(query: str, lang: str, callback) -> None:
    """Search place names; ``callback(results, error)`` with a list of dicts."""
    url = build_url(GEOCODE_URL, {"name": query, "count": 8, "language": lang, "format": "json"})

    def done(data, error) -> None:
        if error is not None:
            callback([], error)
            return
        results = (data or {}).get("results") or []
        callback([r for r in results if isinstance(r, dict)], None)

    fetch_json(url, done)


class WeatherPanel(Panel):
    section = "weather"
    default_icon = "weather-unknown"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.current: dict | None = None
        self.daily: dict | None = None
        self.place = ""
        self.error: str | None = None
        self.locating = False
        self.updated_at = 0.0
        self.timer: int | None = None
        # Guards against a slow reply from a location the user already changed.
        self.generation = 0

    # ------------------------------------------------------------ lifecycle

    def apply_config(self) -> None:
        self.set_visible(self.enabled())
        self.stop_timer()
        if not self.enabled():
            self.refresh()
            return
        self.generation += 1
        self.current = None
        self.error = None
        minutes = max(5, int(self.cfg.get("weather.refresh_minutes", 30) or 30))
        self.timer = GLib.timeout_add_seconds(minutes * 60, self.on_timer)
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

    def reload(self) -> None:
        if not self.enabled():
            return
        self.generation += 1
        generation = self.generation

        mode = self.cfg.get("weather.mode", "auto")
        if mode == "manual":
            lat, lon = self.cfg.get("weather.latitude"), self.cfg.get("weather.longitude")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                self.place = self.cfg.get("weather.place") or f"{lat:.2f}, {lon:.2f}"
                self.fetch_forecast(lat, lon, generation)
            else:
                self.error = None
                self.current = None
                self.refresh()
            return

        cached = self.cfg.get("weather.detected") or {}
        if (
            isinstance(cached, dict)
            and isinstance(cached.get("latitude"), (int, float))
            and time.time() - float(cached.get("at") or 0) < DETECT_TTL
        ):
            self.place = cached.get("place") or ""
            self.fetch_forecast(cached["latitude"], cached["longitude"], generation)
            return

        self.locating = True
        self.refresh()

        def located(found, error) -> None:
            if generation != self.generation:
                return
            self.locating = False
            if error is not None or not found:
                self.error = error or "location unknown"
                self.refresh()
                return
            found["at"] = time.time()
            self.cfg.set("weather.detected", found)
            self.cfg.save()
            self.place = found["place"]
            self.fetch_forecast(found["latitude"], found["longitude"], generation)

        fetch_first(IP_PROVIDERS, accept_ip, located)

    def fetch_forecast(self, lat: float, lon: float, generation: int) -> None:
        unit = self.cfg.get("weather.unit", "celsius")
        url = build_url(
            FORECAST_URL,
            {
                "latitude": round(float(lat), 4),
                "longitude": round(float(lon), 4),
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m,is_day",
                "daily": "temperature_2m_max,temperature_2m_min",
                "temperature_unit": unit,
                "wind_speed_unit": "kmh",
                "timezone": "auto",
                "forecast_days": 1,
            },
        )

        def done(data, error) -> None:
            if generation != self.generation:
                return
            if error is not None or not isinstance(data, dict) or "current" not in data:
                self.error = error or "bad response"
            else:
                self.error = None
                self.current = data.get("current") or {}
                self.daily = data.get("daily") or {}
                self.updated_at = time.time()
            self.refresh()

        fetch_json(url, done)

    # ------------------------------------------------------------------ ui

    def refresh(self) -> None:
        if not self.visible:
            return
        t = self.t
        unit = self.cfg.get("weather.unit", "celsius")

        if self.current:
            code = self.current.get("weather_code")
            is_day = bool(self.current.get("is_day", 1))
            self.set_icon(icon_for(code, is_day), t(f"wx.{group_for(code)}"))
            label = degrees(self.current.get("temperature_2m"), unit)
            self.ind.set_label(label if self.cfg.get("weather.show_label", True) else "", "weather")
            self.ind.set_title(f"{self.place} — {label}" if self.place else label)
        else:
            self.set_icon("weather-unknown", t("weather.title"))
            self.ind.set_label("", "weather")
            self.ind.set_title(t("weather.title"))

        self.build_menu()

    def build_menu(self) -> None:
        t = self.t
        unit = self.cfg.get("weather.unit", "celsius")
        menu = Gtk.Menu()

        if self.place:
            menu.append(self.info_item(f"📍 {self.place}"))

        if self.locating:
            menu.append(self.info_item(t("weather.locating")))
        elif self.error is not None:
            menu.append(self.info_item(t("weather.error", reason=self.error)))
        elif not self.current:
            has_place = self.place or self.cfg.get("weather.mode") == "auto"
            menu.append(self.info_item(t("weather.loading") if has_place else t("weather.nolocation")))
        else:
            cur = self.current
            code = cur.get("weather_code")
            temp = degrees(cur.get("temperature_2m"), unit)
            menu.append(self.info_item(f"{t('wx.' + group_for(code))} · {temp}"))
            menu.append(self.info_item(t("weather.feels", v=degrees(cur.get("apparent_temperature"), unit))))
            menu.append(self.info_item(t("weather.humidity", v=cur.get("relative_humidity_2m", "—"))))
            menu.append(self.info_item(t("weather.wind", v=cur.get("wind_speed_10m", "—"))))
            highs = (self.daily or {}).get("temperature_2m_max") or []
            lows = (self.daily or {}).get("temperature_2m_min") or []
            if highs and lows:
                menu.append(
                    self.info_item(
                        t("weather.range", lo=degrees(lows[0], unit), hi=degrees(highs[0], unit))
                    )
                )
            menu.append(Gtk.SeparatorMenuItem())
            menu.append(self.info_item(t("weather.updated", age=human_age(time.time() - self.updated_at))))
            menu.append(self.info_item(t("weather.source")))

        self.append_tail(menu, refresh=True)
        self.set_menu(menu)
