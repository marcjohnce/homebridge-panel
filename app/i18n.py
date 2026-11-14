"""Languages: current language, translation of texts and number/date formats.

Texts are written in English in the code: `tr("...")` in Python, `qsTr("...")` in QML.
Translations live in `i18n_catalog.py`. Placeholders are `{name}` in Python and `%1` in QML.
Adding a language: add it to LANGUAGES and FORMATS and a column to every catalog entry
(or, like Portuguese, a separate dict merged in i18n_catalog.py)
(tests/test_i18n.py checks that nothing is missing).
"""
from __future__ import annotations

import os

from .i18n_catalog import CATALOG

# Language names in their own language (shown like this in the settings)
LANGUAGES = {"en": "English", "de": "Deutsch", "fr": "Français", "it": "Italiano", "es": "Español", "pt": "Português"}

# Qt locale, decimal point, thousands separator, date format (Qt date format)
FORMATS = {
    "en": ("en_GB", ".", ",", "dddd, d MMMM"),
    "de": ("de_DE", ",", ".", "dddd, d. MMMM"),
    "fr": ("fr_FR", ",", " ", "dddd d MMMM"),
    "it": ("it_IT", ",", ".", "dddd d MMMM"),
    "es": ("es_ES", ",", ".", "dddd, d 'de' MMMM"),
    "pt": ("pt_PT", ",", " ", "dddd, d 'de' MMMM"),
}

_language = "en"


def system_language() -> str:
    """Language of the operating system (LANGUAGE/LC_ALL/LC_MESSAGES/LANG), English if unsupported."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        for part in value.split(":"):
            code = part[:2].lower()
            if code in LANGUAGES:
                return code
    return "en"


def resolve(setting: str) -> str:
    """Setting value ("auto" or a language code) -> language code."""
    return system_language() if setting == "auto" or setting not in LANGUAGES else setting


def set_language(code: str) -> None:
    global _language
    _language = code if code in LANGUAGES else "en"


def language() -> str:
    return _language


def lookup(text: str) -> str:
    """Translation of `text` in the current language, or "" if there is none (English)."""
    if _language == "en":
        return ""
    return CATALOG.get(text, {}).get(_language, "")


def tr(text: str) -> str:
    """Translates an English text; use `.format(...)` afterwards for {placeholders}."""
    return lookup(text) or text


def decimal_point() -> str:
    return FORMATS[_language][1]


def fmt_number(value: float, decimals: int = 0, group: bool = True) -> str:
    """Number with the decimal point (and thousands separator if group) of the current language."""
    s = f"{value:,.{decimals}f}" if group else f"{value:.{decimals}f}"
    _, point, sep, _ = FORMATS[_language]
    return s.replace(",", "\x00").replace(".", point).replace("\x00", sep)


def locale_name() -> str:
    return FORMATS[_language][0]


def date_format() -> str:
    return FORMATS[_language][3]
