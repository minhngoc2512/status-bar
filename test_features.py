"""Headless checks for the weather/crypto/config logic added on top of test_store.py."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from claude_status import crypto as C  # noqa: E402
from claude_status import gpu as GPU  # noqa: E402
from claude_status import labels as L  # noqa: E402
from claude_status import sessions as SESS  # noqa: E402

from claude_status import app as APP  # noqa: E402

import merge_settings as HOOKS  # noqa: E402
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

# ------------------------------------------------------- constant-width labels
# The status area is right-aligned, so any label that changes width shoves every
# indicator to its left. These invariants are what stop that.
FIG, PT = "\u2007", "\u2008"

check("pad uses digit-width spaces", L.pad("7", 3), FIG + FIG + "7")
check("pad leaves a full field alone", L.pad("100", 3), "100")
check("a decimal spends the point slot", L.pad_number("1.1"), FIG + "1.1")
check("no decimal borrows a point space", L.pad_number("12"), PT + FIG + "12")
check("a full field still gets its point space", L.pad_number("512"), PT + "512")
check("pad_number is always four cells", {len(L.pad_number(x)) for x in ("0.0", "1.1", "12", "512")}, {4})

SWEEP = [0, 1, 512, 1023, 1024, 1150, 12_000, 999_999, 1 << 20, 5.2e6, 1 << 30, 1.4e9, 9.9e11]
check("every byte rate is one length", {len(L.rate(v)) for v in SWEEP}, {5})
check("every bit rate is one length", {len(L.rate(v, "bits")) for v in SWEEP}, {6})
check("byte rate reads sensibly", L.rate(1150), FIG + "1.1K")
check("bit rate never drops below kb", L.rate(0, "bits"), FIG + "0.0kb")
check("every percent is one length", {len(L.percent(v)) for v in (0, 7, 42, 100)}, {4})
check("every temperature is one length", {len(L.temperature(v)) for v in (9, 46, 101)}, {5})
check("percent of garbage", L.percent(None), FIG + FIG + "-%")

# Unit letters have no space character defined against them, so they are matched
# by measuring the font. Without a measurer installed nothing is added.
check("no font metrics means no unit padding", L.rate(1150).endswith("1.1K"), True)
WIDTHS = {FIG: 8, PT: 4, "\u2009": 3, "\u200a": 2, "B": 10, "K": 9, "M": 13, "G": 10}
L.use_font_metrics(lambda text: WIDTHS.get(text, 8 * len(text)))
check("narrow unit gets filled to the widest", L.unit_fill("K", ("B", "K", "M", "G")), PT),
check("the widest unit gets nothing", L.unit_fill("M", ("B", "K", "M", "G")), "")
check("padding goes in front, never trailing", L.rate(1150)[-1], "K")
L.use_font_metrics(None)

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

# ------------------------------------------------------- upgrade detection
# apt replaces the files but cannot restart a user service, so the old code
# keeps running until the user is told.
from claude_status import paths as PATHS  # noqa: E402

check("version parsed off disk", bool(PATHS.VERSION_RE.search('__version__ = "9.9.9"')), True)
check("no version in the file", PATHS.VERSION_RE.search("nothing here"), None)

PATHS._upgrade_probe = (0.0, "")
check("running what is installed", PATHS.pending_upgrade(PATHS.installed_version()), "")
PATHS._upgrade_probe = (0.0, "")
check("running something older", PATHS.pending_upgrade("0.0.1"), PATHS.installed_version())
check("the answer is cached", PATHS.pending_upgrade("also-stale"), PATHS.installed_version())
PATHS._upgrade_probe = (0.0, "")

# --------------------------------------------------------- single instance
# Two copies do not merely show two icons: drain() unlinks each event file as it
# reads it, so they split the spool and each ends up with a partial, wrong view.
with tempfile.TemporaryDirectory() as tmp:
    real_lock = APP.LOCK_PATH
    try:
        APP.LOCK_PATH = Path(tmp) / "indicator.lock"
        first = APP.acquire_lock()
        check("the first copy takes the lock", first is not None, True)
        check("the lock carries the pid", APP.running_pid(), os.getpid())
        check("a second copy is refused", APP.acquire_lock(), None)
        # A refused copy must not truncate the file it is about to read: it has
        # to find the pid there in order to hand its request over.
        check("a refused copy leaves the pid intact", APP.running_pid(), os.getpid())
        first.close()
        second = APP.acquire_lock()
        check("the lock frees when the holder goes", second is not None, True)
        second.close()
        # An empty lock file is what older versions left behind; signalling a
        # pid of 0 would be meaningless, and SIGUSR1 to a version without the
        # handler would kill it outright.
        APP.LOCK_PATH.write_text("")
        check("an empty lock yields no pid", APP.running_pid(), 0)
        check("and nothing is signalled", APP.wake_settings(), False)
    finally:
        APP.LOCK_PATH = real_lock

# ------------------------------------------- hook install / uninstall
# Both install routes exist (the .deb and a git checkout). Wiring both up makes
# every Claude Code event spool twice, so whichever installer runs last wins.
check("our hook, packaged path", HOOKS.is_our_hook("/usr/lib/claude-status/hooks/emit.sh"), True)
check("our hook, checkout path", HOOKS.is_our_hook("/home/x/repo/hooks/emit.sh"), True)
check("somebody else's hook", HOOKS.is_our_hook("rtk hook claude"), False)
check("a non-string command", HOOKS.is_our_hook(None), False)

CFG = {
    "hooks": {
        "Stop": [{"hooks": [
            {"command": "/home/x/checkout/hooks/emit.sh"},
            {"command": "rtk hook claude"},
        ]}],
        "PreToolUse": [{"matcher": "*", "hooks": [{"command": "/old/place/hooks/emit.sh"}]}],
        "SessionStart": [{"hooks": [{"command": "/usr/lib/claude-status/hooks/emit.sh"}]}],
    }
}
gone = HOOKS.prune_foreign(CFG, "/usr/lib/claude-status/hooks/emit.sh")
check("both foreign copies removed", sorted(gone), ["/home/x/checkout/hooks/emit.sh", "/old/place/hooks/emit.sh"])
check("another tool's hook survives", CFG["hooks"]["Stop"][0]["hooks"], [{"command": "rtk hook claude"}])
check("our own hook survives", "SessionStart" in CFG["hooks"], True)
check("an emptied event is dropped", "PreToolUse" not in CFG["hooks"], True)
check("pruning again is a no-op", HOOKS.prune_foreign(CFG, "/usr/lib/claude-status/hooks/emit.sh"), [])
check("pruning empty settings", HOOKS.prune_foreign({}, "/x/emit.sh"), [])
check("pruning malformed settings", HOOKS.prune_foreign({"hooks": {"Stop": None}}, "/x/emit.sh"), [])

# ------------------------------------------------- Claude Code detection
# An empty session list means one of three things, and the menu has to say
# which -- otherwise a machine with no Claude Code just looks broken.
check("no hooks at all", SESS.hook_installed({}), False)
check("unrelated hooks only", SESS.hook_installed({"hooks": {"Stop": [{"hooks": [{"command": "other"}]}]}}), False)
check(
    "our hook from a checkout",
    SESS.hook_installed({"hooks": {"Stop": [{"hooks": [{"command": "/home/x/repo/hooks/emit.sh"}]}]}}),
    True,
)
check(
    "our hook from the package",
    SESS.hook_installed({"hooks": {"Stop": [{"hooks": [{"command": "/usr/lib/claude-status/hooks/emit.sh"}]}]}}),
    True,
)
check("malformed settings do not raise", SESS.hook_installed({"hooks": {"Stop": None}}), False)

with tempfile.TemporaryDirectory() as tmp:
    fake = Path(tmp)
    real_dir, real_settings, real_which = SESS.CLAUDE_DIR, SESS.CLAUDE_SETTINGS, SESS.shutil.which
    try:
        SESS.shutil.which = lambda _name: None  # pretend the CLI is absent

        SESS.CLAUDE_DIR = fake / "absent"
        SESS.CLAUDE_SETTINGS = SESS.CLAUDE_DIR / "settings.json"
        SESS._probe = (0.0, "")
        check("no Claude Code at all", SESS.claude_code_status(), SESS.NOT_FOUND)

        SESS.CLAUDE_DIR = fake / "present"
        SESS.CLAUDE_DIR.mkdir()
        SESS.CLAUDE_SETTINGS = SESS.CLAUDE_DIR / "settings.json"
        SESS.CLAUDE_SETTINGS.write_text("{}")
        SESS._probe = (0.0, "")
        check("installed but unwired", SESS.claude_code_status(), SESS.NO_HOOKS)

        SESS.CLAUDE_SETTINGS.write_text(
            json.dumps({"hooks": {"Stop": [{"hooks": [{"command": "/usr/lib/claude-status/hooks/emit.sh"}]}]}})
        )
        SESS._probe = (0.0, "")
        check("installed and wired", SESS.claude_code_status(), SESS.OK)

        SESS.CLAUDE_SETTINGS.write_text("{ not json")
        SESS._probe = (0.0, "")
        check("unreadable settings count as unwired", SESS.claude_code_status(), SESS.NO_HOOKS)

        # The menu rebuilds every few seconds; the probe must not stat on each one.
        SESS.CLAUDE_SETTINGS.unlink()
        check("the answer is cached", SESS.claude_code_status(), SESS.NO_HOOKS)
    finally:
        SESS.CLAUDE_DIR, SESS.CLAUDE_SETTINGS = real_dir, real_settings
        SESS.shutil.which = real_which
        SESS._probe = (0.0, "")

# --------------------------------------------------------------------- system
check("bytes in GiB", SYS.format_bytes(11.1 * 1024**3), "11.1G")
check("bytes under a KiB keep the B", SYS.format_bytes(512), "512B")
check("bytes of nothing", SYS.format_bytes(0), "0B")
check("rate in KB/s", SYS.format_rate(1150), "1.1 KB/s")
check("rate of nothing has one B", SYS.format_rate(0), "0 B/s")
check("rate in bits", SYS.format_rate(1150, "bits"), "9.2 kbps")
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
