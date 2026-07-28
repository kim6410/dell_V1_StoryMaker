from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.beta_storage import SHARED_IMAGE_DIR, prune_unreferenced_shared_images

ROOT = Path(os.getenv("STORYMAKER_BETA_ROOT", "/home/bourne/StoryMaker_1/StoryMaker_beta"))
BETA_DB = ROOT / "data" / "storymaker_beta.db"
JOBS_DIR = ROOT / "data" / "jobs"
V1_DB = Path(os.getenv("STORYMAKER_V1_DB_PATH", "/home/bourne/StoryMaker_1/database/storymaker.db"))
FREE_LIMIT = 10
PAID_LIMIT = 20
_RETENTION_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def archive_limit_for_user(user_id: int) -> int | None:
    """Administrators are unlimited, free users keep 10 and paid users keep 20."""
    safe_user_id = int(user_id or 0)
    if safe_user_id <= 0:
        return FREE_LIMIT
    if not V1_DB.is_file():
        return FREE_LIMIT
    try:
        with _connect(V1_DB) as connection:
            user = connection.execute(
                "SELECT role FROM users WHERE id=? LIMIT 1",
                (safe_user_id,),
            ).fetchone()
            role = str(user["role"] if user else "user").strip().lower()
            if role == "admin":
                return None
            billing = connection.execute(
                "SELECT COALESCE(current_plan_code,'free') AS plan "
                "FROM member_billing_profiles WHERE user_id=? LIMIT 1",
                (safe_user_id,),
            ).fetchone()
            plan = str(billing["plan"] if billing else "free").strip().lower()
            return FREE_LIMIT if plan in {"", "free"} else PAID_LIMIT
    except sqlite3.Error:
        return FREE_LIMIT


def _folder_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        try:
            total += item.stat().st_size
        except OSError:
            continue
    return total


def _shared_images(result: dict[str, Any]) -> list[Path]:
    assets = result.get("assets") if isinstance(result.get("assets"), dict) else {}
    found: list[Path] = []
    try:
        shared_root = SHARED_IMAGE_DIR.resolve()
    except OSError:
        return found
    for value in assets.get("images") or []:
        try:
            candidate = Path(str(value)).resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if candidate.parent == shared_root and candidate.is_file():
            found.append(candidate)
    return found


def _compact_result(result: dict[str, Any], job_id: str, deleted_at: str, deleted_bytes: int) -> dict[str, Any]:
    compact = dict(result or {})
    compact["beta_job_id"] = str(compact.get("beta_job_id") or job_id)
    compact["assets"] = {}
    shortform = compact.get("shortform")
    if isinstance(shortform, dict):
        compact["shortform"] = {
            key: value
            for key, value in shortform.items()
            if key not in {"assets", "output_dir", "mixed_audio", "shortform_video", "shortform_audio", "shortform_subtitle"}
        }
    browser_render = compact.get("browser_render")
    if isinstance(browser_render, dict):
        compact["browser_render"] = {
            key: value
            for key, value in browser_render.items()
            if key not in {"saved", "files", "paths"}
        }
    compact["media_deleted_at"] = deleted_at
    compact["media_deleted_bytes"] = int(deleted_bytes)
    compact["media_delete_reason"] = "archive_limit"
    return compact


def _compact_state(state: dict[str, Any], job_id: str, deleted_at: str) -> dict[str, Any]:
    compact = dict(state or {})
    compact["beta_job_id"] = str(compact.get("beta_job_id") or job_id)
    compact["media_deleted_at"] = deleted_at
    compact["media_delete_reason"] = "archive_limit"
    return compact


def _delete_one_preserve_metadata(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    job_id = str(row["beta_job_id"] or "").strip()
    if not job_id:
        return {"job_id": "", "files_deleted": False, "deleted_bytes": 0, "failed": True}
    job_dir = JOBS_DIR / job_id
    result_path = job_dir / "result.json"
    state_path = job_dir / "state.json"
    result = _read_json(result_path)
    state = _read_json(state_path)
    shared_images = _shared_images(result)
    original_bytes = _folder_size(job_dir)
    deleted_at = _now()
    quarantine = JOBS_DIR / f".__archive_limit__{job_id}"

    if quarantine.exists():
        if quarantine.is_dir():
            shutil.rmtree(quarantine)
        else:
            quarantine.unlink()

    moved = False
    try:
        if job_dir.exists():
            job_dir.replace(quarantine)
            moved = True
        job_dir.mkdir(parents=True, exist_ok=True)
        compact_result = _compact_result(result, job_id, deleted_at, original_bytes)
        compact_state = _compact_state(state, job_id, deleted_at)
        _write_json(result_path, compact_result)
        _write_json(state_path, compact_state)
        compact_bytes = _folder_size(job_dir)
        deleted_bytes = max(0, original_bytes - compact_bytes)
        connection.execute(
            "UPDATE beta_jobs SET media_deleted_at=?,media_deleted_bytes=?,media_delete_reason=?,"
            "selected_thumbnail_template='',selected_thumbnail_path='' WHERE beta_job_id=?",
            (deleted_at, int(deleted_bytes), "archive_limit", job_id),
        )
        connection.commit()
    except Exception:
        try:
            if job_dir.exists():
                shutil.rmtree(job_dir)
            if moved and quarantine.exists():
                quarantine.replace(job_dir)
        finally:
            raise

    if quarantine.exists():
        if quarantine.is_dir():
            shutil.rmtree(quarantine)
        else:
            quarantine.unlink()

    return {
        "job_id": job_id,
        "files_deleted": True,
        "deleted_bytes": int(deleted_bytes),
        "shared_images": [str(path) for path in shared_images],
        "failed": False,
    }


def enforce_beta_archive_limit_for_user(user_id: int) -> dict[str, Any]:
    safe_user_id = int(user_id or 0)
    limit = archive_limit_for_user(safe_user_id)
    if limit is None:
        return {
            "user_id": safe_user_id,
            "limit": None,
            "unlimited": True,
            "overflow": 0,
            "deleted_jobs": 0,
            "deleted_bytes": 0,
            "failed": 0,
            "db_preserved": True,
            "list_preserved": True,
        }

    with _RETENTION_LOCK:
        with _connect(BETA_DB) as connection:
            rows = connection.execute(
                "SELECT beta_job_id,owner_user_id,created_at,result_json,media_deleted_at "
                "FROM beta_jobs WHERE owner_user_id=? AND COALESCE(media_deleted_at,'')='' "
                "ORDER BY created_at DESC,beta_job_id DESC LIMIT -1 OFFSET ?",
                (safe_user_id, int(limit)),
            ).fetchall()
            deleted_jobs = 0
            deleted_bytes = 0
            failed = 0
            details: list[dict[str, Any]] = []
            for row in reversed(rows):
                try:
                    detail = _delete_one_preserve_metadata(connection, row)
                    details.append(detail)
                    deleted_jobs += int(bool(detail.get("files_deleted")))
                    deleted_bytes += int(detail.get("deleted_bytes") or 0)
                except Exception as exc:
                    connection.rollback()
                    failed += 1
                    details.append({"job_id": str(row["beta_job_id"]), "failed": True, "error": str(exc)[:300]})

        pruned_images, pruned_bytes = prune_unreferenced_shared_images(JOBS_DIR)
        return {
            "user_id": safe_user_id,
            "limit": int(limit),
            "unlimited": False,
            "overflow": len(rows),
            "deleted_jobs": deleted_jobs,
            "deleted_bytes": int(deleted_bytes + pruned_bytes),
            "pruned_shared_images": int(pruned_images),
            "pruned_shared_bytes": int(pruned_bytes),
            "failed": failed,
            "db_preserved": True,
            "list_preserved": True,
            "details": details,
        }


def enforce_beta_archive_limit_for_job(job_id: str) -> dict[str, Any]:
    safe_job_id = str(job_id or "").strip()
    if not safe_job_id or not BETA_DB.is_file():
        return {"job_id": safe_job_id, "skipped": True}
    with _connect(BETA_DB) as connection:
        row = connection.execute(
            "SELECT owner_user_id FROM beta_jobs WHERE beta_job_id=? LIMIT 1",
            (safe_job_id,),
        ).fetchone()
    if not row:
        return {"job_id": safe_job_id, "skipped": True}
    return enforce_beta_archive_limit_for_user(int(row["owner_user_id"] or 0))


def enforce_all_beta_archive_limits() -> dict[str, Any]:
    if not BETA_DB.is_file():
        return {"users_checked": 0, "deleted_jobs": 0, "deleted_bytes": 0, "failed": 0}
    with _connect(BETA_DB) as connection:
        users = [
            int(row[0])
            for row in connection.execute(
                "SELECT DISTINCT owner_user_id FROM beta_jobs WHERE owner_user_id IS NOT NULL AND owner_user_id>0 ORDER BY owner_user_id"
            ).fetchall()
        ]
    total = {"users_checked": 0, "deleted_jobs": 0, "deleted_bytes": 0, "failed": 0, "results": []}
    for user_id in users:
        result = enforce_beta_archive_limit_for_user(user_id)
        total["users_checked"] += 1
        total["deleted_jobs"] += int(result.get("deleted_jobs") or 0)
        total["deleted_bytes"] += int(result.get("deleted_bytes") or 0)
        total["failed"] += int(result.get("failed") or 0)
        total["results"].append(result)
    return total
