# -*- coding: utf-8 -*-
"""Pattern Knowledge Engine repository.

All Pattern DB access lives here so SQLite can be swapped later without
touching scheduler/service code.
"""
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import engine


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def migrate_pattern_tables() -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS learning_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                industry TEXT NOT NULL,
                region TEXT NOT NULL,
                primary_keywords TEXT NOT NULL DEFAULT '[]',
                secondary_keywords TEXT NOT NULL DEFAULT '[]',
                priority TEXT NOT NULL DEFAULT 'MEDIUM',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                schedule TEXT NOT NULL DEFAULT 'weekly3',
                last_learning_at TEXT,
                last_success BOOLEAN,
                next_run_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS learning_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                collected_count INTEGER NOT NULL DEFAULT 0,
                analyzed_count INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS pattern_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_at TEXT NOT NULL,
                target_id INTEGER,
                company_name TEXT,
                keyword TEXT NOT NULL,
                region TEXT,
                industry TEXT,
                organic_rank INTEGER,
                recommendation_score INTEGER,
                business_score INTEGER,
                local_score INTEGER,
                seo_score INTEGER,
                cta_score INTEGER,
                trust_score INTEGER,
                freshness_score INTEGER,
                style_type TEXT,
                title_pattern TEXT,
                keyword_frequency INTEGER,
                location_frequency INTEGER,
                cta_type TEXT,
                pattern_summary TEXT,
                analysis_version TEXT,
                cache_status TEXT
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS pattern_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                region TEXT,
                industry TEXT,
                period_days INTEGER NOT NULL,
                summary_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS pattern_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seed_keyword TEXT NOT NULL,
                discovered_keyword TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'pattern_db',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                UNIQUE(seed_keyword, discovered_keyword)
            )
        """))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_pattern_snapshots_keyword ON pattern_snapshots(keyword)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_pattern_snapshots_collected_at ON pattern_snapshots(collected_at)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_learning_targets_active_next ON learning_targets(is_active, next_run_at)"))


def _json_list(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps([str(v).strip() for v in value if str(v).strip()], ensure_ascii=False)
    if isinstance(value, str):
        return json.dumps([v.strip() for v in value.split(",") if v.strip()], ensure_ascii=False)
    return "[]"


def _loads(value: str | None) -> list[str]:
    try:
        return json.loads(value or "[]")
    except Exception:
        return []


def _target_row(row) -> dict:
    data = dict(row._mapping)
    data["primary_keywords"] = _loads(data.get("primary_keywords"))
    data["secondary_keywords"] = _loads(data.get("secondary_keywords"))
    return data


def priority_schedule(priority: str) -> tuple[str, int]:
    priority = (priority or "MEDIUM").upper()
    if priority == "HIGH":
        return "daily", 1
    if priority == "LOW":
        return "weekly", 7
    return "weekly3", 2


def next_run_from(priority: str, base: datetime | None = None) -> str:
    _, days = priority_schedule(priority)
    return ((base or datetime.now()) + timedelta(days=days)).strftime("%Y-%m-%d 02:00:00")


def list_targets(db: Session) -> list[dict]:
    rows = db.execute(text("SELECT * FROM learning_targets ORDER BY priority ASC, id DESC")).all()
    return [_target_row(r) for r in rows]


def upsert_target(db: Session, payload: dict) -> dict:
    stamp = now_iso()
    priority = (payload.get("priority") or "MEDIUM").upper()
    schedule, _ = priority_schedule(priority)
    target_id = payload.get("id")
    values = {
        "company_name": payload.get("company_name", "").strip(),
        "industry": payload.get("industry", "").strip(),
        "region": payload.get("region", "").strip(),
        "primary_keywords": _json_list(payload.get("primary_keywords", [])),
        "secondary_keywords": _json_list(payload.get("secondary_keywords", [])),
        "priority": priority,
        "is_active": bool(payload.get("is_active", True)),
        "schedule": schedule,
        "next_run_at": payload.get("next_run_at") or next_run_from(priority),
        "updated_at": stamp,
    }
    if target_id:
        values["id"] = target_id
        db.execute(text("""
            UPDATE learning_targets
            SET company_name=:company_name, industry=:industry, region=:region,
                primary_keywords=:primary_keywords, secondary_keywords=:secondary_keywords,
                priority=:priority, is_active=:is_active, schedule=:schedule,
                next_run_at=:next_run_at, updated_at=:updated_at
            WHERE id=:id
        """), values)
    else:
        values["created_at"] = stamp
        db.execute(text("""
            INSERT INTO learning_targets
            (company_name, industry, region, primary_keywords, secondary_keywords, priority, is_active, schedule, next_run_at, created_at, updated_at)
            VALUES (:company_name, :industry, :region, :primary_keywords, :secondary_keywords, :priority, :is_active, :schedule, :next_run_at, :created_at, :updated_at)
        """), values)
    db.commit()
    row = db.execute(text("SELECT * FROM learning_targets WHERE id = COALESCE(:id, last_insert_rowid())"), {"id": target_id}).first()
    return _target_row(row)


def due_targets(db: Session, now_text: str) -> list[dict]:
    rows = db.execute(text("""
        SELECT * FROM learning_targets
        WHERE is_active = 1 AND (next_run_at IS NULL OR next_run_at <= :now_text)
        ORDER BY CASE priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, id ASC
    """), {"now_text": now_text}).all()
    return [_target_row(r) for r in rows]


def start_history(db: Session, target_id: int | None) -> int:
    started_at = now_iso()
    db.execute(text("INSERT INTO learning_history (target_id, status, started_at) VALUES (:target_id, 'running', :started_at)"), {
        "target_id": target_id,
        "started_at": started_at,
    })
    db.commit()
    return int(db.execute(text("SELECT last_insert_rowid()")).scalar())


def finish_history(db: Session, history_id: int, status: str, collected: int, analyzed: int, error: str | None = None, retry_count: int = 0) -> None:
    db.execute(text("""
        UPDATE learning_history
        SET status=:status, finished_at=:finished_at, collected_count=:collected,
            analyzed_count=:analyzed, error=:error, retry_count=:retry_count
        WHERE id=:id
    """), {
        "id": history_id,
        "status": status,
        "finished_at": now_iso(),
        "collected": collected,
        "analyzed": analyzed,
        "error": error,
        "retry_count": retry_count,
    })
    db.commit()


def update_target_run(db: Session, target_id: int, success: bool, priority: str) -> None:
    stamp = now_iso()
    db.execute(text("""
        UPDATE learning_targets
        SET last_learning_at=:stamp, last_success=:success, next_run_at=:next_run_at, updated_at=:stamp
        WHERE id=:id
    """), {
        "id": target_id,
        "stamp": stamp,
        "success": success,
        "next_run_at": next_run_from(priority),
    })
    db.commit()


def insert_snapshot(db: Session, snapshot: dict) -> None:
    db.execute(text("""
        INSERT INTO pattern_snapshots
        (collected_at, target_id, company_name, keyword, region, industry, organic_rank,
         recommendation_score, business_score, local_score, seo_score, cta_score,
         trust_score, freshness_score, style_type, title_pattern, keyword_frequency,
         location_frequency, cta_type, pattern_summary, analysis_version, cache_status)
        VALUES
        (:collected_at, :target_id, :company_name, :keyword, :region, :industry, :organic_rank,
         :recommendation_score, :business_score, :local_score, :seo_score, :cta_score,
         :trust_score, :freshness_score, :style_type, :title_pattern, :keyword_frequency,
         :location_frequency, :cta_type, :pattern_summary, :analysis_version, :cache_status)
    """), snapshot)


def list_history(db: Session, limit: int = 50) -> list[dict]:
    rows = db.execute(text("SELECT * FROM learning_history ORDER BY id DESC LIMIT :limit"), {"limit": limit}).all()
    return [dict(r._mapping) for r in rows]


def recent_snapshots(db: Session, days: int = 30, keyword: str | None = None) -> list[dict]:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    sql = "SELECT * FROM pattern_snapshots WHERE collected_at >= :since"
    params = {"since": since}
    if keyword:
        sql += " AND keyword LIKE :keyword"
        params["keyword"] = f"%{keyword}%"
    sql += " ORDER BY collected_at DESC"
    rows = db.execute(text(sql), params).all()
    return [dict(r._mapping) for r in rows]


def insert_discovered_keyword(db: Session, seed: str, keyword: str) -> None:
    db.execute(text("""
        INSERT OR IGNORE INTO pattern_keywords (seed_keyword, discovered_keyword, created_at)
        VALUES (:seed, :keyword, :created_at)
    """), {"seed": seed, "keyword": keyword, "created_at": now_iso()})


def health(db: Session) -> dict:
    counts = {
        "targets": db.execute(text("SELECT COUNT(*) FROM learning_targets")).scalar(),
        "snapshots": db.execute(text("SELECT COUNT(*) FROM pattern_snapshots")).scalar(),
        "history": db.execute(text("SELECT COUNT(*) FROM learning_history")).scalar(),
    }
    last_success = db.execute(text("SELECT * FROM learning_history WHERE status='success' ORDER BY id DESC LIMIT 1")).first()
    last_failure = db.execute(text("SELECT * FROM learning_history WHERE status='failed' ORDER BY id DESC LIMIT 1")).first()
    db_size = 0
    try:
        from app.settings import settings
        db_size = __import__("pathlib").Path(settings.STORYMAKER_DB_PATH).stat().st_size
    except Exception:
        pass
    return {
        "counts": counts,
        "sqlite_bytes": db_size,
        "last_success": dict(last_success._mapping) if last_success else None,
        "last_failure": dict(last_failure._mapping) if last_failure else None,
    }
