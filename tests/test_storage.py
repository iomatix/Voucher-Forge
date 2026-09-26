"""Unit tests verifying StorageRepository and schema versioning contracts."""

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from voucher_forge.models import (
    CURRENT_SCHEMA_VERSION,
    BackgroundConfig,
    BundleRegistry,
    CodeBoxConfig,
    LogoConfig,
    SchemaVersionMismatchError,
    TemplateConfig,
    TextBlockConfig,
    VoucherItem,
    VoucherStatus,
)
from voucher_forge.storage import (
    BundleNotFoundError,
    StorageRepository,
    TemplateNotFoundError,
)


@pytest.fixture
def temp_repo(tmp_path: Path) -> StorageRepository:
    return StorageRepository(base_dir=tmp_path / "data")


def create_sample_template(template_id: str = "tmpl-001") -> TemplateConfig:
    return TemplateConfig(
        id=template_id,
        name="Gift Voucher 100",
        width_mm=210.0,
        height_mm=99.0,
        background=BackgroundConfig(
            type="gradient",
            color_start="#0F172A",
            color_end="#1E293B",
            gradient_angle_deg=45.0,
        ),
        logo=LogoConfig(
            asset_filename="brand.png",
            x_mm=10.0,
            y_mm=10.0,
            width_mm=30.0,
            height_mm=15.0,
        ),
        text_blocks=[
            TextBlockConfig(
                id="header",
                text="VIP DISCOUNT",
                x_mm=50.0,
                y_mm=25.0,
                font_size_pt=18.0,
                color_hex="#F8FAFC",
                font_family="Roboto",
            )
        ],
        code_box=CodeBoxConfig(
            x_mm=140.0,
            y_mm=60.0,
            width_mm=55.0,
            height_mm=25.0,
            show_barcode=True,
            font_size_pt=10.0,
        ),
    )


def test_directory_initialization(temp_repo: StorageRepository) -> None:
    assert temp_repo.templates_dir.is_dir()
    assert temp_repo.bundles_dir.is_dir()
    assert temp_repo.assets_dir.is_dir()
    assert temp_repo.presets_dir.is_dir()
    assert temp_repo.exports_dir.is_dir()


def test_save_and_load_template(temp_repo: StorageRepository) -> None:
    template = create_sample_template("tmpl_a")
    saved_path = temp_repo.save_template(template)

    assert saved_path.exists()
    assert saved_path.name == "tmpl_a.json"

    loaded = temp_repo.load_template("tmpl_a")
    assert loaded.id == "tmpl_a"
    assert loaded.schema_version == CURRENT_SCHEMA_VERSION
    assert loaded.background.type == "gradient"
    assert loaded.background.gradient_angle_deg == 45.0
    assert loaded.logo is not None
    assert loaded.logo.asset_filename == "brand.png"
    assert len(loaded.text_blocks) == 1
    assert loaded.text_blocks[0].id == "header"
    assert loaded.code_box.show_barcode is True


def test_list_templates(temp_repo: StorageRepository) -> None:
    assert temp_repo.list_templates() == []

    t1 = create_sample_template("tmpl_01")
    t2 = create_sample_template("tmpl_02")
    temp_repo.save_template(t1)
    temp_repo.save_template(t2)

    templates = temp_repo.list_templates()
    assert len(templates) == 2
    ids = {t.id for t in templates}
    assert ids == {"tmpl_01", "tmpl_02"}


def test_load_template_not_found(temp_repo: StorageRepository) -> None:
    with pytest.raises(TemplateNotFoundError) as exc_info:
        temp_repo.load_template("non_existent")
    assert exc_info.value.template_id == "non_existent"


def test_save_and_load_bundle(temp_repo: StorageRepository) -> None:
    bundle = BundleRegistry(
        id="bundle_2026_q1",
        name="Spring Promo",
        code_prefix="SP26",
        created_at="2026-03-01T12:00:00Z",
        vouchers=[
            VoucherItem(
                code="SP26-0001",
                template_id="tmpl_a",
                status=VoucherStatus.ACTIVE,
                created_at="2026-03-01T12:00:00Z",
            ),
            VoucherItem(
                code="SP26-0002",
                template_id="tmpl_a",
                status=VoucherStatus.ACTIVE,
                created_at="2026-03-01T12:00:00Z",
            ),
        ],
    )

    saved_path = temp_repo.save_bundle(bundle)
    assert saved_path.exists()
    assert saved_path.name == "bundle_2026_q1.json"

    loaded = temp_repo.load_bundle("bundle_2026_q1")
    assert loaded.id == "bundle_2026_q1"
    assert len(loaded.vouchers) == 2
    assert loaded.vouchers[0].code == "SP26-0001"
    assert loaded.vouchers[0].status == VoucherStatus.ACTIVE


def test_load_bundle_not_found(temp_repo: StorageRepository) -> None:
    with pytest.raises(BundleNotFoundError) as exc_info:
        temp_repo.load_bundle("missing_bundle")
    assert exc_info.value.bundle_id == "missing_bundle"


def test_atomic_write_cleans_up_on_failure(temp_repo: StorageRepository) -> None:
    template = create_sample_template("crash_test")

    with patch("os.replace", side_effect=OSError("Atomic replacement failed")):
        with pytest.raises(OSError, match="Atomic replacement failed"):
            temp_repo.save_template(template)

    target_file = temp_repo.templates_dir / "crash_test.json"
    assert not target_file.exists()

    tmp_remnants = list(temp_repo.templates_dir.glob(".tmp_*"))
    assert tmp_remnants == []


def test_schema_version_mismatch_rejection(temp_repo: StorageRepository) -> None:
    payload = {
        "schema_version": "0.9.0",
        "id": "old_template",
        "name": "Legacy",
        "width_mm": 200.0,
        "height_mm": 100.0,
        "background": {"type": "flat_color", "color_start": "#000000"},
        "logo": None,
        "text_blocks": [],
        "code_box": {
            "x_mm": 0.0,
            "y_mm": 0.0,
            "width_mm": 10.0,
            "height_mm": 10.0,
            "show_barcode": False,
            "font_size_pt": 8.0,
        },
    }

    target_file = temp_repo.templates_dir / "old_template.json"
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    with pytest.raises(SchemaVersionMismatchError) as exc_info:
        temp_repo.load_template("old_template")

    assert exc_info.value.expected == CURRENT_SCHEMA_VERSION
    assert exc_info.value.actual == "0.9.0"


def test_schema_version_missing_rejection(temp_repo: StorageRepository) -> None:
    payload = {
        "id": "missing_ver_bundle",
        "name": "Invalid Bundle",
        "code_prefix": "INV",
        "created_at": "2026-01-01T00:00:00Z",
        "vouchers": [],
    }

    target_file = temp_repo.bundles_dir / "missing_ver_bundle.json"
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    with pytest.raises(SchemaVersionMismatchError) as exc_info:
        temp_repo.load_bundle("missing_ver_bundle")

    assert exc_info.value.expected == CURRENT_SCHEMA_VERSION
    assert exc_info.value.actual is None


def test_update_voucher_status(temp_repo: StorageRepository) -> None:
    bundle = BundleRegistry(
        id="bundle_state_test",
        name="State Check",
        code_prefix="ST",
        created_at="2026-03-01T12:00:00Z",
        vouchers=[
            VoucherItem(
                code="ST-001",
                template_id="tmpl_a",
                status=VoucherStatus.ACTIVE,
                created_at="2026-03-01T12:00:00Z",
            )
        ],
    )
    temp_repo.save_bundle(bundle)

    # 1. Update to REDEEMED
    updated = temp_repo.update_voucher_status(
        "bundle_state_test", "ST-001", VoucherStatus.REDEEMED
    )
    assert updated is True

    reloaded = temp_repo.load_bundle("bundle_state_test")
    voucher = reloaded.vouchers[0]
    assert voucher.status == VoucherStatus.REDEEMED
    assert voucher.redeemed_at is not None

    # 2. Update unknown code returns False without changing data
    not_found = temp_repo.update_voucher_status(
        "bundle_state_test", "NON-EXISTENT", VoucherStatus.CANCELLED
    )
    assert not_found is False

    # 3. Update to ACTIVE clears redeemed_at
    updated_back = temp_repo.update_voucher_status(
        "bundle_state_test", "ST-001", VoucherStatus.ACTIVE
    )
    assert updated_back is True
    reloaded_active = temp_repo.load_bundle("bundle_state_test")
    assert reloaded_active.vouchers[0].status == VoucherStatus.ACTIVE
    assert reloaded_active.vouchers[0].redeemed_at is None