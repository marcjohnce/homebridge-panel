"""Data models for panel devices."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DeviceType(str, Enum):
    LIGHT = "light"
    PLUG = "plug"
    SWITCH = "switch"
    THERMOSTAT = "thermostat"
    FAN = "fan"
    SENSOR = "sensor"
    BLIND = "blind"
    SECURITY = "security"     # contact (window, door, glass break), leak, motion, smoke and CO sensors
    VALUE = "value"           # virtual device: a value received over MQTT
    GARAGE = "garage"         # garage door opener
    VALVE = "valve"           # water valve: generic, irrigation, shower head, faucet
    ALARM = "alarm"           # alarm system (HomeKit SecuritySystem): armed / disarmed / triggered


# Icon names used by the UI (see app/qml/Icons.js):
# light, strip, ceiling, plug, switch, thermostat, radiator, floor, fan, coffee, tv,
# weather, drop, sun
DEFAULT_ICONS = {
    DeviceType.LIGHT: "light",
    DeviceType.PLUG: "plug",
    DeviceType.SWITCH: "switch",
    DeviceType.THERMOSTAT: "thermostat",
    DeviceType.FAN: "fan",
    DeviceType.SENSOR: "thermostat",
    DeviceType.BLIND: "blinds",
    DeviceType.SECURITY: "contact",
    DeviceType.VALUE: "gauge",
    DeviceType.ALARM: "alarm",
    DeviceType.VALVE: "valve",
    DeviceType.GARAGE: "garage",
}

# Kinds of security sensors. A contact sensor can be a window, a door, a plain contact
# (e.g. a cupboard or a gate) or a glass break detector; HomeKit has no glass break type, so
# plugins expose those as contact or motion sensors.
SECURITY_KINDS = ("window", "door", "contact", "glassbreak", "leak", "motion", "presence", "smoke", "co")
SECURITY_ICONS = {"window": "window", "door": "door", "contact": "contact", "glassbreak": "glass",
                  "leak": "leak", "motion": "motion", "presence": "presence",
                  "smoke": "smoke", "co": "co"}
ALARM_KINDS = {"glassbreak", "leak", "smoke", "co"}
# Presence (occupancy) sensors report "present" for as long as someone is in the room: no security
# alerts unless switched on on the panel
QUIET_KINDS = {"presence"}

# What a switch or plug powers; chosen on the panel or with appliance: in config.yaml.
# The kind sets the icon; "fan" puts the device under "Climate", washer and dishwasher
# show "Running" while their plug reports power use.
APPLIANCE_KINDS = ("switch", "plug", "tv", "coffee", "washer", "dishwasher", "fan")
APPLIANCE_ICONS = {k: k for k in APPLIANCE_KINDS}
# Lamp kinds of lights; only the icon changes (lamp: in config.yaml)
LAMP_KINDS = ("bulb", "ceiling", "spot", "wall", "table")
LAMP_ICONS = {"bulb": "light", "ceiling": "ceiling", "spot": "spot", "wall": "wall", "table": "table"}
# Kinds of valves (HomeKit ValveType); generic valves (e.g. water shut-off) go under "Security"
VALVE_KINDS = ("generic", "irrigation", "shower", "faucet")
VALVE_ICONS = {"generic": "valve", "irrigation": "sprinkler", "shower": "shower", "faucet": "faucet"}
KIND_ICONS = {**SECURITY_ICONS, **APPLIANCE_ICONS, **LAMP_ICONS, **VALVE_ICONS}
KIND_KEYS = ("security", "appliance", "lamp", "valve")     # meta keys that hold a device's kind
AREAS = ("light", "climate", "security")      # menu areas a device can be moved to     # triggered = alarm; the others are only "open" / "motion"


@dataclass
class Device:
    id: str
    name: str
    type: DeviceType
    backend: str
    room: str
    icon: str
    state: dict[str, Any] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    reachable: bool = True
    order: int = 100

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d
