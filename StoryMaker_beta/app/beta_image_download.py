from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


PACKAGE_VERSION = "beta-download-package-v7-1-soft-edge-vignette-stronger"


def _clean_name(value: Any, fallback: str, limit: int = 70) -> str:
    text = " ".join(str(value or "").split()).strip() or fallback
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", "_", text).strip(" ._")
    return text[:limit] or fallback


def _font_path() -> str | None:
    for value in (
        r"C:\Windows\Fonts\malgunbd.ttf",
        r"C:\Windows\Fonts\malgun.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ):
        if Path(value).is_file():
            return value
    return None


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _font_path()
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def _fit_font(draw: ImageDraw.ImageDraw, text: str, preferred: int, max_width: int):
    size = max(16, preferred)
    while size >= 16:
        font = _font(size)
        box = draw.textbbox((0, 0), text, font=font, stroke_width=max(1, size // 18))
        if box[2] - box[0] <= max_width:
            return font
        size -= 2
    return _font(16)


def _apply_soft_edge_vignette(base: Image.Image, short_side: int) -> Image.Image:
    width, height = base.size
    vignette = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)
    fade_depth = max(40, round(short_side * 0.075))
    band_width = max(8, fade_depth // 5)
    alpha_steps = (38, 30, 22, 14, 7)
    for index, alpha in enumerate(alpha_steps):
        inset = index * band_width
        if inset * 2 >= width or inset * 2 >= height:
            break
        draw.rectangle(
            (inset, inset, width - 1 - inset, height - 1 - inset),
            outline=(0, 0, 0, alpha),
            width=band_width,
        )
    return Image.alpha_composite(base, vignette)


def _watermark_image(source: Path, target: Path, company: str, phone: str) -> Path:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")

    width, height = image.size
    if width < 64 or height < 64:
        return source

    max_side = 2560
    scale = min(1.0, max_side / max(width, height))
    if scale < 1:
        image = image.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)
        width, height = image.size

    short_side = min(width, height)
    ratio = max(0.45, short_side / 1080.0)
    outer_margin = max(14, round(36 * ratio))
    inner_margin = max(24, round(56 * ratio))
    outer_width = max(2, round(4 * ratio))
    inner_width = max(1, round(2 * ratio))
    radius = max(12, round(32 * ratio))

    base = _apply_soft_edge_vignette(image.convert("RGBA"), short_side)
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.rounded_rectangle(
        (outer_margin, outer_margin, width - outer_margin, height - outer_margin),
        radius=radius,
        outline=(34, 211, 238, 125),
        width=max(3, outer_width * 2),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(max(5, round(16 * ratio))))
    base = Image.alpha_composite(base, glow)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (outer_margin, outer_margin, width - outer_margin, height - outer_margin),
        radius=radius,
        outline=(34, 211, 238, 175),
        width=outer_width,
    )
    draw.rounded_rectangle(
        (inner_margin, inner_margin, width - inner_margin, height - inner_margin),
        radius=max(10, radius - 6),
        outline=(253, 224, 71, 140),
        width=inner_width,
    )

    if company or phone:
        portrait = height > width
        max_text_width = max(120, round(width * (0.84 if portrait else 0.86)))
        brand_preferred = max(24, round(short_side * (0.0504 if portrait else 0.0364)))
        phone_preferred = max(20, round(short_side * (0.041 if portrait else 0.031)))
        brand_font = _fit_font(draw, company, brand_preferred, max_text_width) if company else None
        phone_font = _fit_font(draw, phone, phone_preferred, max_text_width) if phone else None
        gap = max(8, round(short_side * 0.010))
        text_stroke = max(2, round(short_side * 0.0035))
        brand_box = draw.textbbox((0, 0), company, font=brand_font, stroke_width=text_stroke) if company else (0, 0, 0, 0)
        phone_box = draw.textbbox((0, 0), phone, font=phone_font, stroke_width=text_stroke) if phone else (0, 0, 0, 0)
        brand_h = brand_box[3] - brand_box[1]
        phone_h = phone_box[3] - phone_box[1]
        total_h = brand_h + phone_h + (gap if company and phone else 0)
        vertical_padding = max(16, round(short_side * 0.022))
        panel_height = total_h + vertical_padding * 2
        panel_height = min(panel_height, round(height * 0.18))
        panel_top = max(inner_margin, height - inner_margin - panel_height)
        content_top = panel_top + max(0, (panel_height - total_h) // 2)
        y = content_top

        panel = Image.new("RGBA", base.size, (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle(
            (inner_margin + 8, panel_top, width - inner_margin - 8, height - inner_margin),
            radius=max(12, round(28 * ratio)),
            fill=(0, 0, 0, 118),
        )
        overlay = Image.alpha_composite(overlay, panel)
        draw = ImageDraw.Draw(overlay)
        shadow_offset_x = max(3, round(short_side * 0.006))
        shadow_offset_y = max(4, round(short_side * 0.008))
        shadow_stroke = text_stroke + max(2, round(short_side * 0.0025))
        if company:
            x = (width - (brand_box[2] - brand_box[0])) // 2 - brand_box[0]
            text_y = y - brand_box[1]
            draw.text((x + shadow_offset_x, text_y + shadow_offset_y), company, font=brand_font, fill=(0, 0, 0, 235), stroke_width=shadow_stroke, stroke_fill=(0, 0, 0, 248))
            draw.text((x, text_y), company, font=brand_font, fill=(255, 211, 0, 255), stroke_width=text_stroke, stroke_fill=(0, 0, 0, 245))
            y += brand_h + (gap if phone else 0)
        if phone:
            x = (width - (phone_box[2] - phone_box[0])) // 2 - phone_box[0]
            text_y = y - phone_box[1]
            draw.text((x + shadow_offset_x, text_y + shadow_offset_y), phone, font=phone_font, fill=(0, 0, 0, 235), stroke_width=shadow_stroke, stroke_fill=(0, 0, 0, 248))
            draw.text((x, text_y), phone, font=phone_font, fill=(255, 255, 255, 255), stroke_width=text_stroke, stroke_fill=(0, 0, 0, 245))

    result = Image.alpha_composite(base, overlay).convert("RGB")
    target.parent.mkdir(parents=True, exist_ok=True)
    result.save(target, format="JPEG", quality=91, optimize=True)
    return target


def _path(value: Any) -> Path | None:
    try:
        path = Path(str(value or ""))
    except Exception:
        return None
    return path if path.is_file() else None


def _signature(result: dict[str, Any]) -> str:
    assets = result.get("assets") if isinstance(result.get("assets"), dict) else {}
    values: list[str] = [PACKAGE_VERSION, str(result.get("title") or ""), json.dumps(result.get("business") or {}, ensure_ascii=False, sort_keys=True)]
    for key in ("images", "thumbnail", "browser_audio", "audio", "subtitle", "browser_video", "video"):
        item = assets.get(key)
        items = item if isinstance(item, list) else [item]
        for value in items:
            path = _path(value)
            if path:
                stat = path.stat()
                values.append(f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}")
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()[:20]


def build_download_package(job_dir: Path, result: dict[str, Any]) -> tuple[Path, str]:
    business = result.get("business") if isinstance(result.get("business"), dict) else {}
    company = " ".join(str(business.get("name") or "").split())
    phone = " ".join(str(business.get("phone") or "").split())
    short_title = _clean_name(result.get("title"), "콘텐츠", 24)
    company_name = _clean_name(company, "업체", 30)
    created = str(result.get("created_at") or "")
    try:
        stamp = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone().strftime("%Y%m%d")
    except Exception:
        stamp = datetime.now().strftime("%Y%m%d")
    base_name = f"{company_name}_{short_title}_{stamp}"
    download_name = f"{base_name}_StoryMaker_Beta.zip"

    signature = _signature(result)
    cache_root = job_dir / "output" / "download_cache" / signature
    zip_path = cache_root / download_name
    if zip_path.is_file() and zip_path.stat().st_size > 1024:
        return zip_path, download_name

    assets = result.get("assets") if isinstance(result.get("assets"), dict) else {}
    prepared_dir = cache_root / "prepared_images"
    prepared_dir.mkdir(parents=True, exist_ok=True)

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    temp = zip_path.with_suffix(".tmp.zip")
    if temp.exists():
        temp.unlink()

    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        images = assets.get("images") if isinstance(assets.get("images"), list) else []
        for index, value in enumerate(images, start=1):
            source = _path(value)
            if not source:
                continue
            filename = f"{base_name}_{index:03d}.jpg"
            target = prepared_dir / filename
            if not target.exists() or target.stat().st_size <= 0:
                _watermark_image(source, target, company, phone)
            archive.write(target, filename)

        preferred_assets = (
            (_path(assets.get("thumbnail")), "썸네일"),
            (_path(assets.get("browser_audio")) or _path(assets.get("audio")), "팟캐스트"),
            (_path(assets.get("subtitle")), "자막"),
            (_path(assets.get("browser_video")) or _path(assets.get("video")), "최종영상"),
        )
        for source, label in preferred_assets:
            if not source:
                continue
            archive.write(source, f"{base_name}_{label}{source.suffix.lower()}")

    temp.replace(zip_path)
    return zip_path, download_name
