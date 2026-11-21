from app.scenes import as_state, capture, clean, in_scenes


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
    assert in_scenes(light()) and not in_scenes({"type": "thermostat"})
    assert not in_scenes({"type": "light", "meta": {"group": True}})
    assert not in_scenes({"type": "blind", "meta": {"opening": "window"}})
    assert clean([{"id": "s1", "name": "A", "room": "R", "devices": {"x": {"on": True}, "y": 3}}, "junk", {}]) == \
        [{"id": "s1", "name": "A", "room": "R", "devices": {"x": {"on": True}}}]
    assert clean(None) == []
