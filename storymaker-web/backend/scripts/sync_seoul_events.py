# -*- coding: utf-8 -*-
"""Daily Seoul culturalEventInfo collector for StoryMaker."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
API_BASE = "http://openapi.seoul.go.kr:8088"
SOURCE = "seoul_cultural_event"
PAGE_SIZE = 1000


def clean(v):
    return str(v or "").strip()


def ymd(v):
    s = clean(v)
    if not s:
        return ""
    return s[:10].replace("-", "")


def source_id(row):
    stable = "|".join([
        clean(row.get("TITLE")),
        clean(row.get("STRTDATE")),
        clean(row.get("END_DATE")),
        clean(row.get("PLACE")),
    ])
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:32]


def fetch_page(key, start, end):
    url = f"{API_BASE}/{key}/json/culturalEventInfo/{start}/{end}/"
    req = urllib.request.Request(url, headers={"User-Agent": "StoryMaker/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "culturalEventInfo" not in payload:
        result = payload.get("RESULT") or {}
        raise RuntimeError(f"Seoul API error: {result.get('CODE')} {result.get('MESSAGE')}")
    root = payload["culturalEventInfo"]
    result = root.get("RESULT") or {}
    if result.get("CODE") not in (None, "INFO-000"):
        raise RuntimeError(f"Seoul API error: {result.get('CODE')} {result.get('MESSAGE')}")
    return int(root.get("list_total_count") or 0), list(root.get("row") or [])


def month_intersects(row, month):
    month_start = month + "01"
    y, m = int(month[:4]), int(month[4:6])
    next_month = f"{y+1:04d}0101" if m == 12 else f"{y:04d}{m+1:02d}01"
    start = ymd(row.get("STRTDATE"))
    end = ymd(row.get("END_DATE")) or start
    return bool(start and start < next_month and end >= month_start)


def ensure_schema(conn):
    conn.executescript("""
    PRAGMA journal_mode=WAL;
    PRAGMA busy_timeout=30000;
    CREATE TABLE IF NOT EXISTS public_event_source_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        UNIQUE(source, source_id)
    );
    CREATE TABLE IF NOT EXISTS public_event_source_sync_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        target_month TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL,
        total_api_rows INTEGER NOT NULL DEFAULT 0,
        matched_rows INTEGER NOT NULL DEFAULT 0,
        inserted_or_updated INTEGER NOT NULL DEFAULT 0,
        error_message TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS ix_public_event_source_sync_runs
        ON public_event_source_sync_runs(source, started_at);
    """)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default=datetime.now(KST).strftime("%Y%m"))
    args = ap.parse_args()
    month = args.month.replace("-", "")[:6]
    if len(month) != 6 or not month.isdigit():
        raise SystemExit("--month must be YYYYMM or YYYY-MM")

    key = clean(os.getenv("SEOUL_OPENAPI_KEY"))
    if not key:
        raise SystemExit("SEOUL_OPENAPI_KEY is missing")

    db_path = os.getenv("STORYMAKER_DB_PATH", "/data/storymaker.db")
    started = datetime.now(KST).isoformat(timespec="seconds")
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    ensure_schema(conn)
    run_id = conn.execute(
        """INSERT INTO public_event_source_sync_runs
           (source,target_month,started_at,status) VALUES (?,?,?,'running')""",
        (SOURCE, month, started),
    ).lastrowid
    conn.commit()

    total = matched = upserts = 0
    try:
        first = 1
        while True:
            end = first + PAGE_SIZE - 1
            api_total, rows = fetch_page(key, first, end)
            total = api_total
            now = datetime.now(KST).isoformat(timespec="seconds")
            for row in rows:
                if not month_intersects(row, month):
                    continue
                matched += 1
                sid = source_id(row)
                start_date = ymd(row.get("STRTDATE"))
                end_date = ymd(row.get("END_DATE"))
                title = clean(row.get("TITLE"))
                place = clean(row.get("PLACE"))
                gu = clean(row.get("GUNAME"))
                tel = clean(row.get("INQUIRY"))
                image = clean(row.get("MAIN_IMG"))
                mapx = clean(row.get("LOT"))
                mapy = clean(row.get("LAT"))
                festival_type = clean(row.get("CODENAME"))
                price_text = clean(row.get("USE_FEE"))
                modified = clean(row.get("RGSTDATE"))
                conn.execute(
                    """INSERT INTO public_events
                    (source,source_id,content_type_id,title,start_date,end_date,address,tel,image,thumbnail,
                     mapx,mapy,region_code,district_code,region_name,district_name,festival_type,
                     progress_type,copyright_code,source_modified_at,synced_at,price_text)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source,source_id) DO UPDATE SET
                     title=excluded.title,start_date=excluded.start_date,end_date=excluded.end_date,
                     address=excluded.address,tel=excluded.tel,image=excluded.image,thumbnail=excluded.thumbnail,
                     mapx=excluded.mapx,mapy=excluded.mapy,region_name=excluded.region_name,
                     district_name=excluded.district_name,festival_type=excluded.festival_type,
                     source_modified_at=excluded.source_modified_at,synced_at=excluded.synced_at,
                     price_text=excluded.price_text""",
                    (SOURCE,sid,"15",title,start_date,end_date,place,tel,image,image,mapx,mapy,
                     "1","", "서울",gu,festival_type,"","",modified,now,price_text),
                )
                conn.execute(
                    """INSERT INTO public_event_source_raw
                    (source,source_id,payload_json,first_seen_at,last_seen_at)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(source,source_id) DO UPDATE SET
                      payload_json=excluded.payload_json,last_seen_at=excluded.last_seen_at""",
                    (SOURCE,sid,json.dumps(row,ensure_ascii=False),now,now),
                )
                upserts += 1
            conn.commit()
            if not rows or end >= api_total:
                break
            first += PAGE_SIZE

        finished = datetime.now(KST).isoformat(timespec="seconds")
        conn.execute(
            """UPDATE public_event_source_sync_runs
               SET finished_at=?,status='success',total_api_rows=?,matched_rows=?,inserted_or_updated=?
               WHERE id=?""",
            (finished,total,matched,upserts,run_id),
        )
        conn.commit()
        print(json.dumps({"source":SOURCE,"month":month,"total_api_rows":total,
                          "matched_rows":matched,"upserts":upserts,"status":"success"},
                         ensure_ascii=False))
    except Exception as exc:
        finished = datetime.now(KST).isoformat(timespec="seconds")
        conn.execute(
            """UPDATE public_event_source_sync_runs
               SET finished_at=?,status='failed',total_api_rows=?,matched_rows=?,
                   inserted_or_updated=?,error_message=? WHERE id=?""",
            (finished,total,matched,upserts,str(exc)[:1000],run_id),
        )
        conn.commit()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
