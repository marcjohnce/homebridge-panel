import json

from app.config import AppConfig
from app.qt.format import short_name, state_text
from app.settings import FIELDS, SettingsStore, apply_to_config, validate


def test_validate_and_normalize():
    assert validate("hap_pin", "03145154") == ("031-45-154", None)
    assert validate("hap_pin", "031-45-15")[1]
    assert validate("hap_port", "51826") == (51826, None)
    assert validate("hap_port", 70000)[1] == "Erlaubt sind 1 bis 65535"
    assert validate("hap_port", "abc")[1]
    assert validate("hap_host", "192.168.1.20") == ("192.168.1.20", None)
    assert validate("hap_host", "homebridge.local") == ("homebridge.local", None)
    assert validate("hap_host", "192.168.1.300")[1]
    assert validate("hap_host", "")[1]
    assert validate("hap_host", "bad host")[1]
    assert validate("theme", "dark") == ("dark", None)
    assert validate("theme", "pink")[1]
    assert validate("idle_seconds", 120.0) == (120, None)   # Zahlen aus QML kommen als float
    assert validate("hap_enabled", False) == (False, None)
    assert validate("gibt-es-nicht", 1)[1]


def test_store_persists_and_rejects_invalid(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    s = SettingsStore(path)
    assert s.get("hap_port") == 51826
    assert s.update({"hap_port": 53000, "hap_pin": "11122333"}) == {}
    errors = s.update({"hap_port": 0, "theme": "dark"})
    assert set(errors) == {"hap_port"} and s.get("theme") == "auto"  # nichts übernommen
    data = json.loads(path.read_text())
    assert data["hap_port"] == 53000 and data["hap_pin"] == "111-22-333"
    assert SettingsStore(path).get("hap_pin") == "111-22-333"
    path.write_text('{"hap_port": "kaputt", "theme": "dark"}')
    s2 = SettingsStore(path)
    assert s2.get("hap_port") == 51826 and s2.get("theme") == "dark"


def test_schema_contains_all_fields(tmp_path):
    schema = SettingsStore(tmp_path / "s.json").schema()
    keys = [f["key"] for sec in schema for f in sec["fields"]]
    assert keys == [f.key for f in FIELDS]
    assert {sec["id"]: sec["instant"] for sec in schema} == {"display": True, "homebridge": False}


def test_apply_to_config():
    cfg = AppConfig.model_validate({"hap": [{"name": "homebridge", "host": "x", "port": 1, "pin": "000-00-000"},
                                            {"name": "child", "port": 2}]})
    vals = {"hap_enabled": True, "hap_host": "10.0.0.5", "hap_port": 51900, "hap_pin": "123-45-678"}
    eff = apply_to_config(cfg, vals)
    assert [(h.name, h.host, h.port) for h in eff.hap] == [("homebridge", "10.0.0.5", 51900), ("child", "127.0.0.1", 2)]
    assert cfg.hap[0].host == "x"  # Original unverändert
    assert [h.name for h in apply_to_config(cfg, {**vals, "hap_enabled": False}).hap] == ["child"]
    only_child = AppConfig.model_validate({"hap": [{"name": "child", "port": 2}]})
    assert [h.name for h in apply_to_config(only_child, vals).hap] == ["homebridge", "child"]


def test_tile_texts():
    assert short_name("Heizung Wohnzimmer", "Wohnzimmer") == "Heizung"
    assert short_name("Licht im Bad", "Bad") == "Licht"
    assert short_name("Wohnzimmer-Lampe", "Wohnzimmer") == "Lampe"
    assert short_name("Küchenlicht", "Küche") == "Küchenlicht"
    assert short_name("Bad", "Bad") == "Bad"
    th = {"type": "thermostat", "reachable": True, "state": {"mode": "heat", "heating": True, "current_temp": 19.64}}
    assert state_text(th) == "Heizt, ist 19,6 °C"
    assert state_text({**th, "state": {"mode": "off", "current_temp": 18}}) == "Aus, 18,0 °C"
    assert state_text({"type": "light", "reachable": True, "state": {"on": True, "brightness": 40}}) == "40 %"
    assert state_text({"type": "plug", "reachable": True, "state": {"on": True, "in_use": True}}) == "An, in Betrieb"
    assert state_text({"type": "plug", "reachable": False, "state": {}}) == "Nicht erreichbar"
