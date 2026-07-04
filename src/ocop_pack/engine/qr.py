from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import cv2
import qrcode
from PIL import Image
from PIL.Image import Image as PILImage

from ocop_pack.domain.geometry import BoundingBox

QR_POLICY_VERSION = "qr-square-fit-v1"
MIN_QR_SIZE_MM = 12.0
QUIET_ZONE_MODULES = 4


def payload_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_qr(payload: str, box_size: int = 10, border: int = QUIET_ZONE_MODULES) -> PILImage:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=border
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return cast(PILImage, image)


def square_inside_bbox(bbox: BoundingBox, min_size_mm: float = MIN_QR_SIZE_MM) -> BoundingBox:
    side = min(bbox.width_mm, bbox.height_mm)
    if side < min_size_mm:
        raise ValueError(f"QR bbox effective square too small: {side:.2f}mm < {min_size_mm:.2f}mm")
    return BoundingBox(
        x_mm=bbox.x_mm + (bbox.width_mm - side) / 2,
        y_mm=bbox.y_mm + (bbox.height_mm - side) / 2,
        width_mm=side,
        height_mm=side,
    )


def qr_module_count(payload: str) -> int:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=QUIET_ZONE_MODULES
    )
    qr.add_data(payload)
    qr.make(fit=True)
    return len(qr.get_matrix())


def qr_render_metadata(
    payload: str, bbox: BoundingBox, dpi: int | None = None
) -> dict[str, object]:
    square = square_inside_bbox(bbox)
    modules = qr_module_count(payload)
    data: dict[str, object] = {
        "qr_policy_version": QR_POLICY_VERSION,
        "effective_bbox_mm": square.model_dump(mode="json"),
        "effective_size_mm": square.width_mm,
        "quiet_zone_modules": QUIET_ZONE_MODULES,
        "module_count_with_quiet_zone": modules,
        "module_size_mm": square.width_mm / modules,
    }
    if dpi is not None:
        side_px = round(square.width_mm / 25.4 * dpi)
        if side_px < modules:
            raise ValueError(f"QR rendered area too small: {side_px}px for {modules} modules")
        data.update({"effective_size_px": side_px, "module_size_px": side_px / modules})
    return data


def render_qr_square(
    payload: str, target_px: tuple[int, int]
) -> tuple[PILImage, tuple[int, int, int]]:
    width, height = target_px
    side = min(width, height)
    modules = qr_module_count(payload)
    if side <= 0 or side < modules:
        raise ValueError(f"QR rendered area too small: {side}px for {modules} modules")
    qr = generate_qr(payload, box_size=10, border=QUIET_ZONE_MODULES)
    resized = qr.resize((side, side), Image.Resampling.NEAREST).convert("RGBA")
    layer = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    offset = ((width - side) // 2, (height - side) // 2)
    layer.alpha_composite(resized, offset)
    return layer, (offset[0], offset[1], side)


def decode_qr(path: Path) -> str | None:
    img = cv2.imread(str(path))
    if img is None:
        return None
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    return data or None
