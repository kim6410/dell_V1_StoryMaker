# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, Tuple

CACHE_DB_PATH = "/home/bourne/StoryMaker_1/storymaker-web/backend/app/db/cache.db"
CACHE_TTL_SECONDS = 3600


def init_cache_db() -> None:
    try:
        db_dir = os.path.dirname(CACHE_DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS naver_cache (
                cache_key TEXT PRIMARY KEY,
                response_json TEXT,
                expires_at INTEGER
            )
            """
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[Warning] Cache DB Init Error: {exc}")


def get_sqlite_status() -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM naver_cache")
        cached_rows = cursor.fetchone()[0]
        conn.close()

        db_size = os.path.getsize(CACHE_DB_PATH) if os.path.exists(CACHE_DB_PATH) else 0

        return {
            "db_path": CACHE_DB_PATH,
            "db_size_bytes": db_size,
            "cached_items_count": cached_rows,
            "status": "healthy",
        }
    except Exception as exc:
        return {
            "db_path": CACHE_DB_PATH,
            "db_size_bytes": 0,
            "cached_items_count": 0,
            "status": f"error: {str(exc)}",
        }


def _read_cache(cache_key: str) -> Tuple[Dict[str, Any] | None, str]:
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT response_json, expires_at FROM naver_cache WHERE cache_key = ?",
            (cache_key,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None, "miss"

        response_json, expires_at = row
        if int(time.time()) < int(expires_at):
            return json.loads(response_json), "hit"

        _delete_cache(cache_key)
        return None, "miss"
    except Exception:
        return None, "bypass"


def _write_cache(cache_key: str, data: Dict[str, Any], ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
    expires_at = int(time.time()) + int(ttl_seconds)
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO naver_cache (cache_key, response_json, expires_at) VALUES (?, ?, ?)",
            (cache_key, json.dumps(data, ensure_ascii=False), expires_at),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _delete_cache(cache_key: str) -> None:
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM naver_cache WHERE cache_key = ?", (cache_key,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def make_search_cache_key(keyword: str, limit: int) -> str:
    return f"naver_blog_search:{keyword}:{limit}"


def make_analysis_cache_key(keyword: str) -> str:
    return f"naver_blog_analyze:{keyword}"


def get_cached_search(keyword: str, limit: int) -> Tuple[Dict[str, Any] | None, str]:
    return _read_cache(make_search_cache_key(keyword, limit))


def set_cached_search(keyword: str, limit: int, data: Dict[str, Any]) -> None:
    _write_cache(make_search_cache_key(keyword, limit), data)


def get_cached_analysis(keyword: str) -> Tuple[Dict[str, Any] | None, str]:
    return _read_cache(make_analysis_cache_key(keyword))


def set_cached_analysis(keyword: str, data: Dict[str, Any]) -> None:
    _write_cache(make_analysis_cache_key(keyword), data)


init_cache_db()
