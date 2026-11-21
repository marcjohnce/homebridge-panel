"""Configuration (YAML) validated with Pydantic."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

log = logging.getLogger(__name__)


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


class MqttConfig(BaseModel):
    """MQTT broker for virtual devices (values of subscribed topics)."""
    name: str = "mqtt"
    host: str = "127.0.0.1"
    port: int = 1883
    protocol: Literal["tcp", "tls", "websocket"] = "tcp"
    username: str | None = None
    password: str | None = None
    timeout: float = 5.0


class VirtualDevice(BaseModel):
    """A value received over MQTT, shown like a sensor, e.g. the water pressure of a boiler."""
    id: str
    name: str
    topic: str
    unit: str = ""
    json_key: str = Field("", description="Key (a.b for nested) when the payload is JSON")
    decimals: int = Field(1, ge=0, le=3)
    icon: str = Field("gauge", description='Icon of the tile; "none" shows the value without an icon')


class DemoBackendConfig(BaseModel):
    enabled: bool = False
    name: str = "demo"


class DeviceOverride(BaseModel):
    name: str | None = None
    room: str | None = None
    icon: str | None = None
    hidden: bool = False
    order: int = 100
    outdoor: bool = Field(False, description="Outdoor sensor: shown as outdoor temperature, not indoors")
    security: Literal["window", "door", "contact", "glassbreak", "leak", "motion", "presence", "smoke", "co"] | None = Field(
        None, description="Kind of a contact or motion sensor (e.g. glassbreak)")
    valve: Literal["generic", "irrigation", "shower", "faucet"] | None = Field(
        None, description="Kind of a valve (icon; generic valves appear under Security)")
    # "tv" is still accepted from older configurations and treated as a plain switch
    appliance: Literal["switch", "plug", "tv", "coffee", "washer", "dishwasher", "fan"] | None = Field(
        None, description="What a switch or plug powers (icon, washer/dishwasher state, fan under Climate)")
    lamp: Literal["bulb", "ceiling", "pendant", "chandelier", "spot", "wall", "table", "desk", "floorlamp", "globe",
                  "tube", "strip"] | None = Field(
        None, description="Kind of lamp of a light (icon)")
    area: Literal["light", "climate", "security"] | None = Field(
        None, description="Menu area to show the device in, instead of the one of its type")


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
    room: str | None = Field(None, description="Room the scene is offered in; none = whole house")
    actions: list[SceneAction] = []


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    panel: PanelConfig = PanelConfig()
    hap: list[HapBackendConfig] = []
    homebridge_ui: list[HomebridgeUiBackendConfig] = []
    demo: DemoBackendConfig = DemoBackendConfig()
    mqtt: MqttConfig | None = None
    virtual: list[VirtualDevice] = []
    devices: dict[str, DeviceOverride] = {}
    blacklist: list[str] = Field(
        [], description="Devices whose original name contains one of these texts are ignored completely "
                        "(case doesn't matter)")
    scenes: list[Scene] = []

    @field_validator("blacklist", mode="before")
    @classmethod
    def _blacklist_list(cls, v: Any) -> Any:
        # a single text or an empty `blacklist:` are accepted; numbers become texts
        if v is None:
            return []
        if isinstance(v, (str, int, float)):
            v = [v]
        return [str(x) for x in v if x is not None] if isinstance(v, list) else v

    def blacklisted(self, name: str) -> bool:
        """True if the original device name contains a text of the blacklist (empty entries are ignored)."""
        name = name.casefold()
        return any(b in name for b in self._blacklist_texts)

    @property
    def _blacklist_texts(self) -> list[str]:
        return [b.casefold() for b in self.blacklist if b.strip()]


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
    """Loads config.yaml (rooms, scenes). Without a file: empty config unless required."""
    path = config_path(path)
    if not path.exists():
        if not required:
            return AppConfig()
        raise FileNotFoundError(
            f"Configuration '{path}' not found – copy config.example.yaml to config.yaml"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(data, dict) and data.pop("schedules", None):
        log.warning("%s: schedules are no longer supported and are ignored", path)
    return AppConfig.model_validate(_expand_env(data))
