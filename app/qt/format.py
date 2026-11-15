"""Display texts for tiles (no Qt dependency, so they are easy to test)."""
from __future__ import annotations

import re
import time
from typing import Any

from ..i18n import fmt_number, tr
from ..hap_types import LOW_BATTERY_LEVEL
from ..models import ALARM_KINDS

# Menu areas of the home screen and the device types shown in them
CATEGORIES = ("light", "climate", "security")
CATEGORY_OF_TYPE = {"light": "light", "plug": "light", "switch": "light", "blind": "light",
                    "thermostat": "climate", "sensor": "climate", "fan": "climate",
                    "security": "security", "value": "climate", "alarm": "security",
                    "garage": "security", "tv": "light"}

# Motion sensors only raise an alert while an alarm system is armed (set by the controller)
_alarm_armed = False


def set_alarm_armed(armed: bool) -> None:
    global _alarm_armed
    _alarm_armed = armed


def category(d: dict[str, Any]) -> str:
    """Menu area: set on the panel or with area: in config.yaml, else by type (a switch for a fan: climate)."""
    meta = d.get("meta", {})
    if meta.get("area"):
        return meta["area"]
    if meta.get("appliance") == "fan":
        return "climate"
    if d["type"] == "valve":         # water shut-off valves under Security, the others with the switches
        return "security" if meta.get("valve", "generic") == "generic" else "light"
    return CATEGORY_OF_TYPE.get(d["type"], "light")


def battery_low(d: dict[str, Any]) -> bool:
    """Battery almost empty: below 10 % or the device itself reports a low battery."""
    s = d.get("state", {})
    level = s.get("battery")
    return bool(s.get("battery_low")) or (level is not None and level < LOW_BATTERY_LEVEL)


def battery_text(d: dict[str, Any]) -> str:
    """"Battery 7 %" or "Battery low" (devices that only report low / not low)."""
    level = d.get("state", {}).get("battery")
    return tr("Battery {pct} %").format(pct=level) if level is not None else tr("Battery low")


def alert_level(d: dict[str, Any]) -> int:
    """Security sensors: 2 = alarm (leak, glass break, smoke, CO, alarm system triggered),
    1 = open / motion / presence (those only while an alarm system is armed), 0 = quiet."""
    if d["type"] not in ("security", "alarm", "garage") or not d.get("reachable", True) \
            or not d.get("state", {}).get("triggered"):
        return 0
    if d["type"] == "alarm":
        return 2
    if d["type"] == "garage":                # open door: like an open window
        return 0 if d.get("quiet") else 1
    kind = d.get("meta", {}).get("security")
    if d.get("quiet") and kind not in ALARM_KINDS:      # set on the panel: only shown, no alerts
        return 0
    if kind in ("motion", "presence") and not _alarm_armed:
        return 0
    return 2 if kind in ALARM_KINDS else 1


def _open_for(since: float | None) -> str:
    minutes = int((time.time() - since) // 60) if since else 0
    if minutes < 1:
        return tr("Open")
    if minutes < 60:
        return tr("Open for {n} min").format(n=minutes)
    return tr("Open for {n} h").format(n=minutes // 60)


def value_text(d: dict[str, Any]) -> str:
    """Virtual device: "1.6 bar" (number with its decimals and unit) or the text received."""
    v, m = d.get("state", {}).get("value"), d.get("meta", {})
    if v is None:
        return tr("No reading")
    text = fmt_number(float(v), int(m.get("decimals", 1)), group=False) if isinstance(v, (int, float)) \
        and not isinstance(v, bool) else str(v)
    return f"{text} {m['unit']}".strip() if m.get("unit") else text


def security_text(d: dict[str, Any]) -> str:
    kind = d.get("meta", {}).get("security", "contact")
    hit = bool(d.get("state", {}).get("triggered"))
    if kind in ("window", "door", "contact"):
        return _open_for(d.get("since")) if hit else tr("Closed")
    if kind == "glassbreak":
        return tr("Glass break detected") if hit else tr("No alarm")
    if kind == "leak":
        return tr("Water detected") if hit else tr("Dry")
    if kind == "smoke":
        return tr("Smoke detected") if hit else tr("No smoke")
    if kind == "co":
        return tr("CO detected") if hit else tr("No CO")
    if kind == "presence":
        return tr("Present") if hit else tr("Nobody there")
    return tr("Motion") if hit else tr("No motion")


def garage_text(d: dict[str, Any]) -> str:
    s = d.get("state", {})
    if s.get("obstructed"):
        return tr("Obstructed")
    door = s.get("door", "closed")
    if door == "opening":
        return tr("Opening …")
    if door == "closing":
        return tr("Closing …")
    if door == "stopped":
        return tr("Stopped")
    if door == "open":
        return _open_for(d.get("since"))
    return tr("Closed")


def valve_text(s: dict[str, Any]) -> str:
    """"Closed", "Open", "Running" or "Running, 8 min left"."""
    if not s.get("on"):
        return tr("Closed")
    left = int(s.get("remaining") or 0)
    if left > 0:
        return tr("Running, {n} min left").format(n=max(1, -(-left // 60)))
    return tr("Running") if s.get("in_use") else tr("Open")


def alarm_mode_label(mode: str) -> str:
    return {"stay": tr("Home"), "away": tr("Away"), "night": tr("Night"), "off": tr("Disarmed")}.get(mode, mode)


def alarm_text(s: dict[str, Any]) -> str:
    """"Armed – Away", "Disarmed", "Alarm triggered!" or "Switching to Night …" while it changes."""
    if s.get("triggered"):
        return tr("Alarm triggered!")
    target, mode = s.get("target", "off"), s.get("mode", "off")
    if target != mode:
        return tr("Switching to {mode} …").format(mode=alarm_mode_label(target))
    if mode == "off":
        return tr("Disarmed")
    return tr("Armed – {mode}").format(mode=alarm_mode_label(mode))


def fmt_temp(v: Any) -> str:
    if v is None:
        return "–"
    return fmt_number(float(v), 1)


def pct(v: Any) -> str:
    return tr("{pct}%").format(pct=round(float(v)))


def fmt_lux(v: Any) -> str:
    v = float(v)
    return tr("{lux} lx").format(lux=fmt_number(v, 1 if v < 10 else 0))


def sensor_parts(s: dict[str, Any]) -> list[str]:
    """Readings of a sensor as short texts, e.g. ["6.5 °C", "82%", "1014 hPa"]."""
    parts = []
    if s.get("current_temp") is not None:
        parts.append(tr("{temp} °C").format(temp=fmt_temp(s["current_temp"])))
    if s.get("humidity") is not None:
        parts.append(pct(s["humidity"]))
    if s.get("pressure") is not None:
        parts.append(tr("{hpa} hPa").format(hpa=fmt_number(float(s["pressure"]), 0, group=False)))
    if s.get("lux") is not None:
        parts.append(fmt_lux(s["lux"]))
    if s.get("air_quality"):
        parts.append(tr("Air {level}").format(level=air_level(s["air_quality"])))
    if s.get("co2") is not None:
        parts.append(tr("{ppm} ppm").format(ppm=fmt_number(float(s["co2"]), 0, group=False)))
    return parts


def air_level(q: int) -> str:
    """HomeKit air quality 1–5 as a word (lower case, used after "Air")."""
    return {1: tr("excellent"), 2: tr("good"), 3: tr("fair"), 4: tr("inferior"), 5: tr("poor")}.get(int(q), "")


def air_warning(d: dict[str, Any]) -> bool:
    """Bad air: quality inferior or poor, or the CO₂ sensor reports a high level."""
    s = d.get("state", {})
    return d["type"] == "sensor" and d.get("reachable", True) and (int(s.get("air_quality") or 0) >= 4 or bool(s.get("co2_high")))


def short_name(name: str, room: str) -> str:
    """Tiles already show the room: "Living Room Heating" → "Heating"."""
    room = (room or "").strip()
    if not room or name.casefold() == room.casefold():
        return name
    short = re.sub(rf"(^|\s|-){re.escape(room)}(?=$|\s|-)", " ", name, count=1, flags=re.IGNORECASE)
    # leftover connecting words in the supported languages ("Light in the Bathroom" -> "Light")
    short = re.sub(r"\s+(in|in the|of|of the|at|at the|im|in der|der|des|vom|"
                   r"de|du|de la|dans|dans le|dans la|del|della|nel|nella|en|en el|en la)\s*$",
                   "", short, flags=re.IGNORECASE)
    short = re.sub(r"\s{2,}", " ", short).strip(" -")
    return short or name


def state_text(d: dict[str, Any]) -> str:
    if not d.get("reachable", True):
        return tr("Not reachable")
    s = d.get("state", {})
    if d["type"] == "value":
        return value_text(d)
    if d["type"] == "alarm":
        return alarm_text(s)
    if d["type"] == "valve":
        return valve_text(s)
    if d["type"] == "garage":
        return garage_text(d)
    if d["type"] == "tv":
        if not s.get("on"):
            return tr("Off")
        return tr("On – {input}").format(input=s["input_name"]) if s.get("input_name") else tr("On")
    if d.get("meta", {}).get("choice"):         # switch group: the switch that is on
        return s.get("active_name") or tr("Off")
    if d["type"] == "security":
        return security_text(d)
    if d["type"] == "sensor":
        return ", ".join(sensor_parts(s)) or tr("No reading")
    if d["type"] == "blind":
        if s.get("obstructed"):
            return tr("Obstructed")
        if s.get("moving") == "opening":
            return tr("Opening … {pct}").format(pct=pct(s.get("position", 0)))
        if s.get("moving") == "closing":
            return tr("Closing … {pct}").format(pct=pct(s.get("position", 0)))
        pos = s.get("position", 0)
        if pos >= 100:
            return tr("Open")
        if pos <= 0:
            return tr("Closed")
        return tr("{pct} open").format(pct=pct(pos))
    if d["type"] == "thermostat":
        temp = fmt_temp(s.get("current_temp"))
        if s.get("mode") == "off":
            return tr("Off, {temp} °C").format(temp=temp)
        if s.get("heating"):
            return tr("Heating, now {temp} °C").format(temp=temp)
        return tr("Now {temp} °C").format(temp=temp)
    if not s.get("on"):
        return tr("Off")
    if d.get("meta", {}).get("group"):
        text = tr("{on} of {n} on").format(on=s.get("on_count", 0), n=s.get("count", 0))
        return f"{text}, {pct(s['brightness'])}" if s.get("brightness") is not None else text
    if s.get("brightness") is not None:
        return pct(s["brightness"])
    if s.get("speed") is not None:
        return tr("Speed {pct}").format(pct=pct(s["speed"]))
    if d.get("meta", {}).get("appliance") in ("washer", "dishwasher") and "in_use" in s:   # plug measures power
        return tr("Running") if s.get("in_use") else tr("Ready")
    if d["type"] == "plug" and s.get("in_use"):
        return tr("On, in use")
    return tr("On")


def has_detail(d: dict[str, Any]) -> bool:
    caps = d.get("capabilities", [])
    if d.get("meta", {}).get("choice") or d["type"] == "alarm":
        return True
    if d["type"] == "valve":
        return "duration" in caps
    if d["type"] == "tv":
        return any(c in caps for c in ("input", "volume", "mute", "remote"))
    return d["type"] in ("thermostat", "sensor", "blind") or any(
        c in caps for c in ("brightness", "color", "color_temp", "speed"))
