# -*- coding: utf-8 -*-
"""Project Assets API Router.

Mission 7:
- Drag & Drop 다중 업로드
- 최초 업로드 role=PENDING, status=READY, source=UPLOAD
- Role 변경 시 ALT 텍스트 자동 재생성
- project_assets 스키마/인덱스 점검
"""
from __future__ import annotations

from typing import Any
from pathlib import Path
import io
import json
import zipfile
import hashlib
import mimetypes
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.database import get_db
from app.db.models import IndustryPromptTemplate, User, UserPersona
from app.services.project_asset_service import (
    build_public_url,
    make_alt_text,
    read_project_assets,
    restore_project_asset,
    safe_token,
    save_project_asset,
    soft_delete_project_asset,
    to_editor_asset_response,
    update_project_asset_metadata,
)

router = APIRouter()

EXPECTED_PROJECT_ASSET_COLUMNS = {
    "id",
    "user_id",
    "username",
    "project_id",
    "project_key",
    "asset_group_key",
    "version",
    "is_active",
    "asset_type",
    "role",
    "original_filename",
    "stored_filename",
    "relative_path",
    "public_url",
    "company_name",
    "keyword",
    "alt_text",
    "caption",
    "mime_type",
    "file_size",
    "display_order",
    "width",
    "height",
    "duration_seconds",
    "status",
    "source",
    "tags",
    "created_at",
    "updated_at",
}

EXPECTED_PROJECT_ASSET_INDEXES = {
    "ix_project_assets_user_id",
    "ix_project_assets_project_id",
    "ix_project_assets_project_key",
    "ix_project_assets_asset_group_key",
    "ix_project_assets_asset_type",
    "ix_project_assets_role",
    "ix_project_assets_status",
    "ix_project_assets_source",
    "ix_project_assets_is_active",
    "ix_project_assets_display_order",
    "ix_project_assets_created_at",
}


class AssetRoleUpdateRequest(BaseModel):
    role: str
    alt_text: str | None = None
    caption: str | None = None
    tags: str | list[str] | None = None
    display_order: int | None = None
    status: str | None = None
    is_active: bool | None = None


class AssetBulkDownloadRequest(BaseModel):
    asset_ids: list[int]


def _detect_existing_asset_type(path: Path) -> tuple[str, str, str]:
    suffix = path.suffix.lower()
    text = path.as_posix().lower()
    if suffix in {".mp4", ".mov", ".webm", ".m4v"}:
        return "video", "SHORTFORM", "VIDEO"
    if "thumb" in text or "thumbnail" in text or "썸네일" in path.name:
        return "thumbnail", "THUMBNAIL", "THUMBNAIL"
    return "image", "GENERAL", "IMPORT"


def _insert_existing_asset_if_missing(db: Session, *, root: Path, path: Path, user: User, project_key: str, order_no: int) -> bool:
    rel = path.relative_to(root).as_posix()
    public_url = build_public_url(root, path)
    exists = db.execute(text("""
        SELECT id FROM project_assets
        WHERE user_id = :user_id
          AND (relative_path = :relative_path OR public_url = :public_url)
        LIMIT 1
    """), {"user_id": user.id, "relative_path": rel, "public_url": public_url}).first()
    if exists:
        return False
    kind, role, source = _detect_existing_asset_type(path)
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "user_id": user.id,
        "username": getattr(user, "username", "") or "",
        "project_id": None,
        "project_key": safe_token(project_key or path.parent.name or "legacy", "project"),
        "asset_group_key": f"legacy_{hashlib.sha1(rel.encode('utf-8')).hexdigest()[:24]}",
        "version": 1,
        "is_active": 1,
        "asset_type": kind,
        "role": role,
        "original_filename": path.name,
        "stored_filename": path.name,
        "relative_path": rel,
        "public_url": public_url,
        "company_name": "",
        "keyword": project_key or "",
        "alt_text": make_alt_text("", project_key or "", role),
        "caption": "기존 파일 자동 등록",
        "mime_type": mimetypes.guess_type(path.name)[0] or ("video/mp4" if kind == "video" else "image/png"),
        "file_size": path.stat().st_size,
        "display_order": order_no,
        "status": "READY",
        "source": source,
        "tags": "legacy-backfill",
        "created_at": now_text,
        "updated_at": now_text,
    }
    db.execute(text("""
        INSERT INTO project_assets
        (user_id, username, project_id, project_key, asset_group_key, version, is_active, asset_type, role, original_filename, stored_filename, relative_path, public_url, company_name, keyword, alt_text, caption, mime_type, file_size, display_order, status, source, tags, created_at, updated_at)
        VALUES
        (:user_id, :username, :project_id, :project_key, :asset_group_key, :version, :is_active, :asset_type, :role, :original_filename, :stored_filename, :relative_path, :public_url, :company_name, :keyword, :alt_text, :caption, :mime_type, :file_size, :display_order, :status, :source, :tags, :created_at, :updated_at)
    """), payload)
    return True


def _load_default_keyword_sources(db: Session, user: User, industry_key: str = "") -> tuple[str, str]:
    persona = db.query(UserPersona).filter(UserPersona.user_id == user.id).order_by(UserPersona.is_default.desc(), UserPersona.updated_at.desc()).first()
    user_keywords = ""
    resolved_industry = industry_key
    if persona:
        try:
            user_keywords = ", ".join(json.loads(persona.keywords_json or "[]"))
        except Exception:
            user_keywords = ""
        resolved_industry = resolved_industry or getattr(persona, "industry_key", "") or ""
    industry_keywords = ""
    if resolved_industry:
        tmpl = db.query(IndustryPromptTemplate).filter(IndustryPromptTemplate.industry_key == resolved_industry).first()
        if tmpl:
            industry_keywords = tmpl.keyword_hint or ""
    return user_keywords, industry_keywords


def _guess_asset_type(upload: UploadFile) -> str:
    content_type = (upload.content_type or "").lower()
    filename = (upload.filename or "").lower()
    if content_type.startswith("video/") or filename.endswith((".mp4", ".mov", ".webm", ".m4v")):
        return "video"
    if "thumb" in filename or "thumbnail" in filename:
        return "thumbnail"
    return "image"


@router.get("/assets/schema-check")
def check_project_assets_schema(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """SQLite 마이그레이션 후 project_assets 컬럼/인덱스 상태를 점검합니다."""
    try:
        columns = db.execute(text("PRAGMA table_info(project_assets)")).mappings().all()
        indexes = db.execute(text("PRAGMA index_list(project_assets)")).mappings().all()
        column_names = {str(row.get("name")) for row in columns}
        index_names = {str(row.get("name")) for row in indexes}
        missing_columns = sorted(EXPECTED_PROJECT_ASSET_COLUMNS - column_names)
        missing_indexes = sorted(EXPECTED_PROJECT_ASSET_INDEXES - index_names)
        return {
            "ok": not missing_columns and not missing_indexes,
            "table": "project_assets",
            "columns": sorted(column_names),
            "indexes": sorted(index_names),
            "missing_columns": missing_columns,
            "missing_indexes": missing_indexes,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/assets/backfill-existing")
def backfill_existing_assets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    if not root.exists():
        return {"ok": True, "inserted": 0, "skipped": 0, "scanned": 0, "roots": []}
    media_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".webm", ".m4v"}
    scan_roots = []
    for folder in (root / "users" / safe_token(user.id, "user") / "projects", root / "users" / "default_user" / "projects", root / "test_thumbnail_jobs"):
        if folder.exists() and folder.is_dir():
            scan_roots.append(folder)
    inserted = skipped = scanned = 0
    for base in scan_roots:
        files = sorted((p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in media_exts), key=lambda p: p.stat().st_mtime, reverse=True)
        for order_no, path in enumerate(files[:500], start=1):
            scanned += 1
            try:
                project_key = path.parent.parent.name if path.parent.name in {"images", "videos", "thumbnails", "input_images"} else path.parent.name
                if _insert_existing_asset_if_missing(db, root=root, path=path, user=user, project_key=project_key, order_no=order_no):
                    inserted += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
    db.commit()
    return {"ok": True, "inserted": inserted, "skipped": skipped, "scanned": scanned, "roots": [str(p.relative_to(root)) for p in scan_roots]}


@router.get("/assets")
def list_assets(
    project_id: int | None = None,
    project_key: str | None = None,
    active_only: bool = True,
    status: str | None = "READY",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """현재 사용자 프로젝트 에셋 목록을 DB 기준으로 조회합니다."""
    try:
        rows = read_project_assets(
            db,
            user_id=user.id,
            project_id=project_id,
            project_key=project_key,
            active_only=active_only,
            status=status,
        )
        assets = [to_editor_asset_response(row) for row in rows]
        return {"ok": True, "count": len(assets), "assets": assets, "data": assets}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/assets/bulk-download")
def bulk_download_assets(
    req: AssetBulkDownloadRequest = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ids: list[int] = []
    for value in req.asset_ids[:100]:
        try:
            asset_id = int(value)
        except Exception:
            continue
        if asset_id > 0 and asset_id not in ids:
            ids.append(asset_id)
    if not ids:
        raise HTTPException(status_code=400, detail="No asset ids selected")

    params: dict[str, Any] = {"user_id": user.id}
    placeholders: list[str] = []
    for idx, asset_id in enumerate(ids):
        key = f"id_{idx}"
        params[key] = asset_id
        placeholders.append(f":{key}")
    rows = db.execute(text(f"SELECT * FROM project_assets WHERE user_id = :user_id AND id IN ({', '.join(placeholders)}) AND is_active = 1 AND status = 'READY' ORDER BY asset_type ASC, display_order ASC, id ASC"), params).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Selected assets not found")

    root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results")).resolve()
    folders = {"image": "images", "thumbnail": "thumbnails", "video": "videos"}
    buffer = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            rel = str(row.get("relative_path") or "").strip()
            if not rel:
                continue
            path = (root / rel).resolve()
            if root not in path.parents and path != root:
                continue
            if not path.exists() or not path.is_file():
                continue
            folder = folders.get(str(row.get("asset_type") or ""), "files")
            name = str(row.get("stored_filename") or path.name)
            zf.write(path, arcname=f"{folder}/{name}")
            added += 1
    if added == 0:
        raise HTTPException(status_code=404, detail="Selected files are missing")

    buffer.seek(0)
    filename = f"storymaker_assets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return StreamingResponse(buffer, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/assets/upload")
async def upload_assets(
    project_key: str = Form(...),
    project_id: int | None = Form(None),
    company_name: str = Form(""),
    keyword: str = Form(""),
    prompt_keywords: str = Form(""),
    project_keywords: str = Form(""),
    industry_key: str = Form(""),
    role: str = Form(""),
    source: str = Form("UPLOAD"),
    tags: str = Form(""),
    caption: str = Form(""),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Drag & Drop용 다중 업로드 API.

    여러 파일을 한 번에 받아 모두 project_asset_service를 통해 저장합니다.
    최초 업로드 상태는 role=PENDING, status=READY, source=UPLOAD입니다.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    user_keywords, industry_keywords = _load_default_keyword_sources(db, user, industry_key)
    assets: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    try:
        for idx, upload in enumerate(files, start=1):
            original_name = upload.filename or f"asset_{idx}.jpg"
            content_type = upload.content_type or "application/octet-stream"
            try:
                content = await upload.read()
                if not content:
                    failed.append({"filename": original_name, "reason": "empty file"})
                    continue
                asset = save_project_asset(
                    db=db,
                    user_id=user.id,
                    username=getattr(user, "username", "") or "",
                    project_id=project_id,
                    project_key=project_key,
                    file_bytes=content,
                    original_filename=original_name,
                    asset_type=_guess_asset_type(upload),
                    role=role or "PENDING",
                    company_name=company_name or project_key,
                    keyword=keyword or project_key,
                    prompt_keywords=prompt_keywords,
                    project_keywords=project_keywords or keyword,
                    user_keywords=user_keywords,
                    industry_keywords=industry_keywords,
                    caption=caption,
                    mime_type=content_type,
                    source=source or "UPLOAD",
                    status="READY",
                    tags=tags,
                    sequence=idx,
                    display_order=idx,
                    deactivate_previous=False,
                )
                assets.append(to_editor_asset_response(asset))
            except Exception as item_exc:
                failed.append({"filename": original_name, "reason": str(item_exc)})
        db.commit()
        return {
            "ok": True,
            "count": len(assets),
            "failed_count": len(failed),
            "assets": assets,
            "project_assets": assets,
            "failed": failed,
            "data": {"assets": assets, "failed": failed},
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/assets/{asset_id}")
def delete_asset_soft(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """자산 소프트 딜리트 API.

    물리 파일은 삭제하지 않고 status=DELETED, is_active=0으로 전환합니다.
    Copy Studio와 복구 플로우가 안전하게 동작하도록 파일 원본은 보존합니다.
    """
    try:
        row = soft_delete_project_asset(db, asset_id=asset_id, user_id=user.id)
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Asset not found")
        db.commit()
        asset = to_editor_asset_response(row)
        return {"ok": True, "deleted": True, "asset": asset, "data": asset}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/assets/{asset_id}/restore")
def restore_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """자산 복구 API.

    복구 대상과 같은 프로젝트/role의 다른 활성 자산을 먼저 비활성화한 뒤,
    복구 대상만 status=READY, is_active=1로 올립니다.
    """
    try:
        row = restore_project_asset(db, asset_id=asset_id, user_id=user.id)
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Asset not found")
        db.commit()
        asset = to_editor_asset_response(row)
        return {"ok": True, "restored": True, "asset": asset, "data": asset}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/assets/{asset_id}/role")
def update_asset_role(
    asset_id: int,
    req: AssetRoleUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """에셋 Role 변경 API.

    role이 바뀌면 project_asset_service의 20개 한글 ALT 템플릿 로직이 다시 돌고,
    새 alt_text까지 함께 반환됩니다.
    """
    try:
        row = update_project_asset_metadata(
            db,
            asset_id=asset_id,
            user_id=user.id,
            role=req.role,
            alt_text=req.alt_text,
            caption=req.caption,
            tags=req.tags,
            display_order=req.display_order,
            status=req.status,
            is_active=req.is_active,
        )
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="Asset not found")
        db.commit()
        asset = to_editor_asset_response(row)
        return {"ok": True, "asset": asset, "data": asset}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
