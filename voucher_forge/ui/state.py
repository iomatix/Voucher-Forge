"""Application state and reactive i18n manager for NiceGUI UI layer."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from voucher_forge.models import TemplateConfig
from voucher_forge.storage import StorageRepository

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


class AppState:
    def __init__(self, storage: StorageRepository) -> None:
        self.storage = storage
        self.locales: dict[str, dict[str, str]] = self._load_locales()
        self.current_lang: str = "en"

        templates = self.storage.list_templates()
        self.active_template: TemplateConfig = templates[0]

        # Callbacks registered by views to re-render texts on language change
        self._lang_change_listeners: list[Callable[[], None]] = []

    def _load_locales(self) -> dict[str, dict[str, str]]:
        translations: dict[str, dict[str, str]] = {}
        for file_path in LOCALES_DIR.glob("*.json"):
            lang = file_path.stem
            with open(file_path, "r", encoding="utf-8") as f:
                translations[lang] = json.load(f)
        return translations

    def t(self, key: str) -> str:
        """Translates a key into current active language with fallback to English."""
        lang_dict = self.locales.get(self.current_lang, self.locales.get("en", {}))
        return lang_dict.get(key, key)

    def set_language(self, lang_code: str) -> None:
        if lang_code in self.locales and lang_code != self.current_lang:
            self.current_lang = lang_code
            for callback in self._lang_change_listeners:
                callback()

    def register_lang_listener(self, callback: Callable[[], None]) -> None:
        self._lang_change_listeners.append(callback)