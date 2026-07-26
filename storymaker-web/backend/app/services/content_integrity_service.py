from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.database import engine

REPRESENTATIVE_TYPES = {"mp3", "srt", "mp4", "thumbnail"}
OUTPUT_ROOT = Path("/data/output_results")
MOBILE_ROOT = OUTPUT_ROOT / "mobile_one_shot"
TRASH_ROOT = OUTPUT_ROOT / "cleanup_trash"
AUDIT_ROOT = OUTPUT_ROOT / "integrity_audit"
TOMBSTONE_ROOT = TRASH_ROOT / "deleted_job_tombstones"


def _job_tombstone_path(job_id: str) -> Path:
    return TOMBSTONE_ROOT / f"{job_id}.json"


def _job_is_deleted(job_id: str) -> bool:
    return bool(job_id) and _job_tombstone_path(job_id).exists()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_audit(event: str, payload: dict[str, Any]) -> None:
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    row = {"at": _now(), "event": event, **payload}
    with (AUDIT_ROOT / "content_integrity.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _completed_state(status: str, media: dict[str, Any]) -> tuple[str, str, int, str, str, str | None]:
    normalized = str(status or "").strip().lower()
    has_mp4 = bool(media.get("mp4_path") or media.get("mp4_url"))
    completed = normalized in {"completed", "shortform_completed", "thumbnail_done", "thumbnail_completed"} or has_mp4
    if completed:
        return "completed", "completed", 100, "completed", "제작 완료", _now()
    return str(status or "created")[:80], "", 0, "", "", None


def ensure_parent_job(data: dict[str, Any], result_path: str = "") -> bool:
    job_id = str(data.get("job_id") or "").strip()
    user_id = int(data.get("user_bucket") or data.get("user_id") or 0)
    if not job_id or not user_id:
        return False
    if _job_is_deleted(job_id):
        return False

    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    media = data.get("media") if isinstance(data.get("media"), dict) else {}
    title = str(
        data.get("memo")
        or data.get("title")
        or outputs.get("blog_titles")
        or outputs.get("BLOG_TITLES")
        or job_id
    ).strip().splitlines()[0][:500]
    now = str(data.get("updated_at") or data.get("created_at") or _now())
    created = str(data.get("created_at") or now)
    raw_status = str(data.get("status") or media.get("status") or "created")[:80]
    status, stage, percent, worker_status, progress_message, completed_at = _completed_state(raw_status, media)

    values = {
        "job_id": job_id,
        "user_id": user_id,
        "persona_id": (data.get("persona") or {}).get("id") if isinstance(data.get("persona"), dict) else None,
        "status": status,
        "memo": title,
        "created_date": str(data.get("created_date") or "")[:10],
        "result_path": str(result_path or data.get("result_path") or ""),
        "image_count": int(data.get("image_count") or len(data.get("images") or [])),
        "has_text": 1 if data.get("raw_result") or outputs else 0,
        "has_mp3": 1 if media.get("mp3_path") or media.get("mp3_url") else 0,
        "has_mp4": 1 if media.get("mp4_path") or media.get("mp4_url") else 0,
        "has_thumbnail": 1 if media.get("thumbnail_path") or media.get("thumbnail_url") else 0,
        "error_message": str(data.get("error") or media.get("error") or "")[:500],
        "created_at": created,
        "updated_at": now,
        "completed_at": completed_at,
        "stage": stage,
        "percent": percent,
        "worker_status": worker_status,
        "progress_message": progress_message,
    }

    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT user_id FROM mobile_one_shot_jobs WHERE job_id=:job_id"),
            {"job_id": job_id},
        ).first()
        if existing and int(existing[0]) != user_id:
            _append_audit("parent_owner_conflict", {"job_id": job_id, "existing_user_id": int(existing[0]), "incoming_user_id": user_id})
            raise ValueError(f"job_id owner conflict: {job_id}")

        connection.execute(text("""
            INSERT INTO mobile_one_shot_jobs(
                job_id,user_id,persona_id,status,memo,created_date,result_path,image_count,
                has_text,has_mp3,has_mp4,has_thumbnail,error_message,created_at,updated_at,
                completed_at,stage,percent,worker_status,progress_message
            ) VALUES(
                :job_id,:user_id,:persona_id,:status,:memo,:created_date,:result_path,:image_count,
                :has_text,:has_mp3,:has_mp4,:has_thumbnail,:error_message,:created_at,:updated_at,
                :completed_at,:stage,:percent,:worker_status,:progress_message
            )
            ON CONFLICT(job_id) DO UPDATE SET
                status=excluded.status,
                memo=CASE WHEN excluded.memo<>'' THEN excluded.memo ELSE mobile_one_shot_jobs.memo END,
                result_path=CASE WHEN excluded.result_path<>'' THEN excluded.result_path ELSE mobile_one_shot_jobs.result_path END,
                image_count=MAX(mobile_one_shot_jobs.image_count,excluded.image_count),
                has_text=MAX(mobile_one_shot_jobs.has_text,excluded.has_text),
                has_mp3=MAX(mobile_one_shot_jobs.has_mp3,excluded.has_mp3),
                has_mp4=MAX(mobile_one_shot_jobs.has_mp4,excluded.has_mp4),
                has_thumbnail=MAX(mobile_one_shot_jobs.has_thumbnail,excluded.has_thumbnail),
                completed_at=COALESCE(excluded.completed_at,mobile_one_shot_jobs.completed_at),
                stage=CASE WHEN excluded.stage<>'' THEN excluded.stage ELSE mobile_one_shot_jobs.stage END,
                percent=MAX(mobile_one_shot_jobs.percent,excluded.percent),
                worker_status=CASE WHEN excluded.worker_status<>'' THEN excluded.worker_status ELSE mobile_one_shot_jobs.worker_status END,
                progress_message=CASE WHEN excluded.progress_message<>'' THEN excluded.progress_message ELSE mobile_one_shot_jobs.progress_message END,
                updated_at=excluded.updated_at
        """), values)
    return True


def normalize_completed_jobs() -> int:
    with engine.begin() as connection:
        result = connection.execute(text("""
            UPDATE mobile_one_shot_jobs
            SET status='completed',stage='completed',percent=100,worker_status='completed',
                progress_message='제작 완료',completed_at=COALESCE(completed_at,updated_at)
            WHERE (status IN ('completed','shortform_completed','thumbnail_done','thumbnail_completed') OR has_mp4=1)
              AND (percent<>100 OR COALESCE(stage,'')<>'completed' OR COALESCE(worker_status,'')<>'completed'
                   OR COALESCE(progress_message,'')<>'제작 완료')
        """))
    return int(result.rowcount or 0)


def restore_orphan_document_parents() -> int:
    now = _now()
    restored = 0
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT d.job_id,d.user_id,MIN(d.created_at) created_at,MAX(d.updated_at) updated_at,
                   MAX(CASE WHEN d.content_type='blog_titles' THEN d.content ELSE '' END) blog_titles
            FROM content_documents d
            LEFT JOIN mobile_one_shot_jobs j ON j.job_id=d.job_id AND j.user_id=d.user_id
            WHERE j.id IS NULL
            GROUP BY d.job_id,d.user_id
        """)).mappings().all()
        for row in rows:
            title = str(row["blog_titles"] or row["job_id"]).strip().splitlines()[0][:500]
            connection.execute(text("""
                INSERT INTO mobile_one_shot_jobs(
                    job_id,user_id,status,memo,created_date,result_path,image_count,has_text,has_mp3,has_mp4,
                    has_thumbnail,error_message,created_at,updated_at,completed_at,stage,percent,queue_position,
                    ahead_count,worker_status,progress_message
                ) VALUES(
                    :job_id,:user_id,'recovered',:memo,'','',0,1,0,0,0,'',:created_at,:updated_at,NULL,
                    'recovered_from_documents',100,0,0,'recovered','DB 문서에서 부모 작업 복원'
                )
            """), {
                "job_id": row["job_id"], "user_id": row["user_id"], "memo": title,
                "created_at": row["created_at"] or now, "updated_at": row["updated_at"] or now,
            })
            restored += 1
    return restored


def backfill_missing_checksums(limit: int = 1000) -> dict[str, int]:
    updated = 0
    missing = 0
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT id,stored_path FROM content_archive_assets
            WHERE COALESCE(stored_path,'')<>'' AND COALESCE(checksum,'')=''
            ORDER BY id LIMIT :limit
        """), {"limit": int(limit)}).mappings().all()
        for row in rows:
            path = Path(str(row["stored_path"]))
            if not path.exists() or not path.is_file():
                missing += 1
                continue
            connection.execute(text("""
                UPDATE content_archive_assets
                SET checksum=:checksum,file_size=:file_size,storage_type='local',updated_at=:updated_at
                WHERE id=:id
            """), {
                "checksum": _file_checksum(path), "file_size": path.stat().st_size,
                "updated_at": _now(), "id": row["id"],
            })
            updated += 1
    return {"updated": updated, "missing": missing}


def audit_missing_orphan_assets() -> list[dict[str, Any]]:
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT a.id,a.user_id,a.archive_job_id,a.asset_type,a.stored_path
            FROM content_archive_assets a
            LEFT JOIN mobile_one_shot_jobs j ON j.job_id=a.archive_job_id AND j.user_id=a.user_id
            WHERE j.id IS NULL
            ORDER BY a.id
        """)).mappings().all()
    findings = []
    for row in rows:
        item = dict(row)
        item["file_exists"] = Path(str(row["stored_path"] or "")).exists()
        findings.append(item)
    if findings:
        _append_audit("orphan_asset_audit", {"count": len(findings), "items": findings})
    return findings


def delete_job_bundle(user_id: int, job_id: str, delete_files: bool = True) -> dict[str, Any]:
    with engine.begin() as connection:
        job = connection.execute(text("""
            SELECT result_path FROM mobile_one_shot_jobs WHERE user_id=:user_id AND job_id=:job_id
        """), {"user_id": user_id, "job_id": job_id}).mappings().first()
    result_path = str(job["result_path"] or "") if job else ""
    original_folder: Path | None = None
    trash_folder: Path | None = None
    TOMBSTONE_ROOT.mkdir(parents=True, exist_ok=True)
    tombstone_path = _job_tombstone_path(job_id)
    tombstone_path.write_text(json.dumps({
        "job_id": job_id,
        "user_id": user_id,
        "deleted_at": _now(),
        "result_path": result_path,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    if delete_files and result_path:
        result_file = Path(result_path)
        candidate = result_file.parent
        if candidate.exists() and MOBILE_ROOT in candidate.parents:
            TRASH_ROOT.mkdir(parents=True, exist_ok=True)
            trash_folder = TRASH_ROOT / f"{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            try:
                shutil.move(str(candidate), str(trash_folder))
                original_folder = candidate
            except Exception as exc:
                _append_audit("delete_move_failed", {"user_id": user_id, "job_id": job_id, "folder": str(candidate), "error": str(exc)})
                return {"jobs": 0, "documents": 0, "assets": 0, "folder_deleted": False, "moved_to_trash": False, "error": "folder_move_failed"}

    try:
        with engine.begin() as connection:
            doc_count = connection.execute(text("DELETE FROM content_documents WHERE user_id=:user_id AND job_id=:job_id"), {"user_id": user_id, "job_id": job_id}).rowcount
            asset_count = connection.execute(text("DELETE FROM content_archive_assets WHERE user_id=:user_id AND archive_job_id=:job_id"), {"user_id": user_id, "job_id": job_id}).rowcount
            job_count = connection.execute(text("DELETE FROM mobile_one_shot_jobs WHERE user_id=:user_id AND job_id=:job_id"), {"user_id": user_id, "job_id": job_id}).rowcount
    except Exception as exc:
        if trash_folder and original_folder and trash_folder.exists() and not original_folder.exists():
            try:
                shutil.move(str(trash_folder), str(original_folder))
            except Exception:
                pass
        _append_audit("delete_db_failed", {"user_id": user_id, "job_id": job_id, "error": str(exc)})
        raise

    _append_audit("delete_bundle", {
        "user_id": user_id,
        "job_id": job_id,
        "jobs": int(job_count or 0),
        "documents": int(doc_count or 0),
        "assets": int(asset_count or 0),
        "trash_path": str(trash_folder or ""),
    })
    return {
        "jobs": int(job_count or 0),
        "documents": int(doc_count or 0),
        "assets": int(asset_count or 0),
        "folder_deleted": False,
        "moved_to_trash": bool(trash_folder),
        "trash_path": str(trash_folder or ""),
    }
