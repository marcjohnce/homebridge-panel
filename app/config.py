"""Configuration (YAML) validated with Pydantic."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

WEEKDAYS = ["mo", "tu", "we", "th", "fr", "sa", "su"]
# German abbreviations are accepted as aliases
WEEKDAY_ALIASES = {"di": "tu", "mi": "we", "do": "th", "so": "su"}


class ServerConfig(BaseModel):
    poll_interval: float = Field(5.0, ge=1.0, description="Polling interval in seconds")
    timezone: str = "Europe/Berlin"


class PanelConfig(BaseModel):
    title: str = "Smart Home"
    default_room: str = "General"
    show_cooling: bool = Field(False, description="Show the 'Cool' mode on thermostats")


class HapBackendConfig(BaseModel):
    """Direct HAP access to a Homebridge bridge (or child bridge) running in insecure mode."""
    name: str = "homebridge"
    host: str = "127.0.0.1"
    port: int = 51826
    pin: str = "031-45-154"
    timeout: float = 5.0


class HomebridgeUiBackendConfig(BaseModel):
    """Access via the REST API of homebridge-config-ui-x."""
    name: str = "homebridge-ui"
    url: str = "http://127.0.0.1:8581"
    username: str | None = None
    password: str | None = None
    otp: str | None = None
    verify_ssl: bool = True
    timeout: float = 8.0


class DemoBackendConfig(BaseModel):
    enabled: bool = False
    name: str = "demo"


class DeviceOverride(BaseModel):
    name: str | None = None
    room: str | None = None
    icon: str | None = None
    hidden: bool = False
    order: int = 100


class SceneAction(BaseModel):
    device: str = Field(..., description="Device ID or device name")
    set: dict[str, Any]

    @field_validator("set", mode="before")
    @classmethod
    def _fix_yaml_on(cls, v: Any) -> Any:
        # YAML 1.1 reads the key `on:` as boolean True -> map it back to "on"
        if isinstance(v, dict):
            return {("on" if k is True else "off" if k is False else k): val for k, val in v.items()}
        return v


class Scene(BaseModel):
    id: str
    name: str
    icon: str = "power"
    actions: list[SceneAction] = []


class Schedule(BaseModel):
    time: str
    scene: str
    days: list[str] = Field(default_factory=lambda: list(WEEKDAYS))
    enabled: bool = True

    @field_validator("time")
    @classmethod
    def _check_time(cls, v: str) -> str:
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("Time must be given as HH:MM")
        return v

    @field_validator("days")
    @classmethod
    def _check_days(cls, v: list[str]) -> list[str]:
        v = [d.lower()[:2] for d in v]
        v = [WEEKDAY_ALIASES.get(d, d) for d in v]
        bad = [d for d in v if d not in WEEKDAYS]
        if bad:
            raise ValueError(f"Unknown weekdays: {bad} (allowed: {WEEKDAYS})")
        return v


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    panel: PanelConfig = PanelConfig()
    hap: list[HapBackendConfig] = []
    homebridge_ui: list[HomebridgeUiBackendConfig] = []
    demo: DemoBackendConfig = DemoBackendConfig()
    devices: dict[str, DeviceOverride] = {}
    scenes: list[Scene] = []
    schedules: list[Schedule] = []


def _expand_env(obj: Any) -> Any:
    """Replaces ${VAR} in strings with environment variables (e.g. for passwords)."""
    if isinstance(obj, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), obj)
    if isinstance(obj, list):
        return [_expand_env(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    return obj


def config_path(path: str | os.PathLike | None = None) -> Path:
    return Path(path or os.environ.get("SMARTHOME_CONFIG", "config.yaml"))


def load_config(path: str | os.PathLike | None = None, required: bool = True) -> AppConfig:
    """Loads config.yaml (rooms, scenes, schedules). Without a file: empty config unless required."""
    path = config_path(path)
    if not path.exists():
        if not required:
            return AppConfig()
        raise FileNotFoundError(
            f"Configuration '{path}' not found – copy config.example.yaml to config.yaml"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(_expand_env(data))
