"""Unit tests verifying SVG live preview and print-ready HTML/PDF sheet generation."""

import base64
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
from voucher_forge.renderer import (
    _get_contrast_stroke,
    _hex_to_rgb,
    render_bundle_html,
    render_bundle_pdf,
    render_voucher_svg,
)


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


def test_color_utilities() -> None:
    assert _hex_to_rgb("#FFFFFF") == (1.0, 1.0, 1.0)
    assert _hex_to_rgb("#000000") == (0.0, 0.0, 0.0)
    assert _hex_to_rgb("#FFF") == (1.0, 1.0, 1.0)
    assert _hex_to_rgb("invalid") == (0.0, 0.0, 0.0)

    # Light background gets dark stroke, dark background gets white stroke
    assert _get_contrast_stroke("#FFFFFF") == "#0F172A"
    assert _get_contrast_stroke("#000000") == "#FFFFFF"


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


def test_render_voucher_svg_with_stroke_contrast(sample_template: TemplateConfig) -> None:
    svg_output = render_voucher_svg(sample_template, sample_code="VIP-25W-12-8K")
    assert "paint-order: stroke fill;" in svg_output
    assert "stroke=" in svg_output


def test_render_voucher_svg_without_barcode(sample_template: TemplateConfig) -> None:
    sample_template.code_box.show_barcode = False
    svg_output = render_voucher_svg(sample_template, sample_code="CODE-WITHOUT-BARCODE")
    assert "CODE-WITHOUT-BARCODE" in svg_output
    # When barcode is disabled, bars loop is skipped
    assert svg_output.count('<rect ') < 5


def test_render_voucher_svg_image_background_and_logo(
    tmp_path: Path, sample_template: TemplateConfig
) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    bg_file = assets_dir / "bg.png"
    logo_file = assets_dir / "test_logo.png"

    # Write dummy 1x1 transparent PNG bytes
    dummy_png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
    bg_file.write_bytes(dummy_png)
    logo_file.write_bytes(dummy_png)

    sample_template.background = BackgroundConfig(type="image", image_asset="bg.png")
    svg_output = render_voucher_svg(
        sample_template,
        sample_code="TST-222-12-34",
        assets_dir=assets_dir,
    )
    assert "data:image/png;base64," in svg_output
    assert "<image href=" in svg_output


def test_render_voucher_svg_none_asset_overrides(
    tmp_path: Path, sample_template: TemplateConfig
) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    dummy_png = b"dummy"
    (assets_dir / "test_logo.png").write_bytes(dummy_png)

    sample_template.background = BackgroundConfig(type="image", image_asset="test_logo.png")
    svg_output = render_voucher_svg(
        sample_template,
        sample_code="TST-222-12-34",
        assets_dir=assets_dir,
        bg_asset_override="__NONE__",
        logo_asset_override="__NONE__",
    )
    # Both background image and logo should be suppressed
    assert "<image href=" not in svg_output


def test_render_voucher_svg_text_overflow_length_constraint(sample_template: TemplateConfig) -> None:
    long_text = "THIS IS AN EXTREMELY LONG VOUCHER PROMOTION TITLE THAT EXCEEDS BOUNDARIES"
    svg_output = render_voucher_svg(
        sample_template,
        sample_code="VIP-25W-12-8K",
        text_overrides={"tb1": long_text},
    )
    assert 'textLength="' in svg_output
    assert 'lengthAdjust="spacingAndGlyphs"' in svg_output


def test_render_bundle_html_and_pdf_generation(
    tmp_path: Path, sample_template: TemplateConfig
) -> None:
    items_to_pack = [
        ("v_01", sample_template.width_mm, sample_template.height_mm),
        ("v_02", sample_template.width_mm, sample_template.height_mm),
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
        for i in range(1, 3)
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

    # render_bundle_pdf deleguje do render_bundle_html i tworzy plik .html
    assert result_path.exists()
    assert result_path.suffix == ".html"
    assert result_path.is_file()
    assert result_path.stat().st_size > 0

    content = result_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert '<div class="sheet">' in content
    assert '<g id="cut-marks">' in content
    assert '<g id="vouchers">' in content
    assert "VIP-25W-12-01" in content
    assert "VIP-25W-12-02" in content
    assert "VARIANT 1" in content
    assert "VARIANT 2" in content


def test_render_bundle_with_scaled_items(tmp_path: Path, sample_template: TemplateConfig) -> None:
    # Pakowanie z wymuszoną siatką i skalowaniem w dół
    items_to_pack = [(f"v_0{i}", 150.0, 90.0) for i in range(4)]
    packing_result = pack_vouchers(items_to_pack, target_cols=2, target_rows=2)

    templates_map = {sample_template.id: sample_template}
    vouchers_map = {
        f"v_0{i}": VoucherItem(
            code=f"SCALE-222-12-0{i}",
            template_id=sample_template.id,
            status=VoucherStatus.ACTIVE,
            created_at="2026-03-01T12:00:00Z",
        )
        for i in range(4)
    }

    output_html = tmp_path / "scaled_bundle.html"
    result_path = render_bundle_html(
        packing_result=packing_result,
        templates_map=templates_map,
        vouchers_map=vouchers_map,
        output_html_path=output_html,
        assets_dir=tmp_path,
    )

    content = result_path.read_text(encoding="utf-8")
    assert "scale(" in content