# -*- coding: utf-8 -*-
"""AI Content Intelligence Brain repository.

Only this file touches content_intelligence.db.
"""
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from app.settings import settings


INTELLIGENCE_DB_PATH = Path(settings.STORYMAKER_DB_PATH).with_name("content_intelligence.db")
intelligence_engine = create_engine(
    f"sqlite:///{INTELLIGENCE_DB_PATH}",
    connect_args={"check_same_thread": False},
)


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def migrate_intelligence_tables() -> None:
    with intelligence_engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS prompt_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id TEXT,
                keyword TEXT,
                region TEXT,
                industry TEXT,
                seo_score INTEGER NOT NULL,
                human_score INTEGER NOT NULL,
                emotion_score INTEGER NOT NULL,
                readability INTEGER NOT NULL,
                repetition_score INTEGER NOT NULL,
                local_score INTEGER NOT NULL,
                cta_score INTEGER NOT NULL,
                keyword_density INTEGER NOT NULL,
                overall_score INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS brain_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_score_id INTEGER,
                feedback TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS industry_learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                industry TEXT NOT NULL,
                best_pattern TEXT,
                best_cta TEXT,
                best_emotion TEXT,
                best_keyword TEXT,
                score INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS prompt_evolution (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'brain',
                score INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS quality_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_size INTEGER NOT NULL,
                avg_overall REAL NOT NULL,
                avg_seo REAL NOT NULL,
                avg_emotion REAL NOT NULL,
                avg_repetition REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_prompt_scores_created ON prompt_scores(created_at)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_prompt_scores_industry ON prompt_scores(industry)"))


def insert_prompt_score(payload: dict[str, Any]) -> int:
    stamp = now_iso()
    values = {**payload, "created_at": stamp}
    with intelligence_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO prompt_scores
            (prompt_id, keyword, region, industry, seo_score, human_score, emotion_score,
             readability, repetition_score, local_score, cta_score, keyword_density,
             overall_score, created_at)
            VALUES
            (:prompt_id, :keyword, :region, :industry, :seo_score, :human_score, :emotion_score,
             :readability, :repetition_score, :local_score, :cta_score, :keyword_density,
             :overall_score, :created_at)
        """), values)
        score_id = int(connection.execute(text("SELECT last_insert_rowid()")).scalar())
        for feedback in payload.get("feedback", []):
            connection.execute(text("""
                INSERT INTO brain_feedback (prompt_score_id, feedback, severity, created_at)
                VALUES (:prompt_score_id, :feedback, :severity, :created_at)
            """), {
                "prompt_score_id": score_id,
                "feedback": feedback,
                "severity": "warn" if "부족" in feedback or "약" in feedback or "높" in feedback else "info",
                "created_at": stamp,
            })
        return score_id


def upsert_industry_learning(industry: str, best_pattern: str, best_cta: str, best_emotion: str, best_keyword: str, score: int) -> None:
    stamp = now_iso()
    with intelligence_engine.begin() as connection:
        row = connection.execute(text("SELECT id FROM industry_learning WHERE industry=:industry"), {"industry": industry}).first()
        values = {
            "industry": industry,
            "best_pattern": best_pattern,
            "best_cta": best_cta,
            "best_emotion": best_emotion,
            "best_keyword": best_keyword,
            "score": score,
            "updated_at": stamp,
        }
        if row:
            connection.execute(text("""
                UPDATE industry_learning
                SET best_pattern=:best_pattern, best_cta=:best_cta, best_emotion=:best_emotion,
                    best_keyword=:best_keyword, score=:score, updated_at=:updated_at
                WHERE industry=:industry
            """), values)
        else:
            connection.execute(text("""
                INSERT INTO industry_learning
                (industry, best_pattern, best_cta, best_emotion, best_keyword, score, updated_at)
                VALUES (:industry, :best_pattern, :best_cta, :best_emotion, :best_keyword, :score, :updated_at)
            """), values)


def insert_prompt_evolution(summary: str, recommendation: str, score: int, source: str = "brain") -> int:
    with intelligence_engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO prompt_evolution (summary, recommendation, source, score, created_at)
            VALUES (:summary, :recommendation, :source, :score, :created_at)
        """), {"summary": summary, "recommendation": recommendation, "source": source, "score": score, "created_at": now_iso()})
        return int(connection.execute(text("SELECT last_insert_rowid()")).scalar())


def recent_prompt_scores(limit: int = 100) -> list[dict]:
    with intelligence_engine.begin() as connection:
        rows = connection.execute(text("SELECT * FROM prompt_scores ORDER BY id DESC LIMIT :limit"), {"limit": limit}).all()
        return [dict(r._mapping) for r in rows]


def recent_feedback(limit: int = 50) -> list[dict]:
    with intelligence_engine.begin() as connection:
        rows = connection.execute(text("SELECT * FROM brain_feedback ORDER BY id DESC LIMIT :limit"), {"limit": limit}).all()
        return [dict(r._mapping) for r in rows]


def industry_learning(limit: int = 50) -> list[dict]:
    with intelligence_engine.begin() as connection:
        rows = connection.execute(text("SELECT * FROM industry_learning ORDER BY score DESC, updated_at DESC LIMIT :limit"), {"limit": limit}).all()
        return [dict(r._mapping) for r in rows]


def prompt_evolution(limit: int = 20) -> list[dict]:
    with intelligence_engine.begin() as connection:
        rows = connection.execute(text("SELECT * FROM prompt_evolution ORDER BY id DESC LIMIT :limit"), {"limit": limit}).all()
        return [dict(r._mapping) for r in rows]


def quality_trend(window_size: int = 30, persist: bool = False) -> dict:
    rows = recent_prompt_scores(window_size)
    if not rows:
        return {"window_size": window_size, "count": 0, "avg_overall": 0, "avg_seo": 0, "avg_emotion": 0, "avg_repetition": 0}
    avg = lambda key: round(sum((r.get(key) or 0) for r in rows) / len(rows), 1)
    trend = {
        "window_size": window_size,
        "count": len(rows),
        "avg_overall": avg("overall_score"),
        "avg_seo": avg("seo_score"),
        "avg_emotion": avg("emotion_score"),
        "avg_repetition": avg("repetition_score"),
    }
    if persist:
        with intelligence_engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO quality_history (window_size, avg_overall, avg_seo, avg_emotion, avg_repetition, created_at)
                VALUES (:window_size, :avg_overall, :avg_seo, :avg_emotion, :avg_repetition, :created_at)
            """), {**trend, "created_at": now_iso()})
    return trend


def health() -> dict:
    with intelligence_engine.begin() as connection:
        prompt_count = connection.execute(text("SELECT COUNT(*) FROM prompt_scores")).scalar()
        feedback_count = connection.execute(text("SELECT COUNT(*) FROM brain_feedback")).scalar()
        learning_count = connection.execute(text("SELECT COUNT(*) FROM industry_learning")).scalar()
        evolution_count = connection.execute(text("SELECT COUNT(*) FROM prompt_evolution")).scalar()
        avg_score = connection.execute(text("SELECT AVG(overall_score) FROM prompt_scores")).scalar() or 0
    size = INTELLIGENCE_DB_PATH.stat().st_size if INTELLIGENCE_DB_PATH.exists() else 0
    return {
        "db_path": str(INTELLIGENCE_DB_PATH),
        "repository_size_bytes": size,
        "prompt_scores": prompt_count,
        "brain_feedback": feedback_count,
        "industry_learning": learning_count,
        "prompt_evolution": evolution_count,
        "average_overall_score": round(float(avg_score), 1),
    }
