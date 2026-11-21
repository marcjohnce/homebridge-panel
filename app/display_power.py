"""Switches the display off and on (Settings → Display → Display off after).

Tried in this order, the first one that works is used:

1. Backlight in /sys/class/backlight (DSI displays such as the Raspberry Pi Touch Display or
   Waveshare DSI LCDs): brightness 0 and back to where it was. The panel stays powered, so the
   touchscreen still reports the touch that switches it on again. bl_power = 4 ("power down")
   is only used where the brightness cannot be written: on Waveshare DSI displays it also cuts
   the touch controller, and the display could only be woken by an alarm.
   Writing needs permission: deploy/install.sh adds a udev rule for the group "video".
2. Wayland (labwc, wayfire): `wlopm --off '*'` / `wlopm --on '*'`.
3. X11: `xset dpms force off` / `xset dpms force on`.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

BACKLIGHT_DIR = Path("/sys/class/backlight")


class DisplayPower:
    def __init__(self, backlight_dir: Path = BACKLIGHT_DIR, env: dict[str, str] | None = None,
                 run: Callable[[list[str]], int] | None = None, which: Callable[[str], str | None] = shutil.which):
        self.backlight_dir = Path(backlight_dir)
        self.env = os.environ if env is None else env
        self.run = run or self._run
        self.which = which
        self.is_on = True
        self._brightness: dict[Path, str] = {}       # brightness before switching off (fallback)
        self.method = ""                              # how it was switched last time (for the log)

    @staticmethod
    def _run(cmd: list[str]) -> int:
        try:
            return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode
        except (OSError, subprocess.TimeoutExpired):
            return 1

    def _backlights(self) -> list[Path]:
        try:
            return sorted(p for p in self.backlight_dir.iterdir() if (p / "brightness").exists())
        except OSError:
            return []

    def _set_backlight(self, on: bool) -> bool:
        done = False
        for bl in self._backlights():
            if on:
                # also undo a power down (bl_power 4) left by an earlier version of the panel
                try:
                    if (bl / "bl_power").read_text().strip() != "0":
                        (bl / "bl_power").write_text("0")
                        done = True
                except OSError:
                    pass
            try:                                       # brightness 0 and back: the touch keeps working
                if on:
                    saved = self._brightness.pop(bl, None) or (bl / "brightness").read_text().strip()
                    if saved == "0":                   # dark and nothing remembered: full brightness
                        saved = (bl / "max_brightness").read_text().strip()
                    (bl / "brightness").write_text(saved)
                else:
                    current = (bl / "brightness").read_text().strip()
                    if current != "0":
                        self._brightness[bl] = current
                    (bl / "brightness").write_text("0")
                done = True
                continue
            except OSError as e:
                log.debug("Backlight %s: brightness not writable: %s", bl, e)
            try:                                       # brightness read only: power the backlight down
                (bl / "bl_power").write_text("0" if on else "4")
                done = True
            except OSError as e:
                log.debug("Backlight %s not writable: %s", bl, e)
        return done

    def set(self, on: bool) -> bool:
        """Switches the display on or off; False if no way worked (nothing happened)."""
        if self._set_backlight(on):
            self.method = "backlight"
        elif self.env.get("WAYLAND_DISPLAY") and self.which("wlopm") \
                and self.run(["wlopm", "--on" if on else "--off", "*"]) == 0:
            self.method = "wlopm"
        elif self.env.get("DISPLAY") and self.which("xset") \
                and self.run(["xset", "dpms", "force", "on" if on else "off"]) == 0:
            self.method = "xset"
        else:
            log.warning("Display could not be switched %s: no writable backlight, wlopm or xset",
                        "on" if on else "off")
            return False
        self.is_on = on
        log.info("Display %s (%s)", "on" if on else "off", self.method)
        return True
