"""Entrypoint script for Voucher Forge web application."""

from nicegui import ui
from voucher_forge.app import create_app

if __name__ in {"__main__", "__mp_main__"}:
    create_app(base_dir="data")
    ui.run(
        host="127.0.0.1",
        port=8081,
        title="Voucher Forge",
        reload=False,
        show=True,
    )