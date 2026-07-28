from pathlib import Path

from sqlalchemy import text
from app.db.database import engine
from app.services.content_storage_service import sync_result_to_database

def migrate_mobile_one_shot_jobs_table() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS mobile_one_shot_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id VARCHAR(80) NOT NULL UNIQUE, user_id INTEGER NOT NULL, persona_id INTEGER, status VARCHAR(80) DEFAULT 'created' NOT NULL, memo TEXT DEFAULT '' NOT NULL, created_date VARCHAR(10) DEFAULT '' NOT NULL, result_path TEXT DEFAULT '' NOT NULL, image_count INTEGER DEFAULT 0 NOT NULL, has_text INTEGER DEFAULT 0 NOT NULL, has_mp3 INTEGER DEFAULT 0 NOT NULL, has_mp4 INTEGER DEFAULT 0 NOT NULL, has_thumbnail INTEGER DEFAULT 0 NOT NULL, error_message TEXT DEFAULT '' NOT NULL, created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL, completed_at VARCHAR(40))"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_mobile_one_shot_jobs_job_id ON mobile_one_shot_jobs (job_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_one_shot_jobs_user_created ON mobile_one_shot_jobs (user_id, created_at)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_one_shot_jobs_user_created_desc ON mobile_one_shot_jobs (user_id, created_at DESC)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_one_shot_jobs_user_status ON mobile_one_shot_jobs (user_id, status)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_one_shot_jobs_user_status_created_desc ON mobile_one_shot_jobs (user_id, status, created_at DESC)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_one_shot_jobs_created_at ON mobile_one_shot_jobs (created_at)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_one_shot_jobs_user_result_created ON mobile_one_shot_jobs (user_id, result_path, created_at DESC)"))
        existing_columns = {str(row[1]) for row in connection.execute(text("PRAGMA table_info(mobile_one_shot_jobs)")).fetchall()}
        for column_name, ddl in [
            ("stage", "stage TEXT DEFAULT '' NOT NULL"),
            ("percent", "percent INTEGER DEFAULT 0 NOT NULL"),
            ("queue_position", "queue_position INTEGER DEFAULT 0 NOT NULL"),
            ("ahead_count", "ahead_count INTEGER DEFAULT 0 NOT NULL"),
            ("worker_status", "worker_status VARCHAR(80) DEFAULT '' NOT NULL"),
            ("progress_message", "progress_message TEXT DEFAULT '' NOT NULL"),
        ]:
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE mobile_one_shot_jobs ADD COLUMN {ddl}"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_one_shot_jobs_user_progress ON mobile_one_shot_jobs (user_id, status, updated_at DESC)"))


def upsert_mobile_one_shot_job(*, job_id: str, user_id: int, persona_id: int | None, status: str, memo: str, created_date: str, result_path: str, image_count: int, created_at: str, updated_at: str, has_text: bool = False, has_mp3: bool = False, has_mp4: bool = False, has_thumbnail: bool = False, error_message: str = "", completed_at: str | None = None) -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO mobile_one_shot_jobs (job_id, user_id, persona_id, status, memo, created_date, result_path, image_count, has_text, has_mp3, has_mp4, has_thumbnail, error_message, created_at, updated_at, completed_at)
            VALUES (:job_id, :user_id, :persona_id, :status, :memo, :created_date, :result_path, :image_count, :has_text, :has_mp3, :has_mp4, :has_thumbnail, :error_message, :created_at, :updated_at, :completed_at)
            ON CONFLICT(job_id) DO UPDATE SET
                user_id = excluded.user_id,
                persona_id = excluded.persona_id,
                status = excluded.status,
                memo = excluded.memo,
                created_date = excluded.created_date,
                result_path = excluded.result_path,
                image_count = excluded.image_count,
                has_text = excluded.has_text,
                has_mp3 = excluded.has_mp3,
                has_mp4 = excluded.has_mp4,
                has_thumbnail = excluded.has_thumbnail,
                error_message = excluded.error_message,
                updated_at = excluded.updated_at,
                completed_at = COALESCE(excluded.completed_at, mobile_one_shot_jobs.completed_at)
        """), {
            "job_id": job_id,
            "user_id": user_id,
            "persona_id": persona_id,
            "status": status,
            "memo": memo,
            "created_date": created_date,
            "result_path": result_path,
            "image_count": int(image_count or 0),
            "has_text": 1 if has_text else 0,
            "has_mp3": 1 if has_mp3 else 0,
            "has_mp4": 1 if has_mp4 else 0,
            "has_thumbnail": 1 if has_thumbnail else 0,
            "error_message": error_message or "",
            "created_at": created_at,
            "updated_at": updated_at,
            "completed_at": completed_at,
        })


def _mobile_one_shot_raw_block(text_value: object, block_name: str) -> str:
    raw = str(text_value or "")
    start_tag = f"[BLOCK:{block_name}]"
    start = raw.find(start_tag)
    if start < 0:
        return ""
    rest = raw[start + len(start_tag):]
    next_pos = rest.find("\n[BLOCK:")
    return (rest[:next_pos] if next_pos >= 0 else rest).strip()


def _mobile_one_shot_summary_title(data: dict) -> str:
    outputs = data.get("outputs") or {}
    raw_result = str(data.get("raw_result") or "")
    candidates = [
        outputs.get("blog_titles"),
        outputs.get("BLOG_TITLES"),
        _mobile_one_shot_raw_block(raw_result, "BLOG_TITLES"),
        outputs.get("blog"),
        outputs.get("BLOG"),
    ]
    for candidate in candidates:
        for line in str(candidate or "").splitlines():
            cleaned = line.strip().lstrip("#-•0123456789. )").strip()
            if cleaned.startswith("[BLOCK:"):
                continue
            if cleaned.startswith("제목:"):
                cleaned = cleaned.split(":", 1)[1].strip()
            if len(cleaned) >= 4:
                return cleaned[:80]
    return ""


def _deleted_job_tombstone_exists(job_id: str, result_path: str) -> bool:
    if not job_id or not result_path:
        return False
    try:
        path = Path(result_path)
        output_root = path.parents[3]
        return (output_root / "cleanup_trash" / "deleted_job_tombstones" / f"{job_id}.json").exists()
    except (IndexError, OSError):
        return False


def sync_mobile_one_shot_job_from_result(data: dict, result_path: str, updated_at: str) -> None:
    job_id = str(data.get("job_id") or "")
    user_id = int(data.get("user_bucket") or 0)
    if not job_id or not user_id:
        return
    if _deleted_job_tombstone_exists(job_id, result_path):
        return
    media = data.get("media") or {}
    outputs = data.get("outputs") or {}
    persona = data.get("persona") or {}
    status = str(data.get("status") or media.get("status") or "unknown")
    summary_title = _mobile_one_shot_summary_title(data)
    completed_at = updated_at if status in {"completed", "shortform_completed", "thumbnail_done"} or media.get("mp4_url") else None
    upsert_mobile_one_shot_job(
        job_id=job_id,
        user_id=user_id,
        persona_id=persona.get("id"),
        status=status,
        memo=summary_title,
        created_date=str(data.get("created_date") or ""),
        result_path=result_path,
        image_count=int(data.get("image_count") or len(data.get("images") or [])),
        has_text=bool(data.get("raw_result") or outputs),
        has_mp3=bool(media.get("mp3_url") or media.get("mp3_path")),
        has_mp4=bool(media.get("mp4_url") or media.get("mp4_path")),
        has_thumbnail=bool(media.get("thumbnail_url")),
        error_message=str(data.get("error") or media.get("error") or media.get("thumbnail_error") or "")[:500],
        created_at=str(data.get("created_at") or updated_at),
        updated_at=updated_at,
        completed_at=completed_at,
    )

    try:
        from app.services.content_asset_service import sync_content_archive_assets

        result_file = Path(result_path).expanduser().resolve()
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
        sync_result_to_database(data, result_path=result_path)
    except Exception:
        # 자산 DB 등록 실패가 원본 결과 저장을 막지 않도록 분리합니다.
        pass


def update_mobile_one_shot_progress(*, job_id: str, user_id: int, status: str | None = None, stage: str = "", percent: int | None = None, queue_position: int | None = None, ahead_count: int | None = None, worker_status: str = "", progress_message: str = "", updated_at: str = "") -> None:
    updates = []
    values = {"job_id": job_id, "user_id": user_id}
    if status is not None:
        updates.append("status = :status")
        values["status"] = status
    if stage:
        updates.append("stage = :stage")
        values["stage"] = stage[:500]
    if percent is not None:
        updates.append("percent = :percent")
        values["percent"] = max(0, min(int(percent), 100))
    if queue_position is not None:
        updates.append("queue_position = :queue_position")
        values["queue_position"] = max(0, int(queue_position))
    if ahead_count is not None:
        updates.append("ahead_count = :ahead_count")
        values["ahead_count"] = max(0, int(ahead_count))
    if worker_status:
        updates.append("worker_status = :worker_status")
        values["worker_status"] = worker_status[:80]
    if progress_message:
        updates.append("progress_message = :progress_message")
        values["progress_message"] = progress_message[:1000]
    if updated_at:
        updates.append("updated_at = :updated_at")
        values["updated_at"] = updated_at
    if not updates:
        return
    with engine.begin() as connection:
        connection.execute(text(f"""
            UPDATE mobile_one_shot_jobs
            SET {', '.join(updates)}
            WHERE job_id = :job_id AND user_id = :user_id
        """), values)


def get_mobile_one_shot_progress(job_id: str, user_id: int) -> dict:
    terminal_statuses = (
        "completed",
        "done",
        "failed",
        "cancelled",
        "canceled",
        "shortform_completed",
        "thumbnail_done",
    )
    with engine.begin() as connection:
        row = connection.execute(text("""
            SELECT job_id, user_id, status, stage, percent, queue_position, ahead_count,
                   worker_status, progress_message, created_at, updated_at, completed_at, result_path
            FROM mobile_one_shot_jobs
            WHERE job_id = :job_id AND user_id = :user_id
            LIMIT 1
        """), {"job_id": job_id, "user_id": user_id}).mappings().first()
        if not row:
            return {}
        data = dict(row)
        status = str(data.get("status") or "").lower()
        percent = int(data.get("percent") or 0)
        completed_at = str(data.get("completed_at") or "")
        is_active = not completed_at and percent < 100 and status not in terminal_statuses
        if is_active:
            ahead_count = int(connection.execute(text("""
                SELECT COUNT(*)
                FROM mobile_one_shot_jobs
                WHERE job_id != :job_id
                  AND COALESCE(completed_at, '') = ''
                  AND CAST(COALESCE(percent, 0) AS INTEGER) < 100
                  AND LOWER(COALESCE(status, '')) NOT IN (
                    'completed', 'done', 'failed', 'cancelled', 'canceled', 'shortform_completed', 'thumbnail_done'
                  )
                  AND (
                    created_at < :created_at
                    OR (created_at = :created_at AND job_id < :job_id)
                  )
            """), {"job_id": job_id, "created_at": data.get("created_at") or ""}).scalar() or 0)
            queue_position = ahead_count + 1
        else:
            ahead_count = 0
            queue_position = 0
        data["ahead_count"] = ahead_count
        data["queue_position"] = queue_position
        connection.execute(text("""
            UPDATE mobile_one_shot_jobs
            SET ahead_count = :ahead_count,
                queue_position = :queue_position
            WHERE job_id = :job_id AND user_id = :user_id
        """), {
            "ahead_count": ahead_count,
            "queue_position": queue_position,
            "job_id": job_id,
            "user_id": user_id,
        })
        return data


def list_mobile_one_shot_admin_queue(limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(int(limit or 100), 300))
    terminal_statuses = (
        "completed",
        "done",
        "failed",
        "cancelled",
        "canceled",
        "shortform_completed",
        "thumbnail_done",
    )
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT job_id, user_id, status, stage, percent, queue_position, ahead_count,
                   worker_status, progress_message, created_at, updated_at, completed_at,
                   result_path, image_count, has_text, has_mp3, has_mp4, has_thumbnail, error_message
            FROM mobile_one_shot_jobs
            ORDER BY
              CASE
                WHEN COALESCE(completed_at, '') = ''
                 AND CAST(COALESCE(percent, 0) AS INTEGER) < 100
                 AND LOWER(COALESCE(status, '')) NOT IN (
                    'completed', 'done', 'failed', 'cancelled', 'canceled', 'shortform_completed', 'thumbnail_done'
                 ) THEN 0
                ELSE 1
              END,
              created_at ASC
            LIMIT :limit
        """), {"limit": safe_limit}).mappings().fetchall()
        items = []
        active_rows = []
        for row in rows:
            data = dict(row)
            status = str(data.get("status") or "").lower()
            percent = int(data.get("percent") or 0)
            completed_at = str(data.get("completed_at") or "")
            is_active = not completed_at and percent < 100 and status not in terminal_statuses
            data["is_active"] = is_active
            if is_active:
                active_rows.append(data)
            items.append(data)
        active_rows.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("job_id") or "")))
        positions = {str(item.get("job_id")): index + 1 for index, item in enumerate(active_rows)}
        for item in items:
            position = positions.get(str(item.get("job_id") or ""), 0)
            item["queue_position"] = position
            item["ahead_count"] = max(0, position - 1) if position else 0
        return items


def get_mobile_one_shot_admin_usage() -> dict:
    terminal_statuses = (
        "completed",
        "done",
        "shortform_completed",
        "thumbnail_done",
    )
    with engine.begin() as connection:
        summary = connection.execute(text("""
            SELECT
              COUNT(*) AS total_jobs,
              COUNT(DISTINCT user_id) AS total_users,
              SUM(CASE WHEN date(created_at) = date('now', 'localtime') THEN 1 ELSE 0 END) AS today_jobs,
              SUM(CASE WHEN datetime(created_at) >= datetime('now', 'localtime', '-7 days') THEN 1 ELSE 0 END) AS week_jobs,
              SUM(CASE WHEN datetime(created_at) >= datetime('now', 'localtime', '-7 days') THEN user_id ELSE NULL END) AS week_user_sum,
              COUNT(DISTINCT CASE WHEN datetime(created_at) >= datetime('now', 'localtime', '-7 days') THEN user_id END) AS week_users,
              SUM(CASE WHEN COALESCE(completed_at, '') = '' AND CAST(COALESCE(percent, 0) AS INTEGER) < 100 AND LOWER(COALESCE(status, '')) NOT IN ('completed', 'done', 'failed', 'cancelled', 'canceled', 'shortform_completed', 'thumbnail_done') THEN 1 ELSE 0 END) AS active_jobs,
              SUM(CASE WHEN LOWER(COALESCE(status, '')) LIKE '%fail%' OR COALESCE(error_message, '') != '' THEN 1 ELSE 0 END) AS failed_jobs,
              SUM(CASE WHEN COALESCE(completed_at, '') != '' OR CAST(COALESCE(percent, 0) AS INTEGER) >= 100 OR LOWER(COALESCE(status, '')) IN ('completed', 'done', 'shortform_completed', 'thumbnail_done') THEN 1 ELSE 0 END) AS completed_jobs,
              SUM(CASE WHEN has_text = 1 THEN 1 ELSE 0 END) AS text_jobs,
              SUM(CASE WHEN has_mp3 = 1 THEN 1 ELSE 0 END) AS mp3_jobs,
              SUM(CASE WHEN has_mp4 = 1 THEN 1 ELSE 0 END) AS mp4_jobs,
              SUM(CASE WHEN has_thumbnail = 1 THEN 1 ELSE 0 END) AS thumbnail_jobs,
              SUM(COALESCE(image_count, 0)) AS total_images
            FROM mobile_one_shot_jobs
        """)).mappings().first()
        by_day = connection.execute(text("""
            SELECT substr(created_at, 1, 10) AS day,
                   COUNT(*) AS jobs,
                   COUNT(DISTINCT user_id) AS users,
                   SUM(CASE WHEN LOWER(COALESCE(status, '')) LIKE '%fail%' OR COALESCE(error_message, '') != '' THEN 1 ELSE 0 END) AS failed_jobs,
                   SUM(CASE WHEN COALESCE(completed_at, '') != '' OR CAST(COALESCE(percent, 0) AS INTEGER) >= 100 OR LOWER(COALESCE(status, '')) IN ('completed', 'done', 'shortform_completed', 'thumbnail_done') THEN 1 ELSE 0 END) AS completed_jobs
            FROM mobile_one_shot_jobs
            WHERE created_at != ''
            GROUP BY substr(created_at, 1, 10)
            ORDER BY day DESC
            LIMIT 14
        """)).mappings().fetchall()
        by_user = connection.execute(text("""
            SELECT user_id,
                   COUNT(*) AS jobs,
                   SUM(CASE WHEN date(created_at) = date('now', 'localtime') THEN 1 ELSE 0 END) AS today_jobs,
                   SUM(CASE WHEN datetime(created_at) >= datetime('now', 'localtime', '-7 days') THEN 1 ELSE 0 END) AS week_jobs,
                   SUM(CASE WHEN LOWER(COALESCE(status, '')) LIKE '%fail%' OR COALESCE(error_message, '') != '' THEN 1 ELSE 0 END) AS failed_jobs,
                   MAX(updated_at) AS last_seen_at
            FROM mobile_one_shot_jobs
            GROUP BY user_id
            ORDER BY jobs DESC, last_seen_at DESC
            LIMIT 20
        """)).mappings().fetchall()
        by_status = connection.execute(text("""
            SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS jobs
            FROM mobile_one_shot_jobs
            GROUP BY COALESCE(status, 'unknown')
            ORDER BY jobs DESC
            LIMIT 20
        """)).mappings().fetchall()
        return {
            "summary": dict(summary) if summary else {},
            "by_day": [dict(row) for row in by_day],
            "by_user": [dict(row) for row in by_user],
            "by_status": [dict(row) for row in by_status],
        }


def get_mobile_one_shot_result_path(job_id: str, user_id: int) -> str:
    with engine.begin() as connection:
        row = connection.execute(text("SELECT result_path FROM mobile_one_shot_jobs WHERE job_id = :job_id AND user_id = :user_id LIMIT 1"), {"job_id": job_id, "user_id": user_id}).first()
        return str(row[0]) if row and row[0] else ""


def delete_mobile_one_shot_job(job_id: str, user_id: int) -> bool:
    if not job_id or not user_id:
        return False
    with engine.begin() as connection:
        result = connection.execute(
            text("DELETE FROM mobile_one_shot_jobs WHERE job_id = :job_id AND user_id = :user_id"),
            {"job_id": job_id, "user_id": user_id},
        )
        return bool(result.rowcount)


def list_mobile_one_shot_result_paths(user_id: int, limit: int) -> list[str]:
    safe_limit = max(1, min(int(limit or 20), 50))
    with engine.begin() as connection:
        rows = connection.execute(text("SELECT result_path FROM mobile_one_shot_jobs WHERE user_id = :user_id AND result_path != '' ORDER BY created_at DESC LIMIT :limit"), {"user_id": user_id, "limit": safe_limit}).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]


def list_mobile_one_shot_job_summaries(user_id: int, limit: int, offset: int = 0) -> list[dict]:
    safe_limit = max(1, min(int(limit or 10), 10))
    safe_offset = max(0, int(offset or 0))
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT job_id, status, created_at, memo, image_count, result_path, persona_id
            FROM mobile_one_shot_jobs
            WHERE user_id = :user_id AND result_path != ''
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """), {"user_id": user_id, "limit": safe_limit, "offset": safe_offset}).mappings().fetchall()
        return [dict(row) for row in rows]


def list_content_board_job_summaries(
    user_id: int,
    cutoff_at: str,
    limit: int,
    offset: int = 0,
) -> list[dict]:
    """새 보관함 전용 목록입니다.

    DB에 등록된 현재 사용자 작업만 반환하며 파일시스템 재검색은 하지 않습니다.
    created_at이 보관 기한 안에 있는 작업만 최신순으로 조회합니다.
    """
    safe_limit = max(1, min(int(limit or 10), 20))
    safe_offset = max(0, int(offset or 0))
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT job_id, status, created_at, memo, image_count, result_path, persona_id
            FROM mobile_one_shot_jobs
            WHERE user_id = :user_id
              AND result_path != ''
              AND COALESCE(archive_visible, 1) = 1
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """), {
            "user_id": user_id,
            "limit": safe_limit,
            "offset": safe_offset,
        }).mappings().fetchall()
        return [dict(row) for row in rows]


def list_content_board_overflow_jobs(user_id: int, keep_limit: int) -> list[dict]:
    """Return archive rows beyond the newest keep_limit items, oldest first."""
    safe_user_id = int(user_id or 0)
    safe_keep_limit = max(0, int(keep_limit or 0))
    if safe_user_id <= 0:
        return []
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT job_id, user_id, status, created_at, memo, image_count, result_path, persona_id
            FROM mobile_one_shot_jobs
            WHERE user_id = :user_id
              AND result_path != ''
              AND COALESCE(archive_visible, 1) = 1
            ORDER BY created_at DESC, job_id DESC
            LIMIT -1 OFFSET :keep_limit
        """), {
            "user_id": safe_user_id,
            "keep_limit": safe_keep_limit,
        }).mappings().all()
    return [dict(row) for row in reversed(rows)]


def list_expired_content_board_jobs(cutoff_at: str, limit: int = 500) -> list[dict]:
    """7일 보관 기한이 지난 서버 작업을 정리 작업용으로 반환합니다."""
    safe_limit = max(1, min(int(limit or 500), 2000))
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT job_id, user_id, result_path, created_at
            FROM mobile_one_shot_jobs
            WHERE created_at < :cutoff_at
            ORDER BY created_at ASC
            LIMIT :limit
        """), {
            "cutoff_at": cutoff_at,
            "limit": safe_limit,
        }).mappings().fetchall()
        return [dict(row) for row in rows]


def get_content_board_job_record(job_id: str, user_id: int, cutoff_at: str) -> dict:
    """새 보관함 상세 조회용 DB 레코드입니다. 7일이 지난 작업은 반환하지 않습니다."""
    if not job_id or not user_id:
        return {}
    with engine.begin() as connection:
        row = connection.execute(text("""
            SELECT job_id, user_id, status, created_at, memo, image_count, result_path, persona_id
            FROM mobile_one_shot_jobs
            WHERE job_id = :job_id
              AND user_id = :user_id
              AND result_path != ''
              AND COALESCE(archive_visible, 1) = 1
              AND created_at >= :cutoff_at
            LIMIT 1
        """), {
            "job_id": job_id,
            "user_id": user_id,
            "cutoff_at": cutoff_at,
        }).mappings().first()
        return dict(row) if row else {}


def list_mobile_one_shot_title_backfill_candidates(user_id: int, limit: int = 300) -> list[dict]:
    safe_limit = max(1, min(int(limit or 300), 1000))
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT job_id, user_id, memo, result_path, created_at
            FROM mobile_one_shot_jobs
            WHERE user_id = :user_id
              AND result_path != ''
              AND (
                COALESCE(memo, '') = ''
                OR memo LIKE 'mob-%'
              )
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"user_id": user_id, "limit": safe_limit}).mappings().fetchall()
        return [dict(row) for row in rows]


def update_mobile_one_shot_job_memo(job_id: str, user_id: int, memo: str) -> None:
    clean_memo = str(memo or '').strip()[:500]
    if not job_id or not user_id or not clean_memo:
        return
    with engine.begin() as connection:
        connection.execute(text("""
            UPDATE mobile_one_shot_jobs
            SET memo = :memo
            WHERE job_id = :job_id AND user_id = :user_id
        """), {"memo": clean_memo, "job_id": job_id, "user_id": user_id})
