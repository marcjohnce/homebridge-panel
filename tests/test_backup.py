"""Backups of the panel settings."""
import json

import pytest

from app.backup import BackupError, Backups
from app.settings import SettingsStore


def test_create_list_restore_delete(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.rooms = {"order": ["Kitchen", "Hall"], "devices": {"a": "Garden"}, "favorites": ["a", "b"]}
    store.groups = [{"id": "g1"}]
    store.update({"theme": "dark"})
    b = Backups(store.path, "0.0.4")
    assert b.list() == []
    name = b.create()
    assert name.startswith("backup-") and (tmp_path / "backups" / name).exists()
    [entry] = b.list()
    assert (entry["name"], entry["version"], entry["rooms"], entry["favorites"], entry["groups"]) == \
        (name, "0.0.4", 3, 2, 1)

    store.update({"theme": "light"})
    store.rooms = {}
    store.save()
    b.restore(name)
    again = SettingsStore(tmp_path / "settings.json")
    assert again.get("theme") == "dark" and again.rooms["favorites"] == ["a", "b"] and again.groups == [{"id": "g1"}]

    second = b.create()                     # same second: gets its own name, newest first
    assert [e["name"] for e in b.list()] == [second, name]
    b.delete(name)
    assert [e["name"] for e in b.list()] == [second]


def test_rejects_foreign_names_and_files(tmp_path):
    b = Backups(tmp_path / "settings.json")
    for bad in ("../settings.json", "/etc/passwd", "backup-x.json"):
        with pytest.raises(BackupError):
            b.restore(bad)
    (tmp_path / "backups").mkdir()
    (tmp_path / "backups" / "backup-20261120-180000.json").write_text(json.dumps({"theme": "dark"}))
    assert b.list() == []                   # not a backup of the panel: not listed
    with pytest.raises(BackupError, match="not a backup"):
        b.restore("backup-20261120-180000.json")
    assert not (tmp_path / "settings.json").exists()      # nothing overwritten


def test_backup_without_settings_file(tmp_path):
    b = Backups(tmp_path / "settings.json")
    name = b.create()
    assert b.list()[0]["rooms"] == 0
    b.restore(name)
    assert json.loads((tmp_path / "settings.json").read_text()) == {}
