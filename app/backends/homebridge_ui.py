"""Access via the REST API of homebridge-config-ui-x (the Homebridge web UI).

Endpoints:
    POST /api/auth/login        {"username","password","otp"} -> {"access_token","expires_in"}
    POST /api/auth/noauth       (when UI authentication is disabled)
    GET  /api/accessories
    PUT  /api/accessories/{uniqueId}  {"characteristicType":"On","value":true}

Homebridge must run in insecure mode here as well (UI setting
"Homebridge Insecure Mode" or start parameter -I), otherwise the UI returns
no accessories.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from ..config import HomebridgeUiBackendConfig
from ..hap_types import (CHAR_TYPES, DEVICE_TYPE_BY_SERVICE, SENSOR_SERVICES, SERVICE_TYPES, Char, ServiceSnapshot,
                         merge_sensors, short_uuid)
from .base import Backend, BackendError

log = logging.getLogger(__name__)


class HomebridgeUiBackend(Backend):
    def __init__(self, cfg: HomebridgeUiBackendConfig, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(cfg.name)
        self.cfg = cfg
        self.client = httpx.AsyncClient(
            base_url=cfg.url.rstrip("/"), timeout=cfg.timeout,
            verify=cfg.verify_ssl, transport=transport,
        )
        self._token: str | None = None
        self._token_expiry = 0.0

    async def stop(self) -> None:
        await self.client.aclose()

    async def _login(self) -> None:
        try:
            if self.cfg.username:
                payload = {"username": self.cfg.username, "password": self.cfg.password or ""}
                if self.cfg.otp:
                    payload["otp"] = self.cfg.otp
                r = await self.client.post("/api/auth/login", json=payload)
            else:
                r = await self.client.post("/api/auth/noauth")
        except httpx.HTTPError as e:
            raise BackendError(f"Homebridge UI {self.cfg.url} not reachable: {e}") from e
        if r.status_code not in (200, 201):
            raise BackendError(f"Homebridge UI login failed ({r.status_code}) – check username and password")
        data = r.json()
        self._token = data["access_token"]
        self._token_expiry = time.monotonic() + float(data.get("expires_in", 3600)) - 60

    async def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        for attempt in (1, 2):
            if not self._token or time.monotonic() > self._token_expiry:
                await self._login()
            try:
                r = await self.client.request(
                    method, path, headers={"Authorization": f"Bearer {self._token}"}, **kw
                )
            except httpx.HTTPError as e:
                raise BackendError(f"Homebridge UI request failed: {e}") from e
            if r.status_code == 401 and attempt == 1:
                self._token = None
                continue
            return r
        return r

    async def fetch(self) -> list[ServiceSnapshot]:
        r = await self._request("GET", "/api/accessories")
        if r.status_code != 200:
            raise BackendError(f"Homebridge-UI: /api/accessories -> {r.status_code}")
        return self.parse_accessories(r.json())

    @staticmethod
    def parse_accessories(data: list[dict[str, Any]]) -> list[ServiceSnapshot]:
        result: list[ServiceSnapshot] = []
        sensors: dict[str, list[ServiceSnapshot]] = {}
        for svc in data:
            stype = svc.get("type")
            if stype not in DEVICE_TYPE_BY_SERVICE and stype not in SENSOR_SERVICES:
                # custom services (e.g. Eve air pressure) are identified by their UUID
                stype = SERVICE_TYPES.get(short_uuid(svc.get("uuid", "")), stype)
            if stype not in DEVICE_TYPE_BY_SERVICE and stype not in SENSOR_SERVICES:
                continue
            uid = svc["uniqueId"]
            chars: dict[str, Char] = {}
            for ch in svc.get("serviceCharacteristics", []):
                ctype = (ch.get("type") or "").replace(" ", "")
                ctype = CHAR_TYPES.get(short_uuid(ch.get("uuid", "")), ctype)
                if not ctype:
                    continue
                chars[ctype] = Char(
                    name=ctype, value=ch.get("value"), writable=bool(ch.get("canWrite")),
                    ref=(uid, ctype), min=ch.get("minValue"), max=ch.get("maxValue"),
                    step=ch.get("minStep"),
                )
            info = svc.get("accessoryInformation") or {}
            name = svc.get("serviceName") or info.get("Name") or stype
            snap = ServiceSnapshot(key=uid, service_type=stype, name=name, chars=chars,
                                   accessory=info.get("Name", ""))
            if stype in SENSOR_SERVICES:
                instance = (svc.get("instance") or {}).get("username", "")
                group = f"{instance}:{svc['aid']}" if svc.get("aid") is not None else uid
                sensors.setdefault(group, []).append(snap)
            else:
                result.append(snap)
        for group, snaps in sensors.items():
            result.append(merge_sensors(group, snaps[0].accessory, snaps))
        return result

    async def write(self, writes: list[tuple[Char, Any]]) -> None:
        for ch, value in writes:
            uid, ctype = ch.ref
            r = await self._request("PUT", f"/api/accessories/{uid}",
                                    json={"characteristicType": ctype, "value": value})
            if r.status_code not in (200, 204):
                raise BackendError(f"Homebridge UI write failed {r.status_code}: {r.text[:200]}")
