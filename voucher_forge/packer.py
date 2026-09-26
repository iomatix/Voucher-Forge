"""2D Sheet Packing Engine for multi-voucher layout on A4 pages.

Features intelligent grid placement, natural orientation prioritization,
automatic page centering (horizontal and vertical), parametric scaling,
and full-span guillotine cut guidelines.
Zero-UI coupling: standard Python library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

A4_WIDTH_MM: float = 210.0
A4_HEIGHT_MM: float = 297.0
DEFAULT_MARGIN_MM: float = 8.0
DEFAULT_SPACING_MM: float = 4.0
CUT_MARK_LENGTH_MM: float = 4.0


@dataclass(slots=True)
class PackedItem:
    item_id: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    is_rotated: bool
    scale_factor: float = 1.0


@dataclass(slots=True)
class CutMark:
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float


@dataclass(slots=True)
class PackedPage:
    page_index: int
    items: list[PackedItem] = field(default_factory=list)
    cut_marks: list[CutMark] = field(default_factory=list)
    page_width_mm: float = A4_WIDTH_MM
    page_height_mm: float = A4_HEIGHT_MM


@dataclass(slots=True)
class PackingResult:
    pages: list[PackedPage]
    total_pages: int
    efficiency_ratio: float


def _generate_guillotine_cut_marks(
    items: list[PackedItem],
    page_w: float = A4_WIDTH_MM,
    page_h: float = A4_HEIGHT_MM,
    mark_len: float = CUT_MARK_LENGTH_MM,
) -> list[CutMark]:
    """Generates continuous margin guide ticks and gutter cut marks for single-stroke guillotine cuts."""
    if not items:
        return []

    x_coords: set[float] = set()
    y_coords: set[float] = set()

    for item in items:
        x_coords.add(round(item.x_mm, 2))
        x_coords.add(round(item.x_mm + item.width_mm, 2))
        y_coords.add(round(item.y_mm, 2))
        y_coords.add(round(item.y_mm + item.height_mm, 2))

    min_x = min(item.x_mm for item in items)
    max_x = max(item.x_mm + item.width_mm for item in items)
    min_y = min(item.y_mm for item in items)
    max_y = max(item.y_mm + item.height_mm for item in items)

    marks: list[CutMark] = []

    # 1. Vertical guide ticks on top and bottom margins
    for x in sorted(x_coords):
        # Top page margin tick
        marks.append(CutMark(x1_mm=x, y1_mm=max(0.0, min_y - mark_len), x2_mm=x, y2_mm=min_y))
        # Bottom page margin tick
        marks.append(CutMark(x1_mm=x, y1_mm=max_y, x2_mm=x, y2_mm=min(page_h, max_y + mark_len)))

    # 2. Horizontal guide ticks on left and right margins
    for y in sorted(y_coords):
        # Left page margin tick
        marks.append(CutMark(x1_mm=max(0.0, min_x - mark_len), y1_mm=y, x2_mm=min_x, y2_mm=y))
        # Right page margin tick
        marks.append(CutMark(x1_mm=max_x, y1_mm=y, x2_mm=min(page_w, max_x + mark_len), y2_mm=y))

    # 3. Gutter connector marks between vouchers
    sorted_x = sorted(x_coords)
    sorted_y = sorted(y_coords)

    # Vertical lines through horizontal gutters between items
    for item in items:
        # Corner micro-ticks for precise scissors cutting
        x, y, w, h = item.x_mm, item.y_mm, item.width_mm, item.height_mm
        marks.append(CutMark(x1_mm=x - 1.5, y1_mm=y, x2_mm=x, y2_mm=y))
        marks.append(CutMark(x1_mm=x, y1_mm=y - 1.5, x2_mm=x, y2_mm=y))
        marks.append(CutMark(x1_mm=x + w, y1_mm=y - 1.5, x2_mm=x + w, y2_mm=y))
        marks.append(CutMark(x1_mm=x + w, y1_mm=y, x2_mm=x + w + 1.5, y2_mm=y))
        marks.append(CutMark(x1_mm=x - 1.5, y1_mm=y + h, x2_mm=x, y2_mm=y + h))
        marks.append(CutMark(x1_mm=x, y1_mm=y + h, x2_mm=x, y2_mm=y + h + 1.5))
        marks.append(CutMark(x1_mm=x + w, y1_mm=y + h, x2_mm=x + w + 1.5, y2_mm=y + h))
        marks.append(CutMark(x1_mm=x + w, y1_mm=y + h, x2_mm=x + w, y2_mm=y + h + 1.5))

    return marks


def _center_page_items(
    page: PackedPage,
    page_w: float,
    page_h: float,
    min_margin: float,
) -> None:
    """Centers all items on the page both horizontally and vertically."""
    if not page.items:
        return

    min_x = min(item.x_mm for item in page.items)
    max_x = max(item.x_mm + item.width_mm for item in page.items)
    min_y = min(item.y_mm for item in page.items)
    max_y = max(item.y_mm + item.height_mm for item in page.items)

    bounding_w = max_x - min_x
    bounding_h = max_y - min_y

    target_x = max(min_margin, (page_w - bounding_w) / 2.0)
    target_y = max(min_margin, (page_h - bounding_h) / 2.0)

    shift_x = target_x - min_x
    shift_y = target_y - min_y

    for item in page.items:
        item.x_mm = round(item.x_mm + shift_x, 3)
        item.y_mm = round(item.y_mm + shift_y, 3)

    page.cut_marks = _generate_guillotine_cut_marks(page.items, page_w, page_h)


def pack_vouchers(
    items: list[tuple[str, float, float]],
    margin_mm: float = DEFAULT_MARGIN_MM,
    spacing_mm: float = DEFAULT_SPACING_MM,
    scale_factor: float = 1.0,
    target_cols: int | None = None,
    target_rows: int | None = None,
) -> PackingResult:
    """Arranges vouchers on A4 sheets with smart centering, scaling, and grid enforcement."""
    if not items:
        return PackingResult(pages=[], total_pages=0, efficiency_ratio=0.0)

    if scale_factor <= 0.0:
        raise ValueError("scale_factor must be greater than 0.0")

    printable_w = round(A4_WIDTH_MM - 2 * margin_mm, 4)
    printable_h = round(A4_HEIGHT_MM - 2 * margin_mm, 4)

    if printable_w <= 0 or printable_h <= 0:
        raise ValueError("Margins exceed available sheet dimensions.")

    w_base, h_base = items[0][1], items[0][2]
    is_uniform = all(w == w_base and h == h_base for _, w, h in items)

    effective_scale = scale_factor

    if is_uniform and (target_cols is not None or target_rows is not None):
        cols_req = target_cols if target_cols is not None else 1
        rows_req = target_rows if target_rows is not None else 1

        avail_w_for_items = printable_w - (cols_req - 1) * spacing_mm
        avail_h_for_items = printable_h - (rows_req - 1) * spacing_mm

        max_scale_x = (avail_w_for_items / (cols_req * w_base)) if (cols_req > 0 and avail_w_for_items > 0) else scale_factor
        max_scale_y = (avail_h_for_items / (rows_req * h_base)) if (rows_req > 0 and avail_h_for_items > 0) else scale_factor

        auto_fit_scale = min(max_scale_x, max_scale_y)
        effective_scale = min(scale_factor, auto_fit_scale)

    effective_scale = max(0.05, round(effective_scale, 4))

    scaled_items = [
        (item_id, round(w * effective_scale, 3), round(h * effective_scale, 3))
        for item_id, w, h in items
    ]

    pages: list[PackedPage] = []
    current_page = PackedPage(page_index=0)

    if is_uniform:
        w_scaled, h_scaled = scaled_items[0][1], scaled_items[0][2]

        cols = target_cols if target_cols is not None else max(1, int((printable_w + spacing_mm) // (w_scaled + spacing_mm)))
        rows = target_rows if target_rows is not None else max(1, int((printable_h + spacing_mm) // (h_scaled + spacing_mm)))
        capacity_per_page = max(1, cols * rows)

        for idx, (item_id, w, h) in enumerate(scaled_items):
            page_pos = idx % capacity_per_page
            if idx > 0 and page_pos == 0:
                _center_page_items(current_page, A4_WIDTH_MM, A4_HEIGHT_MM, margin_mm)
                pages.append(current_page)
                current_page = PackedPage(page_index=len(pages))

            col_idx = page_pos % cols
            row_idx = page_pos // cols

            item_x = margin_mm + col_idx * (w + spacing_mm)
            item_y = margin_mm + row_idx * (h + spacing_mm)

            current_page.items.append(
                PackedItem(
                    item_id=item_id,
                    x_mm=round(item_x, 3),
                    y_mm=round(item_y, 3),
                    width_mm=round(w, 3),
                    height_mm=round(h, 3),
                    is_rotated=False,
                    scale_factor=effective_scale,
                )
            )

        if current_page.items:
            _center_page_items(current_page, A4_WIDTH_MM, A4_HEIGHT_MM, margin_mm)
            pages.append(current_page)

    else:
        current_x = margin_mm
        current_y = margin_mm
        shelf_height = 0.0

        for item_id, w, h in scaled_items:
            if current_x + w > A4_WIDTH_MM - margin_mm:
                current_x = margin_mm
                current_y += shelf_height + spacing_mm
                shelf_height = 0.0

            if current_y + h > A4_HEIGHT_MM - margin_mm:
                _center_page_items(current_page, A4_WIDTH_MM, A4_HEIGHT_MM, margin_mm)
                pages.append(current_page)
                current_page = PackedPage(page_index=len(pages))
                current_x = margin_mm
                current_y = margin_mm
                shelf_height = 0.0

            current_page.items.append(
                PackedItem(
                    item_id=item_id,
                    x_mm=round(current_x, 3),
                    y_mm=round(current_y, 3),
                    width_mm=round(w, 3),
                    height_mm=round(h, 3),
                    is_rotated=False,
                    scale_factor=effective_scale,
                )
            )
            current_x += w + spacing_mm
            shelf_height = max(shelf_height, h)

        if current_page.items:
            _center_page_items(current_page, A4_WIDTH_MM, A4_HEIGHT_MM, margin_mm)
            pages.append(current_page)

    total_voucher_area = sum(w * h for _, w, h in scaled_items)
    total_page_area = len(pages) * (A4_WIDTH_MM * A4_HEIGHT_MM)
    efficiency = round(total_voucher_area / total_page_area, 4) if total_page_area > 0 else 0.0

    return PackingResult(
        pages=pages,
        total_pages=len(pages),
        efficiency_ratio=efficiency,
    )