from app.models import guess_appliance
from app.openings import OpeningLog, is_open, loggable


def test_opening_log(tmp_path):
    log = OpeningLog(tmp_path / "openings.json")
    assert log.note("w", True, now=1000) and not log.note("w", True, now=1100)
    assert log.note("w", False, now=1600) and log.note("w", True, now=5000)
    assert log.events("w") == [[5000, None], [1000, 1600]]
    assert OpeningLog(tmp_path / "openings.json").events("w") == log.events("w")     # saved
    log.note("w", False, now=5000 + 31 * 86400)      # older than 30 days: gone
    assert log.events("w") == [[5000, 5000 + 31 * 86400]]
    assert loggable({"type": "security", "meta": {"security": "contact"}})
    assert not loggable({"type": "security", "meta": {"security": "smoke"}})
    assert loggable({"type": "blind", "meta": {"opening": "window"}}) and not loggable({"type": "blind", "meta": {}})
    assert is_open({"type": "blind", "state": {"position": 5}}) and not is_open({"type": "garage", "state": {}})


def test_guess_appliance():
    assert guess_appliance("Prusa MK4") == "printer3d"
    assert guess_appliance("3D-Drucker Keller") == "printer3d"
    assert guess_appliance("PC Arbeitszimmer") == "computer"
    assert guess_appliance("NAS") == "computer"
    assert guess_appliance("Kalender Licht") is None          # "ender" only as a word
    assert guess_appliance("Stehlampe") is None
