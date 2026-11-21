"""Display off and on: backlight, wlopm, xset."""
from app.display_power import DisplayPower


def backlight(tmp_path, name="10-0045", bl_power=True, brightness="200"):
    d = tmp_path / name
    d.mkdir(parents=True)
    (d / "brightness").write_text(brightness)
    (d / "max_brightness").write_text("255")
    if bl_power:
        (d / "bl_power").write_text("0")
    return d


def test_backlight_brightness_keeps_the_touch_powered(tmp_path):
    # brightness 0 and back – not bl_power 4, which also cuts the touch of Waveshare DSI displays
    bl = backlight(tmp_path, brightness="180")
    dp = DisplayPower(tmp_path, env={}, run=lambda cmd: 1)
    assert dp.set(False) and dp.method == "backlight"
    assert (bl / "brightness").read_text() == "0" and (bl / "bl_power").read_text() == "0"
    assert dp.set(False) and dp.set(True) and (bl / "brightness").read_text() == "180" and dp.is_on


def test_power_down_left_by_an_older_version_is_undone(tmp_path):
    bl = backlight(tmp_path, brightness="200")
    (bl / "bl_power").write_text("4")                # switched off by the previous version
    dp = DisplayPower(tmp_path, env={}, run=lambda cmd: 1)
    assert dp.set(True) and (bl / "bl_power").read_text() == "0" and (bl / "brightness").read_text() == "200"


def test_dark_at_start_comes_back_at_full_brightness(tmp_path):
    bl = backlight(tmp_path, brightness="0")         # e.g. the app stopped while it was off
    dp = DisplayPower(tmp_path, env={}, run=lambda cmd: 1)
    assert dp.set(False) and dp.set(True) and (bl / "brightness").read_text() == "255"


def test_read_only_brightness_uses_bl_power(tmp_path):
    bl = backlight(tmp_path)
    (bl / "brightness").unlink()
    (bl / "brightness").mkdir()                      # exists, but not writable as a file
    dp = DisplayPower(tmp_path, env={}, run=lambda cmd: 1)
    assert dp.set(False) and (bl / "bl_power").read_text() == "4"
    assert dp.set(True) and (bl / "bl_power").read_text() == "0"


def test_wayland_and_x11(tmp_path):
    calls = []

    def run(cmd):
        calls.append(cmd)
        return 0
    dp = DisplayPower(tmp_path / "none", env={"WAYLAND_DISPLAY": "wayland-0"}, run=run, which=lambda c: "/usr/bin/" + c)
    assert dp.set(False) and dp.method == "wlopm" and calls[-1] == ["wlopm", "--off", "*"]
    assert dp.set(True) and calls[-1] == ["wlopm", "--on", "*"]
    dp = DisplayPower(tmp_path / "none", env={"DISPLAY": ":0"}, run=run, which=lambda c: "/usr/bin/" + c)
    assert dp.set(False) and calls[-1] == ["xset", "dpms", "force", "off"]


def test_nothing_available(tmp_path):
    dp = DisplayPower(tmp_path / "none", env={}, run=lambda cmd: 0, which=lambda c: None)
    assert dp.set(False) is False and dp.is_on                 # stays on, nothing happened
