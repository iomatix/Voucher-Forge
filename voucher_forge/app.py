"""NiceGUI main application orchestrator.

Initializes state, static routes, navigation bar with reactive language selector,
and mounts modular sub-views into tabs.
"""

from __future__ import annotations

from nicegui import app, ui

from voucher_forge.models import (
    BackgroundConfig,
    CodeBoxConfig,
    TemplateConfig,
    TextBlockConfig,
)
from voucher_forge.storage import StorageRepository
from voucher_forge.ui.state import AppState
from voucher_forge.ui.view_forge import BatchForgeView
from voucher_forge.ui.view_scanner import ScannerView
from voucher_forge.ui.view_templates import TemplateStudioView


def _seed_default_templates(storage: StorageRepository) -> None:
    """Seeds initial demonstration templates covering diverse formats and layouts."""
    existing = storage.list_templates()
    if existing:
        return

    # 1. Classic Ticket DL (210 x 99 mm) - Elegant Gold & Slate
    t1 = TemplateConfig(
        id="tmpl_vip_gold_dl",
        name="VIP Access Pass DL (210x99)",
        width_mm=210.0,
        height_mm=99.0,
        background=BackgroundConfig(
            type="gradient",
            color_start="#0F172A",
            color_end="#1E293B",
            gradient_angle_deg=45.0,
        ),
        logo=None,
        text_blocks=[
            TextBlockConfig(
                id="tb_title",
                text="VIP ACCESS PASS",
                x_mm=16.0,
                y_mm=22.0,
                font_size_pt=20.0,
                color_hex="#F59E0B",
                font_family="Helvetica-Bold",
            ),
            TextBlockConfig(
                id="tb_sub",
                text="Exclusive entry to all areas and events",
                x_mm=16.0,
                y_mm=38.0,
                font_size_pt=11.0,
                color_hex="#94A3B8",
                font_family="Helvetica",
            ),
        ],
        code_box=CodeBoxConfig(
            x_mm=135.0,
            y_mm=58.0,
            width_mm=60.0,
            height_mm=26.0,
            show_barcode=True,
            font_size_pt=9.0,
        ),
    )

    # 2. Gift Certificate A6 (148 x 105 mm) - Emerald Gift
    t2 = TemplateConfig(
        id="tmpl_gift_a6",
        name="Gift Certificate A6 (148x105)",
        width_mm=148.0,
        height_mm=105.0,
        background=BackgroundConfig(
            type="gradient",
            color_start="#064E3B",
            color_end="#022C22",
            gradient_angle_deg=135.0,
        ),
        logo=None,
        text_blocks=[
            TextBlockConfig(
                id="tb_title",
                text="GIFT CERTIFICATE",
                x_mm=14.0,
                y_mm=24.0,
                font_size_pt=18.0,
                color_hex="#34D399",
                font_family="Helvetica-Bold",
            ),
            TextBlockConfig(
                id="tb_sub",
                text="Redeemable on all products and services",
                x_mm=14.0,
                y_mm=38.0,
                font_size_pt=10.0,
                color_hex="#E2E8F0",
                font_family="Helvetica",
            ),
        ],
        code_box=CodeBoxConfig(
            x_mm=80.0,
            y_mm=68.0,
            width_mm=56.0,
            height_mm=24.0,
            show_barcode=True,
            font_size_pt=8.5,
        ),
    )

    # 3. Mini Discount Card (85 x 55 mm) - Business Card Format
    t3 = TemplateConfig(
        id="tmpl_mini_card",
        name="Mini Discount Card (85x55)",
        width_mm=85.0,
        height_mm=55.0,
        background=BackgroundConfig(
            type="flat_color",
            color_start="#18181B",
        ),
        logo=None,
        text_blocks=[
            TextBlockConfig(
                id="tb_title",
                text="20% OFF DISCOUNT",
                x_mm=8.0,
                y_mm=12.0,
                font_size_pt=14.0,
                color_hex="#38BDF8",
                font_family="Helvetica-Bold",
            ),
            TextBlockConfig(
                id="tb_sub",
                text="Present at checkout during payment",
                x_mm=8.0,
                y_mm=22.0,
                font_size_pt=8.0,
                color_hex="#A1A1AA",
                font_family="Helvetica",
            ),
        ],
        code_box=CodeBoxConfig(
            x_mm=8.0,
            y_mm=32.0,
            width_mm=69.0,
            height_mm=16.0,
            show_barcode=False,
            font_size_pt=9.5,
        ),
    )

    # 4. Dinner Voucher (160 x 80 mm) - Crimson Luxury
    t4 = TemplateConfig(
        id="tmpl_dinner_voucher",
        name="Dinner Voucher (160x80)",
        width_mm=160.0,
        height_mm=80.0,
        background=BackgroundConfig(
            type="gradient",
            color_start="#881337",
            color_end="#4C0519",
            gradient_angle_deg=90.0,
        ),
        logo=None,
        text_blocks=[
            TextBlockConfig(
                id="tb_title",
                text="DINNER FOR TWO",
                x_mm=14.0,
                y_mm=20.0,
                font_size_pt=16.0,
                color_hex="#FECDD3",
                font_family="Helvetica-Bold",
            ),
            TextBlockConfig(
                id="tb_sub",
                text="Includes starter, main course, and dessert",
                x_mm=14.0,
                y_mm=34.0,
                font_size_pt=9.5,
                color_hex="#FDA4AF",
                font_family="Helvetica",
            ),
        ],
        code_box=CodeBoxConfig(
            x_mm=94.0,
            y_mm=46.0,
            width_mm=54.0,
            height_mm=24.0,
            show_barcode=True,
            font_size_pt=8.5,
        ),
    )

    # 5. Club Pass (120 x 80 mm) - Indigo Fitness Pass
    t5 = TemplateConfig(
        id="tmpl_club_pass",
        name="Club Pass (120x80)",
        width_mm=120.0,
        height_mm=80.0,
        background=BackgroundConfig(
            type="gradient",
            color_start="#312E81",
            color_end="#1E1B4B",
            gradient_angle_deg=120.0,
        ),
        logo=None,
        text_blocks=[
            TextBlockConfig(
                id="tb_title",
                text="FITNESS CLUB PASS",
                x_mm=10.0,
                y_mm=18.0,
                font_size_pt=15.0,
                color_hex="#A5B4FC",
                font_family="Helvetica-Bold",
            ),
            TextBlockConfig(
                id="tb_sub",
                text="Valid for 10 entries to gym and sauna areas",
                x_mm=10.0,
                y_mm=32.0,
                font_size_pt=8.5,
                color_hex="#C7D2FE",
                font_family="Helvetica",
            ),
        ],
        code_box=CodeBoxConfig(
            x_mm=56.0,
            y_mm=48.0,
            width_mm=54.0,
            height_mm=22.0,
            show_barcode=True,
            font_size_pt=8.0,
        ),
    )

    for tmpl in (t1, t2, t3, t4, t5):
        storage.save_template(tmpl)


def create_app(base_dir: str = "data") -> None:
    storage = StorageRepository(base_dir=base_dir)
    _seed_default_templates(storage)

    state = AppState(storage=storage)

    ui.colors(primary="#0284C7", secondary="#475569", accent="#F59E0B")
    app.add_static_files("/exports", str(storage.exports_dir))

    # Top Navigation Bar
    with ui.header().classes("items-center justify-between bg-slate-900 text-white px-6 py-3"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("confirmation_number", size="2rem").classes("text-sky-400")
            title_lbl = ui.label(state.t("title")).classes("text-xl font-bold tracking-wide")

        with ui.row().classes("items-center gap-3"):
            ui.icon("language", size="1.2rem").classes("text-slate-400")
            ui.select(
                options={"pl": "Polski (PL)", "en": "English (EN)"},
                value=state.current_lang,
                on_change=lambda e: state.set_language(e.value),
            ).props("dense borderless dark options-dense").classes("w-36 text-white")

    # Main Tabs
    with ui.tabs().classes("w-full bg-slate-800 text-white shadow") as tabs:
        tab_studio = ui.tab(state.t("tab_templates"), icon="design_services")
        tab_forge = ui.tab(state.t("tab_forge"), icon="inventory_2")
        tab_scanner = ui.tab(state.t("tab_scanner"), icon="qr_code_scanner")

    # Reactive translation for top header and tab labels without page reload
    def update_header_labels() -> None:
        title_lbl.text = state.t("title")
        tab_studio.props(f'label="{state.t("tab_templates")}"')
        tab_forge.props(f'label="{state.t("tab_forge")}"')
        tab_scanner.props(f'label="{state.t("tab_scanner")}"')

    state.register_lang_listener(update_header_labels)

    # Modular Views Container
    with ui.tab_panels(tabs, value=tab_studio).classes("w-full max-w-7xl mx-auto p-6"):
        with ui.tab_panel(tab_studio):
            TemplateStudioView(state).render()

        with ui.tab_panel(tab_forge):
            BatchForgeView(state).render()

        with ui.tab_panel(tab_scanner):
            ScannerView(state).render()