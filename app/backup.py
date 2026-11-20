"""Backups of the panel settings (Settings → System → Backups).

A backup is a copy of settings.json – display, connection, alarm PIN, rooms, names, favorites,
light and switch groups and virtual devices – in the folder "backups" next to it, wrapped with
the time and app version:

    {"smarthome_panel_backup": 1, "created": "2026-11-20T18:10:00+01:00", "version": "0.0.4",
     "settings": {… settings.json …}}

Restoring writes the settings back; the app then restarts to load them. config.yaml and the
temperature history are not part of a backup.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

FORMAT = 1
_NAME_RE = re.compile(r"^backup-\d{8}-\d{6}(-\d+)?\.json$")


class BackupError(Exception):
    pass


class Backups:
    def __init__(self, settings_path: Path, version: str = "", folder: Path | None = None):
        self.settings_path = Path(settings_path)
        self.folder = Path(folder) if folder else self.settings_path.parent / "backups"
        self.version = version

    # ---------- helpers ----------
    def _path(self, name: str) -> Path:
        if not _NAME_RE.match(name):                 # only our own files, no paths
            raise BackupError(f"unknown backup {name!r}")
        return self.folder / name

    @staticmethod
    def _write(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".backup-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    def _read(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise BackupError(f"backup not readable: {e}") from e
        if not (isinstance(data, dict) and data.get("smarthome_panel_backup") == FORMAT
                and isinstance(data.get("settings"), dict)):
            raise BackupError("not a backup of the panel settings")
        return data

    @staticmethod
    def summary(settings: dict[str, Any]) -> dict[str, int]:
        rooms = settings.get("rooms") if isinstance(settings.get("rooms"), dict) else {}
        assigned = rooms.get("devices") if isinstance(rooms.get("devices"), dict) else {}
        order = rooms.get("order") if isinstance(rooms.get("order"), list) else []

        def count(value: Any) -> int:
            return len(value) if isinstance(value, (list, dict)) else 0
        return {"rooms": len(set(order) | set(assigned.values())),
                "favorites": count(rooms.get("favorites")),
                "groups": count(settings.get("groups")) + count(settings.get("switch_groups")),
                "virtual": count(settings.get("virtual")),
                "names": count(rooms.get("names"))}

    # ---------- actions ----------
    def create(self) -> str:
        """Copies the current settings.json; returns the name of the backup."""
        try:
            settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            settings = {}
        except (OSError, ValueError) as e:
            raise BackupError(f"settings not readable: {e}") from e
        now = datetime.now().astimezone()
        name = f"backup-{now:%Y%m%d-%H%M%S}.json"
        n = 1
        while (self.folder / name).exists():          # two backups within one second
            n += 1
            name = f"backup-{now:%Y%m%d-%H%M%S}-{n}.json"
        try:
            self._write(self.folder / name, {"smarthome_panel_backup": FORMAT, "created": now.isoformat(),
                                             "version": self.version, "settings": settings})
        except OSError as e:
            raise BackupError(str(e)) from e
        return name

    def list(self) -> list[dict[str, Any]]:
        """Backups, newest first: name, created (ISO), version and what they contain."""
        out = []
        try:
            files = [p for p in self.folder.iterdir() if _NAME_RE.match(p.name)]
        except OSError:
            return []
        for p in files:
            try:
                data = self._read(p)
            except BackupError:
                continue
            out.append({"name": p.name, "created": str(data.get("created", "")),
                        "version": str(data.get("version", "")), **self.summary(data["settings"])})
        return sorted(out, key=lambda b: (b["created"], len(b["name"])), reverse=True)

    def restore(self, name: str) -> None:
        """Writes the settings of a backup back to settings.json (the app has to restart)."""
        data = self._read(self._path(name))
        try:
            self._write(self.settings_path, data["settings"])
        except OSError as e:
            raise BackupError(str(e)) from e

    def delete(self, name: str) -> None:
        try:
            self._path(name).unlink()
        except FileNotFoundError:
            pass
        except OSError as e:
            raise BackupError(str(e)) from e
