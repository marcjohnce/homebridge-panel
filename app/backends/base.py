from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..hap_types import Char, ServiceSnapshot


class BackendError(Exception):
    pass


class Backend(ABC):
    """A source of devices (e.g. a Homebridge instance)."""

    def __init__(self, name: str):
        self.name = name

    async def start(self) -> None:  # pragma: no cover - optional
        pass

    async def stop(self) -> None:  # pragma: no cover - optional
        pass

    @abstractmethod
    async def fetch(self) -> list[ServiceSnapshot]:
        """Returns all controllable services with their current values."""

    @abstractmethod
    async def write(self, writes: list[tuple[Char, Any]]) -> None:
        """Writes characteristic values."""
