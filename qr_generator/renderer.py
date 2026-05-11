from __future__ import annotations

import base64
from io import BytesIO
import html
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

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
    border: int = 4
    fill_color: str = "#000000"
    gradient_color: str = ""
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
class ScanQualityReport:
    rating: str
    score: int
    module_count: int
    qr_version: int
    output_size: int
    module_pixels: float
    messages: tuple[ValidationMessage, ...]


@dataclass(frozen=True)
class QrRenderResult:
    image: Image.Image
    validation: tuple[ValidationMessage, ...]
    quality: ScanQualityReport


LOGO_RATIO_LIMITS = {
    ErrorCorrectionLevel.L: 0.10,
    ErrorCorrectionLevel.M: 0.15,
    ErrorCorrectionLevel.Q: 0.22,
    ErrorCorrectionLevel.H: 0.28,
}


def generate_qr(style: QrStyle, logo: LogoOptions | None = None, *, output_size: int | None = None) -> QrRenderResult:
    matrix = _qr_matrix(style)
    quality = assess_scan_quality(style, logo, matrix=matrix, output_size=output_size)
    image = _draw_matrix(matrix, style)

    if logo and logo.path and logo.path.exists():
        image = _apply_logo(image, logo, style.back_color)

    return QrRenderResult(image=image, validation=quality.messages, quality=quality)


def generate_qr_svg(
    style: QrStyle,
    logo: LogoOptions | None = None,
    *,
    transparent_background: bool = False,
    display_size: int | None = None,
) -> str:
    matrix = _qr_matrix(style)
    modules = len(matrix)
    size = modules * style.box_size
    width = display_size or size
    finder_origins = _finder_origins(modules, style.border)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{width}" '
            f'viewBox="0 0 {size} {size}" shape-rendering="geometricPrecision">'
        ),
    ]

    if not transparent_background:
        parts.append(f'<rect width="{size}" height="{size}" fill="{_svg_escape(style.back_color)}"/>')

    for y, row in enumerate(matrix):
        for x, active in enumerate(row):
            if not active or _is_finder_module(x, y, finder_origins):
                continue
            parts.append(_svg_data_module(x, y, style, modules))

    for origin in finder_origins:
        parts.extend(_svg_finder(origin, style))

    if logo and logo.path:
        parts.extend(_svg_logo(size, logo, style.back_color))

    parts.append("</svg>")
    return "\n".join(parts)


def _qr_matrix(style: QrStyle) -> list[list[bool]]:
    qr = qrcode.QRCode(
        error_correction=EC_LEVELS[style.error_correction],
        box_size=1,
        border=style.border,
    )
    qr.add_data(style.content.strip())
    qr.make(fit=True)
    return qr.get_matrix()


def assess_scan_quality(
    style: QrStyle,
    logo: LogoOptions | None = None,
    *,
    matrix: list[list[bool]] | None = None,
    output_size: int | None = None,
) -> ScanQualityReport:
    matrix = matrix if matrix is not None else _qr_matrix(style)
    modules = len(matrix)
    core_modules = max(0, modules - style.border * 2)
    version = max(1, round((core_modules - 17) / 4)) if core_modules else 0
    raster_size = output_size or modules * style.box_size
    module_pixels = raster_size / modules if modules else 0
    messages: list[ValidationMessage] = []
    score = 100

    def add_error(text: str) -> None:
        nonlocal score
        messages.append(ValidationMessage("error", text))
        score = 0

    def add_warning(text: str, deduction: int) -> None:
        nonlocal score
        messages.append(ValidationMessage("warning", text))
        score -= deduction

    if not style.content.strip():
        add_error("Add text or a URL before exporting.")

    if style.border < 4:
        deduction = 24 if style.border <= 1 else 16
        add_warning("Set Border to 4 or higher so scanners can separate the QR code from its surroundings.", deduction)

    if module_pixels < 6:
        add_warning("Selected PNG export size is too small; use at least 8 pixels per QR module.", 22)
    elif module_pixels < 8:
        add_warning("Selected PNG export size is tight; larger exports scan better in print.", 12)

    fill_contrast = _contrast_ratio(style.fill_color, style.back_color)
    if fill_contrast < 3:
        add_warning("Use much stronger contrast between Fill Color and Background.", 30)
    elif fill_contrast < 4.5:
        add_warning("Increase contrast between Fill Color and Background for better scanning.", 18)

    if style.gradient_color:
        gradient_contrast = _contrast_ratio(style.gradient_color, style.back_color)
        if gradient_contrast < 3:
            add_warning("Use a darker Gradient Color or a lighter Background.", 24)
        elif gradient_contrast < 4.5:
            add_warning("Increase Gradient Color contrast for better scanning.", 14)

    eye_contrast = _contrast_ratio(_eye_color(style), style.back_color)
    if eye_contrast < 3:
        add_warning("Use much stronger contrast between Eye Color and Background.", 28)
    elif eye_contrast < 4.5:
        add_warning("Increase Eye Color contrast so scanners can lock onto the finder eyes.", 16)

    if style.module_style != ModuleStyle.SQUARE and module_pixels < 16:
        add_warning("Styled modules need at least 16 pixels per module for cleaner edges.", 10)

    if style.module_style == ModuleStyle.DOTS and style.border < 4:
        add_warning("Dot modules need Border 4 or higher for reliable scanning.", 8)

    if version >= 18:
        add_warning("The payload is very dense; shorten the text or export a larger QR code.", 22)
    elif version >= 12:
        add_warning("The payload is getting dense; larger exports will scan more reliably.", 10)

    if logo and logo.path:
        if not logo.path.exists():
            add_error(f"Logo not found: {logo.path}")
        if style.error_correction != ErrorCorrectionLevel.H:
            add_warning("Use H error correction when a centered logo is enabled.", 14)

        safe_ratio = LOGO_RATIO_LIMITS[style.error_correction]
        if logo.max_size_ratio > safe_ratio:
            recommended = round(safe_ratio * 100)
            deduction = 24 if logo.max_size_ratio > safe_ratio + 0.05 else 14
            add_warning(
                f"Keep Logo Max Size Ratio at {recommended}% or less for {style.error_correction.value} error correction.",
                deduction,
            )
        if logo.max_size_ratio > 0.30:
            add_warning("Logos above 30% of the QR width may not scan reliably.", 22)

    score = max(0, min(100, score))
    has_errors = any(message.level == "error" for message in messages)
    has_warnings = any(message.level == "warning" for message in messages)
    if has_errors or score < 70:
        rating = "Risky"
    elif has_warnings or score < 92:
        rating = "Good"
    else:
        rating = "Excellent"

    return ScanQualityReport(
        rating=rating,
        score=score,
        module_count=modules,
        qr_version=version,
        output_size=raster_size,
        module_pixels=module_pixels,
        messages=tuple(messages),
    )


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
        gradient_color=style.gradient_color,
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
            _draw_data_module(draw, x, y, draw_style, modules)

    for origin in finder_origins:
        _draw_finder(draw, origin, draw_style)

    if scale == 1:
        return image
    return image.resize((modules * style.box_size, modules * style.box_size), Image.Resampling.LANCZOS)


def _render_scale(style: QrStyle) -> int:
    if style.module_style == ModuleStyle.SQUARE and style.eye_style == EyeStyle.SQUARE and style.module_radius == 0:
        return 1
    return 3


def _draw_data_module(draw: ImageDraw.ImageDraw, x: int, y: int, style: QrStyle, modules: int) -> None:
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
    fill = _module_fill(style, y, modules)
    if style.module_style == ModuleStyle.DOTS:
        draw.ellipse(bounds, fill=fill)
    elif radius:
        draw.rounded_rectangle(bounds, radius=radius, fill=fill)
    else:
        draw.rectangle(bounds, fill=fill)


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


def _module_fill(style: QrStyle, y: int, modules: int) -> str:
    if not style.gradient_color:
        return style.fill_color
    ratio = y / max(1, modules - 1)
    return _interpolate_color(style.fill_color, style.gradient_color, ratio)


def _svg_data_module(x: int, y: int, style: QrStyle, modules: int) -> str:
    box = style.box_size
    left = x * box
    top = y * box
    fill = _svg_escape(_module_fill(style, y, modules))

    if style.module_style == ModuleStyle.SQUARE:
        return f'<rect x="{left}" y="{top}" width="{box}" height="{box}" fill="{fill}"/>'

    if style.module_style == ModuleStyle.ROUNDED:
        inset = max(0.5, box * 0.08)
        size = box - inset * 2
        radius = max(box * 0.18, box * style.module_radius)
        return (
            f'<rect x="{left + inset:.2f}" y="{top + inset:.2f}" width="{size:.2f}" height="{size:.2f}" '
            f'rx="{radius:.2f}" ry="{radius:.2f}" fill="{fill}"/>'
        )

    radius = box * 0.36
    return f'<circle cx="{left + box / 2:.2f}" cy="{top + box / 2:.2f}" r="{radius:.2f}" fill="{fill}"/>'


def _svg_finder(origin: tuple[int, int], style: QrStyle) -> list[str]:
    box = style.box_size
    x, y = origin
    eye_color = _svg_escape(_eye_color(style))
    back_color = _svg_escape(style.back_color)

    if style.eye_style == EyeStyle.CIRCLE:
        center_x = (x + 3.5) * box
        center_y = (y + 3.5) * box
        return [
            f'<circle cx="{center_x:.2f}" cy="{center_y:.2f}" r="{3.5 * box:.2f}" fill="{eye_color}"/>',
            f'<circle cx="{center_x:.2f}" cy="{center_y:.2f}" r="{2.5 * box:.2f}" fill="{back_color}"/>',
            f'<circle cx="{center_x:.2f}" cy="{center_y:.2f}" r="{1.5 * box:.2f}" fill="{eye_color}"/>',
        ]

    outer = _svg_rect(x, y, 7, box)
    middle = _svg_rect(x + 1, y + 1, 5, box)
    inner = _svg_rect(x + 2, y + 2, 3, box)

    if style.eye_style == EyeStyle.ROUNDED:
        return [
            f'<rect {outer} rx="{box * 1.25:.2f}" ry="{box * 1.25:.2f}" fill="{eye_color}"/>',
            f'<rect {middle} rx="{box * 0.85:.2f}" ry="{box * 0.85:.2f}" fill="{back_color}"/>',
            f'<rect {inner} rx="{box * 0.45:.2f}" ry="{box * 0.45:.2f}" fill="{eye_color}"/>',
        ]

    return [
        f'<rect {outer} fill="{eye_color}"/>',
        f'<rect {middle} fill="{back_color}"/>',
        f'<rect {inner} fill="{eye_color}"/>',
    ]


def _svg_logo(qr_size: int, logo: LogoOptions, back_color: str) -> list[str]:
    if not logo.path.exists():
        return []

    logo_img = Image.open(logo.path).convert("RGBA")
    max_logo_px = max(1, int(qr_size * logo.max_size_ratio))
    logo_img.thumbnail((max_logo_px, max_logo_px), Image.Resampling.LANCZOS)

    bg_width = logo_img.width + max(0, logo.bg_padding_x)
    bg_height = logo_img.height + max(0, logo.bg_padding_y)
    bg_x = (qr_size - bg_width) / 2
    bg_y = (qr_size - bg_height) / 2
    logo_x = bg_x + (bg_width - logo_img.width) / 2
    logo_y = bg_y + (bg_height - logo_img.height) / 2

    buffer = BytesIO()
    logo_img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    radius = max(8, min(bg_width, bg_height) / 8)

    return [
        (
            f'<rect x="{bg_x:.2f}" y="{bg_y:.2f}" width="{bg_width}" height="{bg_height}" '
            f'rx="{radius:.2f}" ry="{radius:.2f}" fill="{_svg_escape(back_color)}"/>'
        ),
        (
            f'<image x="{logo_x:.2f}" y="{logo_y:.2f}" width="{logo_img.width}" height="{logo_img.height}" '
            f'href="data:image/png;base64,{encoded}"/>'
        ),
    ]


def _svg_rect(x: int, y: int, width: int, box: int) -> str:
    return f'x="{x * box}" y="{y * box}" width="{width * box}" height="{width * box}"'


def _svg_escape(value: str) -> str:
    return html.escape(value, quote=True)


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


def _interpolate_color(color_a: str, color_b: str, ratio: float) -> str:
    rgb_a = ImageColor.getrgb(color_a)[:3]
    rgb_b = ImageColor.getrgb(color_b)[:3]
    values = [round(start + (end - start) * ratio) for start, end in zip(rgb_a, rgb_b)]
    return f"#{values[0]:02X}{values[1]:02X}{values[2]:02X}"


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb[:3]:
        normalized = value / 255
        if normalized <= 0.03928:
            channels.append(normalized / 12.92)
        else:
            channels.append(((normalized + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
