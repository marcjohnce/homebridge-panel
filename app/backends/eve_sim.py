"""A simulated Eve history service that answers like fakegato-history (demo backend, tests)."""
from __future__ import annotations

import base64
import math
import struct
import time

from ..eve_history import EPOCH_2001, REF_TIME

# fingerprints as fakegato-history sends them: weather (temperature, humidity, pressure) and
# thermostat (temperature, target temperature, valve position, two unused one-byte values)
WEATHER = [(0x01, 2), (0x02, 2), (0x03, 2)]
THERMO = [(0x01, 2), (0x11, 2), (0x10, 1), (0x12, 1), (0x1D, 1)]


class EveHistorySim:
    def __init__(self, fingerprint: list[tuple[int, int]], values: list[tuple[float, list[int]]], memory: int = 4032):
        """values: (Unix time, raw values in the order of the fingerprint), oldest first. Only the
        newest `memory` entries are kept, like the ring buffer of a real device."""
        self.fingerprint = fingerprint
        self.memory = memory
        self.ref = int(values[0][0]) - EPOCH_2001 if values else int(time.time()) - EPOCH_2001
        # entry 1 is the reference time record, measurements start at 2
        self.entries = [(i + 2, t, v) for i, (t, v) in enumerate(values)]
        self.first = max(1, self.last - memory + 1)
        self.current = 0
        self.reads = 0

    @property
    def last(self) -> int:
        return len(self.entries) + 1

    def add(self, t: float, values: list[int]) -> None:
        self.entries.append((self.last + 1, t, values))
        self.first = max(1, self.last - self.memory + 1)

    def status(self) -> str:
        fp = bytes([len(self.fingerprint)]) + b"".join(bytes(x) for x in self.fingerprint)
        last_t = self.entries[-1][1] if self.entries else EPOCH_2001 + self.ref
        b = (struct.pack("<III", int(last_t) - EPOCH_2001 - self.ref, 0, self.ref) + fp
             + struct.pack("<HHI", self.last - self.first + 1, self.memory, self.first) + bytes(4) + b"\x01\x01")
        return base64.b64encode(b).decode()

    def request(self, value: str) -> None:
        self.current = max(self.first, struct.unpack_from("<I", base64.b64decode(value), 2)[0])

    def read_entries(self) -> str:
        self.reads += 1
        if not self.current or self.current > self.last:
            self.current = 0
            return base64.b64encode(b"\x00").decode()
        out = b""
        for _ in range(11):
            if self.current > self.last:
                break
            if self.current == 1:
                out += struct.pack("<BIIB", 21, 1, 1, REF_TIME) + struct.pack("<I", self.ref) + bytes(7)
            else:
                _, t, values = self.entries[self.current - 2]
                bitmap = (1 << len(values)) - 1
                data = b"".join(struct.pack(("<h" if tag == 0x01 else "<H") if length == 2 else "<b", v)
                                for (tag, length), v in zip(self.fingerprint, values))
                out += struct.pack("<BIIB", 10 + len(data), self.current, int(t) - EPOCH_2001 - self.ref, bitmap) + data
            self.current += 1
        return base64.b64encode(out).decode()


def demo_temperatures(now: float, base: float, swing: float, days: int = 30, step: int = 600) -> list[tuple[float, float]]:
    """A daily curve with some day-to-day drift, every 10 minutes for the last `days` days."""
    out = []
    t = now - days * 86400
    while t <= now:
        hours = (t % 86400) / 3600
        drift = 1.5 * math.sin(t / 86400 / 3.1) + 0.8 * math.sin(t / 86400 / 1.7)
        out.append((t, round(base + drift + swing * math.sin((hours - 9) / 24 * 2 * math.pi), 2)))
        t += step
    return out


def demo_pressure(t: float) -> float:
    """Air pressure in hPa drifting slowly over the days, like weather fronts passing."""
    days = t / 86400
    return round(1013 + 9 * math.sin(days / 2.3) + 4 * math.sin(days / 0.9), 1)
