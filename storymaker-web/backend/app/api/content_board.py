# -*- coding: utf-8 -*-
"""StoryMaker V2 서버 보관함.

기존 보관함의 파일시스템 재검색을 사용하지 않고 mobile_one_shot_jobs DB에
등록된 현재 사용자 작업만 조회합니다. 게시물과 작업 폴더는 7일간 보관합니다.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text

from app.api.auth import get_current_user
from app.api.mobile_one_shot import (
    _archive_persona_from_data,
    _extract_raw_result_block,
    _mobile_archive_has_content,
    _mobile_download_file_urls,
    _mobile_download_zip_has_files,
    _mobile_job_title,
    _mobile_project_files,
    _output_root,
    _start_podcast_job,
    _start_shortform_job,
    _start_thumbnail_job,
    _sync_podcast_result,
    _sync_shortform_result,
    _sync_thumbnail_result,
    _sync_worker_result,
    _reapply_staged_edited_contents,
)
from app.db.mobile_one_shot_repository import (
    delete_mobile_one_shot_job,
    get_content_board_job_record,
    get_mobile_one_shot_result_path,
    list_content_board_job_summaries,
    list_content_board_overflow_jobs,
)
from app.db.content_asset_repository import (
    delete_content_archive_assets,
    get_content_archive_asset,
    list_content_archive_assets,
)
from app.db.database import SessionLocal
from app.db.models import User, UserPersona
from app.services.content_asset_service import sync_content_archive_assets
from app.services.content_storage_service import load_documents
from app.services.image_download_watermark import prepare_watermarked_download_images
from app.services.content_integrity_service import delete_job_bundle

router = APIRouter(prefix="/v2/content-board", tags=["V2 Content Board"])
logger = logging.getLogger(__name__)

ARCHIVE_LIMIT_INTERVAL_SECONDS = 3600
_JOB_ID_PATTERN = re.compile(r"mob-[0-9]{14}-[a-f0-9]{8}")
_retention_thread_started = False
_retention_lock = threading.Lock()


def _cutoff_at() -> str:
    """Archive listing no longer uses age retention."""
    return ""


def _expires_at(created_at: object) -> str:
    """Archive items no longer expire by age."""
    return ""


def _result_file_from_record(record: dict, *, require_exists: bool = True) -> Path | None:
    raw_path = str(record.get("result_path") or "").strip()
    if not raw_path:
        return None
    try:
        result_file = Path(raw_path).expanduser().resolve()
        allowed_root = (_output_root() / "mobile_one_shot").resolve()
    except Exception:
        return None
    if result_file.name != "result.json" or allowed_root not in result_file.parents:
        return None
    if require_exists and not result_file.is_file():
        return None
    return result_file


def _read_owned_result(record: dict) -> tuple[Path, dict]:
    result_file = _result_file_from_record(record)
    if result_file is None:
        raise HTTPException(status_code=404, detail="보관된 작업 파일을 찾을 수 없습니다.")
    try:
        data = json.loads(result_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="보관된 작업 파일을 읽을 수 없습니다.") from exc

    expected_job_id = str(record.get("job_id") or "").strip()
    expected_user_id = str(record.get("user_id") or "").strip()
    if str(data.get("job_id") or "").strip() != expected_job_id:
        raise HTTPException(status_code=404, detail="게시물 연결 정보가 일치하지 않습니다.")
    if str(data.get("user_bucket") or "").strip() != expected_user_id:
        raise HTTPException(status_code=404, detail="게시물 소유자 정보가 일치하지 않습니다.")
    if str(data.get("status") or "").lower() == "deleted" or data.get("deleted_at"):
        raise HTTPException(status_code=404, detail="삭제된 게시물입니다.")
    return result_file, data


def _normalize_outputs(data: dict) -> dict:
    outputs = dict(data.get("outputs") or {})
    raw_result = str(data.get("raw_result") or "")
    if not raw_result:
        data["outputs"] = outputs
        return data

    blog_titles = str(
        outputs.get("blog_titles")
        or outputs.get("BLOG_TITLES")
        or _extract_raw_result_block(raw_result, "BLOG_TITLES")
        or ""
    ).strip()
    blog_post = str(
        outputs.get("blog_post")
        or outputs.get("BLOG_POST")
        or _extract_raw_result_block(raw_result, "BLOG_POST")
        or ""
    ).strip()
    blog_hashtags = str(
        outputs.get("blog_hashtags")
        or outputs.get("BLOG_HASHTAGS")
        or _extract_raw_result_block(raw_result, "BLOG_HASHTAGS")
        or ""
    ).strip()
    if not str(outputs.get("blog") or "").strip():
        outputs["blog"] = "\n\n".join(
            part for part in [blog_titles, blog_post, blog_hashtags] if part
        ).strip()
    outputs.setdefault("blog_titles", blog_titles)
    outputs.setdefault("blog_post", blog_post)
    outputs.setdefault("blog_hashtags", blog_hashtags)
    outputs.setdefault("instagram", _extract_raw_result_block(raw_result, "INSTAGRAM_POST"))
    outputs.setdefault("place", _extract_raw_result_block(raw_result, "NAVER_PLACE_NEWS"))
    outputs.setdefault("google_business", _extract_raw_result_block(raw_result, "GOOGLE_BUSINESS_POST"))
    outputs.setdefault(
        "carrot",
        _extract_raw_result_block(raw_result, "CARROT_POST")
        or _extract_raw_result_block(raw_result, "DAANGN_POST"),
    )
    outputs.setdefault("cardnews", _extract_raw_result_block(raw_result, "CAROUSEL_7"))
    outputs.setdefault(
        "podcast",
        "\n\n".join(
            part
            for part in [
                _extract_raw_result_block(raw_result, "PODCAST_50"),
                _extract_raw_result_block(raw_result, "PODCAST_80"),
            ]
            if part
        ).strip(),
    )
    data["outputs"] = outputs
    return data


def _content_asset_rows(user_id: int, job_id: str, data: dict, result_file: Path) -> list[dict[str, Any]]:
    rows = list_content_archive_assets(user_id, job_id)
    if result_file.is_file():
        try:
            sync_content_archive_assets(
                user_id=user_id,
                archive_job_id=job_id,
                archive_group_key=str(data.get("archive_group_key") or job_id),
                source_menu=str(data.get("latest_source") or data.get("source") or "mobile-one-shot"),
                source_job_id=str(data.get("latest_source_job_id") or data.get("source_job_id") or job_id),
                payload=data,
                metadata=data,
                result_dir=result_file.parent,
            )
            rows = list_content_archive_assets(user_id, job_id)
        except Exception:
            logger.exception("content asset lazy sync failed job_id=%s user_id=%s", job_id, user_id)

    assets: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for row in rows:
        asset_type = str(row.get("asset_type") or "file")
        location = str(row.get("stored_path") or row.get("public_url") or row.get("id") or "")
        asset_order = int(row.get("asset_order") or 0)
        dedupe_key = (asset_type, location, asset_order)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        asset_id = int(row.get("id") or 0)
        assets.append({
            "id": asset_id,
            "asset_type": asset_type,
            "asset_order": asset_order,
            "source_menu": row.get("source_menu"),
            "source_job_id": row.get("source_job_id"),
            "original_filename": row.get("original_filename"),
            "download_name": row.get("download_name"),
            "mime_type": row.get("mime_type"),
            "file_size": int(row.get("file_size") or 0),
            "view_url": f"/api/v2/content-board/assets/{asset_id}/view",
            "download_url": f"/api/v2/content-board/assets/{asset_id}/download",
        })
    return assets


def _asset_projection(assets: list[dict[str, Any]]) -> dict[str, Any]:
    def first(asset_type: str) -> dict[str, Any] | None:
        return next((item for item in assets if item.get("asset_type") == asset_type), None)

    image_assets = [item for item in assets if item.get("asset_type") == "image"]
    mp3 = first("mp3")
    mp4 = first("mp4")
    thumbnail = first("thumbnail")
    srt = first("srt")
    return {
        "images": [
            {
                "name": item.get("download_name") or item.get("original_filename"),
                "stored_name": item.get("original_filename"),
                "url": item.get("view_url"),
                "download_url": item.get("download_url"),
                "size": item.get("file_size") or 0,
                "asset_id": item.get("id"),
            }
            for item in image_assets
        ],
        "media": {
            "mp3_url": mp3.get("view_url") if mp3 else None,
            "mp4_url": mp4.get("view_url") if mp4 else None,
            "thumbnail_url": thumbnail.get("view_url") if thumbnail else None,
            "srt_url": srt.get("view_url") if srt else None,
        },
        "files": {
            "mp3_filename": mp3.get("download_name") if mp3 else None,
            "mp4_filename": mp4.get("download_name") if mp4 else None,
            "thumbnail_filename": thumbnail.get("download_name") if thumbnail else None,
            "srt_filename": srt.get("download_name") if srt else None,
        },
        "file_urls": {
            "mp3": mp3.get("view_url") if mp3 else None,
            "mp4": mp4.get("view_url") if mp4 else None,
            "thumbnail": thumbnail.get("view_url") if thumbnail else None,
            "srt": srt.get("view_url") if srt else None,
        },
    }


def _summary_item(record: dict, result_file: Path, data: dict) -> dict[str, Any]:
    memo = str(record.get("memo") or "").strip()
    job_id = str(record.get("job_id") or "").strip()
    user_id = int(record.get("user_id") or data.get("user_bucket") or 0)
    created_at = record.get("created_at") or data.get("created_at")
    assets = _content_asset_rows(user_id, job_id, data, result_file)
    projection = _asset_projection(assets)
    return {
        "job_id": job_id,
        "content_id": job_id,
        "archive_group_key": str(data.get("archive_group_key") or "").strip(),
        "status": record.get("status") or data.get("status"),
        "created_at": created_at,
        "memo_length": len(memo),
        "image_count": len(projection["images"]),
        "images": projection["images"],
        "keywords": list(data.get("keywords") or [])[:5],
        "persona": _archive_persona_from_data(data),
        "title": _mobile_job_title(data) or memo[:80] or job_id,
        "media": {
            **dict(data.get("media") or {}),
            **{key: value for key, value in projection["media"].items() if value},
        },
        "files": projection["files"],
        "file_urls": projection["file_urls"],
        "assets": assets,
        "download_url": (
            f"/api/mobile/one-shot/jobs/{job_id}/download"
            if _mobile_download_zip_has_files(data, result_file.parent)
            else None
        ),
    }


def _hard_delete_record(record: dict) -> tuple[bool, bool]:
    """작업·문서·자산·실제 폴더를 하나의 서비스로 정리합니다."""
    job_id = str(record.get("job_id") or "").strip()
    user_id = int(record.get("user_id") or 0)
    if not job_id or not user_id:
        return False, False
    result = delete_job_bundle(user_id, job_id, delete_files=True)
    deleted_db = bool(result.get("jobs") or result.get("documents") or result.get("assets"))
    return deleted_db, bool(result.get("folder_deleted"))

def _is_admin_user(user: User | None) -> bool:
    return bool(user and str(getattr(user, "role", "") or "").strip().lower() == "admin")


def _archive_limit_for_user(user_id: int) -> int | None:
    """Return None for administrators, otherwise the active plan archive limit."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            return 10
        if _is_admin_user(user):
            return None
        row = db.execute(text("""
            SELECT sp.archive_item_limit
            FROM subscription_plans sp
            WHERE sp.code = COALESCE(
                (SELECT mbp.current_plan_code FROM member_billing_profiles mbp
                 WHERE mbp.user_id = :user_id LIMIT 1),
                'free'
            )
              AND sp.is_active = 1
            LIMIT 1
        """), {"user_id": int(user_id)}).first()
        if not row or row[0] is None:
            return 10
        return max(0, int(row[0]))


def enforce_content_board_limit_for_user(user_id: int) -> dict:
    archive_limit = _archive_limit_for_user(user_id)
    if archive_limit is None:
        return {"user_id": int(user_id), "archive_limit": None, "unlimited": True,
                "overflow": 0, "deleted_db": 0, "deleted_folders": 0, "failed": 0}

    overflow_rows = list_content_board_overflow_jobs(int(user_id), archive_limit)
    deleted_db = 0
    deleted_folders = 0
    failed = 0
    for record in overflow_rows:
        try:
            row_deleted, folder_deleted = _hard_delete_record(record)
            deleted_db += int(row_deleted)
            deleted_folders += int(folder_deleted)
        except Exception:
            failed += 1
            logger.exception(
                "content board archive-limit cleanup failed user_id=%s job_id=%s",
                user_id,
                record.get("job_id"),
            )
    result = {
        "user_id": int(user_id),
        "archive_limit": archive_limit,
        "unlimited": False,
        "overflow": len(overflow_rows),
        "deleted_db": deleted_db,
        "deleted_folders": deleted_folders,
        "failed": failed,
    }
    if overflow_rows or failed:
        logger.info("content board archive-limit result=%s", result)
    return result


def enforce_all_content_board_limits() -> dict:
    with SessionLocal() as db:
        rows = db.execute(text("""
            SELECT DISTINCT user_id
            FROM mobile_one_shot_jobs
            WHERE user_id IS NOT NULL AND user_id > 0 AND result_path != ''
            ORDER BY user_id
        """)).all()
    totals = {"users_checked": 0, "deleted_db": 0, "deleted_folders": 0, "failed": 0}
    for row in rows:
        result = enforce_content_board_limit_for_user(int(row[0]))
        totals["users_checked"] += 1
        totals["deleted_db"] += int(result.get("deleted_db") or 0)
        totals["deleted_folders"] += int(result.get("deleted_folders") or 0)
        totals["failed"] += int(result.get("failed") or 0)
    return totals


def purge_expired_content_board_items(max_batches: int = 10, batch_size: int = 500) -> dict:
    """Backward-compatible entry point; age retention is disabled."""
    return enforce_all_content_board_limits()


def _retention_loop() -> None:
    while True:
        try:
            enforce_all_content_board_limits()
        except Exception:
            logger.exception("content board archive-limit loop failed")
        time.sleep(ARCHIVE_LIMIT_INTERVAL_SECONDS)


def start_content_board_retention_scheduler() -> None:
    global _retention_thread_started
    with _retention_lock:
        if _retention_thread_started:
            return
        _retention_thread_started = True
    enforce_all_content_board_limits()
    threading.Thread(
        target=_retention_loop,
        name="content-board-archive-limit",
        daemon=True,
    ).start()



@router.get("")
def list_content_board_items(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    safe_limit = max(1, min(int(limit or 10), 20))
    safe_offset = max(0, int(offset or 0))
    enforce_content_board_limit_for_user(current_user.id)
    cutoff = _cutoff_at()
    items: list[dict[str, Any]] = []

    for record in list_content_board_job_summaries(
        current_user.id,
        cutoff,
        safe_limit,
        safe_offset,
    ):
        record["user_id"] = current_user.id
        try:
            result_file, data = _read_owned_result(record)
        except HTTPException:
            continue
        data = _sync_worker_result(data, result_file)
        data = _reapply_staged_edited_contents(data, result_file)
        data = _start_podcast_job(data, result_file)
        data = _sync_podcast_result(data, result_file)
        data = _start_thumbnail_job(data, result_file)
        data = _sync_thumbnail_result(data, result_file)
        data = _start_shortform_job(data, result_file)
        data = _sync_shortform_result(data, result_file)
        if not _mobile_archive_has_content(data):
            continue
        items.append(_summary_item(record, result_file, data))

    return {
        "ok": True,
        "count": len(items),
        "items": items,
        "archive_item_limit": _archive_limit_for_user(current_user.id),
    }


def _resolved_asset_file(asset: dict[str, Any]) -> Path | None:
    raw_path = str(asset.get("stored_path") or "").strip()
    if not raw_path:
        return None
    try:
        candidate = Path(raw_path).expanduser().resolve()
        allowed_roots = [
            _output_root().resolve(),
            Path("/home/bourne/StoryMaker_1/OUTPUT").resolve(),
            Path("/home/bourne/StoryMaker_1/podcast").resolve(),
            Path("/home/bourne/StoryMaker_1/SlidShow").resolve(),
            Path("/home/bourne/StoryMaker_1/uploads").resolve(),
            Path("/home/bourne/StoryMaker_1/tts_cache").resolve(),
        ]
    except Exception:
        return None
    if not candidate.is_file():
        return None
    if not any(root == candidate or root in candidate.parents for root in allowed_roots):
        return None
    return candidate


def _serve_content_asset(asset_id: int, user_id: int, *, download: bool):
    asset = get_content_archive_asset(asset_id, user_id)
    if not asset:
        raise HTTPException(status_code=404, detail="보관함 미디어를 찾을 수 없습니다.")
    filename = str(asset.get("download_name") or asset.get("original_filename") or f"storymaker-{asset_id}")
    media_type = str(asset.get("mime_type") or "application/octet-stream")
    local_file = _resolved_asset_file(asset)
    if local_file is not None:
        response_file = local_file
        if download and str(asset.get("asset_type") or "").lower() == "image":
            try:
                archive_job_id = str(asset.get("archive_job_id") or "").strip()
                record = get_content_board_job_record(archive_job_id, user_id, _cutoff_at()) if archive_job_id else None
                if record:
                    record["user_id"] = user_id
                    result_file, data = _read_owned_result(record)
                    persona = data.get("persona") if isinstance(data.get("persona"), dict) else {}
                    company = str(persona.get("company_name") or persona.get("business_name") or "").strip()
                    phone = str(
                        persona.get("phone_number")
                        or persona.get("phone")
                        or persona.get("business_phone")
                        or persona.get("contact_phone")
                        or persona.get("mobile")
                        or persona.get("tel")
                        or ""
                    ).strip()
                    persona_id = int(persona.get("id") or 0)
                    if persona_id and (not company or not phone):
                        db = SessionLocal()
                        try:
                            db_persona = (
                                db.query(UserPersona)
                                .filter(UserPersona.id == persona_id, UserPersona.user_id == user_id)
                                .first()
                            )
                            if db_persona:
                                company = company or str(db_persona.company_name or "").strip()
                                phone = phone or str(db_persona.phone_number or "").strip()
                        finally:
                            db.close()
                    if company and phone:
                        watermark_data = dict(data)
                        watermark_data["persona"] = {
                            **persona,
                            "company_name": company,
                            "phone_number": phone,
                        }
                        prepared = prepare_watermarked_download_images(
                            [local_file],
                            watermark_data,
                            result_file.parent / ".download_watermark_cache",
                        )
                        if prepared:
                            response_file = prepared[0]
            except Exception:
                logger.exception(
                    "content asset image watermark failed asset_id=%s user_id=%s",
                    asset_id,
                    user_id,
                )
        return FileResponse(
            path=response_file,
            media_type=media_type,
            filename=filename,
            content_disposition_type="attachment" if download else "inline",
        )
    public_url = str(asset.get("public_url") or "").strip()
    if public_url.startswith(("/api/", "http://", "https://")):
        return RedirectResponse(public_url, status_code=307)
    raise HTTPException(status_code=404, detail="보관함 미디어 파일이 존재하지 않습니다.")


@router.get("/assets/{asset_id}/view")
def view_content_asset(asset_id: int, current_user: User = Depends(get_current_user)):
    return _serve_content_asset(asset_id, current_user.id, download=False)


@router.get("/assets/{asset_id}/download")
def download_content_asset(asset_id: int, current_user: User = Depends(get_current_user)):
    return _serve_content_asset(asset_id, current_user.id, download=True)


@router.get("/{content_id}")
def get_content_board_item(
    content_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _JOB_ID_PATTERN.fullmatch(content_id):
        raise HTTPException(status_code=400, detail="content_id 형식이 올바르지 않습니다.")
    record = get_content_board_job_record(content_id, current_user.id, _cutoff_at())
    if not record:
        raise HTTPException(status_code=404, detail="게시물을 찾을 수 없거나 보관 기간이 지났습니다.")
    record["user_id"] = current_user.id
    result_file, data = _read_owned_result(record)
    data = _sync_worker_result(data, result_file)
    data = _reapply_staged_edited_contents(data, result_file)
    data = _start_podcast_job(data, result_file)
    data = _sync_podcast_result(data, result_file)
    data = _sync_thumbnail_result(data, result_file)
    data = _sync_shortform_result(data, result_file)
    data = _normalize_outputs(data)
    db_documents = load_documents(content_id, current_user.id)
    if db_documents:
        outputs = data.setdefault("outputs", {})
        outputs.update(db_documents)
        data["documents"] = db_documents
        data["document_source"] = "database"
    else:
        data["documents"] = dict(data.get("outputs") or {})
        data["document_source"] = "result_json_fallback"

    # 단계별 제작 수정본이 있으면 보관함 화면에서 오래된 Worker raw_result가
    # 최신 outputs/DB 문서보다 먼저 선택되지 않도록 상세 응답에서만 비웁니다.
    pipeline = data.get("pipeline") if isinstance(data.get("pipeline"), dict) else {}
    staged_session = data.get("staged_session") if isinstance(data.get("staged_session"), dict) else {}
    edited_contents = staged_session.get("edited_contents")
    if (
        str(pipeline.get("production_mode") or "").strip().lower() == "staged"
        and isinstance(edited_contents, dict)
        and edited_contents
    ):
        data["raw_result"] = ""

    data["content_id"] = content_id
    data["expires_at"] = _expires_at(record.get("created_at") or data.get("created_at"))
    data["archive_item_limit"] = _archive_limit_for_user(current_user.id)
    assets = _content_asset_rows(current_user.id, content_id, data, result_file)
    projection = _asset_projection(assets)
    data["assets"] = assets
    data["images"] = projection["images"]
    data["image_count"] = len(projection["images"])
    data["media"] = {
        **dict(data.get("media") or {}),
        **{key: value for key, value in projection["media"].items() if value},
    }
    data["file_urls"] = projection["file_urls"]
    data["files"] = projection["files"]
    data["download_url"] = (
        f"/api/mobile/one-shot/jobs/{content_id}/download"
        if _mobile_download_zip_has_files(data, result_file.parent)
        else None
    )
    preview_text = str(
        (data.get("outputs") or {}).get("blog")
        or (data.get("outputs") or {}).get("BLOG")
        or data.get("raw_result")
        or ""
    ).strip()
    data["preview_text"] = preview_text[:3000]
    return {
        "ok": True,
        "job_id": content_id,
        "content_id": content_id,
        "status": data.get("status", "unknown"),
        "message": "게시물을 불러왔습니다.",
        "data": data,
    }


@router.delete("/{content_id}")
def delete_content_board_item(
    content_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _JOB_ID_PATTERN.fullmatch(content_id):
        raise HTTPException(status_code=400, detail="content_id 형식이 올바르지 않습니다.")
    record = get_content_board_job_record(content_id, current_user.id, _cutoff_at())
    if not record:
        result_path = get_mobile_one_shot_result_path(content_id, current_user.id)
        if result_path:
            record = {
                "job_id": content_id,
                "user_id": current_user.id,
                "result_path": result_path,
            }
    if not record:
        raise HTTPException(status_code=404, detail="삭제할 게시물을 찾을 수 없습니다.")
    record["user_id"] = current_user.id
    deleted_db, deleted_folder = _hard_delete_record(record)
    if not deleted_db and not deleted_folder:
        raise HTTPException(status_code=404, detail="삭제할 게시물을 찾을 수 없습니다.")
    return {
        "ok": True,
        "content_id": content_id,
        "job_id": content_id,
        "deleted_db": deleted_db,
        "deleted_folder": deleted_folder,
    }
