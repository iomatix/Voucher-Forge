"""Atomic storage repository for templates and voucher bundles.

Strict zero-UI layer handling directory scaffolding and atomic persistence.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from voucher_forge.models import (
    BundleRegistry,
    SchemaVersionMismatchError,
    TemplateConfig,
    VoucherStatus,
)


class TemplateNotFoundError(FileNotFoundError):
    """Raised when requested template ID is not found on disk."""

    def __init__(self, template_id: str) -> None:
        super().__init__(f"Template with ID '{template_id}' was not found.")
        self.template_id = template_id


class BundleNotFoundError(FileNotFoundError):
    """Raised when requested bundle ID is not found on disk."""

    def __init__(self, bundle_id: str) -> None:
        super().__init__(f"Bundle with ID '{bundle_id}' was not found.")
        self.bundle_id = bundle_id


class StorageRepository:
    def __init__(self, base_dir: Path | str = "data") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.templates_dir = self.base_dir / "templates"
        self.bundles_dir = self.base_dir / "bundles"
        self.assets_dir = self.base_dir / "assets"
        self.presets_dir = self.base_dir / "presets"
        self.exports_dir = self.base_dir / "exports"

        self._initialize_structure()

    def _initialize_structure(self) -> None:
        for folder in (
            self.templates_dir,
            self.bundles_dir,
            self.assets_dir,
            self.presets_dir,
            self.exports_dir,
        ):
            folder.mkdir(parents=True, exist_ok=True)

    def _write_atomic_json(self, destination: Path, payload: dict[str, Any]) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_file = destination.parent / f".tmp_{destination.name}_{uuid.uuid4().hex}"

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, destination)
        except Exception:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise

    def save_template(self, template: TemplateConfig) -> Path:
        target_path = self.templates_dir / f"{template.id}.json"
        self._write_atomic_json(target_path, template.to_dict())
        return target_path

    def load_template(self, template_id: str) -> TemplateConfig:
        file_path = self.templates_dir / f"{template_id}.json"
        if not file_path.is_file():
            raise TemplateNotFoundError(template_id)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return TemplateConfig.from_dict(data)

    def list_templates(self) -> list[TemplateConfig]:
        results: list[TemplateConfig] = []
        for file_path in sorted(self.templates_dir.glob("*.json")):
            if file_path.name.startswith(".tmp_"):
                continue
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            results.append(TemplateConfig.from_dict(data))
        return results

    def save_bundle(self, bundle: BundleRegistry) -> Path:
        target_path = self.bundles_dir / f"{bundle.id}.json"
        self._write_atomic_json(target_path, bundle.to_dict())
        return target_path

    def load_bundle(self, bundle_id: str) -> BundleRegistry:
        file_path = self.bundles_dir / f"{bundle_id}.json"
        if not file_path.is_file():
            raise BundleNotFoundError(bundle_id)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return BundleRegistry.from_dict(data)

    def update_voucher_status(
        self, bundle_id: str, code: str, new_status: VoucherStatus
    ) -> bool:
        bundle = self.load_bundle(bundle_id)
        found = False

        for voucher in bundle.vouchers:
            if voucher.code == code:
                voucher.status = new_status
                if new_status == VoucherStatus.REDEEMED:
                    voucher.redeemed_at = datetime.now(timezone.utc).isoformat()
                elif new_status == VoucherStatus.ACTIVE:
                    voucher.redeemed_at = None
                found = True
                break

        if found:
            self.save_bundle(bundle)

        return found