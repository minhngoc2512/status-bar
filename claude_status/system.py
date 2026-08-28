"""Hardware readings straight from /proc and /sys -- no psutil, no shelling out.

Everything here is a file read costing microseconds, so the panel samples on
the GTK main loop instead of going through net.py's worker threads.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

HWMON = Path("/sys/class/hwmon")
THERMAL = Path("/sys/class/thermal")
NET = Path("/sys/class/net")

# hwmon driver names that report a CPU package temperature, best first.
CPU_CHIPS = ("k10temp", "zenpower", "coretemp", "cpu_thermal", "acpitz", "soc_thermal")
# Preferred sensor label within a chip. AMD exposes Tctl/Tdie, Intel a package.
CPU_LABELS = ("Tctl", "Tdie", "Package id 0", "CPU", "CPU Temperature", "Core 0")

MIB = 1024.0 * 1024.0


def read_text(path) -> str:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def read_int(path) -> int | None:
    raw = read_text(path)
    try:
        return int(raw)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# temperature
# --------------------------------------------------------------------------- #


def discover_sensors() -> list[dict]:
    """Every temperature input as {key, chip, label, path}, without reading it.

    Discovery is separated from reading because the reads are not all equally
    cheap: k10temp costs 0.03 ms but each NVMe sensor costs ~0.6 ms (the read
    wakes the drive controller). The panel discovers once, then reads only the
    sensor it actually shows.

    ``key`` is "<chip>/<label>" -- hwmon numbering is not stable across reboots,
    so that is what goes in the config.
    """
    found: list[dict] = []
    try:
        chips = sorted(HWMON.glob("hwmon*"))
    except OSError:
        chips = []
    for chip_dir in chips:
        chip = read_text(chip_dir / "name") or chip_dir.name
        try:
            inputs = sorted(chip_dir.glob("temp*_input"))
        except OSError:
            continue
        for source in inputs:
            label = read_text(str(source)[: -len("_input")] + "_label")
            label = label or source.name[: -len("_input")]
            found.append({"key": f"{chip}/{label}", "chip": chip, "label": label, "path": source})

    if found:
        return found

    # Some machines expose nothing under hwmon; thermal zones are the fallback.
    try:
        zones = sorted(THERMAL.glob("thermal_zone*"))
    except OSError:
        zones = []
    for zone in zones:
        kind = read_text(zone / "type") or zone.name
        found.append(
            {"key": f"{kind}/{zone.name}", "chip": kind, "label": zone.name, "path": zone / "temp"}
        )
    return found


def read_sensor(entry) -> dict | None:
    """One sensor's current reading, or None if it went away."""
    if not entry:
        return None
    milli = read_int(entry["path"])
    if milli is None:
        return None
    return {**entry, "celsius": milli / 1000.0}


def list_sensors() -> list[dict]:
    """Discover and read everything -- for the settings list and the menu's
    all-sensors submenu, neither of which runs on every tick."""
    return [s for s in (read_sensor(e) for e in discover_sensors()) if s]


def pick_sensor(sensors: list[dict], preferred: str = "") -> dict | None:
    """The configured sensor, or the most CPU-ish one available."""
    if not sensors:
        return None
    if preferred:
        for sensor in sensors:
            if sensor["key"] == preferred:
                return sensor
        # Configured sensor vanished (module unloaded, hardware changed): fall
        # through to auto rather than showing nothing.
    for chip in CPU_CHIPS:
        matching = [s for s in sensors if s["chip"] == chip]
        if not matching:
            continue
        for label in CPU_LABELS:
            for sensor in matching:
                if sensor["label"] == label:
                    return sensor
        return matching[0]
    return sensors[0]


# --------------------------------------------------------------------------- #
# cpu / memory
# --------------------------------------------------------------------------- #


class CpuSampler:
    """Busy percentage from successive /proc/stat snapshots."""

    def __init__(self) -> None:
        self.previous: tuple[int, int] | None = None

    @staticmethod
    def snapshot() -> tuple[int, int] | None:
        line = ""
        try:
            with open("/proc/stat") as handle:
                line = handle.readline()
        except OSError:
            return None
        parts = line.split()
        if len(parts) < 5 or parts[0] != "cpu":
            return None
        try:
            values = [int(v) for v in parts[1:]]
        except ValueError:
            return None
        total = sum(values)
        # idle + iowait
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return total, idle

    def sample(self) -> float | None:
        """None until the second call -- a rate needs two points."""
        current = self.snapshot()
        if current is None:
            return None
        previous, self.previous = self.previous, current
        if previous is None:
            return None
        total_delta = current[0] - previous[0]
        idle_delta = current[1] - previous[1]
        if total_delta <= 0:
            return None
        return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))


def memory() -> dict:
    """Used/total in bytes plus swap, from /proc/meminfo (values are KiB)."""
    fields = {}
    try:
        with open("/proc/meminfo") as handle:
            for line in handle:
                name, _, rest = line.partition(":")
                try:
                    fields[name] = int(rest.split()[0]) * 1024
                except (IndexError, ValueError):
                    continue
    except OSError:
        return {}
    total = fields.get("MemTotal", 0)
    # MemAvailable is the kernel's own estimate; total-free wildly overstates use.
    available = fields.get("MemAvailable", fields.get("MemFree", 0))
    used = max(0, total - available)
    swap_total = fields.get("SwapTotal", 0)
    swap_used = max(0, swap_total - fields.get("SwapFree", 0))
    return {
        "total": total,
        "available": available,
        "used": used,
        "percent": (100.0 * used / total) if total else 0.0,
        "swap_total": swap_total,
        "swap_used": swap_used,
    }


def loadavg() -> tuple[float, float, float] | None:
    parts = read_text("/proc/loadavg").split()
    if len(parts) < 3:
        return None
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None


def uptime() -> float:
    parts = read_text("/proc/uptime").split()
    try:
        return float(parts[0])
    except (IndexError, ValueError):
        return 0.0


# --------------------------------------------------------------------------- #
# network
# --------------------------------------------------------------------------- #


def physical_interfaces() -> list[str]:
    """Real NICs only.

    A `device` symlink under /sys/class/net means the interface is backed by
    hardware, which drops lo, docker bridges, veth pairs and tunnels in one go
    -- a machine running containers has dozens of those and summing them all
    would double-count every byte.
    """
    try:
        names = sorted(p.name for p in NET.iterdir())
    except OSError:
        return []
    return [name for name in names if (NET / name / "device").exists()]


def interface_kind(name: str) -> str:
    """"wifi" or "wired" -- wireless drivers expose a phy80211 link."""
    if (NET / name / "phy80211").exists() or (NET / name / "wireless").exists():
        return "wifi"
    return "wired"


def interface_up(name: str) -> bool:
    return read_text(NET / name / "operstate") == "up"


def default_route_interface() -> str:
    """The interface carrying the default route, per /proc/net/route."""
    try:
        with open("/proc/net/route") as handle:
            handle.readline()  # header
            for line in handle:
                parts = line.split()
                # destination 00000000 == 0.0.0.0, i.e. the default route
                if len(parts) > 1 and parts[1] == "00000000":
                    return parts[0]
    except OSError:
        pass
    return ""


def auto_interfaces() -> list[str]:
    """The interface actually carrying traffic right now.

    A laptop has both wifi and ethernet; summing them double-counts nothing but
    shows a link that is down. The default route names the one in use, and it
    follows the user unplugging the cable without them touching Settings.
    """
    physical = physical_interfaces()
    route = default_route_interface()
    if route in physical:
        return [route]
    live = [name for name in physical if interface_up(name)]
    return live or physical


def resolve_interfaces(configured) -> list[str]:
    """Configured selection, dropping anything that no longer exists."""
    physical = physical_interfaces()
    chosen = [n for n in (configured or []) if n in physical]
    return chosen or auto_interfaces()


def counters(interfaces: list[str]) -> dict[str, tuple[int, int]]:
    """{iface: (rx_bytes, tx_bytes)} from /proc/net/dev."""
    wanted = set(interfaces)
    out: dict[str, tuple[int, int]] = {}
    try:
        with open("/proc/net/dev") as handle:
            for line in handle:
                name, _, rest = line.partition(":")
                name = name.strip()
                if name not in wanted:
                    continue
                parts = rest.split()
                if len(parts) < 9:
                    continue
                try:
                    out[name] = (int(parts[0]), int(parts[8]))
                except ValueError:
                    continue
    except OSError:
        return {}
    return out


class NetSampler:
    """Per-interface byte rates from successive /proc/net/dev snapshots."""

    def __init__(self) -> None:
        self.previous: dict[str, tuple[int, int]] = {}
        self.stamp = 0.0

    def sample(self, interfaces: list[str]) -> dict[str, dict]:
        now = time.monotonic()
        current = counters(interfaces)
        elapsed = now - self.stamp
        previous, self.previous, self.stamp = self.previous, current, now
        if not previous or elapsed <= 0:
            return {}
        rates = {}
        for name, (rx, tx) in current.items():
            if name not in previous:
                continue
            old_rx, old_tx = previous[name]
            # Counters wrap on 32-bit kernels and reset when a NIC re-registers.
            down = max(0, rx - old_rx) / elapsed
            up = max(0, tx - old_tx) / elapsed
            rates[name] = {"down": down, "up": up, "rx": rx, "tx": tx}
        return rates


# --------------------------------------------------------------------------- #
# formatting
# --------------------------------------------------------------------------- #


def format_bytes(value: float) -> str:
    """1.5G / 512M / 4.0K -- short enough for a tray label."""
    number = float(value or 0)
    for limit, suffix in ((1024**3, "G"), (1024**2, "M"), (1024, "K")):
        if number >= limit:
            scaled = number / limit
            return f"{scaled:.1f}{suffix}" if scaled < 100 else f"{scaled:.0f}{suffix}"
    return f"{number:.0f}B"


def scale_rate(bytes_per_second: float, unit: str = "bytes") -> tuple[str, str]:
    """(number, unit) for a transfer rate, e.g. ("1.1", "KB") or ("9.0", "Mb")."""
    if unit == "bits":
        bits = float(bytes_per_second or 0) * 8
        for limit, suffix in ((1e9, "Gb"), (1e6, "Mb"), (1e3, "kb")):
            if bits >= limit:
                return f"{bits / limit:.1f}", suffix
        return f"{bits:.0f}", "b"
    number = float(bytes_per_second or 0)
    for limit, suffix in ((1024**3, "GB"), (1024**2, "MB"), (1024, "KB")):
        if number >= limit:
            return f"{number / limit:.1f}", suffix
    return f"{number:.0f}", "B"


def format_rate(bytes_per_second: float, unit: str = "bytes") -> str:
    """Full form for the menu: "1.1 KB/s", "9.0 Mbps"."""
    number, suffix = scale_rate(bytes_per_second, unit)
    return f"{number} {suffix}ps" if unit == "bits" else f"{number} {suffix}/s"



def format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def temperature_state(celsius: float | None, warn: float, hot: float) -> str:
    """Tray icon variant: idle / warm / hot."""
    if celsius is None:
        return "idle"
    if celsius >= hot:
        return "hot"
    if celsius >= warn:
        return "warm"
    return "idle"
