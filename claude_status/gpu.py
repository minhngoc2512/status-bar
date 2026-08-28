"""GPU readings: NVIDIA through NVML, AMD/Intel through sysfs.

Backends are probed once at startup and the first working one wins. Every
field is optional -- a backend returns None for anything it cannot see, and
the panel simply omits that line.

Why NVML and not nvidia-smi: measured on a GTX 1650 Ti with driver 580, a full
nvidia-smi query costs ~37 ms versus ~4 ms for the NVML calls below. At a 3 s
poll on the GTK main loop the subprocess is a visible hitch; the shared library
is not.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

from .system import read_int, read_text

DRM = Path("/sys/class/drm")

VENDOR_NVIDIA = "0x10de"
VENDOR_AMD = "0x1002"
VENDOR_INTEL = "0x8086"


class Reading(dict):
    """Plain dict with the fields a panel may render; all optional but ``name``."""


# --------------------------------------------------------------------------- #
# NVIDIA -- NVML
# --------------------------------------------------------------------------- #


class _Utilisation(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _Memory(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_ulonglong),
        ("free", ctypes.c_ulonglong),
        ("used", ctypes.c_ulonglong),
    ]


NVML_TEMPERATURE_GPU = 0
NVML_CLOCK_SM = 1
NVML_CLOCK_MEM = 2


class NvmlGpu:
    """NVIDIA via libnvidia-ml, the library nvidia-smi itself is built on."""

    kind = "nvidia"

    def __init__(self) -> None:
        self.lib = None
        self.handle = None
        self.name = ""

    def open(self) -> bool:
        for candidate in ("libnvidia-ml.so.1", "libnvidia-ml.so"):
            try:
                lib = ctypes.CDLL(candidate)
            except OSError:
                continue
            if lib.nvmlInit_v2() != 0:
                continue
            handle = ctypes.c_void_p()
            if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) != 0:
                lib.nvmlShutdown()
                continue
            buffer = ctypes.create_string_buffer(96)
            if lib.nvmlDeviceGetName(handle, buffer, 96) == 0:
                self.name = buffer.value.decode("utf-8", "replace")
            self.lib, self.handle = lib, handle
            return True
        return False

    def _uint(self, fn, *args) -> int | None:
        value = ctypes.c_uint()
        if fn(self.handle, *args, ctypes.byref(value)) != 0:
            return None
        return value.value

    def read(self, full: bool = True) -> Reading | None:
        """``full=False`` skips clocks and power.

        Measured per call: temperature 0.03 ms and memory 0.02 ms, but each
        clock query costs ~1.2 ms and power ~1.4 ms. Those three are menu-only
        detail, so the panel polls them at a slower cadence than the bar.
        """
        if self.lib is None:
            return None
        out = Reading(name=self.name or "NVIDIA GPU")

        out["temperature"] = self._uint(self.lib.nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU)
        if full:
            out["clock_mhz"] = self._uint(self.lib.nvmlDeviceGetClockInfo, NVML_CLOCK_SM)
            out["memory_clock_mhz"] = self._uint(self.lib.nvmlDeviceGetClockInfo, NVML_CLOCK_MEM)
            milliwatts = self._uint(self.lib.nvmlDeviceGetPowerUsage)
            out["power_watts"] = milliwatts / 1000.0 if milliwatts is not None else None

        rates = _Utilisation()
        if self.lib.nvmlDeviceGetUtilizationRates(self.handle, ctypes.byref(rates)) == 0:
            out["utilisation"] = float(rates.gpu)
            out["memory_utilisation"] = float(rates.memory)
        else:
            out["utilisation"] = out["memory_utilisation"] = None

        memory = _Memory()
        if self.lib.nvmlDeviceGetMemoryInfo(self.handle, ctypes.byref(memory)) == 0:
            out["memory_used"] = int(memory.used)
            out["memory_total"] = int(memory.total)
        else:
            out["memory_used"] = out["memory_total"] = None
        return out

    def close(self) -> None:
        if self.lib is not None:
            try:
                self.lib.nvmlShutdown()
            except OSError:
                pass
            self.lib = self.handle = None


# --------------------------------------------------------------------------- #
# AMD / Intel -- sysfs
# --------------------------------------------------------------------------- #


def _card_hwmon_temp(device: Path) -> float | None:
    try:
        chips = sorted((device / "hwmon").glob("hwmon*"))
    except OSError:
        return None
    for chip in chips:
        milli = read_int(chip / "temp1_input")
        if milli is not None:
            return milli / 1000.0
    return None


def _current_dpm(path: Path) -> int | None:
    """Parse pp_dpm_sclk: the active step is the line marked with '*'."""
    for line in read_text(path).splitlines():
        if not line.endswith("*"):
            continue
        # "1: 1000Mhz *"
        for token in line.replace(":", " ").split():
            digits = "".join(c for c in token if c.isdigit())
            if digits and "hz" in token.lower():
                return int(digits)
    return None


class SysfsGpu:
    """AMD (amdgpu) and Intel (i915) through /sys/class/drm.

    Untested here -- this machine only has an NVIDIA card. The paths are the
    documented amdgpu/i915 sysfs interface; anything missing reads as None and
    is dropped from the menu rather than shown as zero.
    """

    def __init__(self, card: Path, vendor: str) -> None:
        self.card = card
        self.device = card / "device"
        self.kind = "amd" if vendor == VENDOR_AMD else "intel"
        self.name = ""

    def open(self) -> bool:
        # Something readable has to exist, otherwise there is no point.
        probes = (
            self.device / "gpu_busy_percent",
            self.device / "mem_info_vram_total",
            self.card / "gt_cur_freq_mhz",
        )
        if not any(p.exists() for p in probes) and _card_hwmon_temp(self.device) is None:
            return False
        self.name = ("AMD GPU" if self.kind == "amd" else "Intel GPU") + f" ({self.card.name})"
        return True

    def read(self, full: bool = True) -> Reading | None:
        out = Reading(name=self.name)
        busy = read_int(self.device / "gpu_busy_percent")
        out["utilisation"] = float(busy) if busy is not None else None
        out["memory_utilisation"] = None
        out["memory_used"] = read_int(self.device / "mem_info_vram_used")
        out["memory_total"] = read_int(self.device / "mem_info_vram_total")
        out["temperature"] = _card_hwmon_temp(self.device)
        if full:
            out["clock_mhz"] = _current_dpm(self.device / "pp_dpm_sclk") or read_int(
                self.card / "gt_cur_freq_mhz"
            )
            out["memory_clock_mhz"] = _current_dpm(self.device / "pp_dpm_mclk")
            microwatts = None
            try:
                for chip in sorted((self.device / "hwmon").glob("hwmon*")):
                    microwatts = read_int(chip / "power1_average")
                    if microwatts is not None:
                        break
            except OSError:
                microwatts = None
            out["power_watts"] = microwatts / 1e6 if microwatts else None
        return out

    def close(self) -> None:
        pass


# --------------------------------------------------------------------------- #
# detection
# --------------------------------------------------------------------------- #


_backend = None
_probed = False


def shared():
    """The process-wide backend, probed on first use.

    Lazy on purpose: nvmlInit costs ~14 ms and holds a driver handle, so a user
    who never turns the system panel on never pays for it.
    """
    global _backend, _probed
    if not _probed:
        _probed = True
        _backend = detect()
    return _backend


def release() -> None:
    global _backend, _probed
    if _backend is not None:
        _backend.close()
    _backend, _probed = None, False


def detect():
    """First working backend, or None when there is no readable GPU."""
    cards = []
    try:
        cards = sorted(p for p in DRM.glob("card[0-9]*") if (p / "device").exists())
    except OSError:
        cards = []

    vendors = {card: read_text(card / "device/vendor") for card in cards}

    if VENDOR_NVIDIA in vendors.values() or not cards:
        backend = NvmlGpu()
        if backend.open():
            return backend

    for card, vendor in vendors.items():
        if vendor in (VENDOR_AMD, VENDOR_INTEL):
            backend = SysfsGpu(card, vendor)
            if backend.open():
                return backend
    return None
