from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re
from urllib.parse import urlparse

from PIL import Image

from .renderer import LogoOptions, QrStyle, ScanQualityReport, ValidationMessage, generate_qr


class ContentKind(str, Enum):
    AUTO = "Auto"
    URL = "URL"
    TEXT = "Text"
    EMAIL = "Email"
    PHONE = "Phone"


@dataclass(frozen=True)
class ContentAnalysis:
    kind: ContentKind
    normalized_content: str
    character_count: int
    byte_count: int
    messages: tuple[ValidationMessage, ...]


@dataclass(frozen=True)
class EngineRenderResult:
    style: QrStyle
    image: Image.Image
    validation: tuple[ValidationMessage, ...]
    quality: ScanQualityReport
    content: ContentAnalysis


DOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9-]{2,})+(?:[/:?#].*)?$", re.I)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s().-]{5,}$")


def render_qr_code(
    style: QrStyle,
    logo: LogoOptions | None = None,
    *,
    output_size: int | None = None,
    content_kind: ContentKind | str = ContentKind.AUTO,
) -> EngineRenderResult:
    content = analyze_content(style.content, content_kind)
    normalized_style = replace(style, content=content.normalized_content)
    render = generate_qr(normalized_style, logo, output_size=output_size)
    validation = (*content.messages, *render.validation)
    return EngineRenderResult(
        style=normalized_style,
        image=render.image,
        validation=validation,
        quality=render.quality,
        content=content,
    )


def analyze_content(content: str, requested_kind: ContentKind | str = ContentKind.AUTO) -> ContentAnalysis:
    requested = ContentKind(requested_kind)
    raw = content.strip()
    kind = _detect_content_kind(raw) if requested == ContentKind.AUTO else requested
    normalized = _normalized_content(raw, kind)
    messages = tuple(_content_messages(raw, normalized, kind, requested))
    return ContentAnalysis(
        kind=kind,
        normalized_content=normalized,
        character_count=len(raw),
        byte_count=len(normalized.encode("utf-8")),
        messages=messages,
    )


def _detect_content_kind(content: str) -> ContentKind:
    if _looks_like_url(content):
        return ContentKind.URL
    if EMAIL_PATTERN.match(content):
        return ContentKind.EMAIL
    if PHONE_PATTERN.match(content):
        return ContentKind.PHONE
    return ContentKind.TEXT


def _normalized_content(content: str, kind: ContentKind) -> str:
    if kind == ContentKind.URL and content and not urlparse(content).scheme:
        return f"https://{content}"
    if kind == ContentKind.EMAIL and content and not content.lower().startswith("mailto:"):
        return f"mailto:{content}"
    if kind == ContentKind.PHONE and content and not content.lower().startswith("tel:"):
        compact = re.sub(r"[\s().-]+", "", content)
        return f"tel:{compact}"
    return content


def _content_messages(
    raw: str,
    normalized: str,
    kind: ContentKind,
    requested: ContentKind,
) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    if not raw:
        return messages

    if kind == ContentKind.URL:
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            messages.append(ValidationMessage("warning", "URL content may not open correctly."))
        elif raw != normalized:
            messages.append(ValidationMessage("info", "URL will be encoded with https://."))

    if kind == ContentKind.EMAIL and not EMAIL_PATTERN.match(raw) and not raw.lower().startswith("mailto:"):
        messages.append(ValidationMessage("warning", "Email content does not look like a complete address."))

    if kind == ContentKind.PHONE and not PHONE_PATTERN.match(raw) and not raw.lower().startswith("tel:"):
        messages.append(ValidationMessage("warning", "Phone content does not look like a complete number."))

    if requested != ContentKind.TEXT and "\n" in raw:
        messages.append(ValidationMessage("warning", "Line breaks are usually best encoded as Text."))

    return messages


def _looks_like_url(content: str) -> bool:
    if not content or any(character.isspace() for character in content):
        return False
    parsed = urlparse(content)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return True
    if content.lower().startswith("www."):
        return True
    return bool(DOMAIN_PATTERN.match(content))
