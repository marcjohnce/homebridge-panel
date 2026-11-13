"""Einstellungen, die direkt im Panel bearbeitet werden.

Neue Einstellung hinzufügen:
  1. Einen `Field(...)` in FIELDS eintragen (Abschnitt, Art, Standardwert, Prüfung).
  2. Falls sie die Gerätekonfiguration betrifft, in `apply_to_config()` auswerten,
     sonst im Qt-Controller als Eigenschaft bereitstellen.
Die Einstellungsseite baut sich aus diesem Schema automatisch auf.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AppConfig, HapBackendConfig


PRIMARY_BRIDGE = "homebridge"


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    instant: bool          # True: Änderung wird sofort gespeichert; False: erst mit "Übernehmen"


@dataclass(frozen=True)
class Field:
    key: str
    section: str
    label: str
    kind: str              # choice | toggle | number | host | pin
    default: Any
    help: str = ""
    options: tuple[tuple[Any, str], ...] = field(default_factory=tuple)
    min: int | None = None
    max: int | None = None


SECTIONS = [
    Section("display", "Anzeige", instant=True),
    Section("homebridge", "Homebridge", instant=False),
]

FIELDS = [
    Field("theme", "display", "Darstellung", "choice", "auto",
          help="Automatisch: dunkel von 19 bis 7 Uhr",
          options=(("auto", "Automatisch"), ("light", "Hell"), ("dark", "Dunkel"))),
    Field("idle_seconds", "display", "Ruhebildschirm nach", "choice", 120,
          options=((0, "Nie"), (60, "1 Min."), (120, "2 Min."), (300, "5 Min."), (900, "15 Min."))),
    Field("hap_enabled", "homebridge", "Mit Homebridge verbinden", "toggle", True),
    Field("hap_host", "homebridge", "Adresse", "host", "127.0.0.1",
          help="IP-Adresse oder Name des Rechners, auf dem Homebridge läuft"),
    Field("hap_port", "homebridge", "Port", "number", 51826, min=1, max=65535,
          help="Steht in der Homebridge-Konfiguration unter „bridge“ → „port“"),
    Field("hap_pin", "homebridge", "PIN", "pin", "031-45-154",
          help="Format 123-45-678, steht unter „bridge“ → „pin“"),
]
FIELDS_BY_KEY = {f.key: f for f in FIELDS}

_HOST_RE = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def validate(key: str, value: Any) -> tuple[Any, str | None]:
    """Prüft und normalisiert einen Wert. Rückgabe: (Wert, Fehlermeldung oder None)."""
    f = FIELDS_BY_KEY.get(key)
    if isinstance(value, float) and value.is_integer():   # Zahlen aus QML kommen als float
        value = int(value)
    if f is None:
        return value, f"Unbekannte Einstellung „{key}“"
    if f.kind == "choice":
        for opt, _ in f.options:
            if str(opt) == str(value):
                return opt, None
        return value, "Bitte eine der angebotenen Möglichkeiten wählen"
    if f.kind == "toggle":
        if isinstance(value, bool):
            return value, None
        return value, "Ein oder Aus erwartet"
    if f.kind == "number":
        try:
            n = int(str(value).strip())
        except ValueError:
            return value, "Bitte eine ganze Zahl eingeben"
        if (f.min is not None and n < f.min) or (f.max is not None and n > f.max):
            return n, f"Erlaubt sind {f.min} bis {f.max}"
        return n, None
    if f.kind == "host":
        v = str(value).strip()
        if not v:
            return v, "Bitte eine Adresse eingeben"
        if _IPV4_RE.match(v):
            if any(int(p) > 255 for p in v.split(".")):
                return v, "Ungültige IP-Adresse: jede Zahl darf höchstens 255 sein"
            return v, None
        if not _HOST_RE.match(v) or v.replace(".", "").isdigit():
            return v, "Ungültige Adresse, z. B. 192.168.1.20 oder homebridge.local"
        return v, None
    if f.kind == "pin":
        digits = re.sub(r"\D", "", str(value))
        if len(digits) != 8:
            return value, "Die PIN hat 8 Ziffern, Format 123-45-678"
        return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}", None
    return value, None


def default_path() -> Path:
    if env := os.environ.get("SMARTHOME_SETTINGS"):
        return Path(env)
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "smarthome-panel" / "settings.json"


class SettingsStore:
    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path) if path else default_path()
        self.values: dict[str, Any] = {f.key: f.default for f in FIELDS}
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        for key, value in data.items():
            if key in FIELDS_BY_KEY:
                v, err = validate(key, value)
                if err is None:
                    self.values[key] = v

    def get(self, key: str) -> Any:
        return self.values[key]

    def update(self, changes: dict[str, Any]) -> dict[str, str]:
        """Übernimmt Änderungen, wenn alle gültig sind. Rückgabe: Fehler je Schlüssel."""
        clean, errors = {}, {}
        for key, value in changes.items():
            v, err = validate(key, value)
            if err:
                errors[key] = err
            else:
                clean[key] = v
        if errors:
            return errors
        self.values.update(clean)
        self.save()
        return {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".settings-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self.values, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def schema(self) -> list[dict[str, Any]]:
        """Abschnitte mit Feldern und aktuellen Werten – für die Einstellungsseite."""
        out = []
        for s in SECTIONS:
            fields = [{
                "key": f.key, "label": f.label, "kind": f.kind, "help": f.help,
                "options": [{"value": v, "label": l} for v, l in f.options],
                "min": f.min, "max": f.max, "value": self.values[f.key],
            } for f in FIELDS if f.section == s.id]
            out.append({"id": s.id, "title": s.title, "instant": s.instant, "fields": fields})
        return out


def apply_to_config(cfg: AppConfig, values: dict[str, Any]) -> AppConfig:
    """Erzeugt die wirksame Konfiguration: Die Panel-Einstellungen bilden die Bridge „homebridge“.

    Weitere Bridges aus config.yaml (z. B. Child-Bridges) bleiben erhalten; ein dortiger
    Eintrag mit dem Namen „homebridge“ wird durch die Panel-Einstellung ersetzt.
    """
    eff = cfg.model_copy(deep=True)
    others = [h for h in eff.hap if h.name != PRIMARY_BRIDGE]
    if values.get("hap_enabled", True):
        primary = HapBackendConfig(name=PRIMARY_BRIDGE, host=values["hap_host"],
                                   port=values["hap_port"], pin=values["hap_pin"])
        eff.hap = [primary, *others]
    else:
        eff.hap = others
    return eff
