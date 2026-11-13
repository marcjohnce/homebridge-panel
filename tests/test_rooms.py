"""Room layout edited on the panel (app/rooms.py)."""
from app.rooms import RoomLayout


def devices():
    # device id -> current room
    return {"lamp": "Living Room", "tv": "Living Room", "fan": "General", "coffee": "Kitchen"}


BASE = {"lamp": "Living Room", "tv": "Living Room", "fan": "General", "coffee": "Kitchen"}


def test_order_and_unknown_rooms_alphabetical():
    lay = RoomLayout({"order": ["Kitchen"]})
    assert lay.sort({"Living Room", "General", "Kitchen"}) == ["Kitchen", "General", "Living Room"]


def test_add_validates_names():
    lay = RoomLayout()
    assert lay.add("  Office  ", devices()) == ("Office", None)
    assert lay.all_rooms(devices().values())[-1] == "Office"
    assert lay.add("office", devices())[1] and lay.add("", devices())[1] and lay.add("x" * 25, devices())[1]


def test_rename_moves_devices_and_keeps_position():
    lay = RoomLayout()
    _, err = lay.rename("Kitchen", "Küche", devices())
    assert err is None
    assert lay.room_of("coffee", "Kitchen") == "Küche"
    assert lay.order == ["General", "Küche", "Living Room"]
    assert lay.rename("Küche", "living room", {**devices(), "coffee": "Küche"})[1]   # name taken


def test_assign_back_to_config_room_removes_override():
    lay = RoomLayout()
    assert lay.set_room("lamp", "Kitchen", "Living Room", devices()) is None
    assert lay.assign == {"lamp": "Kitchen"}
    assert lay.set_room("lamp", "Living Room", "Living Room", devices()) is None
    assert lay.assign == {}
    assert lay.set_room("lamp", "Nowhere", "Living Room", devices())


def test_delete_moves_devices_to_default_room():
    lay = RoomLayout()
    assert lay.delete("Living Room", devices(), BASE) is None
    assert lay.room_of("lamp", "Living Room") == "General" and lay.room_of("tv", "Living Room") == "General"
    assert "Living Room" not in lay.order
    assert lay.delete("General", devices(), BASE)       # default room still has devices


def test_move_and_roundtrip():
    lay = RoomLayout()
    lay.move("Living Room", -2, devices())
    assert lay.order == ["Living Room", "General", "Kitchen"]
    lay.move("Living Room", -1, devices())
    assert lay.order[0] == "Living Room"
    assert RoomLayout(lay.to_dict()).to_dict() == lay.to_dict()


def test_default_room_follows_language():
    name = ["General"]
    lay = RoomLayout(default_room=lambda: name[0])
    name[0] = "Allgemein"
    assert lay.room_of("fan", "General") == "Allgemein" and lay.room_of("lamp", "Hall") == "Hall"
