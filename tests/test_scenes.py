from app.scenes import as_state, capture, clean, in_scenes, matches


def light(**state):
    return {"id": "l", "type": "light", "capabilities": ["on", "brightness", "color", "color_temp"],
            "state": state, "meta": {}}


def test_capture_lights_switches_blinds():
    assert capture(light(on=False, brightness=40)) == {"on": False}
    # a pale colour is white: the white tone is kept
    assert capture(light(on=True, brightness=40, hue=30, saturation=4, color_temp=370)) == \
        {"on": True, "brightness": 40, "color_temp": 370}
    assert capture(light(on=True, brightness=80, hue=240.4, saturation=90, color_temp=153)) == \
        {"on": True, "brightness": 80, "hue": 240, "saturation": 90}
    plug = {"type": "plug", "capabilities": ["on"], "state": {"on": True, "power": 300}, "meta": {}}
    assert capture(plug) == {"on": True}
    blind = {"type": "blind", "capabilities": ["position", "tilt"], "meta": {},
             "state": {"position": 20, "target": 60, "tilt": 30}}
    assert capture(blind) == {"position": 60, "tilt": 30}
    assert as_state(plug, {"on": True})["state"] == {"on": True}        # not what it measures now
    assert as_state(blind, {"position": 0})["state"]["target"] == 0


def test_in_scenes_and_clean():
    assert in_scenes(light()) and in_scenes({"type": "thermostat"}) and not in_scenes({"type": "sensor"})
    assert not in_scenes({"type": "plug", "measureOnly": True})
    assert not in_scenes({"type": "light", "meta": {"group": True}})
    assert not in_scenes({"type": "blind", "meta": {"opening": "window"}})
    assert clean([{"id": "s1", "name": "A", "room": "R", "devices": {"x": {"on": True}, "y": 3}}, "junk", {}]) == \
        [{"id": "s1", "name": "A", "room": "R", "devices": {"x": {"on": True}}}]
    assert clean(None) == []


def test_thermostat_and_matches():
    heat = {"type": "thermostat", "reachable": True, "meta": {},
            "state": {"mode": "heat", "target_temp": 21.5, "current_temp": 19}}
    assert capture(heat) == {"mode": "heat", "target_temp": 21.5}
    assert capture({**heat, "state": {"mode": "off", "target_temp": 20}}) == {"mode": "off"}
    assert matches(heat, {"mode": "heat", "target_temp": 21.4})
    assert not matches(heat, {"mode": "heat", "target_temp": 20})
    lamp = {**light(on=True, brightness=41), "reachable": True}
    assert matches(lamp, {"on": True, "brightness": 40}) and not matches(lamp, {"on": False})
    assert matches({**light(on=False, brightness=80), "reachable": True}, {"on": False})
    assert not matches({**lamp, "reachable": False}, {"on": True, "brightness": 40})
    blind = {"type": "blind", "reachable": True, "meta": {}, "state": {"position": 10, "target": 60}}
    assert matches(blind, {"position": 60})            # moving there
