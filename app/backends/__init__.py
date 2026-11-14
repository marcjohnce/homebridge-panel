from __future__ import annotations

from ..config import AppConfig
from .base import Backend, BackendError
from .demo import DemoBackend
from .hap import HapBackend
from .homebridge_ui import HomebridgeUiBackend
from .mqtt import MqttBackend

__all__ = ["Backend", "BackendError", "DemoBackend", "HapBackend", "HomebridgeUiBackend", "MqttBackend",
           "create_backends"]


def create_backends(cfg: AppConfig) -> list[Backend]:
    backends: list[Backend] = []
    backends += [HapBackend(c) for c in cfg.hap]
    backends += [HomebridgeUiBackend(c) for c in cfg.homebridge_ui]
    if cfg.demo.enabled:
        backends.append(DemoBackend(cfg.demo.name))
    if cfg.mqtt is not None:
        backends.append(MqttBackend(cfg.mqtt, cfg.virtual))
    names = [b.name for b in backends]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"Backend names must be unique, duplicates: {sorted(dupes)}")
    return backends
