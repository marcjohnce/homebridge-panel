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
    SECURITY = "security"     # contact (window, door, glass break), leak and motion sensors


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
}

# Kinds of security sensors. A contact sensor can be a window, a door, a plain contact
# (e.g. a cupboard or a gate) or a glass break detector; HomeKit has no glass break type, so
# plugins expose those as contact or motion sensors.
SECURITY_KINDS = ("window", "door", "contact", "glassbreak", "leak", "motion")
SECURITY_ICONS = {"window": "window", "door": "door", "contact": "contact", "glassbreak": "glass",
                  "leak": "leak", "motion": "motion"}
ALARM_KINDS = {"glassbreak", "leak"}

# What a switch or plug powers; chosen on the panel or with appliance: in config.yaml.
# The kind sets the icon; "fan" puts the device under "Climate", washer and dishwasher
# show "Running" while their plug reports power use.
APPLIANCE_KINDS = ("switch", "plug", "tv", "coffee", "washer", "dishwasher", "fan")
APPLIANCE_ICONS = {k: k for k in APPLIANCE_KINDS}
KIND_ICONS = {**SECURITY_ICONS, **APPLIANCE_ICONS}
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
