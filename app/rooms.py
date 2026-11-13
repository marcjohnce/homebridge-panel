"""Rooms and devices edited on the panel: room order, room of each device, display names
and the kind of security sensors (window, door, glass break …).

A device's room comes from config.yaml (`devices: <id>: room:`) or the default room.
The panel can override it; overrides and the room order are stored in settings.json:

    "rooms": {"order": ["Living Room", "Kitchen"], "devices": {"hap:...": "Kitchen"},
              "names": {"hap:...": "Coffee"}, "kinds": {"hap:...": "window"}}

Rooms without devices are kept in "order" so they can be prepared before devices are
assigned. On the home screen only rooms with devices appear.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from .i18n import tr

MAX_NAME = 24
MAX_DEVICE_NAME = 40
BUILTIN_DEFAULT = "General"


class RoomLayout:
    def __init__(self, data: dict[str, Any] | None = None,
                 default_room: Callable[[], str] = lambda: BUILTIN_DEFAULT):
        data = data or {}
        self.order: list[str] = [str(r) for r in data.get("order", []) if isinstance(r, str) and r.strip()]
        devs = data.get("devices", {})
        self.assign: dict[str, str] = ({str(k): str(v) for k, v in devs.items() if isinstance(v, str) and v.strip()}
                                       if isinstance(devs, dict) else {})
        self.names = self._strings(data.get("names"))
        self.kinds = self._strings(data.get("kinds"))
        self._default = default_room

    @staticmethod
    def _strings(d: Any) -> dict[str, str]:
        return {str(k): str(v) for k, v in d.items() if isinstance(v, str) and v.strip()} if isinstance(d, dict) else {}

    # ---------- reading ----------
    def to_dict(self) -> dict[str, Any]:
        return {"order": list(self.order), "devices": dict(self.assign),
                "names": dict(self.names), "kinds": dict(self.kinds)}

    @property
    def default_room(self) -> str:
        return self._default()

    def base_name(self, base: str) -> str:
        """Room from config.yaml; the built-in default room is shown in the panel language."""
        return self.default_room if base == BUILTIN_DEFAULT else base

    def room_of(self, dev_id: str, base: str) -> str:
        return self.assign.get(dev_id) or self.base_name(base)

    def sort(self, names: Iterable[str]) -> list[str]:
        """Rooms in the stored order; rooms not ordered yet follow alphabetically."""
        names = set(names)
        known = [r for r in self.order if r in names]
        return known + sorted(names - set(known), key=str.casefold)

    def all_rooms(self, device_rooms: Iterable[str]) -> list[str]:
        return self.sort({*self.order, *device_rooms})

    # ---------- changes (device_rooms: {device id: current room}) ----------
    def _check(self, name: str, existing: Iterable[str], allow: str | None = None) -> tuple[str, str | None]:
        name = " ".join(str(name).split())
        if not name:
            return name, tr("Enter a name")
        if len(name) > MAX_NAME:
            return name, tr("At most {n} characters").format(n=MAX_NAME)
        if any(r.casefold() == name.casefold() and r != allow for r in existing):
            return name, tr("A room named \"{name}\" already exists").format(name=name)
        return name, None

    def add(self, name: str, device_rooms: dict[str, str]) -> tuple[str, str | None]:
        rooms = self.all_rooms(device_rooms.values())
        name, err = self._check(name, rooms)
        if err:
            return name, err
        self.order = [*rooms, name]
        return name, None

    def rename(self, old: str, new: str, device_rooms: dict[str, str]) -> tuple[str, str | None]:
        rooms = self.all_rooms(device_rooms.values())
        if old not in rooms:
            return new, tr("Room not found")
        new, err = self._check(new, rooms, allow=old)
        if err or new == old:
            return new, err
        self.order = [new if r == old else r for r in rooms]
        for dev_id, room in device_rooms.items():
            if room == old:
                self.assign[dev_id] = new
        return new, None

    def delete(self, name: str, device_rooms: dict[str, str], base_rooms: dict[str, str]) -> str | None:
        """Devices of a deleted room move to the default room."""
        rooms = self.all_rooms(device_rooms.values())
        if name not in rooms:
            return tr("Room not found")
        members = [d for d, r in device_rooms.items() if r == name]
        if name == self.default_room and members:
            return tr("Devices without a room are collected in \"{name}\". Move them to other rooms first.") \
                .format(name=name)
        self.order = [r for r in rooms if r != name]
        for dev_id in members:
            self._set(dev_id, self.default_room, base_rooms.get(dev_id, BUILTIN_DEFAULT))
        return None

    def move(self, name: str, delta: int, device_rooms: dict[str, str]) -> None:
        rooms = self.all_rooms(device_rooms.values())
        if name not in rooms:
            return
        i = rooms.index(name)
        j = max(0, min(len(rooms) - 1, i + delta))
        rooms.insert(j, rooms.pop(i))
        self.order = rooms

    def set_room(self, dev_id: str, room: str, base: str, device_rooms: dict[str, str]) -> str | None:
        rooms = self.all_rooms(device_rooms.values())
        if room not in rooms:
            return tr("Room not found")
        if room not in self.order:
            self.order = rooms
        self._set(dev_id, room, base)
        return None

    def check_device_name(self, name: str) -> tuple[str, str | None]:
        name = " ".join(str(name).split())
        if len(name) > MAX_DEVICE_NAME:
            return name, tr("At most {n} characters").format(n=MAX_DEVICE_NAME)
        return name, None

    def set_name(self, dev_id: str, name: str, base: str) -> None:
        """Empty or the original name: back to the name from Homebridge / config.yaml."""
        if not name or name == base:
            self.names.pop(dev_id, None)
        else:
            self.names[dev_id] = name

    def set_kind(self, dev_id: str, kind: str, base: str) -> None:
        if not kind or kind == base:
            self.kinds.pop(dev_id, None)
        else:
            self.kinds[dev_id] = kind

    def _set(self, dev_id: str, room: str, base: str) -> None:
        if room == self.base_name(base):
            self.assign.pop(dev_id, None)      # back to the room from config.yaml
        else:
            self.assign[dev_id] = room
