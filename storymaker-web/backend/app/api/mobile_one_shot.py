# -*- coding: utf-8 -*-
"""
Mobile One-Shot Backend v2A

스마트폰 작업실에서 메모와 사진을 한 번에 받아 작업 단위를 생성하는 최소 안정 API입니다.
실제 장시간 생성 파이프라인은 다음 단계에서 워커/큐와 연결하고, v2A에서는 다음을 보장합니다.

- 로그인 사용자는 user_id 기준으로 작업을 분리합니다.
- 비로그인 사용자는 guest 버킷에 저장하되, 운영 파일은 output_results 하위에만 생성합니다.
- 원본 이미지는 안전한 파일명으로 보관합니다.
- 작업 상태와 결과 미리보기 JSON을 생성합니다.
- 삭제 동작은 제공하지 않습니다.
"""

from __future__ import annotations

import io
import json
import os
import re
import logging
import threading
import time
import uuid
import zipfile
import shutil
import subprocess
import random
import httpx
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, unquote, urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.auth import get_current_user, get_optional_current_user
from app.api.podcast import API_URL as WORKER_API_URL, normalize_podcast_speaker_tags, upstream_headers
from app.db.database import get_db
from app.db.models import User, UserPersona
from app.services.content_integrity_service import delete_job_bundle
from app.db.mobile_one_shot_repository import delete_mobile_one_shot_job, get_mobile_one_shot_admin_usage, get_mobile_one_shot_progress, get_mobile_one_shot_result_path, list_mobile_one_shot_admin_queue, list_mobile_one_shot_job_summaries, list_mobile_one_shot_result_paths, list_mobile_one_shot_title_backfill_candidates, sync_mobile_one_shot_job_from_result, update_mobile_one_shot_job_memo, update_mobile_one_shot_progress, upsert_mobile_one_shot_job
from app.schemas import PromptRequest, ResultParseRequest
from app.services import StoryMakerService
from starlette.responses import FileResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(prefix="/mobile/one-shot", tags=["Mobile One-Shot"])
logger = logging.getLogger(__name__)

KST_DATE_FORMAT = "%Y%m%d"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}
MAX_IMAGES = 12
MAX_STAGED_VIDEOS = 4
MAX_STAGED_VIDEO_BYTES = 1024 * 1024 * 1024
MIN_IMAGES = 5
MIN_MEMO_LENGTH = 10

_THUMBNAIL_TIMER_LOCK = threading.Lock()
_THUMBNAIL_TIMER_KEYS: set[str] = set()


def _now() -> datetime:
    return datetime.now()


def _output_root() -> Path:
    return Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))


def _safe_filename(name: str, fallback: str) -> str:
    base = Path(name or fallback).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return base or fallback


def _job_dir(job_id: str, created_date: Optional[str] = None) -> Path:
    date_key = created_date or _now().strftime(KST_DATE_FORMAT)
    return _output_root() / "mobile_one_shot" / date_key / job_id


def _job_url_path(job_dir: Path, file_path: Path) -> str:
    rel = file_path.relative_to(_output_root())
    return "/data/output_results/" + "/".join(rel.parts)


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def _display_filename(value: Any, fallback: Optional[str] = None) -> Optional[str]:
    if not value:
        return fallback
    filename = Path(str(value).split("?", 1)[0].rstrip("/")).name
    return filename or fallback


def _mobile_project_files(data: dict[str, Any]) -> dict[str, Optional[str]]:
    media = data.get("media") or {}
    job_id = str(data.get("job_id") or "mobile")
    return {
        "text_filename": "generated_text.txt",
        "mp3_filename": _display_filename(media.get("mp3_path") or media.get("mp3_url")),
        "srt_filename": _display_filename(media.get("srt_path") or media.get("srt_url")),
        "mp4_filename": _display_filename(media.get("mp4_path") or media.get("mp4_url")),
        "thumbnail_filename": _display_filename(media.get("thumbnail_path") or media.get("thumbnail_url") or media.get("thumbnail_prepared_collage_url") or media.get("thumbnail_collage_url") or media.get("collage_url")),
        "zip_filename": f"storymaker_mobile_{job_id}.zip",
    }


def _extract_raw_result_block(text: Any, block_name: str) -> str:
    raw = str(text or "")
    start_tag = f"[BLOCK:{block_name}]"
    start = raw.find(start_tag)
    if start < 0:
        return ""
    rest = raw[start + len(start_tag):]
    next_match = re.search(r"\n\s*\[BLOCK:[A-Z0-9_]+\]", rest)
    return (rest[: next_match.start()] if next_match else rest).strip()


def _clean_mobile_title_line(value: Any) -> str:
    line = str(value or "").strip().strip("# ").strip()
    line = line.lstrip("-• ").strip()
    line = re.sub(r"^\d+[.)]\s*", "", line).strip()
    line = re.sub(r"^제목\s*[:：]\s*", "", line).strip()
    if line.startswith("[") and line.endswith("]"):
        return ""
    return line


def _first_mobile_blog_title(value: Any) -> str:
    for raw_line in str(value or "").splitlines():
        line = _clean_mobile_title_line(raw_line)
        if line and len(line) >= 4:
            return line[:80]
    return ""


def _archive_persona_from_data(data: dict[str, Any]) -> dict[str, str] | None:
    persona = data.get("persona") or {}
    company_name = str(persona.get("company_name") or "").strip()
    phone_number = str(persona.get("phone_number") or "").strip()
    region = str(persona.get("region") or "").strip()
    text = json.dumps(data.get("extra") or {}, ensure_ascii=False)
    if not company_name:
        match = re.search(r"워터마크:\s*([^/\n]+?)\s*/\s*([0-9\-]{8,})", text)
        if match:
            company_name = match.group(1).strip()
            phone_number = phone_number or match.group(2).strip()
    if not company_name:
        match = re.search(r"--brand-name\s+([^\s]+)", text)
        if match:
            company_name = match.group(1).strip()
    if not phone_number:
        match = re.search(r"(01[016789]-?\d{3,4}-?\d{4})", text)
        if match:
            phone_number = match.group(1).strip()
    if not company_name:
        return None
    return {"company_name": company_name[:80], "phone_number": phone_number, "region": region}


def _mobile_job_title(data: dict[str, Any]) -> str:
    outputs = data.get("outputs") or {}
    title = (
        _first_mobile_blog_title(outputs.get("blog_titles"))
        or _first_mobile_blog_title(outputs.get("BLOG_TITLES"))
        or _first_mobile_blog_title(_extract_raw_result_block(data.get("raw_result"), "BLOG_TITLES"))
        or _first_mobile_blog_title(outputs.get("blog"))
        or _first_mobile_blog_title(outputs.get("BLOG"))
    )
    if title:
        return title
    persona = _archive_persona_from_data(data) or {}
    company_name = str(persona.get("company_name") or "").strip()
    if company_name:
        return company_name[:80]
    return str(data.get("job_id") or "저장 작업")


def _mobile_archive_has_content(data: dict[str, Any]) -> bool:
    if not data:
        return False
    if str(data.get("status") or "").lower() == "deleted" or data.get("deleted_at"):
        return False
    raw_result = str(data.get("raw_result") or "").strip()
    if raw_result:
        return True
    outputs = data.get("outputs") or {}
    if isinstance(outputs, dict):
        for key in [
            "blog",
            "BLOG",
            "blog_post",
            "BLOG_POST",
            "blog_titles",
            "BLOG_TITLES",
            "instagram",
            "INSTAGRAM_POST",
            "place",
            "NAVER_PLACE_NEWS",
            "google_business",
            "GOOGLE_BUSINESS_POST",
            "carrot",
            "CARROT_POST",
            "podcast50",
            "PODCAST_50",
            "podcast80",
            "PODCAST_80",
        ]:
            if str(outputs.get(key) or "").strip():
                return True
    media = data.get("media") or {}
    if isinstance(media, dict):
        for key in ["mp3_url", "mp3_path", "mp4_url", "mp4_path", "thumbnail_url"]:
            if media.get(key):
                return True
    return False


def _is_supported_mobile_job_id(job_id: str) -> bool:
    return bool(
        re.fullmatch(r"mob-[0-9]{14}-[a-f0-9]{8}", job_id)
        or re.fullmatch(r"storymaker_main_[0-9]{14}", job_id)
    )


def _find_mobile_result_file(job_id: str, current_user: User) -> Path:
    if not _is_supported_mobile_job_id(job_id):
        raise HTTPException(status_code=400, detail="job_id 형식이 올바르지 않습니다.")
    db_path = get_mobile_one_shot_result_path(job_id, current_user.id)
    result_file = Path(db_path) if db_path else None
    if not result_file or not result_file.exists():
        base = _output_root() / "mobile_one_shot"
        matches = list(base.glob(f"*/{job_id}/result.json")) if base.exists() else []
        if not matches and re.fullmatch(r"storymaker_main_[0-9]{14}", job_id) and base.exists():
            for candidate in sorted(base.glob("*/mob-*/result.json"), reverse=True):
                try:
                    candidate_data = json.loads(candidate.read_text(encoding="utf-8"))
                except Exception:
                    continue
                pipeline = candidate_data.get("pipeline") or {}
                source_job_id = str(
                    candidate_data.get("source_job_id")
                    or candidate_data.get("archive_group_key")
                    or pipeline.get("source_job_id")
                    or pipeline.get("archive_group_key")
                    or ""
                ).strip()
                if source_job_id == job_id and str(candidate_data.get("user_bucket")) == str(current_user.id):
                    matches = [candidate]
                    break
        if not matches:
            raise HTTPException(status_code=404, detail="작업 결과를 찾을 수 없습니다.")
        result_file = matches[0]
    data = json.loads(result_file.read_text(encoding="utf-8"))
    if str(data.get("user_bucket")) != str(current_user.id):
        raise HTTPException(status_code=404, detail="작업 결과를 찾을 수 없습니다.")
    return result_file


def _safe_existing_output_file(value: Any) -> Optional[Path]:
    if not value:
        return None
    candidate = Path(str(value).split("?", 1)[0])
    if not candidate.is_absolute():
        return None
    output_root = _output_root().resolve()
    try:
        resolved = candidate.resolve()
    except Exception:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    if output_root not in resolved.parents:
        return None
    return resolved


def _safe_output_file_from_public_url(value: Any) -> Optional[Path]:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    path_value = unquote(parsed.path or raw.split("?", 1)[0])
    if not path_value.startswith("/data/output_results/"):
        return None
    rel = path_value.replace("/data/output_results/", "", 1).lstrip("/")
    if not rel:
        return None
    output_root = _output_root().resolve()
    candidate = output_root / rel
    try:
        resolved = candidate.resolve()
    except Exception:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    if output_root not in resolved.parents:
        return None
    return resolved


def _find_output_file_by_name(filename: str, preferred_dirs: Optional[list[Path]] = None) -> Optional[Path]:
    safe_name = Path(str(filename or "").split("?", 1)[0]).name
    if not safe_name or safe_name in {".", ".."}:
        return None
    output_root = _output_root().resolve()
    search_dirs = [path for path in (preferred_dirs or []) if path]
    search_dirs.append(output_root)
    seen: set[str] = set()
    matches: list[Path] = []
    for base_dir in search_dirs:
        try:
            base = base_dir.resolve()
        except Exception:
            continue
        if str(base) in seen or (base != output_root and output_root not in base.parents):
            continue
        seen.add(str(base))
        candidate = base / safe_name
        if candidate.exists() and candidate.is_file():
            matches.append(candidate)
            continue
        try:
            for found in base.rglob(safe_name):
                if found.is_file():
                    matches.append(found)
        except Exception:
            continue
    for found in sorted(matches, key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True):
        try:
            resolved = found.resolve()
        except Exception:
            continue
        if resolved.exists() and resolved.is_file() and output_root in resolved.parents:
            return resolved
    return None


def _resolve_mobile_download_file(value: Any, job_dir: Optional[Path] = None) -> Optional[Path]:
    if not value:
        return None
    direct = _safe_existing_output_file(value)
    if direct:
        return direct
    public_file = _safe_output_file_from_public_url(value)
    if public_file:
        return public_file
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    path_value = unquote(parsed.path or raw.split("?", 1)[0])
    filename = Path(path_value).name
    preferred_dirs: list[Path] = []
    if job_dir:
        preferred_dirs.extend([
            job_dir,
            job_dir / "media",
            job_dir / "videos",
            job_dir / "audio",
            job_dir / "images",
            job_dir / "prepared",
        ])
        if "/api/podcast/media/" in path_value:
            podcast_name_map = {
                "mp3": ["podcast_audio.mp3", "audio.mp3", "podcast.mp3"],
                "srt": ["podcast_subtitle.srt", "subtitle.srt", "caption.srt"],
            }
            for mapped_name in podcast_name_map.get(filename.lower(), []):
                found = _find_output_file_by_name(mapped_name, preferred_dirs)
                if found:
                    return found
    if filename:
        found = _find_output_file_by_name(filename, preferred_dirs)
        if found:
            return found
        if path_value.startswith("/media/") or path_value.startswith("/api/slideshow/media/"):
            extra_dirs = [
                _output_root() / "test_result_packages",
                _output_root() / "test_thumbnail_jobs",
                _output_root() / "test_slideshow_safe_images",
                _output_root() / "mobile_one_shot",
                Path("/home/bourne/StoryMaker_1/storymaker-web/backend/app/static"),
                Path("/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/media"),
                Path("/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/media/slideshow"),
            ]
            return _find_output_file_by_name(filename, preferred_dirs + extra_dirs)
    return None


def _mobile_media_candidates(media: dict[str, Any], file_kind: str) -> list[Any]:
    if file_kind == "mp3":
        keys = ["mp3_path", "local_mp3_path", "audio_path", "mp3_url", "audio_url"]
    elif file_kind == "srt":
        keys = ["srt_path", "subtitle_path", "caption_path", "srt_url", "subtitle_url", "caption_url"]
    elif file_kind == "mp4":
        keys = ["mp4_path", "video_path", "mp4_url", "preview_mp4_url", "download_url", "video_url"]
    elif file_kind == "thumbnail":
        keys = ["thumbnail_path", "thumbnail_url", "thumbnail_prepared_collage_url", "thumbnail_collage_url", "collage_url", "image_url", "download_url"]
    else:
        keys = []
    return [media.get(key) for key in keys if media.get(key)]


def _first_mobile_media_file(media: dict[str, Any], file_kind: str, job_dir: Optional[Path] = None) -> Optional[Path]:
    for value in _mobile_media_candidates(media, file_kind):
        found = _resolve_mobile_download_file(value, job_dir)
        if found:
            return found

    # result.json의 media 필드가 비어 있거나 예전 job_id URL을 가리켜도
    # V1 보관함은 현재 작업 폴더에 실제로 저장된 전용 미디어를 우선 발견합니다.
    if job_dir:
        direct_names = {
            "mp3": "browser_podcast.mp3",
            "srt": "browser_podcast.srt",
            "thumbnail": "thumbnail.jpg",
            "mp4": "shortform.mp4",
        }
        direct_name = direct_names.get(file_kind)
        if direct_name:
            direct_file = job_dir / "media" / direct_name
            if direct_file.exists() and direct_file.is_file() and direct_file.stat().st_size > 0:
                return direct_file
    return None


def _mobile_download_file_urls(job_id: str, data: dict[str, Any], job_dir: Optional[Path] = None) -> dict[str, str]:
    urls: dict[str, str] = {}
    outputs = data.get("outputs") or {}
    raw_result = str(data.get("raw_result") or "").strip()
    media = data.get("media") or {}
    if raw_result or any(str(outputs.get(key) or "").strip() for key in ["blog", "BLOG", "blog_post", "BLOG_POST", "instagram", "INSTAGRAM_POST", "place", "NAVER_PLACE_NEWS", "google_business", "GOOGLE_BUSINESS_POST", "carrot", "CARROT_POST", "podcast50", "PODCAST_50", "podcast80", "PODCAST_80"]):
        urls["text"] = f"/api/mobile/one-shot/jobs/{job_id}/files/text"
    image_dir = (job_dir / "images") if job_dir else None
    has_images = bool(
        (image_dir and image_dir.exists() and any(path.is_file() for path in image_dir.iterdir()))
        or data.get("images")
        or int(data.get("image_count") or 0) > 0
    )
    if has_images:
        urls["images"] = f"/api/mobile/one-shot/jobs/{job_id}/files/images"
    if _first_mobile_media_file(media, "mp3", job_dir):
        urls["mp3"] = f"/api/mobile/one-shot/jobs/{job_id}/files/mp3"
    if _first_mobile_media_file(media, "mp4", job_dir):
        urls["mp4"] = f"/api/mobile/one-shot/jobs/{job_id}/files/mp4"
    if _first_mobile_media_file(media, "thumbnail", job_dir):
        urls["thumbnail"] = f"/api/mobile/one-shot/jobs/{job_id}/files/thumbnail"
    return urls


def _mobile_download_zip_has_files(data: dict[str, Any], job_dir: Optional[Path] = None) -> bool:
    if not job_dir:
        return False
    outputs = data.get("outputs") or {}
    if str(data.get("raw_result") or "").strip() or any(str(outputs.get(key) or "").strip() for key in outputs):
        return True
    image_dir = job_dir / "images"
    if image_dir.exists() and any(path.is_file() for path in image_dir.iterdir()):
        return True
    if data.get("images") or int(data.get("image_count") or 0) > 0:
        return True
    media = data.get("media") or {}
    if any(_first_mobile_media_file(media, file_kind, job_dir) for file_kind in ["mp3", "mp4", "thumbnail"]):
        return True
    return False


def _extract_keywords(memo: str) -> list[str]:
    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", memo)
    stop = {"오늘", "그리고", "하지만", "있는", "합니다", "합니다", "입니다", "좋습니다", "때문", "관련"}
    ranked: list[str] = []
    for word in words:
        if word in stop:
            continue
        if word not in ranked:
            ranked.append(word)
        if len(ranked) >= 8:
            break
    return ranked


def _persona_keywords(persona: Optional[UserPersona]) -> list[str]:
    if not persona:
        return []
    try:
        values = json.loads(persona.keywords_json or "[]")
        if isinstance(values, list):
            return [str(item).strip() for item in values if str(item).strip()][:12]
    except Exception:
        pass
    return []


def _thumbnail_cover_safe(image, target_size: tuple[int, int]):
    from PIL import Image

    target_w, target_h = target_size
    if target_w <= 0 or target_h <= 0:
        return image.copy()

    src = image.convert("RGB")
    src_w, src_h = src.size
    if src_w <= 0 or src_h <= 0:
        return Image.new("RGB", target_size, "#111111")

    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        new_h = target_h
        new_w = max(1, round(new_h * src_ratio))
    else:
        new_w = target_w
        new_h = max(1, round(new_w / src_ratio))

    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _make_mobile_thumbnail_collage(image_paths: list[Path], output_path: Path) -> Path:
    from PIL import Image

    canvas_w, canvas_h = 1080, 1920
    gap = 16
    canvas = Image.new("RGB", (canvas_w, canvas_h), "#111111")

    top_h = 980
    bottom_h = canvas_h - top_h - (gap * 3)
    top_box = (gap, gap, canvas_w - gap, gap + top_h)
    left_box = (gap, top_box[3] + gap, (canvas_w // 2) - (gap // 2), top_box[3] + gap + bottom_h)
    right_box = ((canvas_w // 2) + (gap // 2), top_box[3] + gap, canvas_w - gap, top_box[3] + gap + bottom_h)

    boxes = [top_box, left_box, right_box]
    for idx, img_path in enumerate(image_paths[:3]):
        if idx >= len(boxes):
            break
        x1, y1, x2, y2 = boxes[idx]
        with Image.open(img_path) as src:
            fitted = _thumbnail_cover_safe(src, (x2 - x1, y2 - y1))
            canvas.paste(fitted, (x1, y1))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="JPEG", quality=88, optimize=True)
    return output_path


def _make_mobile_fallback_image(output_path: Path) -> Path:
    from PIL import Image
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (720, 1280), "#111827").save(output_path, format="JPEG", quality=90, optimize=True)
    return output_path


def _prepare_video_safe_image(source_path: Path, safe_dir: Path, index: int) -> Path:
    try:
        from PIL import Image, ImageOps
        if not source_path.exists() or not source_path.is_file() or source_path.stat().st_size < 1024:
            return source_path
        safe_dir.mkdir(parents=True, exist_ok=True)
        target = safe_dir / f"video_image_{index:03d}.jpg"
        with Image.open(source_path) as probe:
            probe.verify()
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", image.size, (255, 255, 255))
                bg.paste(image, mask=image.getchannel("A"))
                image = bg
            else:
                image = image.convert("RGB")
            width, height = image.size
            if width < 64 or height < 64:
                return source_path
            scale = min(1.0, 1920 / max(width, height))
            if scale < 1.0:
                image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.LANCZOS)
            image.save(target, format="JPEG", quality=92, optimize=True, progressive=False)
        if target.exists() and target.stat().st_size > 10 * 1024:
            return target
    except Exception:
        return source_path
    return source_path


def _format_image_reference(saved_images: list[dict[str, Any]]) -> str:
    if not saved_images:
        return "사진은 아직 첨부되지 않았습니다."
    lines = [
        "[모바일 현장 사진 참고]",
        "- 아래 항목은 사용자가 업로드한 사진의 파일명과 내부 참고 URL입니다.",
        "- Gemini가 이미지를 직접 분석하지 못해도 괜찮습니다.",
        "- 이미지 판독을 거절하지 말고, 메모/업체 정보/키워드를 중심으로 콘텐츠를 작성하세요.",
        "- 사진은 현장감과 소재 분위기를 보강하는 참고 자료로만 사용하세요.",
    ]
    for idx, item in enumerate(saved_images[:6], start=1):
        lines.append(f"{idx}. {item.get('name')} - {item.get('url')}")
    return "\n".join(lines)


def _looks_like_ready_prompt(text: str) -> bool:
    value = str(text or "").strip()
    if len(value) < 800:
        return False
    markers = [
        "[BLOCK:",
        "BLOG_POST",
        "INSTAGRAM_POST",
        "NAVER_PLACE",
        "NAVER_PLACE_NEWS",
        "GOOGLE_BUSINESS",
        "GOOGLE_BUSINESS_POST",
        "CARROT_POST",
        "DAANGN_POST",
        "PODCAST_50",
        "PODCAST_80",
    ]
    hit_count = sum(1 for marker in markers if marker in value)
    return hit_count >= 3


def _clean_mobile_one_shot_memo_for_prompt(memo: str) -> tuple[str, dict[str, Any]]:
    raw = str(memo or "").replace("\r\n", "\n").replace("\r", "\n")
    removed_mobile_image_section = False

    mobile_image_block = re.search(r"(?is)\[모바일 현장 사진 참고\].*?(?=\n\s*\n|\Z)", raw)
    if mobile_image_block:
        removed_mobile_image_section = True
        raw = raw[: mobile_image_block.start()] + raw[mobile_image_block.end():]

    ui_noise_patterns = [
        r"(?im)^\s*프로파일\s*$",
        r"(?im)^\s*URL 복사 통계\s*$",
        r"(?im)^\s*본문 기타 기능\s*$",
        r"(?im)^\s*블로그 메뉴\s*$",
        r"(?im)^\s*프롤로그 블로그\s*$",
        r"(?im)^\s*지도 서재 안부\s*$",
        r"(?im)^\s*공지 목록\s*$",
        r"(?im)^\s*공지글\s*$",
        r"(?im)^\s*글 제목 작성일\s*$",
        r"(?im)^\s*삭제 공지\s*$",
        r"(?im)^\s*통계\s*$",
        r"(?im)^\s*서로이웃\s*$",
        r"(?im)^\s*댓글\s*$",
        r"(?im)^\s*공유하기\s*$",
        r"(?im)^\s*이 블로그의 체크인\s*$",
        r"(?im)^\s*카테고리 글\s*$",
        r"(?im)^\s*이전 다음\s*$",
        r"(?im)^\s*네이버 블로그 UI성 문장\s*$",
    ]
    for pattern in ui_noise_patterns:
        raw = re.sub(pattern, "", raw)

    raw = re.sub(r"/data/output_results/[^\s)\"']+", "", raw)
    raw = re.sub(r"/mobile_one_shot/[^\s)\"']+", "", raw)
    raw = re.sub(r"/test_thumbnail_jobs/[^\s)\"']+", "", raw)
    raw = re.sub(r"/images/[^\s)\"']+", "", raw)
    raw = re.sub(r"(?im)^\s*Gemini가 이미지를 직접 분석하지 못해도 괜찮습니다.*$", "", raw)
    raw = re.sub(r"(?im)^\s*사진은 image upload로 처리되므로 memo 텍스트에는 내부 URL 목록을 넣지 않아야 합니다.*$", "", raw)

    cleaned_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if stripped.startswith("-") and any(token in stripped for token in ["/data/output_results/", "/mobile_one_shot/", "/test_thumbnail_jobs/", "/images/"]):
            continue
        cleaned_lines.append(line.rstrip())

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, {"removed_mobile_image_section": removed_mobile_image_section}


def _clean_mobile_one_shot_memo_for_prompt_v2(memo: str) -> tuple[str, dict[str, Any]]:
    raw = str(memo or "").replace("\r\n", "\n").replace("\r", "\n")
    removed_mobile_image_section = False

    interim_lines: list[str] = []
    skip_image_lines = False
    for line in raw.splitlines():
        stripped = line.strip()
        if "모바일 현장 사진 참고" in stripped:
            removed_mobile_image_section = True
            skip_image_lines = True
            continue
        if skip_image_lines:
            if not stripped:
                skip_image_lines = False
                interim_lines.append("")
                continue
            if any(
                token in stripped
                for token in (
                    "/data/output_results/",
                    "/mobile_one_shot/",
                    "/test_thumbnail_jobs/",
                    "/images/",
                    "Gemini가 이미지를 직접 분석하지 못해도 괜찮습니다",
                    "사진은 image upload로 처리되므로 memo 텍스트에는 내부 URL 목록을 넣지 않아야 합니다",
                )
            ) or re.match(r"^[\-\*•]\s*", stripped) or re.match(r"^\s*[\w./-]+\.(?:jpg|jpeg|png|webp|gif)\b", stripped, re.I):
                continue
            skip_image_lines = False
        interim_lines.append(line)

    ui_noise_patterns = [
        r"(?im)^\s*프로파일\s*$",
        r"(?im)^\s*URL 복사 통계\s*$",
        r"(?im)^\s*본문 기타 기능\s*$",
        r"(?im)^\s*블로그 메뉴\s*$",
        r"(?im)^\s*프롤로그 블로그\s*$",
        r"(?im)^\s*지도 서재 안부\s*$",
        r"(?im)^\s*공지 목록\s*$",
        r"(?im)^\s*공지글\s*$",
        r"(?im)^\s*글 제목 작성일\s*$",
        r"(?im)^\s*삭제 공지\s*$",
        r"(?im)^\s*통계\s*$",
        r"(?im)^\s*서로이웃\s*$",
        r"(?im)^\s*댓글\s*$",
        r"(?im)^\s*공유하기\s*$",
        r"(?im)^\s*이 블로그의 체크인\s*$",
        r"(?im)^\s*카테고리 글\s*$",
        r"(?im)^\s*이전 다음\s*$",
        r"(?im)^\s*네이버 블로그 UI성 문장\s*$",
    ]
    raw = "\n".join(interim_lines)
    for pattern in ui_noise_patterns:
        raw = re.sub(pattern, "", raw)

    raw = re.sub(r"/data/output_results/[^\s)\"']+", "", raw)
    raw = re.sub(r"/mobile_one_shot/[^\s)\"']+", "", raw)
    raw = re.sub(r"/test_thumbnail_jobs/[^\s)\"']+", "", raw)
    raw = re.sub(r"/images/[^\s)\"']+", "", raw)
    raw = re.sub(r"(?im)^\s*Gemini가 이미지를 직접 분석하지 못해도 괜찮습니다.*$", "", raw)
    raw = re.sub(r"(?im)^\s*사진은 image upload로 처리되므로 memo 텍스트에는 내부 URL 목록을 넣지 않아야 합니다.*$", "", raw)

    cleaned_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if stripped.startswith("-") and any(token in stripped for token in ["/data/output_results/", "/mobile_one_shot/", "/test_thumbnail_jobs/", "/images/"]):
            continue
        cleaned_lines.append(line.rstrip())

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, {"removed_mobile_image_section": removed_mobile_image_section}


def _format_prompt_for_worker(text_value: str) -> str:
    value = str(text_value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value:
        return ""
    sub_titles = [
        "작성 원칙",
        "작성 참고",
        "전체 원칙",
        "주의",
        "예시",
        "출력 형식",
        "콘텐츠 통합 패키지 생성 프롬프트",
    ]
    for title in sub_titles:
        value = re.sub(r"\s*#{2,3}\s*" + re.escape(title) + r"\s*", "\n\n### " + title + "\n\n", value)
    value = re.sub(r"\s*(\[BLOCK:[A-Z0-9_]+\])\s*", r"\n\n\1\n", value)
    value = re.sub(r"([가-힣A-Za-z0-9).])(-\s+)", r"\1\n\2", value)
    value = re.sub(r"(작성 원칙|작성 참고|주의|전체 원칙|예시)(-\s+)", r"\1\n\2", value)
    value = re.sub(r"(BLOG_POST, CARROT_POST|NAVER_PLACE_NEWS, GOOGLE_BUSINESS_POST|INSTAGRAM_POST|CAROUSEL_7|PODCAST_50, PODCAST_80)(-\s+)", r"\1\n\2", value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    return value


def _build_worker_prompt(persona: Optional[UserPersona], memo: str, keywords: list[str], saved_images: list[dict[str, Any]]) -> str:
    raw_memo = memo or ""
    cleaned_memo, clean_meta = _clean_mobile_one_shot_memo_for_prompt_v2(raw_memo)
    ready_prompt_detected = _looks_like_ready_prompt(cleaned_memo)
    logger.info(
        "mobile one-shot prompt prep raw_memo_len=%s cleaned_memo_len=%s removed_mobile_image_section=%s ready_prompt_detected=%s",
        len(raw_memo),
        len(cleaned_memo),
        clean_meta.get("removed_mobile_image_section"),
        ready_prompt_detected,
    )
    if ready_prompt_detected:
        prompt = "\n\n".join([cleaned_memo.strip(), _format_image_reference(saved_images)]).strip()
        logger.info("mobile one-shot prompt ready_prompt_len=%s", len(prompt))
        return prompt

    company_name = persona.company_name if persona else "모바일 현장 업체"
    persona_text = persona.content if persona else "모바일 현장 메모를 바탕으로 지역 소상공인 관점의 콘텐츠를 생성합니다."
    industry_key = persona.industry_key if persona else "general"
    req = PromptRequest(
        company=company_name,
        persona=persona_text,
        base_content=cleaned_memo,
        reference_text=_format_image_reference(saved_images),
        keywords=keywords,
        style="따뜻하고 자연스러운 지역 소상공인 홍보 글",
        ai_preset="gemini",
        region=getattr(persona, "region", None) or "general",
        industry_key=industry_key or "general",
        phone_number=getattr(persona, "phone_number", "") if persona else "",
        blog_content_length=getattr(persona, "blog_content_length", 1500) if persona else 1500,
        tones=["친근함", "전문성", "현장감"],
    )
    prompt = _format_prompt_for_worker(StoryMakerService.generate_prompt(req))
    logger.info("mobile one-shot prompt generated_prompt_len=%s", len(prompt))
    return prompt


def _mobile_progress_payload(data: dict[str, Any], job_id: str, user_id: int) -> dict[str, Any]:
    pipeline = data.get("pipeline") or {}
    media = data.get("media") or {}
    steps = data.get("steps") or []

    content_status = str(data.get("status") or pipeline.get("ai_worker_status") or "unknown").lower()
    podcast_status = str(media.get("podcast_status") or "").lower()
    shortform_status = str(media.get("shortform_status") or media.get("status") or "").lower()
    thumbnail_status = str(media.get("thumbnail_status") or "").lower()

    has_mp3 = bool(media.get("mp3_url") or media.get("mp3_path"))
    has_srt = bool(media.get("srt_url") or media.get("srt_path"))
    has_mp4 = bool(media.get("mp4_url") or media.get("mp4_path"))
    has_thumbnail = bool(media.get("thumbnail_url") or media.get("thumbnail_path"))

    # 콘텐츠 완료보다 실제 미디어 제작 단계를 우선합니다.
    if has_mp4 or shortform_status in {"shortform_completed", "completed", "done"}:
        current_phase = "completed"
        status = "completed"
        percent = 100
        stage = str(media.get("message") or "쇼츠 제작이 완료되었습니다.")
    elif shortform_status.startswith("shortform") or shortform_status in {"submitted", "running", "processing"} and has_mp3:
        current_phase = "shortform"
        status = "shortform_running"
        percent = int(media.get("shortform_percent") or 75)
        stage = str(media.get("message") or "쇼츠를 만들고 있습니다.")
    elif podcast_status in {"submitted", "queued", "running", "processing"} and not has_mp3:
        current_phase = "podcast"
        status = "podcast_running"
        percent = int(media.get("podcast_percent") or 55)
        stage = str(media.get("message") or "팟캐스트를 만들고 있습니다.")
    elif has_mp3 or podcast_status in {"completed", "done", "podcast_completed"}:
        current_phase = "shortform"
        status = "podcast_completed"
        percent = 70
        stage = str(media.get("message") or "팟캐스트가 완료되어 쇼츠를 준비하고 있습니다.")
    elif data.get("outputs"):
        current_phase = "podcast"
        status = "podcast_waiting"
        percent = 45
        stage = "콘텐츠가 준비되어 팟캐스트 시작을 기다리고 있습니다."
    elif content_status in {"gemini_worker_waiting", "worker_queued", "queued"}:
        current_phase = "content"
        status = content_status
        percent = 10
        stage = str(pipeline.get("stage") or "콘텐츠 생성을 기다리고 있습니다.")
    else:
        current_phase = "content"
        status = content_status
        percent = 0
        stage = str(data.get("stage") or pipeline.get("stage") or "작업 상태를 확인하고 있습니다.")

    done_steps = sum(
        1 for step in steps
        if str(step.get("status") or "").lower() == "done"
    ) if isinstance(steps, list) else 0
    if steps and current_phase == "content":
        percent = max(percent, min(40, int(done_steps / max(1, len(steps)) * 40)))

    queue_position = int(pipeline.get("queue_position") or data.get("queue_position") or 0)
    ahead_count = max(0, queue_position - 1) if queue_position else 0
    message = str(media.get("message") or pipeline.get("message") or stage)[:1000]

    return {
        "ok": True,
        "job_id": job_id,
        "user_id": user_id,
        "status": status,
        "content_status": content_status,
        "current_phase": current_phase,
        "stage": stage or message,
        "percent": max(0, min(percent, 100)),
        "queue_position": queue_position,
        "ahead_count": ahead_count,
        "message": message,
        "podcast_status": podcast_status,
        "shortform_status": shortform_status,
        "thumbnail_status": thumbnail_status,
        "has_mp3": has_mp3,
        "has_srt": has_srt,
        "has_mp4": has_mp4,
        "has_thumbnail": has_thumbnail,
        "media": media,
        "can_cancel": status in {"queued", "gemini_worker_waiting", "worker_queued", "podcast_waiting"},
        "updated_at": _now().isoformat(timespec="seconds"),
    }

def _queue_worker_job(job_id: str, project_title: str, prompt_text: str, job_dir: Path) -> dict[str, Any]:
    output_root = _output_root()
    snapshot_root = output_root / "test_prompt_snapshots"
    trigger_root = output_root / "test_triggers"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    trigger_root.mkdir(parents=True, exist_ok=True)
    prompt_path = job_dir / "prompt_for_chatgpt.md"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    latest_prompt_path = snapshot_root / "latest_prompt.md"
    latest_prompt_path.write_text(prompt_text, encoding="utf-8")
    now_text = _now().isoformat(timespec="seconds")
    meta = {
        "ok": True,
        "created_at": now_text,
        "project_title": project_title,
        "project_name": project_title,
        "prompt": prompt_text,
        "prompt_length": len(prompt_text),
        "prompt_for_chatgpt": str(prompt_path),
        "prompt_path": str(prompt_path),
        "latest_prompt_path": str(latest_prompt_path),
        "mobile_job_id": job_id,
        "source": "mobile_one_shot",
        "handoff": "mobile_to_firefox_gemini",
    }
    (snapshot_root / "latest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    trigger = {
        "ok": True,
        "status": "pending",
        "action": "GENERATE_GEMINI",
        "job_id": job_id,
        "worker_target": "firefox_gemini",
        "project_title": project_title,
        "project_name": project_title,
        "prompt_path": str(prompt_path),
        "latest_prompt_path": str(latest_prompt_path),
        "created_at": now_text,
        "claimed_at": None,
        "worker_id": None,
        "source": "mobile_one_shot",
        "handoff": "mobile_to_firefox_gemini",
    }
    (trigger_root / "trigger_status.json").write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"prompt_path": str(prompt_path), "trigger": trigger}


def _extract_block(blocks: dict[str, str], *names: str) -> str:
    for name in names:
        value = blocks.get(name)
        if value:
            return value.strip()
    return ""


def _looks_like_missing_local_media(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if text.startswith("/api/") or text.startswith("http://") or text.startswith("https://"):
        return True
    try:
        return not Path(text).exists()
    except Exception:
        return True


def _download_podcast_media_to_file(project_key: str, kind: str, target_path: Path) -> Optional[str]:
    if not project_key or kind not in {"mp3", "srt"}:
        return None
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        response = httpx.get(
            f"{WORKER_API_URL}/media/podcast/{quote(str(project_key), safe='')}/{kind}",
            headers=upstream_headers(),
            timeout=120,
        )
        response.raise_for_status()
        if not response.content:
            return None
        target_path.write_bytes(response.content)
        if target_path.exists() and target_path.stat().st_size > 0:
            return str(target_path)
    except Exception:
        return None
    return None


def _start_podcast_job(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    if not (data.get("raw_result") or data.get("outputs")):
        return data
    pipeline = data.get("pipeline") or {}
    outputs = data.get("outputs") or {}
    script = str(
        pipeline.get("podcast_script")
        or outputs.get("podcast50")
        or outputs.get("PODCAST_50")
        or outputs.get("podcast80")
        or outputs.get("PODCAST_80")
        or ""
    ).strip()
    if script and not pipeline.get("podcast_script"):
        pipeline["podcast_script"] = script
        pipeline["podcast_script_ready"] = True
        data["pipeline"] = pipeline
    media = data.setdefault("media", {})
    if bool(pipeline.get("browser_podcast")):
        if media.get("mp3_url") or media.get("mp3_path"):
            media.update({
                "status": "podcast_completed",
                "podcast_status": "completed",
                "message": "브라우저 MP3/SRT가 준비되어 서버 팟캐스트 생성을 건너뜁니다.",
            })
            _write_json_atomic(result_file, data)
        else:
            next_status = "browser_podcast_waiting" if script or data.get("outputs") else "waiting_gemini_result"
            if media.get("status") != next_status:
                media.update({
                    "status": next_status,
                    "podcast_status": "browser_waiting",
                    "message": "모바일 브라우저 WebGPU/WASM 음성 생성을 기다리고 있습니다.",
                })
                _write_json_atomic(result_file, data)
        return data
    outputs = data.get("outputs") or {}
    if not script:
        script = str(
            outputs.get("podcast50")
            or outputs.get("podcast80")
            or outputs.get("podcast_50")
            or outputs.get("podcast_80")
            or outputs.get("PODCAST_50")
            or outputs.get("PODCAST_80")
            or _extract_raw_result_block(data.get("raw_result"), "PODCAST_50")
            or _extract_raw_result_block(data.get("raw_result"), "PODCAST_80")
            or ""
        ).strip()
        if script:
            outputs["podcast50"] = script
            data["outputs"] = outputs
    script = normalize_podcast_speaker_tags(script, "M1", "F1")
    if len(script) > 1400:
        script = script[:1400].rsplit("\n", 1)[0].strip() or script[:1400].strip()
    if not script:
        media.update({
            "status": "podcast_script_missing",
            "podcast_status": "script_missing",
            "message": "PODCAST 블록이 아직 없어 팟캐스트 자동 시작을 대기합니다.",
        })
        _write_json_atomic(result_file, data)
        return data
    if media.get("podcast_job_id"):
        return data
    api_key = os.getenv("SUPERTONIC_API_KEY", "")
    if not api_key:
        media.update({
            "status": "podcast_waiting_api_key",
            "podcast_status": "waiting_api_key",
            "message": "팟캐스트 대본은 준비됐지만 TTS API 키 설정이 없어 자동 생성은 대기 중입니다.",
        })
        _write_json_atomic(result_file, data)
        return data
    api_url = WORKER_API_URL
    project_key = str(data.get("job_id") or "mobile_one_shot")
    timing = data.setdefault("pipeline", {}).setdefault("timing", {})
    timing["podcast_script_length"] = len(script)
    timing["podcast_submit_at"] = _now().isoformat(timespec="milliseconds")
    try:
        response = httpx.post(
            f"{api_url}/api/podcast/run",
            data={
                "project_key": project_key,
                "script": script,
                "male_voice": "__shuffle__",
                "female_voice": "__shuffle__",
                "speed": "1.35",
                "music_random": "true",
                "music_volume": "0.2",
                "voice_volume": "1.0",
                "tts_engine": "supertonic",
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        podcast_data = response.json()
        media.update({
            "status": "podcast_submitted",
            "podcast_status": "submitted",
            "podcast_job_id": podcast_data.get("job_id"),
            "project_key": project_key,
            "message": "AI 결과의 PODCAST 블록을 팟캐스트 생성 작업으로 넘겼습니다.",
        })
    except Exception as exc:
        media.update({
            "status": "podcast_submit_failed",
            "podcast_status": "submit_failed",
            "message": str(exc)[:500],
        })
    _write_json_atomic(result_file, data)
    if media.get("podcast_job_id") and str(media.get("podcast_status") or "").lower() == "submitted":
        _schedule_thumbnail_job_after_podcast_start(result_file, delay_seconds=1.0)
    return data


def _sync_podcast_result(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    media = data.setdefault("media", {})
    podcast_job_id = media.get("podcast_job_id")
    if not podcast_job_id or media.get("mp3_url"):
        return data
    api_url = WORKER_API_URL
    api_key = os.getenv("SUPERTONIC_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = httpx.get(f"{api_url}/api/jobs/{quote(str(podcast_job_id), safe='')}", headers=headers, timeout=3)
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") or payload.get("data") or payload
        mp3_url = result.get("mp3_url") or result.get("download_url") or result.get("audio_url") or result.get("file_url") or result.get("media_url") or result.get("url")
        srt_url = result.get("srt_url") or result.get("subtitle_url") or result.get("caption_url")
        latest_status = payload.get("status") or result.get("status") or payload.get("stage") or result.get("stage") or media.get("podcast_status") or "submitted"
        latest_message = payload.get("message") or result.get("message") or payload.get("stage") or result.get("stage") or "팟캐스트 MP3 생성 결과를 기다리고 있습니다."
        if mp3_url:
            project_key_for_media = result.get("project_key") or payload.get("project_key") or media.get("project_key") or data.get("job_id") or podcast_job_id
            encoded_project_key = quote(str(project_key_for_media), safe="")
            media["project_key"] = str(project_key_for_media)
            media["mp3_url"] = f"/api/podcast/media/{encoded_project_key}/mp3"
            media["srt_url"] = f"/api/podcast/media/{encoded_project_key}/srt" if srt_url or result.get("srt_path") or result.get("subtitle_path") else srt_url
            media["mp3_path"] = result.get("mp3_path") or result.get("audio_path") or result.get("path") or mp3_url
            media["srt_path"] = result.get("srt_path") or result.get("subtitle_path") or srt_url
            media["status"] = "podcast_completed"
            media["podcast_status"] = "completed"
            data.setdefault("pipeline", {}).setdefault("timing", {})["podcast_completed_at"] = _now().isoformat(timespec="milliseconds")
            media["message"] = "팟캐스트 MP3 결과를 연결했습니다."
            steps = data.setdefault("steps", [])
            for step in steps:
                if "팟캐스트" in str(step.get("label", "")):
                    step["status"] = "done"
                if "MP4" in str(step.get("label", "")) or "숏폼" in str(step.get("label", "")):
                    step["status"] = "active"
            _write_json_atomic(result_file, data)
        else:
            media["status"] = f"podcast_{latest_status}"
            media["podcast_status"] = str(latest_status)
            media["message"] = str(latest_message)[:300]
            _write_json_atomic(result_file, data)
    except Exception as exc:
        media["status"] = media.get("status") or "podcast_sync_waiting"
        media["podcast_status"] = media.get("podcast_status") or "sync_waiting"
        media["message"] = str(exc)[:300]
        _write_json_atomic(result_file, data)
    return data


def _start_shortform_job(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    media = data.setdefault("media", {})
    if media.get("slideshow_job_id"):
        return data
    if not (media.get("mp3_url") or media.get("mp3_path")):
        return data
    job_dir = result_file.parent
    image_dir = job_dir / "images"
    image_items = data.get("images") or []
    files = []
    handles = []
    safe_image_dir = job_dir / "safe_images_for_video"
    real_image_items = [item for item in image_items[:12] if "default_shortform_image" not in str(item.get("stored_name") or "")]
    upload_image_items = real_image_items or image_items[:12]
    try:
        for idx, item in enumerate(upload_image_items, start=1):
            stored_name = str(item.get("stored_name") or "")
            if not stored_name:
                continue
            image_path = image_dir / stored_name
            if not image_path.exists():
                continue
            video_image_path = _prepare_video_safe_image(image_path, safe_image_dir, idx)
            if video_image_path == image_path:
                continue
            handle = video_image_path.open("rb")
            handles.append(handle)
            files.append(("images", (video_image_path.name, handle, "image/jpeg")))
        if not files:
            media.update({"status": "shortform_waiting_images", "message": "숏폼에 사용할 이미지를 찾는 중입니다."})
            return data
        persona = data.get("persona") or {}
        podcast_project_key = str(media.get("project_key") or data.get("job_id") or "")
        if _looks_like_missing_local_media(media.get("mp3_path")):
            local_mp3_path = _download_podcast_media_to_file(podcast_project_key, "mp3", job_dir / "podcast_audio.mp3")
            if local_mp3_path:
                media["mp3_path"] = local_mp3_path
        if media.get("srt_url") and _looks_like_missing_local_media(media.get("srt_path")):
            local_srt_path = _download_podcast_media_to_file(podcast_project_key, "srt", job_dir / "podcast_subtitle.srt")
            if local_srt_path:
                media["srt_path"] = local_srt_path
        payload = {
            "project_key": str(data.get("job_id") or "mobile_one_shot"),
            "mp3_path": str(media.get("mp3_path") or media.get("mp3_url") or ""),
            "srt_path": str(media.get("srt_path") or media.get("srt_url") or ""),
            "brand_name": str(persona.get("company_name") or ""),
            "phone_number": str(persona.get("phone_number") or ""),
            "brand_size": "46",
            "phone_size": "43",
            "margin_bottom": "80",
            "box_enabled": "true",
            "stroke_enabled": "true",
            "shadow_enabled": "true",
            "image_sec": "5.5",
            "transition_sec": "0.7",
            "zoom_intensity": "0",
            "zoom_center_only": "false",
            "subtitle_enabled": "true",
            "subtitle_font_size": "10",
            "subtitle_margin": "40",
            "mm_sub_lift": "95",
            "resolution": "720x1280",
            "fps": "18",
            "nvenc_preset": "p2",
            "render_target": "macmini",
        }
        response = httpx.post(f"{WORKER_API_URL}/api/slideshow/run", data=payload, files=files, headers=upstream_headers(), timeout=30)
        response.raise_for_status()
        started = response.json()
        media.update({
            "status": "shortform_submitted",
            "slideshow_job_id": started.get("job_id"),
            "message": "MP3/SRT를 숏폼 영상 생성 단계로 넘겼습니다.",
        })
        data["steps"] = [
            {"label": "1단계 글 만들기", "status": "done"},
            {"label": "2단계 팟캐스트 만들기", "status": "done"},
            {"label": "3단계 숏폼 영상 만들기", "status": "active"},
        ]
        _write_json_atomic(result_file, data)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        media.update({
            "status": "shortform_submit_failed",
            "shortform_status": "submit_failed",
            "shortform_error": detail[:1000],
            "message": detail[:500],
        })
        data.setdefault("pipeline", {}).setdefault("errors", []).append({
            "stage": "shortform_submit",
            "message": detail[:1000],
            "at": _now().isoformat(timespec="milliseconds"),
        })
        _write_json_atomic(result_file, data)
    finally:
        for handle in handles:
            try:
                handle.close()
            except Exception:
                pass
    return data


def _materialize_mobile_media_file(
    value: Any,
    job_dir: Path,
    target_stem: str,
    external_roots: Optional[list[Path]] = None,
) -> Optional[Path]:
    """외부 생성 결과를 게시물 전용 media 폴더로 안전하게 복사합니다."""
    if not value:
        return None

    source = _resolve_mobile_download_file(value, job_dir)
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    path_value = unquote(parsed.path or raw.split("?", 1)[0])
    filename = Path(path_value).name

    if source is None and filename:
        for root_value in external_roots or []:
            try:
                root = root_value.expanduser().resolve()
                candidate = (root / filename).resolve()
            except Exception:
                continue
            if candidate.parent != root:
                continue
            if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
                source = candidate
                break

    if source is None or not source.exists() or not source.is_file() or source.stat().st_size <= 0:
        return None

    media_dir = job_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or Path(filename).suffix.lower() or ".bin"
    target = media_dir / f"{target_stem}{suffix}"

    try:
        if source.resolve() == target.resolve():
            return target
    except Exception:
        pass

    if not target.exists() or target.stat().st_size != source.stat().st_size:
        temp_target = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            shutil.copy2(source, temp_target)
            os.replace(temp_target, target)
        finally:
            if temp_target.exists():
                temp_target.unlink(missing_ok=True)
    return target if target.exists() and target.stat().st_size > 0 else None


def _shortform_external_roots() -> list[Path]:
    return [
        Path(os.getenv("STORYMAKER_SLIDESHOW_DIR", "/home/bourne/StoryMaker_1/supertonic/SlidShow")),
        Path("/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/media/slideshow"),
    ]


def _fetch_slideshow_media_to_job(value: Any, job_dir: Path) -> Optional[Path]:
    """슬라이드쇼 서비스의 MP4를 게시물 전용 폴더로 안전하게 가져옵니다."""
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    filename = Path(unquote(parsed.path or raw.split("?", 1)[0])).name
    if not filename or not filename.lower().endswith(".mp4"):
        return None

    media_dir = job_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    target = media_dir / "shortform.mp4"
    if target.exists() and target.is_file() and target.stat().st_size > 0:
        return target

    temp_target = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        remote_url = f"{WORKER_API_URL}/media/slideshow/{quote(filename, safe='')}"
        with httpx.stream(
            "GET",
            remote_url,
            headers=upstream_headers(),
            timeout=180,
            follow_redirects=True,
        ) as response:
            response.raise_for_status()
            with temp_target.open("wb") as output:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
        if not temp_target.exists() or temp_target.stat().st_size <= 0:
            return None
        os.replace(temp_target, target)
        return target
    except Exception:
        return None
    finally:
        if temp_target.exists():
            temp_target.unlink(missing_ok=True)


def _sync_shortform_result(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    media = data.setdefault("media", {})
    job_dir = result_file.parent
    source_job_id = str(data.get("source_job_id") or data.get("archive_group_key") or "").strip()
    mp4_source_job_id = str(media.get("mp4_source_job_id") or "").strip()
    if media.get("mp4_path") or media.get("mp4_url") or media.get("video_path") or media.get("video_url"):
        if not source_job_id or mp4_source_job_id != source_job_id:
            for key in ("mp4_path", "video_path", "mp4_url", "preview_mp4_url", "video_url", "download_url"):
                media.pop(key, None)
            stale_local = job_dir / "media" / "shortform.mp4"
            if stale_local.exists():
                stale_local.unlink(missing_ok=True)
            media["shortform_status"] = "waiting_current_job_mp4"
            media["message"] = "Current job MP4 is not ready. Previous MP4 reuse was blocked."
            _write_json_atomic(result_file, data)
    current_mp4 = (
        media.get("mp4_path")
        or media.get("video_path")
        or media.get("mp4_url")
        or media.get("preview_mp4_url")
        or media.get("video_url")
    )
    local_mp4 = _materialize_mobile_media_file(
        current_mp4,
        job_dir,
        "shortform",
        _shortform_external_roots(),
    ) or _fetch_slideshow_media_to_job(current_mp4, job_dir)
    if local_mp4:
        local_url = _job_url_path(job_dir, local_mp4)
        changed = (
            media.get("mp4_path") != str(local_mp4)
            or media.get("mp4_url") != local_url
            or media.get("preview_mp4_url") != local_url
        )
        media["mp4_path"] = str(local_mp4)
        media["mp4_url"] = local_url
        media["preview_mp4_url"] = local_url
        media["status"] = "shortform_completed"
        if changed:
            _write_json_atomic(result_file, data)
        return data

    slideshow_job_id = media.get("slideshow_job_id")
    if not slideshow_job_id:
        return data
    try:
        response = httpx.get(f"{WORKER_API_URL}/api/jobs/{slideshow_job_id}", headers=upstream_headers(), timeout=3)
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") or payload.get("data") or payload
        status = payload.get("status") or result.get("status") or "shortform_running"
        mp4_raw = result.get("mp4_url") or result.get("download_url") or result.get("video_url") or result.get("file_url")
        preview_raw = result.get("preview_mp4_url") or result.get("preview_url") or mp4_raw
        if mp4_raw:
            filename = str(mp4_raw).rsplit("?", 1)[0].rstrip("/").split("/")[-1]
            media["mp4_url"] = f"/api/slideshow/media/{filename}"
            media["preview_mp4_url"] = f"/api/slideshow/media/{filename}?preview=true"
            media["mp4_path"] = result.get("mp4_path") or result.get("video_path") or result.get("path") or mp4_raw
            local_mp4 = _materialize_mobile_media_file(
                media.get("mp4_path") or media.get("mp4_url"),
                result_file.parent,
                "shortform",
                _shortform_external_roots(),
            ) or _fetch_slideshow_media_to_job(
                media.get("mp4_path") or media.get("mp4_url"),
                result_file.parent,
            )
            if local_mp4:
                local_url = _job_url_path(result_file.parent, local_mp4)
                media["mp4_path"] = str(local_mp4)
                media["mp4_url"] = local_url
                media["preview_mp4_url"] = local_url
            media["status"] = "shortform_completed"
            media["message"] = "숏폼 MP4 결과를 연결했습니다."
            data["steps"] = [
                {"label": "1단계 글 만들기", "status": "done"},
                {"label": "2단계 팟캐스트 만들기", "status": "done"},
                {"label": "3단계 숏폼 영상 만들기", "status": "done"},
                {"label": "썸네일 연결", "status": "active"},
            ]
            _write_json_atomic(result_file, data)
        else:
            media["status"] = status
            media["message"] = str(payload.get("stage") or payload.get("message") or "숏폼 영상을 생성하고 있습니다.")[:300]
    except Exception as exc:
        media["status"] = media.get("status") or "shortform_sync_waiting"
        media["message"] = str(exc)[:300]
    return data


def _start_thumbnail_job(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    media = data.setdefault("media", {})
    pipeline = data.setdefault("pipeline", {})
    timing = pipeline.setdefault("timing", {})
    if media.get("thumbnail_url"):
        return data
    if media.get("thumbnail_job_id"):
        return data
    podcast_started = bool(
        media.get("podcast_job_id")
        or media.get("mp3_url")
        or media.get("mp3_path")
        or timing.get("podcast_submit_at")
    )
    if not podcast_started:
        media["thumbnail_status"] = "thumbnail_waiting_podcast"
        media["message"] = "Thumbnail waits until podcast generation starts."
        return data
    if not (media.get("mp3_url") or media.get("mp3_path")):
        submit_at = str(timing.get("podcast_submit_at") or "").strip()
        if submit_at:
            try:
                submitted_at = datetime.fromisoformat(submit_at).replace(tzinfo=None)
                if (_now() - submitted_at).total_seconds() < 1.0:
                    media["thumbnail_status"] = "thumbnail_scheduled"
                    media["message"] = "Thumbnail will start after podcast generation begins."
                    return data
            except Exception:
                pass
    thumbnail_status = str(media.get("thumbnail_status") or "").lower()
    if media.get("thumbnail_job_id") and "fail" not in thumbnail_status and "error" not in thumbnail_status:
        return data
    if media.get("thumbnail_job_id") and ("fail" in thumbnail_status or "error" in thumbnail_status):
        media.pop("thumbnail_job_id", None)

    outputs = data.get("outputs") or {}
    instagram_text = str(outputs.get("instagram") or data.get("raw_result") or "").strip()
    image_items = data.get("images") or []
    if not instagram_text:
        media["thumbnail_status"] = "thumbnail_waiting_text"
        return data
    if not image_items:
        media["thumbnail_status"] = "thumbnail_waiting_images"
        return data

    root = _output_root()
    now = _now()
    job_id = "thumbnail_" + now.strftime("%Y%m%d_%H%M%S") + "_mobile"
    job_dir = root / "test_thumbnail_jobs" / job_id
    input_dir = job_dir / "input_images"
    input_dir.mkdir(parents=True, exist_ok=True)
    source_dir = result_file.parent / "images"
    copied_urls: list[str] = []
    copied_image_paths: list[Path] = []
    for item in (data.get("images") or [])[:3]:
        stored_name = str(item.get("stored_name") or "")
        if not stored_name:
            continue
        src = source_dir / stored_name
        if not src.exists():
            continue
        dst = input_dir / src.name
        dst.write_bytes(src.read_bytes())
        copied_image_paths.append(dst)
        copied_urls.append(f"/data/output_results/test_thumbnail_jobs/{job_id}/input_images/{dst.name}")
    if not copied_urls:
        media.update({"thumbnail_status": "thumbnail_waiting", "message": "썸네일에 사용할 이미지를 찾는 중입니다."})
        return data

    reference_urls = copied_urls[:3]
    instagram_text = instagram_text[:3000]
    persona = data.get("persona") or {}
    project_title = str(persona.get("company_name") or data.get("job_id") or "모바일 원샷 썸네일")
    image_lines = "\n".join(f"- 참고 이미지 {index + 1}: {url}" for index, url in enumerate(reference_urls))
    prompt = f"""[썸네일 제작 요청]

첨부된 이미지들을 참고해서 인스타그램용 9:16 세로형 썸네일 이미지를 만들어줘.

[업체 정보]
상호명: {project_title}
전화번호: {persona.get('phone_number') or ''}
키워드: {', '.join(data.get('keywords') or [])}

[인스타그램 게시글 참고 문안]
{instagram_text}

[디자인 지시]
- 첫 인스타그램 문안의 핵심 메시지를 반영해줘.
- 상호, 키워드, 전화번호가 모바일에서 잘 보이게 구성해줘.
- 현장 사진의 실제 분위기를 살려줘.
- 과장된 광고 느낌보다 지역 소상공인 현장감이 느껴지게 만들어줘.
- 글자는 너무 많이 넣지 말고 핵심 문구 중심으로 배치해줘.

[참고 이미지]
{image_lines}

- 위 참고 이미지 3장을 각각 확인하고 현장 구도와 분위기를 반영해 주세요.
- 사진을 단순히 한 장으로 합치지 말고, 가장 적합한 구도와 요소를 선택해 최종 9:16 썸네일을 제작해 주세요.
""".strip()
    prompt_path = job_dir / "thumbnail_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    snapshot_dir = root / "test_prompt_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    latest_prompt_path = snapshot_dir / "latest_thumbnail_prompt.md"
    latest_prompt_path.write_text(prompt, encoding="utf-8")
    worker_latest_prompt_path = snapshot_dir / "latest_prompt.md"
    worker_latest_prompt_path.write_text(prompt, encoding="utf-8")
    worker_latest_meta_path = snapshot_dir / "latest.json"
    worker_latest_meta_path.write_text(json.dumps({
        "ok": True,
        "created_at": now.isoformat(timespec="seconds"),
        "project_title": project_title,
        "prompt_for_chatgpt": str(worker_latest_prompt_path),
        "latest_prompt_path": str(worker_latest_prompt_path),
        "payload": {"source": "mobile_one_shot_thumbnail", "action": "GENERATE_GEMINI_THUMBNAIL", "job_id": job_id},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    trigger_dir = root / "test_triggers"
    trigger_dir.mkdir(parents=True, exist_ok=True)
    trigger = {
        "ok": True,
        "status": "pending",
        "action": "GENERATE_GEMINI_THUMBNAIL",
        "job_id": job_id,
        "source_job_id": str(data.get("job_id") or ""),
        "project_title": project_title,
        "prompt_path": str(prompt_path),
        "latest_prompt_path": str(worker_latest_prompt_path),
        "source": "mobile_one_shot",
        "handoff": "mobile_shortform_to_firefox_thumbnail",
        "created_at": now.isoformat(timespec="seconds"),
        "image_urls": reference_urls,
    }
    (trigger_dir / "trigger_status.json").write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
    media.update({
        "thumbnail_status": "thumbnail_requested",
        "thumbnail_job_id": job_id,
        "thumbnail_reference_urls": reference_urls,
        "message": "숏폼 썸네일 작업을 Firefox AI Worker로 넘겼습니다.",
    })
    data["steps"] = [
        {"label": "1단계 글 만들기", "status": "done"},
        {"label": "썸네일 선처리", "status": "active"},
        {"label": "2단계 팟캐스트 만들기", "status": "active"},
        {"label": "3단계 숏폼 영상 만들기", "status": "waiting"},
    ]
    _write_json_atomic(result_file, data)
    return data


def _schedule_thumbnail_job_after_podcast_start(result_file: Path, delay_seconds: float = 1.0) -> None:
    timer_key = str(result_file.resolve())
    with _THUMBNAIL_TIMER_LOCK:
        if timer_key in _THUMBNAIL_TIMER_KEYS:
            return
        _THUMBNAIL_TIMER_KEYS.add(timer_key)

    def run() -> None:
        try:
            if not result_file.exists():
                return
            data = json.loads(result_file.read_text(encoding="utf-8"))
            media = data.setdefault("media", {})
            if media.get("thumbnail_url") or media.get("thumbnail_job_id"):
                return
            _start_thumbnail_job(data, result_file)
        except Exception as exc:
            logger.warning("thumbnail parallel start failed for %s: %s", result_file, exc)
        finally:
            with _THUMBNAIL_TIMER_LOCK:
                _THUMBNAIL_TIMER_KEYS.discard(timer_key)

    timer = threading.Timer(max(1.05, float(delay_seconds)), run)
    timer.daemon = True
    timer.start()


def _sync_thumbnail_result(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    media = data.setdefault("media", {})
    job_dir = result_file.parent
    current_thumbnail = media.get("thumbnail_path") or media.get("thumbnail_url")
    local_thumbnail = _materialize_mobile_media_file(
        current_thumbnail,
        job_dir,
        "thumbnail",
    )
    if local_thumbnail:
        local_url = _job_url_path(job_dir, local_thumbnail)
        changed = (
            media.get("thumbnail_path") != str(local_thumbnail)
            or media.get("thumbnail_url") != local_url
        )
        media["thumbnail_path"] = str(local_thumbnail)
        media["thumbnail_url"] = local_url
        media["thumbnail_status"] = "thumbnail_done"
        if changed:
            _write_json_atomic(result_file, data)
        return data

    thumbnail_job_id = media.get("thumbnail_job_id")
    if not thumbnail_job_id:
        return data

    def pick_url(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            for item in value:
                found = pick_url(item)
                if found:
                    return found
        if isinstance(value, dict):
            for key in ["image_url", "thumbnail_url", "url", "file_url", "download_url"]:
                found = pick_url(value.get(key))
                if found:
                    return found
            for key in ["image_urls", "images", "files", "assets", "data", "result"]:
                found = pick_url(value.get(key))
                if found:
                    return found
        return ""

    result_path = _output_root() / "test_result_packages" / str(thumbnail_job_id) / "reels_thumbnail_url.json"
    latest_path = _output_root() / "test_result_packages" / "latest_thumbnail.json"
    candidates = [path for path in [result_path, latest_path] if path.exists()]
    if not candidates:
        return data

    last_error = ""
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            payload_job_id = str(payload.get("job_id") or payload.get("thumbnail_job_id") or "")
            if candidate == latest_path and payload_job_id != str(thumbnail_job_id):
                continue

            thumbnail_url = pick_url(payload)
            if thumbnail_url:
                media["thumbnail_url"] = thumbnail_url
                local_thumbnail = _materialize_mobile_media_file(
                    thumbnail_url,
                    result_file.parent,
                    "thumbnail",
                )
                if local_thumbnail:
                    media["thumbnail_path"] = str(local_thumbnail)
                    media["thumbnail_url"] = _job_url_path(result_file.parent, local_thumbnail)
                media["thumbnail_status"] = "thumbnail_done"
                media["thumbnail_version"] = str(thumbnail_job_id)
                media["thumbnail_done_at"] = _now().isoformat(timespec="seconds")
                media.pop("thumbnail_error", None)
                data["steps"] = [
                    {"label": "1단계 글 만들기", "status": "done"},
                    {"label": "2단계 팟캐스트 만들기", "status": "done"},
                    {"label": "3단계 숏폼 영상 만들기", "status": "done"},
                    {"label": "4단계 썸네일 만들기", "status": "done"},
                ]
                _write_json_atomic(result_file, data)
                return data

            status_text = str(payload.get("status") or payload.get("message") or "").lower()
            if "fail" in status_text or "error" in status_text:
                media["thumbnail_status"] = "thumbnail_failed"
                media["thumbnail_error"] = str(payload.get("message") or payload.get("error") or status_text)[:300]
                _write_json_atomic(result_file, data)
                return data
        except Exception as exc:
            last_error = str(exc)[:300]

    if last_error:
        media["thumbnail_status"] = "thumbnail_failed"
        media["thumbnail_error"] = last_error
        _write_json_atomic(result_file, data)
    return data


def _sync_storymaker_main_images(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    # Do not trust result.json metadata alone. Older archive rows can contain an
    # images list while the actual mob-*/images directory is still empty.
    target_dir = result_file.parent / "images"
    if target_dir.exists() and any(path.is_file() and path.stat().st_size > 0 for path in target_dir.iterdir()):
        return data

    pipeline = data.get("pipeline") or {}
    source_job_id = str(
        data.get("source_job_id")
        or data.get("archive_group_key")
        or pipeline.get("source_job_id")
        or pipeline.get("archive_group_key")
        or ""
    ).strip()
    if not re.fullmatch(r"storymaker_main_[0-9]{14}", source_job_id):
        return data

    source_root = _output_root() / "storymaker_main_uploads" / source_job_id
    manifest_path = source_root / "manifest.json"
    source_image_dir = source_root / "images"
    if not manifest_path.exists() or not source_image_dir.exists():
        return data

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return data
    if str(manifest.get("user_bucket") or "") != str(data.get("user_bucket") or ""):
        return data

    target_dir = result_file.parent / "images"
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_images: list[dict[str, Any]] = []
    for index, item in enumerate(list(manifest.get("images") or [])[:MAX_IMAGES], start=1):
        stored_name = Path(str(item.get("stored_name") or "")).name
        if not stored_name:
            continue
        source = source_image_dir / stored_name
        if not source.exists() or not source.is_file() or source.stat().st_size <= 0:
            continue
        target = target_dir / stored_name
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
        saved_images.append({
            "name": str(item.get("name") or stored_name),
            "stored_name": stored_name,
            "size": target.stat().st_size,
            "url": _job_url_path(result_file.parent, target),
        })

    if not saved_images:
        return data
    data["images"] = saved_images
    data["image_count"] = len(saved_images)
    data.setdefault("pipeline", {})["source_job_id"] = source_job_id
    _write_json_atomic(result_file, data)
    return data


def _sync_worker_result(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    data = _sync_storymaker_main_images(data, result_file)
    job_id = str(data.get("job_id") or "")
    package_path = _output_root() / "test_result_packages" / job_id / "result_package.json"
    if not package_path.exists():
        return data
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
        result_text = package.get("result_text") or ""
        if not result_text.strip():
            return data
        parsed = StoryMakerService.parse_result(ResultParseRequest(raw_result=result_text))
        blocks = parsed.get("blocks", {}) or {}
        podcast_script = _extract_block(blocks, "PODCAST_50", "PODCAST_80")
        data["status"] = "gemini_completed"
        data["raw_result"] = result_text
        blog_titles = _extract_block(blocks, "BLOG_TITLES")
        blog_post = _extract_block(blocks, "BLOG_POST")
        blog_hashtags = _extract_block(blocks, "BLOG_HASHTAGS")
        blog_preview = "\n\n".join(part for part in [blog_titles, blog_post, blog_hashtags] if str(part or "").strip()).strip()
        data["outputs"] = {
            "blog": blog_preview or blog_post,
            "blog_titles": blog_titles,
            "blog_post": blog_post,
            "blog_hashtags": blog_hashtags,
            "instagram": _extract_block(blocks, "INSTAGRAM_POST"),
            "place": _extract_block(blocks, "NAVER_PLACE_NEWS"),
            "google_business": _extract_block(blocks, "GOOGLE_BUSINESS_POST"),
            "carrot": _extract_block(blocks, "CARROT_POST", "DAANGN_POST"),
            "podcast50": _extract_block(blocks, "PODCAST_50"),
            "podcast80": _extract_block(blocks, "PODCAST_80"),
        }
        existing_pipeline = data.get("pipeline") or {}
        timing = dict(existing_pipeline.get("timing") or {})
        timing["worker_result_synced_at"] = _now().isoformat(timespec="milliseconds")
        data["pipeline"] = {
            **existing_pipeline,
            "ai_worker_status": "completed",
            "timing": timing,
            "result_package_path": str(package_path),
            "blocks": list(blocks.keys()),
            "podcast_script_ready": bool(podcast_script),
            "podcast_script": podcast_script,
        }
        existing_media = data.get("media") if isinstance(data.get("media"), dict) else {}
        podcast_completed = bool(
            existing_media.get("mp3_path")
            or existing_media.get("mp3_url")
            or str(existing_media.get("podcast_status") or "").strip().lower() in {"completed", "done", "podcast_completed"}
            or str(existing_media.get("status") or "").strip().lower() == "podcast_completed"
        )
        if not podcast_completed:
            data["media"] = {
                **existing_media,
                "status": "podcast_script_ready" if podcast_script else "podcast_script_missing",
                "message": "AI 결과를 파싱했습니다. PODCAST 블록을 팟캐스트 생성 단계로 넘길 준비가 되었습니다." if podcast_script else "AI 결과에서 PODCAST_50 또는 PODCAST_80 블록을 찾지 못했습니다.",
            }
            data["steps"] = [
                {"label": "업체 정보 적용", "status": "done" if data.get("persona") else "waiting"},
                {"label": "프롬프트 생성기 통과", "status": "done"},
                {"label": "Gemini Worker 생성 완료", "status": "done"},
                {"label": "결과 블록 파싱", "status": "done"},
                {"label": "팟캐스트 생성", "status": "active" if podcast_script else "waiting"},
                {"label": "MP4 워커 연결", "status": "waiting"},
            ]
        else:
            data["media"] = existing_media
            data["status"] = "podcast_completed"
            normalized_steps = []
            for step in data.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                normalized_step = dict(step)
                if normalized_step.get("label") == "팟캐스트 생성":
                    normalized_step["status"] = "done"
                elif normalized_step.get("label") == "MP4 워커 연결" and normalized_step.get("status") == "waiting":
                    normalized_step["status"] = "active"
                normalized_steps.append(normalized_step)
            if normalized_steps:
                data["steps"] = normalized_steps
        _write_json_atomic(result_file, data)
        data = data
    except Exception as exc:
        data["status"] = "worker_result_sync_failed"
        data.setdefault("pipeline", {})["sync_error"] = str(exc)
    return data


def _build_preview_text(memo: str, keywords: list[str], persona: Optional[Any] = None) -> dict[str, str]:
    clean_memo = " ".join(memo.strip().split())
    company_name = getattr(persona, "company_name", None) or "우리 업체"
    industry_key = getattr(persona, "industry_key", None) or "업종"
    keyword_line = ", ".join(keywords[:5]) if keywords else "현장 메모"
    return {
        "blog": f"{company_name} {keyword_line}\n\n{clean_memo[:120]}",
        "instagram": f"{company_name} 오늘의 핵심은 {keyword_line}!",
        "place": f"{company_name} {industry_key} 안내 콘텐츠입니다.",
    }


class MobileOneShotJobResponse(BaseModel):
    ok: bool
    job_id: str
    status: str
    message: str
    data: dict[str, Any]


class StagedSessionSaveRequest(BaseModel):
    project_title: str = ""
    work_memo: str = ""
    keyword_input: str = ""
    persona_id: Optional[int] = None
    current_step: int = 1
    stage_status: str = "draft"


class StagedDraftSaveRequest(BaseModel):
    content_key: str = "blog"
    content_text: str = ""
    draft_text: str = ""  # 이전 프런트 요청 호환



def _start_mobile_one_shot_post_handoff(result_file: Path) -> None:
    try:
        worker = threading.Thread(target=_prepare_mobile_one_shot_post_handoff, args=(result_file,), daemon=True)
        worker.start()
    except Exception:
        return


def _prepare_mobile_one_shot_post_handoff(result_file: Path) -> None:
    """Gemini Worker 전송 뒤, 결과 대기 시간에 가능한 이미지 후처리를 먼저 준비합니다."""
    try:
        data = json.loads(result_file.read_text(encoding="utf-8"))
        job_id = str(data.get("job_id") or "")
        if not job_id:
            return
        job_dir = result_file.parent
        image_items = data.get("images") or []
        timing = data.setdefault("pipeline", {}).setdefault("timing", {})
        timing["image_postprocess_start_at"] = _now().isoformat(timespec="milliseconds")
        prepared_dir = job_dir / "prepared"
        prepared_dir.mkdir(parents=True, exist_ok=True)
        (prepared_dir / "image_manifest.json").write_text(json.dumps(image_items, ensure_ascii=False, indent=2), encoding="utf-8")

        input_dir = _output_root() / "test_thumbnail_jobs" / job_id / "input_images"
        input_dir.mkdir(parents=True, exist_ok=True)
        source_dir = job_dir / "images"
        copied_paths: list[Path] = []
        for item in image_items[:3]:
            stored_name = str(item.get("stored_name") or "")
            if not stored_name:
                continue
            source_path = source_dir / stored_name
            if not source_path.exists() or not source_path.is_file():
                continue
            target_path = input_dir / stored_name
            if not target_path.exists():
                target_path.write_bytes(source_path.read_bytes())
            copied_paths.append(target_path)
        if copied_paths:
            collage_path = input_dir / "collage_reference.jpg"
            if not collage_path.exists() or collage_path.stat().st_size <= 0:
                _make_mobile_thumbnail_collage(copied_paths, collage_path)
            if collage_path.exists() and collage_path.stat().st_size > 0:
                data.setdefault("media", {})["thumbnail_prepared_collage_url"] = f"/data/output_results/test_thumbnail_jobs/{job_id}/input_images/{collage_path.name}"
        timing["image_postprocess_ready_at"] = _now().isoformat(timespec="milliseconds")
        data.setdefault("pipeline", {})["image_postprocess_status"] = "prepared_during_gemini_wait"
        _write_json_atomic(result_file, data)
    except Exception as exc:
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            data.setdefault("pipeline", {})["image_postprocess_status"] = "prepare_failed"
            data.setdefault("pipeline", {})["image_postprocess_error"] = str(exc)[:300]
            _write_json_atomic(result_file, data)
        except Exception:
            return


@router.post("/jobs", response_model=MobileOneShotJobResponse)
async def create_mobile_one_shot_job(
    memo: str = Form(...),
    persona_id: Optional[int] = Form(default=None),
    browser_podcast: bool = Form(default=False),
    images: list[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memo_text = memo.strip()
    if len(memo_text) < MIN_MEMO_LENGTH:
        raise HTTPException(status_code=400, detail="메모는 최소 10자 이상 입력해 주세요.")
    if len(images) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail="사진은 최대 12장까지 업로드할 수 있습니다.")

    created_at = _now()
    timing = {"job_created_at": created_at.isoformat(timespec="milliseconds")}
    job_id = f"mob-{created_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    job_dir = _job_dir(job_id, created_at.strftime(KST_DATE_FORMAT))
    image_dir = job_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    saved_images: list[dict[str, Any]] = []
    for index, upload in enumerate(images, start=1):
        original_name = upload.filename or f"image_{index}.jpg"
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            continue
        safe_name = _safe_filename(original_name, f"image_{index}{suffix or '.jpg'}")
        target = image_dir / f"{index:02d}_{safe_name}"
        content = await upload.read()
        if not content:
            continue
        target.write_bytes(content)
        saved_images.append({
            "name": original_name,
            "stored_name": target.name,
            "size": len(content),
            "url": _job_url_path(job_dir, target),
        })

    if not saved_images:
        default_target = image_dir / "00_default_shortform_image.jpg"
        _make_mobile_fallback_image(default_target)
        saved_images.append({
            "name": "default_shortform_image.jpg",
            "stored_name": default_target.name,
            "size": default_target.stat().st_size if default_target.exists() else 0,
            "url": _job_url_path(job_dir, default_target),
            "default_image": True,
        })

    selected_persona: Optional[UserPersona] = None
    selected_persona_payload = None
    if current_user and persona_id:
        persona = db.query(UserPersona).filter(UserPersona.id == persona_id, UserPersona.user_id == current_user.id).first()
        if persona:
            selected_persona = persona
            selected_persona_payload = {
                "id": persona.id,
                "company_name": persona.company_name,
                "industry_key": persona.industry_key,
                "region": getattr(persona, "region", None),
                "phone_number": persona.phone_number,
                "website_url": persona.website_url,
                "blog_content_length": getattr(persona, "blog_content_length", 1500),
                "is_default": persona.is_default,
            }

    keywords = list(dict.fromkeys(_persona_keywords(selected_persona) + _extract_keywords(memo_text)))[:12]
    timing["prompt_start_at"] = _now().isoformat(timespec="milliseconds")
    prompt_text = _build_worker_prompt(selected_persona, memo_text, keywords, saved_images)
    timing["prompt_ready_at"] = _now().isoformat(timespec="milliseconds")
    timing["prompt_length"] = len(prompt_text)
    project_title = f"{(selected_persona.company_name if selected_persona else '모바일 원샷')} {created_at.strftime('%m/%d %H:%M')}"
    worker_meta = _queue_worker_job(job_id, project_title, prompt_text, job_dir)
    timing["worker_handoff_at"] = _now().isoformat(timespec="milliseconds")
    user_bucket = str(current_user.id)
    result = {
        "job_id": job_id,
        "status": "gemini_worker_waiting",
        "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "user_bucket": user_bucket,
        "memo_length": len(memo_text),
        "persona": selected_persona_payload,
        "keywords": keywords,
        "image_count": len(saved_images),
        "images": saved_images,
        "outputs": {},
        "pipeline": {
            "prompt_status": "built",
            "browser_podcast": bool(browser_podcast),
            "prompt_length": len(prompt_text),
            "prompt_preview": prompt_text[:500],
            "ai_worker_status": "queued",
            "timing": timing,
            "prompt_path": worker_meta.get("prompt_path"),
            "trigger": worker_meta.get("trigger"),
        },
        "media": {
            "mp3_url": None,
            "mp4_url": None,
            "status": "waiting_gemini_result",
            "message": "프롬프트 생성기를 거쳐 Gemini Worker 대기열에 등록되었습니다. Gemini 결과가 도착하면 팟캐스트 단계로 이어갑니다.",
        },
        "steps": [
            {"label": "업체 정보 적용", "status": "done" if selected_persona else "waiting"},
            {"label": "메모·이미지 수신", "status": "done"},
            {"label": "프롬프트 생성기 통과", "status": "done"},
            {"label": "Gemini Worker 대기열 등록", "status": "done"},
            {"label": "Gemini 결과 대기", "status": "active"},
            {"label": "팟캐스트 생성", "status": "waiting"},
            {"label": "MP4 워커 연결", "status": "waiting"},
        ],
    }

    result_file = job_dir / "result.json"
    _write_json_atomic(result_file, result)
    try:
        upsert_mobile_one_shot_job(
            job_id=job_id,
            user_id=current_user.id,
            persona_id=selected_persona.id if selected_persona else None,
            status=result["status"],
            memo=memo_text[:2000],
            created_date=created_at.strftime(KST_DATE_FORMAT),
            result_path=str(result_file),
            image_count=len(saved_images),
            created_at=result["created_at"],
            updated_at=_now().isoformat(timespec="seconds"),
        )
    except Exception:
        pass
    try:
        update_mobile_one_shot_progress(
            job_id=job_id,
            user_id=current_user.id,
            status=result["status"],
            stage="Gemini Worker 대기열에 등록되었습니다.",
            percent=10,
            queue_position=0,
            ahead_count=0,
            worker_status="queued",
            progress_message="콘텐츠 생성을 위해 AI Worker가 작업을 기다리고 있습니다.",
            updated_at=_now().isoformat(timespec="seconds"),
        )
    except Exception:
        pass
    _start_mobile_one_shot_post_handoff(result_file)
    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=result["status"],
        message="모바일 원샷 작업이 프롬프트 생성기와 Gemini Worker 대기열에 등록되었습니다.",
        data=result,
    )


@router.get("/jobs/{job_id}", response_model=MobileOneShotJobResponse)
def get_mobile_one_shot_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.fullmatch(r"mob-[0-9]{14}-[a-f0-9]{8}", job_id):
        raise HTTPException(status_code=400, detail="job_id 형식이 올바르지 않습니다.")
    db_path = get_mobile_one_shot_result_path(job_id, current_user.id)
    result_file = Path(db_path) if db_path else None
    if not result_file or not result_file.exists():
        base = _output_root() / "mobile_one_shot"
        matches = list(base.glob(f"*/{job_id}/result.json")) if base.exists() else []
        if not matches:
            raise HTTPException(status_code=404, detail="작업 결과를 찾을 수 없습니다.")
        result_file = matches[0]
    data = json.loads(result_file.read_text(encoding="utf-8"))
    if str(data.get("user_bucket")) != str(current_user.id):
        raise HTTPException(status_code=404, detail="작업 결과를 찾을 수 없습니다.")
    try:
        row = db.execute(
            text("SELECT memo, persona_id, image_count FROM mobile_one_shot_jobs WHERE job_id = :job_id AND user_id = :user_id LIMIT 1"),
            {"job_id": job_id, "user_id": current_user.id},
        ).mappings().first()
        if row:
            if str(row.get("memo") or "").strip():
                data["memo"] = str(row.get("memo") or "")[:2000]
            data.setdefault("db_record", {})
            data["db_record"].update({
                "persona_id": row.get("persona_id"),
                "image_count": int(row.get("image_count") or data.get("image_count") or 0),
            })
    except Exception:
        pass
    data = _sync_worker_result(data, result_file)
    data = _reapply_staged_edited_contents(data, result_file)
    data = _start_podcast_job(data, result_file)
    data = _sync_podcast_result(data, result_file)
    data = _start_thumbnail_job(data, result_file)
    data = _sync_thumbnail_result(data, result_file)
    data = _start_shortform_job(data, result_file)
    data = _sync_shortform_result(data, result_file)
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass
    outputs = data.get("outputs") or {}
    raw_result = str(data.get("raw_result") or "")
    if raw_result:
        blog_titles = str(outputs.get("blog_titles") or outputs.get("BLOG_TITLES") or _extract_raw_result_block(raw_result, "BLOG_TITLES") or "").strip()
        blog_post = str(outputs.get("blog_post") or outputs.get("BLOG_POST") or _extract_raw_result_block(raw_result, "BLOG_POST") or "").strip()
        blog_hashtags = str(outputs.get("blog_hashtags") or outputs.get("BLOG_HASHTAGS") or _extract_raw_result_block(raw_result, "BLOG_HASHTAGS") or "").strip()
        if not str(outputs.get("blog") or "").strip():
            outputs["blog"] = "\n\n".join(part for part in [blog_titles, blog_post, blog_hashtags] if part).strip()
        outputs.setdefault("blog_titles", blog_titles)
        outputs.setdefault("blog_post", blog_post)
        outputs.setdefault("blog_hashtags", blog_hashtags)
        outputs.setdefault("instagram", _extract_raw_result_block(raw_result, "INSTAGRAM_POST"))
        outputs.setdefault("place", _extract_raw_result_block(raw_result, "NAVER_PLACE_NEWS"))
        outputs.setdefault("google_business", _extract_raw_result_block(raw_result, "GOOGLE_BUSINESS_POST"))
        outputs.setdefault("carrot", _extract_raw_result_block(raw_result, "CARROT_POST") or _extract_raw_result_block(raw_result, "DAANGN_POST"))
        data["outputs"] = outputs

    preview_text = str(outputs.get("blog") or outputs.get("BLOG") or data.get("raw_result") or "").strip()
    data["preview_text"] = preview_text[:3000]

    # 완료 화면과 보관함 모두 실제 작업 폴더의 고정 미디어를 동일한 인증 API로 사용합니다.
    media = data.setdefault("media", {})
    v1_job_ref = quote(str(job_id), safe="")
    fixed_media = {
        "mp3": (result_file.parent / "media" / "browser_podcast.mp3", "mp3_url", "mp3_path"),
        "srt": (result_file.parent / "media" / "browser_podcast.srt", "srt_url", "srt_path"),
        "thumbnail": (result_file.parent / "media" / "thumbnail.jpg", "thumbnail_url", "thumbnail_path"),
        "mp4": (result_file.parent / "media" / "shortform.mp4", "mp4_url", "mp4_path"),
    }
    for fixed_kind, (fixed_path, url_key, path_key) in fixed_media.items():
        if not fixed_path.is_file() or fixed_path.stat().st_size <= 0:
            continue
        fixed_url = f"/v1-api/mobile/one-shot/jobs/{v1_job_ref}/files/{fixed_kind}"
        media[path_key] = str(fixed_path)
        media[url_key] = fixed_url
        if fixed_kind == "thumbnail":
            media["thumbnail_preview_url"] = fixed_url
            media["thumbnail_download_url"] = fixed_url
            media["thumbnail_saved"] = True
        elif fixed_kind == "mp4":
            media["preview_mp4_url"] = fixed_url
            media["video_url"] = fixed_url

    data["file_urls"] = _mobile_download_file_urls(job_id, data, result_file.parent)
    data["download_url"] = f"/api/mobile/one-shot/jobs/{job_id}/download" if _mobile_download_zip_has_files(data, result_file.parent) else None

    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=data.get("status", "unknown"),
        message="모바일 원샷 작업 결과를 불러왔습니다.",
        data=data,
    )


def _require_mobile_admin(current_user: User) -> None:
    role = str(getattr(current_user, "role", "") or "").strip().lower()
    username = str(getattr(current_user, "username", "") or "").strip().lower()
    if role not in {"admin", "administrator", "관리자"} and username != "admin":
        raise HTTPException(status_code=403, detail="관리자만 사용할 수 있습니다.")


@router.get("/admin/backfill-titles")
@router.post("/admin/backfill-titles")
def backfill_mobile_one_shot_titles_api(
    limit: int = 300,
    current_user: User = Depends(get_current_user),
):
    _require_mobile_admin(current_user)
    candidates = list_mobile_one_shot_title_backfill_candidates(current_user.id, limit)
    updated = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    for row in candidates:
        job_id = str(row.get("job_id") or "").strip()
        result_path = str(row.get("result_path") or "").strip()
        if not job_id or not result_path:
            skipped += 1
            continue
        try:
            result_file = Path(result_path)
            if not result_file.exists() or not result_file.is_file():
                skipped += 1
                continue
            data = json.loads(result_file.read_text(encoding="utf-8"))
            if str(data.get("user_bucket")) != str(current_user.id):
                skipped += 1
                continue
            title = _mobile_job_title(data).strip()
            if not title or title == job_id or title.startswith("mob-"):
                skipped += 1
                continue
            update_mobile_one_shot_job_memo(job_id, current_user.id, title)
            updated += 1
        except Exception as exc:
            skipped += 1
            if len(errors) < 10:
                errors.append({"job_id": job_id, "error": str(exc)[:120]})
    return {"ok": True, "checked": len(candidates), "updated": updated, "skipped": skipped, "errors": errors}


@router.get("/admin/queue")
def list_mobile_one_shot_admin_queue_api(
    limit: int = 120,
    current_user: User = Depends(get_current_user),
):
    _require_mobile_admin(current_user)
    items = list_mobile_one_shot_admin_queue(limit)
    active_count = sum(1 for item in items if item.get("is_active"))
    failed_count = sum(1 for item in items if "fail" in str(item.get("status") or "").lower() or str(item.get("error_message") or ""))
    completed_count = sum(1 for item in items if item.get("completed_at") or int(item.get("percent") or 0) >= 100)
    return {
        "ok": True,
        "count": len(items),
        "active_count": active_count,
        "failed_count": failed_count,
        "completed_count": completed_count,
        "items": items,
    }


@router.get("/admin/usage")
def get_mobile_one_shot_admin_usage_api(
    current_user: User = Depends(get_current_user),
):
    _require_mobile_admin(current_user)
    usage = get_mobile_one_shot_admin_usage()
    return {"ok": True, **usage}


@router.get("/jobs/{job_id}/progress")
def get_mobile_one_shot_job_progress(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    if not re.fullmatch(r"mob-[0-9]{14}-[a-f0-9]{8}", job_id):
        raise HTTPException(status_code=400, detail="job_id 형식이 올바르지 않습니다.")
    progress = get_mobile_one_shot_progress(job_id, current_user.id)
    result_file = None
    if progress.get("result_path"):
        candidate = Path(str(progress.get("result_path")))
        if candidate.exists():
            result_file = candidate
    if result_file is None:
        base = _output_root() / "mobile_one_shot"
        matches = list(base.glob(f"*/{job_id}/result.json")) if base.exists() else []
        if matches:
            result_file = matches[0]
    if result_file and result_file.exists():
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            if str(data.get("user_bucket")) == str(current_user.id):
                media = data.setdefault("media", {})
                v1_job_ref = quote(str(job_id), safe="")
                repaired_media = False
                for fixed_kind, fixed_name, url_key, path_key in (
                    ("mp3", "browser_podcast.mp3", "mp3_url", "mp3_path"),
                    ("srt", "browser_podcast.srt", "srt_url", "srt_path"),
                    ("mp4", "shortform.mp4", "mp4_url", "mp4_path"),
                ):
                    fixed_path = result_file.parent / "media" / fixed_name
                    if not fixed_path.is_file() or fixed_path.stat().st_size <= 0:
                        continue
                    fixed_url = f"/v1-api/mobile/one-shot/jobs/{v1_job_ref}/files/{fixed_kind}"
                    if media.get(path_key) != str(fixed_path) or media.get(url_key) != fixed_url:
                        media[path_key] = str(fixed_path)
                        media[url_key] = fixed_url
                        repaired_media = True
                if repaired_media:
                    if media.get("mp3_path"):
                        media["podcast_status"] = "completed"
                        if str(media.get("status") or "").lower() in {"failed", "podcast_failed", "podcast_submit_failed"}:
                            media["status"] = "podcast_completed"
                        if str(media.get("message") or "").strip().lower() in {"파일 없음", "file not found", "missing file"}:
                            media["message"] = "브라우저 팟캐스트 MP3/SRT 연결을 복구했습니다."
                    _write_json_atomic(result_file, data)
                thumbnail_path = Path(str(media.get("thumbnail_path") or ""))
                project_key = str(
                    media.get("project_key")
                    or data.get("source_job_id")
                    or data.get("archive_group_key")
                    or ""
                ).strip()
                if thumbnail_path.is_file() and project_key:
                    public_thumbnail_url = f"/v1-api/slideshow/pc-thumbnail/{project_key}"
                    if (
                        media.get("thumbnail_url") != public_thumbnail_url
                        or media.get("thumbnail_preview_url") != public_thumbnail_url
                    ):
                        media["thumbnail_url"] = public_thumbnail_url
                        media["thumbnail_preview_url"] = public_thumbnail_url
                        media["thumbnail_download_url"] = public_thumbnail_url
                        temp_file = result_file.with_suffix(".json.tmp")
                        temp_file.write_text(
                            json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        temp_file.replace(result_file)
                        sync_mobile_one_shot_job_from_result(
                            data,
                            str(result_file),
                            _now().isoformat(timespec="seconds"),
                        )
                # V1 Windows: the progress screen polls only this endpoint.
                # Start the podcast pipeline here as well as in the detail endpoint.
                data = _start_podcast_job(data, result_file)
                payload = _mobile_progress_payload(data, job_id, current_user.id)
                db_queue_position = int(progress.get("queue_position") or 0) if progress else 0
                db_ahead_count = int(progress.get("ahead_count") or 0) if progress else 0
                payload_status = str(payload.get("status") or "").lower()
                payload_percent = int(payload.get("percent") or 0)
                if payload_percent < 100 and payload_status not in {"completed", "done", "failed", "cancelled", "canceled", "shortform_completed", "thumbnail_done"}:
                    payload["queue_position"] = db_queue_position
                    payload["ahead_count"] = db_ahead_count
                    if db_ahead_count > 0:
                        payload["message"] = f"앞에 {db_ahead_count}개 작업이 있습니다."
                try:
                    update_mobile_one_shot_progress(
                        job_id=job_id,
                        user_id=current_user.id,
                        status=payload.get("status"),
                        stage=str(payload.get("stage") or ""),
                        percent=int(payload.get("percent") or 0),
                        queue_position=int(payload.get("queue_position") or 0),
                        ahead_count=int(payload.get("ahead_count") or 0),
                        worker_status=str(payload.get("status") or ""),
                        progress_message=str(payload.get("message") or ""),
                        updated_at=_now().isoformat(timespec="seconds"),
                    )
                except Exception:
                    pass
                return payload
        except Exception:
            pass
    if not progress:
        raise HTTPException(status_code=404, detail="작업 상태를 찾지 못했습니다.")
    return {
        "ok": True,
        "job_id": job_id,
        "user_id": current_user.id,
        "status": progress.get("status") or "unknown",
        "stage": progress.get("stage") or progress.get("progress_message") or "작업 상태를 확인하고 있습니다.",
        "percent": int(progress.get("percent") or 0),
        "queue_position": int(progress.get("queue_position") or 0),
        "ahead_count": int(progress.get("ahead_count") or 0),
        "message": progress.get("progress_message") or progress.get("stage") or "작업 상태를 확인하고 있습니다.",
        "can_cancel": str(progress.get("status") or "") in {"queued", "gemini_worker_waiting", "worker_queued"},
        "created_at": progress.get("created_at"),
        "updated_at": progress.get("updated_at"),
        "completed_at": progress.get("completed_at"),
    }


@router.post("/main-jobs/{job_id}/images")
async def upload_storymaker_main_job_images(
    job_id: str,
    images: list[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
):
    if not re.fullmatch(r"storymaker_main_[0-9]{14}", job_id):
        raise HTTPException(status_code=400, detail="job_id format invalid")
    if len(images) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail="사진은 최대 12장까지 사용할 수 있습니다.")

    root = _output_root() / "storymaker_main_uploads" / job_id
    image_dir = root / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    saved_images: list[dict[str, Any]] = []
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            saved_images = list(manifest.get("images") or [])
        except Exception:
            saved_images = []

    next_index = len(saved_images) + 1
    for upload in images:
        original_name = upload.filename or f"image_{next_index}.jpg"
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            continue
        safe_name = _safe_filename(original_name, f"image_{next_index}{suffix or '.jpg'}")
        target = image_dir / f"{next_index:02d}_{safe_name}"
        content = await upload.read()
        if not content:
            continue
        target.write_bytes(content)
        saved_images.append({
            "name": original_name,
            "stored_name": target.name,
            "size": len(content),
            "url": _job_url_path(root, target),
        })
        next_index += 1
        if len(saved_images) >= MAX_IMAGES:
            break

    manifest = {
        "ok": True,
        "job_id": job_id,
        "source": "storymaker_main",
        "user_bucket": str(current_user.id),
        "image_count": len(saved_images),
        "images": saved_images,
        "updated_at": _now().isoformat(timespec="seconds"),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = _output_root() / "test_prompt_snapshots" / "latest_storymaker_main_images.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "job_id": job_id, "status": "uploaded", "message": "이미지를 현재 작업에 연결했습니다.", "data": manifest}


@router.post("/jobs/{job_id}/images", response_model=MobileOneShotJobResponse)
async def upload_mobile_one_shot_images(
    job_id: str,
    images: list[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
):
    if not re.fullmatch(r"mob-[0-9]{14}-[a-f0-9]{8}", job_id):
        raise HTTPException(status_code=400, detail="job_id format invalid")
    if len(images) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail="사진은 최대 12장까지 사용할 수 있습니다.")
    db_path = get_mobile_one_shot_result_path(job_id, current_user.id)
    result_file = Path(db_path) if db_path else None
    if not result_file or not result_file.exists():
        base = _output_root() / "mobile_one_shot"
        matches = list(base.glob(f"*/{job_id}/result.json")) if base.exists() else []
        if not matches:
            raise HTTPException(status_code=404, detail="job result not found")
        result_file = matches[0]
    data = json.loads(result_file.read_text(encoding="utf-8"))
    if str(data.get("user_bucket")) != str(current_user.id):
        raise HTTPException(status_code=404, detail="job result not found")

    job_dir = result_file.parent
    image_dir = job_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    saved_images = list(data.get("images") or [])
    next_index = len(saved_images) + 1
    for upload in images:
        original_name = upload.filename or f"image_{next_index}.jpg"
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            continue
        safe_name = _safe_filename(original_name, f"image_{next_index}{suffix or '.jpg'}")
        target = image_dir / f"{next_index:02d}_{safe_name}"
        content = await upload.read()
        if not content:
            continue
        target.write_bytes(content)
        saved_images.append({
            "name": original_name,
            "stored_name": target.name,
            "size": len(content),
            "url": _job_url_path(job_dir, target),
        })
        next_index += 1
        if len(saved_images) >= MAX_IMAGES:
            break

    data["images"] = saved_images
    data["image_count"] = len(saved_images)
    timing = data.setdefault("pipeline", {}).setdefault("timing", {})
    timing["images_uploaded_at"] = _now().isoformat(timespec="milliseconds")
    data.setdefault("media", {})["image_upload_status"] = "uploaded" if saved_images else "empty"
    _write_json_atomic(result_file, data)
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass
    try:
        update_mobile_one_shot_progress(
            job_id=job_id,
            user_id=current_user.id,
            status=result["status"],
            stage="Gemini Worker 대기열에 등록되었습니다.",
            percent=10,
            queue_position=0,
            ahead_count=0,
            worker_status="queued",
            progress_message="콘텐츠 생성을 위해 AI Worker가 작업을 기다리고 있습니다.",
            updated_at=_now().isoformat(timespec="seconds"),
        )
    except Exception:
        pass
    _start_mobile_one_shot_post_handoff(result_file)
    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=data.get("status", "gemini_worker_waiting"),
        message="사진을 작업에 추가했습니다.",
        data=data,
    )




@router.get("/staged-session/latest", response_model=MobileOneShotJobResponse)
def get_latest_staged_session(
    current_user: User = Depends(get_current_user),
):
    """현재 사용자의 최근 단계별 제작 작업을 부작용 없이 조회합니다."""
    for path_text in list_mobile_one_shot_result_paths(current_user.id, 50):
        try:
            result_file = Path(path_text).expanduser().resolve()
            if not result_file.is_file():
                continue
            data = json.loads(result_file.read_text(encoding="utf-8"))
            if str(data.get("user_bucket") or "") != str(current_user.id):
                continue
            if str(data.get("status") or "").lower() == "deleted" or data.get("deleted_at"):
                continue
            pipeline = data.get("pipeline") or {}
            if str(pipeline.get("production_mode") or "") != "staged" and not data.get("staged_session"):
                continue
            return MobileOneShotJobResponse(
                ok=True,
                job_id=str(data.get("job_id") or ""),
                status=str(data.get("status") or "staged_saved"),
                message="최근 단계별 제작 작업을 불러왔습니다.",
                data=data,
            )
        except Exception:
            continue
    return MobileOneShotJobResponse(
        ok=True,
        job_id="",
        status="empty",
        message="저장된 단계별 제작 작업이 없습니다.",
        data={},
    )


@router.post("/jobs/{job_id}/staged-session", response_model=MobileOneShotJobResponse)
def save_staged_session(
    job_id: str,
    req: StagedSessionSaveRequest,
    current_user: User = Depends(get_current_user),
):
    """단계별 제작 화면 복원에 필요한 입력값과 현재 단계를 저장합니다."""
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    now_text = _now().isoformat(timespec="milliseconds")
    current_step = max(1, min(int(req.current_step or 1), 9))
    staged_session = data.setdefault("staged_session", {})
    staged_session.update({
        "project_title": str(req.project_title or "")[:300],
        "work_memo": str(req.work_memo or "")[:10000],
        "keyword_input": str(req.keyword_input or "")[:2000],
        "persona_id": int(req.persona_id) if req.persona_id else None,
        "current_step": current_step,
        "stage_status": str(req.stage_status or "draft")[:80],
        "updated_at": now_text,
    })
    pipeline = data.setdefault("pipeline", {})
    pipeline["production_mode"] = "staged"
    pipeline["current_step"] = current_step
    pipeline["staged_status"] = staged_session["stage_status"]
    pipeline.setdefault("timing", {})["staged_session_saved_at"] = now_text
    _write_json_atomic(result_file, data)
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass
    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=str(data.get("status") or "staged_saved"),
        message="단계별 제작 진행 상태를 저장했습니다.",
        data=data,
    )


def _split_staged_blog_content(content_text: str) -> dict[str, str]:
    """단계별 블로그 합본을 제목·본문·해시태그로 분리하고 누적 중복을 정리합니다."""
    text_value = str(content_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text_value:
        return {"blog": "", "blog_titles": "", "blog_post": "", "blog_hashtags": ""}

    lines = text_value.split("\n")
    hashtag_blocks: list[str] = []
    end = len(lines)
    while end > 0:
        while end > 0 and not lines[end - 1].strip():
            end -= 1
        if end <= 0:
            break
        start = end - 1
        while start > 0 and lines[start - 1].strip():
            start -= 1
        block = "\n".join(line.strip() for line in lines[start:end] if line.strip()).strip()
        tokens = block.split()
        if tokens and all(token.startswith("#") and len(token) > 1 for token in tokens):
            hashtag_blocks.append(block)
            end = start
            continue
        break
    hashtags = hashtag_blocks[0] if hashtag_blocks else ""
    main_lines = lines[:end]

    body_start = None
    for idx, line in enumerate(main_lines):
        stripped = line.strip()
        if stripped.startswith("# ") or stripped.startswith("## ") or stripped.startswith("### "):
            body_start = idx
            break
    if body_start is None:
        body_start = 0
        seen_numbered = False
        for idx, line in enumerate(main_lines):
            stripped = line.strip()
            if re.match(r"^(?:\d+\.|\.)\s+", stripped):
                seen_numbered = True
                continue
            if seen_numbered and stripped:
                body_start = idx
                break

    prefix = main_lines[:body_start]
    groups: list[list[str]] = []
    current: list[str] = []
    for line in prefix:
        stripped = line.strip()
        if re.match(r"^(?:\d+\.|\.)\s+", stripped):
            if stripped.startswith(". "):
                stripped = "1. " + stripped[2:].lstrip()
            current.append(stripped)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    complete_groups = [group for group in groups if len(group) >= 3]
    title_group = complete_groups[-1] if complete_groups else (groups[-1] if groups else [])
    titles = "\n".join(title_group).strip()
    body = "\n".join(main_lines[body_start:]).strip()
    canonical = "\n\n".join(part for part in (titles, body, hashtags) if part).strip()
    return {"blog": canonical, "blog_titles": titles, "blog_post": body, "blog_hashtags": hashtags}


def _reapply_staged_edited_contents(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    """Worker 재동기화 뒤 단계별 제작에서 사용자가 저장한 수정본만 다시 적용합니다."""
    pipeline = data.get("pipeline") if isinstance(data.get("pipeline"), dict) else {}
    staged_session = data.get("staged_session") if isinstance(data.get("staged_session"), dict) else {}
    if str(pipeline.get("production_mode") or "").strip().lower() != "staged":
        return data

    edited_contents = staged_session.get("edited_contents")
    if not isinstance(edited_contents, dict) or not edited_contents:
        return data

    output_key_map = {
        "blog": ("blog",),
        "naver_place": ("place", "naver_place", "naver_place_news", "NAVER_PLACE_NEWS"),
        "google_business": ("google_business", "google_business_post", "GOOGLE_BUSINESS_POST"),
        "instagram": ("instagram", "instagram_post", "INSTAGRAM_POST"),
        "carrot": ("carrot", "carrot_post", "CARROT_POST"),
        "carousel": ("carousel_7", "CAROUSEL_7", "cardnews", "CAROUSEL", "CARDNEWS"),
        "podcast_50": ("podcast50", "podcast_50", "PODCAST_50"),
        "podcast_80": ("podcast80", "podcast_80", "PODCAST_80"),
    }

    outputs = data.setdefault("outputs", {})
    changed = False
    for content_key, content_value in edited_contents.items():
        key = str(content_key or "").strip().lower()
        text_value = str(content_value or "").strip()
        aliases = output_key_map.get(key)
        if not aliases or not text_value:
            continue
        if key == "blog":
            blog_parts = _split_staged_blog_content(text_value)
            text_value = blog_parts["blog"]
            staged_session.setdefault("edited_contents", {})["blog"] = text_value
            blog_aliases = {
                "blog": text_value,
                "blog_titles": blog_parts["blog_titles"],
                "BLOG_TITLES": blog_parts["blog_titles"],
                "blog_post": blog_parts["blog_post"],
                "BLOG_POST": blog_parts["blog_post"],
                "blog_hashtags": blog_parts["blog_hashtags"],
                "BLOG_HASHTAGS": blog_parts["blog_hashtags"],
            }
            for alias, alias_value in blog_aliases.items():
                if outputs.get(alias) != alias_value:
                    outputs[alias] = alias_value
                    changed = True
            data["preview_text"] = text_value
            continue
        for alias in aliases:
            if outputs.get(alias) != text_value:
                outputs[alias] = text_value
                changed = True

    if not changed:
        return data

    now_text = _now().isoformat(timespec="milliseconds")
    pipeline.setdefault("timing", {})["staged_edits_reapplied_at"] = now_text
    pipeline["staged_edits_reapplied"] = True
    staged_session["last_reapplied_at"] = now_text
    data["pipeline"] = pipeline
    data["staged_session"] = staged_session
    _write_json_atomic(result_file, data)
    return data


@router.post("/jobs/{job_id}/staged-draft", response_model=MobileOneShotJobResponse)
def save_staged_draft(
    job_id: str,
    req: StagedDraftSaveRequest,
    current_user: User = Depends(get_current_user),
):
    """단계별 제작 3단계에서 선택한 콘텐츠를 현재 작업과 보관함 DB에 저장합니다."""
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    content_key = str(req.content_key or "blog").strip().lower()
    content_text = str(req.content_text or req.draft_text or "").strip()
    if not content_text:
        raise HTTPException(status_code=400, detail="저장할 콘텐츠가 비어 있습니다.")
    if len(content_text) > 200000:
        raise HTTPException(status_code=413, detail="콘텐츠가 너무 깁니다.")

    output_key_map = {
        "blog": ("blog",),
        "naver_place": ("place", "naver_place_news", "NAVER_PLACE_NEWS"),
        "google_business": ("google_business", "google_business_post", "GOOGLE_BUSINESS_POST"),
        "instagram": ("instagram", "instagram_post", "INSTAGRAM_POST"),
        "carrot": ("carrot", "carrot_post", "CARROT_POST"),
        "carousel": ("carousel_7", "CAROUSEL_7", "cardnews", "CAROUSEL", "CARDNEWS"),
        "podcast_50": ("podcast50", "podcast_50", "PODCAST_50"),
        "podcast_80": ("podcast80", "podcast_80", "PODCAST_80"),
    }
    aliases = output_key_map.get(content_key)
    if not aliases:
        raise HTTPException(status_code=400, detail="지원하지 않는 콘텐츠 종류입니다.")

    outputs = data.setdefault("outputs", {})
    if content_key == "blog":
        blog_parts = _split_staged_blog_content(content_text)
        content_text = blog_parts["blog"]
        outputs.update({
            "blog": content_text,
            "blog_titles": blog_parts["blog_titles"],
            "BLOG_TITLES": blog_parts["blog_titles"],
            "blog_post": blog_parts["blog_post"],
            "BLOG_POST": blog_parts["blog_post"],
            "blog_hashtags": blog_parts["blog_hashtags"],
            "BLOG_HASHTAGS": blog_parts["blog_hashtags"],
        })
        data["preview_text"] = content_text
    else:
        for alias in aliases:
            outputs[alias] = content_text

    staged_session = data.setdefault("staged_session", {})
    now_text = _now().isoformat(timespec="milliseconds")
    edited_contents = staged_session.setdefault("edited_contents", {})
    edited_contents[content_key] = content_text
    staged_session["active_content_key"] = content_key
    staged_session["draft_edited"] = True
    staged_session["draft_saved_at"] = now_text
    staged_session["current_step"] = max(3, int(staged_session.get("current_step") or 3))
    staged_session["stage_status"] = "content_edited"
    if content_key == "blog":
        staged_session["edited_draft"] = content_text

    pipeline = data.setdefault("pipeline", {})
    pipeline["production_mode"] = "staged"
    pipeline["current_step"] = max(3, int(pipeline.get("current_step") or 3))
    pipeline["staged_status"] = "content_edited"
    pipeline.setdefault("timing", {})["staged_draft_saved_at"] = now_text

    _write_json_atomic(result_file, data)
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception as exc:
        logger.exception("staged content DB sync failed job_id=%s content_key=%s", job_id, content_key)
        raise HTTPException(status_code=500, detail=f"콘텐츠 파일은 저장됐지만 보관함 DB 동기화에 실패했습니다: {str(exc)[:200]}")

    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=str(data.get("status") or "staged_saved"),
        message="수정한 콘텐츠를 현재 작업과 보관함 DB에 저장했습니다.",
        data=data,
    )


@router.post("/jobs/{job_id}/staged-videos", response_model=MobileOneShotJobResponse)
async def upload_staged_job_videos(
    job_id: str,
    videos: list[UploadFile] = File(default=[]),
    media_order: str = Form(default="[]"),
    current_user: User = Depends(get_current_user),
):
    stage2_started = time.perf_counter()
    stage2_started_at = _now().isoformat(timespec="milliseconds")
    """단계별 제작 전용 동영상 저장 API.

    기존 딸깍 제작의 /jobs 생성 API와 images 저장 흐름은 수정하지 않습니다.
    이 엔드포인트를 명시적으로 호출한 단계별 제작 작업에만 videos 폴더와
    staged_media_order 메타데이터를 추가합니다.
    """
    if len(videos) > MAX_STAGED_VIDEOS:
        raise HTTPException(status_code=400, detail=f"동영상은 최대 {MAX_STAGED_VIDEOS}개까지 사용할 수 있습니다.")

    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    job_dir = result_file.parent
    video_dir = job_dir / "videos"

    try:
        parsed_order = json.loads(media_order or "[]")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="사진·동영상 순서 정보가 올바르지 않습니다.")
    if not isinstance(parsed_order, list) or len(parsed_order) > (MAX_IMAGES + MAX_STAGED_VIDEOS):
        raise HTTPException(status_code=400, detail="사진·동영상 순서 정보가 올바르지 않습니다.")

    normalized_order: list[dict[str, int | str]] = []
    for item in parsed_order:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if kind in {"image", "video"} and index >= 0:
            normalized_order.append({"kind": kind, "index": index})

    if video_dir.exists():
        shutil.rmtree(video_dir)
    video_dir.mkdir(parents=True, exist_ok=True)

    saved_videos: list[dict[str, Any]] = []
    try:
        for index, upload in enumerate(videos, start=1):
            original_name = upload.filename or f"video_{index}.mp4"
            suffix = Path(original_name).suffix.lower()
            if suffix not in ALLOWED_VIDEO_EXTENSIONS:
                continue
            safe_name = _safe_filename(original_name, f"video_{index}{suffix}")
            target = video_dir / f"{index:02d}_{safe_name}"
            temp_target = video_dir / f".{target.name}.{uuid.uuid4().hex}.tmp"
            total_size = 0
            with temp_target.open("wb") as output:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_STAGED_VIDEO_BYTES:
                        raise HTTPException(status_code=413, detail="동영상 한 개의 최대 크기는 1GB입니다.")
                    output.write(chunk)
            if total_size <= 0:
                temp_target.unlink(missing_ok=True)
                continue
            os.replace(temp_target, target)
            saved_videos.append({
                "name": original_name,
                "stored_name": target.name,
                "size": total_size,
                "url": _job_url_path(job_dir, target),
                "kind": "video",
            })
    finally:
        for upload in videos:
            try:
                await upload.close()
            except Exception:
                pass

    file_write_done = time.perf_counter()
    data["videos"] = saved_videos
    data["video_count"] = len(saved_videos)
    pipeline = data.setdefault("pipeline", {})
    pipeline["production_mode"] = "staged"
    pipeline["staged_media_order"] = normalized_order
    timing = pipeline.setdefault("timing", {})
    timing["staged_videos_upload_started_at"] = stage2_started_at
    timing["staged_videos_uploaded_at"] = _now().isoformat(timespec="milliseconds")
    metrics = pipeline.setdefault("stage2_metrics", {})
    metrics["videos"] = {
        "count": len(saved_videos),
        "bytes": sum(int(item.get("size") or 0) for item in saved_videos),
        "file_write_ms": round((file_write_done - stage2_started) * 1000, 2),
    }
    data.setdefault("media", {})["staged_video_upload_status"] = "uploaded" if saved_videos else "empty"
    _write_json_atomic(result_file, data)
    db_started = time.perf_counter()
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass
    db_done = time.perf_counter()
    metrics["videos"]["db_sync_ms"] = round((db_done - db_started) * 1000, 2)
    metrics["videos"]["total_ms"] = round((db_done - stage2_started) * 1000, 2)
    _write_json_atomic(result_file, data)

    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=data.get("status", "gemini_worker_waiting"),
        message="단계별 제작 동영상과 혼합 순서를 저장했습니다.",
        data=data,
    )


@router.post("/jobs/{job_id}/staged-images", response_model=MobileOneShotJobResponse)
async def upload_staged_job_images(
    job_id: str,
    images: list[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
):
    stage2_started = time.perf_counter()
    stage2_started_at = _now().isoformat(timespec="milliseconds")
    """단계별 제작 전용 이미지 저장 API. 기존 딸깍 후속 제작은 시작하지 않습니다."""
    if len(images) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail=f"사진은 최대 {MAX_IMAGES}장까지 사용할 수 있습니다.")

    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    job_dir = result_file.parent
    image_dir = job_dir / "images"
    if image_dir.exists():
        shutil.rmtree(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)

    saved_images: list[dict[str, Any]] = []
    try:
        for index, upload in enumerate(images, start=1):
            original_name = upload.filename or f"image_{index}.jpg"
            suffix = Path(original_name).suffix.lower()
            if suffix not in ALLOWED_IMAGE_EXTENSIONS:
                continue
            safe_name = _safe_filename(original_name, f"image_{index}{suffix or '.jpg'}")
            target = image_dir / f"{index:02d}_{safe_name}"
            content = await upload.read()
            if not content:
                continue
            target.write_bytes(content)
            saved_images.append({
                "name": original_name,
                "stored_name": target.name,
                "size": len(content),
                "url": _job_url_path(job_dir, target),
                "kind": "image",
            })
    finally:
        for upload in images:
            try:
                await upload.close()
            except Exception:
                pass

    file_write_done = time.perf_counter()
    data["images"] = saved_images
    data["image_count"] = len(saved_images)
    pipeline = data.setdefault("pipeline", {})
    pipeline["production_mode"] = "staged"
    timing = pipeline.setdefault("timing", {})
    timing["staged_images_upload_started_at"] = stage2_started_at
    timing["staged_images_uploaded_at"] = _now().isoformat(timespec="milliseconds")
    metrics = pipeline.setdefault("stage2_metrics", {})
    metrics["images"] = {
        "count": len(saved_images),
        "bytes": sum(int(item.get("size") or 0) for item in saved_images),
        "file_write_ms": round((file_write_done - stage2_started) * 1000, 2),
    }
    data.setdefault("media", {})["staged_image_upload_status"] = "uploaded" if saved_images else "empty"
    _write_json_atomic(result_file, data)
    db_started = time.perf_counter()
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass
    db_done = time.perf_counter()
    metrics["images"]["db_sync_ms"] = round((db_done - db_started) * 1000, 2)
    metrics["images"]["total_ms"] = round((db_done - stage2_started) * 1000, 2)
    _write_json_atomic(result_file, data)
    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=data.get("status", "gemini_worker_waiting"),
        message="단계별 제작 이미지를 저장했습니다.",
        data=data,
    )




def _start_staged_thumbnail_job(data: dict[str, Any], result_file: Path) -> dict[str, Any]:
    """단계별 제작 전용 썸네일 요청. 기존 딸깍 썸네일 함수는 호출하거나 변경하지 않는다."""
    thumbnail_started = time.perf_counter()
    thumbnail_started_at = _now().isoformat(timespec="milliseconds")
    media = data.setdefault("media", {})
    if media.get("thumbnail_url"):
        return data
    if media.get("thumbnail_job_id"):
        return data

    outputs = data.get("outputs") or {}
    instagram_text = str(outputs.get("instagram") or data.get("raw_result") or "").strip()
    image_items = data.get("images") or []
    if not instagram_text:
        media["thumbnail_status"] = "thumbnail_waiting_text"
        return data
    if not image_items:
        media["thumbnail_status"] = "thumbnail_waiting_images"
        return data

    root = _output_root()
    now = _now()
    job_id = "thumbnail_" + now.strftime("%Y%m%d_%H%M%S") + "_mobile"
    job_dir = root / "test_thumbnail_jobs" / job_id
    input_dir = job_dir / "input_images"
    input_dir.mkdir(parents=True, exist_ok=True)
    source_dir = result_file.parent / "images"
    copied_urls: list[str] = []
    copied_image_paths: list[Path] = []
    for item in image_items[:3]:
        stored_name = str(item.get("stored_name") or "")
        if not stored_name:
            continue
        src = source_dir / stored_name
        if not src.exists():
            continue
        dst = input_dir / src.name
        dst.write_bytes(src.read_bytes())
        copied_image_paths.append(dst)
        copied_urls.append(f"/data/output_results/test_thumbnail_jobs/{job_id}/input_images/{dst.name}")
    if not copied_urls:
        media.update({"thumbnail_status": "thumbnail_waiting", "message": "썸네일에 사용할 이미지를 찾는 중입니다."})
        return data

    reference_urls = copied_urls[:3]
    instagram_text = instagram_text[:3000]
    persona = data.get("persona") or {}
    project_title = str(persona.get("company_name") or data.get("job_id") or "모바일 원샷 썸네일")
    image_lines = "\n".join(f"- 참고 이미지 {index + 1}: {url}" for index, url in enumerate(reference_urls))
    prompt = f"""[썸네일 제작 요청]

첨부된 이미지들을 참고해서 인스타그램용 9:16 세로형 썸네일 이미지를 만들어줘.

[업체 정보]
상호명: {project_title}
전화번호: {persona.get('phone_number') or ''}
키워드: {', '.join(data.get('keywords') or [])}

[인스타그램 게시글 참고 문안]
{instagram_text}

[디자인 지시]
- 첫 인스타그램 문안의 핵심 메시지를 반영해줘.
- 상호, 키워드, 전화번호가 모바일에서 잘 보이게 구성해줘.
- 현장 사진의 실제 분위기를 살려줘.
- 과장된 광고 느낌보다 지역 소상공인 현장감이 느껴지게 만들어줘.
- 글자는 너무 많이 넣지 말고 핵심 문구 중심으로 배치해줘.

[참고 이미지]
{image_lines}

- 위 참고 이미지 3장을 각각 확인하고 현장 구도와 분위기를 반영해 주세요.
- 사진을 단순히 한 장으로 합치지 말고, 가장 적합한 구도와 요소를 선택해 최종 9:16 썸네일을 제작해 주세요.
""".strip()
    prompt_path = job_dir / "thumbnail_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    snapshot_dir = root / "test_prompt_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    worker_latest_prompt_path = snapshot_dir / "latest_prompt.md"
    worker_latest_prompt_path.write_text(prompt, encoding="utf-8")
    (snapshot_dir / "latest_thumbnail_prompt.md").write_text(prompt, encoding="utf-8")
    (snapshot_dir / "latest.json").write_text(json.dumps({
        "ok": True,
        "created_at": now.isoformat(timespec="seconds"),
        "project_title": project_title,
        "prompt_for_chatgpt": str(worker_latest_prompt_path),
        "latest_prompt_path": str(worker_latest_prompt_path),
        "payload": {"source": "mobile_one_shot_thumbnail", "action": "GENERATE_GEMINI_THUMBNAIL", "job_id": job_id},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    trigger_dir = root / "test_triggers"
    trigger_dir.mkdir(parents=True, exist_ok=True)
    trigger = {
        "ok": True,
        "status": "pending",
        "action": "GENERATE_GEMINI_THUMBNAIL",
        "job_id": job_id,
        "source_job_id": str(data.get("job_id") or ""),
        "project_title": project_title,
        "prompt_path": str(prompt_path),
        "latest_prompt_path": str(worker_latest_prompt_path),
        "source": "mobile_one_shot",
        "handoff": "mobile_shortform_to_firefox_thumbnail",
        "created_at": now.isoformat(timespec="seconds"),
        "image_urls": reference_urls,
    }
    (trigger_dir / "trigger_status.json").write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
    trigger_done = time.perf_counter()
    media.update({
        "thumbnail_status": "thumbnail_requested",
        "thumbnail_job_id": job_id,
        "thumbnail_reference_urls": reference_urls,
        "message": "단계별 제작 썸네일 작업을 Firefox AI Worker로 넘겼습니다.",
    })
    pipeline = data.setdefault("pipeline", {})
    pipeline["production_mode"] = "staged"
    timing = pipeline.setdefault("timing", {})
    timing["staged_thumbnail_started_at"] = thumbnail_started_at
    timing["staged_thumbnail_triggered_at"] = _now().isoformat(timespec="milliseconds")
    pipeline.setdefault("stage2_metrics", {})["thumbnail"] = {
        "reference_count": len(reference_urls),
        "reference_bytes": sum(path.stat().st_size for path in copied_image_paths if path.exists()),
        "prepare_and_trigger_ms": round((trigger_done - thumbnail_started) * 1000, 2),
    }
    data["steps"] = [
        {"label": "1단계 글 만들기", "status": "done"},
        {"label": "2단계 사진·동영상 저장", "status": "done"},
        {"label": "썸네일 생성", "status": "active"},
    ]
    _write_json_atomic(result_file, data)
    return data


@router.post("/jobs/{job_id}/staged-thumbnail", response_model=MobileOneShotJobResponse)
def start_staged_job_thumbnail(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    if not (data.get("outputs") or {}).get("instagram") and not str(data.get("raw_result") or "").strip():
        raise HTTPException(status_code=409, detail="1단계 콘텐츠 결과가 아직 준비되지 않았습니다.")
    if not data.get("images"):
        raise HTTPException(status_code=409, detail="썸네일에 사용할 사진이 저장되지 않았습니다.")
    route_started = time.perf_counter()
    data = _start_staged_thumbnail_job(data, result_file)
    prepared = time.perf_counter()
    _write_json_atomic(result_file, data)
    db_started = time.perf_counter()
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass
    db_done = time.perf_counter()
    thumbnail_metrics = data.setdefault("pipeline", {}).setdefault("stage2_metrics", {}).setdefault("thumbnail", {})
    thumbnail_metrics["route_prepare_ms"] = round((prepared - route_started) * 1000, 2)
    thumbnail_metrics["db_sync_ms"] = round((db_done - db_started) * 1000, 2)
    thumbnail_metrics["total_ms"] = round((db_done - route_started) * 1000, 2)
    _write_json_atomic(result_file, data)
    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=data.get("status", "thumbnail_requested"),
        message=str((data.get("media") or {}).get("message") or "썸네일 프롬프트를 Worker에 전달했습니다."),
        data=data,
    )


@router.post("/jobs/{job_id}/podcast-started", response_model=MobileOneShotJobResponse)
def mark_mobile_one_shot_browser_podcast_started(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    # PC one-click keeps source images in storymaker_main_uploads. Materialize
    # them into the archive result before scheduling the shared thumbnail flow.
    data = _sync_storymaker_main_images(data, result_file)
    media = data.setdefault("media", {})
    pipeline = data.setdefault("pipeline", {})
    timing = pipeline.setdefault("timing", {})

    if not timing.get("podcast_submit_at"):
        timing["podcast_submit_at"] = _now().isoformat(timespec="milliseconds")

    if not media.get("mp3_url") and not media.get("mp3_path"):
        media["podcast_status"] = "browser_running"
        media["message"] = "PC browser podcast generation started and thumbnail job was scheduled."

    _write_json_atomic(result_file, data)
    _schedule_thumbnail_job_after_podcast_start(result_file, delay_seconds=1.0)

    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass

    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=data.get("status", "gemini_completed"),
        message="PC browser podcast start signal recorded.",
        data=data,
    )




@router.get("/jobs/{job_id}/staged-image/{image_index}")
def get_mobile_one_shot_staged_image(
    job_id: str,
    image_index: int,
    current_user: User = Depends(get_current_user),
):
    """단계별 제작 브라우저 MP4 렌더러용 이미지 1장 조회."""
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    pipeline = data.get("pipeline") or {}
    if str(pipeline.get("production_mode") or "") != "staged" and not data.get("staged_session"):
        raise HTTPException(status_code=404, detail="단계별 제작 작업이 아닙니다.")
    image_dir = result_file.parent / "images"
    image_files = [path for path in sorted(image_dir.iterdir()) if path.is_file()] if image_dir.exists() else []
    if image_index < 0 or image_index >= len(image_files):
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")
    target = image_files[image_index]
    return FileResponse(path=target, filename=target.name)

@router.post("/jobs/{job_id}/browser-shortform")
async def upload_mobile_one_shot_browser_shortform(
    job_id: str,
    mp4: UploadFile = File(...),
    provider: str = Form(default="browser"),
    duration_seconds: float = Form(default=0),
    current_user: User = Depends(get_current_user),
):
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    job_dir = result_file.parent
    media_dir = job_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    filename = str(mp4.filename or "shortform.mp4").lower()
    content_type = str(mp4.content_type or "").lower()
    if not filename.endswith(".mp4") and content_type not in {"video/mp4", "application/mp4", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="MP4 파일만 저장할 수 있습니다.")

    target = media_dir / "shortform.mp4"
    temp_target = media_dir / f".shortform.mp4.{uuid.uuid4().hex}.tmp"
    max_bytes = 2 * 1024 * 1024 * 1024
    total_size = 0
    try:
        with temp_target.open("wb") as output:
            while True:
                chunk = await mp4.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_bytes:
                    raise HTTPException(status_code=413, detail="MP4 파일이 너무 큽니다.")
                output.write(chunk)
        if total_size <= 0:
            raise HTTPException(status_code=400, detail="MP4 파일이 비어 있습니다.")
        os.replace(temp_target, target)
    finally:
        try:
            await mp4.close()
        except Exception:
            pass
        if temp_target.exists():
            temp_target.unlink(missing_ok=True)

    video_url = f"/v1-api/mobile/one-shot/jobs/{quote(job_id, safe='')}/files/mp4"
    data_url = _job_url_path(job_dir, target)
    media = data.setdefault("media", {})
    source_job_id = str(data.get("source_job_id") or data.get("archive_group_key") or data.get("job_id") or job_id or "").strip()
    if not source_job_id:
        raise HTTPException(status_code=409, detail="Current source_job_id is missing; MP4 upload was rejected.")
    media.update({
        "mp4_path": str(target),
        "mp4_url": video_url,
        "preview_mp4_url": video_url,
        "video_url": video_url,
        "mp4_source_job_id": source_job_id,
        "mp4_archive_job_id": str(job_id),
        "status": "shortform_completed",
        "shortform_status": "completed",
        "video_rendered": True,
        "video_saved": True,
        "shortform_provider": str(provider or "browser")[:40],
        "shortform_duration_seconds": max(0.0, float(duration_seconds or 0)),
        "message": "브라우저에서 제작한 MP4를 서버에 저장했습니다.",
    })
    timing = data.setdefault("pipeline", {}).setdefault("timing", {})
    timing["browser_mp4_saved_at"] = _now().isoformat(timespec="milliseconds")
    data["steps"] = [
        {"label": "1단계 글 만들기", "status": "done"},
        {"label": "2단계 팟캐스트 만들기", "status": "done"},
        {"label": "3단계 숏폼 영상 만들기", "status": "done"},
        {"label": "영상 서버 저장", "status": "done"},
    ]
    _write_json_atomic(result_file, data)
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass

    return {
        "ok": True,
        "job_id": job_id,
        "status": "video_saved",
        "video_url": video_url,
        "data_url": data_url,
        "size": total_size,
    }


@router.post("/jobs/{job_id}/browser-podcast", response_model=MobileOneShotJobResponse)
async def upload_mobile_one_shot_browser_podcast(
    job_id: str,
    mp3: UploadFile = File(...),
    srt: UploadFile = File(...),
    provider: str = Form(default="wasm"),
    duration_seconds: float = Form(default=0),
    current_user: User = Depends(get_current_user),
):
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    job_dir = result_file.parent
    media_dir = job_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    mp3_content = await mp3.read()
    srt_content = await srt.read()
    if not mp3_content:
        raise HTTPException(status_code=400, detail="MP3 파일이 비어 있습니다.")
    if len(mp3_content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="MP3 파일이 너무 큽니다.")
    if len(srt_content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="SRT 파일이 너무 큽니다.")

    browser_mp3_path = media_dir / "browser_podcast.mp3"
    browser_srt_path = media_dir / "browser_podcast.srt"
    browser_mp3_path.write_bytes(mp3_content)
    if srt_content:
        browser_srt_path.write_bytes(srt_content)

    # 단계별 제작에서만 브라우저 음성 MP3에 V1 음악 라이브러리의 배경음을 섞습니다.
    # 일반 딸깍 작업과 기존 pc-backend 음악 믹싱 소유권 흐름은 그대로 둡니다.
    pipeline = data.get("pipeline") if isinstance(data.get("pipeline"), dict) else {}
    is_staged = str(pipeline.get("production_mode") or "").strip().lower() == "staged"
    staged_mixed_mp3_path = None
    staged_music_file = None
    staged_music_volume = 0.10
    staged_mix_error = None
    if is_staged:
        try:
            music_root = Path(os.getenv("STORYMAKER_MUSIC_LIBRARY_DIR", "/data/music")).resolve()
            music_extensions = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
            music_candidates = [
                item for item in music_root.iterdir()
                if item.is_file() and item.suffix.lower() in music_extensions and item.stat().st_size > 0
            ] if music_root.is_dir() else []
            if music_candidates:
                preferred = [item for item in music_candidates if item.name.lower() in {"background_music.mp3", "1background_music.mp3"}]
                selected_music = random.choice(preferred or music_candidates)
                staged_mixed_mp3_path = media_dir / "browser_podcast_mixed.mp3"
                command = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(browser_mp3_path),
                    "-stream_loop", "-1", "-i", str(selected_music),
                    "-filter_complex",
                    f"[1:a]volume={staged_music_volume}[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "[a]", "-c:a", "libmp3lame", "-q:a", "2",
                    str(staged_mixed_mp3_path),
                ]
                completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
                if completed.returncode != 0 or not staged_mixed_mp3_path.exists() or staged_mixed_mp3_path.stat().st_size <= 0:
                    raise RuntimeError((completed.stderr or completed.stdout or "ffmpeg music mix failed").strip())
                staged_music_file = selected_music.name
            else:
                staged_mix_error = "music library is empty"
        except Exception as exc:
            staged_mixed_mp3_path = None
            staged_mix_error = str(exc)[:500]

    source_job_id = str(data.get("source_job_id") or data.get("archive_group_key") or "").strip()
    claim_file = job_dir / "pc_podcast_claim.json"
    claim = {}
    if claim_file.exists():
        try:
            claim = json.loads(claim_file.read_text(encoding="utf-8"))
        except Exception:
            claim = {}
    claim_source_job_id = str(claim.get("source_job_id") or "").strip()
    server_root = Path(os.getenv("V1_PODCAST_OUTPUT_DIR", "/data/v1_podcast_output"))
    server_mp3 = server_root / source_job_id / f"{source_job_id}.mp3"
    server_srt = server_root / source_job_id / f"{source_job_id}.srt"
    use_server_mix = bool(
        source_job_id
        and claim.get("owner") == "pc-backend"
        and claim_source_job_id == source_job_id
        and server_mp3.exists()
        and server_mp3.is_file()
        and server_mp3.stat().st_size > 0
    )
    if use_server_mix:
        mp3_path = media_dir / "server_podcast.mp3"
        srt_path = media_dir / "server_podcast.srt"
        shutil.copy2(server_mp3, mp3_path)
        if server_srt.exists() and server_srt.stat().st_size > 0:
            shutil.copy2(server_srt, srt_path)
            final_srt_exists = True
        elif srt_content:
            shutil.copy2(browser_srt_path, srt_path)
            final_srt_exists = True
        else:
            final_srt_exists = False
        podcast_provider = "pc-backend-mixed"
    else:
        mp3_path = staged_mixed_mp3_path if staged_mixed_mp3_path is not None else browser_mp3_path
        srt_path = browser_srt_path
        final_srt_exists = bool(srt_content)
        podcast_provider = provider if provider in {"webgpu", "wasm"} else "wasm"
        if staged_mixed_mp3_path is not None:
            podcast_provider = f"{podcast_provider}-music-mixed"

    safe_provider = podcast_provider
    media = data.setdefault("media", {})
    v1_job_ref = quote(str(job_id), safe="")
    media.update({
        "mp3_path": str(mp3_path),
        "mp3_url": f"/v1-api/mobile/one-shot/jobs/{v1_job_ref}/files/mp3",
        "srt_path": str(srt_path) if final_srt_exists else None,
        "srt_url": f"/v1-api/mobile/one-shot/jobs/{v1_job_ref}/files/srt" if final_srt_exists else None,
        "podcast_source_job_id": source_job_id,
        "server_music_mix_applied": use_server_mix,
        "staged_music_mix_applied": bool(staged_mixed_mp3_path),
        "staged_music_file": staged_music_file,
        "staged_music_volume": staged_music_volume if is_staged else None,
        "staged_music_mix_error": staged_mix_error,
        "browser_original_mp3_path": str(browser_mp3_path) if is_staged else None,
        "status": "podcast_completed",
        "podcast_status": "completed",
        "podcast_provider": safe_provider,
        "podcast_duration_seconds": max(0.0, float(duration_seconds or 0)),
        "message": "모바일 브라우저 MP3/SRT 업로드가 완료되었습니다.",
    })
    timing = data.setdefault("pipeline", {}).setdefault("timing", {})
    if not timing.get("podcast_submit_at"):
        timing["podcast_submit_at"] = _now().isoformat(timespec="milliseconds")
    timing["podcast_completed_at"] = _now().isoformat(timespec="milliseconds")

    # V1 one-click keeps its source images under storymaker_main_uploads, while
    # the archive result lives under a generated mob-* job.
    data = _sync_storymaker_main_images(data, result_file)
    media = data.setdefault("media", {})
    _write_json_atomic(result_file, data)
    if is_staged:
        data = _start_shortform_job(data, result_file)
        data = _sync_shortform_result(data, result_file)
    else:
        pipeline = data.setdefault("pipeline", {})
        pipeline["shortform_owner"] = "browser"
        pipeline["server_shortform_skipped_at"] = _now().isoformat(timespec="milliseconds")
    _schedule_thumbnail_job_after_podcast_start(result_file, delay_seconds=1.0)
    data["steps"] = [
        {"label": "1단계 글 만들기", "status": "done"},
        {"label": "2단계 팟캐스트 만들기", "status": "done"},
        {"label": "3단계 숏폼 영상 만들기", "status": "active"},
    ]
    _write_json_atomic(result_file, data)
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass

    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=data.get("status", "gemini_completed"),
        message="모바일 브라우저 팟캐스트를 저장했습니다.",
        data=data,
    )


@router.post("/jobs/{job_id}/podcast", response_model=MobileOneShotJobResponse)
def start_mobile_one_shot_podcast(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 이 엔드포인트를 명시적으로 호출한 경우에는 무거운 모바일 브라우저 TTS 대신
    # Dell 서버의 기존 팟캐스트 생성기를 사용한다.
    explicit_result_file = _find_mobile_result_file(job_id, current_user)
    explicit_data = json.loads(explicit_result_file.read_text(encoding="utf-8"))
    explicit_data.setdefault("pipeline", {})["browser_podcast"] = False
    explicit_data.setdefault("media", {}).update({
        "status": "podcast_requested",
        "podcast_status": "requested",
        "message": "Dell 서버에서 MP3 생성을 시작합니다.",
    })
    _write_json_atomic(explicit_result_file, explicit_data)
    if not re.fullmatch(r"mob-[0-9]{14}-[a-f0-9]{8}", job_id):
        raise HTTPException(status_code=400, detail="job_id 형식이 올바르지 않습니다.")
    db_path = get_mobile_one_shot_result_path(job_id, current_user.id)
    result_file = Path(db_path) if db_path else None
    if not result_file or not result_file.exists():
        base = _output_root() / "mobile_one_shot"
        matches = list(base.glob(f"*/{job_id}/result.json")) if base.exists() else []
        if not matches:
            raise HTTPException(status_code=404, detail="작업 결과를 찾을 수 없습니다.")
        result_file = matches[0]
    data = json.loads(result_file.read_text(encoding="utf-8"))
    if str(data.get("user_bucket")) != str(current_user.id):
        raise HTTPException(status_code=404, detail="작업 결과를 찾을 수 없습니다.")
    try:
        row = db.execute(
            text("SELECT memo, persona_id, image_count FROM mobile_one_shot_jobs WHERE job_id = :job_id AND user_id = :user_id LIMIT 1"),
            {"job_id": job_id, "user_id": current_user.id},
        ).mappings().first()
        if row:
            if str(row.get("memo") or "").strip():
                data["memo"] = str(row.get("memo") or "")[:2000]
            data.setdefault("db_record", {})
            data["db_record"].update({
                "persona_id": row.get("persona_id"),
                "image_count": int(row.get("image_count") or data.get("image_count") or 0),
            })
    except Exception:
        pass
    data = _sync_worker_result(data, result_file)
    data = _start_podcast_job(data, result_file)
    data = _sync_podcast_result(data, result_file)
    data = _start_thumbnail_job(data, result_file)
    data = _sync_thumbnail_result(data, result_file)
    data = _start_shortform_job(data, result_file)
    data = _sync_shortform_result(data, result_file)
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass
    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=data.get("status", "unknown"),
        message="팟캐스트 만들기 요청을 처리했습니다.",
        data=data,
    )


@router.post("/jobs/{job_id}/shortform", response_model=MobileOneShotJobResponse)
def start_mobile_one_shot_shortform(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    data = _sync_worker_result(data, result_file)
    data = _sync_podcast_result(data, result_file)
    data = _start_thumbnail_job(data, result_file)
    data = _sync_thumbnail_result(data, result_file)
    data = _start_shortform_job(data, result_file)
    data = _sync_shortform_result(data, result_file)
    try:
        sync_mobile_one_shot_job_from_result(data, str(result_file), _now().isoformat(timespec="seconds"))
    except Exception:
        pass
    return MobileOneShotJobResponse(
        ok=True,
        job_id=job_id,
        status=data.get("status", "unknown"),
        message="shortform request handled",
        data=data,
    )


@router.get("/jobs/{job_id}/download")
def download_mobile_one_shot_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))

    job_dir = result_file.parent
    try:
        data = _sync_podcast_result(data, result_file)
        data = _sync_thumbnail_result(data, result_file)
        data = _sync_shortform_result(data, result_file)
    except Exception:
        pass
    files = _mobile_project_files(data)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(result_file, "result.json")
        outputs = data.get("outputs") or {}
        text_parts = []
        for key in ["blog", "instagram", "place", "carrot", "podcast50", "podcast80"]:
            value = str(outputs.get(key) or "").strip()
            if value:
                text_parts.append(f"[{key}]\n{value}")
        if not text_parts and data.get("raw_result"):
            text_parts.append(str(data.get("raw_result")))
        zf.writestr("texts/generated_text.txt", "\n\n".join(text_parts))

        image_dir = job_dir / "images"
        if image_dir.exists():
            for path in sorted(image_dir.iterdir()):
                if path.is_file():
                    zf.write(path, f"images/{path.name}")

        media = data.get("media") or {}
        media_zip_items = [
            ("mp3", "media/" + (files.get("mp3_filename") or "podcast.mp3")),
            ("srt", "media/" + (files.get("srt_filename") or "subtitle.srt")),
            ("mp4", "media/" + (files.get("mp4_filename") or "shortform.mp4")),
            ("thumbnail", "media/" + (files.get("thumbnail_filename") or "thumbnail.jpg")),
        ]
        fallback_file_keys = {
            "mp3": "mp3_filename",
            "srt": "srt_filename",
            "mp4": "mp4_filename",
            "thumbnail": "thumbnail_filename",
        }
        for file_kind, arc_name in media_zip_items:
            found = _first_mobile_media_file(media, file_kind, job_dir)
            if not found:
                found = _resolve_mobile_download_file(files.get(fallback_file_keys.get(file_kind, "")), job_dir)
            if found:
                zf.write(found, arc_name)

    buffer.seek(0)
    filename = files.get("zip_filename") or f"storymaker_mobile_{job_id}.zip"
    return StreamingResponse(buffer, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/jobs/{job_id}/files/{file_kind}")
def download_mobile_one_shot_file(
    job_id: str,
    file_kind: str,
    current_user: User = Depends(get_current_user),
):
    result_file = _find_mobile_result_file(job_id, current_user)
    data = json.loads(result_file.read_text(encoding="utf-8"))
    job_dir = result_file.parent
    try:
        data = _sync_podcast_result(data, result_file)
        data = _sync_thumbnail_result(data, result_file)
        data = _sync_shortform_result(data, result_file)
    except Exception:
        pass
    media = data.get("media") or {}

    if file_kind == "text":
        outputs = data.get("outputs") or {}
        text_parts = []
        for key in ["blog", "place", "carrot", "instagram", "podcast50", "podcast80"]:
            value = str(outputs.get(key) or "").strip()
            if value:
                text_parts.append(f"[{key}]\n{value}")
        if not text_parts and data.get("raw_result"):
            text_parts.append(str(data.get("raw_result")))
        content = "\n\n".join(text_parts).strip()
        if not content:
            raise HTTPException(status_code=404, detail="텍스트 결과가 아직 없습니다.")
        buffer = io.BytesIO(content.encode("utf-8"))
        return StreamingResponse(
            buffer,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="storymaker_{job_id}_text.txt"'},
        )

    if file_kind == "images":
        image_dir = job_dir / "images"
        image_files = [path for path in sorted(image_dir.iterdir()) if path.is_file()] if image_dir.exists() else []
        if not image_files:
            for item in data.get("images") or []:
                stored_name = str(item.get("stored_name") or item.get("name") or "").strip() if isinstance(item, dict) else ""
                if not stored_name:
                    continue
                found = _find_output_file_by_name(stored_name, [image_dir, job_dir])
                if found and found not in image_files:
                    image_files.append(found)
        if not image_files:
            raise HTTPException(status_code=404, detail="다운로드할 이미지가 없습니다.")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in image_files:
                zf.write(path, f"images/{path.name}")
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="storymaker_{job_id}_images.zip"'},
        )

    candidates: list[Path] = []
    if file_kind in {"mp3", "srt", "mp4", "thumbnail"}:
        found = _first_mobile_media_file(media, file_kind, job_dir)
        if not found:
            files = _mobile_project_files(data)
            fallback_file_keys = {
                "mp3": "mp3_filename",
                "srt": "srt_filename",
                "mp4": "mp4_filename",
                "thumbnail": "thumbnail_filename",
            }
            found = _resolve_mobile_download_file(files.get(fallback_file_keys.get(file_kind, "")), job_dir)
        if found:
            candidates.append(found)
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 파일 종류입니다.")

    if not candidates:
        raise HTTPException(status_code=404, detail="다운로드할 파일이 아직 없습니다.")
    target = candidates[0]
    return FileResponse(path=target, filename=target.name)


def _request_v1_podcast_cleanup(data: dict[str, Any], job_id: str) -> dict[str, Any]:
    """V1 Windows Podcast API에 작업 산출물 정리를 요청합니다.

    Docker 컨테이너에서는 Windows F: 드라이브에 직접 접근할 수 없으므로
    host.docker.internal의 V1 전용 Podcast API가 물리 파일을 삭제합니다.
    """
    media = data.get("media") or {}
    project_keys = []
    for value in (
        data.get("source_job_id"),
        data.get("archive_group_key"),
        media.get("project_key"),
        (data.get("pipeline") or {}).get("latest_external_job_id"),
    ):
        value = str(value or "").strip()
        if value and value not in project_keys:
            project_keys.append(value)
    payload = {
        "archive_job_id": str(job_id),
        "podcast_job_id": str(media.get("podcast_job_id") or ""),
        "project_keys": project_keys,
        "purge_shared_cache": True,
    }
    api_url = os.getenv("PODCAST_API_URL", "http://host.docker.internal:8003").rstrip("/")
    api_key = os.getenv("SUPERTONIC_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = httpx.request(
            "DELETE",
            f"{api_url}/api/podcast/archive-files",
            json=payload,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
        return result if isinstance(result, dict) else {"ok": True}
    except Exception as exc:
        logger.warning("V1 podcast cleanup failed for %s: %s", job_id, exc)
        return {"ok": False, "error": str(exc)[:300]}


@router.delete("/jobs/{job_id}")
def delete_mobile_one_shot_job_api(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_supported_mobile_job_id(job_id):
        raise HTTPException(status_code=400, detail="job_id 형식이 올바르지 않습니다.")
    result_file = None
    result_file_from_db = False
    db_path = get_mobile_one_shot_result_path(job_id, current_user.id)
    if db_path:
        candidate = Path(db_path)
        if candidate.exists():
            result_file = candidate
            result_file_from_db = True
    if result_file is None:
        base = _output_root() / "mobile_one_shot"
        matches = list(base.glob(f"*/{job_id}/result.json")) if base.exists() else []
        if matches:
            result_file = matches[0]
    deleted_file = False
    cleanup_result: dict[str, Any] = {"ok": True, "deleted_count": 0}
    if result_file and result_file.exists():
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            owner_matches = str(data.get("user_bucket")) == str(current_user.id)
            if not owner_matches and not result_file_from_db:
                raise HTTPException(status_code=404, detail="삭제할 작업을 찾을 수 없습니다.")
            cleanup_result = _request_v1_podcast_cleanup(data, job_id)
            if not cleanup_result.get("ok"):
                raise HTTPException(status_code=502, detail="Podcast/Supertonic 파일 정리에 실패했습니다.")
            job_dir = result_file.parent
            allowed_root = (_output_root() / "mobile_one_shot").resolve()
            resolved_job_dir = job_dir.resolve()
            if allowed_root not in resolved_job_dir.parents:
                raise HTTPException(status_code=500, detail="삭제 경로 안전성 검증에 실패했습니다.")
            shutil.rmtree(resolved_job_dir, ignore_errors=False)
            deleted_file = not resolved_job_dir.exists()
            if not deleted_file:
                raise HTTPException(status_code=500, detail="작업 폴더 삭제에 실패했습니다.")
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("V1 archive physical delete failed: %s", job_id)
            raise HTTPException(status_code=500, detail=f"실제 파일 삭제에 실패했습니다: {str(exc)[:160]}")

    # 실제 파일 삭제가 성공한 뒤에만 관련 자산 DB와 보관함 DB를 제거합니다.
    db.execute(
        text("DELETE FROM content_archive_assets WHERE archive_job_id = :job_id AND user_id = :user_id"),
        {"job_id": job_id, "user_id": current_user.id},
    )
    db.commit()
    deleted_db = delete_mobile_one_shot_job(job_id, current_user.id)
    if not deleted_db and not deleted_file:
        raise HTTPException(status_code=404, detail="삭제할 작업을 찾을 수 없습니다.")
    logger.info("V1 archive physically deleted: job=%s cleanup=%s", job_id, cleanup_result)
    return {
        "ok": True,
        "job_id": job_id,
        "deleted_db": deleted_db,
        "deleted_file": deleted_file,
        "podcast_cleanup": cleanup_result,
    }


@router.get("/library")
def list_mobile_one_shot_jobs(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    safe_limit = max(1, min(int(limit or 10), 10))
    safe_offset = max(0, int(offset or 0))
    base = _output_root() / "mobile_one_shot"
    results: list[dict[str, Any]] = []
    user_bucket = str(current_user.id)
    seen_job_ids: set[str] = set()

    for row in list_mobile_one_shot_job_summaries(current_user.id, safe_limit, safe_offset):
        job_id = str(row.get("job_id") or "").strip()
        if not job_id:
            continue
        seen_job_ids.add(job_id)
        memo = str(row.get("memo") or "").strip()
        row_data: dict[str, Any] = {}
        row_file: Optional[Path] = None
        row_result_path = str(row.get("result_path") or "").strip()
        if row_result_path:
            try:
                row_file = Path(row_result_path)
                if not row_file.exists():
                    continue
                row_data = json.loads(row_file.read_text(encoding="utf-8"))
            except Exception:
                row_data = {}
        if str(row_data.get("status") or "").lower() == "deleted" or row_data.get("deleted_at"):
            continue
        if not _mobile_archive_has_content(row_data):
            continue
        row_persona = _archive_persona_from_data(row_data) if row_data else None
        title = _mobile_job_title(row_data) if row_data else (memo[:80] if memo else job_id)
        results.append({
            "job_id": job_id,
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "memo_length": len(memo),
            "image_count": row.get("image_count") or row_data.get("image_count") or 0,
            "keywords": row_data.get("keywords", [])[:5] if row_data else [],
            "persona": row_persona,
            "title": title,
            "media": row_data.get("media") or {},
            "files": _mobile_project_files(row_data or {"job_id": job_id, "media": {}}),
            "file_urls": _mobile_download_file_urls(job_id, row_data, row_file.parent if row_file else None),
            "download_url": f"/api/mobile/one-shot/jobs/{job_id}/download" if _mobile_download_zip_has_files(row_data, row_file.parent if row_file else None) else None,
        })
    seen_paths: set[str] = set()
    for db_path in list_mobile_one_shot_result_paths(current_user.id, safe_limit):
        result_file = Path(db_path)
        if not result_file.exists():
            continue
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            if str(data.get("user_bucket")) != user_bucket:
                continue
            if str(data.get("status") or "").lower() == "deleted" or data.get("deleted_at"):
                continue
            if not _mobile_archive_has_content(data):
                continue
            result_job_id = str(data.get("job_id") or "").strip()
            if result_job_id and result_job_id in seen_job_ids:
                seen_paths.add(str(result_file))
                continue
            results.append({
                "job_id": data.get("job_id"),
                "status": data.get("status"),
                "created_at": data.get("created_at"),
                "memo_length": data.get("memo_length"),
                "image_count": data.get("image_count"),
                "keywords": data.get("keywords", [])[:5],
                "persona": _archive_persona_from_data(data),
                "title": _mobile_job_title(data),
                "media": data.get("media"),
                "files": _mobile_project_files(data),
                "file_urls": _mobile_download_file_urls(str(data.get("job_id") or ""), data, result_file.parent),
                "download_url": f"/api/mobile/one-shot/jobs/{data.get('job_id')}/download" if _mobile_download_zip_has_files(data, result_file.parent) else None,
            })
            seen_paths.add(str(result_file))
            if result_job_id:
                seen_job_ids.add(result_job_id)
        except Exception:
            continue
    if base.exists():
        for result_file in sorted(base.glob("*/mob-*/result.json"), reverse=True):
            if str(result_file) in seen_paths:
                continue
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                if str(data.get("user_bucket")) != user_bucket:
                    continue
                if str(data.get("status") or "").lower() == "deleted" or data.get("deleted_at"):
                    continue
                if not _mobile_archive_has_content(data):
                    continue
                result_job_id = str(data.get("job_id") or "").strip()
                if result_job_id and result_job_id in seen_job_ids:
                    continue
                results.append({
                    "job_id": data.get("job_id"),
                    "status": data.get("status"),
                    "created_at": data.get("created_at"),
                    "memo_length": data.get("memo_length"),
                    "image_count": data.get("image_count"),
                    "keywords": data.get("keywords", [])[:5],
                    "persona": _archive_persona_from_data(data),
                    "title": _mobile_job_title(data),
                    "media": data.get("media"),
                    "files": _mobile_project_files(data),
                    "file_urls": _mobile_download_file_urls(str(data.get("job_id") or ""), data, result_file.parent),
                    "download_url": f"/api/mobile/one-shot/jobs/{data.get('job_id')}/download" if _mobile_download_zip_has_files(data, result_file.parent) else None,
                })
            except Exception:
                continue
            if result_job_id:
                seen_job_ids.add(result_job_id)
            if len(results) >= max(safe_limit * 2, safe_limit + 5):
                break
    results.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"ok": True, "count": len(results), "items": results[:safe_limit]}
