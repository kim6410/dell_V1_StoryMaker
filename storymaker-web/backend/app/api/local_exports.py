# -*- coding: utf-8 -*-
"""
StoryMaker Local exports manifest API.

This API stores metadata only. It must not receive or store absolute Windows
paths such as D:\\... and it must not upload local media files.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.database import engine, get_db
from app.db.models import User

router = APIRouter(prefix="/local/exports", tags=["Local Exports"])


class LocalExportFile(BaseModel):
    name: str = ""
    relative_path: str = ""
    suffix: str = ""
    size: int = 0
    mtime: str = ""


class LocalExportItem(BaseModel):
    local_id: str
    title: str = ""
    project_key: str = ""
    created_at: str = ""
    updated_at: str = ""
    has_mp3: bool = False
    has_srt: bool = False
    has_mp4: bool = False
    has_result_json: bool = False
    mp3_size: int = 0
    srt_size: int = 0
    mp4_size: int = 0
    result_json_size: int = 0
    total_size: int = 0
    file_count: int = 0
    files: list[LocalExportFile] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LocalExportsManifest(BaseModel):
    schema_version: str = "0.1"
    app_version: str = ""
    generated_at: str = ""
    exports_label: str = "이 PC의 exports 폴더"
    device_id: str
    device_name: str = "Windows PC"
    item_count: int = 0
    items: list[LocalExportItem] = Field(default_factory=list)


def _now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def migrate_local_exports_manifest_table() -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS local_export_manifest_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_id VARCHAR(80) NOT NULL,
                device_name VARCHAR(160) DEFAULT '' NOT NULL,
                local_id VARCHAR(120) NOT NULL,
                title TEXT DEFAULT '' NOT NULL,
                project_key VARCHAR(160) DEFAULT '' NOT NULL,
                app_version VARCHAR(40) DEFAULT '' NOT NULL,
                generated_at VARCHAR(40) DEFAULT '' NOT NULL,
                created_at VARCHAR(40) DEFAULT '' NOT NULL,
                updated_at VARCHAR(40) DEFAULT '' NOT NULL,
                has_mp3 INTEGER DEFAULT 0 NOT NULL,
                has_srt INTEGER DEFAULT 0 NOT NULL,
                has_mp4 INTEGER DEFAULT 0 NOT NULL,
                has_result_json INTEGER DEFAULT 0 NOT NULL,
                mp3_size INTEGER DEFAULT 0 NOT NULL,
                srt_size INTEGER DEFAULT 0 NOT NULL,
                mp4_size INTEGER DEFAULT 0 NOT NULL,
                result_json_size INTEGER DEFAULT 0 NOT NULL,
                total_size INTEGER DEFAULT 0 NOT NULL,
                file_count INTEGER DEFAULT 0 NOT NULL,
                item_json TEXT DEFAULT '' NOT NULL,
                last_synced_at VARCHAR(40) DEFAULT '' NOT NULL,
                is_active INTEGER DEFAULT 1 NOT NULL,
                UNIQUE(user_id, device_id, local_id)
            )
        """))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_local_export_user_updated ON local_export_manifest_items (user_id, updated_at DESC)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_local_export_user_device ON local_export_manifest_items (user_id, device_id, updated_at DESC)"))


def _clean_text(value: Any, limit: int = 200) -> str:
    return str(value or "").strip()[:limit]


def _safe_relative_path(value: str) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    if not raw:
        return ""
    if ":" in raw or raw.startswith("/") or raw.startswith("~"):
        return ""
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        return ""
    return "/".join(parts)[:300]


def _safe_item_payload(item: LocalExportItem) -> dict[str, Any]:
    raw = item.model_dump()
    safe_files = []
    for file_item in item.files[:20]:
        file_data = file_item.model_dump()
        file_data["name"] = _clean_text(file_data.get("name"), 180)
        file_data["relative_path"] = _safe_relative_path(file_data.get("relative_path", ""))
        file_data["suffix"] = _clean_text(file_data.get("suffix"), 20).lower()
        file_data["size"] = max(0, int(file_data.get("size") or 0))
        safe_files.append(file_data)
    raw["files"] = safe_files
    raw["title"] = _clean_text(raw.get("title"), 160)
    raw["project_key"] = _clean_text(raw.get("project_key"), 160)
    return raw


@router.post("/sync")
def sync_local_exports_manifest(
    manifest: LocalExportsManifest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    migrate_local_exports_manifest_table()
    device_id = _clean_text(manifest.device_id, 80)
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id가 필요합니다.")
    device_name = _clean_text(manifest.device_name, 160) or "Windows PC"
    now_text = _now_text()
    items = manifest.items[:500]
    synced = 0
    with engine.begin() as connection:
        for item in items:
            local_id = _clean_text(item.local_id, 120)
            if not local_id:
                continue
            safe_payload = _safe_item_payload(item)
            connection.execute(text("""
                INSERT INTO local_export_manifest_items (
                    user_id, device_id, device_name, local_id, title, project_key,
                    app_version, generated_at, created_at, updated_at,
                    has_mp3, has_srt, has_mp4, has_result_json,
                    mp3_size, srt_size, mp4_size, result_json_size, total_size, file_count,
                    item_json, last_synced_at, is_active
                ) VALUES (
                    :user_id, :device_id, :device_name, :local_id, :title, :project_key,
                    :app_version, :generated_at, :created_at, :updated_at,
                    :has_mp3, :has_srt, :has_mp4, :has_result_json,
                    :mp3_size, :srt_size, :mp4_size, :result_json_size, :total_size, :file_count,
                    :item_json, :last_synced_at, 1
                )
                ON CONFLICT(user_id, device_id, local_id) DO UPDATE SET
                    device_name = excluded.device_name,
                    title = excluded.title,
                    project_key = excluded.project_key,
                    app_version = excluded.app_version,
                    generated_at = excluded.generated_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    has_mp3 = excluded.has_mp3,
                    has_srt = excluded.has_srt,
                    has_mp4 = excluded.has_mp4,
                    has_result_json = excluded.has_result_json,
                    mp3_size = excluded.mp3_size,
                    srt_size = excluded.srt_size,
                    mp4_size = excluded.mp4_size,
                    result_json_size = excluded.result_json_size,
                    total_size = excluded.total_size,
                    file_count = excluded.file_count,
                    item_json = excluded.item_json,
                    last_synced_at = excluded.last_synced_at,
                    is_active = 1
            """), {
                "user_id": current_user.id,
                "device_id": device_id,
                "device_name": device_name,
                "local_id": local_id,
                "title": _clean_text(item.title, 160),
                "project_key": _clean_text(item.project_key, 160),
                "app_version": _clean_text(manifest.app_version, 40),
                "generated_at": _clean_text(manifest.generated_at, 40),
                "created_at": _clean_text(item.created_at, 40),
                "updated_at": _clean_text(item.updated_at, 40),
                "has_mp3": 1 if item.has_mp3 else 0,
                "has_srt": 1 if item.has_srt else 0,
                "has_mp4": 1 if item.has_mp4 else 0,
                "has_result_json": 1 if item.has_result_json else 0,
                "mp3_size": max(0, int(item.mp3_size or 0)),
                "srt_size": max(0, int(item.srt_size or 0)),
                "mp4_size": max(0, int(item.mp4_size or 0)),
                "result_json_size": max(0, int(item.result_json_size or 0)),
                "total_size": max(0, int(item.total_size or 0)),
                "file_count": max(0, int(item.file_count or 0)),
                "item_json": json.dumps(safe_payload, ensure_ascii=False),
                "last_synced_at": now_text,
            })
            synced += 1
    return {"ok": True, "data": {"synced": synced, "device_id": device_id, "device_name": device_name, "last_synced_at": now_text}, "message": "로컬 보관함 manifest가 동기화되었습니다."}


@router.get("/items")
def list_local_export_items(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    migrate_local_exports_manifest_table()
    safe_limit = max(1, min(int(limit or 50), 100))
    safe_offset = max(0, int(offset or 0))
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT local_id, device_id, device_name, title, project_key, app_version,
                   created_at, updated_at, has_mp3, has_srt, has_mp4, has_result_json,
                   mp3_size, srt_size, mp4_size, result_json_size, total_size, file_count,
                   item_json, last_synced_at
            FROM local_export_manifest_items
            WHERE user_id = :user_id AND is_active = 1
            ORDER BY updated_at DESC, last_synced_at DESC
            LIMIT :limit OFFSET :offset
        """), {"user_id": current_user.id, "limit": safe_limit, "offset": safe_offset}).mappings().fetchall()
    items = []
    for row in rows:
        item = dict(row)
        try:
            payload = json.loads(item.pop("item_json") or "{}")
        except Exception:
            payload = {}
        item["storage_type"] = "local"
        item["source_label"] = "로컬 보관"
        item["open_protocol_url"] = f"storymaker-local://open?device_id={item.get('device_id')}&local_id={item.get('local_id')}"
        item["files"] = payload.get("files") if isinstance(payload, dict) else []
        items.append(item)
    return {"ok": True, "data": {"items": items, "limit": safe_limit, "offset": safe_offset}, "message": ""}
