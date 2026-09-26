"""Domain models and serialization contracts for voucher-forge.

Zero-UI coupling: relies strictly on standard Python library.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

CURRENT_SCHEMA_VERSION = "1.0.0"


class SchemaVersionMismatchError(Exception):
    """Raised when data schema version does not match expected system schema version."""

    def __init__(self, expected: str, actual: str | None) -> None:
        super().__init__(
            f"Schema version mismatch: expected '{expected}', found '{actual}'"
        )
        self.expected = expected
        self.actual = actual


class VoucherStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REDEEMED = "REDEEMED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class BackgroundConfig:
    type: str  # "flat_color", "gradient", "image"
    color_start: str = "#FFFFFF"
    color_end: str | None = None
    gradient_angle_deg: float = 0.0
    image_asset: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackgroundConfig:
        return cls(
            type=str(data["type"]),
            color_start=str(data.get("color_start", "#FFFFFF")),
            color_end=data.get("color_end"),
            gradient_angle_deg=float(data.get("gradient_angle_deg", 0.0)),
            image_asset=data.get("image_asset"),
        )


@dataclass(slots=True)
class LogoConfig:
    asset_filename: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LogoConfig:
        return cls(
            asset_filename=str(data["asset_filename"]),
            x_mm=float(data["x_mm"]),
            y_mm=float(data["y_mm"]),
            width_mm=float(data["width_mm"]),
            height_mm=float(data["height_mm"]),
        )


@dataclass(slots=True)
class TextBlockConfig:
    id: str
    text: str
    x_mm: float
    y_mm: float
    font_size_pt: float
    color_hex: str
    font_family: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextBlockConfig:
        return cls(
            id=str(data["id"]),
            text=str(data["text"]),
            x_mm=float(data["x_mm"]),
            y_mm=float(data["y_mm"]),
            font_size_pt=float(data["font_size_pt"]),
            color_hex=str(data["color_hex"]),
            font_family=str(data["font_family"]),
        )


@dataclass(slots=True)
class CodeBoxConfig:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    show_barcode: bool
    font_size_pt: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeBoxConfig:
        return cls(
            x_mm=float(data["x_mm"]),
            y_mm=float(data["y_mm"]),
            width_mm=float(data["width_mm"]),
            height_mm=float(data["height_mm"]),
            show_barcode=bool(data["show_barcode"]),
            font_size_pt=float(data["font_size_pt"]),
        )


@dataclass(slots=True)
class TemplateConfig:
    id: str
    name: str
    width_mm: float
    height_mm: float
    background: BackgroundConfig
    code_box: CodeBoxConfig
    schema_version: str = CURRENT_SCHEMA_VERSION
    logo: LogoConfig | None = None
    text_blocks: list[TextBlockConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "background": self.background.to_dict(),
            "logo": self.logo.to_dict() if self.logo is not None else None,
            "text_blocks": [block.to_dict() for block in self.text_blocks],
            "code_box": self.code_box.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemplateConfig:
        version = data.get("schema_version")
        if version != CURRENT_SCHEMA_VERSION:
            raise SchemaVersionMismatchError(
                expected=CURRENT_SCHEMA_VERSION, actual=version
            )

        logo_raw = data.get("logo")
        logo = LogoConfig.from_dict(logo_raw) if logo_raw is not None else None

        return cls(
            schema_version=str(data["schema_version"]),
            id=str(data["id"]),
            name=str(data["name"]),
            width_mm=float(data["width_mm"]),
            height_mm=float(data["height_mm"]),
            background=BackgroundConfig.from_dict(data["background"]),
            logo=logo,
            text_blocks=[
                TextBlockConfig.from_dict(item) for item in data.get("text_blocks", [])
            ],
            code_box=CodeBoxConfig.from_dict(data["code_box"]),
        )


@dataclass(slots=True)
class VoucherItem:
    code: str
    template_id: str
    status: VoucherStatus
    created_at: str
    redeemed_at: str | None = None
    text_overrides: dict[str, str] = field(default_factory=dict)
    bg_asset_override: str | None = None
    logo_asset_override: str | None = None
    bg_color_override: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "template_id": self.template_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "redeemed_at": self.redeemed_at,
            "text_overrides": self.text_overrides,
            "bg_asset_override": self.bg_asset_override,
            "logo_asset_override": self.logo_asset_override,
            "bg_color_override": self.bg_color_override,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoucherItem:
        return cls(
            code=str(data["code"]),
            template_id=str(data["template_id"]),
            status=VoucherStatus(data["status"]),
            created_at=str(data["created_at"]),
            redeemed_at=data.get("redeemed_at"),
            text_overrides=data.get("text_overrides", {}),
            bg_asset_override=data.get("bg_asset_override"),
            logo_asset_override=data.get("logo_asset_override"),
            bg_color_override=data.get("bg_color_override"),
        )


@dataclass(slots=True)
class BundleRegistry:
    id: str
    name: str
    code_prefix: str
    created_at: str
    vouchers: list[VoucherItem] = field(default_factory=list)
    schema_version: str = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "code_prefix": self.code_prefix,
            "created_at": self.created_at,
            "vouchers": [voucher.to_dict() for voucher in self.vouchers],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BundleRegistry:
        version = data.get("schema_version")
        if version != CURRENT_SCHEMA_VERSION:
            raise SchemaVersionMismatchError(
                expected=CURRENT_SCHEMA_VERSION, actual=version
            )

        return cls(
            schema_version=str(data["schema_version"]),
            id=str(data["id"]),
            name=str(data["name"]),
            code_prefix=str(data["code_prefix"]),
            created_at=str(data["created_at"]),
            vouchers=[
                VoucherItem.from_dict(item) for item in data.get("vouchers", [])
            ],
        )


@dataclass(slots=True)
class VariantPreset:
    """Configuration snapshot of a single variant row in Batch Forge."""

    title: str
    sub_text: str
    count: int
    bg_asset: str | None = None
    logo_asset: str | None = None
    bg_color: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariantPreset:
        return cls(
            title=str(data.get("title", "")),
            sub_text=str(data.get("sub_text", "")),
            count=int(data.get("count", 1)),
            bg_asset=data.get("bg_asset"),
            logo_asset=data.get("logo_asset"),
            bg_color=data.get("bg_color"),
        )


@dataclass(slots=True)
class CampaignPreset:
    """Persisted snapshot of a multi-variant campaign configuration."""

    id: str
    name: str
    template_id: str
    prefix: str = "OFF"
    validity_months: int = 12
    variants: list[VariantPreset] = field(default_factory=list)
    schema_version: str = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "template_id": self.template_id,
            "prefix": self.prefix,
            "validity_months": self.validity_months,
            "variants": [variant.to_dict() for variant in self.variants],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CampaignPreset:
        version = data.get("schema_version")
        if version != CURRENT_SCHEMA_VERSION:
            raise SchemaVersionMismatchError(
                expected=CURRENT_SCHEMA_VERSION, actual=version
            )

        return cls(
            schema_version=str(data["schema_version"]),
            id=str(data["id"]),
            name=str(data["name"]),
            template_id=str(data.get("template_id", "")),
            prefix=str(data.get("prefix", "OFF")),
            validity_months=int(data.get("validity_months", 12)),
            variants=[
                VariantPreset.from_dict(item) for item in data.get("variants", [])
            ],
        )