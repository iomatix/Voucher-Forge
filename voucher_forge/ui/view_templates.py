"""Template Studio view module for visual configuration and live SVG preview."""

from __future__ import annotations

import re
from typing import Any

from nicegui import events, ui

from voucher_forge.models import LogoConfig
from voucher_forge.renderer import render_voucher_svg
from voucher_forge.ui.state import AppState


class TemplateStudioView:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def _get_available_assets(self) -> list[str]:
        assets_dir = self.state.storage.assets_dir
        if not assets_dir.exists():
            return []
        valid_exts = {".png", ".jpg", ".jpeg", ".svg"}
        return [
            f.name
            for f in assets_dir.iterdir()
            if f.is_file() and f.suffix.lower() in valid_exts
        ]

    def render(self) -> None:
        templates = self.state.storage.list_templates()
        template_options = {t.id: t.name for t in templates}

        with ui.row().classes("w-full gap-6 items-start"):
            # Configuration Column
            with ui.column().classes(
                "flex-1 bg-white p-6 rounded-lg shadow-sm border border-slate-200"
            ):
                self.header_lbl = ui.label(
                    self.state.t("templates_header")
                ).classes("text-xl font-bold text-slate-800 mb-2")

                self.template_select = ui.select(
                    options=template_options,
                    value=self.state.active_template.id,
                    label=self.state.t("select_template"),
                    on_change=lambda e: self._on_template_selected(e.value),
                ).classes("w-full mb-2")

                self.name_input = ui.input(
                    label=self.state.t("template_name"),
                    value=self.state.active_template.name,
                    on_change=lambda e: self._update_active_and_refresh("name", e.value),
                ).classes("w-full mb-2")

                with ui.row().classes("w-full gap-4"):
                    self.width_input = ui.number(
                        label=self.state.t("width_mm"),
                        value=self.state.active_template.width_mm,
                        format="%.1f",
                        on_change=lambda e: self._update_active_and_refresh(
                            "width_mm", e.value
                        ),
                    ).classes("flex-1")

                    self.height_input = ui.number(
                        label=self.state.t("height_mm"),
                        value=self.state.active_template.height_mm,
                        format="%.1f",
                        on_change=lambda e: self._update_active_and_refresh(
                            "height_mm", e.value
                        ),
                    ).classes("flex-1")

                # Background Section
                with ui.row().classes("w-full gap-4 items-center"):
                    self.bg_type_select = ui.select(
                        options={
                            "flat_color": "Flat Color",
                            "gradient": "Gradient",
                            "image": "Image",
                        },
                        value=self.state.active_template.background.type,
                        label=self.state.t("bg_type"),
                        on_change=lambda e: self._update_active_and_refresh(
                            "bg_type", e.value
                        ),
                    ).classes("flex-1")

                    with ui.row().classes("items-center gap-2 flex-1"):
                        self.color_start_input = ui.input(
                            label=self.state.t("color_start"),
                            value=self.state.active_template.background.color_start,
                            on_change=lambda e: self._update_active_and_refresh(
                                "color_start", e.value
                            ),
                        ).classes("flex-1")
                        ui.color_picker(
                            on_pick=lambda e: self._update_active_and_refresh(
                                "color_start", e.color
                            )
                        )

                # Background Image asset dropdown
                available_assets = self._get_available_assets()
                self.asset_select = ui.select(
                    options=[""] + available_assets,
                    value=self.state.active_template.background.image_asset or "",
                    label=self.state.t("select_image_asset"),
                    on_change=lambda e: self._update_active_and_refresh(
                        "image_asset", e.value
                    ),
                ).classes("w-full mb-2")
                self.asset_select.set_visibility(
                    self.state.active_template.background.type == "image"
                )

                # Gradient Options
                self.grad_container = ui.row().classes("w-full gap-4 items-center")
                with self.grad_container:
                    with ui.row().classes("items-center gap-2 flex-1"):
                        self.color_end_input = ui.input(
                            label=self.state.t("color_end"),
                            value=self.state.active_template.background.color_end
                            or "#1E293B",
                            on_change=lambda e: self._update_active_and_refresh(
                                "color_end", e.value
                            ),
                        ).classes("flex-1")
                        ui.color_picker(
                            on_pick=lambda e: self._update_active_and_refresh(
                                "color_end", e.color
                            )
                        )

                    self.grad_angle_input = ui.number(
                        label=self.state.t("gradient_angle"),
                        value=self.state.active_template.background.gradient_angle_deg,
                        on_change=lambda e: self._update_active_and_refresh(
                            "gradient_angle_deg", e.value
                        ),
                    ).classes("flex-1")

                self.grad_container.set_visibility(
                    self.state.active_template.background.type == "gradient"
                )

                # Logo Section
                with ui.row().classes("w-full items-center justify-between mt-2"):
                    self.logo_checkbox = ui.checkbox(
                        "Dołącz Logo",
                        value=self.state.active_template.logo is not None,
                        on_change=lambda e: self._toggle_logo(bool(e.value)),
                    )

                self.logo_container = ui.column().classes("w-full gap-2")
                with self.logo_container:
                    self.logo_asset_select = ui.select(
                        options=[""] + available_assets,
                        value=(
                            self.state.active_template.logo.asset_filename
                            if self.state.active_template.logo
                            else ""
                        ),
                        label="Plik Logo",
                        on_change=lambda e: self._update_logo_asset(e.value),
                    ).classes("w-full")

                self.logo_container.set_visibility(
                    self.state.active_template.logo is not None
                )

                # Text Configuration
                tb_h = (
                    self.state.active_template.text_blocks[0]
                    if len(self.state.active_template.text_blocks) > 0
                    else None
                )
                tb_s = (
                    self.state.active_template.text_blocks[1]
                    if len(self.state.active_template.text_blocks) > 1
                    else None
                )

                t1_val = tb_h.text if tb_h else ""
                t1_col = tb_h.color_hex if tb_h else "#FFFFFF"
                t2_val = tb_s.text if tb_s else ""
                t2_col = tb_s.color_hex if tb_s else "#A1A1AA"

                # Header text + color
                with ui.row().classes("w-full items-center gap-2 mb-2"):
                    self.header_text_input = ui.input(
                        label=self.state.t("header_text"),
                        value=t1_val,
                        on_change=lambda e: self._update_text_block(0, "text", e.value),
                    ).classes("flex-1")

                    self.header_color_input = ui.input(
                        label=self.state.t("text_color"),
                        value=t1_col,
                        on_change=lambda e: self._update_text_block(
                            0, "color_hex", e.value
                        ),
                    ).classes("w-32")
                    ui.color_picker(
                        on_pick=lambda e: self._update_text_block(0, "color_hex", e.color)
                    )

                # Subtitle text + color
                with ui.row().classes("w-full items-center gap-2 mb-2"):
                    self.sub_text_input = ui.input(
                        label=self.state.t("sub_text"),
                        value=t2_val,
                        on_change=lambda e: self._update_text_block(1, "text", e.value),
                    ).classes("flex-1")

                    self.sub_color_input = ui.input(
                        label=self.state.t("text_color"),
                        value=t2_col,
                        on_change=lambda e: self._update_text_block(
                            1, "color_hex", e.value
                        ),
                    ).classes("w-32")
                    ui.color_picker(
                        on_pick=lambda e: self._update_text_block(1, "color_hex", e.color)
                    )

                # Barcode / Code Box Geometry Section
                with (
                    ui.expansion(
                        self.state.t("code_box_header"), icon="qr_code"
                    ).classes("w-full bg-slate-50 border border-slate-200 rounded my-2"),
                    ui.column().classes("w-full p-2 gap-2"),
                ):
                    self.barcode_checkbox = ui.checkbox(
                        self.state.t("show_barcode"),
                        value=self.state.active_template.code_box.show_barcode,
                        on_change=lambda e: self._update_active_and_refresh(
                            "show_barcode", e.value
                        ),
                    )

                    with ui.row().classes("w-full gap-2"):
                        self.cb_x_input = ui.number(
                            label=self.state.t("pos_x_mm"),
                            value=self.state.active_template.code_box.x_mm,
                            format="%.1f",
                            min=0.0,
                            step=1.0,
                            on_change=lambda e: self._update_active_and_refresh(
                                "cb_x", e.value
                            ),
                        ).classes("flex-1")

                        self.cb_y_input = ui.number(
                            label=self.state.t("pos_y_mm"),
                            value=self.state.active_template.code_box.y_mm,
                            format="%.1f",
                            min=0.0,
                            step=1.0,
                            on_change=lambda e: self._update_active_and_refresh(
                                "cb_y", e.value
                            ),
                        ).classes("flex-1")

                    with ui.row().classes("w-full gap-2"):
                        self.cb_w_input = ui.number(
                            label=self.state.t("box_width_mm"),
                            value=self.state.active_template.code_box.width_mm,
                            format="%.1f",
                            min=20.0,
                            step=1.0,
                            on_change=lambda e: self._update_active_and_refresh(
                                "cb_w", e.value
                            ),
                        ).classes("flex-1")

                        self.cb_h_input = ui.number(
                            label=self.state.t("box_height_mm"),
                            value=self.state.active_template.code_box.height_mm,
                            format="%.1f",
                            min=10.0,
                            step=1.0,
                            on_change=lambda e: self._update_active_and_refresh(
                                "cb_h", e.value
                            ),
                        ).classes("flex-1")

                # Asset Upload Section
                ui.label(self.state.t("upload_asset")).classes(
                    "text-sm font-semibold text-slate-700"
                )
                ui.label(self.state.t("upload_asset_desc")).classes(
                    "text-xs text-slate-500 mb-2"
                )
                ui.upload(
                    on_upload=self._handle_asset_upload,
                    auto_upload=True,
                    max_file_size=5_000_000,
                ).props('accept=".png,.jpg,.jpeg,.svg" flat bordered').classes(
                    "w-full mb-4"
                )

                with ui.row().classes("w-full gap-3"):
                    self.save_btn = ui.button(
                        self.state.t("save_template"),
                        icon="save",
                        on_click=self._save_current_template,
                    ).classes("flex-1 bg-sky-600 text-white py-2 font-semibold")

                    self.save_as_new_btn = ui.button(
                        self.state.t("save_as_new"),
                        icon="add_circle",
                        on_click=self._save_as_new_template,
                    ).classes("flex-1 bg-slate-700 text-white py-2 font-semibold")

            # Preview Column
            with ui.column().classes(
                "flex-1 bg-white p-6 rounded-lg shadow-sm border border-slate-200 sticky top-6"
            ):
                self.preview_lbl = ui.label(
                    self.state.t("live_preview")
                ).classes("text-lg font-bold text-slate-800 mb-4")
                self.preview_container = ui.html("").classes(
                    "w-full border border-slate-100 rounded p-2 bg-slate-50"
                )
                self._refresh_preview()

        self.state.register_lang_listener(self._update_labels)

    async def _handle_asset_upload(self, e: events.UploadEventArguments) -> None:
        file_name = e.file.name
        content = await e.file.read()

        target_path = self.state.storage.assets_dir / file_name
        target_path.write_bytes(content)

        updated_assets = self._get_available_assets()
        options = [""] + updated_assets

        self.asset_select.options = options
        self.logo_asset_select.options = options

        if self.state.active_template.background.type == "image":
            self.state.active_template.background.image_asset = file_name
            self.asset_select.value = file_name

        self.asset_select.update()
        self.logo_asset_select.update()

        self._refresh_preview()
        ui.notify(
            self.state.t("asset_uploaded").format(filename=file_name), type="positive"
        )

    def _toggle_logo(self, enabled: bool) -> None:
        tmpl = self.state.active_template
        if enabled:
            available = self._get_available_assets()
            first_asset = available[0] if available else ""
            tmpl.logo = LogoConfig(
                asset_filename=first_asset,
                x_mm=10.0,
                y_mm=10.0,
                width_mm=24.0,
                height_mm=24.0,
            )
            self.logo_asset_select.value = first_asset
            text_x = 10.0 + 24.0 + 6.0
            for tb in tmpl.text_blocks:
                tb.x_mm = text_x
        else:
            tmpl.logo = None
            for tb in tmpl.text_blocks:
                tb.x_mm = 10.0

        self.logo_container.set_visibility(enabled)
        self._refresh_preview()

    def _update_logo_asset(self, asset_name: str | None) -> None:
        tmpl = self.state.active_template
        if tmpl.logo and asset_name:
            tmpl.logo.asset_filename = asset_name
            self._refresh_preview()

    def _update_active_and_refresh(self, field_name: str, value: Any) -> None:
        tmpl = self.state.active_template
        if field_name == "name":
            tmpl.name = str(value)
        elif field_name == "width_mm":
            new_w = max(40.0, float(value or 40.0))
            tmpl.width_mm = new_w
            cb = tmpl.code_box
            if cb.width_mm > new_w - 10.0:
                cb.width_mm = max(20.0, new_w - 10.0)
            if cb.x_mm + cb.width_mm > new_w - 4.0:
                cb.x_mm = max(2.0, new_w - cb.width_mm - 4.0)

        elif field_name == "height_mm":
            new_h = max(30.0, float(value or 30.0))
            tmpl.height_mm = new_h
            cb = tmpl.code_box
            if cb.height_mm > new_h * 0.5:
                cb.height_mm = max(10.0, new_h * 0.35)
            if cb.y_mm + cb.height_mm > new_h - 4.0:
                cb.y_mm = max(2.0, new_h - cb.height_mm - 4.0)

        elif field_name == "bg_type":
            tmpl.background.type = str(value)
            self.grad_container.set_visibility(str(value) == "gradient")
            self.asset_select.set_visibility(str(value) == "image")
        elif field_name == "image_asset":
            tmpl.background.image_asset = str(value) if value else None
        elif field_name == "color_start":
            tmpl.background.color_start = str(value)
        elif field_name == "color_end":
            tmpl.background.color_end = str(value)
        elif field_name == "gradient_angle_deg":
            tmpl.background.gradient_angle_deg = float(value or 0.0)
        elif field_name == "show_barcode":
            tmpl.code_box.show_barcode = bool(value)
        elif field_name == "cb_x":
            tmpl.code_box.x_mm = max(0.0, float(value or 0.0))
        elif field_name == "cb_y":
            tmpl.code_box.y_mm = max(0.0, float(value or 0.0))
        elif field_name == "cb_w":
            tmpl.code_box.width_mm = max(20.0, float(value or 20.0))
        elif field_name == "cb_h":
            tmpl.code_box.height_mm = max(10.0, float(value or 10.0))

        self._refresh_preview()

    def _update_text_block(self, index: int, field_name: str, value: Any) -> None:
        if index < len(self.state.active_template.text_blocks):
            setattr(
                self.state.active_template.text_blocks[index], field_name, str(value)
            )
            if field_name == "color_hex":
                if index == 0:
                    self.header_color_input.value = str(value)
                elif index == 1:
                    self.sub_color_input.value = str(value)
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        svg_content = render_voucher_svg(
            self.state.active_template,
            sample_code="KPN-25W-12-8K",
            assets_dir=self.state.storage.assets_dir,
        )
        self.preview_container.content = svg_content

    def _refresh_template_dropdown(self) -> None:
        templates = self.state.storage.list_templates()
        self.template_select.options = {t.id: t.name for t in templates}
        self.template_select.value = self.state.active_template.id
        self.template_select.update()

    def _on_template_selected(self, template_id: str) -> None:
        loaded = self.state.storage.load_template(template_id)
        self.state.active_template = loaded
        tmpl = self.state.active_template

        self.name_input.value = tmpl.name
        self.width_input.value = tmpl.width_mm
        self.height_input.value = tmpl.height_mm
        self.bg_type_select.value = tmpl.background.type
        self.color_start_input.value = tmpl.background.color_start
        self.color_end_input.value = tmpl.background.color_end or "#1E293B"
        self.grad_angle_input.value = tmpl.background.gradient_angle_deg

        cb = tmpl.code_box
        self.barcode_checkbox.value = cb.show_barcode
        self.cb_x_input.value = cb.x_mm
        self.cb_y_input.value = cb.y_mm
        self.cb_w_input.value = cb.width_mm
        self.cb_h_input.value = cb.height_mm

        available_assets = self._get_available_assets()
        options = [""] + available_assets
        self.asset_select.options = options
        self.asset_select.value = tmpl.background.image_asset or ""

        self.grad_container.set_visibility(tmpl.background.type == "gradient")
        self.asset_select.set_visibility(tmpl.background.type == "image")

        has_logo = tmpl.logo is not None
        self.logo_checkbox.value = has_logo
        self.logo_asset_select.options = options
        self.logo_asset_select.value = tmpl.logo.asset_filename if tmpl.logo else ""
        self.logo_container.set_visibility(has_logo)

        tb_h = tmpl.text_blocks[0] if len(tmpl.text_blocks) > 0 else None
        tb_s = tmpl.text_blocks[1] if len(tmpl.text_blocks) > 1 else None

        self.header_text_input.value = tb_h.text if tb_h else ""
        self.header_color_input.value = tb_h.color_hex if tb_h else "#FFFFFF"
        self.sub_text_input.value = tb_s.text if tb_s else ""
        self.sub_color_input.value = tb_s.color_hex if tb_s else "#A1A1AA"

        self._refresh_preview()

    def _save_current_template(self) -> None:
        self.state.storage.save_template(self.state.active_template)
        self._refresh_template_dropdown()
        ui.notify(self.state.t("template_saved"), type="positive")

    def _save_as_new_template(self) -> None:
        tmpl = self.state.active_template
        base_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", tmpl.name.lower()).strip("_")
        new_id = f"tmpl_{base_slug}" if base_slug else "tmpl_custom"

        existing_ids = {t.id for t in self.state.storage.list_templates()}
        counter = 1
        candidate_id = new_id
        while candidate_id in existing_ids:
            candidate_id = f"{new_id}_{counter}"
            counter += 1

        tmpl.id = candidate_id
        self.state.storage.save_template(tmpl)
        self._refresh_template_dropdown()
        ui.notify(
            self.state.t("template_created").format(name=tmpl.name), type="positive"
        )

    def _update_labels(self) -> None:
        self.header_lbl.text = self.state.t("templates_header")
        self.preview_lbl.text = self.state.t("live_preview")
        self.template_select.props(f'label="{self.state.t("select_template")}"')
        self.name_input.props(f'label="{self.state.t("template_name")}"')
        self.width_input.props(f'label="{self.state.t("width_mm")}"')
        self.height_input.props(f'label="{self.state.t("height_mm")}"')
        self.bg_type_select.props(f'label="{self.state.t("bg_type")}"')
        self.color_start_input.props(f'label="{self.state.t("color_start")}"')
        self.color_end_input.props(f'label="{self.state.t("color_end")}"')
        self.grad_angle_input.props(f'label="{self.state.t("gradient_angle")}"')
        self.header_text_input.props(f'label="{self.state.t("header_text")}"')
        self.header_color_input.props(f'label="{self.state.t("text_color")}"')
        self.sub_text_input.props(f'label="{self.state.t("sub_text")}"')
        self.sub_color_input.props(f'label="{self.state.t("text_color")}"')
        self.barcode_checkbox.text = self.state.t("show_barcode")
        self.cb_x_input.props(f'label="{self.state.t("pos_x_mm")}"')
        self.cb_y_input.props(f'label="{self.state.t("pos_y_mm")}"')
        self.cb_w_input.props(f'label="{self.state.t("box_width_mm")}"')
        self.cb_h_input.props(f'label="{self.state.t("box_height_mm")}"')
        self.save_btn.text = self.state.t("save_template")
        self.save_as_new_btn.text = self.state.t("save_as_new")
        self.asset_select.props(f'label="{self.state.t("select_image_asset")}"')
        self._refresh_preview()