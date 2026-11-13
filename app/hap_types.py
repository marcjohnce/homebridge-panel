"""HAP types (Apple HomeKit Accessory Protocol) and their translation into panel devices.

Both backends (direct HAP access and the Homebridge UI API) deliver services with
characteristics. This module turns them into a uniform device state and, in the
other direction, translates a panel command (e.g. {"on": true, "brightness": 40})
into characteristic writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .i18n import tr
from .models import APPLIANCE_KINDS, DeviceType

HAP_BASE_SUFFIX = "-0000-1000-8000-0026BB765291"
# Eve (Elgato) custom types: air pressure is not an Apple-defined characteristic
EVE_WEATHER_SERVICE = "E863F001-079E-48FF-8F27-9C2605A29F52"
EVE_AIR_PRESSURE_SERVICE = "E863F00A-079E-48FF-8F27-9C2605A29F52"
EVE_AIR_PRESSURE = "E863F10F-079E-48FF-8F27-9C2605A29F52"      # hPa

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
    "82": "HumiditySensor",
    "84": "LightSensor",
    "8A": "TemperatureSensor",
    "8C": "WindowCovering",
    "80": "ContactSensor",
    "83": "LeakSensor",
    "85": "MotionSensor",
    "86": "OccupancySensor",
    EVE_WEATHER_SERVICE: "EveWeather",
    EVE_AIR_PRESSURE_SERVICE: "AirPressureSensor",
}

# Sensor services; all sensors of one accessory are merged into one "Sensor" device
SENSOR_SERVICES = {"TemperatureSensor", "HumiditySensor", "LightSensor", "AirPressureSensor", "EveWeather"}

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
    "10": "CurrentRelativeHumidity",
    "24": "ObstructionDetected",
    "6C": "CurrentHorizontalTiltAngle",
    "6D": "CurrentPosition",
    "6E": "CurrentVerticalTiltAngle",
    "6F": "HoldPosition",
    "72": "PositionState",
    "7B": "TargetHorizontalTiltAngle",
    "7C": "TargetPosition",
    "7D": "TargetVerticalTiltAngle",
    "6B": "CurrentAmbientLightLevel",
    "6A": "ContactSensorState",
    "70": "LeakDetected",
    "22": "MotionDetected",
    "71": "OccupancyDetected",
    EVE_AIR_PRESSURE: "AirPressure",
}
SENSOR_CHARS = {"CurrentTemperature", "CurrentRelativeHumidity", "CurrentAmbientLightLevel", "AirPressure"}

DEVICE_TYPE_BY_SERVICE: dict[str, DeviceType] = {
    "Lightbulb": DeviceType.LIGHT,
    "Outlet": DeviceType.PLUG,
    "Switch": DeviceType.SWITCH,
    "Thermostat": DeviceType.THERMOSTAT,
    "HeaterCooler": DeviceType.THERMOSTAT,
    "Fan": DeviceType.FAN,
    "Fanv2": DeviceType.FAN,
    "Sensor": DeviceType.SENSOR,
    "WindowCovering": DeviceType.BLIND,
    "ContactSensor": DeviceType.SECURITY,
    "LeakSensor": DeviceType.SECURITY,
    "MotionSensor": DeviceType.SECURITY,
    "OccupancySensor": DeviceType.SECURITY,
}

# Security sensors: (characteristic, value meaning "triggered", default kind, selectable kinds)
SECURITY_SERVICES = {
    "ContactSensor": ("ContactSensorState", 1, "contact", ("window", "door", "contact", "glassbreak")),  # 1 = open
    "LeakSensor": ("LeakDetected", 1, "leak", ("leak",)),
    "MotionSensor": ("MotionDetected", True, "motion", ("motion", "glassbreak")),
    "OccupancySensor": ("OccupancyDetected", 1, "motion", ("motion", "glassbreak")),
}

# WindowCovering.PositionState; position 0 = closed, 100 = fully open
POSITION_STATES = {0: "closing", 1: "opening", 2: "stopped"}

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


def merge_sensors(group_key: str, accessory: str, services: list[ServiceSnapshot]) -> ServiceSnapshot:
    """Merges the sensor services of one accessory (e.g. a weather station with temperature,
    humidity and air pressure services) into a single "Sensor" device."""
    chars: dict[str, Char] = {}
    for svc in services:
        for name, ch in svc.chars.items():
            if name in SENSOR_CHARS and name not in chars:
                chars[name] = ch
    name = services[0].name if len(services) == 1 else (accessory or services[0].name)
    return ServiceSnapshot(key=f"{group_key}.sensors", service_type="Sensor", name=name,
                           chars=chars, accessory=accessory)


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

    if s.service_type == "WindowCovering":
        pos = int(round(_num(s.get("CurrentPosition", 0)) or 0))
        target = int(round(_num(s.get("TargetPosition", pos)) or 0))
        state["position"] = pos
        state["target"] = target
        moving = POSITION_STATES.get(int(s.get("PositionState", 2)), "stopped")
        # Many plugins report "stopped" all the time: if the target differs, the blind is moving
        if moving == "stopped" and abs(target - pos) > 1:
            moving = "opening" if target > pos else "closing"
        state["moving"] = moving
        state["on"] = pos > 0
        state["obstructed"] = bool(s.get("ObstructionDetected", False))
        caps += ["on", "position", "stop"]
        tilt = c.get("TargetHorizontalTiltAngle") or c.get("TargetVerticalTiltAngle")
        if tilt is not None:
            state["tilt"] = int(_num(tilt.value) or 0)
            caps.append("tilt")
            meta.update(min_tilt=tilt.min if tilt.min is not None else -90,
                        max_tilt=tilt.max if tilt.max is not None else 90)
    elif s.service_type in SECURITY_SERVICES:
        char, hit, kind, kinds = SECURITY_SERVICES[s.service_type]
        v = s.get(char, 0)
        state["triggered"] = bool(v) if isinstance(hit, bool) else int(v or 0) == hit
        meta.update(security=kind, kinds=list(kinds))
    elif s.service_type == "Sensor":
        if "CurrentRelativeHumidity" in c:
            state["humidity"] = _num(s.get("CurrentRelativeHumidity"))
            caps.append("humidity")
        if "AirPressure" in c:
            state["pressure"] = _num(s.get("AirPressure"))
            caps.append("pressure")
        if "CurrentAmbientLightLevel" in c:
            state["lux"] = _num(s.get("CurrentAmbientLightLevel"))
            caps.append("lux")
        meta["icon_hint"] = ("weather" if "pressure" in caps else
                             "thermostat" if "CurrentTemperature" in c else
                             "drop" if "humidity" in caps else "sun")
    elif s.service_type == "Thermostat":
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
        if s.service_type in ("Switch", "Outlet"):
            meta.update(appliance="plug" if s.service_type == "Outlet" else "switch", kinds=list(APPLIANCE_KINDS))
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
            raise ValueError(tr("Device '{name}' does not support '{feature}'").format(name=s.name, feature=name))
        return c[name]

    for key, value in attrs.items():
        if key == "on":
            on = bool(value)
            if s.service_type == "Thermostat":
                ch = need("TargetHeatingCoolingState")
                writes.append((ch, THERMOSTAT_MODES_REV["heat"] if on else 0))
            elif s.service_type == "WindowCovering":     # on = open fully, off = close
                writes.append((need("TargetPosition"), 100 if on else 0))
            elif "On" in c:
                writes.append((c["On"], on))
            elif "Active" in c:
                writes.append((c["Active"], 1 if on else 0))
            else:
                raise ValueError(tr("Device '{name}' cannot be switched on or off").format(name=s.name))
        elif key == "brightness":
            writes.append((need("Brightness"), int(_clamp(value, need("Brightness"), 0, 100))))
        elif key == "hue":
            writes.append((need("Hue"), _clamp(value, need("Hue"), 0, 360)))
        elif key == "saturation":
            writes.append((need("Saturation"), _clamp(value, need("Saturation"), 0, 100)))
        elif key == "color_temp":
            writes.append((need("ColorTemperature"), int(_clamp(value, need("ColorTemperature"), 140, 500))))
        elif key == "position":
            writes.append((need("TargetPosition"), int(_clamp(value, need("TargetPosition"), 0, 100))))
        elif key == "stop":
            if not value:
                continue
            hold = c.get("HoldPosition")
            if hold is not None and hold.writable:
                writes.append((hold, True))
            else:   # without HoldPosition: target = where the blind is now
                writes.append((need("TargetPosition"), int(_num(s.get("CurrentPosition", 0)) or 0)))
        elif key == "tilt":
            ch = c.get("TargetHorizontalTiltAngle") or c.get("TargetVerticalTiltAngle")
            if ch is None:
                raise ValueError(tr("Device '{name}' does not support '{feature}'").format(name=s.name, feature="tilt"))
            writes.append((ch, int(_clamp(value, ch, -90, 90))))
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
                    raise ValueError(tr("Unknown mode '{mode}'").format(mode=mode))
                writes.append((need("TargetHeatingCoolingState"), THERMOSTAT_MODES_REV[mode]))
            elif s.service_type == "HeaterCooler":
                if mode == "off":
                    writes.append((need("Active"), 0))
                elif mode in HEATERCOOLER_MODES_REV:
                    writes.append((need("Active"), 1))
                    writes.append((need("TargetHeaterCoolerState"), HEATERCOOLER_MODES_REV[mode]))
                else:
                    raise ValueError(tr("Unknown mode '{mode}'").format(mode=mode))
            else:
                raise ValueError(tr("Device '{name}' has no operating modes").format(name=s.name))
        else:
            raise ValueError(tr("Unknown attribute '{key}'").format(key=key))

    for ch, _ in writes:
        if not ch.writable:
            raise ValueError(tr("'{feature}' of '{name}' is read-only").format(feature=ch.name, name=s.name))
    return writes
