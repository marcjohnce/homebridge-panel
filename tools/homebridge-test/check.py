"""Checks the panel against a real Homebridge with the test plugin of this folder.

Every device type must be recognized, and every command must arrive and be read back.

    python tools/homebridge-test/check.py hap                     # HAP, insecure mode, port 51900
    python tools/homebridge-test/check.py ui admin panel-test-1   # Homebridge UI on port 8581
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.backends import create_backends  # noqa: E402
from app.config import AppConfig  # noqa: E402
from app.i18n import set_language  # noqa: E402
from app.manager import DeviceManager  # noqa: E402
from app.qt.format import alert_level, battery_low, category, state_text  # noqa: E402

TYPES = {"Color Light": "light", "White Light": "light", "Plug": "plug", "Switch": "switch", "Fan": "fan",
         "Thermostat": "thermostat", "Blinds": "blind", "Window": "security", "Leak": "security",
         "Motion": "security", "Presence": "security", "Smoke": "security", "CO": "security",
         "Weather": "sensor", "Air": "sensor", "Light Level": "sensor", "Alarm": "alarm",
         "Sprinkler": "valve", "Garage": "garage", "Television": "tv", "Skylight": "blind",
         "Motor Door": "blind", "Speaker": "speaker", "Smart Speaker": "speaker", "Purifier": "purifier",
         "Humidifier": "humidifier", "Lock": "lock"}
COMMANDS = [("Color Light", {"on": False}, "on", False), ("Color Light", {"brightness": 25}, "brightness", 25),
            ("Color Light", {"hue": 200, "saturation": 50}, "hue", 200),
            ("White Light", {"color_temp": 400}, "color_temp", 400), ("Plug", {"on": False}, "on", False),
            ("Switch", {"on": True}, "on", True), ("Fan", {"on": True}, "on", True), ("Fan", {"speed": 80}, "speed", 80),
            ("Thermostat", {"target_temp": 22.5}, "target_temp", 22.5), ("Thermostat", {"mode": "off"}, "mode", "off"),
            ("Blinds", {"position": 30}, "target", 30), ("Alarm", {"mode": "away"}, "mode", "away"),
            ("Alarm", {"mode": "off"}, "mode", "off"), ("Sprinkler", {"duration": 900}, "duration", 900),
            ("Sprinkler", {"on": True}, "remaining", 900), ("Sprinkler", {"on": False}, "on", False),
            ("Garage", {"on": True}, "door", "open"), ("Garage", {"on": False}, "door", "closed"),
            ("Television", {"on": True}, "on", True), ("Television", {"input": 3}, "input_name", "Netflix"),
            ("Television", {"mute": True}, "mute", True), ("Television", {"volume_step": 1}, "mute", True),
            ("Television", {"remote": "select"}, "on", True),
            ("Skylight", {"position": 40}, "position", 40), ("Motor Door", {"on": True}, "position", 100),
            ("Speaker", {"volume": 70}, "volume", 70), ("Speaker", {"on": False}, "mute", True),
            ("Smart Speaker", {"on": True}, "media", "playing"), ("Smart Speaker", {"media": "stop"}, "media", "stopped"),
            ("Purifier", {"on": True}, "purifying", True), ("Purifier", {"auto": False, "speed": 70}, "speed", 70),
            ("Humidifier", {"mode": "dehumidify"}, "mode", "dehumidify"),
            ("Humidifier", {"dehumidify_target": 55}, "dehumidify_target", 55),
            ("Lock", {"on": True}, "lock", "unlocked"), ("Lock", {"on": False}, "lock", "locked")]


async def run(cfg: AppConfig) -> int:
    fails: list[str] = []

    def check(ok: bool, msg: str) -> None:
        print(("  ok   " if ok else "  FAIL ") + msg)
        if not ok:
            fails.append(msg)

    m = DeviceManager(cfg, create_backends(cfg))
    await m.start()
    devs = {d.name: d for d in m.devices.values()}
    for name, d in sorted(devs.items()):
        dd = d.to_dict()
        print(f"  {name:<14} {d.type.value:<10} {category(dd):<9} {state_text(dd):<26} "
              f"{'battery low ' if battery_low(dd) else ''}{'alert' if alert_level(dd) else ''}")
    for name, t in TYPES.items():
        check(name in devs and devs[name].type.value == t, f"{name} is {t}")
    if len(fails) == 0:
        check(devs["Thermostat"].state.get("battery") == 7, "battery level from the Battery service")
        check(devs["Leak"].state.get("battery_low") is True, "StatusLowBattery")
        check(devs["Weather"].state.get("humidity") == 82, "temperature and humidity merged")
        check(devs["Air"].state.get("co2") == 640, "air quality and CO₂ merged")
        check(devs["Presence"].meta.get("security") == "presence", "occupancy sensor = presence")
        check(devs["Alarm"].meta.get("modes") == ["stay", "away", "night", "off"], "alarm modes")
        check([i["name"] for i in devs["Television"].meta.get("inputs", [])] == ["HDMI 1", "HDMI 2", "Netflix"],
              "television input sources")
        for name, attrs, key, want in COMMANDS:
            try:
                await m.command(devs[name].id, attrs)
            except Exception as e:                       # noqa: BLE001 – report and go on
                check(False, f"{name} {attrs}: {e}")
                continue
            await asyncio.sleep(1.5)
            await m.refresh_all()
            got = m.devices[devs[name].id].state.get(key)
            check(got == want, f"{name} {attrs} → {key} = {got!r}")
    # Eve history (only when fakegato-history is installed for the test plugin)
    for name, count, last in (("History Weather", 432, 5.12), ("History Thermostat", 98, 20.1)):
        if name not in devs:
            print(f"  skip {name}: fakegato-history not installed")
            continue
        check(devs[name].meta.get("history") is True, f"{name} has an Eve history")
        try:
            pts = await m.temperature_history(devs[name].id)
        except Exception as e:                           # noqa: BLE001 – report and go on
            check(False, f"{name} history: {e}")
            continue
        check(len(pts) == count and pts[-1][1] == last, f"{name} history: {len(pts)} values, last {pts[-1:]}")
        check(all(b[0] - a[0] == 600 for a, b in zip(pts, pts[1:])), f"{name} history: every 10 minutes")
    await m.stop()
    print("\nFAILED:\n  " + "\n  ".join(fails) if fails else "\nall checks passed")
    return 1 if fails else 0


def main() -> int:
    set_language("en")
    if len(sys.argv) > 1 and sys.argv[1] == "ui":
        user = sys.argv[2] if len(sys.argv) > 2 else "admin"
        password = sys.argv[3] if len(sys.argv) > 3 else "panel-test-1"
        cfg = AppConfig.model_validate({"homebridge_ui": [{"url": "http://127.0.0.1:8581",
                                                            "username": user, "password": password}]})
    else:
        cfg = AppConfig.model_validate({"hap": [{"name": "test", "host": "127.0.0.1", "port": 51900,
                                                  "pin": "031-45-154"}]})
    return asyncio.run(run(cfg))


if __name__ == "__main__":
    sys.exit(main())
