"""Batch Forge view module for generating multi-variant voucher campaigns."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from nicegui import run, ui

from voucher_forge.code_engine import CodeEngine
from voucher_forge.packer import pack_vouchers
from voucher_forge.renderer import render_bundle_pdf, render_voucher_svg
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

    def render(self) -> None:
        templates = self.state.storage.list_templates()
        template_options = {t.id: t.name for t in templates}

        with ui.column().classes(
            "w-full max-w-4xl mx-auto bg-white p-8 rounded-lg shadow-sm border border-slate-200"
        ):
            self.header_lbl = ui.label(self.state.t("forge_header")).classes(
                "text-xl font-bold text-slate-800 mb-4"
            )

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
    
    def _render_variant_svg(self, row: VariantRow) -> str:
        tmpl = self.state.storage.load_template(self.template_select.value)
        overrides = {}
        if len(tmpl.text_blocks) > 0:
            overrides[tmpl.text_blocks[0].id] = row.title
        if len(tmpl.text_blocks) > 1:
            overrides[tmpl.text_blocks[1].id] = row.sub_text

        # Obsługa jawnego zdjęcia grafiki (__NONE__) lub pozostawienia domyślnej
        bg_override = "__NONE__" if row.bg_asset == "none" else (row.bg_asset or None)
        logo_override = "__NONE__" if row.logo_asset == "none" else (row.logo_asset or None)

        return render_voucher_svg(
            template=tmpl,
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
                    # Mini preview SVG container
                    preview_box = ui.html(
                        self._render_variant_svg(row)
                    ).classes(
                        "w-44 border border-slate-200 rounded bg-white p-1 shrink-0 self-center"
                    )
                    self.preview_containers[idx] = preview_box

                    # Inputs Column
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

                        # Per-variant asset & color selectors
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

    def _update_summary(self) -> None:
        total = sum(r.count for r in self.variants)
        tmpl = self.state.storage.load_template(self.template_select.value)

        v_area = max(100.0, tmpl.width_mm * tmpl.height_mm)
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
        self.template_select.props(f'label="{self.state.t("select_template")}"')
        self.b_id.props(f'label="{self.state.t("bundle_id")}"')
        self.b_name.props(f'label="{self.state.t("bundle_name")}"')
        self.b_prefix.props(f'label="{self.state.t("code_prefix")}"')
        self.b_validity.props(f'label="{self.state.t("validity_months")}"')
        self.add_btn.text = self.state.t("add_variant")
        self.export_btn.text = self.state.t("generate_and_export")
        self._update_summary()
        self._render_variants_table()

    async def _handle_generation(self) -> None:
        try:
            variant_tuples = [
                (r.title.strip(), r.sub_text.strip(), r.count, r.bg_asset, r.logo_asset, r.bg_color)
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

            template = self.state.storage.load_template(self.template_select.value)
            items_to_pack = [
                (v.code, template.width_mm, template.height_mm)
                for v in bundle.vouchers
            ]
            packing_result = pack_vouchers(items_to_pack, margin_mm=8.0, spacing_mm=4.0)

            output_pdf = self.state.storage.exports_dir / f"{bundle.id}.pdf"
            templates_map = {template.id: template}
            vouchers_map = {v.code: v for v in bundle.vouchers}

            await run.cpu_bound(
                render_bundle_pdf,
                packing_result=packing_result,
                templates_map=templates_map,
                vouchers_map=vouchers_map,
                output_pdf_path=output_pdf,
                assets_dir=self.state.storage.assets_dir,
            )

            ui.notify(
                self.state.t("bundle_success").format(count=len(bundle.vouchers)),
                type="positive",
            )
            ui.download(f"/exports/{output_pdf.name}")

        except (ValueError, OSError, RuntimeError) as exc:
            ui.notify(f"Generation Error: {exc}", type="negative")