"""Rendering engine for vector SVG previews and multi-page print sheets.

Maintains strict separation between responsive UI preview vectors (CSS-scaled SVG)
and print-sheet layout logic with parametric scale, enterprise typography (Inter),
and crisp vector clipping masks.
Zero-UI coupling: standard library only.
"""

from __future__ import annotations

import base64
import html
import math
import mimetypes
import uuid
from pathlib import Path

from voucher_forge.models import TemplateConfig, VoucherItem
from voucher_forge.packer import (
    A4_HEIGHT_MM,
    A4_WIDTH_MM,
    PackedPage,
    PackingResult,
)

FONT_STACK: str = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def _hex_to_rgb(hex_code: str) -> tuple[float, float, float]:
    clean = hex_code.lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        return 0.0, 0.0, 0.0
    r = int(clean[0:2], 16) / 255.0
    g = int(clean[2:4], 16) / 255.0
    b = int(clean[4:6], 16) / 255.0
    return r, g, b


def _get_contrast_stroke(hex_code: str) -> str:
    """Returns dark stroke for light text, light stroke for dark text."""
    r, g, b = _hex_to_rgb(hex_code)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#0F172A" if luminance > 0.45 else "#FFFFFF"


def _encode_image_to_base64_uri(image_path: Path) -> str | None:
    if not image_path.is_file():
        return None
    mime, _ = mimetypes.guess_type(str(image_path))
    if mime is None:
        mime = "image/png"
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def render_voucher_svg(
    template: TemplateConfig,
    sample_code: str = "URO-K9A-03-7B",
    assets_dir: Path | None = None,
    text_overrides: dict[str, str] | None = None,
    bg_asset_override: str | None = None,
    logo_asset_override: str | None = None,
    bg_color_override: str | None = None,
) -> str:
    """Renders a standalone, responsive SVG XML representation of a voucher for UI preview."""
    w_mm = template.width_mm
    h_mm = template.height_mm
    svg_elements: list[str] = []
    defs_elements: list[str] = []

    render_uid = uuid.uuid4().hex[:8]
    clip_id = f"voucher-clip-{template.id}-{render_uid}"
    defs_elements.append(
        f'  <clipPath id="{clip_id}">\n'
        f'    <rect width="{w_mm}" height="{h_mm}" rx="0" ry="0" />\n'
        f"  </clipPath>"
    )

    # 1. Background layer
    bg = template.background
    eff_color_start = bg_color_override or bg.color_start

    if bg_asset_override == "__NONE__":
        eff_bg_type = "flat_color"
        eff_bg_asset = None
    else:
        eff_bg_type = "image" if bg_asset_override else bg.type
        eff_bg_asset = bg_asset_override or bg.image_asset

    if eff_bg_type == "gradient" and bg.color_end:
        angle_rad = math.radians(bg.gradient_angle_deg)
        x1 = round(50 - 50 * math.cos(angle_rad), 2)
        y1 = round(50 - 50 * math.sin(angle_rad), 2)
        x2 = round(50 + 50 * math.cos(angle_rad), 2)
        y2 = round(50 + 50 * math.sin(angle_rad), 2)

        grad_id = f"bg-grad-{template.id}-{render_uid}"
        defs_elements.append(
            f'  <linearGradient id="{grad_id}" x1="{x1}%" y1="{y1}%" x2="{x2}%" y2="{y2}%">\n'
            f'    <stop offset="0%" stop-color="{html.escape(eff_color_start)}" />\n'
            f'    <stop offset="100%" stop-color="{html.escape(bg.color_end)}" />\n'
            f"  </linearGradient>"
        )
        svg_elements.append(
            f'<rect width="{w_mm}" height="{h_mm}" fill="url(#{grad_id})" />'
        )
    elif eff_bg_type == "image":
        svg_elements.append(
            f'<rect width="{w_mm}" height="{h_mm}" fill="{html.escape(eff_color_start)}" />'
        )
        if eff_bg_asset and assets_dir:
            img_path = (assets_dir / eff_bg_asset).resolve()
            uri = _encode_image_to_base64_uri(img_path)
            if uri:
                svg_elements.append(
                    f'<image href="{uri}" xlink:href="{uri}" width="{w_mm}" height="{h_mm}" preserveAspectRatio="xMidYMid slice" />'
                )
    else:
        svg_elements.append(
            f'<rect width="{w_mm}" height="{h_mm}" fill="{html.escape(eff_color_start)}" />'
        )

    # 2. Logo layer
    if template.logo and assets_dir and logo_asset_override != "__NONE__":
        eff_logo_asset = logo_asset_override or template.logo.asset_filename
        if eff_logo_asset:
            l_path = (assets_dir / eff_logo_asset).resolve()
            uri = _encode_image_to_base64_uri(l_path)
            if uri:
                svg_elements.append(
                    f'<image href="{uri}" xlink:href="{uri}" x="{template.logo.x_mm}" y="{template.logo.y_mm}" '
                    f'width="{template.logo.width_mm}" height="{template.logo.height_mm}" preserveAspectRatio="xMidYMid meet" />'
                )

    # 3. Text blocks layer (Inter typography with automatic boundary safety)
    raw_overrides = text_overrides or {}
    override_vals = list(raw_overrides.values())

    for idx, tb in enumerate(template.text_blocks):
        if tb.id in raw_overrides:
            display_text = raw_overrides[tb.id]
        elif idx < len(override_vals):
            display_text = override_vals[idx]
        else:
            display_text = tb.text

        font_size_units = round(tb.font_size_pt * 0.352778, 3)
        escaped_text = html.escape(display_text)
        stroke_color = _get_contrast_stroke(tb.color_hex)
        stroke_w = round(font_size_units * 0.12, 3)

        max_text_w = max(10.0, round(w_mm - tb.x_mm - 4.0, 2))
        est_char_w = font_size_units * 0.58
        est_total_w = len(display_text) * est_char_w

        length_constraint = ""
        if est_total_w > max_text_w:
            length_constraint = f'textLength="{max_text_w}" lengthAdjust="spacingAndGlyphs"'

        svg_elements.append(
            f'<text x="{tb.x_mm}" y="{tb.y_mm}" {length_constraint} '
            f'font-family="{FONT_STACK}" '
            f'font-size="{font_size_units}" font-weight="700" fill="{html.escape(tb.color_hex)}" '
            f'stroke="{stroke_color}" stroke-width="{stroke_w}" stroke-linejoin="round" '
            f'style="paint-order: stroke fill; letter-spacing: -0.01em;" dominant-baseline="hanging">{escaped_text}</text>'
        )

    # 4. Code Box layer
    cb = template.code_box
    svg_elements.append(
        f'<rect x="{cb.x_mm}" y="{cb.y_mm}" width="{cb.width_mm}" height="{cb.height_mm}" '
        f'fill="#FFFFFF" stroke="#0F172A" stroke-width="0.3" rx="1.5" />'
    )

    if cb.show_barcode:
        bar_area_h = cb.height_mm * 0.52
        bar_count = 28
        usable_w = cb.width_mm - 4.0
        start_x = cb.x_mm + 2.0
        start_y = cb.y_mm + 2.0
        step = usable_w / bar_count

        for i in range(bar_count):
            if (i * 7 + 3) % 11 > 3:
                bx = start_x + (i * step)
                bw = max(0.25, step * 0.55)
                svg_elements.append(
                    f'<rect x="{bx:.2f}" y="{start_y:.2f}" width="{bw:.2f}" height="{bar_area_h:.2f}" fill="#0F172A" />'
                )

        font_size_units = round(cb.font_size_pt * 0.352778, 3)
        text_y = cb.y_mm + cb.height_mm - 1.5
        text_x = cb.x_mm + (cb.width_mm / 2.0)
        svg_elements.append(
            f'<text x="{text_x:.2f}" y="{text_y:.2f}" font-family="monospace" '
            f'font-size="{font_size_units}" font-weight="700" fill="#0F172A" '
            f'text-anchor="middle">{html.escape(sample_code)}</text>'
        )
    else:
        font_size_units = round(cb.font_size_pt * 0.352778, 3)
        text_y = cb.y_mm + (cb.height_mm / 2.0) + (font_size_units * 0.35)
        text_x = cb.x_mm + (cb.width_mm / 2.0)
        svg_elements.append(
            f'<text x="{text_x:.2f}" y="{text_y:.2f}" font-family="monospace" '
            f'font-size="{font_size_units}" font-weight="700" fill="#0F172A" '
            f'text-anchor="middle">{html.escape(sample_code)}</text>'
        )

    # 5. Technical clean border (hairline guideline for manual trimming)
    svg_elements.append(
        f'<rect width="{w_mm}" height="{h_mm}" fill="none" stroke="#CBD5E1" stroke-width="0.15" />'
    )

    defs_block = "<defs>\n" + "\n".join(defs_elements) + "\n</defs>\n" if defs_elements else ""
    body = "\n    ".join(svg_elements)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" '
        f'viewBox="0 0 {w_mm} {h_mm}" style="width: 100%; height: auto; max-height: 480px; display: block;">\n'
        f"{defs_block}"
        f'  <g clip-path="url(#{clip_id})">\n'
        f"    {body}\n"
        f"  </g>\n"
        f"</svg>"
    )


def _render_page_svg(
    page: PackedPage,
    templates_map: dict[str, TemplateConfig],
    vouchers_map: dict[str, VoucherItem],
    assets_dir: Path,
) -> str:
    """Composes a complete A4 sheet SVG embedding exact voucher vector outputs with parametric scaling."""
    sheet_w = A4_WIDTH_MM
    sheet_h = A4_HEIGHT_MM

    cut_mark_lines: list[str] = []
    for mark in page.cut_marks:
        cut_mark_lines.append(
            f'<line x1="{mark.x1_mm}" y1="{mark.y1_mm}" x2="{mark.x2_mm}" y2="{mark.y2_mm}" '
            f'stroke="#94A3B8" stroke-width="0.25" stroke-linecap="round" />'
        )

    voucher_elements: list[str] = []
    for item in page.items:
        voucher = vouchers_map.get(item.item_id)
        template_id = voucher.template_id if voucher else "default"
        template = templates_map.get(template_id) or next(iter(templates_map.values()))

        overrides = voucher.text_overrides if voucher else {}
        bg_override = voucher.bg_asset_override if voucher else None
        logo_override = voucher.logo_asset_override if voucher else None
        bg_color_override = getattr(voucher, "bg_color_override", None) if voucher else None
        code_str = voucher.code if voucher else item.item_id

        raw_voucher_svg = render_voucher_svg(
            template=template,
            sample_code=code_str,
            assets_dir=assets_dir,
            text_overrides=overrides,
            bg_asset_override=bg_override,
            logo_asset_override=logo_override,
            bg_color_override=bg_color_override,
        )

        inner_content = raw_voucher_svg
        start_idx = inner_content.find(">")
        if start_idx != -1:
            inner_content = inner_content[start_idx + 1 :]
        end_idx = inner_content.rfind("</svg>")
        if end_idx != -1:
            inner_content = inner_content[:end_idx]

        scale_val = getattr(item, "scale_factor", 1.0)
        if abs(scale_val - 1.0) > 1e-4:
            transform_attr = f'transform="translate({item.x_mm}, {item.y_mm}) scale({scale_val})"'
        else:
            transform_attr = f'transform="translate({item.x_mm}, {item.y_mm})"'

        voucher_elements.append(
            f'<g id="voucher-{html.escape(code_str)}" {transform_attr}>\n'
            f"{inner_content}\n"
            f"</g>"
        )

    all_marks = "\n  ".join(cut_mark_lines)
    all_vouchers = "\n  ".join(voucher_elements)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" '
        f'viewBox="0 0 {sheet_w} {sheet_h}" width="{sheet_w}mm" height="{sheet_h}mm" '
        f'style="background: #FFFFFF; display: block;">\n'
        f'  <g id="cut-marks">\n  {all_marks}\n  </g>\n'
        f'  <g id="vouchers">\n  {all_vouchers}\n  </g>\n'
        f"</svg>"
    )


def render_bundle_html(
    packing_result: PackingResult,
    templates_map: dict[str, TemplateConfig],
    vouchers_map: dict[str, VoucherItem],
    output_html_path: Path | str,
    assets_dir: Path | str = "data/assets",
) -> Path:
    """Generates print-ready multi-page HTML sheet with pure vector SVGs for browser printing."""
    target_path = Path(output_html_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    assets_dir_path = Path(assets_dir).resolve()

    page_svgs: list[str] = [
        _render_page_svg(
            page=page,
            templates_map=templates_map,
            vouchers_map=vouchers_map,
            assets_dir=assets_dir_path,
        )
        for page in packing_result.pages
    ]

    pages_html = "\n".join(
        f'<div class="sheet">\n{svg}\n</div>' for svg in page_svgs
    )
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(target_path.stem)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  @page {{
    size: A4 portrait;
    margin: 0;
  }}
  * {{
    box-sizing: border-box;
  }}
  body {{
    margin: 0;
    padding: 0;
    background: #0f172A;
    font-family: {FONT_STACK};
  }}
  .sheet {{
    width: 210mm;
    height: 297mm;
    page-break-after: always;
    break-after: page;
    background: #ffffff;
    margin: 20px auto;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
    overflow: hidden;
  }}
  @media print {{
    body {{
      background: none;
    }}
    .sheet {{
      margin: 0;
      box-shadow: none;
      page-break-after: always;
      break-after: page;
    }}
  }}
</style>
</head>
<body>
{pages_html}
</body>
</html>"""

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    return target_path


def render_bundle_pdf(
    packing_result: PackingResult,
    templates_map: dict[str, TemplateConfig],
    vouchers_map: dict[str, VoucherItem],
    output_pdf_path: Path | str,
    assets_dir: Path | str = "data/assets",
) -> Path:
    """Delegates to render_bundle_html without corrupting the .pdf binary extension."""
    target_pdf = Path(output_pdf_path).resolve()
    target_html = target_pdf.with_suffix(".html")
    render_bundle_html(
        packing_result=packing_result,
        templates_map=templates_map,
        vouchers_map=vouchers_map,
        output_html_path=target_html,
        assets_dir=assets_dir,
    )
    return target_html