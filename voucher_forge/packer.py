"""2D Sheet Packing Engine for multi-voucher layout on A4 pages.

Uses Shelf First-Fit Decreasing Height (FFDH) heuristic with 90-degree rotation support
and generates corner cut marks for guillotine trimming.
Zero-UI coupling: standard Python library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

A4_WIDTH_MM: float = 210.0
A4_HEIGHT_MM: float = 297.0
DEFAULT_MARGIN_MM: float = 8.0
DEFAULT_SPACING_MM: float = 4.0
CUT_MARK_LENGTH_MM: float = 3.0


@dataclass(slots=True)
class PackedItem:
    item_id: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    is_rotated: bool


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


@dataclass(slots=True)
class PackingResult:
    pages: list[PackedPage]
    total_pages: int
    efficiency_ratio: float


@dataclass(slots=True)
class _Shelf:
    y: float
    height: float
    current_x: float
    max_w: float

    def can_fit(self, width: float, height: float, spacing: float) -> bool:
        required_width = width if self.current_x == 0.0 else width + spacing
        return (self.current_x + required_width <= self.max_w) and (height <= self.height)

    def allocate(self, width: float, spacing: float) -> float:
        x = self.current_x if self.current_x == 0.0 else self.current_x + spacing
        self.current_x = x + width
        return x


class _PagePacker:
    def __init__(self, printable_width: float, printable_height: float, spacing: float) -> None:
        self.printable_width = printable_width
        self.printable_height = printable_height
        self.spacing = spacing
        self.shelves: list[_Shelf] = []
        self.used_y: float = 0.0

    def try_pack(self, width: float, height: float) -> tuple[float, float] | None:
        """Attempts to fit (width, height) on existing shelves or creates a new shelf."""
        for shelf in self.shelves:
            if shelf.can_fit(width, height, self.spacing):
                allocated_x = shelf.allocate(width, self.spacing)
                return allocated_x, shelf.y

        # Allocate new shelf
        required_shelf_height = height
        shelf_y = self.used_y if not self.shelves else self.used_y + self.spacing

        if shelf_y + required_shelf_height <= self.printable_height and width <= self.printable_width:
            new_shelf = _Shelf(
                y=shelf_y,
                height=required_shelf_height,
                current_x=width,
                max_w=self.printable_width,
            )
            self.shelves.append(new_shelf)
            self.used_y = shelf_y + required_shelf_height
            return 0.0, shelf_y

        return None


def _generate_corner_cut_marks(
    x: float, y: float, w: float, h: float, mark_len: float = CUT_MARK_LENGTH_MM
) -> list[CutMark]:
    """Generates 8 outward-pointing L-shaped corner tick marks for a rectangular item."""
    return [
        # Top-Left corner
        CutMark(x1_mm=x, y1_mm=y, x2_mm=x - mark_len, y2_mm=y),
        CutMark(x1_mm=x, y1_mm=y, x2_mm=x, y2_mm=y - mark_len),
        # Top-Right corner
        CutMark(x1_mm=x + w, y1_mm=y, x2_mm=x + w + mark_len, y2_mm=y),
        CutMark(x1_mm=x + w, y1_mm=y, x2_mm=x + w, y2_mm=y - mark_len),
        # Bottom-Left corner
        CutMark(x1_mm=x, y1_mm=y + h, x2_mm=x - mark_len, y2_mm=y + h),
        CutMark(x1_mm=x, y1_mm=y + h, x2_mm=x, y2_mm=y + h + mark_len),
        # Bottom-Right corner
        CutMark(x1_mm=x + w, y1_mm=y + h, x2_mm=x + w + mark_len, y2_mm=y + h),
        CutMark(x1_mm=x + w, y1_mm=y + h, x2_mm=x + w, y2_mm=y + h + mark_len),
    ]


def pack_vouchers(
    items: list[tuple[str, float, float]],
    margin_mm: float = DEFAULT_MARGIN_MM,
    spacing_mm: float = DEFAULT_SPACING_MM,
) -> PackingResult:
    """Arranges rectangular voucher items onto A4 portrait sheets using FFDH with 90° rotation.

    Args:
        items: List of tuples (item_id, width_mm, height_mm).
        margin_mm: Margin applied to all 4 edges of the A4 page.
        spacing_mm: Gutter spacing between adjacent vouchers.

    Returns:
        PackingResult containing pages with positioned items and cutting marks.
    """
    if not items:
        return PackingResult(pages=[], total_pages=0, efficiency_ratio=0.0)

    printable_w = round(A4_WIDTH_MM - 2 * margin_mm, 4)
    printable_h = round(A4_HEIGHT_MM - 2 * margin_mm, 4)

    if printable_w <= 0 or printable_h <= 0:
        raise ValueError("Margins exceed available sheet dimensions.")

    # Validate physical fit against page boundaries
    for item_id, w, h in items:
        fits_normal = w <= printable_w and h <= printable_h
        fits_rotated = h <= printable_w and w <= printable_h
        if not (fits_normal or fits_rotated):
            raise ValueError(
                f"Item '{item_id}' ({w}x{h} mm) exceeds printable area ({printable_w}x{printable_h} mm) "
                "even with 90° rotation."
            )

    # Sort items by max dimension descending (FFDH heuristic)
    sorted_items = sorted(
        items,
        key=lambda item: (max(item[1], item[2]), min(item[1], item[2])),
        reverse=True,
    )

    pages: list[PackedPage] = []
    page_packers: list[_PagePacker] = []

    for item_id, orig_w, orig_h in sorted_items:
        placed = False

        # Orientation candidates: evaluate upright first, then rotated 90 degrees
        orientations = [
            (orig_w, orig_h, False),
            (orig_h, orig_w, True),
        ]

        # Prioritize orientation that minimizes shelf height waste (lower height)
        orientations.sort(key=lambda o: o[1])

        # Try existing pages
        for page_idx, (page, packer) in enumerate(zip(pages, page_packers)):
            for w, h, is_rot in orientations:
                if w > printable_w or h > printable_h:
                    continue
                placement = packer.try_pack(w, h)
                if placement is not None:
                    local_x, local_y = placement
                    actual_x = margin_mm + local_x
                    actual_y = margin_mm + local_y

                    page.items.append(
                        PackedItem(
                            item_id=item_id,
                            x_mm=round(actual_x, 4),
                            y_mm=round(actual_y, 4),
                            width_mm=round(w, 4),
                            height_mm=round(h, 4),
                            is_rotated=is_rot,
                        )
                    )
                    page.cut_marks.extend(
                        _generate_corner_cut_marks(actual_x, actual_y, w, h)
                    )
                    placed = True
                    break
            if placed:
                break

        # Open a new page if no existing page could accommodate
        if not placed:
            new_packer = _PagePacker(printable_w, printable_h, spacing_mm)
            new_page = PackedPage(page_index=len(pages))

            for w, h, is_rot in orientations:
                if w > printable_w or h > printable_h:
                    continue
                placement = new_packer.try_pack(w, h)
                if placement is not None:
                    local_x, local_y = placement
                    actual_x = margin_mm + local_x
                    actual_y = margin_mm + local_y

                    new_page.items.append(
                        PackedItem(
                            item_id=item_id,
                            x_mm=round(actual_x, 4),
                            y_mm=round(actual_y, 4),
                            width_mm=round(w, 4),
                            height_mm=round(h, 4),
                            is_rotated=is_rot,
                        )
                    )
                    new_page.cut_marks.extend(
                        _generate_corner_cut_marks(actual_x, actual_y, w, h)
                    )
                    placed = True
                    break

            if not placed:
                raise RuntimeError(f"Unexpected layout failure for item '{item_id}'")

            pages.append(new_page)
            page_packers.append(new_packer)

    # Compute overall printable area efficiency ratio
    total_voucher_area = sum(item[1] * item[2] for item in items)
    total_printable_area = len(pages) * (printable_w * printable_h)
    efficiency = round(total_voucher_area / total_printable_area, 4) if total_printable_area > 0 else 0.0

    return PackingResult(
        pages=pages,
        total_pages=len(pages),
        efficiency_ratio=efficiency,
    )