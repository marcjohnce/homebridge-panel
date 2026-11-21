"""Simulated devices – for trying out the UI without Homebridge."""
from __future__ import annotations

import copy
import random
import time
from typing import Any

from ..hap_types import Char, ServiceSnapshot
from .base import Backend
from .eve_sim import ENERGY, THERMO, WEATHER, EveHistorySim, demo_power, demo_pressure, demo_temperatures

# devices with an Eve history: fingerprint, mean temperature, daily swing and mean humidity
_HISTORY = {"weather-station": (WEATHER, 5.0, 4.0, 82.0), "living-climate": (WEATHER, 21.0, 0.7, 46.0),
            "heating-living": (THERMO, 20.0, 1.0, 0.0)}

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
    ("tv", "Outlet", "TV Plug", [("On", True, True, {}), ("OutletInUse", True, False, {}),
                                 ("EvePower", 62.5, False, {}), ("EveEnergy", 48.9, False, {})]),
    ("washer", "Outlet", "Washing Machine", [("On", True, True, {}), ("OutletInUse", True, False, {}),
                                             ("EvePower", 384.0, False, {}), ("EveEnergy", 213.4, False, {})]),
    ("heating-living", "Thermostat", "Living Room Heating",
     [("TargetHeatingCoolingState", 1, True, dict(min=0, max=3)), ("CurrentHeatingCoolingState", 1, False, {}),
      ("TargetTemperature", 21.0, True, dict(min=10, max=30, step=0.5)), ("CurrentTemperature", 19.6, False, {})]),
    ("heating-bath", "Thermostat", "Bathroom Heating",
     [("TargetHeatingCoolingState", 0, True, dict(min=0, max=3)), ("CurrentHeatingCoolingState", 0, False, {}),
      ("TargetTemperature", 22.0, True, dict(min=10, max=30, step=0.5)), ("CurrentTemperature", 18.4, False, {}),
      ("BatteryLevel", 7, False, {})]),                  # radiator thermostat, battery almost empty
    ("fan", "Fan", "Fan",
     [("On", False, True, {}), ("RotationSpeed", 50, True, dict(min=0, max=100))]),
    ("weather-station", "Sensor", "Weather Station",
     [("CurrentTemperature", 6.5, False, {}), ("CurrentRelativeHumidity", 82.0, False, {}),
      ("AirPressure", 1014.2, False, {})]),
    ("living-climate", "Sensor", "Living Room Climate",
     [("CurrentTemperature", 21.2, False, {}), ("CurrentRelativeHumidity", 46.0, False, {})]),
    ("hall-light", "Sensor", "Hall Light Sensor", [("CurrentAmbientLightLevel", 320.0, False, {})]),
    ("living-air", "Sensor", "Air Quality",
     [("AirQuality", 2, False, {}), ("CarbonDioxideLevel", 640.0, False, {}), ("PM2_5Density", 9.0, False, {}),
      ("VOCDensity", 180.0, False, {})]),
    ("living-blinds", "WindowCovering", "Living Room Blinds",
     [("CurrentPosition", 60, False, {}), ("TargetPosition", 60, True, dict(min=0, max=100, step=1)),
      ("PositionState", 2, False, {}), ("HoldPosition", False, True, {}),
      ("CurrentHorizontalTiltAngle", 30, False, {}),
      ("TargetHorizontalTiltAngle", 30, True, dict(min=-90, max=90, step=1))]),
    ("terrace-door", "ContactSensor", "Terrace Door", [("ContactSensorState", 0, False, {}),
                                                        ("BatteryLevel", 62, False, {}), ("StatusLowBattery", 0, False, {})]),
    ("bedroom-window", "ContactSensor", "Bedroom Window", [("ContactSensorState", 1, False, {}),
                                                            ("StatusLowBattery", 0, False, {})]),
    ("terrace-glass", "ContactSensor", "Terrace Glass Break", [("ContactSensorState", 0, False, {})]),
    ("washer-leak", "LeakSensor", "Washing Machine Leak", [("LeakDetected", 0, False, {}),     # battery almost empty
                                                             ("BatteryLevel", 4, False, {}), ("StatusLowBattery", 1, False, {})]),
    # without HoldPosition and tilt: stop sets the target to the current position
    ("skylight", "Window", "Skylight",
     [("CurrentPosition", 0, False, {}), ("TargetPosition", 0, True, dict(min=0, max=100)),
      ("PositionState", 2, False, {}), ("ObstructionDetected", False, False, {})]),
    ("speaker", "SmartSpeaker", "Kitchen Speaker",
     [("CurrentMediaState", 1, False, {}), ("TargetMediaState", 1, True, {}), ("Volume", 35, True, dict(min=0, max=100)),
      ("Mute", False, True, {})]),
    ("purifier", "AirPurifier", "Bedroom Air Purifier",
     [("Active", 1, True, {}), ("CurrentAirPurifierState", 2, False, {}), ("TargetAirPurifierState", 1, True, {}),
      ("RotationSpeed", 40, True, dict(min=0, max=100))]),
    ("humidifier", "HumidifierDehumidifier", "Bedroom Humidifier",
     [("Active", 1, True, {}), ("CurrentHumidifierDehumidifierState", 2, False, {}),
      ("TargetHumidifierDehumidifierState", 1, True, dict(min=0, max=2)), ("CurrentRelativeHumidity", 38, False, {}),
      ("RelativeHumidityHumidifierThreshold", 45, True, dict(min=0, max=100)),
      ("RelativeHumidityDehumidifierThreshold", 60, True, dict(min=0, max=100)), ("WaterLevel", 70, False, {})]),
    ("television", "Television", "Living Room TV",
     [("Active", 0, True, {}), ("ActiveIdentifier", 1, True, {}), ("RemoteKey", None, True, {}),
      ("Mute", False, True, {}), ("VolumeSelector", None, True, {})]),
    ("front-lock", "LockMechanism", "Front Door Lock",
     [("LockCurrentState", 1, False, {}), ("LockTargetState", 1, True, {})]),
    ("garage", "GarageDoorOpener", "Garage Door",
     [("CurrentDoorState", 1, False, {}), ("TargetDoorState", 1, True, {}), ("ObstructionDetected", False, False, {})]),
    ("sprinkler", "Valve", "Garden Sprinkler",
     [("Active", 0, True, {}), ("InUse", 0, False, {}), ("ValveType", 1, False, {}),
      ("SetDuration", 600, True, dict(min=0, max=3600)), ("RemainingDuration", 0, False, {})]),
    ("alarm", "SecuritySystem", "Alarm System",
     [("SecuritySystemCurrentState", 3, False, {}), ("SecuritySystemTargetState", 3, True, dict(min=0, max=3))]),
    ("hall-smoke", "SmokeSensor", "Hall Smoke Detector", [("SmokeDetected", 0, False, {}),
                                                           ("BatteryLevel", 80, False, {})]),
    ("bedroom-blinds", "WindowCovering", "Bedroom Blinds",
     [("CurrentPosition", 0, False, {}), ("TargetPosition", 0, True, dict(min=0, max=100, step=1)),
      ("PositionState", 2, False, {})]),
]
BLIND_STEP = 20   # % per poll

# Simulated drift per poll for sensor readings: (step, lower bound, upper bound, decimals)
_SENSOR_DRIFT = {
    "CurrentTemperature": (0.05, -10.0, 30.0, 1),
    "CurrentRelativeHumidity": (0.3, 20.0, 99.0, 0),
    "AirPressure": (0.2, 980.0, 1040.0, 1),
    "CurrentAmbientLightLevel": (6.0, 50.0, 900.0, 0),
    "AirQuality": (0, 1, 5, 0),
    "CarbonDioxideLevel": (8.0, 420.0, 1600.0, 0),
    "PM2_5Density": (0.4, 1.0, 60.0, 0),
    "VOCDensity": (4.0, 20.0, 900.0, 0),
}


class DemoBackend(Backend):
    def __init__(self, name: str = "demo"):
        super().__init__(name)
        self._services: dict[str, ServiceSnapshot] = {}
        self._valve_started: float | None = None
        self._valve_duration = 0
        for key, stype, nm, chars in _DEVICES:
            self._services[key] = ServiceSnapshot(
                key=key, service_type=stype, name=nm,
                chars={c: Char(name=c, value=v, writable=w, ref=(key, c), **kw) for c, v, w, kw in chars},
            )
        # Eve history (temperature charts)
        self.history: dict[str, EveHistorySim] = {}
        now = time.time()
        for key, (fingerprint, base, swing, humidity) in _HISTORY.items():
            if fingerprint is WEATHER:
                # humidity falls when it gets warmer; like fakegato-history, the living room
                # sensor without a barometer records 0 hPa
                raw = [(t, [round(v * 100), round(max(0.0, min(100.0, humidity - 3 * (v - base))) * 100),
                            round(demo_pressure(t) * 10) if key == "weather-station" else 0])
                       for t, v in demo_temperatures(now, base, swing)]
            else:
                raw = [(t, [round(v * 100), 2100, 40, 0, 0]) for t, v in demo_temperatures(now, base, swing)]
            self.history[key] = EveHistorySim(fingerprint, raw)
            self._services[key].history = {part: (key, part) for part in ("status", "entries", "request")}
        # power history of the washing machine plug (fakegato "energy")
        self.history["washer"] = EveHistorySim(ENERGY, [(t, [round(w * 10)]) for t, w in demo_power(now)])
        self._services["washer"].history = {part: ("washer", part) for part in ("status", "entries", "request")}
        # input sources of the television: services of their own, linked to it
        for ident, label in ((1, "HDMI 1"), (2, "HDMI 2"), (3, "Netflix")):
            key = f"tv-input-{ident}"
            self._services["television"].linked.append(ServiceSnapshot(
                key=key, service_type="InputSource", name=label,
                chars={c: Char(name=c, value=v, ref=(key, c)) for c, v in (
                    ("Identifier", ident), ("ConfiguredName", label), ("IsConfigured", 1),
                    ("CurrentVisibilityState", 0))}))

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
        for s in self._services.values():
            if s.service_type not in ("WindowCovering", "Window"):
                continue
            cur, tgt = s.chars["CurrentPosition"], s.chars["TargetPosition"].value
            diff = tgt - cur.value
            cur.value += max(-BLIND_STEP, min(BLIND_STEP, diff))
            s.chars["PositionState"].value = 2 if cur.value == tgt else (1 if tgt > cur.value else 0)
            if "TargetHorizontalTiltAngle" in s.chars:
                s.chars["CurrentHorizontalTiltAngle"].value = s.chars["TargetHorizontalTiltAngle"].value
        alarm = self._services["alarm"].chars        # the alarm system follows its target (unless triggered)
        if alarm["SecuritySystemCurrentState"].value != 4:
            alarm["SecuritySystemCurrentState"].value = alarm["SecuritySystemTargetState"].value
        spk = self._services["speaker"].chars          # the speaker follows play / pause / stop
        spk["CurrentMediaState"].value = spk["TargetMediaState"].value
        pur = self._services["purifier"].chars
        pur["CurrentAirPurifierState"].value = 2 if pur["Active"].value else 0
        hum = self._services["humidifier"].chars
        mode, now = hum["TargetHumidifierDehumidifierState"].value, hum["CurrentRelativeHumidity"].value
        low, high = hum["RelativeHumidityHumidifierThreshold"].value, hum["RelativeHumidityDehumidifierThreshold"].value
        hum["CurrentHumidifierDehumidifierState"].value = (
            0 if not hum["Active"].value else 2 if mode in (0, 1) and now < low else 3 if mode in (0, 2) and now > high else 1)
        lock = self._services["front-lock"].chars      # the lock follows its target
        lock["LockCurrentState"].value = lock["LockTargetState"].value
        door = self._services["garage"].chars        # the garage door moves within one poll
        cur, tgt = door["CurrentDoorState"], door["TargetDoorState"].value
        if tgt == 0 and cur.value != 0:
            cur.value = 0 if cur.value == 2 else 2          # opening, then open
        elif tgt == 1 and cur.value != 1:
            cur.value = 1 if cur.value == 3 else 3          # closing, then closed
        valve = self._services["sprinkler"].chars    # the sprinkler runs for its set duration
        if valve["Active"].value and self._valve_started is not None:
            # like real valves: a new run time applies to the next run, not the running one
            left = self._valve_duration - int(time.monotonic() - self._valve_started)
            valve["RemainingDuration"].value = max(0, left)
            if left <= 0:
                valve["Active"].value = valve["InUse"].value = 0
                self._valve_started = None
        coffee = self._services["coffee"].chars
        coffee["OutletInUse"].value = bool(coffee["On"].value)
        tv = self._services["tv"].chars             # a plug that measures: power only while on
        tv["EvePower"].value = 62.5 if tv["On"].value else 0.0

    async def fetch(self) -> list[ServiceSnapshot]:
        self._simulate()
        return copy.deepcopy(list(self._services.values()))

    async def read_char(self, ref: tuple[str, str]) -> Any:
        sim = self.history[ref[0]]
        return sim.status() if ref[1] == "status" else sim.read_entries()

    async def write_char(self, ref: tuple[str, str], value: Any) -> None:
        self.history[ref[0]].request(value)

    async def write(self, writes: list[tuple[Char, Any]]) -> None:
        for ch, value in writes:
            key, cname = ch.ref
            chars = self._services[key].chars
            if cname == "HoldPosition":     # stop where the blind is now
                chars["TargetPosition"].value = chars["CurrentPosition"].value
                continue
            chars[cname].value = value
            if key == "sprinkler" and cname == "Active":
                chars["InUse"].value = 1 if value else 0
                chars["RemainingDuration"].value = chars["SetDuration"].value if value else 0
                self._valve_started = time.monotonic() if value else None
                self._valve_duration = chars["SetDuration"].value
            if cname == "TargetPosition" and "PositionState" in chars:
                cur = chars["CurrentPosition"].value
                chars["PositionState"].value = 2 if value == cur else (1 if value > cur else 0)
