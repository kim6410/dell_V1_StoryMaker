# -*- coding: utf-8 -*-
"""다운로드 전용 이미지 워터마크.

원본 파일은 수정하지 않고 작업 폴더의 캐시 사본만 생성합니다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _font_path() -> str | None:
    candidates = [
        "/app/app/assets/fonts/malgunbd.ttf",
        "/app/app/assets/fonts/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for value in candidates:
        if Path(value).is_file():
            return value
    return None


def _clean_text(value: Any, limit: int = 80) -> str:
    return " ".join(str(value or "").split())[:limit]


def _watermark_identity(data: dict[str, Any]) -> tuple[str, str]:
    persona = data.get("persona") if isinstance(data.get("persona"), dict) else {}
    company = _clean_text(persona.get("company_name") or persona.get("business_name"), 80)
    phone = _clean_text(
        persona.get("phone_number")
        or persona.get("phone")
        or persona.get("business_phone")
        or persona.get("contact_phone")
        or persona.get("mobile")
        or persona.get("tel"),
        40,
    )
    return company, phone


def _cache_key(source: Path, company: str, phone: str) -> str:
    stat = source.stat()
    raw = json.dumps(
        {
            "path": str(source.resolve()),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
            "company": company,
            "phone": phone,
            "version": "storymaker-download-watermark-v4-compact-gap",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _fit_font(draw, text: str, font_path: str | None, preferred: int, max_width: int):
    from PIL import ImageFont

    size = max(16, preferred)
    while size >= 16:
        font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        box = draw.textbbox((0, 0), text, font=font, stroke_width=max(1, size // 18))
        if box[2] - box[0] <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(font_path, 16) if font_path else ImageFont.load_default()


def _render(source: Path, target: Path, company: str, phone: str) -> Path:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps

    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")

    width, height = image.size
    if width < 64 or height < 64:
        return source

    max_side = 2560
    scale_down = min(1.0, max_side / max(width, height))
    if scale_down < 1.0:
        image = image.resize(
            (max(1, round(width * scale_down)), max(1, round(height * scale_down))),
            Image.Resampling.LANCZOS,
        )
        width, height = image.size

    short_side = min(width, height)
    ratio = max(0.45, short_side / 1080.0)
    outer_margin = max(14, round(36 * ratio))
    inner_margin = max(24, round(56 * ratio))
    outer_width = max(2, round(4 * ratio))
    inner_width = max(1, round(2 * ratio))
    outer_radius = max(12, round(32 * ratio))
    inner_radius = max(10, round(26 * ratio))
    glow_radius = max(5, round(16 * ratio))

    base = image.convert("RGBA")
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.rounded_rectangle(
        (outer_margin, outer_margin, width - outer_margin, height - outer_margin),
        radius=outer_radius,
        outline=(34, 211, 238, 120),
        width=max(3, outer_width * 2),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(glow_radius))
    base = Image.alpha_composite(base, glow)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (outer_margin, outer_margin, width - outer_margin, height - outer_margin),
        radius=outer_radius,
        outline=(34, 211, 238, 155),
        width=outer_width,
    )
    draw.rounded_rectangle(
        (inner_margin, inner_margin, width - inner_margin, height - inner_margin),
        radius=inner_radius,
        outline=(253, 224, 71, 125),
        width=inner_width,
    )

    if company or phone:
        font_path = _font_path()
        max_text_width = max(120, width - inner_margin * 2 - round(36 * ratio))
        portrait_brand_scale = 1.5 if height > width else 1.0
        brand_size = max(20, round(39 * ratio * portrait_brand_scale))
        phone_size = max(18, round(43 * ratio))
        brand_font = _fit_font(draw, company, font_path, brand_size, max_text_width) if company else None
        phone_font = _fit_font(draw, phone, font_path, phone_size, max_text_width) if phone else None

        line_gap = max(10, round(19 * ratio))
        brand_box = draw.textbbox((0, 0), company, font=brand_font, stroke_width=max(1, round(4 * ratio))) if company else (0, 0, 0, 0)
        phone_box = draw.textbbox((0, 0), phone, font=phone_font, stroke_width=max(1, round(4 * ratio))) if phone else (0, 0, 0, 0)
        brand_h = brand_box[3] - brand_box[1]
        phone_h = phone_box[3] - phone_box[1]
        total_h = brand_h + phone_h + (line_gap if company and phone else 0)
        bottom_margin = max(inner_margin + 10, round(86 * ratio))
        y = max(inner_margin, height - bottom_margin - total_h)

        pad_x = max(16, round(30 * ratio))
        pad_y = max(8, round(12 * ratio))
        panel_top = max(inner_margin, y - pad_y)
        panel_bottom = min(height - inner_margin, y + total_h + pad_y)
        panel = Image.new("RGBA", base.size, (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle(
            (inner_margin + 8, panel_top, width - inner_margin - 8, panel_bottom),
            radius=max(10, round(22 * ratio)),
            fill=(0, 0, 0, 70),
        )
        overlay = Image.alpha_composite(overlay, panel)
        draw = ImageDraw.Draw(overlay)

        stroke = max(1, round(4 * ratio))
        shadow = max(1, round(2 * ratio))
        if company:
            text_w = brand_box[2] - brand_box[0]
            x = (width - text_w) // 2
            draw.text((x + shadow, y + shadow), company, font=brand_font, fill=(0, 0, 0, 210), stroke_width=stroke, stroke_fill=(0, 0, 0, 220))
            draw.text((x, y), company, font=brand_font, fill=(255, 211, 0, 255), stroke_width=stroke, stroke_fill=(0, 0, 0, 230))
            y += brand_h + (line_gap if phone else 0)
        if phone:
            text_w = phone_box[2] - phone_box[0]
            x = (width - text_w) // 2
            draw.text((x + shadow, y + shadow), phone, font=phone_font, fill=(0, 0, 0, 210), stroke_width=stroke, stroke_fill=(0, 0, 0, 220))
            draw.text((x, y), phone, font=phone_font, fill=(255, 255, 255, 255), stroke_width=stroke, stroke_fill=(0, 0, 0, 230))

    result = Image.alpha_composite(base, overlay).convert("RGB")
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = target.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        result.save(target, format="JPEG", quality=90, optimize=True)
    elif suffix == ".webp":
        result.save(target, format="WEBP", quality=90, method=4)
    else:
        result.save(target, format="PNG", optimize=True)
    return target


def prepare_watermarked_download_images(
    image_files: list[Path],
    data: dict[str, Any],
    cache_dir: Path,
) -> list[Path]:
    """다운로드 이미지 목록을 워터마크 캐시 사본 목록으로 변환합니다."""
    company, phone = _watermark_identity(data)
    if not company and not phone:
        return image_files

    prepared: list[Path] = []
    cache_dir.mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(image_files, start=1):
        try:
            suffix = source.suffix.lower() if source.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"
            key = _cache_key(source, company, phone)
            target = cache_dir / key / source.name
            if not target.exists() or target.stat().st_size <= 0:
                _render(source, target, company, phone)
            prepared.append(target if target.exists() and target.stat().st_size > 0 else source)
        except Exception:
            prepared.append(source)
    return prepared
