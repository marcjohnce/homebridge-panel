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


def test_backlight_bl_power(tmp_path):
    bl = backlight(tmp_path)
    dp = DisplayPower(tmp_path, env={}, run=lambda cmd: 1)
    assert dp.set(False) and dp.method == "backlight" and (bl / "bl_power").read_text() == "4"
    assert dp.set(True) and (bl / "bl_power").read_text() == "0" and dp.is_on


def test_backlight_without_bl_power_keeps_the_brightness(tmp_path):
    bl = backlight(tmp_path, bl_power=False, brightness="123")
    (bl / "bl_power").mkdir()                      # not writable as a file
    dp = DisplayPower(tmp_path, env={}, run=lambda cmd: 1)
    assert dp.set(False) and (bl / "brightness").read_text() == "0"
    assert dp.set(True) and (bl / "brightness").read_text() == "123"


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
