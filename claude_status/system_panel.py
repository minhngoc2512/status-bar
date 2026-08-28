"""System monitor panel: CPU, memory, GPU and network on one indicator."""

from __future__ import annotations

from gi.repository import GLib, Gtk

from . import gpu as gpu_mod
from . import labels
from . import system as sysinfo
from .panel import Panel

# Order the bar label renders in, regardless of the order they were ticked.
BAR_METRICS = ("cpu", "temp", "ram", "gpu", "gpu_temp", "net")

# Detail that only the menu shows and that costs milliseconds to fetch -- every
# NVMe sensor, the GPU clocks and power draw -- is refreshed once every this
# many ticks instead of on each one.
SLOW_EVERY = 8


class SystemPanel(Panel):
    section = "system"
    default_icon = "system-idle"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.cpu_sampler = sysinfo.CpuSampler()
        self.net_sampler = sysinfo.NetSampler()
        self.cpu: float | None = None
        # Discovered once: hwmon paths do not move while the process runs.
        self.sensor_entries = sysinfo.discover_sensors()
        self.sensors: list[dict] = []
        self.cpu_entry: dict | None = None
        self.cpu_sensor: dict | None = None
        # Walking /sys/class/net stats every entry; a laptop's set of NICs does
        # not change between ticks, so it rides the slow cadence too.
        self.chosen_interfaces: list[str] = []
        self.tick = 0
        self.memory: dict = {}
        self.rates: dict[str, dict] = {}
        self.gpu: dict | None = None
        self.timer: int | None = None

    # ------------------------------------------------------------ lifecycle

    @property
    def gpu_backend(self):
        # Probed once per process, on first use: walking /sys/class/drm or
        # loading NVML on every tick would be wasted work, and the answer
        # cannot change while we run.
        return gpu_mod.shared()

    @property
    def gpu_available(self) -> bool:
        return self.gpu_backend is not None

    def gpu_wanted(self) -> bool:
        return self.gpu_available and bool(self.cfg.get("system.gpu", True))

    def apply_config(self) -> None:
        self.set_visible(self.enabled())
        self.stop_timer()
        if not self.enabled():
            self.refresh()
            return
        self.cpu_entry = sysinfo.pick_sensor(
            self.sensor_entries, self.cfg.get("system.temp_sensor") or ""
        )
        self.chosen_interfaces = []
        self.tick = 0
        seconds = max(1, int(self.cfg.get("system.refresh_seconds", 3) or 3))
        self.timer = GLib.timeout_add_seconds(seconds, self.on_timer)
        self.reload()

    def stop_timer(self) -> None:
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None

    def shutdown(self) -> None:
        self.stop_timer()
        gpu_mod.release()

    def on_timer(self) -> bool:
        self.reload()
        return True

    # --------------------------------------------------------------- sample

    def interfaces(self, refresh: bool = False) -> list[str]:
        if refresh or not self.chosen_interfaces:
            self.chosen_interfaces = sysinfo.resolve_interfaces(self.cfg.get("system.interfaces"))
        return self.chosen_interfaces

    def reload(self) -> None:
        """Everything here is a /proc or /sys read, so it stays on the main
        loop rather than going through net.py's worker threads.

        The per-tick path is deliberately narrow: only the one temperature
        sensor being displayed, and only the cheap GPU counters. The rest is
        menu detail and rides the SLOW_EVERY cadence.
        """
        if not self.enabled():
            return
        slow = self.tick % SLOW_EVERY == 0
        self.tick += 1

        self.cpu = self.cpu_sampler.sample()
        self.cpu_sensor = sysinfo.read_sensor(self.cpu_entry)
        self.memory = sysinfo.memory()
        self.rates = self.net_sampler.sample(self.interfaces(refresh=slow))

        if self.gpu_wanted():
            reading = self.gpu_backend.read(full=slow)
            if reading is not None and not slow and self.gpu:
                # Carry forward the fields this pass skipped.
                for key in ("clock_mhz", "memory_clock_mhz", "power_watts"):
                    reading.setdefault(key, self.gpu.get(key))
            self.gpu = reading
        else:
            self.gpu = None

        if slow:
            self.sensors = sysinfo.list_sensors()
        self.refresh()

    def totals(self) -> tuple[float, float]:
        down = sum(r["down"] for r in self.rates.values())
        up = sum(r["up"] for r in self.rates.values())
        return down, up

    def hottest(self) -> float | None:
        """Worst of CPU and GPU: the icon reflects whichever is closer to the edge."""
        readings = [
            value
            for value in (
                self.cpu_sensor["celsius"] if self.cpu_sensor else None,
                (self.gpu or {}).get("temperature"),
            )
            if isinstance(value, (int, float))
        ]
        return max(readings) if readings else None

    # ------------------------------------------------------------------- ui

    def bar_label(self) -> str:
        """Every number is padded to a constant width.

        The status area is right-aligned, so a value growing a digit shifts
        every indicator to the left of this one. See claude_status/labels.py.
        """
        if not self.cfg.get("system.show_label", True):
            return ""
        wanted = set(self.cfg.get("system.bar_metrics") or [])
        unit = self.cfg.get("system.net_unit", "bytes")
        parts = []

        # A rate needs two samples, so the first tick has no CPU or network
        # figure yet. Render a same-width placeholder rather than dropping the
        # field, which would make the whole label jump once on startup.
        if "cpu" in wanted:
            parts.append(f"CPU {labels.percent(self.cpu)}")
        if "temp" in wanted and self.cpu_entry:
            parts.append(labels.temperature((self.cpu_sensor or {}).get("celsius")))
        if "ram" in wanted and self.memory.get("total"):
            parts.append(f"RAM {labels.percent(self.memory['percent'])}")

        # GPU load and GPU temperature share one "GPU" prefix so the label does
        # not read "GPU 38% GPU 46°C".
        gpu_bits = []
        if self.gpu_wanted():
            reading = self.gpu or {}
            if "gpu" in wanted:
                gpu_bits.append(labels.percent(reading.get("utilisation")))
            if "gpu_temp" in wanted:
                gpu_bits.append(labels.temperature(reading.get("temperature")))
        if gpu_bits:
            parts.append("GPU " + " ".join(gpu_bits))

        if "net" in wanted and (self.rates or self.interfaces()):
            down, up = self.totals()
            parts.append(f"↓{labels.rate(down, unit)} ↑{labels.rate(up, unit)}")
        return "  ".join(parts)

    def refresh(self) -> None:
        if not self.visible:
            return
        warn = float(self.cfg.get("system.warn_celsius", 85) or 85)
        hot = float(self.cfg.get("system.hot_celsius", 95) or 95)
        state = sysinfo.temperature_state(self.hottest(), warn, hot)
        self.set_icon(f"system-{state}", self.t("sys.title"))
        self.ind.set_label(self.bar_label(), "system")
        self.ind.set_title(self.t("sys.title"))
        self.build_menu()

    def build_menu(self) -> None:
        t = self.t
        menu = Gtk.Menu()

        if self.cpu is None and not self.memory:
            menu.append(self.info_item(t("sys.sampling")))
            self.append_tail(menu, refresh=True)
            self.set_menu(menu)
            return

        # ---- cpu
        if self.cpu is not None:
            menu.append(self.info_item(t("sys.cpu", v=f"{self.cpu:.0f}")))
        load = sysinfo.loadavg()
        if load:
            menu.append(self.info_item(t("sys.load", a=f"{load[0]:.2f}", b=f"{load[1]:.2f}", c=f"{load[2]:.2f}")))
        if self.cpu_sensor:
            celsius = f"{self.cpu_sensor['celsius']:.0f}"
            menu.append(
                self.info_item(f"{t('sys.cputemp', v=celsius)}   ({self.cpu_sensor['key']})")
            )
        else:
            menu.append(self.info_item(t("sys.notemp")))

        # ---- memory
        if self.memory.get("total"):
            menu.append(Gtk.SeparatorMenuItem())
            menu.append(
                self.info_item(
                    t(
                        "sys.ram",
                        used=sysinfo.format_bytes(self.memory["used"]),
                        total=sysinfo.format_bytes(self.memory["total"]),
                        percent=f"{self.memory['percent']:.0f}",
                    )
                )
            )
            if self.memory.get("swap_total"):
                menu.append(
                    self.info_item(
                        t(
                            "sys.swap",
                            used=sysinfo.format_bytes(self.memory["swap_used"]),
                            total=sysinfo.format_bytes(self.memory["swap_total"]),
                        )
                    )
                )

        # ---- gpu
        menu.append(Gtk.SeparatorMenuItem())
        if not self.gpu_available:
            menu.append(self.info_item(t("sys.nogpu")))
        elif self.gpu:
            menu.append(self.info_item(self.gpu.get("name") or "GPU"))
            head = []
            if self.gpu.get("utilisation") is not None:
                head.append(t("sys.gpu", v=f"{self.gpu['utilisation']:.0f}"))
            if self.gpu.get("temperature") is not None:
                head.append(t("sys.gputemp", v=f"{self.gpu['temperature']:.0f}"))
            if self.gpu.get("power_watts") is not None:
                head.append(t("sys.power", v=f"{self.gpu['power_watts']:.1f}"))
            if head:
                menu.append(self.info_item("    " + "  ·  ".join(head)))
            if self.gpu.get("memory_total"):
                used, total = self.gpu["memory_used"] or 0, self.gpu["memory_total"]
                menu.append(
                    self.info_item(
                        "    "
                        + t(
                            "sys.vram",
                            used=sysinfo.format_bytes(used),
                            total=sysinfo.format_bytes(total),
                            percent=f"{100.0 * used / total:.0f}",
                        )
                    )
                )
            if self.gpu.get("clock_mhz") or self.gpu.get("memory_clock_mhz"):
                menu.append(
                    self.info_item(
                        "    "
                        + t(
                            "sys.clock",
                            core=self.gpu.get("clock_mhz") or "—",
                            memory=self.gpu.get("memory_clock_mhz") or "—",
                        )
                    )
                )

        # ---- network
        menu.append(Gtk.SeparatorMenuItem())
        unit = self.cfg.get("system.net_unit", "bytes")
        if not self.rates:
            menu.append(self.info_item(t("sys.nonet")))
        for name, rate in sorted(self.rates.items()):
            kind = t(f"prefs.iface.{sysinfo.interface_kind(name)}")
            menu.append(self.info_item(t("sys.net", name=name, kind=kind)))
            menu.append(
                self.info_item(
                    "    "
                    + t(
                        "sys.netrate",
                        down=sysinfo.format_rate(rate["down"], unit),
                        up=sysinfo.format_rate(rate["up"], unit),
                    )
                )
            )
            menu.append(
                self.info_item(
                    "    "
                    + t(
                        "sys.nettotal",
                        down=sysinfo.format_bytes(rate["rx"]),
                        up=sysinfo.format_bytes(rate["tx"]),
                    )
                )
            )

        # ---- footer
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(self.info_item(t("sys.uptime", v=sysinfo.format_uptime(sysinfo.uptime()))))
        if self.sensors:
            item = Gtk.MenuItem(label=t("sys.sensors"))
            sub = Gtk.Menu()
            for sensor in self.sensors:
                sub.append(self.info_item(f"{sensor['key']}   {sensor['celsius']:.1f}°C"))
            item.set_submenu(sub)
            menu.append(item)

        self.append_tail(menu, refresh=True)
        self.set_menu(menu)
