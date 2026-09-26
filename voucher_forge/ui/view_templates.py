"""Template Studio view module for editing templates with live SVG preview."""

from __future__ import annotations

from typing import Any
from nicegui import ui

from voucher_forge.models import TextBlockConfig
from voucher_forge.renderer import render_voucher_svg
from voucher_forge.ui.state import AppState


class TemplateStudioView:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def render(self) -> None:
        templates = self.state.storage.list_templates()
        template_options = {t.id: t.name for t in templates}

        with ui.row().classes("w-full items-start gap-8"):
            # Left column: Form configuration
            with ui.column().classes("flex-1 bg-white p-6 rounded-lg shadow-sm border border-slate-200"):
                header_lbl = ui.label(self.state.t("templates_header")).classes("text-lg font-bold text-slate-800 mb-2")

                template_select = ui.select(
                    options=template_options,
                    value=self.state.active_template.id,
                    label=self.state.t("select_template"),
                    on_change=lambda e: self._on_template_selected(e.value),
                ).classes("w-full mb-3")

                name_input = ui.input(
                    label=self.state.t("template_name"),
                    value=self.state.active_template.name,
                    on_change=lambda e: self._update_active_and_refresh("name", e.value),
                ).classes("w-full mb-2")

                with ui.row().classes("w-full gap-4"):
                    width_input = ui.number(
                        label=self.state.t("width_mm"),
                        value=self.state.active_template.width_mm,
                        format="%.1f",
                        on_change=lambda e: self._update_active_and_refresh("width_mm", float(e.value or 0)),
                    ).classes("flex-1")
                    height_input = ui.number(
                        label=self.state.t("height_mm"),
                        value=self.state.active_template.height_mm,
                        format="%.1f",
                        on_change=lambda e: self._update_active_and_refresh("height_mm", float(e.value or 0)),
                    ).classes("flex-1")

                with ui.row().classes("w-full gap-4 items-center mt-2"):
                    bg_type_select = ui.select(
                        options=["flat_color", "gradient"],
                        value=self.state.active_template.background.type,
                        label=self.state.t("bg_type"),
                        on_change=lambda e: self._on_bg_type_change(e.value),
                    ).classes("flex-1")

                    with ui.row().classes("items-center gap-2"):
                        color_start_lbl = ui.label(self.state.t("color_start")).classes("text-xs text-slate-600")
                        color_start_input = ui.color_input(
                            value=self.state.active_template.background.color_start,
                            on_change=lambda e: self._update_active_and_refresh("color_start", e.value),
                        ).props("dense")

                self.color_end_row = ui.row().classes("w-full gap-4 items-center")
                with self.color_end_row:
                    color_end_lbl = ui.label(self.state.t("color_end")).classes("text-xs text-slate-600")
                    color_end_input = ui.color_input(
                        value=self.state.active_template.background.color_end or "#1E293B",
                        on_change=lambda e: self._update_active_and_refresh("color_end", e.value),
                    ).props("dense")
                    gradient_angle_input = ui.number(
                        label=self.state.t("gradient_angle"),
                        value=self.state.active_template.background.gradient_angle_deg,
                        on_change=lambda e: self._update_active_and_refresh("gradient_angle_deg", float(e.value or 0)),
                    ).classes("w-32")

                self.color_end_row.set_visibility(self.state.active_template.background.type == "gradient")

                header_text = self.state.active_template.text_blocks[0].text if self.state.active_template.text_blocks else ""
                sub_text = self.state.active_template.text_blocks[1].text if len(self.state.active_template.text_blocks) > 1 else ""

                header_text_input = ui.input(
                    label=self.state.t("header_text"),
                    value=header_text,
                    on_change=lambda e: self._update_text_block(0, e.value),
                ).classes("w-full mt-2")

                sub_text_input = ui.input(
                    label=self.state.t("sub_text"),
                    value=sub_text,
                    on_change=lambda e: self._update_text_block(1, e.value),
                ).classes("w-full")

                barcode_checkbox = ui.checkbox(
                    self.state.t("show_barcode"),
                    value=self.state.active_template.code_box.show_barcode,
                    on_change=lambda e: self._update_active_and_refresh("show_barcode", e.value),
                ).classes("mt-2")

                save_btn = ui.button(
                    self.state.t("save_template"),
                    icon="save",
                    on_click=self._save_current_template,
                ).classes("mt-4 w-full bg-sky-600 text-white")

            # Right column: Live preview
            with ui.column().classes("flex-1 items-center"):
                with ui.card().classes("w-full p-4 items-center justify-center bg-slate-100 border border-slate-300"):
                    preview_lbl = ui.label(self.state.t("live_preview")).classes("text-sm font-semibold text-slate-700 self-start mb-2")
                    self.preview_container = ui.html().classes("w-full flex justify-center overflow-auto shadow-md p-2 bg-white rounded")
                    self._refresh_preview()

        # Re-apply text labels when language changes without page reload
        def update_labels() -> None:
            header_lbl.text = self.state.t("templates_header")
            template_select.props(f'label="{self.state.t("select_template")}"')
            name_input.props(f'label="{self.state.t("template_name")}"')
            width_input.props(f'label="{self.state.t("width_mm")}"')
            height_input.props(f'label="{self.state.t("height_mm")}"')
            bg_type_select.props(f'label="{self.state.t("bg_type")}"')
            color_start_lbl.text = self.state.t("color_start")
            color_end_lbl.text = self.state.t("color_end")
            gradient_angle_input.props(f'label="{self.state.t("gradient_angle")}"')
            header_text_input.props(f'label="{self.state.t("header_text")}"')
            sub_text_input.props(f'label="{self.state.t("sub_text")}"')
            barcode_checkbox.text = self.state.t("show_barcode")
            save_btn.text = self.state.t("save_template")
            preview_lbl.text = self.state.t("live_preview")

        self.state.register_lang_listener(update_labels)

    def _on_template_selected(self, template_id: str) -> None:
        self.state.active_template = self.state.storage.load_template(template_id)
        self._refresh_preview()

    def _on_bg_type_change(self, bg_type: str) -> None:
        self._update_active_and_refresh("bg_type", bg_type)
        self.color_end_row.set_visibility(bg_type == "gradient")

    def _update_active_and_refresh(self, field_name: str, value: Any) -> None:
        tmpl = self.state.active_template
        if field_name == "name":
            tmpl.name = str(value)
        elif field_name == "width_mm":
            new_w = max(40.0, float(value or 40.0))
            tmpl.width_mm = new_w
            # Auto-fit code_box to boundary width
            cb = tmpl.code_box
            if cb.width_mm > new_w - 10.0:
                cb.width_mm = max(30.0, new_w - 10.0)
            if cb.x_mm + cb.width_mm > new_w - 4.0:
                cb.x_mm = max(4.0, new_w - cb.width_mm - 6.0)
            # Auto-fit text block margins to boundary width
            for tb in tmpl.text_blocks:
                if tb.x_mm > new_w * 0.4:
                    tb.x_mm = max(8.0, new_w * 0.1)

        elif field_name == "height_mm":
            new_h = max(30.0, float(value or 30.0))
            tmpl.height_mm = new_h
            # Auto-fit code_box to boundary height
            cb = tmpl.code_box
            if cb.height_mm > new_h * 0.45:
                cb.height_mm = max(14.0, new_h * 0.35)
            if cb.y_mm + cb.height_mm > new_h - 4.0:
                cb.y_mm = max(6.0, new_h - cb.height_mm - 6.0)

        elif field_name == "bg_type":
            tmpl.background.type = str(value)
        elif field_name == "color_start":
            tmpl.background.color_start = str(value)
        elif field_name == "color_end":
            tmpl.background.color_end = str(value)
        elif field_name == "gradient_angle_deg":
            tmpl.background.gradient_angle_deg = float(value or 0.0)
        elif field_name == "show_barcode":
            tmpl.code_box.show_barcode = bool(value)

        self._refresh_preview()

    def _update_text_block(self, index: int, text_value: str) -> None:
        while len(self.state.active_template.text_blocks) <= index:
            self.state.active_template.text_blocks.append(
                TextBlockConfig(
                    id=f"tb_{index}",
                    text="",
                    x_mm=10.0,
                    y_mm=20.0 + (index * 12.0),
                    font_size_pt=12.0,
                    color_hex="#FFFFFF",
                    font_family="Helvetica",
                )
            )
        self.state.active_template.text_blocks[index].text = text_value
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        svg_content = render_voucher_svg(
            template=self.state.active_template,
            sample_code="KPN-25W-12-8K",
            assets_dir=self.state.storage.assets_dir,
        )
        self.preview_container.content = svg_content

    def _save_current_template(self) -> None:
        self.state.storage.save_template(self.state.active_template)
        ui.notify(self.state.t("template_saved"), type="positive")