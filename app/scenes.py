"""Scenes set up on the panel (menu entry "Scenes").

A scene belongs to a room and holds, for some of the room's lights, switches, plugs and blinds,
the state to switch them to. It is made from the state the devices have when it is saved; devices
left out are not changed when the scene runs. Stored in settings.json (so they are part of every
backup and of the settings shared over MQTT):

    "scenes": [{"id": "s1a2b3", "name": "Ice age", "room": "Living Room",
                "devices": {"hap:12.10": {"on": true, "brightness": 70, "color_temp": 370},
                            "hap:14.10": {"on": false},
                            "hap:20.9": {"position": 60}}}]

Scenes in config.yaml are separate and stay as they are.
"""
from __future__ import annotations

import secrets
from typing import Any

SCENE_TYPES = ("light", "switch", "plug", "blind")
MAX_SCENE_NAME = 24


def in_scenes(d: dict[str, Any]) -> bool:
    """Lights, switches, plugs and blinds – not groups, motorized windows or doors, panel tiles."""
    meta = d.get("meta", {})
    return (d.get("type") in SCENE_TYPES and not meta.get("group") and not meta.get("choice")
            and not meta.get("opening") and not d.get("panelTile"))


def capture(d: dict[str, Any]) -> dict[str, Any]:
    """The state of a device as the commands that bring it back."""
    s, caps = d.get("state", {}), d.get("capabilities", [])
    if d.get("type") == "blind":
        out: dict[str, Any] = {"position": int(s.get("target", s.get("position", 0)) or 0)}
        if "tilt" in caps and s.get("tilt") is not None:
            out["tilt"] = int(s["tilt"])
        return out
    if not s.get("on"):
        return {"on": False}
    out = {"on": True}
    if "brightness" in caps and s.get("brightness") is not None:
        out["brightness"] = int(s["brightness"])
    # HomeKit lights report hue/saturation and white tone together: a pale colour means white
    coloured = "color" in caps and s.get("hue") is not None and (s.get("saturation") or 0) >= 10
    if coloured or ("color" in caps and s.get("hue") is not None and "color_temp" not in caps):
        out.update(hue=round(s["hue"]), saturation=round(s.get("saturation") or 0))
    elif "color_temp" in caps and s.get("color_temp") is not None:
        out["color_temp"] = int(s["color_temp"])
    return out


def as_state(d: dict[str, Any], attrs: dict[str, Any]) -> dict[str, Any]:
    """The device as it would be with these commands (for its state text: "On", not what the
    plug measures right now)."""
    state = {k: v for k, v in attrs.items() if k != "position"}
    if "position" in attrs:
        state.update(position=attrs["position"], target=attrs["position"], moving="stopped",
                     on=attrs["position"] > 0)
    return {**d, "state": state, "reachable": True}


def new_id(taken: set[str]) -> str:
    while True:
        sid = "s" + secrets.token_hex(3)
        if sid not in taken:
            return sid


def clean(scenes: Any) -> list[dict[str, Any]]:
    """Valid scenes of settings.json (anything else is dropped)."""
    out = []
    for sc in scenes if isinstance(scenes, list) else []:
        if not (isinstance(sc, dict) and isinstance(sc.get("id"), str) and isinstance(sc.get("name"), str)
                and isinstance(sc.get("room"), str) and isinstance(sc.get("devices"), dict)):
            continue
        devices = {str(k): v for k, v in sc["devices"].items() if isinstance(v, dict)}
        out.append({"id": sc["id"], "name": sc["name"], "room": sc["room"], "devices": devices})
    return out
