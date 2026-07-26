# -*- coding: utf-8 -*-
"""Content Performance repository.

This is the only layer that touches content_performance.db.
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from app.settings import settings


PERFORMANCE_DB_PATH = Path(settings.STORYMAKER_DB_PATH).with_name("content_performance.db")
performance_engine = create_engine(
    f"sqlite:///{PERFORMANCE_DB_PATH}",
    connect_args={"check_same_thread": False},
)


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def migrate_performance_tables() -> None:
    with performance_engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS content_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT,
                title TEXT,
                keyword TEXT,
                region TEXT,
                industry TEXT,
                performance_score INTEGER NOT NULL,
                seo_score INTEGER NOT NULL,
                keyword_coverage INTEGER NOT NULL,
                cta_quality INTEGER NOT NULL,
                readability INTEGER NOT NULL,
                local_seo INTEGER NOT NULL,
                industry_match INTEGER NOT NULL,
                seasonal_match INTEGER NOT NULL,
                pattern_match INTEGER NOT NULL,
                trend_match INTEGER NOT NULL,
                duplicate_risk INTEGER NOT NULL,
                improvement_summary TEXT NOT NULL,
                performance_summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS seo_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_score_id INTEGER,
                title_length INTEGER,
                has_location BOOLEAN,
                keyword_count INTEGER,
                subheading_count INTEGER,
                cta_position TEXT,
                has_internal_link BOOLEAN,
                has_image_alt BOOLEAN,
                meta_description_length INTEGER,
                improvements TEXT,
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS ranking_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                search_engine TEXT NOT NULL,
                ranking INTEGER,
                difference INTEGER,
                trend TEXT,
                checked_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS traffic_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT,
                views INTEGER DEFAULT 0,
                ctr REAL DEFAULT 0,
                dwell_seconds INTEGER DEFAULT 0,
                conversions INTEGER DEFAULT 0,
                measured_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS engagement_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                saves INTEGER DEFAULT 0,
                measured_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS feedback_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT,
                region TEXT,
                industry TEXT,
                feedback_summary TEXT NOT NULL,
                score INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS improvement_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_score_id INTEGER,
                improvement TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_content_scores_created ON content_scores(created_at)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_content_scores_keyword ON content_scores(keyword)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_ranking_history_keyword ON ranking_history(keyword)"))


def insert_score(payload: dict[str, Any]) -> int:
    stamp = now_iso()
    values = {**payload, "created_at": stamp}
    with performance_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO content_scores
            (content_id, title, keyword, region, industry, performance_score, seo_score,
             keyword_coverage, cta_quality, readability, local_seo, industry_match,
             seasonal_match, pattern_match, trend_match, duplicate_risk,
             improvement_summary, performance_summary, created_at)
            VALUES
            (:content_id, :title, :keyword, :region, :industry, :performance_score, :seo_score,
             :keyword_coverage, :cta_quality, :readability, :local_seo, :industry_match,
             :seasonal_match, :pattern_match, :trend_match, :duplicate_risk,
             :improvement_summary, :performance_summary, :created_at)
        """), values)
        score_id = int(connection.execute(text("SELECT last_insert_rowid()")).scalar())
        seo = payload.get("seo_intelligence", {})
        connection.execute(text("""
            INSERT INTO seo_scores
            (content_score_id, title_length, has_location, keyword_count, subheading_count,
             cta_position, has_internal_link, has_image_alt, meta_description_length,
             improvements, created_at)
            VALUES
            (:content_score_id, :title_length, :has_location, :keyword_count, :subheading_count,
             :cta_position, :has_internal_link, :has_image_alt, :meta_description_length,
             :improvements, :created_at)
        """), {
            "content_score_id": score_id,
            "title_length": seo.get("title_length", 0),
            "has_location": bool(seo.get("has_location")),
            "keyword_count": seo.get("keyword_count", 0),
            "subheading_count": seo.get("subheading_count", 0),
            "cta_position": seo.get("cta_position", "-"),
            "has_internal_link": bool(seo.get("has_internal_link")),
            "has_image_alt": bool(seo.get("has_image_alt")),
            "meta_description_length": seo.get("meta_description_length", 0),
            "improvements": payload.get("improvement_summary", ""),
            "created_at": stamp,
        })
        for item in payload.get("improvements", []):
            connection.execute(text("""
                INSERT INTO improvement_history (content_score_id, improvement, created_at)
                VALUES (:content_score_id, :improvement, :created_at)
            """), {"content_score_id": score_id, "improvement": item, "created_at": stamp})
        connection.execute(text("""
            INSERT INTO feedback_patterns (keyword, region, industry, feedback_summary, score, created_at)
            VALUES (:keyword, :region, :industry, :feedback_summary, :score, :created_at)
        """), {
            "keyword": payload.get("keyword"),
            "region": payload.get("region"),
            "industry": payload.get("industry"),
            "feedback_summary": payload.get("performance_summary", ""),
            "score": payload.get("performance_score", 0),
            "created_at": stamp,
        })
        return score_id


def insert_ranking(keyword: str, search_engine: str, ranking: int | None, previous_ranking: int | None = None) -> dict:
    diff = None if ranking is None or previous_ranking is None else previous_ranking - ranking
    trend = "flat"
    if diff and diff > 0:
        trend = "up"
    elif diff and diff < 0:
        trend = "down"
    row = {
        "keyword": keyword,
        "search_engine": search_engine,
        "ranking": ranking,
        "difference": diff,
        "trend": trend,
        "checked_at": now_iso(),
    }
    with performance_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO ranking_history (keyword, search_engine, ranking, difference, trend, checked_at)
            VALUES (:keyword, :search_engine, :ranking, :difference, :trend, :checked_at)
        """), row)
    return row


def recent_scores(limit: int = 50) -> list[dict]:
    with performance_engine.begin() as connection:
        rows = connection.execute(text("SELECT * FROM content_scores ORDER BY id DESC LIMIT :limit"), {"limit": limit}).all()
        return [dict(r._mapping) for r in rows]


def recent_improvements(limit: int = 30) -> list[dict]:
    with performance_engine.begin() as connection:
        rows = connection.execute(text("SELECT * FROM improvement_history ORDER BY id DESC LIMIT :limit"), {"limit": limit}).all()
        return [dict(r._mapping) for r in rows]


def ranking_history(keyword: str | None = None, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM ranking_history"
    params: dict[str, Any] = {"limit": limit}
    if keyword:
        sql += " WHERE keyword = :keyword"
        params["keyword"] = keyword
    sql += " ORDER BY checked_at DESC LIMIT :limit"
    with performance_engine.begin() as connection:
        rows = connection.execute(text(sql), params).all()
        return [dict(r._mapping) for r in rows]


def trend(days: int = 30) -> dict:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with performance_engine.begin() as connection:
        rows = connection.execute(text("SELECT * FROM content_scores WHERE created_at >= :since"), {"since": since}).all()
    items = [dict(r._mapping) for r in rows]
    if not items:
        return {"period_days": days, "count": 0, "trend_score": 0, "items": []}
    avg = lambda key: round(sum((i.get(key) or 0) for i in items) / len(items), 1)
    trend_score = round((avg("performance_score") + avg("seo_score") + avg("trend_match")) / 3, 1)
    return {
        "period_days": days,
        "count": len(items),
        "avg_performance_score": avg("performance_score"),
        "avg_seo_score": avg("seo_score"),
        "avg_trend_match": avg("trend_match"),
        "trend_score": trend_score,
        "summary": "Performance Trend ▲" if trend_score >= 70 else "Performance Trend 점검 필요",
    }


def feedback_summaries(limit: int = 5) -> list[dict]:
    with performance_engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT * FROM feedback_patterns
            ORDER BY score DESC, id DESC
            LIMIT :limit
        """), {"limit": limit}).all()
        return [dict(r._mapping) for r in rows]


def health() -> dict:
    with performance_engine.begin() as connection:
        content_count = connection.execute(text("SELECT COUNT(*) FROM content_scores")).scalar()
        ranking_count = connection.execute(text("SELECT COUNT(*) FROM ranking_history")).scalar()
        improvement_count = connection.execute(text("SELECT COUNT(*) FROM improvement_history WHERE status='open'")).scalar()
        avg_score = connection.execute(text("SELECT AVG(performance_score) FROM content_scores")).scalar() or 0
    size = PERFORMANCE_DB_PATH.stat().st_size if PERFORMANCE_DB_PATH.exists() else 0
    return {
        "db_path": str(PERFORMANCE_DB_PATH),
        "repository_size_bytes": size,
        "content_scores": content_count,
        "ranking_history": ranking_count,
        "feedback_queue": improvement_count,
        "score_success_rate": 100 if content_count else 0,
        "average_performance_score": round(float(avg_score), 1),
        "average_runtime_ms": 0,
        "cache_hit": "-",
        "duplicate_rate": 0,
    }
