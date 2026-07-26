# -*- coding: utf-8 -*-
"""딸깍·팟캐스트·릴스/숏츠 결과를 공통 보관함 자산 DB에 등록합니다."""

from __future__ import annotations

import json
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Iterable
from urllib.parse import unquote, urlparse

from app.db.content_asset_repository import (
    list_missing_content_archive_asset_jobs,
    upsert_content_archive_assets,
)


KST = ZoneInfo("Asia/Seoul")


def _now_kst() -> datetime:
    """반드시 한국 시간 기준의 timezone 없는 datetime을 반환합니다."""
    return datetime.now(KST).replace(tzinfo=None)


SOURCE_MENU_ALIASES = {
    "storymaker-main": "one_shot",
    "mobile-one-shot": "one_shot",
    "mobile_one_shot": "one_shot",
    "one-shot": "one_shot",
    "podcast": "podcast",
    "shortform": "shortform",
    "slideshow": "shortform",
    "reels": "shortform",
    "thumbnail": "thumbnail",
}

ASSET_FIELD_MAP: dict[str, dict[str, tuple[str, ...]]] = {
    "mp3": {
        "paths": ("mp3_path", "local_mp3_path", "audio_path", "final_audio_path"),
        "urls": ("mp3_url", "audio_url"),
    },
    "srt": {
        "paths": ("srt_path", "subtitle_path", "caption_path"),
        "urls": ("srt_url", "subtitle_url", "caption_url"),
    },
    "mp4": {
        "paths": ("mp4_path", "video_path", "preview_mp4_path", "final_video_path"),
        "urls": ("mp4_url", "preview_mp4_url", "video_url"),
    },
    "thumbnail": {
        "paths": ("thumbnail_path", "final_image_path", "thumbnail_file", "image_path"),
        "urls": (
            "thumbnail_url", "final_image_url", "thumbnail_prepared_collage_url",
            "thumbnail_collage_url", "collage_url", "image_url", "preview_url",
        ),
    },
}

IMAGE_COLLECTION_KEYS = {
    "images", "image_urls", "saved_public_urls", "project_assets", "assets",
    "generated_images", "downloaded_images", "source_images",
}


def normalize_source_menu(value: Any) -> str:
    raw = str(value or "unknown").strip().lower().replace(" ", "-")
    return SOURCE_MENU_ALIASES.get(raw, raw.replace("-", "_")[:40] or "unknown")


def _safe_name_part(value: Any, fallback: str, limit: int = 60) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._- ")
    return (text or fallback)[:limit]


def _iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _iter_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_dicts(item)


def _first_scalar(value: Any, keys: tuple[str, ...]) -> str:
    roots: list[Any] = []
    if isinstance(value, dict):
        roots.extend([value.get("media"), value.get("result"), value])
    else:
        roots.append(value)
    for root in roots:
        for mapping in _iter_dicts(root):
            for key in keys:
                candidate = mapping.get(key)
                if isinstance(candidate, (str, Path)) and str(candidate).strip():
                    return str(candidate).strip()
    return ""


def _first_named_value(value: Any, keys: tuple[str, ...]) -> str:
    for mapping in _iter_dicts(value):
        for key in keys:
            candidate = mapping.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _normalize_location(value: Any, result_dir: Path | None) -> tuple[str, str]:
    raw = str(value or "").strip()
    if not raw:
        return "", ""
    if raw.startswith(("http://", "https://", "/api/")):
        return "", raw
    if raw.startswith("file://"):
        raw = unquote(urlparse(raw).path)
    try:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute() and result_dir is not None:
            candidate = result_dir / candidate
        candidate = candidate.resolve()
        if candidate.is_file():
            return str(candidate), ""
    except Exception:
        pass
    return "", ""


def _filename_from_location(path_text: str, url_text: str, fallback: str) -> str:
    if path_text:
        return Path(path_text).name
    if url_text:
        try:
            name = unquote(urlparse(url_text).path.rsplit("/", 1)[-1]).strip()
            if name:
                return name
        except Exception:
            pass
    return fallback


def _mime_type(asset_type: str, original_name: str) -> str:
    guessed = mimetypes.guess_type(original_name)[0]
    if guessed:
        return guessed
    return {
        "mp3": "audio/mpeg",
        "mp4": "video/mp4",
        "srt": "text/plain; charset=utf-8",
        "thumbnail": "image/jpeg",
        "image": "image/jpeg",
    }.get(asset_type, "application/octet-stream")


def _parse_created_at(value: Any) -> datetime:
    raw = str(value or "").strip().replace("Z", "+00:00")
    if raw:
        try:
            parsed = datetime.fromisoformat(raw)
            return parsed.astimezone(KST).replace(tzinfo=None) if parsed.tzinfo else parsed
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S", "%Y%m%d_%H%M%S"):
            try:
                return datetime.strptime(raw, fmt)
            except Exception:
                continue
    return _now_kst()


def _first_line(value: Any) -> str:
    for line in str(value or "").splitlines():
        clean = line.strip().lstrip("-•0123456789.) ").strip()
        clean = re.sub(r"^제목\s*[:：]\s*", "", clean).strip()
        if clean:
            return clean
    return ""


def _company_and_keyword(metadata: dict[str, Any]) -> tuple[str, str]:
    persona = metadata.get("persona") if isinstance(metadata.get("persona"), dict) else {}
    extra = metadata.get("extra") if isinstance(metadata.get("extra"), dict) else {}
    company = (
        str(persona.get("company_name") or persona.get("business_name") or persona.get("name") or "").strip()
        or _first_named_value(extra, ("company_name", "business_name", "brand_name", "company", "project_title"))
    )

    keywords = metadata.get("keywords")
    keyword = ""
    if isinstance(keywords, list):
        keyword = next((str(item).strip() for item in keywords if str(item).strip()), "")
    elif isinstance(keywords, str):
        keyword = next((item.strip() for item in re.split(r"[,\n]", keywords) if item.strip()), "")

    outputs = metadata.get("outputs") if isinstance(metadata.get("outputs"), dict) else {}
    title = str(metadata.get("memo") or metadata.get("title") or "").strip()
    if not keyword:
        keyword = _first_line(
            outputs.get("blog_titles")
            or outputs.get("BLOG_TITLES")
            or outputs.get("blog")
            or title
        )
    keyword = re.sub(r"^(팟캐스트|숏폼|숏츠|릴스|썸네일)\s*[·:_-]?\s*", "", keyword).strip() or "콘텐츠"

    if not company:
        company = _first_named_value(metadata, ("company_name", "business_name", "brand_name", "company"))
    if not company and "·" in title:
        company = title.split("·", 1)[1].strip()
    return _safe_name_part(company, "StoryMaker"), _safe_name_part(keyword, "콘텐츠")


def _download_name(metadata: dict[str, Any], asset_type: str, order: int, image_total: int = 0) -> str:
    company, keyword = _company_and_keyword(metadata)
    stamp = _parse_created_at(metadata.get("created_at") or metadata.get("updated_at")).strftime("%Y%m%d_%H%M%S")
    base = f"{company}_{keyword}_{stamp}"
    if asset_type == "mp3":
        return f"{base}.mp3"
    if asset_type == "mp4":
        return f"{base}.mp4"
    if asset_type in {"image", "thumbnail"}:
        suffix = f"_{order + 1:02d}" if asset_type == "image" and image_total > 1 else ""
        return f"{base}{suffix}.jpg"
    if asset_type == "srt":
        return f"{base}.srt"
    return f"{base}.bin"


def _single_asset_candidates(payload: dict[str, Any], metadata: dict[str, Any], result_dir: Path | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    disk_fallbacks = {
        "mp3": ("media/browser_podcast.mp3", "media/podcast_audio.mp3", "media/podcast.mp3"),
        "srt": ("media/browser_podcast.srt", "media/podcast_subtitle.srt", "media/subtitle.srt"),
        "mp4": ("media/shortform.mp4",),
        "thumbnail": ("media/thumbnail.jpg", "media/thumbnail.jpeg", "media/thumbnail.png"),
    }
    for asset_type, fields in ASSET_FIELD_MAP.items():
        path_value = _first_scalar(payload, fields["paths"])
        url_value = _first_scalar(payload, fields["urls"])
        stored_path, path_url = _normalize_location(path_value, result_dir)
        public_url = path_url or _normalize_location(url_value, result_dir)[1]
        if not stored_path and result_dir is not None:
            for relative_name in disk_fallbacks.get(asset_type, ()):
                candidate = (result_dir / relative_name).resolve()
                if candidate.is_file() and result_dir.resolve() in candidate.parents:
                    stored_path = str(candidate)
                    public_url = ""
                    break
        if not stored_path and not public_url:
            continue
        original = _filename_from_location(stored_path, public_url, f"{asset_type}")
        file_size = 0
        if stored_path:
            try:
                file_size = Path(stored_path).stat().st_size
            except OSError:
                file_size = 0
        items.append({
            "asset_type": asset_type,
            "asset_order": 0,
            "stored_path": stored_path,
            "public_url": public_url,
            "original_filename": original,
            "download_name": _download_name(metadata, asset_type, 0),
            "mime_type": _mime_type(asset_type, original),
            "file_size": file_size,
            "status": "ready",
        })
    return items


def _looks_like_image(value: str, item: dict[str, Any] | None = None) -> bool:
    lower = value.lower().split("?", 1)[0]
    if lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif")):
        return True
    if item:
        kind = str(item.get("type") or item.get("asset_type") or item.get("mime_type") or "").lower()
        return "image" in kind or "thumbnail" in kind
    return False


def _image_values(payload: Any) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    def add(value: Any, item: dict[str, Any] | None = None) -> None:
        if isinstance(value, str) and value.strip() and _looks_like_image(value.strip(), item):
            found.append((value.strip(), str((item or {}).get("name") or (item or {}).get("stored_name") or "")))
        elif isinstance(value, dict):
            marker = " ".join(str(value.get(key) or "") for key in ("name", "stored_name", "url", "path")).lower()
            if value.get("default_image") or "default_shortform_image" in marker:
                return
            for key in ("path", "stored_path", "local_path", "image_path", "url", "image_url", "download_url", "preview_url"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip() and _looks_like_image(candidate.strip(), value):
                    found.append((candidate.strip(), str(value.get("name") or value.get("stored_name") or "")))
                    return

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in IMAGE_COLLECTION_KEYS:
                    if isinstance(item, list):
                        for child in item:
                            add(child, child if isinstance(child, dict) else None)
                    else:
                        add(item, item if isinstance(item, dict) else None)
                if isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for location, name in found:
        if location in seen:
            continue
        seen.add(location)
        unique.append((location, name))
    return unique[:30]


def _image_asset_candidates(payload: dict[str, Any], metadata: dict[str, Any], result_dir: Path | None) -> list[dict[str, Any]]:
    raw_images = _image_values(payload)
    if result_dir is not None:
        image_dir = result_dir / "images"
        if image_dir.is_dir():
            disk_images = [
                (str(path.resolve()), path.name)
                for path in sorted(image_dir.iterdir())
                if path.is_file() and _looks_like_image(path.name)
            ]
            seen_locations = {str(location) for location, _ in raw_images}
            for location, supplied_name in disk_images:
                if location not in seen_locations:
                    raw_images.append((location, supplied_name))
                    seen_locations.add(location)
    items: list[dict[str, Any]] = []
    for index, (location, supplied_name) in enumerate(raw_images):
        stored_path, public_url = _normalize_location(location, result_dir)
        if not stored_path and not public_url:
            continue
        original = supplied_name or _filename_from_location(stored_path, public_url, f"image_{index + 1}.jpg")
        file_size = 0
        if stored_path:
            try:
                file_size = Path(stored_path).stat().st_size
            except OSError:
                file_size = 0
        items.append({
            "asset_type": "image",
            "asset_order": index,
            "stored_path": stored_path,
            "public_url": public_url,
            "original_filename": original,
            "download_name": "",
            "mime_type": _mime_type("image", original),
            "file_size": file_size,
            "status": "ready",
        })
    total = len(items)
    for item in items:
        item["download_name"] = _download_name(metadata, "image", int(item["asset_order"]), total)
    return items


def sync_content_archive_assets(
    *,
    user_id: int,
    archive_job_id: str,
    archive_group_key: str,
    source_menu: str,
    source_job_id: str,
    payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    result_dir: Path | None = None,
) -> list[int]:
    if not user_id or not archive_job_id or not isinstance(payload, dict):
        return []
    metadata_value = dict(metadata or payload)
    assets = _single_asset_candidates(payload, metadata_value, result_dir)
    assets.extend(_image_asset_candidates(payload, metadata_value, result_dir))
    if not assets:
        return []
    now_text = _now_kst().isoformat(timespec="seconds")
    created_text = str(metadata_value.get("created_at") or now_text)
    return upsert_content_archive_assets(
        user_id=int(user_id),
        archive_job_id=str(archive_job_id),
        archive_group_key=str(archive_group_key or ""),
        source_menu=normalize_source_menu(source_menu),
        source_job_id=str(source_job_id or archive_job_id),
        assets=assets,
        created_at=created_text,
        updated_at=now_text,
    )


def backfill_recent_content_archive_assets(limit: int = 200) -> dict[str, int]:
    scanned = 0
    registered = 0
    failed = 0
    for row in list_missing_content_archive_asset_jobs(limit):
        scanned += 1
        try:
            job_id = str(row.get("job_id") or "").strip()
            user_id = int(row.get("user_id") or 0)
            result_file = Path(str(row.get("result_path") or "")).expanduser().resolve()
            if not job_id or not user_id or not result_file.is_file():
                continue
            data = json.loads(result_file.read_text(encoding="utf-8"))
            ids = sync_content_archive_assets(
                user_id=user_id,
                archive_job_id=job_id,
                archive_group_key=str(data.get("archive_group_key") or job_id),
                source_menu=str(data.get("latest_source") or data.get("source") or "mobile-one-shot"),
                source_job_id=str(data.get("latest_source_job_id") or data.get("source_job_id") or job_id),
                payload=data,
                metadata=data,
                result_dir=result_file.parent,
            )
            registered += len(ids)
        except Exception:
            failed += 1
    return {"scanned": scanned, "registered": registered, "failed": failed}
