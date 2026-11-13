"""Simulierte Geräte – zum Testen der Oberfläche ohne Homebridge."""
from __future__ import annotations

import copy
import random
from typing import Any

from ..hap_types import Char, ServiceSnapshot
from .base import Backend

_DEVICES = [
    ("wz-decke", "Lightbulb", "Deckenlicht Wohnzimmer",
     [("On", True, True, {}), ("Brightness", 70, True, dict(min=0, max=100, step=1))]),
    ("wz-strip", "Lightbulb", "LED-Streifen",
     [("On", False, True, {}), ("Brightness", 40, True, dict(min=0, max=100, step=1)),
      ("Hue", 30, True, dict(min=0, max=360)), ("Saturation", 80, True, dict(min=0, max=100))]),
    ("kueche", "Lightbulb", "Küchenlicht",
     [("On", False, True, {}), ("Brightness", 100, True, dict(min=0, max=100, step=1)),
      ("ColorTemperature", 300, True, dict(min=140, max=500, step=1))]),
    ("kaffee", "Outlet", "Kaffeemaschine", [("On", False, True, {}), ("OutletInUse", False, False, {})]),
    ("tv", "Outlet", "TV-Steckdose", [("On", True, True, {}), ("OutletInUse", True, False, {})]),
    ("heizung-wz", "Thermostat", "Heizung Wohnzimmer",
     [("TargetHeatingCoolingState", 1, True, dict(min=0, max=3)), ("CurrentHeatingCoolingState", 1, False, {}),
      ("TargetTemperature", 21.0, True, dict(min=10, max=30, step=0.5)), ("CurrentTemperature", 19.6, False, {})]),
    ("heizung-bad", "Thermostat", "Heizung Bad",
     [("TargetHeatingCoolingState", 0, True, dict(min=0, max=3)), ("CurrentHeatingCoolingState", 0, False, {}),
      ("TargetTemperature", 22.0, True, dict(min=10, max=30, step=0.5)), ("CurrentTemperature", 18.4, False, {})]),
    ("ventilator", "Fan", "Ventilator",
     [("On", False, True, {}), ("RotationSpeed", 50, True, dict(min=0, max=100))]),
]


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
        coffee = self._services["kaffee"].chars
        coffee["OutletInUse"].value = bool(coffee["On"].value)

    async def fetch(self) -> list[ServiceSnapshot]:
        self._simulate()
        return copy.deepcopy(list(self._services.values()))

    async def write(self, writes: list[tuple[Char, Any]]) -> None:
        for ch, value in writes:
            key, cname = ch.ref
            self._services[key].chars[cname].value = value
