"""NiceGUI main application orchestrator.

Initializes state, static routes, navigation bar with reactive language selector,
and mounts modular sub-views into tabs.
"""

from __future__ import annotations

from nicegui import app, ui

from voucher_forge.models import (
    BackgroundConfig,
    CodeBoxConfig,
    LogoConfig,
    TemplateConfig,
    TextBlockConfig,
)
from voucher_forge.storage import StorageRepository
from voucher_forge.ui.state import AppState
from voucher_forge.ui.view_forge import BatchForgeView
from voucher_forge.ui.view_scanner import ScannerView
from voucher_forge.ui.view_templates import TemplateStudioView


def _seed_default_templates(storage: StorageRepository) -> None:
    """Seeds initial demonstration templates if repository is empty."""
    existing = storage.list_templates()
    if existing:
        return

    # Birthday Ticket DL (210 x 99 mm)
    t1 = TemplateConfig(
        id="tmpl_birthday_dl",
        name="Birthday Ticket DL",
        width_mm=210.0,
        height_mm=99.0,
        background=BackgroundConfig(
            type="gradient",
            color_start="#0F172A",
            color_end="#334155",
            gradient_angle_deg=45.0,
        ),
        logo=LogoConfig(
            asset_filename="brand.png",
            x_mm=12.0,
            y_mm=12.0,
            width_mm=28.0,
            height_mm=14.0,
        ),
        text_blocks=[
            TextBlockConfig(
                id="tb_title",
                text="BIRTHDAY GIFT VOUCHER",
                x_mm=48.0,
                y_mm=18.0,
                font_size_pt=18.0,
                color_hex="#F8FAFC",
                font_family="Helvetica-Bold",
            ),
            TextBlockConfig(
                id="tb_sub",
                text="Valid for all services and store products",
                x_mm=48.0,
                y_mm=32.0,
                font_size_pt=11.0,
                color_hex="#94A3B8",
                font_family="Helvetica",
            ),
        ],
        code_box=CodeBoxConfig(
            x_mm=135.0,
            y_mm=58.0,
            width_mm=62.0,
            height_mm=28.0,
            show_barcode=True,
            font_size_pt=9.0,
        ),
    )

    # Mini Discount Coupon (85 x 55 mm)
    t2 = TemplateConfig(
        id="tmpl_mini_card",
        name="Mini Discount Coupon",
        width_mm=85.0,
        height_mm=55.0,
        background=BackgroundConfig(
            type="flat_color",
            color_start="#1E293B",
        ),
        logo=None,
        text_blocks=[
            TextBlockConfig(
                id="tb_mini_title",
                text="-20% SPECIAL OFFER",
                x_mm=8.0,
                y_mm=10.0,
                font_size_pt=12.0,
                color_hex="#38BDF8",
                font_family="Helvetica-Bold",
            ),
            TextBlockConfig(
                id="tb_mini_desc",
                text="Show at checkout",
                x_mm=8.0,
                y_mm=20.0,
                font_size_pt=8.0,
                color_hex="#E2E8F0",
                font_family="Helvetica",
            ),
        ],
        code_box=CodeBoxConfig(
            x_mm=8.0,
            y_mm=30.0,
            width_mm=69.0,
            height_mm=18.0,
            show_barcode=False,
            font_size_pt=10.0,
        ),
    )

    storage.save_template(t1)
    storage.save_template(t2)


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
            lang_dropdown = ui.select(
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