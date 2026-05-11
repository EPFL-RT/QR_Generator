from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

import qrcode
from PIL import Image, ImageColor, ImageDraw


class ErrorCorrectionLevel(str, Enum):
    L = "L"
    M = "M"
    Q = "Q"
    H = "H"


class ModuleStyle(str, Enum):
    SQUARE = "Square"
    ROUNDED = "Rounded"
    DOTS = "Dots"


class EyeStyle(str, Enum):
    SQUARE = "Square"
    ROUNDED = "Rounded"
    CIRCLE = "Circle"


EC_LEVELS = {
    ErrorCorrectionLevel.L: qrcode.constants.ERROR_CORRECT_L,
    ErrorCorrectionLevel.M: qrcode.constants.ERROR_CORRECT_M,
    ErrorCorrectionLevel.Q: qrcode.constants.ERROR_CORRECT_Q,
    ErrorCorrectionLevel.H: qrcode.constants.ERROR_CORRECT_H,
}


@dataclass(frozen=True)
class QrStyle:
    content: str
    error_correction: ErrorCorrectionLevel = ErrorCorrectionLevel.H
    box_size: int = 24
    border: int = 1
    fill_color: str = "#000000"
    back_color: str = "#FFFFFF"
    eye_color: str = "#000000"
    module_style: ModuleStyle = ModuleStyle.SQUARE
    eye_style: EyeStyle = EyeStyle.SQUARE
    module_radius: float = 0.0


@dataclass(frozen=True)
class LogoOptions:
    path: Path
    max_size_ratio: float = 0.30
    bg_padding_x: int = 30
    bg_padding_y: int = 80


@dataclass(frozen=True)
class ValidationMessage:
    level: str
    text: str


@dataclass(frozen=True)
class QrRenderResult:
    image: Image.Image
    validation: tuple[ValidationMessage, ...]


def generate_qr(style: QrStyle, logo: LogoOptions | None = None) -> QrRenderResult:
    validation = tuple(_validate(style, logo))

    qr = qrcode.QRCode(
        error_correction=EC_LEVELS[style.error_correction],
        box_size=1,
        border=style.border,
    )
    qr.add_data(style.content.strip())
    qr.make(fit=True)

    matrix = qr.get_matrix()
    image = _draw_matrix(matrix, style)

    if logo and logo.path:
        image = _apply_logo(image, logo, style.back_color)

    return QrRenderResult(image=image, validation=validation)


def _validate(style: QrStyle, logo: LogoOptions | None) -> Iterable[ValidationMessage]:
    if not style.content.strip():
        yield ValidationMessage("error", "Add text or a URL before exporting.")

    if style.border < 4:
        yield ValidationMessage("warning", "A quiet zone of at least 4 modules scans more reliably.")

    if style.box_size < 8:
        yield ValidationMessage("warning", "Small module sizes can make exported QR codes hard to scan.")

    if _contrast_ratio(style.fill_color, style.back_color) < 4.5:
        yield ValidationMessage("warning", "Increase color contrast for better scanning.")

    if _contrast_ratio(_eye_color(style), style.back_color) < 4.5:
        yield ValidationMessage("warning", "Increase eye contrast for better scanner detection.")

    if style.module_style != ModuleStyle.SQUARE and style.box_size < 16:
        yield ValidationMessage("warning", "Styled modules look and scan better at module sizes of 16 px or more.")

    if style.module_style == ModuleStyle.DOTS and style.border < 4:
        yield ValidationMessage("warning", "Dot modules need a wider quiet zone for reliable scanning.")

    if logo and logo.path:
        if not logo.path.exists():
            yield ValidationMessage("error", f"Logo not found: {logo.path}")
        if logo.max_size_ratio > 0.25 and style.error_correction != ErrorCorrectionLevel.H:
            yield ValidationMessage("warning", "Large logos should use H error correction.")
        if logo.max_size_ratio > 0.30:
            yield ValidationMessage("warning", "Logos above 30% of the QR width may not scan reliably.")


def _draw_matrix(matrix: list[list[bool]], style: QrStyle) -> Image.Image:
    modules = len(matrix)
    scale = _render_scale(style)
    box = style.box_size * scale
    size = modules * box
    draw_style = QrStyle(
        content=style.content,
        error_correction=style.error_correction,
        box_size=box,
        border=style.border,
        fill_color=style.fill_color,
        back_color=style.back_color,
        eye_color=style.eye_color,
        module_style=style.module_style,
        eye_style=style.eye_style,
        module_radius=style.module_radius,
    )

    image = Image.new("RGB", (size, size), style.back_color)
    draw = ImageDraw.Draw(image)
    finder_origins = _finder_origins(modules, style.border)

    for y, row in enumerate(matrix):
        for x, active in enumerate(row):
            if not active or _is_finder_module(x, y, finder_origins):
                continue
            _draw_data_module(draw, x, y, draw_style)

    for origin in finder_origins:
        _draw_finder(draw, origin, draw_style)

    if scale == 1:
        return image
    return image.resize((modules * style.box_size, modules * style.box_size), Image.Resampling.LANCZOS)


def _render_scale(style: QrStyle) -> int:
    if style.module_style == ModuleStyle.SQUARE and style.eye_style == EyeStyle.SQUARE and style.module_radius == 0:
        return 1
    return 3


def _draw_data_module(draw: ImageDraw.ImageDraw, x: int, y: int, style: QrStyle) -> None:
    box = style.box_size
    left = x * box
    top = y * box
    right = (x + 1) * box
    bottom = (y + 1) * box

    if style.module_style == ModuleStyle.SQUARE:
        inset = 0
        radius = 0
    elif style.module_style == ModuleStyle.ROUNDED:
        inset = max(1, int(box * 0.08))
        radius = max(box * 0.18, box * style.module_radius)
    else:
        inset = max(1, int(box * 0.14))
        radius = box

    bounds = (left + inset, top + inset, right - inset, bottom - inset)
    if style.module_style == ModuleStyle.DOTS:
        draw.ellipse(bounds, fill=style.fill_color)
    elif radius:
        draw.rounded_rectangle(bounds, radius=radius, fill=style.fill_color)
    else:
        draw.rectangle(bounds, fill=style.fill_color)


def _finder_origins(modules: int, border: int) -> tuple[tuple[int, int], ...]:
    last = modules - border - 7
    first = border
    if last <= first:
        return ()
    return ((first, first), (last, first), (first, last))


def _is_finder_module(x: int, y: int, origins: tuple[tuple[int, int], ...]) -> bool:
    return any(origin_x <= x < origin_x + 7 and origin_y <= y < origin_y + 7 for origin_x, origin_y in origins)


def _draw_finder(draw: ImageDraw.ImageDraw, origin: tuple[int, int], style: QrStyle) -> None:
    box = style.box_size
    x, y = origin
    eye_color = _eye_color(style)

    outer = _module_bounds(x, y, 7, box)
    middle = _module_bounds(x + 1, y + 1, 5, box)
    inner = _module_bounds(x + 2, y + 2, 3, box)

    if style.eye_style == EyeStyle.CIRCLE:
        draw.ellipse(outer, fill=eye_color)
        draw.ellipse(middle, fill=style.back_color)
        draw.ellipse(inner, fill=eye_color)
        return

    if style.eye_style == EyeStyle.ROUNDED:
        draw.rounded_rectangle(outer, radius=box * 1.25, fill=eye_color)
        draw.rounded_rectangle(middle, radius=box * 0.85, fill=style.back_color)
        draw.rounded_rectangle(inner, radius=box * 0.45, fill=eye_color)
        return

    draw.rectangle(outer, fill=eye_color)
    draw.rectangle(middle, fill=style.back_color)
    draw.rectangle(inner, fill=eye_color)


def _module_bounds(x: int, y: int, width: int, box: int) -> tuple[int, int, int, int]:
    return (x * box, y * box, (x + width) * box, (y + width) * box)


def _eye_color(style: QrStyle) -> str:
    return style.eye_color or style.fill_color


def _apply_logo(image: Image.Image, logo: LogoOptions, back_color: str) -> Image.Image:
    logo_img = Image.open(logo.path).convert("RGBA")
    qr_w, qr_h = image.size
    max_logo_px = max(1, int(min(qr_w, qr_h) * logo.max_size_ratio))

    logo_img.thumbnail((max_logo_px, max_logo_px), Image.Resampling.LANCZOS)

    bg_size = (
        logo_img.width + max(0, logo.bg_padding_x),
        logo_img.height + max(0, logo.bg_padding_y),
    )
    bg = Image.new("RGBA", bg_size, back_color)
    bg_draw = ImageDraw.Draw(bg)
    bg_draw.rounded_rectangle(
        (0, 0, bg_size[0] - 1, bg_size[1] - 1),
        radius=max(8, min(bg_size) // 8),
        fill=back_color,
    )

    bg_pos = ((qr_w - bg.width) // 2, (qr_h - bg.height) // 2)
    logo_pos = (
        bg_pos[0] + (bg.width - logo_img.width) // 2,
        bg_pos[1] + (bg.height - logo_img.height) // 2,
    )

    composed = image.convert("RGBA")
    composed.alpha_composite(bg, bg_pos)
    composed.alpha_composite(logo_img, logo_pos)
    return composed.convert("RGB")


def _contrast_ratio(color_a: str, color_b: str) -> float:
    rgb_a = _relative_luminance(ImageColor.getrgb(color_a))
    rgb_b = _relative_luminance(ImageColor.getrgb(color_b))
    lighter = max(rgb_a, rgb_b)
    darker = min(rgb_a, rgb_b)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb[:3]:
        normalized = value / 255
        if normalized <= 0.03928:
            channels.append(normalized / 12.92)
        else:
            channels.append(((normalized + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
