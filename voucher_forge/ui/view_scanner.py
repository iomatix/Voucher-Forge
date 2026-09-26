"""Scanner & Validation view module for verifying voucher keys and status redemption."""

from __future__ import annotations

from nicegui import ui

from voucher_forge.code_engine import CodeEngine
from voucher_forge.models import VoucherItem, VoucherStatus
from voucher_forge.ui.state import AppState


class ScannerView:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def render(self) -> None:
        with ui.column().classes(
            "w-full max-w-xl mx-auto bg-white p-8 rounded-lg shadow-sm border border-slate-200"
        ):
            header_lbl = ui.label(self.state.t("scanner_header")).classes(
                "text-xl font-bold text-slate-800 mb-4"
            )

            code_input = ui.input(
                label=self.state.t("enter_code"),
                placeholder="e.g. KPN-25W-12-8K",
            ).classes("w-full text-lg uppercase font-mono")

            result_card = ui.card().classes(
                "w-full bg-slate-50 p-4 border border-slate-200 mt-4"
            )
            result_card.set_visibility(False)

            with result_card:
                status_label = ui.label("").classes("text-lg font-bold")
                offer_badge = ui.label("").classes(
                    "text-sm font-semibold text-sky-800 bg-sky-100 border border-sky-200 rounded px-3 py-1 my-1"
                )
                offer_badge.set_visibility(False)

                details_label = ui.label("").classes("text-sm text-slate-600 font-mono")
                redeem_btn = ui.button(
                    self.state.t("redeem_btn"), icon="check_circle"
                ).classes("mt-3 bg-emerald-600 text-white w-full")

            async def on_verify() -> None:
                key = (code_input.value or "").strip().upper()
                is_valid = CodeEngine.validate_key(key)
                result_card.set_visibility(True)

                if not is_valid:
                    status_label.text = f"{self.state.t('status')}: {self.state.t('invalid')}"
                    status_label.classes(replace="text-lg font-bold text-rose-600")
                    details_label.text = self.state.t("code_invalid_msg")
                    offer_badge.set_visibility(False)
                    redeem_btn.set_visibility(False)
                    return

                decoded = CodeEngine.decode_key(key)
                status_label.text = f"{self.state.t('status')}: {self.state.t('valid')}"
                status_label.classes(replace="text-lg font-bold text-emerald-600")

                # Match voucher item from storage to display specific offer variant
                matched_voucher: VoucherItem | None = None
                for b_file in self.state.storage.bundles_dir.glob("*.json"):
                    b_reg = self.state.storage.load_bundle(b_file.stem)
                    for item in b_reg.vouchers:
                        if item.code == key:
                            matched_voucher = item
                            break
                    if matched_voucher:
                        break

                if matched_voucher and matched_voucher.text_overrides:
                    offer_title = matched_voucher.text_overrides.get("tb_title", "")
                    if offer_title:
                        offer_badge.text = f"🎁 {self.state.t('scanned_offer')}: {offer_title}"
                        offer_badge.set_visibility(True)
                    else:
                        offer_badge.set_visibility(False)
                else:
                    offer_badge.set_visibility(False)

                val_text = (
                    self.state.t("unlimited")
                    if decoded["validity_months"] == 99
                    else f"{decoded['validity_months']} m."
                )
                details_label.text = (
                    f"{self.state.t('code_valid_msg')}\n"
                    f"{self.state.t('prefix')}: {decoded['prefix']} | "
                    f"{self.state.t('created_date')}: {decoded['creation_date']} | "
                    f"{self.state.t('validity')}: {val_text}"
                )
                redeem_btn.set_visibility(True)

            async def on_redeem() -> None:
                key = (code_input.value or "").strip().upper()
                found = False

                for b_file in self.state.storage.bundles_dir.glob("*.json"):
                    b_id = b_file.stem
                    if self.state.storage.update_voucher_status(
                        b_id, key, VoucherStatus.REDEEMED
                    ):
                        found = True
                        ui.notify(
                            self.state.t("redeemed_success").format(code=key),
                            type="positive",
                        )
                        break

                if not found:
                    ui.notify(self.state.t("code_not_found"), type="warning")

            verify_btn = ui.button(
                self.state.t("verify_btn"), icon="search", on_click=on_verify
            ).classes("w-full mt-3 bg-sky-600 text-white py-2")
            redeem_btn.on_click(on_redeem)

        def update_labels() -> None:
            header_lbl.text = self.state.t("scanner_header")
            code_input.props(f'label="{self.state.t("enter_code")}"')
            verify_btn.text = self.state.t("verify_btn")
            redeem_btn.text = self.state.t("redeem_btn")

        self.state.register_lang_listener(update_labels)