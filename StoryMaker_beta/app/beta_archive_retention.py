from __future__ import annotations

import fcntl
import json
import logging
import os
import shutil
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.beta_storage import SHARED_IMAGE_DIR, prune_unreferenced_shared_images

ROOT = Path(os.getenv("STORYMAKER_BETA_ROOT", "/home/bourne/StoryMaker_1/StoryMaker_beta"))
BETA_DB = ROOT / "data" / "storymaker_beta.db"
JOBS_DIR = ROOT / "data" / "jobs"
V1_DB = Path(os.getenv("STORYMAKER_V1_DB_PATH", "/home/bourne/StoryMaker_1/database/storymaker.db"))
LOG_DIR = ROOT / "logs"
AUDIT_LOG = LOG_DIR / "beta_archive_retention.jsonl"
LOCK_FILE = ROOT / "data" / ".beta_archive_retention.lock"
QUARANTINE_PREFIX = ".__archive_limit__"
FREE_LIMIT = 10
PAID_LIMIT = 20
RETENTION_INTERVAL_SECONDS = max(300, int(os.getenv("BETA_ARCHIVE_RETENTION_INTERVAL_SECONDS", "3600")))
AUDIT_MAX_BYTES = max(1024 * 1024, int(os.getenv("BETA_ARCHIVE_RETENTION_AUDIT_MAX_BYTES", str(5 * 1024 * 1024))))

logger = logging.getLogger(__name__)
_RETENTION_LOCK = threading.RLock()
_SCHEDULER_LOCK = threading.Lock()
_SCHEDULER_STARTED = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def _audit(event: str, payload: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {"at": _now(), "event": str(event), **payload}
    try:
        if AUDIT_LOG.is_file() and AUDIT_LOG.stat().st_size >= AUDIT_MAX_BYTES:
            rotated = AUDIT_LOG.with_suffix(AUDIT_LOG.suffix + ".1")
            rotated.unlink(missing_ok=True)
            AUDIT_LOG.replace(rotated)
        with AUDIT_LOG.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("Beta archive retention audit write failed event=%s", event)


@contextmanager
def _retention_guard() -> Iterator[None]:
    """Serialize retention across threads and future multi-worker processes."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _RETENTION_LOCK:
        with LOCK_FILE.open("a+") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


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
    """Admin is unlimited; free keeps 10; every paid plan keeps 20.

    If membership data cannot be verified, return None and skip deletion. This
    fail-safe prevents a temporary V1 DB problem from downgrading paid/admin
    users to the free limit.
    """
    safe_user_id = int(user_id or 0)
    if safe_user_id <= 0 or not V1_DB.is_file():
        return None
    try:
        with _connect(V1_DB) as connection:
            user = connection.execute(
                "SELECT role FROM users WHERE id=? LIMIT 1",
                (safe_user_id,),
            ).fetchone()
            if not user:
                return None
            role = str(user["role"] or "user").strip().lower()
            if role == "admin":
                return None
            billing = connection.execute(
                "SELECT COALESCE(current_plan_code,'free') AS plan "
                "FROM member_billing_profiles WHERE user_id=? LIMIT 1",
                (safe_user_id,),
            ).fetchone()
            plan = str(billing["plan"] if billing else "free").strip().lower()
            return FREE_LIMIT if plan in {"", "free"} else PAID_LIMIT
    except sqlite3.Error as exc:
        _audit("membership_lookup_failed", {"user_id": safe_user_id, "error": str(exc)[:300]})
        return None


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


def _job_has_generated_media(job_id: str) -> bool:
    """Count only jobs that actually hold generated/uploaded media."""
    job_dir = JOBS_DIR / str(job_id)
    if not job_dir.is_dir():
        return False
    ignored = {"result.json", "state.json"}
    for path in job_dir.rglob("*"):
        if path.is_file() and path.name not in ignored:
            try:
                if path.stat().st_size > 0:
                    return True
            except OSError:
                continue
    result = _read_json(job_dir / "result.json")
    assets = result.get("assets") if isinstance(result.get("assets"), dict) else {}
    for value in assets.values():
        values = value if isinstance(value, list) else [value]
        for candidate in values:
            if not candidate:
                continue
            try:
                if Path(str(candidate)).is_file():
                    return True
            except (OSError, ValueError):
                continue
    return False


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


def _clear_deleted_db_marker(connection: sqlite3.Connection, job_id: str) -> None:
    connection.execute(
        "UPDATE beta_jobs SET media_deleted_at='',media_deleted_bytes=0,media_delete_reason='' WHERE beta_job_id=?",
        (job_id,),
    )
    connection.commit()


def _recover_stale_quarantines_locked() -> dict[str, int]:
    """Recover or finalize interrupted archive-limit operations without data loss."""
    recovered = 0
    finalized = 0
    conflicts = 0
    if not JOBS_DIR.is_dir() or not BETA_DB.is_file():
        return {"recovered": 0, "finalized": 0, "conflicts": 0}
    with _connect(BETA_DB) as connection:
        for quarantine in JOBS_DIR.glob(f"{QUARANTINE_PREFIX}*"):
            job_id = quarantine.name[len(QUARANTINE_PREFIX):]
            job_dir = JOBS_DIR / job_id
            row = connection.execute(
                "SELECT media_deleted_at,media_delete_reason FROM beta_jobs WHERE beta_job_id=? LIMIT 1",
                (job_id,),
            ).fetchone()
            if not row:
                conflicts += 1
                _audit("quarantine_orphan_preserved", {"job_id": job_id, "path": str(quarantine)})
                continue
            db_deleted = bool(str(row["media_deleted_at"] or "")) and str(row["media_delete_reason"] or "") == "archive_limit"
            compact = _read_json(job_dir / "result.json") if job_dir.is_dir() else {}
            compact_deleted = str(compact.get("media_delete_reason") or "") == "archive_limit"

            if db_deleted and compact_deleted:
                try:
                    shutil.rmtree(quarantine) if quarantine.is_dir() else quarantine.unlink()
                    finalized += 1
                    _audit("quarantine_finalized", {"job_id": job_id})
                except OSError as exc:
                    conflicts += 1
                    _audit("quarantine_finalize_failed", {"job_id": job_id, "error": str(exc)[:300]})
                continue

            if not db_deleted:
                try:
                    if compact_deleted and job_dir.exists():
                        shutil.rmtree(job_dir)
                    if not job_dir.exists():
                        quarantine.replace(job_dir)
                        recovered += 1
                        _audit("quarantine_restored", {"job_id": job_id})
                    else:
                        conflicts += 1
                        _audit("quarantine_conflict_preserved", {"job_id": job_id, "path": str(quarantine)})
                except OSError as exc:
                    conflicts += 1
                    _audit("quarantine_restore_failed", {"job_id": job_id, "error": str(exc)[:300]})
                continue

            # DB says deleted, but compact metadata is missing. Restore original
            # and clear the DB marker rather than losing the only complete copy.
            try:
                if job_dir.exists():
                    shutil.rmtree(job_dir)
                quarantine.replace(job_dir)
                _clear_deleted_db_marker(connection, job_id)
                recovered += 1
                _audit("quarantine_db_rollback", {"job_id": job_id})
            except OSError as exc:
                conflicts += 1
                _audit("quarantine_db_rollback_failed", {"job_id": job_id, "error": str(exc)[:300]})
    return {"recovered": recovered, "finalized": finalized, "conflicts": conflicts}


def recover_stale_beta_archive_quarantines() -> dict[str, int]:
    with _retention_guard():
        return _recover_stale_quarantines_locked()


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
    quarantine = JOBS_DIR / f"{QUARANTINE_PREFIX}{job_id}"

    if quarantine.exists():
        raise RuntimeError(f"unresolved archive quarantine exists: {quarantine.name}")

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
        connection.rollback()
        try:
            if job_dir.exists():
                shutil.rmtree(job_dir)
            if moved and quarantine.exists():
                quarantine.replace(job_dir)
        finally:
            raise

    try:
        if quarantine.exists():
            shutil.rmtree(quarantine) if quarantine.is_dir() else quarantine.unlink()
    except OSError as exc:
        _audit("quarantine_cleanup_deferred", {"job_id": job_id, "error": str(exc)[:300]})

    _audit("media_pruned", {"job_id": job_id, "deleted_bytes": int(deleted_bytes), "reason": "archive_limit"})
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

    with _retention_guard():
        recovery = _recover_stale_quarantines_locked()
        with _connect(BETA_DB) as connection:
            active_rows = connection.execute(
                "SELECT beta_job_id,owner_user_id,created_at,result_json,media_deleted_at "
                "FROM beta_jobs WHERE owner_user_id=? AND COALESCE(media_deleted_at,'')='' "
                "ORDER BY created_at DESC,beta_job_id DESC",
                (safe_user_id,),
            ).fetchall()
            media_rows = [row for row in active_rows if _job_has_generated_media(str(row["beta_job_id"]))]
            overflow_rows = media_rows[int(limit):]
            deleted_jobs = 0
            deleted_bytes = 0
            failed = 0
            details: list[dict[str, Any]] = []
            for row in reversed(overflow_rows):
                try:
                    detail = _delete_one_preserve_metadata(connection, row)
                    details.append(detail)
                    deleted_jobs += int(bool(detail.get("files_deleted")))
                    deleted_bytes += int(detail.get("deleted_bytes") or 0)
                except Exception as exc:
                    connection.rollback()
                    failed += 1
                    details.append({"job_id": str(row["beta_job_id"]), "failed": True, "error": str(exc)[:300]})
                    _audit("media_prune_failed", {"user_id": safe_user_id, "job_id": str(row["beta_job_id"]), "error": str(exc)[:300]})

        pruned_images = 0
        pruned_bytes = 0
        if deleted_jobs:
            pruned_images, pruned_bytes = prune_unreferenced_shared_images(JOBS_DIR)
        result = {
            "user_id": safe_user_id,
            "limit": int(limit),
            "unlimited": False,
            "eligible_media_jobs": len(media_rows),
            "overflow": len(overflow_rows),
            "deleted_jobs": deleted_jobs,
            "deleted_bytes": int(deleted_bytes + pruned_bytes),
            "pruned_shared_images": int(pruned_images),
            "pruned_shared_bytes": int(pruned_bytes),
            "failed": failed,
            "recovery": recovery,
            "db_preserved": True,
            "list_preserved": True,
            "details": details,
        }
        if overflow_rows or failed or any(recovery.values()):
            _audit("retention_result", result)
        return result


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
    recover_stale_beta_archive_quarantines()
    with _connect(BETA_DB) as connection:
        users = [
            int(row[0])
            for row in connection.execute(
                "SELECT DISTINCT owner_user_id FROM beta_jobs WHERE owner_user_id IS NOT NULL AND owner_user_id>0 ORDER BY owner_user_id"
            ).fetchall()
        ]
    total: dict[str, Any] = {"users_checked": 0, "deleted_jobs": 0, "deleted_bytes": 0, "failed": 0, "results": []}
    for user_id in users:
        result = enforce_beta_archive_limit_for_user(user_id)
        total["users_checked"] += 1
        total["deleted_jobs"] += int(result.get("deleted_jobs") or 0)
        total["deleted_bytes"] += int(result.get("deleted_bytes") or 0)
        total["failed"] += int(result.get("failed") or 0)
        total["results"].append(result)
    return total


def _retention_loop() -> None:
    while True:
        time.sleep(RETENTION_INTERVAL_SECONDS)
        try:
            enforce_all_beta_archive_limits()
        except Exception as exc:
            logger.exception("Beta archive retention loop failed")
            _audit("scheduler_failed", {"error": str(exc)[:300]})


def start_beta_archive_retention_scheduler() -> dict[str, Any]:
    """Run startup recovery/enforcement and start one hourly daemon checker."""
    global _SCHEDULER_STARTED
    with _SCHEDULER_LOCK:
        if _SCHEDULER_STARTED:
            return {"started": False, "already_started": True}
        try:
            startup_result = enforce_all_beta_archive_limits()
        except Exception as exc:
            logger.exception("Beta archive retention startup check failed")
            startup_result = {"users_checked": 0, "deleted_jobs": 0, "deleted_bytes": 0, "failed": 1, "error": str(exc)[:300]}
            _audit("startup_check_failed", {"error": str(exc)[:300]})
        threading.Thread(
            target=_retention_loop,
            name="beta-archive-retention",
            daemon=True,
        ).start()
        _SCHEDULER_STARTED = True
    _audit("scheduler_started", {"interval_seconds": RETENTION_INTERVAL_SECONDS, "startup": startup_result})
    return {"started": True, "interval_seconds": RETENTION_INTERVAL_SECONDS, "startup": startup_result}
