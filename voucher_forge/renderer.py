"""Rendering engine for vector SVG previews and multi-page print-ready PDFs.

Transforms TemplateConfig, VoucherItem, and PackingResult into SVG strings and ReportLab PDFs.
Zero-UI coupling: depends strictly on standard library and reportlab.
"""

from __future__ import annotations

import base64
import html
import math
import mimetypes
from pathlib import Path
from typing import Any

from reportlab.graphics.barcode.code128 import Code128
from reportlab.lib.colors import HexColor, gray
from reportlab.lib.units import mm as MM_TO_PT
from reportlab.pdfgen import canvas

from voucher_forge.models import TemplateConfig, VoucherItem
from voucher_forge.packer import A4_HEIGHT_MM, A4_WIDTH_MM, CutMark, PackedItem, PackingResult

A4_PAGE_WIDTH_PT = A4_WIDTH_MM * MM_TO_PT
A4_PAGE_HEIGHT_PT = A4_HEIGHT_MM * MM_TO_PT


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
) -> str:
    """Renders a standalone, proportional SVG XML representation of a voucher for UI preview."""
    w_mm = template.width_mm
    h_mm = template.height_mm
    svg_elements: list[str] = []
    defs_elements: list[str] = []

    # 1. Background layer
    bg = template.background
    if bg.type == "gradient" and bg.color_end:
        angle_rad = math.radians(bg.gradient_angle_deg)
        x1 = round(50 - 50 * math.cos(angle_rad), 2)
        y1 = round(50 - 50 * math.sin(angle_rad), 2)
        x2 = round(50 + 50 * math.cos(angle_rad), 2)
        y2 = round(50 + 50 * math.sin(angle_rad), 2)

        grad_id = f"bg-grad-{template.id}"
        defs_elements.append(
            f'  <linearGradient id="{grad_id}" x1="{x1}%" y1="{y1}%" x2="{x2}%" y2="{y2}%">\n'
            f'    <stop offset="0%" stop-color="{html.escape(bg.color_start)}" />\n'
            f'    <stop offset="100%" stop-color="{html.escape(bg.color_end)}" />\n'
            f"  </linearGradient>"
        )
        svg_elements.append(
            f'<rect width="{w_mm}" height="{h_mm}" fill="url(#{grad_id})" />'
        )
    elif bg.type == "image" and bg.image_asset and assets_dir:
        img_path = assets_dir / bg.image_asset
        uri = _encode_image_to_base64_uri(img_path)
        if uri:
            svg_elements.append(
                f'<image href="{uri}" width="{w_mm}" height="{h_mm}" preserveAspectRatio="xMidYMid slice" />'
            )
        else:
            svg_elements.append(
                f'<rect width="{w_mm}" height="{h_mm}" fill="{html.escape(bg.color_start)}" />'
            )
    else:
        svg_elements.append(
            f'<rect width="{w_mm}" height="{h_mm}" fill="{html.escape(bg.color_start)}" />'
        )

    # 2. Logo layer (render only if file actually exists on disk)
    if template.logo and assets_dir:
        l_path = assets_dir / template.logo.asset_filename
        uri = _encode_image_to_base64_uri(l_path)
        if uri:
            svg_elements.append(
                f'<image href="{uri}" x="{template.logo.x_mm}" y="{template.logo.y_mm}" '
                f'width="{template.logo.width_mm}" height="{template.logo.height_mm}" preserveAspectRatio="xMidYMid meet" />'
            )

    # 3. Text blocks layer (proportional viewBox user units)
    for tb in template.text_blocks:
        font_size_units = round(tb.font_size_pt * 0.352778, 3)
        escaped_text = html.escape(tb.text)
        svg_elements.append(
            f'<text x="{tb.x_mm}" y="{tb.y_mm}" font-family="{html.escape(tb.font_family)}, sans-serif" '
            f'font-size="{font_size_units}" font-weight="bold" fill="{html.escape(tb.color_hex)}" '
            f'dominant-baseline="hanging">{escaped_text}</text>'
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
            f'font-size="{font_size_units}" font-weight="bold" fill="#0F172A" '
            f'text-anchor="middle">{html.escape(sample_code)}</text>'
        )
    else:
        font_size_units = round(cb.font_size_pt * 0.352778, 3)
        text_y = cb.y_mm + (cb.height_mm / 2.0) + (font_size_units * 0.35)
        text_x = cb.x_mm + (cb.width_mm / 2.0)
        svg_elements.append(
            f'<text x="{text_x:.2f}" y="{text_y:.2f}" font-family="monospace" '
            f'font-size="{font_size_units}" font-weight="bold" fill="#0F172A" '
            f'text-anchor="middle">{html.escape(sample_code)}</text>'
        )

    defs_block = f"<defs>\n" + "\n".join(defs_elements) + "\n</defs>\n" if defs_elements else ""
    body = "\n  ".join(svg_elements)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'viewBox="0 0 {w_mm} {h_mm}" style="width: 100%; height: auto; max-height: 480px; display: block;">\n'
        f"{defs_block}"
        f"  {body}\n"
        f"</svg>"
    )
    
def _draw_cut_mark(c: canvas.Canvas, mark: CutMark) -> None:
    c.setLineWidth(0.5)
    c.setStrokeColor(gray)
    x1_pt = mark.x1_mm * MM_TO_PT
    y1_pt = A4_PAGE_HEIGHT_PT - (mark.y1_mm * MM_TO_PT)
    x2_pt = mark.x2_mm * MM_TO_PT
    y2_pt = A4_PAGE_HEIGHT_PT - (mark.y2_mm * MM_TO_PT)
    c.line(x1_pt, y1_pt, x2_pt, y2_pt)


def _render_voucher_on_pdf(
    c: canvas.Canvas,
    item: PackedItem,
    template: TemplateConfig,
    code: str,
    assets_dir: Path,
) -> None:
    c.saveState()

    x_pt = item.x_mm * MM_TO_PT
    y_top_pt = A4_PAGE_HEIGHT_PT - (item.y_mm * MM_TO_PT)

    c.translate(x_pt, y_top_pt)

    if item.is_rotated:
        c.rotate(-90)
        c.translate(-template.width_mm * MM_TO_PT, 0)

    # Invert local Y-axis so (0,0) is top-left
    c.scale(1, -1)

    t_w_pt = template.width_mm * MM_TO_PT
    t_h_pt = template.height_mm * MM_TO_PT

    # 1. Background
    bg = template.background
    if bg.type == "gradient" and bg.color_end:
        r1, g1, b1 = _hex_to_rgb(bg.color_start)
        r2, g2, b2 = _hex_to_rgb(bg.color_end)
        steps = 40
        step_w = t_w_pt / steps
        for step_idx in range(steps):
            ratio = step_idx / steps
            r = r1 + (r2 - r1) * ratio
            g = g1 + (g2 - g1) * ratio
            b = b1 + (b2 - b1) * ratio
            c.setFillColorRGB(r, g, b)
            c.setStrokeColorRGB(r, g, b)
            c.rect(step_idx * step_w, 0, step_w + 0.5, t_h_pt, fill=1, stroke=0)
    elif bg.type == "image" and bg.image_asset:
        img_path = assets_dir / bg.image_asset
        if img_path.is_file():
            c.saveState()
            c.scale(1, -1)
            c.drawImage(str(img_path), 0, -t_h_pt, width=t_w_pt, height=t_h_pt)
            c.restoreState()
        else:
            r, g, b = _hex_to_rgb(bg.color_start)
            c.setFillColorRGB(r, g, b)
            c.rect(0, 0, t_w_pt, t_h_pt, fill=1, stroke=0)
    else:
        r, g, b = _hex_to_rgb(bg.color_start)
        c.setFillColorRGB(r, g, b)
        c.rect(0, 0, t_w_pt, t_h_pt, fill=1, stroke=0)

    # 2. Logo
    if template.logo:
        logo = template.logo
        l_path = assets_dir / logo.asset_filename
        if l_path.is_file():
            c.saveState()
            lx_pt = logo.x_mm * MM_TO_PT
            ly_pt = logo.y_mm * MM_TO_PT
            lw_pt = logo.width_mm * MM_TO_PT
            lh_pt = logo.height_mm * MM_TO_PT
            c.translate(lx_pt, ly_pt)
            c.scale(1, -1)
            c.drawImage(str(l_path), 0, -lh_pt, width=lw_pt, height=lh_pt, mask="auto")
            c.restoreState()

    # 3. Text Blocks
    for tb in template.text_blocks:
        c.saveState()
        tx_pt = tb.x_mm * MM_TO_PT
        ty_pt = tb.y_mm * MM_TO_PT
        c.translate(tx_pt, ty_pt)
        c.scale(1, -1)
        r, g, b = _hex_to_rgb(tb.color_hex)
        c.setFillColorRGB(r, g, b)
        c.setFont("Helvetica-Bold", tb.font_size_pt)
        c.drawString(0, -tb.font_size_pt * 0.8, tb.text)
        c.restoreState()

    # 4. Code Box & Barcode
    cb = template.code_box
    cb_x = cb.x_mm * MM_TO_PT
    cb_y = cb.y_mm * MM_TO_PT
    cb_w = cb.width_mm * MM_TO_PT
    cb_h = cb.height_mm * MM_TO_PT

    c.setFillColor(HexColor("#FFFFFF"))
    c.setStrokeColor(HexColor("#0F172A"))
    c.setLineWidth(0.5)
    c.roundRect(cb_x, cb_y, cb_w, cb_h, 3, fill=1, stroke=1)

    if cb.show_barcode:
        barcode_h_pt = cb_h * 0.52
        barcode = Code128(
            code,
            barWidth=0.8,
            barHeight=barcode_h_pt,
            humanReadable=False,
            checksum=0,
        )

        c.saveState()
        # Barcode draws upward in standard Cartesian; flip back to normal orientation
        bx = cb_x + max(0.0, (cb_w - barcode.width) / 2.0)
        by = cb_y + cb_h - 3.0
        c.translate(bx, by)
        c.scale(1, -1)
        barcode.drawOn(c, 0, 0)
        c.restoreState()

        # Text label under barcode
        c.saveState()
        c.scale(1, -1)
        c.setFillColor(HexColor("#0F172A"))
        c.setFont("Courier-Bold", cb.font_size_pt)
        label_x = cb_x + (cb_w / 2.0)
        label_y = -(cb_y + cb_h - 3.0)
        c.drawCentredString(label_x, label_y, code)
        c.restoreState()
    else:
        c.saveState()
        c.scale(1, -1)
        c.setFillColor(HexColor("#0F172A"))
        c.setFont("Courier-Bold", cb.font_size_pt)
        label_x = cb_x + (cb_w / 2.0)
        label_y = -(cb_y + (cb_h / 2.0) - (cb.font_size_pt * 0.3))
        c.drawCentredString(label_x, label_y, code)
        c.restoreState()

    c.restoreState()


def render_bundle_pdf(
    packing_result: PackingResult,
    templates_map: dict[str, TemplateConfig],
    vouchers_map: dict[str, VoucherItem],
    output_pdf_path: Path | str,
    assets_dir: Path | str = "data/assets",
) -> Path:
    """Renders all packed pages into a multi-page A4 print PDF."""
    target_path = Path(output_pdf_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    assets_dir_path = Path(assets_dir).resolve()

    pdf_canvas = canvas.Canvas(
        str(target_path),
        pagesize=(A4_PAGE_WIDTH_PT, A4_PAGE_HEIGHT_PT),
    )

    for page in packing_result.pages:
        for mark in page.cut_marks:
            _draw_cut_mark(pdf_canvas, mark)

        for item in page.items:
            voucher = vouchers_map.get(item.item_id)
            code_value = voucher.code if voucher else item.item_id
            template_id = voucher.template_id if voucher else "default"

            template = templates_map.get(template_id)
            if template is None:
                template = next(iter(templates_map.values()))

            _render_voucher_on_pdf(
                pdf_canvas,
                item=item,
                template=template,
                code=code_value,
                assets_dir=assets_dir_path,
            )

        pdf_canvas.showPage()

    pdf_canvas.save()
    return target_path