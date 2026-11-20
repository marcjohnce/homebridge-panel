"""Reads the history that Eve-compatible accessories keep (Eve "History" service).

Plugins built on fakegato-history or homebridge-lib add this service to their accessories; the
Eve app uses it to show charts. The protocol (reverse engineered, see those libraries):

* History Status (E863F116, read): little endian –
  0: seconds since the reference time of the last entry (u32), 4: 0 (u32),
  8: reference time in seconds since 2001-01-01 (u32), 12: n, then n × (tag, length) –
  the "fingerprint" of the values an entry can hold – then the number of entries (u16), the memory
  size (u16) and the number of the first entry (u32).
* History Request (E863F11C, write): bytes 2–5 = number of the first entry to send (u32).
* History Entries (E863F117, read): every read returns the next records (up to 11), a single 00
  byte when there are no more. Record: length (u8, including itself), entry number (u32),
  seconds since the reference time (u32), bitmap (u8) and the values whose bit is set, in the
  order of the fingerprint. Bitmap 0x81 is a reference time record (reference time at offset 10).

Used are the temperature (tag 0x01, signed, 1/100 °C), the relative humidity (tag 0x02,
1/100 %) and the air pressure (tag 0x03, 1/10 hPa).
"""
from __future__ import annotations

import base64
import json
import logging
import struct
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

EPOCH_2001 = 978307200          # 2001-01-01 00:00:00 UTC in Unix time
TAG_TEMPERATURE = 0x01
TAG_HUMIDITY = 0x02
TAG_PRESSURE = 0x03
# quantity -> (tag, struct format, divisor, plausible range); values outside the range are
# left out, e.g. the 0 hPa that fakegato-history records for a weather device without a barometer
QUANTITIES = {
    "temperature": (TAG_TEMPERATURE, "<h", 100, (-60.0, 100.0)),
    "humidity": (TAG_HUMIDITY, "<H", 100, (0.0, 100.0)),
    "pressure": (TAG_PRESSURE, "<H", 10, (300.0, 1200.0)),
}
REF_TIME = 0x81
MAX_READS = 1000                # 11 entries per read: enough for the usual 4032 entries


class HistoryError(Exception):
    pass


@dataclass
class Status:
    ref_time: int                       # seconds since 2001-01-01
    fingerprint: list[tuple[int, int]]  # (tag, length) of the values an entry can hold
    count: int
    memory: int
    first: int

    @property
    def last(self) -> int:
        return self.first + self.count - 1


@dataclass
class Entry:
    number: int
    time: float                         # Unix time
    values: dict[int, bytes] = field(default_factory=dict)

    def value(self, quantity: str) -> float | None:
        tag, fmt, divisor, (lo, hi) = QUANTITIES[quantity]
        raw = self.values.get(tag)
        if not raw or len(raw) < 2:
            return None
        v = struct.unpack(fmt, raw[:2])[0] / divisor
        return v if lo <= v <= hi else None

    @property
    def temperature(self) -> float | None:
        return self.value("temperature")


def _b64(value: Any) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    try:
        return base64.b64decode(str(value or ""))
    except ValueError as e:
        raise HistoryError(f"invalid history data: {e}") from e


def parse_status(value: Any) -> Status:
    b = _b64(value)
    if len(b) < 13:
        raise HistoryError("history status too short")
    n = b[12]
    pos = 13 + 2 * n
    if len(b) < pos + 8:
        raise HistoryError("history status too short")
    fingerprint = [(b[13 + 2 * i], b[14 + 2 * i]) for i in range(n)]
    ref_time = struct.unpack_from("<I", b, 8)[0]
    count, memory, first = struct.unpack_from("<HHI", b, pos)
    return Status(ref_time, fingerprint, count, memory, first)


def parse_entries(value: Any, fingerprint: list[tuple[int, int]], ref_time: int) -> tuple[list[Entry], int, bool]:
    """Returns (entries, reference time after them, end reached)."""
    b = _b64(value)
    if len(b) <= 1:
        return [], ref_time, True
    out: list[Entry] = []
    pos = 0
    while pos < len(b):
        size = b[pos]
        if size < 10 or pos + size > len(b):
            break                                       # garbage or a cut record
        rec = b[pos:pos + size]
        pos += size
        number, offset = struct.unpack_from("<II", rec, 1)
        bitmap = rec[9]
        if bitmap == REF_TIME:
            if len(rec) >= 14:
                ref_time = struct.unpack_from("<I", rec, 10)[0]
            out.append(Entry(number, EPOCH_2001 + ref_time))      # no values; counts for the sequence
            continue
        if bitmap >> len(fingerprint):                 # bits the fingerprint does not describe
            out.append(Entry(number, EPOCH_2001 + ref_time + offset))
            continue
        values: dict[int, bytes] = {}
        p = 10
        for i, (tag, length) in enumerate(fingerprint):
            if bitmap & (1 << i):
                values[tag] = rec[p:p + length]
                p += length
        if p > len(rec):                                # values longer than the record: unknown layout
            values = {}
        out.append(Entry(number, EPOCH_2001 + ref_time + offset, values))
    return out, ref_time, False


def request(entry: int) -> str:
    """Value for History Request: send the entries from this number on."""
    return base64.b64encode(b"\x01\x14" + struct.pack("<I", entry) + bytes(14)).decode()


Read = Callable[[Any], Awaitable[Any]]
Write = Callable[[Any, Any], Awaitable[None]]


async def read_entries(refs: dict[str, Any], read: Read, write: Write, start: int = 0) -> tuple[Status, list[Entry]]:
    """Reads the entries from `start` on (the whole memory with 0). `refs` holds the characteristic
    references "status", "entries" and "request" of the History service."""
    status = parse_status(await read(refs["status"]))
    first = max(start, status.first, 1)
    if status.count <= 0 or first > status.last:
        return status, []
    await write(refs["request"], request(first))
    ref_time = status.ref_time
    entries: dict[int, Entry] = {}
    expected = first
    retried = False
    for _ in range(MAX_READS):
        batch, ref_time, end = parse_entries(await read(refs["entries"]), status.fingerprint, ref_time)
        if end:
            break
        for e in batch:
            entries[e.number] = e
        numbers = [e.number for e in batch]
        if numbers and numbers[0] > expected and not retried:
            # entries were skipped (someone else read them): ask again from the first missing one
            retried = True
            await write(refs["request"], request(expected))
            continue
        if numbers:
            expected = max(expected, numbers[-1] + 1)
        if expected > status.last:
            break
    else:
        log.warning("History: stopped after %d reads", MAX_READS)
    return status, [entries[n] for n in sorted(entries)]


Series = dict[str, list[tuple[float, float]]]     # quantity -> [(Unix time, value)], oldest first


class DeviceHistory:
    """History per device (temperature, humidity, air pressure), read incrementally and kept in
    a JSON file: {device: {"ref": …, "last": entry number, "series": {quantity: [[t, v], …]}}}."""

    KEEP = 40 * 86400       # seconds

    def __init__(self, path: Path | None = None):
        self.path = path
        self.data: dict[str, dict[str, Any]] = {}
        if path and path.exists():
            try:
                self.data = json.loads(path.read_text())
            except (OSError, ValueError):
                log.warning("History cache %s unreadable, starting empty", path)

    def _save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, separators=(",", ":")))
            tmp.replace(self.path)
        except OSError as e:
            log.warning("History cache not saved: %s", e)

    async def update(self, dev_id: str, refs: dict[str, Any], read: Read, write: Write) -> Series:
        """Reads the new entries of a device and returns all its series, oldest point first."""
        cached = self.data.get(dev_id, {})
        status = parse_status(await read(refs["status"]))
        fresh = (cached.get("ref") != status.ref_time or cached.get("last", 0) > status.last)
        # cache of an older version: temperatures only. Read the device memory again for the other
        # quantities and keep the older temperatures the device no longer has.
        migrate = not fresh and "series" not in cached
        start = 0 if fresh or migrate else cached.get("last", 0) + 1
        status, entries = await read_entries(refs, read, write, start)
        if fresh:
            old: Series = {}
        elif migrate:
            old = {"temperature": [tuple(p) for p in cached.get("points", [])]}
        else:
            old = {q: [tuple(p) for p in pts] for q, pts in cached.get("series", {}).items()}
        first_new = min((e.time for e in entries if e.values), default=None)
        cutoff = time.time() - self.KEEP
        series: Series = {}
        for q in QUANTITIES:
            pts = [p for p in old.get(q, []) if first_new is None or p[0] < first_new]
            pts += [(round(e.time), v) for e in entries if (v := e.value(q)) is not None]
            pts = [p for p in pts if p[0] >= cutoff]
            if pts:
                series[q] = pts
        last = max([0 if fresh else cached.get("last", 0)] + [e.number for e in entries])
        self.data[dev_id] = {"ref": status.ref_time, "last": last, "series": series}
        self._save()
        return series


def bucket(points: list[tuple[float, float]], since: float, until: float, n: int = 240) -> list[tuple[float, float]]:
    """Averages the points between `since` and `until` into at most n buckets (for the chart)."""
    sel = [p for p in points if since <= p[0] <= until]
    if len(sel) <= n:
        return sel
    width = (until - since) / n
    sums: dict[int, list[float]] = {}
    for t, v in sel:
        acc = sums.setdefault(min(n - 1, int((t - since) / width)), [0.0, 0.0, 0])
        acc[0] += t
        acc[1] += v
        acc[2] += 1
    return [(s[0] / s[2], round(s[1] / s[2], 2)) for _, s in sorted(sums.items())]
