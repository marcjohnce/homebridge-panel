"""Touch sounds: a short click through the audio output (HDMI, headphone jack or a USB / I2S
amplifier) on every touch, played with aplay (alsa-utils). The click is made here, as a WAV
file in the temp folder, so the panel ships no sound files."""
from __future__ import annotations

import logging
import math
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path

log = logging.getLogger(__name__)
LEVELS = {"quiet": 0.12, "normal": 0.3, "loud": 0.7}      # amplitude of the click
RATE = 44100
MIN_GAP = 0.06          # seconds between two clicks; faster touches play one


def make_click(path: Path, amplitude: float) -> None:
    """Writes a 25 ms click: a 1.8 kHz tone that dies away quickly (16 bit mono)."""
    frames = bytearray()
    for i in range(int(RATE * 0.025)):
        t = i / RATE
        v = amplitude * math.sin(2 * math.pi * 1800 * t) * math.exp(-t * 220)
        frames += struct.pack("<h", int(v * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


class TouchSound:
    command = ["aplay", "-q"]       # overridable for tests

    def __init__(self, folder: Path | None = None):
        self.folder = folder or Path(tempfile.gettempdir()) / "smarthome-panel-sounds"
        self._proc: subprocess.Popen | None = None
        self._last = 0.0
        self._broken = False

    def file(self, level: str) -> Path:
        path = self.folder / f"click-{level}.wav"
        if not path.exists():
            self.folder.mkdir(parents=True, exist_ok=True)
            make_click(path, LEVELS[level])
        return path

    def play(self, level: str) -> bool:
        """Plays the click at this level ("off": nothing); True if it was started."""
        if level not in LEVELS or self._broken:
            return False
        now = time.monotonic()
        if now - self._last < MIN_GAP or (self._proc is not None and self._proc.poll() is None):
            return False
        self._last = now
        try:
            self._proc = subprocess.Popen([*self.command, str(self.file(level))],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:          # no aplay (alsa-utils) or no audio device
            log.warning("Touch sounds off: %s", e)
            self._broken = True
            return False
        return True
