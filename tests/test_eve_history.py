"""Eve history: decoding (fakegato-history and homebridge-lib layouts), transfer and cache."""
import asyncio
import base64
import json
import struct
import time

import pytest

from app.backends.eve_sim import ENERGY, THERMO, WEATHER, EveHistorySim
from app.backends.hap import HapBackend
from app.eve_history import (EPOCH_2001, DeviceHistory, HistoryError, bucket, energy_kwh, parse_entries, parse_status,
                             read_entries, request)


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def sim_io(sim: EveHistorySim):
    async def read(ref):
        return sim.status() if ref == "status" else sim.read_entries()

    async def write(ref, value):
        sim.request(value)
    return read, write


REFS = {"status": "status", "entries": "entries", "request": "request"}


def values(start, n, temp=lambda i: 2000 + i):
    return [(start + i * 600, [temp(i), 5000, 10130]) for i in range(n)]


def test_fakegato_weather_status_and_entries():
    # the hex strings fakegato-history 0.6.7 builds for a weather accessory
    ref = 815000000
    status = bytes.fromhex("58020000" "00000000") + struct.pack("<I", ref) + bytes.fromhex(
        "03 0102 0202 0302".replace(" ", "")) + struct.pack("<HHI", 3, 4032, 0) + bytes(4) + b"\x01\x01"
    s = parse_status(b64(status))
    assert (s.ref_time, s.fingerprint, s.count, s.memory, s.first, s.last) == (ref, WEATHER, 3, 4032, 0, 2)
    rec_ref = bytes.fromhex("15" "01000000" "01000000" "81") + struct.pack("<I", ref) + bytes(7)
    rec = bytes.fromhex("10") + struct.pack("<II", 2, 600) + b"\x07" + struct.pack("<hHH", 1234, 6500, 10142)
    entries, ref_after, end = parse_entries(b64(rec_ref + rec), s.fingerprint, 0)
    assert not end and ref_after == ref and len(entries) == 2 and entries[0].values == {}
    e = entries[1]
    assert e.number == 2 and e.time == EPOCH_2001 + ref + 600 and e.temperature == 12.34
    assert e.value("humidity") == 65.0 and e.value("pressure") == 1014.2
    assert parse_entries(b64(b"\x00"), s.fingerprint, ref) == ([], ref, True)


def test_homebridge_lib_layout_and_negative_temperature():
    # homebridge-lib: fingerprint of up to seven data points, entries with only some values present
    fp = [(0x01, 2), (0x02, 2), (0x03, 2)]
    ref = 820000000
    status = struct.pack("<III", 1200, 0, ref) + bytes([3]) + bytes(sum(fp, ())) \
        + struct.pack("<HHI", 2, 4032, 1) + bytes(4) + b"\x01\x01"
    s = parse_status(b64(status))
    assert s.fingerprint == fp and s.first == 1 and s.last == 2
    only_humidity = struct.pack("<BIIB", 12, 2, 600, 0b010) + struct.pack("<H", 5000)
    cold = struct.pack("<BIIB", 12, 3, 1200, 0b001) + struct.pack("<h", -725)
    entries, _, _ = parse_entries(b64(only_humidity + cold), fp, ref)
    assert [e.temperature for e in entries] == [None, -7.25]
    assert [e.value("humidity") for e in entries] == [50.0, None]


def test_implausible_values_are_left_out():
    # fakegato-history records 0 hPa for a weather accessory without a barometer
    rec = struct.pack("<BIIB", 16, 2, 600, 0b111) + struct.pack("<hHH", 2100, 4500, 0)
    e = parse_entries(b64(rec), WEATHER, 0)[0][0]
    assert (e.temperature, e.value("humidity"), e.value("pressure")) == (21.0, 45.0, None)


def test_unknown_layout_is_ignored():
    # fakegato "energy": bitmap 0x1f has more bits than the fingerprint knows – no temperature
    fp = [(0x01, 2), (0x02, 2), (0x07, 2), (0x0F, 3)]
    rec = struct.pack("<BIIB", 20, 2, 600, 0x1F) + bytes(10)
    entries, _, _ = parse_entries(b64(rec), fp, 0)
    assert entries[0].temperature is None
    with pytest.raises(HistoryError):
        parse_status(b64(b"\x00\x01"))


def test_fakegato_energy_entries_carry_the_power():
    # fakegato-history "energy": fingerprint 01 02 07 0F, but five two-byte values (bitmap 0x1F),
    # the third is the power in 1/10 W; temperature and humidity are always 0 and left out
    fp = [(0x01, 2), (0x02, 2), (0x07, 2), (0x0F, 3)]
    rec = bytes.fromhex("14") + struct.pack("<II", 2, 600) + b"\x1f" + struct.pack("<hHHHH", 0, 0, 12345, 0, 0)
    e = parse_entries(b64(rec), fp, 0)[0][0]
    assert e.value("power") == 1234.5 and e.temperature is None and e.value("humidity") is None
    now = int(time.time())
    sim = EveHistorySim(ENERGY, [(now - (6 - i) * 600, [w]) for i, w in enumerate([25, 25, 15000, 15000, 25, 25])])
    series = asyncio.run(DeviceHistory().update("plug", REFS, *sim_io(sim)))
    assert set(series) == {"power"} and [v for _, v in series["power"]] == [2.5, 2.5, 1500.0, 1500.0, 2.5, 2.5]


def test_energy_from_power():
    # 1000 W for one hour = 1 kWh; a gap of more than an hour counts as nothing
    pts = [(0, 1000.0), (1800, 1000.0), (3600, 1000.0), (3600 + 7200, 1000.0)]
    assert energy_kwh(pts, 0, 3600) == 1.0
    assert energy_kwh(pts, 0, 20000) == 1.0


def test_read_all_entries_of_a_wrapped_ring():
    start = int(time.time()) - 300 * 600
    sim = EveHistorySim(WEATHER, values(start, 300), memory=100)
    status, entries = asyncio.run(read_entries(REFS, *sim_io(sim)))
    assert len(entries) == 100 and entries[-1].temperature == 22.99
    assert entries[-1].time == start + 299 * 600
    assert sim.reads == 10                              # 11 entries per read, no request again


def test_skipped_entries_are_requested_again():
    sim = EveHistorySim(WEATHER, values(int(time.time()) - 50 * 600, 50))
    read, write = sim_io(sim)
    stolen = []

    async def read_with_poll(ref):
        if ref == "entries" and sim.reads == 1 and not stolen:
            stolen.append(sim.read_entries())           # a poll of /accessories in between
        return await read(ref)
    _, entries = asyncio.run(read_entries(REFS, read_with_poll, write))
    assert [e.number for e in entries] == list(range(1, 52))      # with the reference time record


def test_cache_reads_only_new_entries_and_restarts_after_a_reset(tmp_path):
    now = int(time.time())
    sim = EveHistorySim(THERMO, [(now - (20 - i) * 600, [2000 + i, 2100, 40, 0, 0]) for i in range(20)])
    path = tmp_path / "history.json"
    hist = DeviceHistory(path)
    pts = asyncio.run(hist.update("d", REFS, *sim_io(sim)))["temperature"]
    assert len(pts) == 20 and pts[-1][1] == 20.19
    reads = sim.reads
    sim.add(now, [2500, 2100, 40, 0, 0])
    pts = asyncio.run(DeviceHistory(path).update("d", REFS, *sim_io(sim)))["temperature"]   # from the file
    assert len(pts) == 21 and pts[-1] == (now, 25.0) and sim.reads - reads == 1     # one new entry
    fresh = EveHistorySim(THERMO, [(now, [1800, 2100, 40, 0, 0])])                 # device memory cleared
    assert asyncio.run(hist.update("d", REFS, *sim_io(fresh))) == {"temperature": [(now, 18.0)]}


def test_weather_series_and_cache_of_an_older_version(tmp_path):
    now = int(time.time())
    sim = EveHistorySim(WEATHER, [(now - (10 - i) * 600, [2000 + i, 6000 - i * 100, 10130 + i]) for i in range(10)])
    path = tmp_path / "history.json"
    # cache written by the previous version: temperatures only, some older than the device memory
    old = [[now - 20 * 600, 15.0], [now - 15 * 600, 16.0], [now - 5 * 600, 99.0]]
    path.write_text(json.dumps({"d": {"ref": parse_status(sim.status()).ref_time, "last": sim.last, "points": old}}))
    series = asyncio.run(DeviceHistory(path).update("d", REFS, *sim_io(sim)))
    assert series["humidity"][-1][1] == 51.0 and series["pressure"][-1][1] == 1013.9 and len(series["pressure"]) == 10
    temps = series["temperature"]
    assert temps[:2] == [(now - 20 * 600, 15.0), (now - 15 * 600, 16.0)]     # older ones kept …
    assert len(temps) == 12 and (now - 5 * 600, 99.0) not in temps          # … the rest read again
    assert "series" in json.loads(path.read_text())["d"]


def test_bucket():
    pts = [(t, float(t % 7)) for t in range(0, 1000)]
    assert bucket(pts, 900, 1000) == [p for p in pts if p[0] >= 900]
    b = bucket(pts, 0, 1000, n=10)
    assert len(b) == 10 and all(0 <= v <= 6 for _, v in b)


def test_hap_history_service_goes_to_the_temperature_device():
    eve = "-079E-48FF-8F27-9C2605A29F52"
    data = {"accessories": [{"aid": 2, "services": [
        {"iid": 1, "type": "3E", "characteristics": [{"iid": 2, "type": "23", "value": "Garden"}]},
        {"iid": 10, "type": "8A", "characteristics": [{"iid": 11, "type": "11", "value": 6.5, "perms": ["pr"]}]},
        {"iid": 20, "type": "82", "characteristics": [{"iid": 21, "type": "10", "value": 80, "perms": ["pr"]}]},
        {"iid": 30, "type": "E863F007" + eve, "characteristics": [
            {"iid": 31, "type": "E863F116" + eve}, {"iid": 32, "type": "E863F117" + eve},
            {"iid": 33, "type": "E863F11C" + eve}, {"iid": 34, "type": "E863F121" + eve}]}]},
        {"aid": 3, "services": [{"iid": 10, "type": "49", "characteristics": [
            {"iid": 11, "type": "25", "value": True, "perms": ["pr", "pw"]}]}]}]}
    snaps = HapBackend.parse_accessories(data)
    sensor = next(s for s in snaps if "CurrentTemperature" in s.chars)
    assert sensor.history == {"status": (2, 31), "entries": (2, 32), "request": (2, 33)}
    assert all(s.history is None for s in snaps if s is not sensor)
    assert request(2) == b64(b"\x01\x14\x02\x00\x00\x00" + bytes(14))
