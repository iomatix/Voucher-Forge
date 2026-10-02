"""Tests for i18n locale files consistency and automatic missing key repair."""

import json
import os
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).resolve().parent.parent / "voucher_forge" / "locales"
EN_PATH = LOCALES_DIR / "en.json"
PL_PATH = LOCALES_DIR / "pl.json"


def _load_json(file_path: Path) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(file_path: Path, data: dict[str, Any]) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def synchronize_keys(
    source: dict[str, Any], target: dict[str, Any], target_lang: str
) -> tuple[dict[str, Any], list[str]]:
    """Mirrors missing keys from source to target, marking values with TODO tags."""
    updated_target = dict(target)
    missing_keys: list[str] = []

    for key, val in source.items():
        if key not in updated_target:
            updated_target[key] = f"[TODO: missing {target_lang} translation] {val}"
            missing_keys.append(key)

    return updated_target, missing_keys


def test_i18n_locales_exist() -> None:
    assert EN_PATH.is_file(), f"Missing English locale at {EN_PATH}"
    assert PL_PATH.is_file(), f"Missing Polish locale at {PL_PATH}"


def test_i18n_keys_parity_and_autofix() -> None:
    en_dict = _load_json(EN_PATH)
    pl_dict = _load_json(PL_PATH)

    en_keys = set(en_dict.keys())
    pl_keys = set(pl_dict.keys())

    missing_in_pl = en_keys - pl_keys
    missing_in_en = pl_keys - en_keys

    # Tryb samonaprawiania przy zmiennej środowiskowej AUTOFIX_I18N=1
    should_autofix = os.getenv("AUTOFIX_I18N", "0") == "1"

    if should_autofix and (missing_in_pl or missing_in_en):
        if missing_in_pl:
            fixed_pl, _ = synchronize_keys(en_dict, pl_dict, "pl")
            _save_json(PL_PATH, fixed_pl)
        if missing_in_en:
            fixed_en, _ = synchronize_keys(pl_dict, en_dict, "en")
            _save_json(EN_PATH, fixed_en)

        # Przeładuj do weryfikacji
        en_dict = _load_json(EN_PATH)
        pl_dict = _load_json(PL_PATH)
        missing_in_pl = set(en_dict.keys()) - set(pl_dict.keys())
        missing_in_en = set(pl_dict.keys()) - set(en_dict.keys())

    assert not missing_in_pl, (
        f"Missing keys in pl.json: {sorted(missing_in_pl)}. "
        f"Run with AUTOFIX_I18N=1 to mirror keys with TODO placeholders."
    )
    assert not missing_in_en, (
        f"Missing keys in en.json: {sorted(missing_in_en)}. "
        f"Run with AUTOFIX_I18N=1 to mirror keys with TODO placeholders."
    )


def test_i18n_no_empty_values() -> None:
    en_dict = _load_json(EN_PATH)
    pl_dict = _load_json(PL_PATH)

    for k, v in en_dict.items():
        assert isinstance(v, str) and v.strip() != "", f"Empty value for key '{k}' in en.json"

    for k, v in pl_dict.items():
        assert isinstance(v, str) and v.strip() != "", f"Empty value for key '{k}' in pl.json"