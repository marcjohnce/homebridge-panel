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


# ---------- fake HAP server (like Homebridge in insecure mode) ----------
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
        {"uniqueId": "abc", "type": "Outlet", "serviceName": "Washing Machine",
         "serviceCharacteristics": [
             {"type": "On", "value": 0, "canWrite": True},
             {"type": "OutletInUse", "value": 1, "canWrite": False}],
         "accessoryInformation": {"Name": "Plug 1"}},
        {"uniqueId": "def", "type": "HeaterCooler", "serviceName": "Radiator",
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
        assert [s.name for s in snaps] == ["Washing Machine", "Radiator"]
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
        "devices": {"Coffee Maker": {"room": "Kitchen", "icon": "coffee"}, "Fan": {"hidden": True}},
        "scenes": [{"id": "off", "name": "All off", "actions": [
            {"device": "Living Room Ceiling Light", "set": {"on": False}},
            {"device": "TV Plug", "set": {"on": False}},
            {"device": "does-not-exist", "set": {"on": False}}]}],
        **kw,
    })


def test_manager_with_demo_backend():
    async def run():
        m = DeviceManager(demo_cfg(), create_backends(demo_cfg()))
        q = m.subscribe()
        await m.start()
        names = {d.name for d in m.devices.values()}
        assert "Coffee Maker" in names and "Fan" not in names
        coffee = m.devices[m.resolve("Coffee Maker")]
        assert coffee.room == "Kitchen" and coffee.icon == "coffee" and coffee.state["on"] is False
        assert (await m.command("Coffee Maker", {"on": True})).state["on"] is True
        assert (await m.command("Bathroom Heating", {"mode": "heat", "target_temp": 23})).state["target_temp"] == 23
        with pytest.raises(ValueError):
            await m.command("Coffee Maker", {"brightness": 3})
        with pytest.raises(DeviceNotFound):
            await m.command("unbekannt", {"on": True})
        res = await m.run_scene("off")
        assert list(res["errors"]) == ["does-not-exist"]
        assert m.devices[m.resolve("Living Room Ceiling Light")].state["on"] is False
        assert not q.empty()
        await m.stop()
    asyncio.run(run())


def test_scheduler_due():
    cfg = AppConfig.model_validate({"schedules": [
        {"time": "06:30", "days": ["Mo", "Di"], "scene": "a"},  # "Di" = German alias for "tu"
        {"time": "06:30", "scene": "b", "enabled": True}]})
    s = Scheduler(cfg, DeviceManager(cfg, []))
    monday = datetime(2026, 11, 16, 6, 30)
    assert s.due(monday) == ["a", "b"]
    assert s.due(monday) == []                    # not twice
    assert s.due(datetime(2026, 11, 18, 6, 30)) == ["b"]  # Wednesday


# ---------- sensors ----------
EVE = lambda s: f"E863F{s}-079E-48FF-8F27-9C2605A29F52"  # noqa: E731


def test_hap_sensors_are_merged_per_accessory():
    data = {"accessories": [
        {"aid": 4, "services": [
            {"iid": 1, "type": U("3E"), "characteristics": [
                {"iid": 2, "type": U("23"), "value": "Weather Station", "perms": ["pr"]}]},
            {"iid": 10, "type": U("8A"), "characteristics": [
                {"iid": 11, "type": U("23"), "value": "Temperature", "perms": ["pr"]},
                {"iid": 12, "type": U("11"), "value": 6.4, "perms": ["pr", "ev"]}]},
            {"iid": 20, "type": U("82"), "characteristics": [
                {"iid": 21, "type": U("10"), "value": 81, "perms": ["pr", "ev"]}]},
            {"iid": 30, "type": EVE("00A"), "characteristics": [
                {"iid": 31, "type": EVE("10F"), "value": 1013.6, "perms": ["pr", "ev"]}]}]},
        {"aid": 5, "services": [
            {"iid": 1, "type": U("3E"), "characteristics": [
                {"iid": 2, "type": U("23"), "value": "Hall Lux", "perms": ["pr"]}]},
            {"iid": 8, "type": U("84"), "characteristics": [
                {"iid": 9, "type": U("23"), "value": "Hall Lux", "perms": ["pr"]},
                {"iid": 10, "type": U("6B"), "value": 245.5, "perms": ["pr", "ev"]}]}]},
    ]}
    snaps = HapBackend.parse_accessories(data)
    assert [(s.key, s.service_type, s.name) for s in snaps] == [
        ("4.sensors", "Sensor", "Weather Station"), ("5.sensors", "Sensor", "Hall Lux")]
    dtype, state, caps, meta = snapshot_to_state(snaps[0])
    assert dtype.value == "sensor"
    assert state == {"current_temp": 6.4, "humidity": 81.0, "pressure": 1013.6}
    assert meta["icon_hint"] == "weather"
    _, state, _, meta = snapshot_to_state(snaps[1])
    assert state == {"lux": 245.5} and meta["icon_hint"] == "sun"
    with pytest.raises(ValueError):
        command_to_writes(snaps[0], {"on": True})


def test_ui_sensors_including_eve_air_pressure():
    data = [
        {"uniqueId": "t1", "aid": 7, "instance": {"username": "0E:AA"}, "type": "TemperatureSensor",
         "serviceName": "Balcony", "accessoryInformation": {"Name": "Balcony Weather"},
         "serviceCharacteristics": [{"type": "CurrentTemperature", "value": 3.5, "canWrite": False}]},
        {"uniqueId": "p1", "aid": 7, "instance": {"username": "0E:AA"}, "type": "Unknown",
         "uuid": EVE("00A"), "serviceName": "Air Pressure", "accessoryInformation": {"Name": "Balcony Weather"},
         "serviceCharacteristics": [{"type": "Air Pressure", "uuid": EVE("10F"), "value": 998.2, "canWrite": False}]},
        {"uniqueId": "h1", "aid": 8, "instance": {"username": "0E:AA"}, "type": "HumiditySensor",
         "serviceName": "Bathroom Humidity", "accessoryInformation": {"Name": "Bath Sensor"},
         "serviceCharacteristics": [{"type": "CurrentRelativeHumidity", "value": 64, "canWrite": False}]},
    ]
    snaps = HomebridgeUiBackend.parse_accessories(data)
    assert [(s.key, s.name) for s in snaps] == [("0E:AA:7.sensors", "Balcony Weather"),
                                                ("0E:AA:8.sensors", "Bathroom Humidity")]
    assert snapshot_to_state(snaps[0])[1] == {"pressure": 998.2, "current_temp": 3.5}
    _, state, _, meta = snapshot_to_state(snaps[1])
    assert state == {"humidity": 64.0} and meta["icon_hint"] == "drop"


def test_outdoor_override_and_icon_hint():
    cfg = AppConfig.model_validate({"demo": {"enabled": True},
                                    "devices": {"Weather Station": {"room": "Garden", "outdoor": True}}})

    async def run():
        m = DeviceManager(cfg, create_backends(cfg))
        await m.start()
        ws = m.devices[m.resolve("Weather Station")]
        lux = m.devices[m.resolve("Hall Light Sensor")]
        assert ws.type.value == "sensor" and ws.room == "Garden" and ws.meta["outdoor"] is True
        assert ws.icon == "weather" and lux.icon == "sun" and "outdoor" not in lux.meta
        assert "icon_hint" not in ws.meta
        await m.stop()
    asyncio.run(run())
