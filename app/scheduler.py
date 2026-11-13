"""Simple scheduler: runs scenes at fixed times on selected weekdays."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import WEEKDAYS, AppConfig
from .manager import DeviceManager

log = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, cfg: AppConfig, manager: DeviceManager):
        self.cfg = cfg
        self.manager = manager
        self.tz = ZoneInfo(cfg.server.timezone)
        self._fired: set[str] = set()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self.cfg.schedules:
            self._task = asyncio.create_task(self._loop(), name="scheduler")

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    def due(self, now: datetime) -> list[str]:
        hhmm, day = now.strftime("%H:%M"), WEEKDAYS[now.weekday()]
        out = []
        for i, s in enumerate(self.cfg.schedules):
            key = f"{now.date()}|{i}"
            if s.enabled and s.time == hhmm and day in s.days and key not in self._fired:
                self._fired.add(key)
                out.append(s.scene)
        # drop entries from previous days
        self._fired = {k for k in self._fired if k.startswith(str(now.date()))}
        return out

    async def _loop(self) -> None:
        while True:
            for scene in self.due(datetime.now(self.tz)):
                log.info("Schedule: running scene %s", scene)
                try:
                    await self.manager.run_scene(scene)
                except KeyError:
                    log.error("Schedule refers to unknown scene '%s'", scene)
            await asyncio.sleep(15)
