from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..hap_types import Char, ServiceSnapshot


class BackendError(Exception):
    pass


class Backend(ABC):
    """Eine Quelle für Geräte (z. B. eine Homebridge-Instanz)."""

    def __init__(self, name: str):
        self.name = name

    async def start(self) -> None:  # pragma: no cover - optional
        pass

    async def stop(self) -> None:  # pragma: no cover - optional
        pass

    @abstractmethod
    async def fetch(self) -> list[ServiceSnapshot]:
        """Liefert alle steuerbaren Services mit aktuellen Werten."""

    @abstractmethod
    async def write(self, writes: list[tuple[Char, Any]]) -> None:
        """Schreibt Characteristic-Werte."""
