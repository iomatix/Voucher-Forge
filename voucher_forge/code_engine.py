"""Deterministic CD-Key generation, verification, and decoding engine.

Uses custom 31-character unambiguous base alphabet and Luhn mod 31 algorithm.
Zero-UI coupling: standard Python library only.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

from voucher_forge.models import BundleRegistry, VoucherItem, VoucherStatus

# 31 unambiguous characters (excludes 0, O, 1, I, L)
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
BASE = len(ALPHABET)  # 31

BASE31_CHAR_TO_VAL = {ch: idx for idx, ch in enumerate(ALPHABET)}
VAL_TO_BASE31_CHAR = {idx: ch for idx, ch in enumerate(ALPHABET)}

# Extended map allowing decimal digits in VALIDITY block for checksum calculation
CHECKSUM_CHAR_TO_VAL = dict(BASE31_CHAR_TO_VAL)
CHECKSUM_CHAR_TO_VAL["0"] = 0
CHECKSUM_CHAR_TO_VAL["1"] = 1

EPOCH_DATE = date(2026, 1, 1)


class InvalidCodeFormatError(ValueError):
    """Raised when key structure or character set does not meet specification."""


def _int_to_base31(value: int, length: int) -> str:
    chars: list[str] = []
    current = value
    while current > 0:
        chars.append(VAL_TO_BASE31_CHAR[current % BASE])
        current //= BASE
    while len(chars) < length:
        chars.append(VAL_TO_BASE31_CHAR[0])
    if len(chars) > length:
        raise ValueError(f"Value {value} exceeds allocated length of {length} characters")
    return "".join(reversed(chars))


def _base31_to_int(encoded: str) -> int:
    val = 0
    for ch in encoded:
        if ch not in BASE31_CHAR_TO_VAL:
            raise InvalidCodeFormatError(f"Character '{ch}' not in valid alphabet")
        val = val * BASE + BASE31_CHAR_TO_VAL[ch]
    return val


def compute_luhn_mod31_check_digit(payload_raw: str) -> str:
    """Computes Luhn mod 31 check character for unhyphenated payload.

    Processes characters right-to-left with alternating weights 2 and 1.
    """
    total_sum = 0
    factor = 2

    for ch in reversed(payload_raw):
        if ch not in CHECKSUM_CHAR_TO_VAL:
            raise InvalidCodeFormatError(f"Invalid character '{ch}' in payload")
        code_point = CHECKSUM_CHAR_TO_VAL[ch]
        addend = factor * code_point
        factor = 1 if factor == 2 else 2
        addend = (addend // BASE) + (addend % BASE)
        total_sum += addend

    remainder = total_sum % BASE
    check_code_point = (BASE - remainder) % BASE
    return VAL_TO_BASE31_CHAR[check_code_point]


def verify_luhn_mod31(raw_key: str) -> bool:
    """Verifies Luhn mod 31 checksum of an unhyphenated string containing check character."""
    if not raw_key:
        return False
    total_sum = 0
    factor = 1

    for ch in reversed(raw_key):
        if ch not in CHECKSUM_CHAR_TO_VAL:
            return False
        code_point = CHECKSUM_CHAR_TO_VAL[ch]
        addend = factor * code_point
        factor = 2 if factor == 1 else 1
        addend = (addend // BASE) + (addend % BASE)
        total_sum += addend

    return (total_sum % BASE) == 0


class CodeEngine:
    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        clean = prefix.strip().upper()
        if not (2 <= len(clean) <= 4):
            raise InvalidCodeFormatError(f"Prefix length must be 2-4 characters, got '{prefix}'")
        for ch in clean:
            if ch not in BASE31_CHAR_TO_VAL:
                raise InvalidCodeFormatError(f"Prefix character '{ch}' not in allowed alphabet")
        return clean

    @staticmethod
    def _encode_timestamp(target_date: date) -> str:
        delta_days = (target_date - EPOCH_DATE).days
        if delta_days < 0:
            raise InvalidCodeFormatError(f"Date {target_date} is earlier than epoch {EPOCH_DATE}")
        return _int_to_base31(delta_days, 3)

    @staticmethod
    def _format_validity(validity_months: int) -> str:
        if not (1 <= validity_months <= 99):
            raise InvalidCodeFormatError("validity_months must be between 1 and 99")
        return f"{validity_months:02d}"

    @classmethod
    def generate_key(
        cls,
        prefix: str,
        validity_months: int = 99,
        target_date: date | None = None,
        entropy_char: str | None = None,
    ) -> str:
        clean_prefix = cls._normalize_prefix(prefix)
        date_effective = target_date if target_date is not None else date.today()
        ts_part = cls._encode_timestamp(date_effective)
        val_part = cls._format_validity(validity_months)

        if entropy_char is not None:
            if entropy_char not in BASE31_CHAR_TO_VAL:
                raise InvalidCodeFormatError(f"Invalid entropy char: '{entropy_char}'")
            ent_char = entropy_char
        else:
            ent_char = secrets.choice(ALPHABET)

        payload = f"{clean_prefix}{ts_part}{val_part}{ent_char}"
        check_char = compute_luhn_mod31_check_digit(payload)

        return f"{clean_prefix}-{ts_part}-{val_part}-{ent_char}{check_char}"

    @classmethod
    def validate_key(cls, key: str) -> bool:
        parts = key.strip().split("-")
        if len(parts) != 4:
            return False

        prefix, ts_part, val_part, tail = parts
        if not (2 <= len(prefix) <= 4):
            return False
        if len(ts_part) != 3 or len(val_part) != 2 or len(tail) != 2:
            return False

        for ch in f"{prefix}{ts_part}{tail}".upper():
            if ch not in BASE31_CHAR_TO_VAL:
                return False

        if not val_part.isdigit():
            return False
        val_int = int(val_part)
        if not (1 <= val_int <= 99):
            return False

        raw_str = f"{prefix}{ts_part}{val_part}{tail}".upper()
        return verify_luhn_mod31(raw_str)

    @classmethod
    def decode_key(cls, key: str) -> dict[str, Any]:
        parts = key.strip().split("-")
        if len(parts) != 4:
            return {
                "prefix": "",
                "creation_date": None,
                "validity_months": None,
                "is_valid": False,
            }

        prefix, ts_part, val_part, _ = parts
        is_valid = cls.validate_key(key)
        if not is_valid:
            return {
                "prefix": prefix,
                "creation_date": None,
                "validity_months": None,
                "is_valid": False,
            }

        days = _base31_to_int(ts_part)
        creation_date = EPOCH_DATE + timedelta(days=days)
        validity_months = int(val_part)

        return {
            "prefix": prefix,
            "creation_date": creation_date,
            "validity_months": validity_months,
            "is_valid": True,
        }

    @classmethod
    def generate_bundle(
        cls,
        bundle_id: str,
        bundle_name: str,
        template_id: str,
        count: int,
        prefix: str,
        validity_months: int = 99,
        target_date: date | None = None,
    ) -> BundleRegistry:
        if count < 1:
            raise ValueError("Amount of vouchers must be at least 1.")
        if count > len(ALPHABET):  # 31
            raise ValueError(
                f"Max amount of vouchers per bundle is {len(ALPHABET)}."
            )

        clean_prefix = cls._normalize_prefix(prefix)
        cls._format_validity(validity_months)
        date_effective = target_date if target_date is not None else date.today()
        ts_part = cls._encode_timestamp(date_effective)
        val_part = cls._format_validity(validity_months)

        created_at_iso = datetime.now(timezone.utc).isoformat()
        vouchers: list[VoucherItem] = []

        available_entropy = list(ALPHABET)
        secrets.SystemRandom().shuffle(available_entropy)

        for i in range(count):
            ent_ch = available_entropy[i]
            payload = f"{clean_prefix}{ts_part}{val_part}{ent_ch}"
            chk = compute_luhn_mod31_check_digit(payload)
            key = f"{clean_prefix}-{ts_part}-{val_part}-{ent_ch}{chk}"

            vouchers.append(
                VoucherItem(
                    code=key,
                    template_id=template_id,
                    status=VoucherStatus.ACTIVE,
                    created_at=created_at_iso,
                )
            )

        return BundleRegistry(
            id=bundle_id,
            name=bundle_name,
            code_prefix=clean_prefix,
            created_at=created_at_iso,
            vouchers=vouchers,
        )


    @classmethod
    def generate_campaign_bundle(
        cls,
        bundle_id: str,
        bundle_name: str,
        template_id: str,
        variants: list[tuple[str, str, int]],
        prefix: str,
        validity_months: int = 99,
        target_date: date | None = None,
    ) -> BundleRegistry:
        """Generates a bundle with multiple content variants (title + subtitle) sharing a base template."""
        total_count = sum(count for _, _, count in variants)
        if total_count < 1:
            raise ValueError("Amount of vouchers must be at least 1.")
        if total_count > len(ALPHABET):  # 31
            raise ValueError(
                f"Max amount of vouchers per bundle is {len(ALPHABET)}."
            )

        clean_prefix = cls._normalize_prefix(prefix)
        cls._format_validity(validity_months)
        date_effective = target_date if target_date is not None else date.today()
        ts_part = cls._encode_timestamp(date_effective)
        val_part = cls._format_validity(validity_months)

        created_at_iso = datetime.now(timezone.utc).isoformat()
        vouchers: list[VoucherItem] = []

        available_entropy = list(ALPHABET)
        secrets.SystemRandom().shuffle(available_entropy)

        voucher_idx = 0
        for variant_title, variant_sub, count in variants:
            for _ in range(count):
                ent_ch = available_entropy[voucher_idx]
                payload = f"{clean_prefix}{ts_part}{val_part}{ent_ch}"
                chk = compute_luhn_mod31_check_digit(payload)
                key = f"{clean_prefix}-{ts_part}-{val_part}-{ent_ch}{chk}"

                overrides: dict[str, str] = {}
                if variant_title:
                    overrides["tb_title"] = variant_title
                if variant_sub:
                    overrides["tb_sub"] = variant_sub

                vouchers.append(
                    VoucherItem(
                        code=key,
                        template_id=template_id,
                        status=VoucherStatus.ACTIVE,
                        created_at=created_at_iso,
                        text_overrides=overrides,
                    )
                )
                voucher_idx += 1

        return BundleRegistry(
            id=bundle_id,
            name=bundle_name,
            code_prefix=clean_prefix,
            created_at=created_at_iso,
            vouchers=vouchers,
        )
