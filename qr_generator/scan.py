from __future__ import annotations

from io import BytesIO
from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageFilter


@dataclass(frozen=True)
class ScanValidationResult:
    status: str
    message: str
    decoded_text: str = ""


@dataclass(frozen=True)
class ScanStressCaseResult:
    name: str
    status: str
    message: str
    decoded_text: str = ""


@dataclass(frozen=True)
class ScanStressValidationResult:
    status: str
    message: str
    passed_cases: int
    total_cases: int
    cases: tuple[ScanStressCaseResult, ...]


def validate_qr_image(image: Image.Image, expected_content: str) -> ScanValidationResult:
    result = _validate_image(image, expected_content)
    if result.status == "failed":
        return ScanValidationResult("failed", "Generated QR could not be decoded.", result.decoded_text)
    return result


def stress_validate_qr_image(image: Image.Image, expected_content: str) -> ScanStressValidationResult:
    cases = tuple(_stress_cases(image))
    results = tuple(
        ScanStressCaseResult(case_name, validation.status, validation.message, validation.decoded_text)
        for case_name, transformed in cases
        for validation in (_validate_image(transformed, expected_content),)
    )

    unavailable = next((result for result in results if result.status == "unavailable"), None)
    if unavailable is not None:
        return ScanStressValidationResult(
            "unavailable",
            unavailable.message,
            0,
            len(results),
            results,
        )

    passed = sum(1 for result in results if result.status == "passed")
    total = len(results)
    if passed == total:
        return ScanStressValidationResult(
            "passed",
            f"Stress validation passed {passed}/{total} scan checks.",
            passed,
            total,
            results,
        )

    failed_names = ", ".join(result.name for result in results if result.status != "passed")
    return ScanStressValidationResult(
        "failed",
        f"Stress validation passed {passed}/{total}; failed: {failed_names}.",
        passed,
        total,
        results,
    )


def _validate_image(image: Image.Image, expected_content: str) -> ScanValidationResult:
    try:
        decoded, found = _decode_qr_image(image)
    except ImportError:
        return ScanValidationResult("unavailable", "Scan validation unavailable.")
    except Exception as exc:
        return ScanValidationResult("unavailable", f"Scan validation failed: {exc}")

    if not found or not decoded:
        return ScanValidationResult("failed", "QR could not be decoded.")

    if decoded != expected_content:
        return ScanValidationResult("mismatch", "Decoded content does not match the input.", decoded)

    return ScanValidationResult("passed", "Generated QR decodes successfully.", decoded)


def _decode_qr_image(image: Image.Image) -> tuple[str, bool]:
    import cv2
    import numpy as np

    rgb = image.convert("RGB")
    array = np.array(rgb)
    detector = cv2.QRCodeDetector()
    decoded, points, _ = detector.detectAndDecode(array)
    return decoded, points is not None


def _stress_cases(image: Image.Image) -> tuple[tuple[str, Image.Image], ...]:
    return (
        ("Original", image),
        ("Small export", _scaled_image(image, 0.65)),
        ("Soft blur", image.filter(ImageFilter.GaussianBlur(radius=0.45))),
        ("JPEG 70%", _jpeg_roundtrip(image, 70)),
        ("Reduced contrast", ImageEnhance.Contrast(image.convert("RGB")).enhance(0.72)),
    )


def _scaled_image(image: Image.Image, ratio: float) -> Image.Image:
    width, height = image.size
    size = (max(64, round(width * ratio)), max(64, round(height * ratio)))
    return image.convert("RGB").resize(size, Image.Resampling.LANCZOS)


def _jpeg_roundtrip(image: Image.Image, quality: int) -> Image.Image:
    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")
