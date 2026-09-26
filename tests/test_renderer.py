"""Unit tests verifying SVG live preview and multi-page PDF generation."""

from pathlib import Path
import pytest

from voucher_forge.models import (
    BackgroundConfig,
    CodeBoxConfig,
    LogoConfig,
    TemplateConfig,
    TextBlockConfig,
    VoucherItem,
    VoucherStatus,
)
from voucher_forge.packer import pack_vouchers
from voucher_forge.renderer import render_bundle_pdf, render_voucher_svg


@pytest.fixture
def sample_template() -> TemplateConfig:
    return TemplateConfig(
        id="tmpl_vip",
        name="VIP Ticket",
        width_mm=180.0,
        height_mm=80.0,
        background=BackgroundConfig(
            type="gradient",
            color_start="#0F172A",
            color_end="#1E293B",
            gradient_angle_deg=90.0,
        ),
        logo=LogoConfig(
            asset_filename="test_logo.png",
            x_mm=10.0,
            y_mm=10.0,
            width_mm=30.0,
            height_mm=15.0,
        ),
        text_blocks=[
            TextBlockConfig(
                id="tb1",
                text="VIP ACCESS PASS",
                x_mm=50.0,
                y_mm=20.0,
                font_size_pt=16.0,
                color_hex="#F8FAFC",
                font_family="Helvetica",
            )
        ],
        code_box=CodeBoxConfig(
            x_mm=110.0,
            y_mm=45.0,
            width_mm=60.0,
            height_mm=25.0,
            show_barcode=True,
            font_size_pt=10.0,
        ),
    )


def test_render_voucher_svg(sample_template: TemplateConfig) -> None:
    code = "VIP-25W-12-8K"
    svg_output = render_voucher_svg(sample_template, sample_code=code)

    assert isinstance(svg_output, str)
    assert svg_output.startswith("<svg")
    assert svg_output.strip().endswith("</svg>")
    assert 'viewBox="0 0 180.0 80.0"' in svg_output
    assert "VIP ACCESS PASS" in svg_output
    assert code in svg_output
    assert "<linearGradient" in svg_output


def test_render_voucher_svg_with_text_overrides(sample_template: TemplateConfig) -> None:
    svg_output = render_voucher_svg(
        sample_template,
        sample_code="VIP-25W-12-8K",
        text_overrides={"tb1": "CUSTOM SPA OFFER"},
    )
    assert "CUSTOM SPA OFFER" in svg_output
    assert "VIP ACCESS PASS" not in svg_output


def test_render_bundle_pdf_generation(
    tmp_path: Path, sample_template: TemplateConfig
) -> None:
    items_to_pack = [
        ("v_01", sample_template.width_mm, sample_template.height_mm),
        ("v_02", sample_template.width_mm, sample_template.height_mm),
        ("v_03", sample_template.width_mm, sample_template.height_mm),
        ("v_04", sample_template.width_mm, sample_template.height_mm),
    ]

    packing_result = pack_vouchers(items_to_pack, margin_mm=8.0, spacing_mm=4.0)

    templates_map = {sample_template.id: sample_template}
    vouchers_map = {
        f"v_0{i}": VoucherItem(
            code=f"VIP-25W-12-0{i}",
            template_id=sample_template.id,
            status=VoucherStatus.ACTIVE,
            created_at="2026-03-01T12:00:00Z",
            text_overrides={"tb1": f"VARIANT {i}"},
        )
        for i in range(1, 5)
    }

    output_pdf = tmp_path / "test_bundle.pdf"
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    result_path = render_bundle_pdf(
        packing_result=packing_result,
        templates_map=templates_map,
        vouchers_map=vouchers_map,
        output_pdf_path=output_pdf,
        assets_dir=assets_dir,
    )

    assert result_path.exists()
    assert result_path.is_file()
    assert result_path.stat().st_size > 0

    with open(result_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-"


def test_render_rotated_voucher_in_pdf(tmp_path: Path) -> None:
    wide_template = TemplateConfig(
        id="tmpl_wide",
        name="Wide Banner Voucher",
        width_mm=280.0,
        height_mm=80.0,
        background=BackgroundConfig(type="flat_color", color_start="#22C55E"),
        logo=None,
        text_blocks=[
            TextBlockConfig(
                id="w_text",
                text="EXTENDED COUPON",
                x_mm=20.0,
                y_mm=20.0,
                font_size_pt=14.0,
                color_hex="#000000",
                font_family="Helvetica",
            )
        ],
        code_box=CodeBoxConfig(
            x_mm=180.0,
            y_mm=20.0,
            width_mm=70.0,
            height_mm=30.0,
            show_barcode=True,
            font_size_pt=9.0,
        ),
    )

    items = [("v_wide_1", 280.0, 80.0)]
    packing_result = pack_vouchers(items, margin_mm=8.0, spacing_mm=4.0)

    assert packing_result.pages[0].items[0].is_rotated is True

    templates_map = {wide_template.id: wide_template}
    vouchers_map = {
        "v_wide_1": VoucherItem(
            code="WID-25W-12-8X",
            template_id=wide_template.id,
            status=VoucherStatus.ACTIVE,
            created_at="2026-03-01T12:00:00Z",
        )
    }

    output_pdf = tmp_path / "rotated_bundle.pdf"
    result_path = render_bundle_pdf(
        packing_result=packing_result,
        templates_map=templates_map,
        vouchers_map=vouchers_map,
        output_pdf_path=output_pdf,
        assets_dir=tmp_path,
    )

    assert result_path.exists()
    assert result_path.stat().st_size > 0