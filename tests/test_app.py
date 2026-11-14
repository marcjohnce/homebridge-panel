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
        {"uniqueId": "zzz", "type": "AirPurifier", "serviceName": "Purifier", "serviceCharacteristics": []},
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


# ---------- blinds ----------
def blind_snapshot(with_hold=True, with_tilt=True):
    chars = [
        {"iid": 10, "type": U("6D"), "value": 40, "perms": ["pr", "ev"]},
        {"iid": 11, "type": U("7C"), "value": 40, "perms": ["pr", "pw", "ev"], "minValue": 0, "maxValue": 100},
        {"iid": 12, "type": U("72"), "value": 2, "perms": ["pr", "ev"]},
    ]
    if with_hold:
        chars.append({"iid": 13, "type": U("6F"), "perms": ["pw"]})
    if with_tilt:
        chars.append({"iid": 14, "type": U("7B"), "value": 0, "perms": ["pr", "pw"], "minValue": -90, "maxValue": 90})
    data = {"accessories": [{"aid": 6, "services": [
        {"iid": 1, "type": U("3E"), "characteristics": [{"iid": 2, "type": U("23"), "value": "Study Blind", "perms": ["pr"]}]},
        {"iid": 9, "type": U("8C"), "characteristics": chars}]}]}
    return HapBackend.parse_accessories(data)[0]


def test_blind_state_and_commands():
    s = blind_snapshot()
    dtype, state, caps, meta = snapshot_to_state(s)
    assert dtype.value == "blind" and s.service_type == "WindowCovering"
    assert state == {"position": 40, "target": 40, "moving": "stopped", "on": True, "obstructed": False, "tilt": 0}
    assert set(caps) >= {"position", "stop", "tilt"} and meta == {"min_tilt": -90, "max_tilt": 90}

    w = lambda attrs: [(ch.name, v) for ch, v in command_to_writes(s, attrs)]  # noqa: E731
    assert w({"position": 130}) == [("TargetPosition", 100)]
    assert w({"on": False}) == [("TargetPosition", 0)]
    assert w({"on": True}) == [("TargetPosition", 100)]
    assert w({"stop": True}) == [("HoldPosition", True)]
    assert w({"stop": False}) == []
    assert w({"tilt": -120}) == [("TargetHorizontalTiltAngle", -90)]

    plain = blind_snapshot(with_hold=False, with_tilt=False)
    assert [(ch.name, v) for ch, v in command_to_writes(plain, {"stop": True})] == [("TargetPosition", 40)]
    with pytest.raises(ValueError):
        command_to_writes(plain, {"tilt": 10})
    with pytest.raises(ValueError):
        command_to_writes(plain, {"brightness": 10})


def test_blind_moving_state_without_position_state():
    s = blind_snapshot()
    del s.chars["PositionState"]
    s.chars["TargetPosition"].value = 90
    assert snapshot_to_state(s)[1]["moving"] == "opening"
    s.chars["TargetPosition"].value = 10
    assert snapshot_to_state(s)[1]["moving"] == "closing"


def test_blind_moves_and_is_followed_quickly():
    cfg = AppConfig.model_validate({"demo": {"enabled": True}, "server": {"poll_interval": 60}})

    async def run():
        m = DeviceManager(cfg, create_backends(cfg))
        await m.start()
        dev = await m.command("Living Room Blinds", {"position": 0})
        assert dev.state["target"] == 0 and dev.state["moving"] == "closing"
        # regular polling is 60 s; the blind must still arrive within a few seconds
        for _ in range(60):
            await asyncio.sleep(0.1)
            if m.devices[m.resolve("Living Room Blinds")].state["position"] == 0:
                break
        state = m.devices[m.resolve("Living Room Blinds")].state
        assert state["position"] == 0 and state["moving"] == "stopped"
        await m.command("Bedroom Blinds", {"on": True})
        await asyncio.sleep(1.2)
        await m.command("Bedroom Blinds", {"stop": True})
        await asyncio.sleep(2.5)
        state = m.devices[m.resolve("Bedroom Blinds")].state
        assert 0 < state["position"] < 100 and state["moving"] == "stopped"
        await m.stop()
    asyncio.run(run())


def test_fast_polling_stops_for_stuck_blind():
    import app.manager as mgr_mod
    cfg = AppConfig.model_validate({"demo": {"enabled": True}, "server": {"poll_interval": 60}})

    async def run():
        m = DeviceManager(cfg, create_backends(cfg))
        await m.start()
        backend = next(iter(m.backends.values()))
        calls = 0
        orig = backend.fetch

        async def counting_fetch():
            nonlocal calls
            calls += 1
            snaps = await orig()
            for s in snaps:                       # blind never reaches its target
                if s.key == "living-blinds":
                    s.chars["CurrentPosition"].value = 55
                    s.chars["TargetPosition"].value = 0
                    s.chars["PositionState"].value = 2
            return snaps
        backend.fetch = counting_fetch
        old = mgr_mod.MOVING_POLL
        mgr_mod.MOVING_POLL = 0.05
        try:
            await m.refresh(backend)
            await asyncio.sleep(1.5)
            assert calls <= mgr_mod.MOVING_STALL + 3      # stopped following, no endless fast polling
        finally:
            mgr_mod.MOVING_POLL = old
        await m.stop()
    asyncio.run(run())


# ---------- security sensors ----------
def test_security_sensors_from_hap():
    data = {"accessories": [{"aid": 7, "services": [
        {"iid": 1, "type": U("3E"), "characteristics": [{"iid": 2, "type": U("23"), "value": "Hall", "perms": ["pr"]}]},
        {"iid": 10, "type": U("80"), "characteristics": [{"iid": 11, "type": U("6A"), "value": 1, "perms": ["pr", "ev"]}]},
        {"iid": 20, "type": U("83"), "characteristics": [{"iid": 21, "type": U("70"), "value": 0, "perms": ["pr", "ev"]}]},
        {"iid": 30, "type": U("85"), "characteristics": [{"iid": 31, "type": U("22"), "value": True, "perms": ["pr", "ev"]}]},
    ]}]}
    contact, leak, motion = HapBackend.parse_accessories(data)
    dtype, st, _, meta = snapshot_to_state(contact)
    assert dtype.value == "security" and st == {"triggered": True}
    assert meta == {"security": "contact", "kinds": ["window", "door", "contact", "glassbreak"]}
    assert snapshot_to_state(leak)[1:4:2] == ({"triggered": False}, {"security": "leak", "kinds": ["leak"]})
    assert snapshot_to_state(motion)[1] == {"triggered": True}
    with pytest.raises(ValueError):
        command_to_writes(contact, {"on": True})


def test_security_kind_override_and_icon():
    cfg = AppConfig.model_validate({"demo": {"enabled": True}, "devices": {
        "Bedroom Window": {"security": "window"}, "Washing Machine Leak": {"security": "window"}}})

    async def run():
        m = DeviceManager(cfg, create_backends(cfg))
        await m.start()
        win = m.devices[m.resolve("Bedroom Window")]
        leak = m.devices[m.resolve("Washing Machine Leak")]
        assert win.meta["security"] == "window" and win.icon == "window" and win.state["triggered"] is True
        assert leak.meta["security"] == "leak" and leak.icon == "leak"     # a leak sensor cannot be a window
        await m.stop()
    asyncio.run(run())


def test_washer_state_texts():
    from app.qt.format import category, state_text
    d = {"type": "plug", "reachable": True, "meta": {"appliance": "washer"}, "state": {"on": True, "in_use": True}}
    assert state_text(d) == "Running"
    assert state_text({**d, "state": {"on": True, "in_use": False}}) == "Ready"
    assert state_text({**d, "state": {"on": False, "in_use": False}}) == "Off"
    assert state_text({**d, "type": "switch", "state": {"on": True}}) == "On"     # no power measurement
    assert category({**d, "meta": {"appliance": "fan"}}) == "climate"
    assert category({**d, "meta": {"appliance": "fan", "area": "security"}}) == "security"


def test_mqtt_payload_extraction():
    from app.backends.mqtt import extract
    assert extract("1.62", "") == 1.62 and extract("1,5", "") == 1.5 and extract("on", "") == "on"
    assert extract('{"a": {"p": 2}}', "a.p") == 2.0 and extract('{"x": 1}', "y") is None
    assert extract("no json", "x") is None


def test_value_text():
    from app.qt.format import value_text
    d = {"type": "value", "state": {"value": 1.6213}, "meta": {"unit": "bar", "decimals": 2}}
    assert value_text(d) == "1.62 bar"
    assert value_text({**d, "state": {"value": None}}) == "No reading"
    assert value_text({**d, "state": {"value": "ok"}, "meta": {}}) == "ok"


def test_air_quality_sensor_merged_and_texts():
    from app.qt.format import air_warning, state_text
    data = {"accessories": [{"aid": 9, "services": [
        {"iid": 1, "type": U("3E"), "characteristics": [{"iid": 2, "type": U("23"), "value": "Eve Room", "perms": ["pr"]}]},
        {"iid": 10, "type": U("8A"), "characteristics": [{"iid": 11, "type": U("11"), "value": 21.5, "perms": ["pr"]}]},
        {"iid": 20, "type": U("8D"), "characteristics": [
            {"iid": 21, "type": U("95"), "value": 4, "perms": ["pr"]},
            {"iid": 22, "type": U("C8"), "value": 450, "perms": ["pr"]}]},
        {"iid": 30, "type": U("97"), "characteristics": [
            {"iid": 31, "type": U("92"), "value": 0, "perms": ["pr"]},
            {"iid": 32, "type": U("93"), "value": 820, "perms": ["pr"]}]},
    ]}]}
    snaps = HapBackend.parse_accessories(data)
    assert len(snaps) == 1                                  # one tile for the whole accessory
    dtype, st, _, meta = snapshot_to_state(snaps[0])
    assert dtype.value == "sensor" and st["air_quality"] == 4 and st["voc"] == 450 and st["co2"] == 820
    d = {"type": "sensor", "reachable": True, "state": st, "meta": meta}
    assert state_text(d) == "21.5 °C, Air inferior, 820 ppm"
    assert air_warning(d)
    assert not air_warning({**d, "state": {**st, "air_quality": 2}})
