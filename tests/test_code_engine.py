"""Unit tests verifying CodeEngine contracts, Luhn mod 31 algorithm, and bundle generation."""

from datetime import date

import pytest

from voucher_forge.code_engine import (
    ALPHABET,
    CodeEngine,
    InvalidCodeFormatError,
)
from voucher_forge.models import VoucherStatus


def test_generate_and_validate_key() -> None:
    key = CodeEngine.generate_key(
        prefix="URK", validity_months=12, target_date=date(2026, 3, 15)
    )
    assert isinstance(key, str)
    parts = key.split("-")
    assert len(parts) == 4
    assert parts[0] == "URK"
    assert len(parts[1]) == 3
    assert parts[2] == "12"
    assert len(parts[3]) == 2
    assert CodeEngine.validate_key(key) is True


def test_single_typo_detection() -> None:
    key = CodeEngine.generate_key(
        prefix="VR", validity_months=6, target_date=date(2026, 6, 1)
    )
    assert CodeEngine.validate_key(key) is True

    parts = key.split("-")
    p0, p1, p2, p3 = parts

    for part_idx, part in enumerate([p0, p1, p3]):
        for char_idx in range(len(part)):
            orig_char = part[char_idx]
            alt_char = ALPHABET[(ALPHABET.index(orig_char) + 1) % len(ALPHABET)]

            mutated_part = part[:char_idx] + alt_char + part[char_idx + 1 :]
            new_parts = [p0, p1, p2, p3]
            actual_idx = 0 if part_idx == 0 else (1 if part_idx == 1 else 3)
            new_parts[actual_idx] = mutated_part

            mutated_key = "-".join(new_parts)
            assert (
                CodeEngine.validate_key(mutated_key) is False
            ), f"Failed to detect typo in part {actual_idx} at {char_idx}: {mutated_key}"


def test_adjacent_transposition_detection() -> None:
    key = CodeEngine.generate_key(
        prefix="DSC", validity_months=3, target_date=date(2026, 4, 10)
    )
    assert CodeEngine.validate_key(key) is True

    parts = key.split("-")
    raw = list(f"{parts[0]}{parts[1]}{parts[2]}{parts[3]}")

    for idx in range(len(raw) - 1):
        if raw[idx] == raw[idx + 1]:
            continue
        swapped = list(raw)
        swapped[idx], swapped[idx + 1] = swapped[idx + 1], swapped[idx]

        p0 = "".join(swapped[: len(parts[0])])
        offset = len(parts[0])
        p1 = "".join(swapped[offset : offset + 3])
        offset += 3
        p2 = "".join(swapped[offset : offset + 2])
        offset += 2
        p3 = "".join(swapped[offset : offset + 2])

        swapped_key = f"{p0}-{p1}-{p2}-{p3}"
        assert CodeEngine.validate_key(swapped_key) is False, f"Failed at swap {idx}<->{idx+1}"


def test_decode_key_attributes() -> None:
    test_date = date(2026, 8, 20)
    key = CodeEngine.generate_key(
        prefix="GND", validity_months=24, target_date=test_date
    )

    decoded = CodeEngine.decode_key(key)
    assert decoded["is_valid"] is True
    assert decoded["prefix"] == "GND"
    assert decoded["creation_date"] == test_date
    assert decoded["validity_months"] == 24


def test_decode_invalid_key() -> None:
    decoded = CodeEngine.decode_key("INVALID-KEY-FORMAT")
    assert decoded["is_valid"] is False
    assert decoded["creation_date"] is None
    assert decoded["validity_months"] is None


def test_prefix_boundary_and_validation() -> None:
    with pytest.raises(InvalidCodeFormatError):
        CodeEngine.generate_key(prefix="A")

    with pytest.raises(InvalidCodeFormatError):
        CodeEngine.generate_key(prefix="TOOLONG")

    with pytest.raises(InvalidCodeFormatError):
        CodeEngine.generate_key(prefix="U01")

    with pytest.raises(InvalidCodeFormatError):
        CodeEngine.generate_key(prefix="URO")


def test_validity_bounds() -> None:
    with pytest.raises(InvalidCodeFormatError):
        CodeEngine.generate_key(prefix="ABC", validity_months=0)

    with pytest.raises(InvalidCodeFormatError):
        CodeEngine.generate_key(prefix="ABC", validity_months=100)


def test_bundle_allocation_uniqueness() -> None:
    count = 31
    bundle = CodeEngine.generate_bundle(
        bundle_id="b_test_31",
        bundle_name="Scale Allocation Test",
        template_id="tmpl_main",
        count=count,
        prefix="KPN",
        validity_months=12,
        target_date=date(2026, 5, 1),
    )

    assert bundle.id == "b_test_31"
    assert len(bundle.vouchers) == count

    generated_codes = [v.code for v in bundle.vouchers]
    unique_codes = set(generated_codes)
    assert len(unique_codes) == count

    for v in bundle.vouchers:
        assert v.status == VoucherStatus.ACTIVE
        assert CodeEngine.validate_key(v.code) is True


def test_bundle_allocation_exceeds_entropy_limit() -> None:
    with pytest.raises(ValueError, match="Max amount of vouchers per bundle is 31"):
        CodeEngine.generate_bundle(
            bundle_id="b_test_overflow",
            bundle_name="Overflow Test",
            template_id="tmpl_main",
            count=32,
            prefix="KPN",
            validity_months=12,
            target_date=date(2026, 5, 1),
        )

def test_campaign_bundle_generation() -> None:
    variants = [
        ("DINNER FOR TWO", "Includes starter & main", 3),
        ("MASSAGE SESSION", "60 minutes relax", 2),
        ("SPA PASS", "Full day access", 1),
    ]
    bundle = CodeEngine.generate_campaign_bundle(
        bundle_id="b_campaign_test",
        bundle_name="Campaign Test",
        template_id="tmpl_dinner_voucher",
        variants=variants,
        prefix="CMP",
    )

    assert bundle.id == "b_campaign_test"
    assert len(bundle.vouchers) == 6

    titles = [v.text_overrides.get("tb_title") for v in bundle.vouchers]
    assert titles == [
        "DINNER FOR TWO",
        "DINNER FOR TWO",
        "DINNER FOR TWO",
        "MASSAGE SESSION",
        "MASSAGE SESSION",
        "SPA PASS",
    ]

    subs = [v.text_overrides.get("tb_sub") for v in bundle.vouchers]
    assert subs == [
        "Includes starter & main",
        "Includes starter & main",
        "Includes starter & main",
        "60 minutes relax",
        "60 minutes relax",
        "Full day access",
    ]


def test_campaign_bundle_overflow_raises_error() -> None:
    variants = [("ITEM A", "Desc A", 20), ("ITEM B", "Desc B", 12)]
    with pytest.raises(ValueError, match="Max amount of vouchers per bundle is 31"):
        CodeEngine.generate_campaign_bundle(
            bundle_id="b_overflow",
            bundle_name="Overflow",
            template_id="tmpl_main",
            variants=variants,
            prefix="CMP",
        )