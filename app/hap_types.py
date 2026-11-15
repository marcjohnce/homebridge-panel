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
from .models import APPLIANCE_KINDS, LAMP_KINDS, DeviceType

HAP_BASE_SUFFIX = "-0000-1000-8000-0026BB765291"
# Eve (Elgato) custom types: air pressure is not an Apple-defined characteristic
EVE_WEATHER_SERVICE = "E863F001-079E-48FF-8F27-9C2605A29F52"
EVE_AIR_PRESSURE_SERVICE = "E863F00A-079E-48FF-8F27-9C2605A29F52"
EVE_AIR_PRESSURE = "E863F10F-079E-48FF-8F27-9C2605A29F52"      # hPa
# Eve history (fakegato-history, homebridge-lib): see app/eve_history.py
EVE_HISTORY_SERVICE = "E863F007-079E-48FF-8F27-9C2605A29F52"
EVE_HISTORY_CHARS = {"E863F116-079E-48FF-8F27-9C2605A29F52": "status",
                     "E863F117-079E-48FF-8F27-9C2605A29F52": "entries",
                     "E863F11C-079E-48FF-8F27-9C2605A29F52": "request"}

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
    "8D": "AirQualitySensor",
    "97": "CarbonDioxideSensor",
    "8C": "WindowCovering",
    "80": "ContactSensor",
    "83": "LeakSensor",
    "85": "MotionSensor",
    "86": "OccupancySensor",
    "87": "SmokeSensor",
    "7E": "SecuritySystem",
    "D0": "Valve",
    "41": "GarageDoorOpener",
    "45": "LockMechanism",
    "D8": "Television",
    "D9": "InputSource",
    "113": "Speaker",            # also the speaker of a television (same type)
    "228": "SmartSpeaker",
    "81": "Door",
    "8B": "Window",
    "BB": "AirPurifier",
    "BD": "HumidifierDehumidifier",
    "7F": "CarbonMonoxideSensor",
    "96": "Battery",
    EVE_WEATHER_SERVICE: "EveWeather",
    EVE_AIR_PRESSURE_SERVICE: "AirPressureSensor",
}

# Sensor services; all sensors of one accessory are merged into one "Sensor" device
SENSOR_SERVICES = {"TemperatureSensor", "HumiditySensor", "LightSensor", "AirPressureSensor", "EveWeather",
                   "AirQualitySensor", "CarbonDioxideSensor"}

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
    "95": "AirQuality",
    "C6": "PM2_5Density",
    "C7": "PM10Density",
    "C8": "VOCDensity",
    "92": "CarbonDioxideDetected",
    "93": "CarbonDioxideLevel",
    "70": "LeakDetected",
    "22": "MotionDetected",
    "71": "OccupancyDetected",
    "76": "SmokeDetected",
    "66": "SecuritySystemCurrentState",
    "D2": "InUse",
    "E": "CurrentDoorState",
    "1D": "LockCurrentState",
    "1E": "LockTargetState",
    "E7": "ActiveIdentifier",
    "E1": "RemoteKey",
    "E6": "Identifier",
    "DB": "InputSourceType",
    "D6": "IsConfigured",
    "135": "CurrentVisibilityState",
    "11A": "Mute",
    "E0": "CurrentMediaState",
    "137": "TargetMediaState",
    "A9": "CurrentAirPurifierState",
    "A8": "TargetAirPurifierState",
    "B3": "CurrentHumidifierDehumidifierState",
    "B4": "TargetHumidifierDehumidifierState",
    "CA": "RelativeHumidityHumidifierThreshold",
    "C9": "RelativeHumidityDehumidifierThreshold",
    "B5": "WaterLevel",
    "119": "Volume",
    "EA": "VolumeSelector",
    "32": "TargetDoorState",
    "D3": "SetDuration",
    "D4": "RemainingDuration",
    "D5": "ValveType",
    "67": "SecuritySystemTargetState",
    "69": "CarbonMonoxideDetected",
    "68": "BatteryLevel",
    "79": "StatusLowBattery",
    EVE_AIR_PRESSURE: "AirPressure",
}
SENSOR_CHARS = {"CurrentTemperature", "CurrentRelativeHumidity", "CurrentAmbientLightLevel", "AirPressure",
                "AirQuality", "PM2_5Density", "PM10Density", "VOCDensity", "CarbonDioxideDetected", "CarbonDioxideLevel"}

# Battery of a battery powered accessory: a service of its own whose values are attached to
# every device of the accessory (some sensors also carry StatusLowBattery themselves)
BATTERY_CHARS = {"BatteryLevel", "StatusLowBattery"}
LOW_BATTERY_LEVEL = 10      # below this a battery counts as almost empty


def attach_battery(snaps: list["ServiceSnapshot"], battery: dict[str, "Char"]) -> None:
    """Adds the battery characteristics of an accessory to its devices (own values win)."""
    for snap in snaps:
        for name, ch in battery.items():
            snap.chars.setdefault(name, ch)


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
    "SmokeSensor": DeviceType.SECURITY,
    "SecuritySystem": DeviceType.ALARM,
    "Valve": DeviceType.VALVE,
    "GarageDoorOpener": DeviceType.GARAGE,
    "LockMechanism": DeviceType.LOCK,
    "Television": DeviceType.TV,
    "Speaker": DeviceType.SPEAKER,
    "SmartSpeaker": DeviceType.SPEAKER,
    "Door": DeviceType.BLIND,             # motorized door / window: moved like a blind, shown under Security
    "Window": DeviceType.BLIND,
    "AirPurifier": DeviceType.PURIFIER,
    "HumidifierDehumidifier": DeviceType.HUMIDIFIER,
    "CarbonMonoxideSensor": DeviceType.SECURITY,
    "Value": DeviceType.VALUE,          # virtual device from MQTT (app/backends/mqtt.py)
}

# Security sensors: (characteristic, value meaning "triggered", default kind, selectable kinds)
SECURITY_SERVICES = {
    "ContactSensor": ("ContactSensorState", 1, "contact", ("window", "door", "contact", "glassbreak")),  # 1 = open
    "LeakSensor": ("LeakDetected", 1, "leak", ("leak",)),
    "MotionSensor": ("MotionDetected", True, "motion", ("motion", "presence", "glassbreak")),
    "OccupancySensor": ("OccupancyDetected", 1, "presence", ("presence", "motion", "glassbreak")),
    "SmokeSensor": ("SmokeDetected", 1, "smoke", ("smoke",)),
    "CarbonMonoxideSensor": ("CarbonMonoxideDetected", 1, "co", ("co",)),
}

# Television: input sources and the speaker are services of their own in the same accessory;
# they are attached to the television (see attach_tv_parts)
TV_PARTS = {"InputSource", "Speaker"}
SPEAKER_CHARS = {"Mute", "Volume", "VolumeSelector"}
# RemoteKey values (HAP); the panel offers these
REMOTE_KEYS = {"rewind": 0, "forward": 1, "up": 4, "down": 5, "left": 6, "right": 7, "select": 8, "back": 9,
               "play_pause": 11, "info": 15}


def attach_tv_parts(snaps: list["ServiceSnapshot"], parts: list["ServiceSnapshot"]) -> None:
    """Adds input sources and the speaker of an accessory to its television service. Without a
    television a speaker is a device of its own (added to snaps)."""
    tv = next((s for s in snaps if s.service_type == "Television"), None)
    if tv is None:
        snaps += [p for p in parts if p.service_type == "Speaker"]
        return
    for part in parts:
        if part.service_type == "InputSource":
            tv.linked.append(part)
        else:
            for name, ch in part.chars.items():
                if name in SPEAKER_CHARS:
                    tv.chars.setdefault(name, ch)


# SmartSpeaker media states (current: 0 play, 1 pause, 2 stop, 4 loading, 5 interrupted)
MEDIA_STATES = {0: "playing", 1: "paused", 2: "stopped", 4: "loading", 5: "interrupted"}
MEDIA_TARGETS = {"play": 0, "pause": 1, "stop": 2}
# HumidifierDehumidifier: activity and target mode
HUMIDIFIER_STATES = {0: "inactive", 1: "idle", 2: "humidifying", 3: "dehumidifying"}
HUMIDIFIER_MODES = {0: "auto", 1: "humidify", 2: "dehumidify"}
HUMIDIFIER_MODES_REV = {v: k for k, v in HUMIDIFIER_MODES.items()}

# LockMechanism: current state (the target is 0 = unsecured, 1 = secured)
LOCK_STATES = {0: "unlocked", 1: "locked", 2: "jammed", 3: "unknown"}

# GarageDoorOpener: current door state; the target is 0 = open, 1 = closed
DOOR_STATES = {0: "open", 1: "closed", 2: "opening", 3: "closing", 4: "stopped"}

# Valve.ValveType
VALVE_TYPES = {0: "generic", 1: "irrigation", 2: "shower", 3: "faucet"}

# SecuritySystem: current state 0–3 like the target state, 4 = alarm triggered
ALARM_MODES = {0: "stay", 1: "away", 2: "night", 3: "off"}
ALARM_MODES_REV = {v: k for k, v in ALARM_MODES.items()}
ALARM_TRIGGERED = 4

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
    valid: list[int] | None = None      # allowed values (HAP "valid-values"), e.g. alarm modes


@dataclass
class ServiceSnapshot:
    key: str                 # unique within the backend
    service_type: str        # e.g. "Lightbulb"
    name: str
    chars: dict[str, Char] = field(default_factory=dict)
    accessory: str = ""      # name of the parent accessory
    linked: list["ServiceSnapshot"] = field(default_factory=list)   # e.g. input sources of a television
    history: dict[str, Any] | None = None   # Eve history of the accessory: refs of status, entries, request

    def get(self, name: str, default: Any = None) -> Any:
        c = self.chars.get(name)
        return default if c is None or c.value is None else c.value


def merge_sensors(group_key: str, accessory: str, services: list[ServiceSnapshot]) -> ServiceSnapshot:
    """Merges the sensor services of one accessory (e.g. a weather station with temperature,
    humidity and air pressure services) into a single "Sensor" device."""
    chars: dict[str, Char] = {}
    for svc in services:
        for name, ch in svc.chars.items():
            if (name in SENSOR_CHARS or name in BATTERY_CHARS) and name not in chars:
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

    if s.service_type in ("Door", "Window"):          # motorized: an opening like a window contact
        meta["opening"] = s.service_type.lower()
    if s.service_type in ("WindowCovering", "Door", "Window"):
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
    elif s.service_type == "Television":
        state["on"] = int(s.get("Active", 0) or 0) == 1
        caps.append("on")
        inputs = []
        for src in s.linked:
            if int(src.get("IsConfigured", 1) or 0) != 1 or int(src.get("CurrentVisibilityState", 0) or 0) != 0:
                continue                                   # hidden or not set up in the Home app
            ident = src.get("Identifier")
            if ident is not None:
                inputs.append({"id": int(ident), "name": src.get("ConfiguredName") or src.get("Name") or src.name})
        if inputs:
            meta["inputs"] = inputs
            caps.append("input")
            active = s.get("ActiveIdentifier")
            state["input"] = int(active) if active is not None else None
            state["input_name"] = next((i["name"] for i in inputs if i["id"] == state["input"]), "")
        if "VolumeSelector" in c:
            caps.append("volume")
        if "Mute" in c:
            state["mute"] = bool(s.get("Mute", False))
            caps.append("mute")
        if "RemoteKey" in c:
            caps.append("remote")
    elif s.service_type in ("Speaker", "SmartSpeaker"):
        if "Volume" in c:
            state["volume"] = int(_num(s.get("Volume")) or 0)
            caps.append("volume")
        if "Mute" in c:
            state["mute"] = bool(s.get("Mute", False))
            caps.append("mute")
        if "TargetMediaState" in c:
            state["media"] = MEDIA_STATES.get(int(s.get("CurrentMediaState", 2) or 0), "stopped")
            state["on"] = state["media"] == "playing"
            caps += ["on", "media"]
        elif "Active" in c:
            state["on"] = int(s.get("Active", 0) or 0) == 1
            caps.append("on")
        elif "Mute" in c:                            # a plain speaker: "on" = not muted
            state["on"] = not state["mute"]
            caps.append("on")
    elif s.service_type == "AirPurifier":
        state["on"] = int(s.get("Active", 0) or 0) == 1
        state["purifying"] = int(s.get("CurrentAirPurifierState", 0) or 0) == 2
        caps.append("on")
        if "TargetAirPurifierState" in c:
            state["auto"] = int(s.get("TargetAirPurifierState", 0) or 0) == 1
            caps.append("auto")
        if "RotationSpeed" in c:
            state["speed"] = _num(s.get("RotationSpeed", 0))
            caps.append("speed")
    elif s.service_type == "HumidifierDehumidifier":
        state["on"] = int(s.get("Active", 0) or 0) == 1
        state["activity"] = HUMIDIFIER_STATES.get(int(s.get("CurrentHumidifierDehumidifierState", 0) or 0), "idle")
        state["mode"] = HUMIDIFIER_MODES.get(int(s.get("TargetHumidifierDehumidifierState", 0) or 0), "auto")
        caps += ["on", "mode"]
        t = c.get("TargetHumidifierDehumidifierState")
        valid = t.valid if t is not None and t.valid else (
            list(range(int(t.min or 0), int(t.max) + 1)) if t is not None and t.max is not None else list(HUMIDIFIER_MODES))
        meta["modes"] = [HUMIDIFIER_MODES[v] for v in sorted(valid) if v in HUMIDIFIER_MODES]
        if "CurrentRelativeHumidity" in c:
            state["humidity"] = _num(s.get("CurrentRelativeHumidity"))
        for char, key in (("RelativeHumidityHumidifierThreshold", "humidify_target"),
                          ("RelativeHumidityDehumidifierThreshold", "dehumidify_target")):
            if char in c:
                state[key] = int(_num(s.get(char)) or 0)
                caps.append(key)
        if "RotationSpeed" in c:
            state["speed"] = _num(s.get("RotationSpeed", 0))
            caps.append("speed")
        if "WaterLevel" in c:
            state["water"] = int(_num(s.get("WaterLevel")) or 0)
    elif s.service_type == "LockMechanism":
        lock = LOCK_STATES.get(int(s.get("LockCurrentState", 3) or 0), "unknown")
        state["lock"] = lock
        state["target"] = "locked" if int(s.get("LockTargetState", 1) or 0) == 1 else "unlocked"
        state["triggered"] = lock in ("unlocked", "jammed")           # not locked: a security alert
        caps.append("on")
        meta["icon_hint"] = "lock" if lock == "locked" else "lockOpen"
    elif s.service_type == "GarageDoorOpener":
        door = DOOR_STATES.get(int(s.get("CurrentDoorState", 1) or 0), "closed")
        state["door"] = door
        state["target"] = "closed" if int(s.get("TargetDoorState", 1) or 0) == 1 else "open"
        state["obstructed"] = bool(s.get("ObstructionDetected", False))
        state["triggered"] = door != "closed" or state["obstructed"]      # not closed: a security alert
        caps.append("on")
    elif s.service_type == "Valve":
        state["on"] = int(s.get("Active", 0) or 0) == 1
        state["in_use"] = int(s.get("InUse", 0) or 0) == 1
        caps.append("on")
        if "SetDuration" in c:
            state["duration"] = int(_num(s.get("SetDuration")) or 0)
            caps.append("duration")
        if "RemainingDuration" in c:
            state["remaining"] = int(_num(s.get("RemainingDuration")) or 0)
        meta.update(valve=VALVE_TYPES.get(int(s.get("ValveType", 0) or 0), "generic"), kinds=list(VALVE_TYPES.values()))
    elif s.service_type == "SecuritySystem":
        cur = int(s.get("SecuritySystemCurrentState", 3) or 0)
        target = ALARM_MODES.get(int(s.get("SecuritySystemTargetState", 3) or 0), "off")
        state["triggered"] = cur == ALARM_TRIGGERED
        state["mode"] = target if cur == ALARM_TRIGGERED else ALARM_MODES.get(cur, "off")
        state["target"] = target
        state["armed"] = state["mode"] != "off" or state["triggered"]
        state["on"] = state["armed"] and not state["triggered"]
        caps.append("mode")
        t = c.get("SecuritySystemTargetState")
        valid = t.valid if t is not None and t.valid else list(ALARM_MODES)
        meta["modes"] = [ALARM_MODES[v] for v in sorted(valid) if v in ALARM_MODES]
        meta["icon_hint"] = "alarm" if state["armed"] else "alarmOff"
    elif s.service_type == "Value":
        state["value"] = s.get("Value")
        meta.update(unit=s.get("Unit", ""), decimals=int(s.get("Decimals", 1)), icon_hint=s.get("Icon") or "none",
                    topic=s.accessory)
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
        # air quality: 1 excellent … 5 poor (0 = unknown, left out); densities in µg/m³, CO₂ in ppm
        if int(s.get("AirQuality", 0) or 0) in range(1, 6):
            state["air_quality"] = int(s.get("AirQuality"))
            caps.append("air_quality")
        for char, key in (("PM2_5Density", "pm25"), ("PM10Density", "pm10"), ("VOCDensity", "voc"),
                          ("CarbonDioxideLevel", "co2")):
            if char in c and _num(s.get(char)) is not None:
                state[key] = _num(s.get(char))
                caps.append(key)
        if "CarbonDioxideDetected" in c:
            state["co2_high"] = int(s.get("CarbonDioxideDetected", 0) or 0) == 1
        meta["icon_hint"] = ("weather" if "pressure" in caps else
                             "thermostat" if "CurrentTemperature" in c else
                             "drop" if "humidity" in caps else
                             "air" if {"air_quality", "co2", "pm25", "pm10", "voc"} & set(caps) else "sun")
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
        elif s.service_type == "Lightbulb":
            meta.update(lamp="bulb", kinds=list(LAMP_KINDS))
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
        if s.history:
            meta["history"] = True          # temperature chart from the Eve history

    level = _num(s.get("BatteryLevel"))
    if level is not None:
        state["battery"] = int(round(level))
    if "StatusLowBattery" in c:
        state["battery_low"] = int(s.get("StatusLowBattery", 0) or 0) == 1

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
            if s.service_type == "LockMechanism":          # on = unlock, off = lock
                writes.append((need("LockTargetState"), 0 if on else 1))
            elif s.service_type == "SmartSpeaker" and "TargetMediaState" in c:     # on = play, off = pause
                writes.append((c["TargetMediaState"], MEDIA_TARGETS["play" if on else "pause"]))
            elif s.service_type == "Speaker" and "Active" not in c:              # a plain speaker: mute
                writes.append((need("Mute"), not on))
            elif s.service_type == "GarageDoorOpener":    # on = open, off = close
                writes.append((need("TargetDoorState"), 0 if on else 1))
            elif s.service_type == "Thermostat":
                ch = need("TargetHeatingCoolingState")
                writes.append((ch, THERMOSTAT_MODES_REV["heat"] if on else 0))
            elif s.service_type in ("WindowCovering", "Door", "Window"):     # on = open fully, off = close
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
        elif key == "input":                     # television: input source by identifier
            writes.append((need("ActiveIdentifier"), int(value)))
        elif key == "volume_step":               # television speaker: +1 louder, -1 quieter
            writes.append((need("VolumeSelector"), 0 if int(value) > 0 else 1))
        elif key == "mute":
            writes.append((need("Mute"), bool(value)))
        elif key == "remote":
            if value not in REMOTE_KEYS:
                raise ValueError(tr("Unknown attribute '{key}'").format(key=f"remote {value}"))
            writes.append((need("RemoteKey"), REMOTE_KEYS[value]))
        elif key == "volume":                    # speaker: 0–100
            writes.append((need("Volume"), int(_clamp(value, need("Volume"), 0, 100))))
        elif key == "media":                     # smart speaker: play / pause / stop
            if value not in MEDIA_TARGETS:
                raise ValueError(tr("Unknown mode '{mode}'").format(mode=value))
            writes.append((need("TargetMediaState"), MEDIA_TARGETS[value]))
        elif key == "auto":                      # air purifier: automatic or manual
            writes.append((need("TargetAirPurifierState"), 1 if value else 0))
        elif key in ("humidify_target", "dehumidify_target"):
            ch = need("RelativeHumidityHumidifierThreshold" if key == "humidify_target"
                      else "RelativeHumidityDehumidifierThreshold")
            writes.append((ch, int(_clamp(value, ch, 0, 100))))
        elif key == "duration":                  # valve: run time in seconds
            ch = need("SetDuration")
            writes.append((ch, int(_clamp(value, ch, 0, 3600))))
        elif key == "mode":
            mode = str(value)
            if s.service_type == "HumidifierDehumidifier":
                if mode not in HUMIDIFIER_MODES_REV:
                    raise ValueError(tr("Unknown mode '{mode}'").format(mode=mode))
                writes.append((need("TargetHumidifierDehumidifierState"), HUMIDIFIER_MODES_REV[mode]))
            elif s.service_type == "SecuritySystem":
                if mode not in ALARM_MODES_REV:
                    raise ValueError(tr("Unknown mode '{mode}'").format(mode=mode))
                writes.append((need("SecuritySystemTargetState"), ALARM_MODES_REV[mode]))
            elif s.service_type == "Thermostat":
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
