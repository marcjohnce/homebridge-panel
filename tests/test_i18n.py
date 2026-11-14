"""Every user-visible text has German, French, Italian and Spanish translations."""
import re
from collections import Counter
from pathlib import Path

import pytest

from app import i18n, settings
from app.i18n_catalog import _ROWS, CATALOG, LANGS
from app.rooms import BUILTIN_DEFAULT

APP = Path(__file__).resolve().parent.parent / "app"
LITERAL = r'"((?:[^"\\]|\\.)*)"'


def unescape(s: str) -> str:
    return s.replace('\\"', '"').replace("\\\\", "\\")


def source_texts() -> set[str]:
    texts = {BUILTIN_DEFAULT}
    for p in (APP / "qml").rglob("*.qml"):
        texts |= {unescape(m) for m in re.findall(r"qsTr\(\s*" + LITERAL, p.read_text(encoding="utf-8"))}
    for p in APP.rglob("*.py"):
        if p.name != "i18n_catalog.py":
            texts |= {unescape(m) for m in re.findall(r"\btr\(\s*" + LITERAL, p.read_text(encoding="utf-8"))}
    from app.qt.controller import RoomsBridge     # labels translated with tr(variable)
    texts |= set(RoomsBridge.KIND_LABELS.values()) | set(RoomsBridge.AREA_LABELS.values()) - {""}
    for s in settings.SECTIONS:
        texts.add(s.title)
    for f in settings.FIELDS:
        texts |= {t for t in (f.label, f.help, f.button, f.confirm) if t}
        texts |= {label for value, label in f.options if not (f.key == "language" and value != "auto")}
    return texts


def needs_translation(text: str) -> bool:
    """Pure number/unit formats such as "{pct}%", "%1 K" or "{hpa} hPa" stay as they are."""
    words = re.sub(r"\{\w+\}|%\d", "", text)
    return bool(re.search(r"[A-Za-z]{2,}", words)) and words.strip() not in {"hPa", "lx"}


def placeholders(text: str) -> Counter:
    return Counter(re.findall(r"\{\w+\}|%\d", text))


def test_all_texts_are_translated():
    missing = sorted(t for t in source_texts() if needs_translation(t) and t not in CATALOG)
    assert not missing, "Missing in app/i18n_catalog.py:\n" + "\n".join(missing)


def test_no_unused_or_duplicate_entries():
    counts = Counter(row[0] for row in _ROWS)
    assert [t for t, n in counts.items() if n > 1] == []
    assert sorted(set(CATALOG) - source_texts()) == []


@pytest.mark.parametrize("lang", LANGS)
def test_translations_keep_placeholders(lang):
    for en, tr in CATALOG.items():
        assert tr[lang].strip(), (lang, en)
        assert placeholders(tr[lang]) == placeholders(en), (lang, en, tr[lang])


def test_languages_offered_in_settings():
    assert set(LANGS) | {"en"} == set(i18n.LANGUAGES)
    options = [v for v, _ in settings.FIELDS_BY_KEY["language"].options]
    assert options == ["auto", "en", "de", "fr", "it", "es", "pt"]


def test_lookup_and_formats():
    try:
        i18n.set_language("de")
        assert i18n.tr("Settings") == "Einstellungen"
        assert i18n.fmt_number(1234.5, 1) == "1.234,5"
        i18n.set_language("fr")
        assert i18n.tr("{n} rooms").format(n=3) == "3 pièces"
        i18n.set_language("en")
        assert i18n.tr("Settings") == "Settings" and i18n.lookup("Settings") == ""
    finally:
        i18n.set_language("en")
