"""Lists every accessory and service a Homebridge bridge delivers and what the panel makes of it.

Helps when a device does not show up on the panel: is it on this bridge at all, which HomeKit
service does the plugin use, and does the panel know that service?

    .venv/bin/python tools/list_services.py           # bridges from the panel settings and config.yaml
    .venv/bin/python tools/list_services.py --host 192.168.1.20 --port 51826 --pin 031-45-154

(with the Python of the app, in ~/homebridge-panel: the system Python lacks its packages)

Child bridges have a port (and PIN) of their own: a plugin running as a child bridge is not on
the main bridge. Add it under `hap:` in config.yaml or pass --port/--pin.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backends.hap import HapBackend  # noqa: E402
from app.config import HapBackendConfig, load_config  # noqa: E402
from app.hap_types import (CHAR_TYPES, DEVICE_TYPE_BY_SERVICE, EVE_HISTORY_SERVICE, POWER_CHARS,  # noqa: E402
                           SENSOR_SERVICES, SERVICE_TYPES, short_uuid)
from app.settings import SettingsStore, apply_to_config, default_path  # noqa: E402

SKIP = {"AccessoryInformation", "A2"}   # no device of their own (A2: HAP protocol information)
NOTE = {"Battery": "battery of the other services"}


def bridges(args: argparse.Namespace) -> list[HapBackendConfig]:
    if args.host:
        return [HapBackendConfig(name="bridge", host=args.host, port=args.port, pin=args.pin)]
    cfg = load_config(args.config, required=False)
    store = SettingsStore(Path(args.settings) if args.settings else default_path())
    return list(apply_to_config(cfg, store.values).hap)


async def dump(b: HapBackendConfig) -> None:
    print(f"\n=== {b.name}: {b.host}:{b.port}")
    backend = HapBackend(b)
    try:
        r = await backend.client.get("/accessories")
    except Exception as e:                      # noqa: BLE001 – show any connection problem
        print(f"  not reachable: {e}")
        await backend.stop()
        return
    if r.status_code != 200:
        print(f"  HTTP {r.status_code} – PIN wrong or Homebridge not started with -I (insecure mode)?")
        await backend.stop()
        return
    for acc in r.json().get("accessories", []):
        name = ""
        for svc in acc.get("services", []):
            if SERVICE_TYPES.get(short_uuid(svc.get("type", ""))) == "AccessoryInformation":
                for ch in svc.get("characteristics", []):
                    if CHAR_TYPES.get(short_uuid(ch.get("type", ""))) == "Name":
                        name = ch.get("value") or ""
        print(f"  [{acc.get('aid')}] {name}")
        for svc in acc.get("services", []):
            short = short_uuid(svc.get("type", ""))
            stype = SERVICE_TYPES.get(short)
            if stype in SKIP or short in SKIP:
                continue
            if stype in DEVICE_TYPE_BY_SERVICE:
                status = f"shown as {DEVICE_TYPE_BY_SERVICE[stype].value}"
            elif stype in SENSOR_SERVICES:
                status = "shown as sensor"
            elif stype in NOTE:
                status = NOTE[stype]
            elif str(svc.get("type", "")).upper() == EVE_HISTORY_SERVICE:
                status = "Eve history (charts in the detail view)"
            elif any(CHAR_TYPES.get(short_uuid(c.get("type", ""))) in POWER_CHARS for c in svc.get("characteristics", [])):
                status = "power readings, shown at the plug or switch"
            else:
                status = "NOT SUPPORTED by the panel"
            chars = [CHAR_TYPES.get(short_uuid(c.get("type", "")), short_uuid(c.get("type", "")))
                     for c in svc.get("characteristics", [])]
            print(f"      {stype or 'unknown service ' + short:<28} {status}")
            print(f"          {', '.join(str(c) for c in chars)}")
    await backend.stop()


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--host")
    p.add_argument("--port", type=int, default=51826)
    p.add_argument("--pin", default="031-45-154")
    p.add_argument("--config", help="Path to config.yaml")
    p.add_argument("--settings", help="Path to the panel settings.json")
    args = p.parse_args()
    for b in bridges(args):
        await dump(b)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
