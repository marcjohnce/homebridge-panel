"""Opening log of windows, doors and contacts, garage doors and motorized windows/doors: the
panel notes when each one opens and closes (only while it runs) in openings.json next to
settings.json, for the last 30 days:

    {"hap:12.10": [[1764000000.0, 1764000600.0], [1764090000.0, null]]}   # open, closed (null: still open)
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
KEEP_DAYS = 30
MAX_ENTRIES = 300          # per device


def loggable(d: dict[str, Any]) -> bool:
    meta = d.get("meta", {})
    return ((d.get("type") == "security" and meta.get("security") in ("window", "door", "contact"))
            or d.get("type") == "garage" or (d.get("type") == "blind" and bool(meta.get("opening"))))


def is_open(d: dict[str, Any]) -> bool:
    s = d.get("state", {})
    if d.get("type") == "blind":
        return (s.get("position") or 0) > 0
    return bool(s.get("triggered"))


class OpeningLog:
    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[str, list[list[float | None]]] = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.entries = {str(k): [list(e) for e in v if isinstance(e, list) and len(e) == 2]
                                for k, v in data.items() if isinstance(v, list)}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def note(self, dev_id: str, opened: bool, now: float | None = None) -> bool:
        """Notes the state of a device; True if that started or ended an opening (and was saved)."""
        now = now or time.time()
        events = self.entries.get(dev_id, [])
        last_open = bool(events) and events[-1][1] is None
        if opened == last_open:
            return False
        if opened:
            events.append([now, None])
        else:
            events[-1][1] = now
        cutoff = now - KEEP_DAYS * 86400
        self.entries[dev_id] = [e for e in events if (e[1] or now) >= cutoff][-MAX_ENTRIES:]
        self._save()
        return True

    def events(self, dev_id: str) -> list[list[float | None]]:
        """Openings of a device, newest first: [opened, closed or None]."""
        return list(reversed(self.entries.get(dev_id, [])))

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".openings-")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.entries, fh)
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("Opening log not saved: %s", e)
