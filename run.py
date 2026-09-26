"""Entrypoint script for Voucher Forge web application."""

from nicegui import ui
from voucher_forge.app import create_app

if __name__ in {"__main__", "__mp_main__"}:
    create_app(base_dir="data")
    ui.run(
        title="Voucher Forge",
        port=8080,
        reload=False,
        show=True,
    )