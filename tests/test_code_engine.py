"""Unit tests verifying CodeEngine contracts, Luhn mod 31 algorithm, and bundle generation."""

from datetime import date

import pytest

from voucher_forge.code_engine import (
    ALPHABET,
    CodeEngine,
    InvalidCodeFormatError,
    _base31_to_int,
    _int_to_base31,
    compute_luhn_mod31_check_digit,
    verify_luhn_mod31,
)
from voucher_forge.models import VoucherStatus


def test_base31_conversion_roundtrip() -> None:
    for val in [0, 1, 30, 31, 500, 29790]:
        encoded = _int_to_base31(val, length=3)
        assert len(encoded) == 3
        decoded = _base31_to_int(encoded)
        assert decoded == val


def test_int_to_base31_overflow() -> None:
    with pytest.raises(ValueError, match="exceeds allocated length"):
        _int_to_base31(31**3 + 1, length=3)


def test_base31_to_int_invalid_char() -> None:
    with pytest.raises(InvalidCodeFormatError, match="not in valid alphabet"):
        _base31_to_int("0AB")


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


def test_generate_key_with_explicit_entropy_char() -> None:
    key = CodeEngine.generate_key(
        prefix="ABC",
        validity_months=6,
        target_date=date(2026, 1, 1),
        entropy_char="K",
    )
    assert key.startswith("ABC-222-06-K")
    assert CodeEngine.validate_key(key) is True


def test_generate_key_with_invalid_entropy_char() -> None:
    with pytest.raises(InvalidCodeFormatError, match="Invalid entropy char"):
        CodeEngine.generate_key(prefix="ABC", entropy_char="0")


def test_generate_key_earlier_than_epoch_raises_error() -> None:
    with pytest.raises(InvalidCodeFormatError, match="earlier than epoch"):
        CodeEngine.generate_key(prefix="ABC", target_date=date(2025, 12, 31))


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


def test_validate_key_structural_malformations() -> None:
    assert CodeEngine.validate_key("") is False
    assert CodeEngine.validate_key("ABC-222-12") is False
    assert CodeEngine.validate_key("A-222-12-AB") is False  # Prefix too short (< 2)
    assert CodeEngine.validate_key("TOOLONG-222-12-AB") is False  # Prefix too long (> 4)
    assert CodeEngine.validate_key("ABC-22-12-AB") is False  # ts_part len != 3
    assert CodeEngine.validate_key("ABC-222-1-AB") is False  # val_part len != 2
    assert CodeEngine.validate_key("ABC-222-12-A") is False  # tail len != 2
    assert CodeEngine.validate_key("ABC-222-XX-AB") is False  # val_part not numeric
    assert CodeEngine.validate_key("ABC-222-00-AB") is False  # val_part < 1
    assert CodeEngine.validate_key("ABC-222-12-A0") is False  # tail contains forbidden '0'


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


def test_decode_tampered_key_returns_invalid() -> None:
    key = CodeEngine.generate_key(
        prefix="GND", validity_months=24, target_date=date(2026, 8, 20)
    )
    tampered = key[:-1] + ("2" if key[-1] != "2" else "3")
    decoded = CodeEngine.decode_key(tampered)
    assert decoded["is_valid"] is False
    assert decoded["creation_date"] is None


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


def test_compute_luhn_mod31_invalid_char() -> None:
    with pytest.raises(InvalidCodeFormatError, match="Invalid character"):
        compute_luhn_mod31_check_digit("ABC#DEF")


def test_verify_luhn_mod31_empty_and_invalid_char() -> None:
    assert verify_luhn_mod31("") is False
    assert verify_luhn_mod31("ABC?12") is False


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


def test_bundle_allocation_bounds() -> None:
    with pytest.raises(ValueError, match="must be at least 1"):
        CodeEngine.generate_bundle(
            bundle_id="b_zero",
            bundle_name="Zero Test",
            template_id="tmpl_main",
            count=0,
            prefix="KPN",
        )

    with pytest.raises(ValueError, match="Max amount of vouchers per bundle is 31"):
        CodeEngine.generate_bundle(
            bundle_id="b_test_overflow",
            bundle_name="Overflow Test",
            template_id="tmpl_main",
            count=32,
            prefix="KPN",
        )


def test_campaign_bundle_generation() -> None:
    # Testing with custom text box target IDs: "tb_title" and "tb_sub"
    variants = [
        ("DINNER FOR TWO", "Includes starter & main", 3, None, None, None, "tb_title", "tb_sub"),
        ("MASSAGE SESSION", "60 minutes relax", 2, None, None, None, "tb_title", "tb_sub"),
        ("SPA PASS", "Full day access", 1, "bg.png", "logo.png", "#112233", "tb_title", "tb_sub"),
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

    last_voucher = bundle.vouchers[-1]
    assert last_voucher.bg_asset_override == "bg.png"
    assert last_voucher.logo_asset_override == "logo.png"
    assert last_voucher.bg_color_override == "#112233"


def test_campaign_bundle_bounds_errors() -> None:
    with pytest.raises(ValueError, match="must be at least 1"):
        CodeEngine.generate_campaign_bundle(
            bundle_id="b_empty",
            bundle_name="Empty",
            template_id="tmpl_main",
            variants=[],
            prefix="CMP",
        )

    variants_overflow = [("ITEM A", "Desc A", 20), ("ITEM B", "Desc B", 12)]
    with pytest.raises(ValueError, match="Max amount of vouchers per bundle is 31"):
        CodeEngine.generate_campaign_bundle(
            bundle_id="b_overflow",
            bundle_name="Overflow",
            template_id="tmpl_main",
            variants=variants_overflow,
            prefix="CMP",
        )