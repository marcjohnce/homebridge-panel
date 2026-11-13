from __future__ import annotations

from ..config import AppConfig
from .base import Backend, BackendError
from .demo import DemoBackend
from .hap import HapBackend
from .homebridge_ui import HomebridgeUiBackend

__all__ = ["Backend", "BackendError", "DemoBackend", "HapBackend", "HomebridgeUiBackend", "create_backends"]


def create_backends(cfg: AppConfig) -> list[Backend]:
    backends: list[Backend] = []
    backends += [HapBackend(c) for c in cfg.hap]
    backends += [HomebridgeUiBackend(c) for c in cfg.homebridge_ui]
    if cfg.demo.enabled:
        backends.append(DemoBackend(cfg.demo.name))
    names = [b.name for b in backends]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"Backend-Namen müssen eindeutig sein, doppelt: {sorted(dupes)}")
    return backends
