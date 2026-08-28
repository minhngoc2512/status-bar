"""Headless checks for the weather/crypto/config logic added on top of test_store.py."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from claude_status import crypto as C  # noqa: E402
from claude_status import gpu as GPU  # noqa: E402
from claude_status import system as SYS  # noqa: E402
from claude_status import weather as W  # noqa: E402
from claude_status.config import DEFAULTS, Config, merged  # noqa: E402
from claude_status.paths import ICON_DIR  # noqa: E402

checks = []


def check(label, got, want):
    ok = got == want
    checks.append(ok)
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f"  (want {want!r})"))


# --------------------------------------------------------------------- config
check("merge keeps defaults", merged(DEFAULTS, {"lang": "vi"})["crypto"]["refresh_seconds"], 60)
check("merge overrides nested", merged(DEFAULTS, {"weather": {"unit": "fahrenheit"}})["weather"]["unit"], "fahrenheit")
check("merge does not mutate DEFAULTS", DEFAULTS["weather"]["unit"], "celsius")

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "config.json"
    cfg = Config(path)
    seen = []
    cfg.subscribe(seen.append)
    check("get dotted path", cfg.get("crypto.bar_symbol"), "BTCUSDT")
    check("get missing path", cfg.get("nope.nope", "fallback"), "fallback")
    check("set reports a change", cfg.set("weather.unit", "fahrenheit"), True)
    check("set reports a no-op", cfg.set("weather.unit", "fahrenheit"), False)
    cfg.set("notify", False)
    cfg.save()
    check("save notifies dirty sections", seen, [{"weather", "general"}])
    check("save is atomic and readable", json.loads(path.read_text())["weather"]["unit"], "fahrenheit")
    check("reload keeps the value", Config(path).get("weather.unit"), "fahrenheit")

    # Two instances (the service and a second run) must not revert each other.
    one, two = Config(path), Config(path)
    one.set("lang", "vi")
    two.set("crypto.refresh_seconds", 120)
    one.save()
    two.save()
    final = Config(path)
    check("concurrent save keeps the other's edit", final.get("lang"), "vi")
    check("concurrent save keeps its own edit", final.get("crypto.refresh_seconds"), 120)
    check("untouched keys survive", final.get("weather.unit"), "fahrenheit")

# -------------------------------------------------------------------- weather
check("wmo 0 -> clear", W.group_for(0), "clear")
check("wmo 95 -> thunder", W.group_for(95), "thunder")
check("wmo unmapped -> unknown", W.group_for(4), "unknown")
check("wmo None -> unknown", W.group_for(None), "unknown")
check("clear at night uses the moon", W.icon_for(0, is_day=False), "weather-moon")
check("rain has no night variant", W.icon_for(61, is_day=False), "weather-rain")
check("celsius formatting", W.degrees(28.4, "celsius"), "28°C")
check("fahrenheit formatting", W.degrees(83.1, "fahrenheit"), "83°F")
check("missing temperature", W.degrees(None, "celsius"), "—")
check(
    "place label skips a duplicate admin",
    W.place_label({"name": "Hanoi", "admin1": "Hanoi", "country": "Vietnam"}),
    "Hanoi, Vietnam",
)
check(
    "ip shape: ipwho.is",
    W.accept_ip({"success": True, "latitude": 21.0, "longitude": 105.8, "city": "Hanoi", "country": "Viet Nam"}),
    {"latitude": 21.0, "longitude": 105.8, "place": "Hanoi, Viet Nam"},
)
check(
    "ip shape: ip-api.com",
    W.accept_ip({"status": "success", "lat": 21.0, "lon": 105.8, "city": "Hanoi", "country": "Vietnam"}),
    {"latitude": 21.0, "longitude": 105.8, "place": "Hanoi, Vietnam"},
)
check("ip provider error is rejected", W.accept_ip({"error": True, "reason": "RateLimited"}), None)
check("ip provider failure is rejected", W.accept_ip({"status": "fail"}), None)

# --------------------------------------------------------------------- crypto
check("typed slash is stripped", C.normalise_symbol("BNB/USDT"), "BNBUSDT")
check("typed dash and case", C.normalise_symbol("bnb-usdt"), "BNBUSDT")
check("typed spaces", C.normalise_symbol("  BNB USDT "), "BNBUSDT")
check("digits survive", C.normalise_symbol("1000pepe/usdt"), "1000PEPEUSDT")
check("empty stays empty", C.normalise_symbol("///"), "")
check("None is safe", C.normalise_symbol(None), "")
CATALOGUE = ["BNBUSDT", "BNBUSDC", "BNBBTC", "SOLBNB", "BNBUPUSDT", "BTCUSDT", "ETHFDUSD"]
check("search puts the USDT pair first", C.search_catalogue(CATALOGUE, "BNB")[0], "BNBUSDT")
check("search accepts a slash", C.search_catalogue(CATALOGUE, "bnb/usdt"), ["BNBUSDT"])
check("search ranks prefix over substring", C.search_catalogue(CATALOGUE, "BNB")[-1], "SOLBNB")
check("search honours the limit", len(C.search_catalogue(CATALOGUE, "BNB", limit=2)), 2)
check("search on empty input", C.search_catalogue(CATALOGUE, "  "), [])
check("search miss", C.search_catalogue(CATALOGUE, "ZZZ"), [])
check("split BTCUSDT", C.split_symbol("BTCUSDT"), ("BTC", "USDT"))
check("split longest quote first", C.split_symbol("ETHFDUSD"), ("ETH", "FDUSD"))
check("split unknown quote", C.split_symbol("WEIRD"), ("WEIRD", ""))
check("split never eats the whole symbol", C.split_symbol("USDT"), ("USDT", ""))
check("price >= 1000", C.format_price("79697.28"), "79,697.28")
check("price compact drops the cents", C.format_price("79697.28", compact=True), "79,697")
check("price under 1", C.format_price("0.4312"), "0.4312")
check("price of a micro cap", C.format_price("0.00004312"), "0.00004312")
check("price of garbage", C.format_price(None), "—")
check("percent is signed", C.format_percent("1.207"), "+1.21%")
check("negative percent", C.format_percent("-0.5"), "-0.50%")
check("volume in billions", C.format_volume("1477475376"), "1.48B")
check("direction up", C.direction("0.01"), C.UP)
check("direction down", C.direction("-0.01"), C.DOWN)
check("direction flat on garbage", C.direction("x"), C.FLAT)
check(
    "ticker url",
    C.ticker_url("https://api.binance.com/", ["BTCUSDT", "ETHUSDT"]),
    "https://api.binance.com/api/v3/ticker/24hr?symbols=%5B%22BTCUSDT%22%2C%22ETHUSDT%22%5D",
)

# --------------------------------------------------------------------- system
check("bytes in GiB", SYS.format_bytes(11.1 * 1024**3), "11.1G")
check("bytes under a KiB keep the B", SYS.format_bytes(512), "512B")
check("bytes of nothing", SYS.format_bytes(0), "0B")
check("rate in KB/s", SYS.format_rate(1150), "1.1 KB/s")
check("rate of nothing has one B", SYS.format_rate(0), "0 B/s")
check("rate in bits", SYS.format_rate(1150, "bits"), "9.2 kbps")
check("short rate for the tray", SYS.format_rate_short(1150), "1.1K")
check("short rate in bits", SYS.format_rate_short(1150, "bits"), "9.2kb")
check("uptime in days", SYS.format_uptime(2 * 86400 + 3 * 3600), "2d 3h")
check("uptime in hours", SYS.format_uptime(3 * 3600 + 5 * 60), "3h 05m")
check("uptime in minutes", SYS.format_uptime(300), "5m")

check("temp state cool", SYS.temperature_state(60, 85, 95), "idle")
check("temp state warm", SYS.temperature_state(88, 85, 95), "warm")
check("temp state hot", SYS.temperature_state(96, 85, 95), "hot")
check("temp state without a sensor", SYS.temperature_state(None, 85, 95), "idle")

ENTRIES = [
    {"key": "nvme/Composite", "chip": "nvme", "label": "Composite"},
    {"key": "k10temp/Tctl", "chip": "k10temp", "label": "Tctl"},
    {"key": "iwlwifi_1/temp1", "chip": "iwlwifi_1", "label": "temp1"},
]
check("auto pick prefers the CPU chip", SYS.pick_sensor(ENTRIES)["key"], "k10temp/Tctl")
check("configured sensor wins", SYS.pick_sensor(ENTRIES, "nvme/Composite")["key"], "nvme/Composite")
check("vanished sensor falls back to auto", SYS.pick_sensor(ENTRIES, "gone/x")["key"], "k10temp/Tctl")
check("no sensors at all", SYS.pick_sensor([]), None)
check(
    "intel package beats a bare core",
    SYS.pick_sensor(
        [
            {"key": "coretemp/Core 0", "chip": "coretemp", "label": "Core 0"},
            {"key": "coretemp/Package id 0", "chip": "coretemp", "label": "Package id 0"},
        ]
    )["key"],
    "coretemp/Package id 0",
)
check("a rate needs two samples", SYS.CpuSampler().sample(), None)
check("net sampler starts empty", SYS.NetSampler().sample(["lo"]), {})

with tempfile.TemporaryDirectory() as tmp:
    dpm = Path(tmp) / "pp_dpm_sclk"
    dpm.write_text("0: 500Mhz\n1: 1000Mhz *\n2: 1700Mhz\n")
    check("amd dpm picks the active step", GPU._current_dpm(dpm), 1000)
    dpm.write_text("0: 500Mhz\n1: 1000Mhz\n")
    check("amd dpm with nothing active", GPU._current_dpm(dpm), None)
    check("amd dpm on a missing file", GPU._current_dpm(Path(tmp) / "nope"), None)

# ---------------------------------------------------------------------- icons
wanted = set(W.GROUP_ICON.values()) | set(W.NIGHT_ICON.values())
wanted |= {f"crypto-{k}" for k in (C.UP, C.DOWN, C.FLAT)} | {"crypto-error"}
wanted |= {f"system-{s}" for s in ("idle", "warm", "hot")}
missing = sorted(n for n in wanted if not (ICON_DIR / f"{n}.svg").exists())
check("every weather/crypto icon exists", missing, [])
check("every WMO group has an icon", sorted(set(W.WMO_GROUP.values()) - set(W.GROUP_ICON)), [])

print()
print(f"{sum(checks)}/{len(checks)} passed")
sys.exit(0 if all(checks) else 1)
