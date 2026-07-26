from __future__ import annotations

import hashlib
import json
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from app.db.database import engine

DOCUMENT_ALIASES = {
    "blog_titles": ("blog_titles", "BLOG_TITLES"),
    "blog_post": ("blog_post", "BLOG_POST"),
    "instagram": ("instagram", "INSTAGRAM_POST"),
    "carrot": ("carrot", "CARROT"),
    "naver_place": ("naver_place", "place", "NAVER_PLACE"),
    "google_business": ("google_business", "GOOGLE_BUSINESS_PROFILE", "GBP"),
    "podcast_50": ("podcast50", "podcast_50", "PODCAST_50"),
    "podcast_80": ("podcast80", "podcast_80", "PODCAST_80"),
    "cardnews": ("cardnews", "CAROUSEL", "CARDNEWS"),
    "hashtags": ("hashtags", "blog_hashtags", "HASHTAGS"),
}

ASSET_FIELDS = {
    "mp3": ("mp3_path", "mp3_url", "audio/mpeg"),
    "srt": ("srt_path", "srt_url", "application/x-subrip"),
    "mp4": ("mp4_path", "mp4_url", "video/mp4"),
    "thumbnail": ("thumbnail_path", "thumbnail_url", "image/jpeg"),
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_content_storage_schema() -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS content_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id VARCHAR(80) NOT NULL,
                user_id INTEGER NOT NULL,
                content_type VARCHAR(80) NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                status VARCHAR(40) NOT NULL DEFAULT 'active',
                created_at VARCHAR(40) NOT NULL,
                updated_at VARCHAR(40) NOT NULL,
                UNIQUE(job_id, user_id, content_type)
            )
        """))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_content_documents_job_user ON content_documents(job_id, user_id)"))
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(content_archive_assets)").fetchall()}
        additions = {
            "storage_type": "VARCHAR(20) NOT NULL DEFAULT 'local'",
            "checksum": "VARCHAR(64) NOT NULL DEFAULT ''",
            "duration": "REAL",
            "width": "INTEGER",
            "height": "INTEGER",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.exec_driver_sql(f"ALTER TABLE content_archive_assets ADD COLUMN {name} {definition}")
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_archive_assets_job_type ON content_archive_assets(archive_job_id, user_id, asset_type)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_archive_assets_checksum ON content_archive_assets(user_id, archive_job_id, asset_type, checksum)"))
        for representative_type in ("mp3", "srt", "mp4", "thumbnail"):
            connection.execute(text("""
                DELETE FROM content_archive_assets AS duplicate
                WHERE duplicate.asset_type = :asset_type
                  AND duplicate.id <> (
                      SELECT keeper.id
                      FROM content_archive_assets AS keeper
                      WHERE keeper.user_id = duplicate.user_id
                        AND keeper.archive_job_id = duplicate.archive_job_id
                        AND keeper.asset_type = duplicate.asset_type
                      ORDER BY
                        CASE WHEN length(coalesce(keeper.checksum, '')) = 64 THEN 1 ELSE 0 END DESC,
                        CASE WHEN length(coalesce(keeper.stored_path, '')) > 0 THEN 1 ELSE 0 END DESC,
                        CASE WHEN length(coalesce(keeper.public_url, '')) > 0 THEN 1 ELSE 0 END DESC,
                        keeper.updated_at DESC,
                        keeper.id DESC
                      LIMIT 1
                  )
            """), {"asset_type": representative_type})


def _pick(outputs: dict[str, Any], aliases: tuple[str, ...]) -> str:
    lowered = {str(k).lower(): v for k, v in outputs.items()}
    for alias in aliases:
        value = outputs.get(alias, lowered.get(alias.lower()))
        if value is not None and str(value).strip():
            return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    return ""


def sync_documents_from_result(data: dict[str, Any]) -> int:
    ensure_content_storage_schema()
    job_id = str(data.get("job_id") or "").strip()
    user_id = int(data.get("user_bucket") or data.get("user_id") or 0)
    if not job_id or not user_id:
        return 0
    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    title = str(data.get("memo") or data.get("title") or "").strip()
    now = _now()
    saved = 0
    with engine.begin() as connection:
        for content_type, aliases in DOCUMENT_ALIASES.items():
            content = _pick(outputs, aliases)
            if not content:
                continue
            row = connection.execute(text("SELECT id,content,version FROM content_documents WHERE job_id=:job_id AND user_id=:user_id AND content_type=:content_type LIMIT 1"), {"job_id": job_id, "user_id": user_id, "content_type": content_type}).mappings().first()
            if row:
                version = int(row["version"] or 1) + (1 if str(row["content"]) != content else 0)
                connection.execute(text("UPDATE content_documents SET title=:title,content=:content,version=:version,status='active',updated_at=:updated_at WHERE id=:id"), {"title": title, "content": content, "version": version, "updated_at": now, "id": row["id"]})
            else:
                connection.execute(text("INSERT INTO content_documents(job_id,user_id,content_type,title,content,version,status,created_at,updated_at) VALUES(:job_id,:user_id,:content_type,:title,:content,1,'active',:created_at,:updated_at)"), {"job_id": job_id, "user_id": user_id, "content_type": content_type, "title": title, "content": content, "created_at": now, "updated_at": now})
            saved += 1
    return saved


def _real_file(value: Any) -> Path | None:
    raw = str(value or "").split("?", 1)[0]
    if not raw.startswith("/"):
        return None
    path = Path(raw)
    try:
        return path if path.is_file() and path.stat().st_size > 0 else None
    except OSError:
        return None


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sync_assets_from_result(data: dict[str, Any]) -> int:
    ensure_content_storage_schema()
    job_id = str(data.get("job_id") or "").strip()
    group_key = str(data.get("archive_group_key") or data.get("source_job_id") or job_id).strip()
    user_id = int(data.get("user_bucket") or data.get("user_id") or 0)
    media = data.get("media") if isinstance(data.get("media"), dict) else {}
    if not job_id or not user_id:
        return 0
    now = _now()
    saved = 0
    with engine.begin() as connection:
        for asset_type, (path_key, url_key, default_mime) in ASSET_FIELDS.items():
            file_path = _real_file(media.get(path_key))
            if not file_path:
                if asset_type == "mp4":
                    connection.execute(text("UPDATE mobile_one_shot_jobs SET has_mp4=0,updated_at=:updated_at WHERE job_id=:job_id AND user_id=:user_id"), {"updated_at": now, "job_id": job_id, "user_id": user_id})
                continue
            checksum = _checksum(file_path)
            mime_type = mimetypes.guess_type(file_path.name)[0] or default_mime
            rows = connection.execute(text("SELECT id,source_menu,source_job_id FROM content_archive_assets WHERE user_id=:user_id AND archive_job_id=:job_id AND asset_type=:asset_type ORDER BY updated_at DESC,id DESC"), {"user_id": user_id, "job_id": job_id, "asset_type": asset_type}).all()
            preferred = next((item for item in rows if str(item[1] or "") == "mobile_one_shot" and str(item[2] or "") == group_key), None)
            row = preferred or (rows[0] if rows else None)
            params = {"archive_job_id": job_id, "archive_group_key": group_key, "user_id": user_id, "source_menu": "mobile_one_shot", "source_job_id": group_key, "asset_type": asset_type, "stored_path": str(file_path), "public_url": str(media.get(url_key) or ""), "original_filename": file_path.name, "download_name": file_path.name, "mime_type": mime_type, "file_size": file_path.stat().st_size, "status": "ready", "storage_type": "local", "checksum": checksum, "updated_at": now}
            if row:
                keeper_id = int(row[0])
                connection.execute(text("DELETE FROM content_archive_assets WHERE user_id=:user_id AND archive_job_id=:archive_job_id AND asset_type=:asset_type AND id<>:id"), {"user_id": user_id, "archive_job_id": job_id, "asset_type": asset_type, "id": keeper_id})
                params["id"] = keeper_id
                connection.execute(text("UPDATE content_archive_assets SET archive_group_key=:archive_group_key,source_menu=:source_menu,source_job_id=:source_job_id,stored_path=:stored_path,public_url=:public_url,original_filename=:original_filename,download_name=:download_name,mime_type=:mime_type,file_size=:file_size,status=:status,storage_type=:storage_type,checksum=:checksum,updated_at=:updated_at WHERE id=:id"), params)
            else:
                params["created_at"] = now
                connection.execute(text("INSERT INTO content_archive_assets(archive_job_id,archive_group_key,user_id,source_menu,source_job_id,asset_type,asset_order,stored_path,public_url,original_filename,download_name,mime_type,file_size,status,created_at,updated_at,storage_type,checksum) VALUES(:archive_job_id,:archive_group_key,:user_id,:source_menu,:source_job_id,:asset_type,0,:stored_path,:public_url,:original_filename,:download_name,:mime_type,:file_size,:status,:created_at,:updated_at,:storage_type,:checksum)"), params)
            flag = {"mp3": "has_mp3", "mp4": "has_mp4", "thumbnail": "has_thumbnail"}.get(asset_type)
            if flag:
                connection.execute(text(f"UPDATE mobile_one_shot_jobs SET {flag}=1,updated_at=:updated_at WHERE job_id=:job_id AND user_id=:user_id"), {"updated_at": now, "job_id": job_id, "user_id": user_id})
            saved += 1
    return saved


def load_documents(job_id: str, user_id: int) -> dict[str, str]:
    ensure_content_storage_schema()
    with engine.begin() as connection:
        rows = connection.execute(text("SELECT content_type,content FROM content_documents WHERE job_id=:job_id AND user_id=:user_id AND status='active' ORDER BY id"), {"job_id": job_id, "user_id": user_id}).mappings().all()
    return {str(row["content_type"]): str(row["content"] or "") for row in rows}


def sync_result_to_database(data: dict[str, Any], result_path: str = "") -> dict[str, int]:
    from app.services.content_integrity_service import ensure_parent_job
    ensure_parent_job(data, result_path=result_path)
    return {"documents": sync_documents_from_result(data), "assets": sync_assets_from_result(data)}
