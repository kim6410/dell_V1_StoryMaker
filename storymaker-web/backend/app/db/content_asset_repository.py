# -*- coding: utf-8 -*-
"""StoryMaker 콘텐츠 보관함 공통 미디어 자산 저장소."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.db.database import engine


TABLE_NAME = "content_archive_assets"


def migrate_content_archive_assets_table() -> None:
    with engine.begin() as connection:
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archive_job_id VARCHAR(80) NOT NULL,
                archive_group_key VARCHAR(180) DEFAULT '' NOT NULL,
                user_id INTEGER NOT NULL,
                source_menu VARCHAR(40) DEFAULT 'unknown' NOT NULL,
                source_job_id VARCHAR(160) DEFAULT '' NOT NULL,
                asset_type VARCHAR(30) NOT NULL,
                asset_order INTEGER DEFAULT 0 NOT NULL,
                stored_path TEXT DEFAULT '' NOT NULL,
                public_url TEXT DEFAULT '' NOT NULL,
                original_filename TEXT DEFAULT '' NOT NULL,
                download_name TEXT DEFAULT '' NOT NULL,
                mime_type VARCHAR(120) DEFAULT '' NOT NULL,
                file_size INTEGER DEFAULT 0 NOT NULL,
                status VARCHAR(30) DEFAULT 'ready' NOT NULL,
                created_at VARCHAR(40) NOT NULL,
                updated_at VARCHAR(40) NOT NULL,
                UNIQUE(user_id, archive_job_id, source_menu, source_job_id, asset_type, asset_order)
            )
        """))
        connection.execute(text(
            f"CREATE INDEX IF NOT EXISTS ix_{TABLE_NAME}_archive ON {TABLE_NAME} (user_id, archive_job_id, asset_type, asset_order)"
        ))
        connection.execute(text(
            f"CREATE INDEX IF NOT EXISTS ix_{TABLE_NAME}_group ON {TABLE_NAME} (user_id, archive_group_key, asset_type)"
        ))
        connection.execute(text(
            f"CREATE INDEX IF NOT EXISTS ix_{TABLE_NAME}_source ON {TABLE_NAME} (source_menu, source_job_id)"
        ))


def upsert_content_archive_assets(
    *,
    user_id: int,
    archive_job_id: str,
    archive_group_key: str,
    source_menu: str,
    source_job_id: str,
    assets: list[dict[str, Any]],
    created_at: str,
    updated_at: str,
) -> list[int]:
    if not user_id or not archive_job_id or not assets:
        return []

    ids: list[int] = []
    with engine.begin() as connection:
        for item in assets:
            values = {
                "archive_job_id": str(archive_job_id)[:80],
                "archive_group_key": str(archive_group_key or "")[:180],
                "user_id": int(user_id),
                "source_menu": str(source_menu or "unknown")[:40],
                "source_job_id": str(source_job_id or archive_job_id)[:160],
                "asset_type": str(item.get("asset_type") or "file")[:30],
                "asset_order": max(0, int(item.get("asset_order") or 0)),
                "stored_path": str(item.get("stored_path") or ""),
                "public_url": str(item.get("public_url") or ""),
                "original_filename": str(item.get("original_filename") or "")[:500],
                "download_name": str(item.get("download_name") or "")[:500],
                "mime_type": str(item.get("mime_type") or "")[:120],
                "file_size": max(0, int(item.get("file_size") or 0)),
                "status": str(item.get("status") or "ready")[:30],
                "created_at": created_at,
                "updated_at": updated_at,
            }
            connection.execute(text(f"""
                INSERT INTO {TABLE_NAME} (
                    archive_job_id, archive_group_key, user_id, source_menu, source_job_id,
                    asset_type, asset_order, stored_path, public_url, original_filename,
                    download_name, mime_type, file_size, status, created_at, updated_at
                ) VALUES (
                    :archive_job_id, :archive_group_key, :user_id, :source_menu, :source_job_id,
                    :asset_type, :asset_order, :stored_path, :public_url, :original_filename,
                    :download_name, :mime_type, :file_size, :status, :created_at, :updated_at
                )
                ON CONFLICT(user_id, archive_job_id, source_menu, source_job_id, asset_type, asset_order)
                DO UPDATE SET
                    archive_group_key = excluded.archive_group_key,
                    stored_path = excluded.stored_path,
                    public_url = excluded.public_url,
                    original_filename = excluded.original_filename,
                    download_name = excluded.download_name,
                    mime_type = excluded.mime_type,
                    file_size = excluded.file_size,
                    status = excluded.status,
                    updated_at = excluded.updated_at
            """), values)
            row = connection.execute(text(f"""
                SELECT id FROM {TABLE_NAME}
                WHERE user_id = :user_id
                  AND archive_job_id = :archive_job_id
                  AND source_menu = :source_menu
                  AND source_job_id = :source_job_id
                  AND asset_type = :asset_type
                  AND asset_order = :asset_order
                LIMIT 1
            """), values).first()
            if row:
                ids.append(int(row[0]))

        for representative_type in ("mp3", "srt", "mp4", "thumbnail"):
            connection.execute(text(f"""
                DELETE FROM {TABLE_NAME}
                WHERE user_id = :user_id
                  AND archive_job_id = :archive_job_id
                  AND asset_type = :asset_type
                  AND id NOT IN (
                      SELECT id FROM {TABLE_NAME}
                      WHERE user_id = :user_id
                        AND archive_job_id = :archive_job_id
                        AND asset_type = :asset_type
                      ORDER BY updated_at DESC, id DESC
                      LIMIT 1
                  )
            """), {
                "user_id": int(user_id),
                "archive_job_id": str(archive_job_id)[:80],
                "asset_type": representative_type,
            })
    return ids


def list_content_archive_assets(user_id: int, archive_job_id: str) -> list[dict[str, Any]]:
    if not user_id or not archive_job_id:
        return []
    with engine.begin() as connection:
        rows = connection.execute(text(f"""
            SELECT id, archive_job_id, archive_group_key, user_id, source_menu, source_job_id,
                   asset_type, asset_order, stored_path, public_url, original_filename,
                   download_name, mime_type, file_size, status, created_at, updated_at
            FROM {TABLE_NAME}
            WHERE user_id = :user_id AND archive_job_id = :archive_job_id AND status = 'ready'
            ORDER BY CASE asset_type
                WHEN 'image' THEN 1
                WHEN 'thumbnail' THEN 2
                WHEN 'mp3' THEN 3
                WHEN 'mp4' THEN 4
                WHEN 'srt' THEN 5
                ELSE 9 END,
                asset_order ASC,
                id DESC
        """), {"user_id": int(user_id), "archive_job_id": str(archive_job_id)}).mappings().fetchall()
        return [dict(row) for row in rows]


def get_content_archive_asset(asset_id: int, user_id: int) -> dict[str, Any]:
    if not asset_id or not user_id:
        return {}
    with engine.begin() as connection:
        row = connection.execute(text(f"""
            SELECT id, archive_job_id, archive_group_key, user_id, source_menu, source_job_id,
                   asset_type, asset_order, stored_path, public_url, original_filename,
                   download_name, mime_type, file_size, status, created_at, updated_at
            FROM {TABLE_NAME}
            WHERE id = :asset_id AND user_id = :user_id AND status = 'ready'
            LIMIT 1
        """), {"asset_id": int(asset_id), "user_id": int(user_id)}).mappings().first()
        return dict(row) if row else {}


def list_missing_content_archive_asset_jobs(limit: int = 200) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 200), 1000))
    with engine.begin() as connection:
        rows = connection.execute(text(f"""
            SELECT jobs.job_id, jobs.user_id, jobs.result_path, jobs.created_at
            FROM mobile_one_shot_jobs AS jobs
            WHERE jobs.result_path != ''
              AND NOT EXISTS (
                  SELECT 1 FROM {TABLE_NAME} AS assets
                  WHERE assets.user_id = jobs.user_id
                    AND assets.archive_job_id = jobs.job_id
              )
            ORDER BY jobs.created_at DESC
            LIMIT :limit
        """), {"limit": safe_limit}).mappings().fetchall()
        return [dict(row) for row in rows]


def delete_content_archive_assets(user_id: int, archive_job_id: str) -> int:
    if not user_id or not archive_job_id:
        return 0
    with engine.begin() as connection:
        result = connection.execute(text(f"""
            DELETE FROM {TABLE_NAME}
            WHERE user_id = :user_id AND archive_job_id = :archive_job_id
        """), {"user_id": int(user_id), "archive_job_id": str(archive_job_id)})
        return int(result.rowcount or 0)
