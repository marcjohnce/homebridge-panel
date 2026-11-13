"""Anzeigetexte für Kacheln (deutsch, ohne Qt-Abhängigkeit – dadurch testbar)."""
from __future__ import annotations

import re
from typing import Any


def fmt_temp(v: Any) -> str:
    if v is None:
        return "–"
    return f"{float(v):.1f}".replace(".", ",")


def short_name(name: str, room: str) -> str:
    """Auf Kacheln steht der Raum schon dabei: „Heizung Wohnzimmer“ → „Heizung“."""
    room = (room or "").strip()
    if not room or name.casefold() == room.casefold():
        return name
    short = re.sub(rf"(^|\s|-){re.escape(room)}(?=$|\s|-)", " ", name, count=1, flags=re.IGNORECASE)
    short = re.sub(r"\s+(im|in|in der|der|des|vom)\s*$", "", short, flags=re.IGNORECASE)
    short = re.sub(r"\s{2,}", " ", short).strip(" -")
    return short or name


def state_text(d: dict[str, Any]) -> str:
    if not d.get("reachable", True):
        return "Nicht erreichbar"
    s = d.get("state", {})
    if d["type"] == "thermostat":
        if s.get("mode") == "off":
            return f"Aus, {fmt_temp(s.get('current_temp'))} °C"
        prefix = "Heizt, ist" if s.get("heating") else "Ist"
        return f"{prefix} {fmt_temp(s.get('current_temp'))} °C"
    if not s.get("on"):
        return "Aus"
    if s.get("brightness") is not None:
        return f"{s['brightness']} %"
    if s.get("speed") is not None:
        return f"Stufe {round(s['speed'])} %"
    if d["type"] == "plug" and s.get("in_use"):
        return "An, in Betrieb"
    return "An"


def has_detail(d: dict[str, Any]) -> bool:
    caps = d.get("capabilities", [])
    return d["type"] == "thermostat" or any(c in caps for c in ("brightness", "color", "color_temp", "speed"))
