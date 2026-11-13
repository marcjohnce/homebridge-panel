"""Tests: python -m pytest -q"""
import asyncio
import json
from datetime import datetime

import httpx
import pytest

from app.backends import HapBackend, HomebridgeUiBackend, create_backends
from app.config import AppConfig, HapBackendConfig, HomebridgeUiBackendConfig
from app.hap_types import command_to_writes, short_uuid, snapshot_to_state
from app.manager import DeviceManager, DeviceNotFound
from app.scheduler import Scheduler

U = lambda s: f"{int(s, 16):08X}-0000-1000-8000-0026BB765291"  # noqa: E731


# ---------- Fake-HAP-Server (wie Homebridge im Insecure-Modus) ----------
def fake_hap_server(pin="031-45-154"):
    accessories = {"accessories": [
        {"aid": 1, "services": [
            {"iid": 1, "type": U("3E"), "characteristics": [
                {"iid": 2, "type": U("23"), "value": "Bridge", "perms": ["pr"]}]}]},
        {"aid": 2, "services": [
            {"iid": 1, "type": U("3E"), "characteristics": [
                {"iid": 2, "type": "23", "value": "Stehlampe", "perms": ["pr"]}]},
            {"iid": 9, "type": U("43"), "characteristics": [
                {"iid": 10, "type": U("25"), "value": False, "perms": ["pr", "pw", "ev"], "format": "bool"},
                {"iid": 11, "type": U("8"), "value": 50, "perms": ["pr", "pw", "ev"],
                 "minValue": 0, "maxValue": 100, "minStep": 1}]}]},
        {"aid": 3, "services": [
            {"iid": 1, "type": U("3E"), "characteristics": [
                {"iid": 2, "type": U("23"), "value": "Thermostat Flur", "perms": ["pr"]}]},
            {"iid": 20, "type": U("4A"), "characteristics": [
                {"iid": 21, "type": U("F"), "value": 0, "perms": ["pr", "ev"]},
                {"iid": 22, "type": U("33"), "value": 0, "perms": ["pr", "pw"], "minValue": 0, "maxValue": 3},
                {"iid": 23, "type": U("11"), "value": 19.5, "perms": ["pr", "ev"]},
                {"iid": 24, "type": U("35"), "value": 20, "perms": ["pr", "pw"],
                 "minValue": 10, "maxValue": 30, "minStep": 0.5}]}]},
    ]}
    writes = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.headers.get("authorization") != pin:
            return httpx.Response(470, json={"status": -70401})
        if req.method == "GET" and req.url.path == "/accessories":
            return httpx.Response(200, json=accessories)
        if req.method == "PUT" and req.url.path == "/characteristics":
            body = json.loads(req.content)
            for w in body["characteristics"]:
                writes.append(w)
                for acc in accessories["accessories"]:
                    if acc["aid"] == w["aid"]:
                        for svc in acc["services"]:
                            for ch in svc["characteristics"]:
                                if ch["iid"] == w["iid"]:
                                    ch["value"] = w["value"]
            return httpx.Response(204)
        return httpx.Response(404)

    return httpx.MockTransport(handler), writes


def test_short_uuid():
    assert short_uuid("00000043-0000-1000-8000-0026BB765291") == "43"
    assert short_uuid("0000000F-0000-1000-8000-0026bb765291") == "F"
    assert short_uuid("4a") == "4A"


def test_hap_backend_fetch_and_write():
    async def run():
        transport, writes = fake_hap_server()
        b = HapBackend(HapBackendConfig(), transport=transport)
        snaps = await b.fetch()
        assert [s.service_type for s in snaps] == ["Lightbulb", "Thermostat"]
        lamp, th = snaps
        assert lamp.name == "Stehlampe" and lamp.key == "2.9"
        dtype, state, caps, _ = snapshot_to_state(lamp)
        assert dtype.value == "light" and state == {"on": False, "brightness": 50}
        await b.write(command_to_writes(lamp, {"on": True, "brightness": 120}))
        assert writes == [{"aid": 2, "iid": 10, "value": True}, {"aid": 2, "iid": 11, "value": 100}]
        await b.write(command_to_writes(th, {"mode": "heat", "target_temp": 21.3}))
        assert writes[-2:] == [{"aid": 3, "iid": 22, "value": 1}, {"aid": 3, "iid": 24, "value": 21.5}]
        _, state, _, meta = snapshot_to_state((await b.fetch())[1])
        assert state["mode"] == "heat" and state["target_temp"] == 21.5 and meta["max_temp"] == 30
        await b.stop()
    asyncio.run(run())


def test_hap_wrong_pin():
    async def run():
        transport, _ = fake_hap_server(pin="111-11-111")
        b = HapBackend(HapBackendConfig(), transport=transport)
        with pytest.raises(Exception, match="PIN"):
            await b.fetch()
    asyncio.run(run())


def test_homebridge_ui_backend():
    calls = []
    data = [
        {"uniqueId": "abc", "type": "Outlet", "serviceName": "Waschmaschine",
         "serviceCharacteristics": [
             {"type": "On", "value": 0, "canWrite": True},
             {"type": "OutletInUse", "value": 1, "canWrite": False}],
         "accessoryInformation": {"Name": "Plug 1"}},
        {"uniqueId": "def", "type": "HeaterCooler", "serviceName": "Heizkörper",
         "serviceCharacteristics": [
             {"type": "Active", "value": 1, "canWrite": True},
             {"type": "TargetHeaterCoolerState", "value": 1, "canWrite": True},
             {"type": "CurrentHeaterCoolerState", "value": 2, "canWrite": False},
             {"type": "CurrentTemperature", "value": 20.1, "canWrite": False},
             {"type": "HeatingThresholdTemperature", "value": 21, "canWrite": True,
              "minValue": 5, "maxValue": 30, "minStep": 0.5}]},
        {"uniqueId": "zzz", "type": "MotionSensor", "serviceName": "PIR", "serviceCharacteristics": []},
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path, req.content and json.loads(req.content)))
        if req.url.path == "/api/auth/login":
            return httpx.Response(201, json={"access_token": "tok", "expires_in": 28800})
        assert req.headers["authorization"] == "Bearer tok"
        if req.url.path == "/api/accessories":
            return httpx.Response(200, json=data)
        if req.method == "PUT":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    async def run():
        b = HomebridgeUiBackend(HomebridgeUiBackendConfig(username="admin", password="pw"),
                                transport=httpx.MockTransport(handler))
        snaps = await b.fetch()
        assert [s.name for s in snaps] == ["Waschmaschine", "Heizkörper"]
        _, st, _, _ = snapshot_to_state(snaps[0])
        assert st == {"on": False, "in_use": True}
        _, st, caps, _ = snapshot_to_state(snaps[1])
        assert st["mode"] == "heat" and st["heating"] and st["target_temp"] == 21 and "target_temp" in caps
        await b.write(command_to_writes(snaps[1], {"mode": "off"}))
        await b.write(command_to_writes(snaps[1], {"target_temp": 23.2}))
        puts = [c for c in calls if c[0] == "PUT"]
        assert puts == [
            ("PUT", "/api/accessories/def", {"characteristicType": "Active", "value": 0}),
            ("PUT", "/api/accessories/def", {"characteristicType": "HeatingThresholdTemperature", "value": 23.0}),
        ]
        assert sum(1 for c in calls if c[1] == "/api/auth/login") == 1
    asyncio.run(run())


def test_invalid_commands():
    async def run():
        transport, _ = fake_hap_server()
        lamp, th = await HapBackend(HapBackendConfig(), transport=transport).fetch()
        with pytest.raises(ValueError):
            command_to_writes(lamp, {"target_temp": 20})
        with pytest.raises(ValueError):
            command_to_writes(th, {"mode": "turbo"})
        with pytest.raises(ValueError):
            command_to_writes(lamp, {"foo": 1})
    asyncio.run(run())


def demo_cfg(**kw):
    return AppConfig.model_validate({
        "demo": {"enabled": True},
        "devices": {"Kaffeemaschine": {"room": "Küche", "icon": "coffee"}, "Ventilator": {"hidden": True}},
        "scenes": [{"id": "aus", "name": "Alles aus", "actions": [
            {"device": "Deckenlicht Wohnzimmer", "set": {"on": False}},
            {"device": "TV-Steckdose", "set": {"on": False}},
            {"device": "gibt-es-nicht", "set": {"on": False}}]}],
        **kw,
    })


def test_manager_with_demo_backend():
    async def run():
        m = DeviceManager(demo_cfg(), create_backends(demo_cfg()))
        q = m.subscribe()
        await m.start()
        names = {d.name for d in m.devices.values()}
        assert "Kaffeemaschine" in names and "Ventilator" not in names
        coffee = m.devices[m.resolve("Kaffeemaschine")]
        assert coffee.room == "Küche" and coffee.icon == "coffee" and coffee.state["on"] is False
        assert (await m.command("Kaffeemaschine", {"on": True})).state["on"] is True
        assert (await m.command("Heizung Bad", {"mode": "heat", "target_temp": 23})).state["target_temp"] == 23
        with pytest.raises(ValueError):
            await m.command("Kaffeemaschine", {"brightness": 3})
        with pytest.raises(DeviceNotFound):
            await m.command("unbekannt", {"on": True})
        res = await m.run_scene("aus")
        assert list(res["errors"]) == ["gibt-es-nicht"]
        assert m.devices[m.resolve("Deckenlicht Wohnzimmer")].state["on"] is False
        assert not q.empty()
        await m.stop()
    asyncio.run(run())


def test_scheduler_due():
    cfg = AppConfig.model_validate({"schedules": [
        {"time": "06:30", "days": ["Mo", "Di"], "scene": "a"},
        {"time": "06:30", "scene": "b", "enabled": True}]})
    s = Scheduler(cfg, DeviceManager(cfg, []))
    monday = datetime(2026, 11, 16, 6, 30)
    assert s.due(monday) == ["a", "b"]
    assert s.due(monday) == []                    # nicht doppelt
    assert s.due(datetime(2026, 11, 18, 6, 30)) == ["b"]  # Mittwoch
