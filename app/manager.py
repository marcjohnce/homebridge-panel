"""Central device management: polls backends, executes commands, distributes changes."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .backends import Backend
from .config import AppConfig
from .hap_types import ServiceSnapshot, command_to_writes, snapshot_to_state
from .models import DEFAULT_ICONS, Device

log = logging.getLogger(__name__)
MOVING_POLL = 1.0   # seconds between polls while a blind is moving
MOVING_STALL = 5    # stop fast polling after this many polls without any position change


class DeviceNotFound(KeyError):
    pass


class DeviceManager:
    def __init__(self, cfg: AppConfig, backends: list[Backend]):
        self.cfg = cfg
        self.backends = {b.name: b for b in backends}
        self.snapshots: dict[str, tuple[Backend, ServiceSnapshot]] = {}
        self.devices: dict[str, Device] = {}
        self.status: dict[str, dict[str, Any]] = {
            b.name: {"ok": False, "error": None, "last_update": None, "devices": 0} for b in backends
        }
        self._listeners: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._locks = {b.name: asyncio.Lock() for b in backends}
        self._follow: set[str] = set()
        self._stall: dict[str, tuple[tuple, int]] = {}   # backend -> (last positions, polls unchanged)

    # ---------- lifecycle ----------
    async def start(self) -> None:
        for b in self.backends.values():
            await b.start()
        await self.refresh_all()
        self._task = asyncio.create_task(self._poll_loop(), name="poll")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        for b in self.backends.values():
            await b.stop()

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self.cfg.server.poll_interval)
            try:
                await self.refresh_all()
            except Exception:  # pragma: no cover - keep the loop alive
                log.exception("Polling failed")

    # ---------- polling ----------
    async def refresh_all(self) -> None:
        await asyncio.gather(*(self.refresh(b) for b in self.backends.values()))

    async def refresh(self, backend: Backend) -> None:
        async with self._locks[backend.name]:
            st = self.status[backend.name]
            try:
                snaps = await backend.fetch()
            except Exception as e:
                if st["ok"] or st["error"] != str(e):
                    log.warning("Backend %s: %s", backend.name, e)
                st.update(ok=False, error=str(e))
                changed = []
                for dev in self.devices.values():
                    if dev.backend == backend.name and dev.reachable:
                        dev.reachable = False
                        changed.append(dev)
                for dev in changed:
                    await self._broadcast({"type": "device", "device": dev.to_dict()})
                await self._broadcast({"type": "status", "backends": self.status})
                return

            was_ok = st["ok"]
            seen: set[str] = set()
            for snap in snaps:
                dev_id = f"{backend.name}:{snap.key}"
                seen.add(dev_id)
                self.snapshots[dev_id] = (backend, snap)
                dev = self._build(dev_id, backend, snap)
                if dev is None:
                    continue
                old = self.devices.get(dev_id)
                if old is None or old.to_dict() != dev.to_dict():
                    self.devices[dev_id] = dev
                    await self._broadcast({"type": "device", "device": dev.to_dict()})
            for dev_id in [d for d, (b, _) in self.snapshots.items() if b is backend and d not in seen]:
                self.snapshots.pop(dev_id, None)
                if self.devices.pop(dev_id, None):
                    await self._broadcast({"type": "remove", "id": dev_id})
            st.update(ok=True, error=None, last_update=time.time(),
                      devices=sum(1 for d in self.devices.values() if d.backend == backend.name))
            self._follow_movement(backend)
            if not was_ok:
                log.info("Backend %s connected (%d devices)", backend.name, st["devices"])
                await self._broadcast({"type": "status", "backends": self.status})

    def _follow_movement(self, backend: Backend) -> None:
        """While a blind of this backend is moving, poll it every MOVING_POLL seconds
        instead of waiting for the regular interval, so its position updates smoothly."""
        positions = tuple(sorted((d.id, d.state.get("position")) for d in self.devices.values()
                                 if d.backend == backend.name and d.state.get("moving") in ("opening", "closing")))
        if not positions:
            self._stall.pop(backend.name, None)
            return
        last, unchanged = self._stall.get(backend.name, ((), 0))
        unchanged = unchanged + 1 if positions == last else 0
        self._stall[backend.name] = (positions, unchanged)
        if unchanged >= MOVING_STALL:     # blind stuck short of its target: back to normal polling
            return
        if backend.name not in self._follow:
            self._follow.add(backend.name)

            async def again():
                self._follow.discard(backend.name)
                await self.refresh(backend)

            asyncio.get_running_loop().call_later(MOVING_POLL, lambda: asyncio.ensure_future(again()))

    def _build(self, dev_id: str, backend: Backend, snap: ServiceSnapshot) -> Device | None:
        ov = self.cfg.devices.get(dev_id) or self.cfg.devices.get(snap.name)
        if ov and ov.hidden:
            return None
        dtype, state, caps, meta = snapshot_to_state(snap)
        if ov and ov.outdoor:
            meta["outdoor"] = True
        icon_hint = meta.pop("icon_hint", None)
        if "modes" in meta and not self.cfg.panel.show_cooling:
            meta["modes"] = [m for m in meta["modes"] if m != "cool"]
        return Device(
            id=dev_id,
            name=(ov.name if ov and ov.name else snap.name),
            type=dtype,
            backend=backend.name,
            room=(ov.room if ov and ov.room else self.cfg.panel.default_room),
            icon=(ov.icon if ov and ov.icon else icon_hint or DEFAULT_ICONS[dtype]),
            state=state,
            capabilities=caps,
            meta=meta,
            reachable=True,
            order=ov.order if ov else 100,
        )

    # ---------- commands ----------
    def resolve(self, ref: str) -> str:
        """Device ID or (display/original) name -> device ID."""
        if ref in self.devices:
            return ref
        low = ref.casefold()
        for dev_id, dev in self.devices.items():
            if dev.name.casefold() == low or self.snapshots[dev_id][1].name.casefold() == low:
                return dev_id
        raise DeviceNotFound(ref)

    async def command(self, ref: str, attrs: dict[str, Any]) -> Device:
        dev_id = self.resolve(ref)
        backend, snap = self.snapshots[dev_id]
        writes = command_to_writes(snap, attrs)  # ValueError for invalid commands
        await backend.write(writes)
        # apply optimistically; the next poll corrects it if needed
        for ch, value in writes:
            ch.value = value
        dev = self._build(dev_id, backend, snap)
        if dev:
            self.devices[dev_id] = dev
            await self._broadcast({"type": "device", "device": dev.to_dict()})
        asyncio.get_running_loop().call_later(
            1.0, lambda: asyncio.ensure_future(self.refresh(backend))
        )
        self._stall.pop(backend.name, None)
        self._follow_movement(backend)
        return dev

    async def run_scene(self, scene_id: str) -> dict[str, Any]:
        scene = next((s for s in self.cfg.scenes if s.id == scene_id), None)
        if scene is None:
            raise KeyError(scene_id)
        errors: dict[str, str] = {}

        async def run(action):
            try:
                await self.command(action.device, action.set)
            except Exception as e:
                errors[action.device] = str(e) or type(e).__name__

        await asyncio.gather(*(run(a) for a in scene.actions))
        if errors:
            log.warning("Scene %s: errors %s", scene_id, errors)
        await self._broadcast({"type": "scene", "id": scene_id, "errors": errors})
        return {"scene": scene_id, "errors": errors}

    # ---------- live updates ----------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._listeners.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._listeners.discard(q)

    async def _broadcast(self, msg: dict[str, Any]) -> None:
        for q in list(self._listeners):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                self._listeners.discard(q)

    def snapshot_message(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "title": self.cfg.panel.title,
            "devices": [d.to_dict() for d in self.devices.values()],
            "scenes": [s.model_dump(include={"id", "name", "icon"}) for s in self.cfg.scenes],
            "backends": self.status,
        }
