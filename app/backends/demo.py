"""Simulated devices – for trying out the UI without Homebridge."""
from __future__ import annotations

import copy
import random
from typing import Any

from ..hap_types import Char, ServiceSnapshot
from .base import Backend

_DEVICES = [
    ("living-ceiling", "Lightbulb", "Living Room Ceiling Light",
     [("On", True, True, {}), ("Brightness", 70, True, dict(min=0, max=100, step=1))]),
    ("living-strip", "Lightbulb", "LED Strip",
     [("On", False, True, {}), ("Brightness", 40, True, dict(min=0, max=100, step=1)),
      ("Hue", 30, True, dict(min=0, max=360)), ("Saturation", 80, True, dict(min=0, max=100))]),
    ("kitchen-light", "Lightbulb", "Kitchen Light",
     [("On", False, True, {}), ("Brightness", 100, True, dict(min=0, max=100, step=1)),
      ("ColorTemperature", 300, True, dict(min=140, max=500, step=1))]),
    ("coffee", "Outlet", "Coffee Maker", [("On", False, True, {}), ("OutletInUse", False, False, {})]),
    ("tv", "Outlet", "TV Plug", [("On", True, True, {}), ("OutletInUse", True, False, {})]),
    ("heating-living", "Thermostat", "Living Room Heating",
     [("TargetHeatingCoolingState", 1, True, dict(min=0, max=3)), ("CurrentHeatingCoolingState", 1, False, {}),
      ("TargetTemperature", 21.0, True, dict(min=10, max=30, step=0.5)), ("CurrentTemperature", 19.6, False, {})]),
    ("heating-bath", "Thermostat", "Bathroom Heating",
     [("TargetHeatingCoolingState", 0, True, dict(min=0, max=3)), ("CurrentHeatingCoolingState", 0, False, {}),
      ("TargetTemperature", 22.0, True, dict(min=10, max=30, step=0.5)), ("CurrentTemperature", 18.4, False, {})]),
    ("fan", "Fan", "Fan",
     [("On", False, True, {}), ("RotationSpeed", 50, True, dict(min=0, max=100))]),
    ("weather-station", "Sensor", "Weather Station",
     [("CurrentTemperature", 6.5, False, {}), ("CurrentRelativeHumidity", 82.0, False, {}),
      ("AirPressure", 1014.2, False, {})]),
    ("living-climate", "Sensor", "Living Room Climate",
     [("CurrentTemperature", 21.2, False, {}), ("CurrentRelativeHumidity", 46.0, False, {})]),
    ("hall-light", "Sensor", "Hall Light Sensor", [("CurrentAmbientLightLevel", 320.0, False, {})]),
]

# Simulated drift per poll for sensor readings: (step, lower bound, upper bound, decimals)
_SENSOR_DRIFT = {
    "CurrentTemperature": (0.05, -10.0, 30.0, 1),
    "CurrentRelativeHumidity": (0.3, 20.0, 99.0, 0),
    "AirPressure": (0.2, 980.0, 1040.0, 1),
    "CurrentAmbientLightLevel": (6.0, 50.0, 900.0, 0),
}


class DemoBackend(Backend):
    def __init__(self, name: str = "demo"):
        super().__init__(name)
        self._services: dict[str, ServiceSnapshot] = {}
        for key, stype, nm, chars in _DEVICES:
            self._services[key] = ServiceSnapshot(
                key=key, service_type=stype, name=nm,
                chars={c: Char(name=c, value=v, writable=w, ref=(key, c), **kw) for c, v, w, kw in chars},
            )

    def _simulate(self) -> None:
        for s in self._services.values():
            if s.service_type != "Thermostat":
                continue
            cur, tgt = s.chars["CurrentTemperature"], s.chars["TargetTemperature"].value
            heating = s.chars["TargetHeatingCoolingState"].value != 0 and cur.value < tgt
            s.chars["CurrentHeatingCoolingState"].value = 1 if heating else 0
            drift = 0.1 if heating else -0.03
            cur.value = round(max(15.0, min(28.0, cur.value + drift + random.uniform(-0.02, 0.02))), 1)
        for s in self._services.values():
            if s.service_type != "Sensor":
                continue
            for name, ch in s.chars.items():
                step, lo, hi, digits = _SENSOR_DRIFT[name]
                ch.value = round(max(lo, min(hi, ch.value + random.uniform(-step, step))), digits)
        coffee = self._services["coffee"].chars
        coffee["OutletInUse"].value = bool(coffee["On"].value)

    async def fetch(self) -> list[ServiceSnapshot]:
        self._simulate()
        return copy.deepcopy(list(self._services.values()))

    async def write(self, writes: list[tuple[Char, Any]]) -> None:
        for ch, value in writes:
            key, cname = ch.ref
            self._services[key].chars[cname].value = value
