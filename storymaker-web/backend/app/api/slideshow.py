import asyncio
import httpx
import os
import json
import uuid
import re
from pathlib import Path, PureWindowsPath
from datetime import datetime
from urllib.parse import quote
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Response, UploadFile, Request
from fastapi.responses import FileResponse
from app.api.auth import get_current_user
from app.api.podcast import API_URL, upstream_headers, upstream_error
from sqlalchemy.orm import Session
from app.db.models import IndustryPromptTemplate, User, UserPersona
from app.db.database import get_db
from app.services.common_archive_service import register_common_archive
from app.services.project_asset_service import save_project_asset, to_editor_asset_response

router = APIRouter()
SLIDESHOW_CLEANUP_TOKENS: dict[str, dict[str, str]] = {}
_SLIDESHOW_SUBMISSION_CACHE: dict[str, dict] = {}

def _resolve_exact_podcast_audio(audio_project_key: str) -> tuple[str, str]:
    key = str(audio_project_key or "").strip()
    if not re.fullmatch(r"storymaker_main_\d{14}", key):
        raise HTTPException(status_code=400, detail="audio_project_key 형식이 올바르지 않습니다.")
    try:
        response = httpx.get(
            f"{API_URL}/api/audio/list",
            headers=upstream_headers(),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)
    items = payload if isinstance(payload, list) else payload.get("items", [])
    matches = [
        item for item in items
        if isinstance(item, dict) and str(item.get("project_key") or "").strip() == key
    ]
    if len(matches) != 1:
        raise HTTPException(
            status_code=409,
            detail="현재 작업의 MP3를 정확히 한 건으로 찾지 못했습니다.",
        )
    mp3_path = str(matches[0].get("path") or "").strip()
    parsed_path = PureWindowsPath(mp3_path) if "\\" in mp3_path else Path(mp3_path)
    if not mp3_path or parsed_path.suffix.lower() != ".mp3" or parsed_path.stem != key:
        raise HTTPException(status_code=409, detail="현재 작업 ID와 MP3 파일 ID가 일치하지 않습니다.")
    return mp3_path, str(parsed_path.with_suffix(".srt"))

def _media_filename(url: str) -> str:
    return url.rsplit("?", 1)[0].rstrip("/").split("/")[-1]

def _media_url(url: str, preview: bool = False) -> str:
    filename = quote(_media_filename(url), safe="")
    suffix = "?preview=true" if preview else ""
    return f"/api/slideshow/media/{filename}{suffix}"


def _extract_keyword_text(text: str, limit: int = 12) -> str:
    raw = str(text or "")
    tags = re.findall(r"#([^\s#,.，]+)", raw)
    words = re.split(r"[,#\n\r\t|/]+", raw)
    result: list[str] = []
    for item in [*tags, *words]:
        cleaned = re.sub(r"\s+", " ", str(item or "").strip())
        cleaned = re.sub(r"^[\-:;·•]+|[\-:;·•]+$", "", cleaned).strip()
        if not cleaned or cleaned.isdigit() or len(cleaned) < 2 or len(cleaned) > 24:
            continue
        if re.fullmatch(r"\d{2,4}-\d{3,4}-\d{4}", cleaned):
            continue
        if cleaned not in result:
            result.append(cleaned)
        if len(result) >= limit:
            break
    return ", ".join(result)


def _load_content_text(root: Path, content_id: str | None = None, content_path: str | None = None) -> str:
    test_result_dir = root / "test_result_packages"
    candidates: list[Path] = []
    if content_id:
        candidates.append(test_result_dir / content_id / "result_package.json")
    if content_path:
        p = Path(content_path)
        candidates.append(p / "result_package.json" if p.is_dir() else p)
    for path in candidates:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return str(data.get("result_text") or "")
        except Exception:
            continue
    return ""


def _keyword_sources(db: Session, user: User, *, root: Path, project_key: str = "", title: str = "", content_id: str | None = None, content_path: str | None = None, text_hint: str = "") -> dict[str, str]:
    content_text = _load_content_text(root, content_id, content_path)
    prompt_keywords = _extract_keyword_text("\n".join([text_hint or "", content_text]))
    project_keywords = _extract_keyword_text(", ".join([title or "", project_key or ""]))
    user_keywords = ""
    industry_keywords = ""
    try:
        persona = db.query(UserPersona).filter(UserPersona.user_id == user.id).order_by(UserPersona.is_default.desc(), UserPersona.updated_at.desc()).first()
        if persona:
            try:
                user_keywords = ", ".join(json.loads(persona.keywords_json or "[]"))
            except Exception:
                user_keywords = ""
            industry_key = getattr(persona, "industry_key", "") or ""
            if industry_key:
                tmpl = db.query(IndustryPromptTemplate).filter(IndustryPromptTemplate.industry_key == industry_key).first()
                if tmpl:
                    industry_keywords = tmpl.keyword_hint or ""
    except Exception:
        pass
    return {
        "prompt_keywords": prompt_keywords,
        "project_keywords": project_keywords,
        "user_keywords": user_keywords,
        "industry_keywords": industry_keywords,
    }


def _prepare_slideshow_result(data: dict, user: User) -> dict:
    result = data.get("result") or {}
    mp4_url = (
        result.get("mp4_url")
        or result.get("download_url")
        or result.get("video_url")
        or result.get("output_url")
        or result.get("file_url")
        or data.get("mp4_url")
        or data.get("download_url")
        or data.get("video_url")
        or data.get("output_url")
        or data.get("file_url")
    )
    import re
    log_lines = data.get("log") or result.get("log") or []
    if isinstance(log_lines, str):
        log_lines = [log_lines]
    joined_log = "\n".join(str(x) for x in log_lines)
    final_match = re.search(r"SUCCESS:\s*Output file generated at\s+([^\s]+\.mp4)", joined_log)
    if final_match:
        # 렌더 서버가 중간 산출물 URL을 result.mp4_url로 주더라도,
        # 실제 회수 완료된 최종 파일을 최우선으로 사용합니다.
        mp4_url = final_match.group(1)
    elif not mp4_url:
        matches = re.findall(r"([^\s/\\]+\.mp4)", joined_log)
        if matches:
            preferred = [m for m in matches if "slideshow" in m.lower() or "guest_" in m.lower() or "_팟캐스트_" in m]
            mp4_url = preferred[-1] if preferred else matches[-1]
    if not mp4_url:
        return data

    proxy_url = _media_url(mp4_url)
    preview_url = _media_url(mp4_url, preview=True)
    result["mp4_url"] = proxy_url
    result["download_url"] = proxy_url
    result["video_url"] = proxy_url
    result["preview_mp4_url"] = preview_url
    result["anchor_tag"] = "[VIDEO_SHORTFORM]"
    result["preview_url"] = preview_url

    job_id = str(data.get("job_id") or "")
    if job_id:
        token_data = SLIDESHOW_CLEANUP_TOKENS.setdefault(job_id, {
            "user_id": str(user.id),
            "token": uuid.uuid4().hex,
        })
        result["cleanup_token"] = token_data["token"]
        data["cleanup_token"] = token_data["token"]

    data["result"] = result
    return data

def _validate_cleanup_token(job_id: str, cleanup_token: str, user: User | None = None) -> None:
    token_data = SLIDESHOW_CLEANUP_TOKENS.get(job_id)
    if not token_data or token_data.get("token") != cleanup_token:
        raise HTTPException(status_code=403, detail="Invalid cleanup token")
    if user is not None and token_data.get("user_id") != str(user.id):
        raise HTTPException(status_code=403, detail="Cleanup job owner mismatch")

def _cleanup_upstream(job_id: str, cleanup_token: str, reason: str) -> dict:
    payload = {"cleanup_token": cleanup_token, "reason": reason}
    for path in (
        f"/api/slideshow/jobs/{quote(job_id, safe='')}/cleanup",
        f"/api/jobs/{quote(job_id, safe='')}/cleanup",
    ):
        response = httpx.post(f"{API_URL}{path}", json=payload, headers=upstream_headers(), timeout=20)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"ok": True, "deleted": [], "missing": [], "reason": reason}
    return {
        "ok": False,
        "deleted": [],
        "missing": [],
        "reason": reason,
        "detail": "Upstream cleanup endpoint is not available",
    }

def _thumbnail_cover(image, target_size: tuple[int, int]):
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


def _make_thumbnail_collage(image_paths: list[Path], output_path: Path) -> Path:
    from PIL import Image
    canvas_w, canvas_h = 1080, 1920
    gap = 16
    bg = "#111111"

    canvas = Image.new("RGB", (canvas_w, canvas_h), bg)

    top_h = 980
    bottom_h = canvas_h - top_h - (gap * 3)
    top_box = (gap, gap, canvas_w - gap, gap + top_h)
    left_box = (gap, top_box[3] + gap, (canvas_w // 2) - (gap // 2), top_box[3] + gap + bottom_h)
    right_box = ((canvas_w // 2) + (gap // 2), top_box[3] + gap, canvas_w - gap, top_box[3] + gap + bottom_h)

    boxes = [top_box, left_box, right_box]
    selected = image_paths[:3]

    for idx, img_path in enumerate(selected):
        if idx >= len(boxes):
            break
        box = boxes[idx]
        x1, y1, x2, y2 = box
        target_size = (x2 - x1, y2 - y1)
        with Image.open(img_path) as src:
            fitted = _thumbnail_cover(src, target_size)
            canvas.paste(fitted, (x1, y1))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="JPEG", quality=88, optimize=True)
    return output_path


def _prepare_video_safe_upload(content: bytes, original_name: str, content_type: str, safe_dir: Path, index: int) -> tuple[str, bytes, str]:
    try:
        from io import BytesIO
        from PIL import Image, ImageOps
        if not content or len(content) < 1024:
            return original_name, content, content_type
        safe_dir.mkdir(parents=True, exist_ok=True)
        target = safe_dir / f"video_image_{index:03d}.jpg"
        with Image.open(BytesIO(content)) as probe:
            probe.verify()
        with Image.open(BytesIO(content)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", image.size, (255, 255, 255))
                bg.paste(image, mask=image.getchannel("A"))
                image = bg
            else:
                image = image.convert("RGB")
            width, height = image.size
            if width < 64 or height < 64:
                return original_name, content, content_type
            scale = min(1.0, 1920 / max(width, height))
            if scale < 1.0:
                image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.LANCZOS)
            image.save(target, format="JPEG", quality=92, optimize=True, progressive=False)
        if target.exists() and target.stat().st_size > 10 * 1024:
            return target.name, target.read_bytes(), "image/jpeg"
    except Exception:
        return original_name, content, content_type
    return original_name, content, content_type


async def _read_uploads_parallel(images: list[UploadFile], limit: int | None = None) -> list[tuple[int, UploadFile, bytes, str, str]]:
    """업로드 파일 바이트를 먼저 병렬 수집해 렌더 요청 대기 시간을 줄입니다.

    DB Session은 스레드 안전하지 않으므로 DB 저장은 기존 요청 흐름 안에서 처리하고,
    순수 I/O인 UploadFile.read만 asyncio.gather로 앞당깁니다.
    """
    selected = list(images[:limit] if limit else images)

    async def read_one(idx: int, image: UploadFile) -> tuple[int, UploadFile, bytes, str, str]:
        return (
            idx,
            image,
            await image.read(),
            image.filename or f"image_{idx}.jpg",
            image.content_type or "application/octet-stream",
        )

    return await asyncio.gather(*(read_one(idx, image) for idx, image in enumerate(selected, start=1)))

@router.get("/slideshow/pc-thumbnail/{source_job_id}")
def slideshow_pc_thumbnail_compat(source_job_id: str):
    root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    mobile_root = root / "mobile_one_shot"
    if mobile_root.exists():
        for result_file in sorted(mobile_root.glob("*/mob-*/result.json"), reverse=True):
            try:
                raw_text = result_file.read_text(encoding="utf-8")
                data = json.loads(raw_text)
            except Exception:
                continue
            pipeline = data.get("pipeline") or {}
            candidates = {
                str(data.get("job_id") or ""),
                str(data.get("source_job_id") or ""),
                str(data.get("archive_group_key") or ""),
                str(pipeline.get("source_job_id") or ""),
                str(pipeline.get("archive_group_key") or ""),
            }
            if source_job_id not in candidates and source_job_id not in raw_text:
                continue
            media = data.get("media") or {}
            for value in (media.get("thumbnail_path"), media.get("thumbnail_url")):
                if not value:
                    continue
                path = Path(str(value).split("?", 1)[0])
                if not path.is_absolute() and str(value).startswith("/data/output_results/"):
                    path = root / str(value).replace("/data/output_results/", "", 1)
                if path.exists() and path.is_file():
                    suffix = path.suffix.lower()
                    media_type = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".webp": "image/webp",
                    }.get(suffix, "application/octet-stream")
                    return FileResponse(
                        path,
                        media_type=media_type,
                        content_disposition_type="inline",
                        headers={
                            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                            "Pragma": "no-cache",
                            "Expires": "0",
                            "Content-Disposition": f'inline; filename="{path.name}"',
                        },
                    )
    # Gemini Worker가 저장한 전용 썸네일 결과에서도 원본 StoryMaker 작업 ID를 찾는다.
    result_root = root / "test_result_packages"
    if result_root.exists():
        nearest: tuple[float, Path] | None = None
        source_dt = None
        source_match = re.fullmatch(r"storymaker_main_(\d{14})", source_job_id)
        if source_match:
            try:
                source_dt = datetime.strptime(source_match.group(1), "%Y%m%d%H%M%S")
            except ValueError:
                source_dt = None
        for result_json in sorted(result_root.glob("thumbnail_*/reels_thumbnail_url.json"), reverse=True):
            try:
                payload = json.loads(result_json.read_text(encoding="utf-8"))
            except Exception:
                continue
            linked_id = str(payload.get("source_job_id") or "").strip()
            image_url = str(payload.get("final_image_url") or payload.get("image_url") or "").strip()
            image_path = None
            if image_url.startswith("/data/output_results/"):
                image_path = root / image_url.replace("/data/output_results/", "", 1)
            elif image_url:
                candidate = Path(image_url.split("?", 1)[0])
                if candidate.is_absolute():
                    image_path = candidate
            if not image_path or not image_path.exists() or not image_path.is_file():
                continue
            if linked_id == source_job_id:
                return FileResponse(image_path, media_type="image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png", filename=image_path.name)
            if source_dt:
                thumb_match = re.fullmatch(r"thumbnail_(\d{8})_(\d{6})_mobile", result_json.parent.name)
                if thumb_match:
                    try:
                        thumb_dt = datetime.strptime(thumb_match.group(1) + thumb_match.group(2), "%Y%m%d%H%M%S")
                        delta = abs((thumb_dt - source_dt).total_seconds())
                        if delta <= 600 and (nearest is None or delta < nearest[0]):
                            nearest = (delta, image_path)
                    except ValueError:
                        pass
        if nearest:
            image_path = nearest[1]
            return FileResponse(image_path, media_type="image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png", filename=image_path.name)
    raise HTTPException(status_code=404, detail="thumbnail not found")


@router.get("/slideshow/health")
def slideshow_health():
    try:
        response = httpx.get(f"{API_URL}/health", timeout=5)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)

@router.get("/slideshow/audio-list")
def slideshow_audio_list(_: User = Depends(get_current_user)):
    try:
        response = httpx.get(f"{API_URL}/api/audio/list", headers=upstream_headers(), timeout=20)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)


@router.post("/slideshow/run")
async def run_slideshow(
    project_key: str = Form(...),
    project_id: int | None = Form(None),
    mp3_path: str = Form(...),
    srt_path: str = Form(""),
    audio_project_key: str = Form(""),
    brand_name: str = Form(""),
    phone_number: str = Form(""),
    brand_size: int = Form(46),
    phone_size: int = Form(43),
    margin_bottom: int = Form(80),
    box_enabled: bool = Form(True),
    stroke_enabled: bool = Form(True),
    shadow_enabled: bool = Form(True),
    image_sec: float = Form(2.0),
    transition_sec: float = Form(0.8),
    zoom_intensity: float = Form(0.004),
    subtitle_enabled: bool = Form(True),
    subtitle_font_size: int = Form(11),
    subtitle_margin: int = Form(40),
    mm_sub_lift: int = Form(95),
    images: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    resolution: str = Form("1080x1920"),
    fps: int = Form(24),
    nvenc_preset: str = Form("p3"),
    render_target: str = Form("macmini"),
):
    try:
        data = {
            "user_id": str(user.id),
            "project_key": project_key,
            "mp3_path": mp3_path,
            "srt_path": srt_path or "",
            "brand_name": brand_name,
            "phone_number": phone_number,
            "brand_size": str(brand_size),
            "phone_size": str(phone_size),
            "margin_bottom": str(margin_bottom),
            "box_enabled": str(box_enabled).lower(),
            "stroke_enabled": str(stroke_enabled).lower(),
            "shadow_enabled": str(shadow_enabled).lower(),
            "image_sec": str(image_sec),
            "transition_sec": str(transition_sec),
            "zoom_intensity": str(zoom_intensity),
            "subtitle_enabled": str(subtitle_enabled).lower(),
            "subtitle_font_size": str(subtitle_font_size),
            "subtitle_margin": str(subtitle_margin),
            "mm_sub_lift": str(mm_sub_lift),
            "resolution": resolution,
            "fps": str(fps),
            "nvenc_preset": nvenc_preset,
            "render_target": render_target if render_target in ["macmini", "dell"] else "macmini",
        }
        files = []
        project_assets = []
        root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
        keyword_sources = _keyword_sources(db, user, root=root, project_key=project_key, title=brand_name)
        safe_image_dir = root / "test_slideshow_safe_images" / uuid.uuid4().hex
        for idx, image, content, original_name, content_type in await _read_uploads_parallel(images):
            asset = save_project_asset(
                db=db,
                user_id=user.id,
                username=getattr(user, "username", "") or "",
                project_id=project_id,
                project_key=project_key,
                file_bytes=content,
                original_filename=original_name,
                asset_type="image",
                role="GENERAL",
                company_name=brand_name or project_key,
                keyword=project_key,
                prompt_keywords=keyword_sources["prompt_keywords"],
                project_keywords=keyword_sources["project_keywords"],
                user_keywords=keyword_sources["user_keywords"],
                industry_keywords=keyword_sources["industry_keywords"],
                mime_type=content_type,
                source="SLIDESHOW",
                sequence=idx,
                display_order=idx,
            )
            renderer_name = asset.get("stored_filename") or original_name
            safe_name, safe_content, safe_type = _prepare_video_safe_upload(content, renderer_name, content_type, safe_image_dir, idx)
            if safe_name == renderer_name:
                continue
            files.append(("images", (safe_name, safe_content, safe_type)))
            project_assets.append(to_editor_asset_response(asset))
        if not files:
            raise HTTPException(status_code=400, detail="영상 생성에 사용할 수 있는 안전 이미지가 없습니다. JPG 또는 PNG 이미지를 다시 업로드해 주세요.")

        db.commit()
        response = httpx.post(f"{API_URL}/api/slideshow/run", data=data, files=files, headers=upstream_headers(), timeout=120)
        response.raise_for_status()
        upstream_data = response.json()
        slideshow_job_id = str(upstream_data.get("job_id") or upstream_data.get("id") or "").strip()
        archive_group_key = str(data.get("archive_group_key") or data.get("source_job_id") or project_key or "").strip()
        if slideshow_job_id and archive_group_key.startswith("storymaker_main_"):
            register_common_archive(
                user_id=current_user.id,
                source="shortform",
                source_job_id=slideshow_job_id,
                archive_group_key=archive_group_key,
                title=str(data.get("title") or project_key or slideshow_job_id),
                media={
                    "status": "shortform_submitted",
                    "slideshow_job_id": slideshow_job_id,
                    "project_key": project_key,
                },
                extra={"slideshow_job": upstream_data},
            )
        return {**upstream_data, "project_key": project_key, "assets": project_assets, "project_assets": project_assets}
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)


@router.post("/slideshow/create")
async def create_slideshow(
    project_key: str = Form(...),
    project_id: int | None = Form(None),
    mp3_path: str = Form(...),
    srt_path: str = Form(""),
    audio_project_key: str = Form(""),
    brand_name: str = Form(""),
    phone_number: str = Form(""),
    brand_size: int = Form(46),
    phone_size: int = Form(43),
    margin_bottom: int = Form(80),
    box_enabled: bool = Form(True),
    stroke_enabled: bool = Form(True),
    shadow_enabled: bool = Form(True),
    image_sec: float = Form(2.0),
    transition_sec: float = Form(0.8),
    zoom_intensity: float = Form(0.004),
    subtitle_enabled: bool = Form(True),
    subtitle_font_size: int = Form(11),
    subtitle_margin: int = Form(40),
    mm_sub_lift: int = Form(95),
    images: list[UploadFile] = File(...),
    content_id: str = Form(None),
    content_path: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    resolution: str = Form("1080x1920"),
    fps: int = Form(24),
    nvenc_preset: str = Form("p3"),
    render_target: str = Form("macmini"),
):
    try:
        exact_key = str(audio_project_key or "").strip()
        if exact_key:
            mp3_path, srt_path = _resolve_exact_podcast_audio(exact_key)
            project_key = exact_key
        dedupe_key = f"{user.id}:{exact_key or project_key}"
        now_ts = datetime.now().timestamp()
        cached = _SLIDESHOW_SUBMISSION_CACHE.get(dedupe_key)
        if cached and now_ts - float(cached.get("at") or 0) < 120:
            return dict(cached.get("response") or {})
        data = {
            "user_id": str(user.id),
            "project_key": project_key,
            "mp3_path": mp3_path,
            "srt_path": srt_path or "",
            "brand_name": brand_name,
            "phone_number": phone_number,
            "brand_size": str(brand_size),
            "phone_size": str(phone_size),
            "margin_bottom": str(margin_bottom),
            "box_enabled": str(box_enabled).lower(),
            "stroke_enabled": str(stroke_enabled).lower(),
            "shadow_enabled": str(shadow_enabled).lower(),
            "image_sec": str(image_sec),
            "transition_sec": str(transition_sec),
            "zoom_intensity": str(zoom_intensity),
            "subtitle_enabled": str(subtitle_enabled).lower(),
            "subtitle_font_size": str(subtitle_font_size),
            "subtitle_margin": str(subtitle_margin),
            "mm_sub_lift": str(mm_sub_lift),
            "resolution": resolution,
            "fps": str(fps),
            "nvenc_preset": nvenc_preset,
            "render_target": render_target if render_target in ["macmini", "dell"] else "macmini",
            "content_id": content_id or "",
            "content_path": content_path or "",
        }
        files = []
        project_assets = []
        root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
        keyword_sources = _keyword_sources(db, user, root=root, project_key=project_key, title=brand_name, content_id=content_id, content_path=content_path)
        safe_image_dir = root / "test_slideshow_safe_images" / uuid.uuid4().hex
        for idx, image, content, original_name, content_type in await _read_uploads_parallel(images):
            asset = save_project_asset(
                db=db,
                user_id=user.id,
                username=getattr(user, "username", "") or "",
                project_id=project_id,
                project_key=project_key,
                file_bytes=content,
                original_filename=original_name,
                asset_type="image",
                role="GENERAL",
                company_name=brand_name or project_key,
                keyword=project_key,
                prompt_keywords=keyword_sources["prompt_keywords"],
                project_keywords=keyword_sources["project_keywords"],
                user_keywords=keyword_sources["user_keywords"],
                industry_keywords=keyword_sources["industry_keywords"],
                mime_type=content_type,
                source="SLIDESHOW",
                sequence=idx,
                display_order=idx,
            )
            renderer_name = asset.get("stored_filename") or original_name
            safe_name, safe_content, safe_type = _prepare_video_safe_upload(content, renderer_name, content_type, safe_image_dir, idx)
            if safe_name == renderer_name:
                continue
            files.append(("images", (safe_name, safe_content, safe_type)))
            project_assets.append(to_editor_asset_response(asset))
        if not files:
            raise HTTPException(status_code=400, detail="영상 생성에 사용할 수 있는 안전 이미지가 없습니다. JPG 또는 PNG 이미지를 다시 업로드해 주세요.")

        db.commit()
        response = httpx.post(f"{API_URL}/api/slideshow/run", data=data, files=files, headers=upstream_headers(), timeout=120)
        response.raise_for_status()
        upstream_data = response.json()
        slideshow_job_id = str(upstream_data.get("job_id") or upstream_data.get("id") or "").strip()
        archive_group_key = str(data.get("archive_group_key") or data.get("source_job_id") or project_key or "").strip()
        if slideshow_job_id and archive_group_key.startswith("storymaker_main_"):
            register_common_archive(
                user_id=user.id,
                source="shortform",
                source_job_id=slideshow_job_id,
                archive_group_key=archive_group_key,
                title=str(data.get("title") or project_key or slideshow_job_id),
                media={
                    "status": "shortform_submitted",
                    "slideshow_job_id": slideshow_job_id,
                    "project_key": project_key,
                },
                extra={"slideshow_job": upstream_data},
            )
        final_response = {**upstream_data, "project_key": project_key, "audio_project_key": exact_key or project_key, "assets": project_assets, "project_assets": project_assets}
        _SLIDESHOW_SUBMISSION_CACHE[dedupe_key] = {"at": now_ts, "response": dict(final_response)}
        return final_response
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)


@router.get("/slideshow/contents")
def get_slideshow_contents(_: User = Depends(get_current_user)):
    """최근 생성된 콘텐츠 패키지 목록을 가져옵니다. (최대 10개)"""
    try:
        root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
        test_result_dir = root / "test_result_packages"
        if not test_result_dir.exists():
            return {"ok": True, "data": []}
            
        packages = []
        for p in test_result_dir.iterdir():
            if p.is_dir() and not p.name.startswith("thumbnail_"):
                pkg_json = p / "result_package.json"
                if pkg_json.exists():
                    try:
                        data = json.loads(pkg_json.read_text(encoding="utf-8"))
                        packages.append({
                            "content_id": p.name,
                            "content_path": str(pkg_json),
                            "project_title": data.get("project_title") or "새 프로젝트",
                            "created_at": data.get("created_at") or "",
                            "result_text": data.get("result_text") or "",
                        })
                    except Exception:
                        pass
                        
        packages.sort(key=lambda x: x["created_at"] or x["content_id"], reverse=True)
        return {"ok": True, "data": packages[:10]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slideshow/thumbnail-start")
async def slideshow_thumbnail_start(
    project_title: str = Form("슬라이드쇼 썸네일"),
    instagram_text: str = Form(""),
    content_id: str = Form(None),
    content_path: str = Form(None),
    images: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    now = datetime.now()
    job_id = "thumbnail_" + now.strftime("%Y%m%d_%H%M%S") + "_" + str(user.id)
    job_dir = root / "test_thumbnail_jobs" / job_id
    input_dir = job_dir / "input_images"
    input_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    collage_sources = []
    project_assets = []
    safe_project_key = project_title or job_id
    keyword_sources = _keyword_sources(db, user, root=root, project_key=safe_project_key, title=project_title, content_id=content_id, content_path=content_path, text_hint=instagram_text)
    for idx, image in enumerate(images[:3], start=1):
        content = await image.read()
        original_name = image.filename or f"image_{idx}.jpg"
        content_type = image.content_type or "application/octet-stream"
        asset = save_project_asset(
            db=db,
            user_id=user.id,
            username=getattr(user, "username", "") or "",
            project_key=safe_project_key,
            file_bytes=content,
            original_filename=original_name,
            asset_type="image",
            role="THUMBNAIL",
            company_name=project_title,
            keyword=project_title,
            prompt_keywords=keyword_sources["prompt_keywords"],
            project_keywords=keyword_sources["project_keywords"],
            user_keywords=keyword_sources["user_keywords"],
            industry_keywords=keyword_sources["industry_keywords"],
            mime_type=content_type,
            source="THUMBNAIL",
            sequence=idx,
            display_order=idx,
        )
        target = input_dir / (asset.get("stored_filename") or original_name)
        target.write_bytes(content)
        collage_sources.append(target)
        project_assets.append(to_editor_asset_response(asset))
        saved.append({
            "name": target.name,
            "url": f"/data/output_results/test_thumbnail_jobs/{job_id}/input_images/{target.name}",
            "size": len(content),
            "anchor_tag": project_assets[-1]["anchor_tag"],
            "preview_url": project_assets[-1]["preview_url"],
            "asset": project_assets[-1],
        })
    db.commit()

    collage_path = input_dir / "collage_reference.jpg"
    collage_asset = None
    collage_url = None

    collage_error = None
    if collage_sources:
        try:
            _make_thumbnail_collage(collage_sources, collage_path)
            collage_bytes = collage_path.read_bytes()

            collage_asset = save_project_asset(
                db=db,
                user_id=user.id,
                username=getattr(user, "username", "") or "",
                project_key=safe_project_key,
                file_bytes=collage_bytes,
                original_filename="collage_reference.jpg",
                asset_type="image",
                role="THUMBNAIL_COLLAGE",
                company_name=project_title,
                keyword=project_title,
                prompt_keywords=keyword_sources["prompt_keywords"],
                project_keywords=keyword_sources["project_keywords"],
                user_keywords=keyword_sources["user_keywords"],
                industry_keywords=keyword_sources["industry_keywords"],
                mime_type="image/jpeg",
                source="THUMBNAIL",
                sequence=99,
                display_order=99,
            )
            db.commit()

            collage_url = f"/data/output_results/test_thumbnail_jobs/{job_id}/input_images/{collage_path.name}"
        except Exception as exc:
            collage_error = str(exc)[:300]
            collage_asset = None
            collage_url = None

    if collage_url:
        image_lines = "- 콜라주 참고 이미지: " + collage_url
    else:
        image_lines = "\n".join(["- " + item["url"] for item in saved])

    instagram_post = ""
    business_name = ""
    phone = ""
    keywords = ""

    latest_result_package_path = None
    test_result_dir = root / "test_result_packages"
    
    if content_id:
        target_path = test_result_dir / content_id / "result_package.json"
        if target_path.exists():
            latest_result_package_path = target_path
    elif content_path:
        target_path = Path(content_path)
        if target_path.exists():
            if target_path.is_dir():
                target_path = target_path / "result_package.json"
            if target_path.exists():
                latest_result_package_path = target_path

    if not latest_result_package_path and test_result_dir.exists():
        try:
            packages = []
            for p in test_result_dir.iterdir():
                if p.is_dir() and not p.name.startswith("thumbnail_"):
                    pkg_json = p / "result_package.json"
                    if pkg_json.exists():
                        packages.append(pkg_json)
            if packages:
                packages.sort(key=lambda x: x.parent.name, reverse=True)
                latest_result_package_path = packages[0]
        except Exception as e:
            print(f"Error scanning result packages: {e}")

    if latest_result_package_path and latest_result_package_path.exists():
        try:
            package_data = json.loads(latest_result_package_path.read_text(encoding="utf-8"))
            result_text = package_data.get("result_text") or ""
            
            # Extract INSTAGRAM_POST
            import re
            match = re.search(r'\[BLOCK:INSTAGRAM_POST\]\s*\n(.*?)(?=\n\[BLOCK:|\Z)', result_text, re.DOTALL)
            if match:
                instagram_post = match.group(1).strip()
            
            # Extract Phone
            phone_match = re.search(r'\b\d{2,4}-\d{3,4}-\d{4}\b', result_text)
            if phone_match:
                phone = phone_match.group(0)
            
            # Extract Business Name
            biz_match = re.search(r'\b\d{2,4}-\d{3,4}-\d{4}\s*\(\s*([^)]+)\s*\)', result_text)
            if biz_match:
                business_name = biz_match.group(1).strip()
            if not business_name:
                hashtag_match = re.search(r'\[BLOCK:INSTAGRAM_HASHTAGS\]\s*\n#([^\s#]+)', result_text)
                if hashtag_match:
                    business_name = hashtag_match.group(1).strip()
            
            # Extract Keywords
            hashtags_match = re.search(r'\[BLOCK:INSTAGRAM_HASHTAGS\]\s*\n(.*?)(?=\n\[BLOCK:|\Z)', result_text, re.DOTALL)
            if hashtags_match:
                tags = re.findall(r'#([^\s#]+)', hashtags_match.group(1))
                filtered_tags = [t for t in tags if t != business_name]
                keywords = ", ".join(filtered_tags[:4])
        except Exception as e:
            print(f"Error extracting thumbnail info: {e}")

    # Fallback to form field if extraction failed
    if not instagram_post:
        instagram_post = instagram_text.strip() or "현장 사진을 바탕으로 신뢰감 있는 소상공인 홍보용 썸네일을 만들어줘."
    
    if not phone:
        import re
        phone_match = re.search(r'\b\d{2,4}-\d{3,4}-\d{4}\b', instagram_post)
        if phone_match:
            phone = phone_match.group(0)
            
    if not business_name:
        import re
        biz_match = re.search(r'\b\d{2,4}-\d{3,4}-\d{4}\s*\(\s*([^)]+)\s*\)', instagram_post)
        if biz_match:
            business_name = biz_match.group(1).strip()

    prompt = f"""[썸네일 제작 요청]

첨부된 이미지들을 참고해서 인스타그램용 9:16 세로형 썸네일 이미지를 만들어줘.

[업체 정보]
상호: {business_name}
전화번호: {phone}
키워드: {keywords}

[인스타그램 게시글 참고 문안]
{instagram_post}

[디자인 지시]
- 위 인스타그램 문안의 핵심 메시지를 반영해줘.
- 상호, 키워드, 전화번호가 모바일에서 잘 보이게 구성해줘.
- 현장 사진의 실제 분위기를 살려줘.
- 과장된 광고 느낌보다 지역 소상공인 현장감이 느껴지게 만들어줘.
- 글자는 너무 많이 넣지 말고 핵심 문구 중심으로 배치해줘.

참고 이미지:
{image_lines}

- 위 참고 이미지는 현장 사진 여러 장을 하나로 합친 콜라주일 수 있습니다.
- 콜라주 안의 사진 구도와 분위기를 참고해서 최종 9:16 썸네일을 제작해 주세요.
"""

    prompt_path = job_dir / "thumbnail_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    snapshot_dir = root / "test_prompt_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    latest_prompt_path = snapshot_dir / "latest_prompt.md"
    latest_json_path = snapshot_dir / "latest.json"
    latest_prompt_path.write_text(prompt, encoding="utf-8")
    latest_json_path.write_text(json.dumps({
        "ok": True,
        "created_at": now.isoformat(timespec="seconds"),
        "project_title": project_title,
        "prompt_for_chatgpt": str(prompt_path),
        "latest_prompt_path": str(latest_prompt_path),
        "snapshot_json": str(job_dir / "thumbnail_snapshot.json"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    trigger_dir = root / "test_triggers"
    trigger_dir.mkdir(parents=True, exist_ok=True)
    trigger = {
        "ok": True,
        "status": "pending",
        "action": "GENERATE_GEMINI_THUMBNAIL",
        "job_id": job_id,
        "project_title": project_title,
        "prompt_path": str(prompt_path),
        "created_at": now.isoformat(timespec="seconds"),
        "claimed_at": None,
        "worker_id": None,
        "image_urls": [collage_url] if collage_url else [item["url"] for item in saved],
    }
    (trigger_dir / "trigger_status.json").write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_dir = root / "test_result_packages"
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest = {
        "ok": True,
        "status": "pending",
        "job_id": job_id,
        "project_title": project_title,
        "image_count": len(saved),
        "image_urls": [collage_url] if collage_url else [item["url"] for item in saved],
        "collage_url": collage_url,
        "collage_filename": collage_path.name if collage_url else None,
        "created_at": trigger["created_at"],
    }
    (latest_dir / "latest_thumbnail.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "status": "pending", "job_id": job_id, "image_count": len(saved), "collage_url": collage_url, "collage_filename": collage_path.name if collage_url else None, "assets": project_assets, "project_assets": project_assets, "data": {**latest, "assets": project_assets, "project_assets": project_assets}}


@router.get("/slideshow/queue")
def slideshow_queue(_: User = Depends(get_current_user)):
    try:
        response = httpx.get(f"{API_URL}/api/queue", headers=upstream_headers(), timeout=10)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)

@router.post("/slideshow/queue/{job_id}/stop")
def slideshow_queue_stop(job_id: str, _: User = Depends(get_current_user)):
    try:
        response = httpx.post(f"{API_URL}/api/queue/{quote(job_id, safe='')}/cancel", headers=upstream_headers(), timeout=15)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)

@router.get("/slideshow/jobs/{job_id}")
def slideshow_job(job_id: str, current_user: User = Depends(get_current_user)):
    try:
        response = httpx.get(f"{API_URL}/api/jobs/{quote(job_id, safe='')}", headers=upstream_headers(), timeout=10)
        response.raise_for_status()
        data = response.json()
        prepared = _prepare_slideshow_result(data, current_user)
        try:
            result = prepared.get("result") or {}
            mp4_url = result.get("mp4_url") or result.get("preview_mp4_url") or result.get("download_url")
            if mp4_url:
                archive_info = register_common_archive(
                    user_id=current_user.id,
                    source="shortform",
                    source_job_id=job_id,
                    archive_group_key=str(
                        prepared.get("archive_group_key")
                        or prepared.get("pipeline_id")
                        or result.get("archive_group_key")
                        or result.get("pipeline_id")
                        or result.get("project_key")
                        or ""
                    ).strip() or None,
                    title=f"숏폼 · {result.get('project_key') or result.get('project_title') or job_id}",
                    status="shortform_completed",
                    raw_result=str(result.get("script") or result.get("caption") or result.get("message") or ""),
                    media={
                        "mp4_url": result.get("mp4_url"),
                        "preview_mp4_url": result.get("preview_mp4_url"),
                        "thumbnail_url": result.get("thumbnail_url"),
                        "mp4_path": result.get("mp4_path") or result.get("video_path") or result.get("path"),
                    },
                    extra={"slideshow_job": prepared},
                )
                if archive_info.get("ok"):
                    result["archive_job_id"] = archive_info.get("archive_job_id")
        except Exception:
            pass
        return prepared
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)

@router.post("/slideshow/jobs/{job_id}/cleanup")
def slideshow_cleanup(job_id: str, payload: dict = Body(default_factory=dict), user: User = Depends(get_current_user)):
    cleanup_token = str(payload.get("cleanup_token") or "")
    reason = str(payload.get("reason") or "manual")
    _validate_cleanup_token(job_id, cleanup_token, user)
    try:
        data = _cleanup_upstream(job_id, cleanup_token, reason)
        if data.get("ok") is not False:
            SLIDESHOW_CLEANUP_TOKENS.pop(job_id, None)
        return data
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)

@router.post("/slideshow/jobs/{job_id}/cleanup-beacon")
def slideshow_cleanup_beacon(job_id: str, cleanup_token: str = Form(""), reason: str = Form("pagehide")):
    _validate_cleanup_token(job_id, cleanup_token)
    try:
        data = _cleanup_upstream(job_id, cleanup_token, reason)
        if data.get("ok") is not False:
            SLIDESHOW_CLEANUP_TOKENS.pop(job_id, None)
        return data
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)


@router.api_route("/slideshow/media/{filename}", methods=["GET", "HEAD"])
def slideshow_media(filename: str, request: Request, preview: bool = False, _: User = Depends(get_current_user)):
    from urllib.parse import unquote
    import re
    
    # 1. URL 디코딩
    decoded_filename = unquote(filename)
    
    # 2. 경로 이탈(traversal) 방지 보안 검증
    if "/" in decoded_filename or "\\" in decoded_filename or ".." in decoded_filename:
        raise HTTPException(status_code=400, detail="Invalid filename path")
        
    # 3. 확장자 검증
    if not decoded_filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only MP4 files are allowed")
        
    try:
        # 업스트림 서버는 원래 파일명(한글 포함 가능)을 인식하므로 인코딩하여 요청합니다.
        # HTML5 video 미리보기는 Range 요청을 사용하는 경우가 많으므로 Range 헤더를 그대로 전달합니다.
        headers_upstream = upstream_headers()
        if request.headers.get("range"):
            headers_upstream["Range"] = request.headers.get("range")
        response = httpx.request(
            request.method,
            f"{API_URL}/media/slideshow/{quote(decoded_filename, safe='')}?preview={str(preview).lower()}", 
            headers=headers_upstream, 
            timeout=180
        )
        response.raise_for_status()
        
        # 4. 브라우저 호환을 위한 ASCII 안전 파일명 생성
        safe_name_str = decoded_filename.replace("팟캐스트", "podcast").replace("슬라이드쇼", "slideshow")
        safe_name_str = re.sub(r'[^a-zA-Z0-9\-_.]', '_', safe_name_str)
        safe_name_str = re.sub(r'_{2,}', '_', safe_name_str).strip('_')
        if not safe_name_str.lower().endswith(".mp4"):
            safe_name_str += ".mp4"
            
        # 5. 안정화된 다운로드 응답 헤더 제공
        disposition = "inline" if preview else f'attachment; filename="{safe_name_str}"'
        headers = {
            "Content-Type": "video/mp4",
            "Content-Disposition": disposition,
            "Accept-Ranges": response.headers.get("accept-ranges", "bytes"),
            "Cache-Control": "no-store",
        }
        for header_name in ("content-length", "content-range"):
            if header_name in response.headers:
                canonical = "-".join(part.capitalize() for part in header_name.split("-"))
                headers[canonical] = response.headers[header_name]
            
        content = response.content if request.method == "GET" else b""
        return Response(content, status_code=response.status_code, media_type="video/mp4", headers=headers)
    except httpx.HTTPError as exc:
        upstream_error(exc)
