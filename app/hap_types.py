"""HAP types (Apple HomeKit Accessory Protocol) and their translation into panel devices.

Both backends (direct HAP access and the Homebridge UI API) deliver services with
characteristics. This module turns them into a uniform device state and, in the
other direction, translates a panel command (e.g. {"on": true, "brightness": 40})
into characteristic writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import DeviceType

HAP_BASE_SUFFIX = "-0000-1000-8000-0026BB765291"

# Service UUIDs (short form) -> name
SERVICE_TYPES: dict[str, str] = {
    "3E": "AccessoryInformation",
    "40": "Fan",
    "B7": "Fanv2",
    "43": "Lightbulb",
    "47": "Outlet",
    "49": "Switch",
    "4A": "Thermostat",
    "BC": "HeaterCooler",
}

# Characteristic UUIDs (short form) -> name
CHAR_TYPES: dict[str, str] = {
    "8": "Brightness",
    "F": "CurrentHeatingCoolingState",
    "11": "CurrentTemperature",
    "12": "HeatingThresholdTemperature",
    "13": "Hue",
    "20": "Manufacturer",
    "21": "Model",
    "23": "Name",
    "25": "On",
    "26": "OutletInUse",
    "29": "RotationSpeed",
    "2F": "Saturation",
    "33": "TargetHeatingCoolingState",
    "35": "TargetTemperature",
    "36": "TemperatureDisplayUnits",
    "B0": "Active",
    "B1": "CurrentHeaterCoolerState",
    "B2": "TargetHeaterCoolerState",
    "CE": "ColorTemperature",
    "E3": "ConfiguredName",
}

DEVICE_TYPE_BY_SERVICE: dict[str, DeviceType] = {
    "Lightbulb": DeviceType.LIGHT,
    "Outlet": DeviceType.PLUG,
    "Switch": DeviceType.SWITCH,
    "Thermostat": DeviceType.THERMOSTAT,
    "HeaterCooler": DeviceType.THERMOSTAT,
    "Fan": DeviceType.FAN,
    "Fanv2": DeviceType.FAN,
}

# Thermostat.TargetHeatingCoolingState
THERMOSTAT_MODES = {0: "off", 1: "heat", 2: "cool", 3: "auto"}
THERMOSTAT_MODES_REV = {v: k for k, v in THERMOSTAT_MODES.items()}
# HeaterCooler.TargetHeaterCoolerState
HEATERCOOLER_MODES = {0: "auto", 1: "heat", 2: "cool"}
HEATERCOOLER_MODES_REV = {v: k for k, v in HEATERCOOLER_MODES.items()}


def short_uuid(uuid: str) -> str:
    """'00000043-0000-1000-8000-0026BB765291' -> '43', '43' -> '43'."""
    u = str(uuid).upper()
    if u.endswith(HAP_BASE_SUFFIX):
        u = u[: -len(HAP_BASE_SUFFIX)].lstrip("0") or "0"
    return u


@dataclass
class Char:
    """A characteristic of a service. `ref` is backend specific (address used for writing)."""
    name: str
    value: Any
    writable: bool = False
    ref: Any = None
    min: float | None = None
    max: float | None = None
    step: float | None = None


@dataclass
class ServiceSnapshot:
    key: str                 # unique within the backend
    service_type: str        # e.g. "Lightbulb"
    name: str
    chars: dict[str, Char] = field(default_factory=dict)
    accessory: str = ""      # name of the parent accessory

    def get(self, name: str, default: Any = None) -> Any:
        c = self.chars.get(name)
        return default if c is None or c.value is None else c.value


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def snapshot_to_state(s: ServiceSnapshot) -> tuple[DeviceType, dict[str, Any], list[str], dict[str, Any]]:
    """Translates a service into (device type, state, capabilities, metadata)."""
    dtype = DEVICE_TYPE_BY_SERVICE[s.service_type]
    state: dict[str, Any] = {}
    caps: list[str] = []
    meta: dict[str, Any] = {}
    c = s.chars

    if s.service_type == "Thermostat":
        mode = THERMOSTAT_MODES.get(int(s.get("TargetHeatingCoolingState", 0)), "off")
        state["mode"] = mode
        state["on"] = mode != "off"
        state["heating"] = int(s.get("CurrentHeatingCoolingState", 0)) == 1
        caps += ["on", "mode"]
        if "TargetTemperature" in c:
            state["target_temp"] = _num(s.get("TargetTemperature"))
            caps.append("target_temp")
            t = c["TargetTemperature"]
            meta.update(min_temp=t.min if t.min is not None else 10,
                        max_temp=t.max if t.max is not None else 30,
                        temp_step=t.step or 0.5)
        tch = c.get("TargetHeatingCoolingState")
        meta["modes"] = ["off", "heat", "auto"] if tch is None or tch.max is None \
            else [THERMOSTAT_MODES[i] for i in range(0, int(tch.max) + 1) if i in THERMOSTAT_MODES]
    elif s.service_type == "HeaterCooler":
        active = int(s.get("Active", 0)) == 1
        hc_mode = HEATERCOOLER_MODES.get(int(s.get("TargetHeaterCoolerState", 1)), "heat")
        state["on"] = active
        state["mode"] = hc_mode if active else "off"
        state["heating"] = int(s.get("CurrentHeaterCoolerState", 0)) == 2
        caps += ["on", "mode"]
        if "HeatingThresholdTemperature" in c:
            t = c["HeatingThresholdTemperature"]
            state["target_temp"] = _num(t.value)
            caps.append("target_temp")
            meta.update(min_temp=t.min if t.min is not None else 10,
                        max_temp=t.max if t.max is not None else 30,
                        temp_step=t.step or 0.5)
        meta["modes"] = ["off", "heat", "auto"]
    else:
        if "On" in c:
            state["on"] = bool(s.get("On", False))
            caps.append("on")
        elif "Active" in c:
            state["on"] = int(s.get("Active", 0)) == 1
            caps.append("on")
        if "Brightness" in c:
            state["brightness"] = int(s.get("Brightness", 0))
            caps.append("brightness")
        if "Hue" in c and "Saturation" in c:
            state["hue"] = _num(s.get("Hue", 0))
            state["saturation"] = _num(s.get("Saturation", 0))
            caps.append("color")
        if "ColorTemperature" in c:
            ct = c["ColorTemperature"]
            state["color_temp"] = int(s.get("ColorTemperature", 300))
            caps.append("color_temp")
            meta.update(min_mired=ct.min or 140, max_mired=ct.max or 500)
        if "RotationSpeed" in c:
            state["speed"] = _num(s.get("RotationSpeed", 0))
            caps.append("speed")
        if "OutletInUse" in c:
            state["in_use"] = bool(s.get("OutletInUse", False))

    if "CurrentTemperature" in c:
        state["current_temp"] = _num(s.get("CurrentTemperature"))
        caps.append("current_temp")

    return dtype, state, caps, meta


def _clamp(v: float, ch: Char, lo: float, hi: float) -> float:
    lo = ch.min if ch.min is not None else lo
    hi = ch.max if ch.max is not None else hi
    v = max(lo, min(hi, float(v)))
    if ch.step:
        v = round(round((v - lo) / ch.step) * ch.step + lo, 4)
    return v


def command_to_writes(s: ServiceSnapshot, attrs: dict[str, Any]) -> list[tuple[Char, Any]]:
    """Translates a panel command into a list of (characteristic, value)."""
    c = s.chars
    writes: list[tuple[Char, Any]] = []

    def need(name: str) -> Char:
        if name not in c:
            raise ValueError(f"Device '{s.name}' does not support '{name}'")
        return c[name]

    for key, value in attrs.items():
        if key == "on":
            on = bool(value)
            if s.service_type == "Thermostat":
                ch = need("TargetHeatingCoolingState")
                writes.append((ch, THERMOSTAT_MODES_REV["heat"] if on else 0))
            elif "On" in c:
                writes.append((c["On"], on))
            elif "Active" in c:
                writes.append((c["Active"], 1 if on else 0))
            else:
                raise ValueError(f"Device '{s.name}' cannot be switched on or off")
        elif key == "brightness":
            writes.append((need("Brightness"), int(_clamp(value, need("Brightness"), 0, 100))))
        elif key == "hue":
            writes.append((need("Hue"), _clamp(value, need("Hue"), 0, 360)))
        elif key == "saturation":
            writes.append((need("Saturation"), _clamp(value, need("Saturation"), 0, 100)))
        elif key == "color_temp":
            writes.append((need("ColorTemperature"), int(_clamp(value, need("ColorTemperature"), 140, 500))))
        elif key == "speed":
            writes.append((need("RotationSpeed"), _clamp(value, need("RotationSpeed"), 0, 100)))
        elif key == "target_temp":
            name = "TargetTemperature" if s.service_type == "Thermostat" else "HeatingThresholdTemperature"
            ch = need(name)
            writes.append((ch, _clamp(value, ch, 10, 30)))
        elif key == "mode":
            mode = str(value)
            if s.service_type == "Thermostat":
                if mode not in THERMOSTAT_MODES_REV:
                    raise ValueError(f"Unknown mode '{mode}'")
                writes.append((need("TargetHeatingCoolingState"), THERMOSTAT_MODES_REV[mode]))
            elif s.service_type == "HeaterCooler":
                if mode == "off":
                    writes.append((need("Active"), 0))
                elif mode in HEATERCOOLER_MODES_REV:
                    writes.append((need("Active"), 1))
                    writes.append((need("TargetHeaterCoolerState"), HEATERCOOLER_MODES_REV[mode]))
                else:
                    raise ValueError(f"Unknown mode '{mode}'")
            else:
                raise ValueError(f"Device '{s.name}' has no operating modes")
        else:
            raise ValueError(f"Unknown attribute '{key}'")

    for ch, _ in writes:
        if not ch.writable:
            raise ValueError(f"'{ch.name}' of '{s.name}' is read-only")
    return writes
