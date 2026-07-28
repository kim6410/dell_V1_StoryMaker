# -*- coding: utf-8 -*-
"""요청형 최신 날씨 캐시 서비스.

실제 요청 지역만 조회하고 같은 기상청 nx/ny 격자는 하나의 캐시를 공유합니다.
TTL 재사용, 격자별 잠금, 전역 호출 간격, 실패 회로 차단으로 외부 API 폭주를 막습니다.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from app.settings import settings
from app.services.weather_region_grid_service import resolve_region_grid

KST = ZoneInfo("Asia/Seoul")
CACHE_TTL_SECONDS = max(300, int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "3600")))
CACHE_RETENTION_DAYS = max(1, int(os.getenv("WEATHER_CACHE_RETENTION_DAYS", "30")))
EXTERNAL_MIN_INTERVAL_SECONDS = max(0.2, float(os.getenv("WEATHER_EXTERNAL_MIN_INTERVAL_SECONDS", "2.0")))
CIRCUIT_FAILURE_THRESHOLD = max(2, int(os.getenv("WEATHER_CIRCUIT_FAILURE_THRESHOLD", "5")))
CIRCUIT_OPEN_SECONDS = max(60, int(os.getenv("WEATHER_CIRCUIT_OPEN_SECONDS", "600")))
CACHE_DB_PATH = Path(
    os.getenv(
        "WEATHER_CACHE_DB_PATH",
        str(Path(settings.STORYMAKER_DB_PATH).with_name("weather_cache.db")),
    )
)

_init_lock = threading.Lock()
_key_locks_guard = threading.Lock()
_key_locks: dict[str, threading.Lock] = {}
_initialized = False
_rate_lock = threading.Lock()
_last_external_call_monotonic = 0.0
_circuit_lock = threading.Lock()
_consecutive_failures = 0
_circuit_open_until = 0.0


def _connect() -> sqlite3.Connection:
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def ensure_weather_cache_db() -> None:
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weather_current_cache (
                    cache_key TEXT PRIMARY KEY,
                    region TEXT NOT NULL,
                    weather TEXT NOT NULL,
                    temperature TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'on_demand',
                    fetched_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 1,
                    canonical_region TEXT NOT NULL DEFAULT '',
                    nx INTEGER,
                    ny INTEGER
                )
                """
            )
            columns = _table_columns(conn, "weather_current_cache")
            for name, ddl in (
                ("canonical_region", "TEXT NOT NULL DEFAULT ''"),
                ("nx", "INTEGER"),
                ("ny", "INTEGER"),
            ):
                if name not in columns:
                    conn.execute(f"ALTER TABLE weather_current_cache ADD COLUMN {name} {ddl}")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_weather_current_cache_accessed "
                "ON weather_current_cache(last_accessed_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_weather_current_cache_grid "
                "ON weather_current_cache(nx, ny)"
            )
            conn.commit()
        _initialized = True


def _normalize_region(region: str) -> str:
    return " ".join(str(region or "").strip().split())


def _resolve_request(region: str) -> dict:
    requested = _normalize_region(region)
    mapped = resolve_region_grid(requested)
    if mapped:
        nx = int(mapped["nx"])
        ny = int(mapped["ny"])
        return {
            "requested_region": requested,
            "canonical_region": str(mapped["target_full_name"]),
            "cache_key": f"kma:{nx}:{ny}",
            "nx": nx,
            "ny": ny,
            "match_method": str(mapped.get("match_method") or "mapped"),
        }
    return {
        "requested_region": requested,
        "canonical_region": requested,
        "cache_key": requested,
        "nx": None,
        "ny": None,
        "match_method": "string_fallback",
    }


def _key_lock(cache_key: str) -> threading.Lock:
    with _key_locks_guard:
        lock = _key_locks.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _key_locks[cache_key] = lock
        return lock


def _parse_dt(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=KST)
    except Exception:
        return None


def cleanup_expired_weather_cache() -> int:
    ensure_weather_cache_db()
    cutoff = (datetime.now(KST) - timedelta(days=CACHE_RETENTION_DAYS)).isoformat(timespec="seconds")
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM weather_current_cache WHERE last_accessed_at < ?",
            (cutoff,),
        )
        conn.commit()
        return int(cursor.rowcount or 0)


def _get_cached_by_key(cache_key: str, allow_stale: bool = False) -> tuple[str, str] | None:
    ensure_weather_cache_db()
    now = datetime.now(KST)
    with _connect() as conn:
        row = conn.execute(
            "SELECT weather, temperature, fetched_at FROM weather_current_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if not row:
            return None
        fetched_at = _parse_dt(str(row["fetched_at"]))
        if not allow_stale and (not fetched_at or (now - fetched_at).total_seconds() > CACHE_TTL_SECONDS):
            return None
        conn.execute(
            """
            UPDATE weather_current_cache
            SET last_accessed_at = ?, access_count = access_count + 1
            WHERE cache_key = ?
            """,
            (now.isoformat(timespec="seconds"), cache_key),
        )
        conn.commit()
        return str(row["weather"]), str(row["temperature"])


def get_cached_weather(region: str) -> tuple[str, str] | None:
    request = _resolve_request(region)
    return _get_cached_by_key(request["cache_key"], allow_stale=False)


def get_stale_weather(region: str) -> tuple[str, str] | None:
    request = _resolve_request(region)
    return _get_cached_by_key(request["cache_key"], allow_stale=True)


def save_weather_cache(
    region: str,
    weather: str,
    temperature: str,
    source: str = "on_demand",
    *,
    request: dict | None = None,
) -> None:
    ensure_weather_cache_db()
    request = request or _resolve_request(region)
    now_text = datetime.now(KST).isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO weather_current_cache
                (cache_key, region, weather, temperature, source, fetched_at,
                 last_accessed_at, access_count, canonical_region, nx, ny)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                region = excluded.region,
                weather = excluded.weather,
                temperature = excluded.temperature,
                source = excluded.source,
                fetched_at = excluded.fetched_at,
                last_accessed_at = excluded.last_accessed_at,
                canonical_region = excluded.canonical_region,
                nx = excluded.nx,
                ny = excluded.ny,
                access_count = weather_current_cache.access_count + 1
            """,
            (
                request["cache_key"], request["requested_region"], str(weather),
                str(temperature), source, now_text, now_text,
                request["canonical_region"], request["nx"], request["ny"],
            ),
        )
        conn.commit()


def _circuit_is_open() -> bool:
    with _circuit_lock:
        return time.monotonic() < _circuit_open_until


def _record_success() -> None:
    global _consecutive_failures, _circuit_open_until
    with _circuit_lock:
        _consecutive_failures = 0
        _circuit_open_until = 0.0


def _record_failure() -> None:
    global _consecutive_failures, _circuit_open_until
    with _circuit_lock:
        _consecutive_failures += 1
        if _consecutive_failures >= CIRCUIT_FAILURE_THRESHOLD:
            _circuit_open_until = time.monotonic() + CIRCUIT_OPEN_SECONDS


def _wait_for_external_slot() -> None:
    global _last_external_call_monotonic
    with _rate_lock:
        now = time.monotonic()
        wait = EXTERNAL_MIN_INTERVAL_SECONDS - (now - _last_external_call_monotonic)
        if wait > 0:
            time.sleep(wait)
        _last_external_call_monotonic = time.monotonic()


def get_or_fetch_weather(
    region: str,
    fetcher: Callable[[str], tuple[str, str]],
) -> tuple[str, str]:
    request = _resolve_request(region)
    cache_key = request["cache_key"]
    if not cache_key:
        return "맑음", "20"

    cached = _get_cached_by_key(cache_key, allow_stale=False)
    if cached:
        return cached

    lock = _key_lock(cache_key)
    with lock:
        cached = _get_cached_by_key(cache_key, allow_stale=False)
        if cached:
            return cached

        stale = _get_cached_by_key(cache_key, allow_stale=True)
        if _circuit_is_open():
            if stale:
                return stale
            raise RuntimeError("weather external circuit is open")

        try:
            _wait_for_external_slot()
            weather, temperature = fetcher(request["canonical_region"])
            save_weather_cache(
                request["requested_region"], weather, temperature,
                source=f"on_demand:{request['match_method']}", request=request,
            )
            _record_success()
            return str(weather), str(temperature)
        except Exception:
            _record_failure()
            if stale:
                return stale
            raise


def get_weather_cache_record(region: str) -> dict | None:
    """프롬프트·관리 화면 확인용 최신 캐시 메타데이터를 반환합니다."""
    ensure_weather_cache_db()
    request = _resolve_request(region)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT cache_key, region, canonical_region, nx, ny, weather, temperature,
                   source, fetched_at, last_accessed_at, access_count
            FROM weather_current_cache WHERE cache_key = ?
            """,
            (request["cache_key"],),
        ).fetchone()
    return dict(row) if row else None


def weather_cache_status() -> dict:
    ensure_weather_cache_db()
    with _connect() as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM weather_current_cache").fetchone()[0]
        grid_count = conn.execute(
            "SELECT COUNT(*) FROM weather_current_cache WHERE nx IS NOT NULL AND ny IS NOT NULL"
        ).fetchone()[0]
    with _circuit_lock:
        circuit_open = time.monotonic() < _circuit_open_until
        failures = _consecutive_failures
    return {
        "rows": row_count,
        "grid_rows": grid_count,
        "ttl_seconds": CACHE_TTL_SECONDS,
        "min_external_interval_seconds": EXTERNAL_MIN_INTERVAL_SECONDS,
        "circuit_open": circuit_open,
        "consecutive_failures": failures,
    }
