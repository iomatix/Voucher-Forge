"""Unit tests verifying 2D Sheet Packing Engine, collision detection, and cut marks."""

import pytest

from voucher_forge.packer import (
    A4_HEIGHT_MM,
    A4_WIDTH_MM,
    PackedItem,
    pack_vouchers,
)


def _check_bounding_box_overlap(a: PackedItem, b: PackedItem) -> bool:
    """Returns True if two packed items intersect (excluding boundary touch)."""
    return not (
        a.x_mm + a.width_mm <= b.x_mm
        or b.x_mm + b.width_mm <= a.x_mm
        or a.y_mm + a.height_mm <= b.y_mm
        or b.y_mm + b.height_mm <= a.y_mm
    )


def test_fit_large_ticket_and_small_coupons_single_page() -> None:
    # 1 ticket DL-like (180x100) and 4 small business-card size coupons (85x55)
    items = [
        ("ticket_vip", 180.0, 100.0),
        ("coupon_1", 85.0, 55.0),
        ("coupon_2", 85.0, 55.0),
        ("coupon_3", 85.0, 55.0),
        ("coupon_4", 85.0, 55.0),
    ]

    result = pack_vouchers(items, margin_mm=8.0, spacing_mm=4.0)

    assert result.total_pages == 1
    page = result.pages[0]
    assert len(page.items) == 5
    assert result.efficiency_ratio > 0.0


def test_multi_page_overflow() -> None:
    # 12 large DL tickets (200x90). Each page can hold at most 2 or 3 tickets.
    items = [(f"ticket_{i}", 190.0, 80.0) for i in range(12)]

    result = pack_vouchers(items, margin_mm=8.0, spacing_mm=4.0)

    assert result.total_pages > 1
    total_packed_items = sum(len(p.items) for p in result.pages)
    assert total_packed_items == 12

    for idx, page in enumerate(result.pages):
        assert page.page_index == idx
        assert len(page.items) > 0


def test_no_boundary_violations_and_no_overlaps() -> None:
    items = [
        ("item_a", 150.0, 70.0),
        ("item_b", 80.0, 45.0),
        ("item_c", 60.0, 40.0),
        ("item_d", 90.0, 50.0),
        ("item_e", 75.0, 35.0),
        ("item_f", 120.0, 60.0),
        ("item_g", 85.0, 55.0),
    ]

    margin = 10.0
    result = pack_vouchers(items, margin_mm=margin, spacing_mm=3.0)

    for page in result.pages:
        for item in page.items:
            # Boundary checks within printable zone
            assert item.x_mm >= margin
            assert item.y_mm >= margin
            assert round(item.x_mm + item.width_mm, 2) <= round(A4_WIDTH_MM - margin, 2)
            assert round(item.y_mm + item.height_mm, 2) <= round(A4_HEIGHT_MM - margin, 2)

        # Collision verification O(N^2)
        item_count = len(page.items)
        for i in range(item_count):
            for j in range(i + 1, item_count):
                assert not _check_bounding_box_overlap(
                    page.items[i], page.items[j]
                ), f"Collision detected between '{page.items[i].item_id}' and '{page.items[j].item_id}'"


def test_cut_marks_generation_and_placement() -> None:
    items = [("v_01", 100.0, 50.0)]
    margin = 8.0
    result = pack_vouchers(items, margin_mm=margin, spacing_mm=4.0)

    page = result.pages[0]
    item = page.items[0]
    # Each item generates 8 tick marks (2 per corner)
    assert len(page.cut_marks) == 8

    for mark in page.cut_marks:
        # One point of each mark starts on the item bounding box
        on_left = round(mark.x1_mm, 2) == round(item.x_mm, 2)
        on_right = round(mark.x1_mm, 2) == round(item.x_mm + item.width_mm, 2)
        on_top = round(mark.y1_mm, 2) == round(item.y_mm, 2)
        on_bottom = round(mark.y1_mm, 2) == round(item.y_mm + item.height_mm, 2)

        assert (on_left or on_right) and (on_top or on_bottom)

        # Cut ticks point away from the voucher (outside its interior)
        if mark.x2_mm != mark.x1_mm:
            assert (
                mark.x2_mm < item.x_mm or mark.x2_mm > item.x_mm + item.width_mm
            )
        if mark.y2_mm != mark.y1_mm:
            assert (
                mark.y2_mm < item.y_mm or mark.y2_mm > item.y_mm + item.height_mm
            )


def test_item_exceeding_sheet_raises_error() -> None:
    # 250x250 does not fit on A4 (210x297 minus margins) in any orientation
    items = [("oversized", 250.0, 250.0)]
    with pytest.raises(ValueError, match="exceeds printable area"):
        pack_vouchers(items)


def test_empty_items_input() -> None:
    result = pack_vouchers([])
    assert result.total_pages == 0
    assert result.pages == []
    assert result.efficiency_ratio == 0.0