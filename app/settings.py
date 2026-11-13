"""Settings that are edited directly on the panel.

Adding a setting:
  1. Add a `Field(...)` to FIELDS (section, kind, default, limits).
  2. If it affects the device configuration, evaluate it in `apply_to_config()`;
     otherwise expose it as a property of the Qt controller.
The settings page builds itself from this schema.
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
    instant: bool          # True: saved immediately; False: saved with "Apply"


@dataclass(frozen=True)
class Field:
    key: str
    section: str
    label: str
    kind: str              # choice | toggle | number | host | pin | action
    default: Any
    help: str = ""
    options: tuple[tuple[Any, str], ...] = field(default_factory=tuple)
    min: int | None = None
    max: int | None = None
    button: str = ""       # action: button text
    confirm: str = ""      # action: question in the confirmation dialog (empty = no dialog)


SECTIONS = [
    Section("display", "Display", instant=True),
    Section("homebridge", "Homebridge", instant=False),
    Section("system", "System", instant=True),
]

FIELDS = [
    Field("theme", "display", "Appearance", "choice", "auto",
          help="Automatic: dark from 7 pm to 7 am",
          options=(("auto", "Automatic"), ("light", "Light"), ("dark", "Dark"))),
    Field("idle_seconds", "display", "Screen saver after", "choice", 120,
          options=((0, "Never"), (60, "1 min"), (120, "2 min"), (300, "5 min"), (900, "15 min"))),
    Field("hap_enabled", "homebridge", "Connect to Homebridge", "toggle", True),
    Field("hap_host", "homebridge", "Address", "host", "127.0.0.1",
          help="IP address or name of the computer running Homebridge"),
    Field("hap_port", "homebridge", "Port", "number", 51826, min=1, max=65535,
          help="Found in the Homebridge config under \"bridge\" → \"port\""),
    Field("hap_pin", "homebridge", "PIN", "pin", "031-45-154",
          help="Format 123-45-678, found under \"bridge\" → \"pin\""),
    # Actions are buttons, not stored values. The controller runs them (Controller.run_action).
    Field("restart_app", "system", "Restart app", "action", None,
          help="Reloads the panel and reconnects to Homebridge",
          button="Restart", confirm="Restart the panel app now?"),
    Field("reboot", "system", "Restart Raspberry Pi", "action", None,
          help="Reboots the whole device; the panel is back after about a minute",
          button="Restart", confirm="Restart the Raspberry Pi now? The panel is unavailable for about a minute."),
]
ACTIONS = {f.key for f in FIELDS if f.kind == "action"}
FIELDS_BY_KEY = {f.key: f for f in FIELDS}

_HOST_RE = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def validate(key: str, value: Any) -> tuple[Any, str | None]:
    """Checks and normalizes a value. Returns (value, error message or None)."""
    f = FIELDS_BY_KEY.get(key)
    if isinstance(value, float) and value.is_integer():   # numbers from QML arrive as float
        value = int(value)
    if f is None:
        return value, f"Unknown setting \"{key}\""
    if f.kind == "action":
        return value, f"\"{key}\" is an action, not a setting"
    if f.kind == "choice":
        for opt, _ in f.options:
            if str(opt) == str(value):
                return opt, None
        return value, "Choose one of the offered options"
    if f.kind == "toggle":
        if isinstance(value, bool):
            return value, None
        return value, "Expected on or off"
    if f.kind == "number":
        try:
            n = int(str(value).strip())
        except ValueError:
            return value, "Enter a whole number"
        if (f.min is not None and n < f.min) or (f.max is not None and n > f.max):
            return n, f"Allowed range is {f.min} to {f.max}"
        return n, None
    if f.kind == "host":
        v = str(value).strip()
        if not v:
            return v, "Enter an address"
        if _IPV4_RE.match(v):
            if any(int(p) > 255 for p in v.split(".")):
                return v, "Invalid IP address: each number can be at most 255"
            return v, None
        if not _HOST_RE.match(v) or v.replace(".", "").isdigit():
            return v, "Invalid address, e.g. 192.168.1.20 or homebridge.local"
        return v, None
    if f.kind == "pin":
        digits = re.sub(r"\D", "", str(value))
        if len(digits) != 8:
            return value, "The PIN has 8 digits, format 123-45-678"
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
        self.values: dict[str, Any] = {f.key: f.default for f in FIELDS if f.kind != "action"}
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
        """Applies changes if all are valid. Returns errors per key."""
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
        """Sections with fields and current values – for the settings page."""
        out = []
        for s in SECTIONS:
            fields = [{
                "key": f.key, "label": f.label, "kind": f.kind, "help": f.help,
                "options": [{"value": v, "label": l} for v, l in f.options],
                "min": f.min, "max": f.max, "value": self.values.get(f.key),
                "button": f.button, "confirm": f.confirm,
            } for f in FIELDS if f.section == s.id]
            out.append({"id": s.id, "title": s.title, "instant": s.instant, "fields": fields})
        return out


def apply_to_config(cfg: AppConfig, values: dict[str, Any]) -> AppConfig:
    """Builds the effective configuration: the panel settings define the bridge "homebridge".

    Further bridges from config.yaml (e.g. child bridges) are kept; an entry there
    named "homebridge" is replaced by the panel setting.
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
