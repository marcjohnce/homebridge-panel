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
}


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
