"""Feeds QML's qsTr() from the Python catalog (app/i18n_catalog.py) instead of .qm files."""
from __future__ import annotations

from PySide6.QtCore import QTranslator

from .. import i18n


class CatalogTranslator(QTranslator):
    def translate(self, context, source_text, disambiguation=None, n=-1):  # noqa: ANN001
        # PySide hands an empty string to Qt as an empty translation rather than "none",
        # so untranslated texts return the English source explicitly
        return i18n.lookup(source_text) or source_text

    def isEmpty(self) -> bool:
        return False
