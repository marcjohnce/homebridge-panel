"""Direkter HAP-Zugriff auf Homebridge (HAP-NodeJS) im Insecure-Modus.

Homebridge muss mit `-I` (Insecure-Modus) gestartet sein. Dann akzeptiert der
HAP-Server unverschlüsselte HTTP-Anfragen mit dem Bridge-PIN im
Authorization-Header:

    GET  /accessories
    PUT  /characteristics   {"characteristics":[{"aid":2,"iid":10,"value":true}]}

Child-Bridges laufen auf eigenen Ports – dafür einfach weitere `hap`-Einträge
in der Konfiguration anlegen.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..config import HapBackendConfig
from ..hap_types import CHAR_TYPES, DEVICE_TYPE_BY_SERVICE, SERVICE_TYPES, Char, ServiceSnapshot, short_uuid
from .base import Backend, BackendError

log = logging.getLogger(__name__)


class HapBackend(Backend):
    def __init__(self, cfg: HapBackendConfig, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(cfg.name)
        self.cfg = cfg
        self.client = httpx.AsyncClient(
            base_url=f"http://{cfg.host}:{cfg.port}",
            headers={"Authorization": cfg.pin, "Content-Type": "application/hap+json"},
            timeout=cfg.timeout,
            transport=transport,
        )

    async def stop(self) -> None:
        await self.client.aclose()

    async def fetch(self) -> list[ServiceSnapshot]:
        try:
            r = await self.client.get("/accessories")
        except httpx.HTTPError as e:
            raise BackendError(f"HAP {self.cfg.host}:{self.cfg.port} nicht erreichbar: {e}") from e
        if r.status_code in (401, 470):
            raise BackendError("HAP: Zugriff verweigert – PIN prüfen und Homebridge mit -I (Insecure) starten")
        if r.status_code != 200:
            raise BackendError(f"HAP: unerwartete Antwort {r.status_code}")
        return self.parse_accessories(r.json())

    @staticmethod
    def parse_accessories(data: dict[str, Any]) -> list[ServiceSnapshot]:
        result: list[ServiceSnapshot] = []
        for acc in data.get("accessories", []):
            aid = acc["aid"]
            acc_name = ""
            services = acc.get("services", [])
            for svc in services:
                if SERVICE_TYPES.get(short_uuid(svc.get("type", ""))) == "AccessoryInformation":
                    for ch in svc.get("characteristics", []):
                        if CHAR_TYPES.get(short_uuid(ch.get("type", ""))) == "Name":
                            acc_name = ch.get("value") or ""
            for svc in services:
                stype = SERVICE_TYPES.get(short_uuid(svc.get("type", "")))
                if stype not in DEVICE_TYPE_BY_SERVICE:
                    continue
                chars: dict[str, Char] = {}
                for ch in svc.get("characteristics", []):
                    cname = CHAR_TYPES.get(short_uuid(ch.get("type", "")))
                    if not cname:
                        continue
                    chars[cname] = Char(
                        name=cname,
                        value=ch.get("value"),
                        writable="pw" in ch.get("perms", []),
                        ref=(aid, ch["iid"]),
                        min=ch.get("minValue"),
                        max=ch.get("maxValue"),
                        step=ch.get("minStep"),
                    )
                name = (chars.get("ConfiguredName") and chars["ConfiguredName"].value) \
                    or (chars.get("Name") and chars["Name"].value) or acc_name or f"{stype} {aid}"
                result.append(ServiceSnapshot(
                    key=f"{aid}.{svc['iid']}", service_type=stype, name=name,
                    chars=chars, accessory=acc_name,
                ))
        return result

    async def write(self, writes: list[tuple[Char, Any]]) -> None:
        body = {"characteristics": [
            {"aid": ch.ref[0], "iid": ch.ref[1], "value": value} for ch, value in writes
        ]}
        try:
            r = await self.client.put("/characteristics", content=json.dumps(body))
        except httpx.HTTPError as e:
            raise BackendError(f"HAP-Schreibfehler: {e}") from e
        if r.status_code == 207:  # Multi-Status: Teilfehler
            errors = [c for c in r.json().get("characteristics", []) if c.get("status", 0) != 0]
            if errors:
                raise BackendError(f"HAP meldet Fehler beim Schreiben: {errors}")
        elif r.status_code not in (200, 204):
            raise BackendError(f"HAP-Schreibfehler: Status {r.status_code} {r.text[:200]}")
