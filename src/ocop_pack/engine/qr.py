from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import cv2
import qrcode
from PIL.Image import Image as PILImage


def payload_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_qr(payload: str, box_size: int = 10, border: int = 4) -> PILImage:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=border
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return cast(PILImage, image)


def decode_qr(path: Path) -> str | None:
    img = cv2.imread(str(path))
    if img is None:
        return None
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    return data or None
