#!/home/bourne/Weather/.venv/bin/python
# -*- coding: utf-8 -*-
"""Store one genuine KMA ultra-short observation per active grid and hour."""
from __future__ import annotations

import argparse
import fcntl
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

WEATHER_ROOT = Path('/home/bourne/Weather')
sys.path.insert(0, str(WEATHER_ROOT))
import weather as kma  # noqa: E402

KST = ZoneInfo('Asia/Seoul')
DB = Path('/home/bourne/StoryMaker_1/database/weather_cache.db')
LOCK = Path('/tmp/storymaker-v1-weather-kma-grid.lock')
PTY = {0: '맑음', 1: '비', 2: '비 또는 눈', 3: '눈', 5: '빗방울', 6: '빗방울 또는 눈날림', 7: '눈날림'}


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=NORMAL')
    con.execute('PRAGMA busy_timeout=30000')
    return con


def items(payload: dict) -> list[dict]:
    try:
        return payload['response']['body']['items']['item'] or []
    except Exception:
        return []


def fetch_grid(nx: int, ny: int) -> tuple[str, float, str]:
    base_date, base_time = kma.get_base_datetime()
    status, payload = kma.call_kma('getUltraSrtNcst', base_date, base_time, nx, ny)
    if status != 200 or not kma.check_kma_response(payload, '초단기실황'):
        raise RuntimeError(f'KMA response failed: HTTP {status}')
    values: dict[str, str] = {}
    observed = f'{base_date}{base_time}'
    for row in items(payload):
        category = str(row.get('category') or '')
        values[category] = str(row.get('obsrValue') or '')
        if row.get('baseDate') and row.get('baseTime'):
            observed = f"{row['baseDate']}{row['baseTime']}"
    if not values.get('T1H'):
        raise RuntimeError('KMA T1H missing')
    temp = float(values['T1H'])
    pty_code = int(float(values.get('PTY') or 0))
    condition = PTY.get(pty_code, '날씨 확인')
    return condition, temp, observed


def update_current_cache(con: sqlite3.Connection, row: sqlite3.Row, weather: str, temp: float, now_text: str) -> None:
    con.execute(
        """
        INSERT INTO weather_current_cache
          (cache_key, region, weather, temperature, source, fetched_at,
           last_accessed_at, access_count, canonical_region, nx, ny)
        VALUES (?, ?, ?, ?, 'kma_hourly_member_grid', ?, ?, 1, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
          region=excluded.region, weather=excluded.weather, temperature=excluded.temperature,
          source=excluded.source, fetched_at=excluded.fetched_at,
          last_accessed_at=excluded.last_accessed_at,
          canonical_region=excluded.canonical_region, nx=excluded.nx, ny=excluded.ny,
          access_count=weather_current_cache.access_count + 1
        """,
        (row['cache_key'], row['canonical_region'], weather, str(temp), now_text, now_text,
         row['canonical_region'], row['nx'], row['ny']),
    )


def update_daily(con: sqlite3.Connection, row: sqlite3.Row, day: str, now_text: str) -> None:
    samples = con.execute(
        """SELECT weather,temperature_c FROM weather_hourly_snapshots
           WHERE nx=? AND ny=? AND substr(observed_hour,1,10)=? ORDER BY observed_hour""",
        (row['nx'], row['ny'], day),
    ).fetchall()
    temps = [float(x['temperature_c']) for x in samples if x['temperature_c'] is not None]
    dominant = Counter(str(x['weather']) for x in samples if str(x['weather']).strip()).most_common(1)
    con.execute(
        """
        INSERT INTO weather_daily_grid_summaries
          (nx,ny,cache_key,canonical_region,weather_date,min_temp_c,max_temp_c,avg_temp_c,
           dominant_weather,sample_count,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(nx,ny,weather_date) DO UPDATE SET
          cache_key=excluded.cache_key, canonical_region=excluded.canonical_region,
          min_temp_c=excluded.min_temp_c, max_temp_c=excluded.max_temp_c,
          avg_temp_c=excluded.avg_temp_c, dominant_weather=excluded.dominant_weather,
          sample_count=excluded.sample_count, updated_at=excluded.updated_at
        """,
        (row['nx'], row['ny'], row['cache_key'], row['canonical_region'], day,
         min(temps) if temps else None, max(temps) if temps else None,
         round(sum(temps)/len(temps),2) if temps else None,
         dominant[0][0] if dominant else None, len(samples), now_text),
    )


def run(force: bool) -> int:
    now = datetime.now(KST)
    hour = now.replace(minute=0, second=0, microsecond=0).isoformat(timespec='seconds')
    now_text = now.isoformat(timespec='seconds')
    day = now.date().isoformat()
    with connect() as con:
        grids = con.execute(
            'SELECT * FROM weather_active_grids WHERE is_active=1 ORDER BY nx,ny'
        ).fetchall()
        success = skipped = failed = 0
        for row in grids:
            exists = con.execute(
                'SELECT 1 FROM weather_hourly_snapshots WHERE nx=? AND ny=? AND observed_hour=?',
                (row['nx'], row['ny'], hour),
            ).fetchone()
            if exists and not force:
                skipped += 1
                continue
            try:
                condition, temp, kma_observed = fetch_grid(int(row['nx']), int(row['ny']))
                con.execute(
                    """
                    INSERT INTO weather_hourly_snapshots
                      (cache_key,nx,ny,canonical_region,observed_hour,weather,temperature_c,source,fetched_at)
                    VALUES (?,?,?,?,?,?,?,'kma_hourly_member_grid',?)
                    ON CONFLICT(nx,ny,observed_hour) DO UPDATE SET
                      cache_key=excluded.cache_key, canonical_region=excluded.canonical_region,
                      weather=excluded.weather, temperature_c=excluded.temperature_c,
                      source=excluded.source, fetched_at=excluded.fetched_at
                    """,
                    (row['cache_key'],row['nx'],row['ny'],row['canonical_region'],hour,condition,temp,now_text),
                )
                update_current_cache(con,row,condition,temp,now_text)
                update_daily(con,row,day,now_text)
                con.execute(
                    """UPDATE weather_active_grids SET last_collected_hour=?,last_success_at=?,last_error=NULL
                       WHERE cache_key=?""", (hour,now_text,row['cache_key']))
                con.commit()
                success += 1
                print(f"OK {row['cache_key']} {condition} {temp:.1f}C KMA={kma_observed}", flush=True)
            except Exception as exc:
                failed += 1
                con.execute('UPDATE weather_active_grids SET last_error=? WHERE cache_key=?',
                            (f'{type(exc).__name__}: {exc}'[:500],row['cache_key']))
                con.commit()
                print(f"ERROR {row['cache_key']}: {exc}", flush=True)
        print(f'active_grids={len(grids)} success={success} skipped={skipped} failed={failed}', flush=True)
        return 1 if failed and not success and grids else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open('w') as fp:
        try: fcntl.flock(fp.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('collector already running'); return 0
        return run(args.force)

if __name__ == '__main__':
    raise SystemExit(main())
