from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass(frozen=True)
class ScanValidationResult:
    status: str
    message: str
    decoded_text: str = ""


def validate_qr_image(image: Image.Image, expected_content: str) -> ScanValidationResult:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return ScanValidationResult("unavailable", "Scan validation unavailable.")

    try:
        rgb = image.convert("RGB")
        array = np.array(rgb)
        detector = cv2.QRCodeDetector()
        decoded, points, _ = detector.detectAndDecode(array)
    except Exception as exc:
        return ScanValidationResult("unavailable", f"Scan validation failed: {exc}")

    if points is None or not decoded:
        return ScanValidationResult("failed", "Generated QR could not be decoded.")

    if decoded != expected_content:
        return ScanValidationResult("mismatch", "Decoded content does not match the input.", decoded)

    return ScanValidationResult("passed", "Generated QR decodes successfully.", decoded)
