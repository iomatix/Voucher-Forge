"""Batch Forge view module for generating multi-variant voucher campaigns."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from nicegui import run, ui

from voucher_forge.code_engine import CodeEngine
from voucher_forge.models import CampaignPreset, VariantPreset
from voucher_forge.packer import pack_vouchers
from voucher_forge.renderer import render_bundle_html, render_voucher_svg
from voucher_forge.ui.state import AppState


@dataclass
class VariantRow:
    title: str
    sub_text: str
    count: int
    bg_asset: str | None = None
    logo_asset: str | None = None
    bg_color: str | None = None


class BatchForgeView:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.preview_containers: dict[int, ui.html] = {}
        self.print_scale_val: float = 1.0
        self.variants: list[VariantRow] = [
            VariantRow("DINNER FOR TWO", "Includes starter, main course, and dessert", 3),
            VariantRow("RELAX MASSAGE", "60-minute full body hot stone session", 2),
        ]

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

    def _get_preset_options(self) -> dict[str, str]:
        presets = self.state.storage.list_presets()
        options = {"": self.state.t("preset_empty_option")}
        for p in presets:
            options[p.id] = f"{p.name} ({p.id})"
        return options

    def render(self) -> None:
        templates = self.state.storage.list_templates()
        template_options = {t.id: t.name for t in templates}

        with ui.column().classes(
            "w-full max-w-4xl mx-auto bg-white p-8 rounded-lg shadow-sm border border-slate-200"
        ):
            self.header_lbl = ui.label(self.state.t("forge_header")).classes(
                "text-xl font-bold text-slate-800 mb-2"
            )

            # --- Preset Management Toolbar ---
            with ui.row().classes(
                "w-full items-center gap-3 p-3 mb-4 bg-slate-50 border border-slate-200 rounded"
            ):
                self.preset_select = ui.select(
                    options=self._get_preset_options(),
                    value="",
                    label=self.state.t("load_preset"),
                    on_change=lambda e: self._on_preset_selected(str(e.value or "")),
                ).classes("flex-1 text-sm")

                self.save_preset_btn = ui.button(
                    self.state.t("save_preset"),
                    icon="save",
                    on_click=self._save_current_preset,
                ).classes("bg-sky-600 text-white text-xs py-2 px-3")

                self.save_as_new_preset_btn = ui.button(
                    self.state.t("save_as_new_preset"),
                    icon="add_circle",
                    on_click=self._save_as_new_preset,
                ).classes("bg-slate-700 text-white text-xs py-2 px-3")

            self.template_select = ui.select(
                options=template_options,
                value=self.state.active_template.id,
                label=self.state.t("select_template"),
                on_change=lambda _: self._on_template_change(),
            ).classes("w-full mb-3")

            with ui.row().classes("w-full gap-4"):
                self.b_id = ui.input(
                    label=self.state.t("bundle_id"),
                    value=f"campaign_{datetime.now(UTC).date().strftime('%Y%m%d')}",
                ).classes("flex-1")

                self.b_name = ui.input(
                    label=self.state.t("bundle_name"),
                    value="Spring Multi-Offer Campaign",
                ).classes("flex-1")

            with ui.row().classes("w-full gap-4"):
                self.b_prefix = ui.input(
                    label=self.state.t("code_prefix"),
                    value="KPN",
                ).classes("flex-1 uppercase font-mono")

                self.b_validity = ui.number(
                    label=self.state.t("validity_months"),
                    value=12,
                    min=1,
                    max=99,
                    step=1,
                ).classes("flex-1")

            # --- Layout & Print Scale Controls ---
            with ui.row().classes(
                "w-full items-center justify-between p-3 mt-2 bg-slate-50 border border-slate-200 rounded"
            ):
                with ui.column().classes("gap-0"):
                    self.scale_label = ui.label(
                        f"{self.state.t('print_scale')}: {int(self.print_scale_val * 100)}%"
                    ).classes("text-xs font-semibold text-slate-700")

                    self.scale_desc = ui.label(
                        self.state.t("print_scale_desc")
                    ).classes("text-[11px] text-slate-500")

                with ui.row().classes("items-center gap-3"):
                    self.scale_slider = ui.slider(
                        min=0.3,
                        max=1.0,
                        step=0.05,
                        value=self.print_scale_val,
                        on_change=self._on_scale_change,
                    ).classes("w-48")
                    self.scale_pct_badge = ui.badge(
                        f"{int(self.print_scale_val * 100)}%", color="slate-700"
                    ).classes("text-xs font-mono")

            ui.separator().classes("my-3")

            # Variants Matrix
            self.variants_container = ui.column().classes("w-full gap-3")
            self._render_variants_table()

            self.add_btn = ui.button(
                self.state.t("add_variant"),
                icon="add",
                on_click=self._add_variant_row,
            ).classes("bg-slate-700 text-white text-xs mt-2 self-start")

            # Capacity / Sheet Estimation Badge
            self.summary_badge = ui.label("").classes(
                "w-full text-center py-2 px-3 mt-4 bg-slate-100 rounded text-sm font-semibold text-slate-700"
            )
            self._update_summary()

            self.export_btn = ui.button(
                self.state.t("generate_and_export"),
                icon="print",
                on_click=self._handle_generation,
            ).classes("w-full bg-emerald-600 text-white py-3 font-semibold mt-4")

        self.state.register_lang_listener(self._update_labels)

    def _on_scale_change(self, e: Any) -> None:
        self.print_scale_val = round(float(e.value or 1.0), 2)
        pct_text = f"{int(self.print_scale_val * 100)}%"
        self.scale_label.text = f"{self.state.t('print_scale')}: {pct_text}"
        self.scale_pct_badge.text = pct_text
        self._update_summary()

    def _render_variant_svg(self, row: VariantRow) -> str:
        template = self.state.storage.load_template(self.template_select.value)
        overrides = {}
        if len(template.text_blocks) > 0:
            overrides[template.text_blocks[0].id] = row.title
        if len(template.text_blocks) > 1:
            overrides[template.text_blocks[1].id] = row.sub_text

        bg_override = "__NONE__" if row.bg_asset == "none" else (row.bg_asset or None)
        logo_override = "__NONE__" if row.logo_asset == "none" else (row.logo_asset or None)

        return render_voucher_svg(
            template=template,
            sample_code="KPN-25W-12-8K",
            assets_dir=self.state.storage.assets_dir,
            text_overrides=overrides,
            bg_asset_override=bg_override,
            logo_asset_override=logo_override,
            bg_color_override=row.bg_color,
        )

    def _render_variants_table(self) -> None:
        self.variants_container.clear()
        self.preview_containers.clear()
        raw_assets = self._get_available_assets()
        asset_options = {
            "": self.state.t("asset_default"),
            "none": self.state.t("asset_none"),
        }
        for item in raw_assets:
            asset_options[item] = item

        with self.variants_container:
            for idx, row in enumerate(self.variants):
                with (
                    ui.card().classes("w-full p-4 bg-slate-50 border border-slate-200"),
                    ui.row().classes("w-full items-start gap-4"),
                ):
                    preview_box = ui.html(
                        self._render_variant_svg(row)
                    ).classes(
                        "w-44 border border-slate-200 rounded bg-white p-1 shrink-0 self-center"
                    )
                    self.preview_containers[idx] = preview_box

                    with ui.column().classes("flex-1 gap-2"):
                        with ui.row().classes("w-full items-center gap-3"):
                            ui.input(
                                value=row.title,
                                label=self.state.t("variant_title"),
                                on_change=lambda e, r=row, i=idx: self._update_row_field(
                                    r, i, "title", e.value
                                ),
                            ).classes("flex-1 font-semibold")

                            ui.number(
                                value=row.count,
                                label=self.state.t("variant_qty"),
                                min=1,
                                max=31,
                                step=1,
                                on_change=lambda e, r=row: self._set_variant_count(
                                    r, int(e.value or 1)
                                ),
                            ).classes("w-24")

                            ui.button(
                                icon="delete",
                                color="negative",
                                on_click=lambda _, i=idx: self._remove_variant_row(i),
                            ).props("flat dense").classes("mt-2")

                        ui.input(
                            value=row.sub_text,
                            label=self.state.t("sub_text"),
                            on_change=lambda e, r=row, i=idx: self._update_row_field(
                                r, i, "sub_text", e.value
                            ),
                        ).classes("w-full text-sm")

                        with ui.row().classes("w-full gap-2 mt-1 items-center"):
                            ui.select(
                                options=asset_options,
                                value=row.bg_asset or "",
                                label=self.state.t("variant_bg_asset"),
                                on_change=lambda e, r=row, i=idx: self._update_row_field(
                                    r, i, "bg_asset", e.value
                                ),
                            ).classes("flex-1 text-xs")

                            ui.select(
                                options=asset_options,
                                value=row.logo_asset or "",
                                label=self.state.t("variant_logo_asset"),
                                on_change=lambda e, r=row, i=idx: self._update_row_field(
                                    r, i, "logo_asset", e.value
                                ),
                            ).classes("flex-1 text-xs")

                            with ui.row().classes("items-center gap-1 w-36"):
                                ui.input(
                                    label=self.state.t("variant_bg_color"),
                                    value=row.bg_color or "",
                                    placeholder=self.state.t("variant_color_default"),
                                    on_change=lambda e, r=row, i=idx: self._update_row_field(
                                        r, i, "bg_color", e.value or None
                                    ),
                                ).classes("flex-1 text-xs")
                                ui.color_picker(
                                    on_pick=lambda e, r=row, i=idx: self._update_row_field(
                                        r, i, "bg_color", e.color
                                    )
                                )

    def _update_row_field(
        self, row: VariantRow, index: int, field_name: str, value: Any
    ) -> None:
        setattr(row, field_name, value)
        if index in self.preview_containers:
            self.preview_containers[index].content = self._render_variant_svg(row)

    def _set_variant_count(self, row: VariantRow, count: int) -> None:
        row.count = count
        self._update_summary()

    def _add_variant_row(self) -> None:
        self.variants.append(
            VariantRow(
                f"OFFER VARIANT {len(self.variants) + 1}",
                "Special promotional service package",
                2,
            )
        )
        self._render_variants_table()
        self._update_summary()

    def _remove_variant_row(self, index: int) -> None:
        if len(self.variants) > 1:
            self.variants.pop(index)
            self._render_variants_table()
            self._update_summary()

    def _on_template_change(self) -> None:
        self._update_summary()
        self._render_variants_table()

    def _on_preset_selected(self, preset_id: str) -> None:
        if not preset_id:
            return
        try:
            preset = self.state.storage.load_preset(preset_id)
            self.b_id.value = preset.id
            self.b_name.value = preset.name
            self.b_prefix.value = preset.prefix
            self.b_validity.value = preset.validity_months
            if preset.template_id in self.template_select.options:
                self.template_select.value = preset.template_id

            self.variants = [
                VariantRow(
                    title=v.title,
                    sub_text=v.sub_text,
                    count=v.count,
                    bg_asset=v.bg_asset,
                    logo_asset=v.logo_asset,
                    bg_color=v.bg_color,
                )
                for v in preset.variants
            ]
            self._update_summary()
            self._render_variants_table()
            ui.notify(
                self.state.t("preset_loaded").format(name=preset.name),
                type="positive",
            )
        except Exception as exc:
            ui.notify(f"Error loading preset: {exc}", type="negative")

    def _save_current_preset(self) -> None:
        pid = str(self.b_id.value or "").strip()
        if not pid:
            ui.notify(self.state.t("preset_enter_id"), type="warning")
            return

        preset = CampaignPreset(
            id=pid,
            name=str(self.b_name.value or "").strip() or pid,
            template_id=str(self.template_select.value),
            prefix=str(self.b_prefix.value or "OFF").strip(),
            validity_months=int(self.b_validity.value or 12),
            variants=[
                VariantPreset(
                    title=r.title,
                    sub_text=r.sub_text,
                    count=r.count,
                    bg_asset=r.bg_asset,
                    logo_asset=r.logo_asset,
                    bg_color=r.bg_color,
                )
                for r in self.variants
            ],
        )
        self.state.storage.save_preset(preset)
        self.preset_select.options = self._get_preset_options()
        self.preset_select.value = preset.id
        self.preset_select.update()
        ui.notify(
            self.state.t("preset_saved").format(name=preset.name),
            type="positive",
        )

    def _save_as_new_preset(self) -> None:
        p_name = str(self.b_name.value or "").strip() or "Custom Campaign"
        base_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", p_name.lower()).strip("_")
        candidate_id = f"preset_{base_slug}" if base_slug else "preset_custom"

        existing_ids = {p.id for p in self.state.storage.list_presets()}
        counter = 1
        final_id = candidate_id
        while final_id in existing_ids:
            final_id = f"{candidate_id}_{counter}"
            counter += 1

        self.b_id.value = final_id
        self._save_current_preset()

    def _update_summary(self) -> None:
        total = sum(r.count for r in self.variants)
        template = self.state.storage.load_template(self.template_select.value)

        scale = getattr(self, "print_scale_val", 1.0)
        scaled_w = template.width_mm * scale
        scaled_h = template.height_mm * scale
        v_area = max(50.0, scaled_w * scaled_h)

        capacity_per_sheet = max(1, math.floor(52000.0 / v_area))
        sheets = max(1, math.ceil(total / capacity_per_sheet))

        self.summary_badge.text = self.state.t("summary_counter").format(
            total=total, sheets=sheets
        )

        if total > 31 or total < 1:
            self.summary_badge.classes(
                replace="w-full text-center py-2 px-3 mt-4 bg-rose-100 text-rose-700 rounded text-sm font-semibold"
            )
        else:
            self.summary_badge.classes(
                replace="w-full text-center py-2 px-3 mt-4 bg-slate-100 text-slate-700 rounded text-sm font-semibold"
            )

    def _update_labels(self) -> None:
        self.header_lbl.text = self.state.t("forge_header")
        self.preset_select.props(f'label="{self.state.t("load_preset")}"')
        self.preset_select.options = self._get_preset_options()
        self.preset_select.update()

        self.save_preset_btn.text = self.state.t("save_preset")
        self.save_as_new_preset_btn.text = self.state.t("save_as_new_preset")

        self.template_select.props(f'label="{self.state.t("select_template")}"')
        self.b_id.props(f'label="{self.state.t("bundle_id")}"')
        self.b_name.props(f'label="{self.state.t("bundle_name")}"')
        self.b_prefix.props(f'label="{self.state.t("code_prefix")}"')
        self.b_validity.props(f'label="{self.state.t("validity_months")}"')

        pct_text = f"{int(self.print_scale_val * 100)}%"
        self.scale_label.text = f"{self.state.t('print_scale')}: {pct_text}"
        self.scale_desc.text = self.state.t("print_scale_desc")
        self.scale_pct_badge.text = pct_text

        self.add_btn.text = self.state.t("add_variant")
        self.export_btn.text = self.state.t("generate_and_export")
        self._update_summary()
        self._render_variants_table()

    async def _handle_generation(self) -> None:
        try:
            template = self.state.storage.load_template(self.template_select.value)
            t_id1 = template.text_blocks[0].id if len(template.text_blocks) > 0 else "tb1"
            t_id2 = template.text_blocks[1].id if len(template.text_blocks) > 1 else "tb2"

            variant_tuples = [
                (
                    r.title.strip(),
                    r.sub_text.strip(),
                    r.count,
                    r.bg_asset,
                    r.logo_asset,
                    r.bg_color,
                    t_id1,
                    t_id2,
                )
                for r in self.variants
                if r.title.strip()
            ]
            bundle = CodeEngine.generate_campaign_bundle(
                bundle_id=self.b_id.value,
                bundle_name=self.b_name.value,
                template_id=self.template_select.value,
                variants=variant_tuples,
                prefix=self.b_prefix.value,
                validity_months=int(self.b_validity.value or 99),
            )
            self.state.storage.save_bundle(bundle)

            items_to_pack = [
                (v.code, template.width_mm, template.height_mm)
                for v in bundle.vouchers
            ]
            packing_result = pack_vouchers(
                items=items_to_pack,
                margin_mm=8.0,
                spacing_mm=4.0,
                scale_factor=self.print_scale_val,
            )

            output_html = self.state.storage.exports_dir / f"{bundle.id}.html"
            templates_map = {template.id: template}
            vouchers_map = {v.code: v for v in bundle.vouchers}

            await run.cpu_bound(
                render_bundle_html,
                packing_result=packing_result,
                templates_map=templates_map,
                vouchers_map=vouchers_map,
                output_html_path=output_html,
                assets_dir=self.state.storage.assets_dir,
            )

            ui.notify(
                self.state.t("bundle_success").format(count=len(bundle.vouchers)),
                type="positive",
            )

            export_url = f"/exports/{output_html.name}"
            ui.download(export_url)
            ui.navigate.to(export_url, new_tab=True)

        except (ValueError, OSError, RuntimeError) as exc:
            ui.notify(f"Generation Error: {exc}", type="negative")