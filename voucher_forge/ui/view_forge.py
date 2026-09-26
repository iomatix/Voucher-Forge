"""Batch Forge view module for generating voucher series and exporting multi-page PDFs."""

from __future__ import annotations

from datetime import date
from nicegui import run, ui

from voucher_forge.code_engine import CodeEngine
from voucher_forge.packer import pack_vouchers
from voucher_forge.renderer import render_bundle_pdf
from voucher_forge.ui.state import AppState


class BatchForgeView:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def render(self) -> None:
        templates = self.state.storage.list_templates()
        template_options = {t.id: t.name for t in templates}

        with ui.column().classes("w-full max-w-xl mx-auto bg-white p-8 rounded-lg shadow-sm border border-slate-200"):
            header_lbl = ui.label(self.state.t("forge_header")).classes("text-xl font-bold text-slate-800 mb-4")

            template_select = ui.select(
                options=template_options,
                value=self.state.active_template.id,
                label=self.state.t("select_template"),
            ).classes("w-full mb-3")

            b_id = ui.input(
                label=self.state.t("bundle_id"),
                value=f"bundle_{date.today().strftime('%Y%m%d')}",
            ).classes("w-full mb-2")

            b_name = ui.input(
                label=self.state.t("bundle_name"),
                value="Spring Promotion 2026",
            ).classes("w-full mb-2")

            with ui.row().classes("w-full gap-4"):
                b_prefix = ui.input(
                    label=self.state.t("code_prefix"),
                    value="KPN",
                ).classes("flex-1 uppercase font-mono")

                b_count = ui.number(
                    label=self.state.t("count"),
                    value=10,
                    min=1,
                    max=31,
                    step=1,
                ).classes("flex-1")

            b_validity = ui.number(
                label=self.state.t("validity_months"),
                value=12,
                min=1,
                max=99,
                step=1,
            ).classes("w-full mb-4")

            export_btn = ui.button(
                self.state.t("generate_and_export"),
                icon="print",
                on_click=lambda: self._handle_bundle_generation(
                    template_id=template_select.value,
                    bundle_id=b_id.value,
                    bundle_name=b_name.value,
                    prefix=b_prefix.value,
                    count=int(b_count.value or 1),
                    validity=int(b_validity.value or 99),
                ),
            ).classes("w-full bg-emerald-600 text-white py-3 font-semibold")

        def update_labels() -> None:
            header_lbl.text = self.state.t("forge_header")
            template_select.props(f'label="{self.state.t("select_template")}"')
            b_id.props(f'label="{self.state.t("bundle_id")}"')
            b_name.props(f'label="{self.state.t("bundle_name")}"')
            b_prefix.props(f'label="{self.state.t("code_prefix")}"')
            b_count.props(f'label="{self.state.t("count")}"')
            b_validity.props(f'label="{self.state.t("validity_months")}"')
            export_btn.text = self.state.t("generate_and_export")

        self.state.register_lang_listener(update_labels)

    async def _handle_bundle_generation(
        self,
        template_id: str,
        bundle_id: str,
        bundle_name: str,
        prefix: str,
        count: int,
        validity: int,
    ) -> None:
        try:
            # 1. Deterministic generation of codes
            bundle = CodeEngine.generate_bundle(
                bundle_id=bundle_id,
                bundle_name=bundle_name,
                template_id=template_id,
                count=count,
                prefix=prefix,
                validity_months=validity,
            )
            self.state.storage.save_bundle(bundle)

            # 2. 2D Bin Packing
            template = self.state.storage.load_template(template_id)
            items_to_pack = [
                (v.code, template.width_mm, template.height_mm)
                for v in bundle.vouchers
            ]
            packing_result = pack_vouchers(items_to_pack, margin_mm=8.0, spacing_mm=4.0)

            # 3. Background PDF rendering
            output_pdf = self.state.storage.exports_dir / f"{bundle_id}.pdf"
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

            ui.notify(self.state.t("bundle_success").format(count=count), type="positive")
            ui.download(f"/exports/{output_pdf.name}")

        except Exception as exc:
            ui.notify(f"Generation Error: {exc}", type="negative")