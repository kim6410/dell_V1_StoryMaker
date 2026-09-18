# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.settings import settings
from app.integration.public_events import TourAPIClient, PublicEventsError

KST = ZoneInfo("Asia/Seoul")
_SYNC_LOCK = threading.Lock()
_SCHEDULER_STARTED = False


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.STORYMAKER_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def migrate_public_events_tables() -> None:
    conn = _connect()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS public_event_regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_code TEXT NOT NULL,
            region_name TEXT NOT NULL,
            district_code TEXT NOT NULL DEFAULT '',
            district_name TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            UNIQUE(region_code, district_code)
        );
        CREATE INDEX IF NOT EXISTS ix_public_event_regions_name
            ON public_event_regions(region_name, district_name);

        CREATE TABLE IF NOT EXISTS public_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL DEFAULT 'tourapi',
            source_id TEXT NOT NULL,
            content_type_id TEXT NOT NULL DEFAULT '15',
            title TEXT NOT NULL,
            start_date TEXT NOT NULL DEFAULT '',
            end_date TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            tel TEXT NOT NULL DEFAULT '',
            image TEXT NOT NULL DEFAULT '',
            thumbnail TEXT NOT NULL DEFAULT '',
            mapx TEXT NOT NULL DEFAULT '',
            mapy TEXT NOT NULL DEFAULT '',
            region_code TEXT NOT NULL DEFAULT '',
            district_code TEXT NOT NULL DEFAULT '',
            region_name TEXT NOT NULL DEFAULT '',
            district_name TEXT NOT NULL DEFAULT '',
            festival_type TEXT NOT NULL DEFAULT '',
            progress_type TEXT NOT NULL DEFAULT '',
            copyright_code TEXT NOT NULL DEFAULT '',
            source_modified_at TEXT NOT NULL DEFAULT '',
            synced_at TEXT NOT NULL,
            UNIQUE(source, source_id)
        );
        CREATE INDEX IF NOT EXISTS ix_public_events_dates ON public_events(start_date, end_date);
        CREATE INDEX IF NOT EXISTS ix_public_events_region ON public_events(region_name, district_name);

        CREATE TABLE IF NOT EXISTS public_places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL DEFAULT 'tourapi',
            source_id TEXT NOT NULL,
            content_type_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            address TEXT NOT NULL DEFAULT '',
            image TEXT NOT NULL DEFAULT '',
            thumbnail TEXT NOT NULL DEFAULT '',
            mapx TEXT NOT NULL DEFAULT '',
            mapy TEXT NOT NULL DEFAULT '',
            region_code TEXT NOT NULL DEFAULT '',
            district_code TEXT NOT NULL DEFAULT '',
            region_name TEXT NOT NULL DEFAULT '',
            district_name TEXT NOT NULL DEFAULT '',
            synced_at TEXT NOT NULL,
            UNIQUE(source, source_id)
        );
        CREATE INDEX IF NOT EXISTS ix_public_places_region ON public_places(region_name, district_name);

        CREATE TABLE IF NOT EXISTS public_event_sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            sync_date TEXT NOT NULL,
            event_count INTEGER NOT NULL DEFAULT 0,
            place_count INTEGER NOT NULL DEFAULT 0,
            region_count INTEGER NOT NULL DEFAULT 0,
            api_calls INTEGER NOT NULL DEFAULT 0,
            detail TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS ix_public_event_sync_runs_date ON public_event_sync_runs(sync_date, status);
        """)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(public_events)")}
        if "price_text" not in cols:
            conn.execute("ALTER TABLE public_events ADD COLUMN price_text TEXT NOT NULL DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def _norm(value: str) -> str:
    text = re.sub(r"\s+", "", str(value or ""))
    for suffix in ("특별자치도", "특별자치시", "특별시", "광역시"):
        text = text.replace(suffix, "")
    return text.lower()


def _region_maps(conn: sqlite3.Connection) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    region_names: dict[str, str] = {}
    district_names: dict[tuple[str, str], str] = {}
    for row in conn.execute("SELECT region_code, region_name, district_code, district_name FROM public_event_regions"):
        rc = str(row["region_code"] or "")
        dc = str(row["district_code"] or "")
        if rc and not dc:
            region_names[rc] = str(row["region_name"] or "")
        if rc and dc:
            district_names[(rc, dc)] = str(row["district_name"] or "")
            region_names.setdefault(rc, str(row["region_name"] or ""))
    return region_names, district_names


def _resolve_from_db(conn: sqlite3.Connection, text: str) -> tuple[str, str, str, str]:
    target = _norm(text)
    if not target:
        return "", "", "", ""
    rows = conn.execute(
        "SELECT region_code, region_name, district_code, district_name FROM public_event_regions ORDER BY CASE WHEN district_code='' THEN 1 ELSE 0 END"
    ).fetchall()
    best = ("", "", "", "")
    for row in rows:
        rn = str(row["region_name"] or "")
        dn = str(row["district_name"] or "")
        rkey = _norm(rn)
        dkey = _norm(dn)
        if rkey and (rkey in target or re.sub(r"(도|시)$", "", rkey) in target):
            if dkey and dkey in target:
                return str(row["region_code"]), rn, str(row["district_code"]), dn
            if not best[0]:
                best = (str(row["region_code"]), rn, "", "")
    return best


def _upsert_region(conn: sqlite3.Connection, rc: str, rn: str, dc: str, dn: str, stamp: str) -> None:
    conn.execute("""
        INSERT INTO public_event_regions(region_code, region_name, district_code, district_name, updated_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(region_code, district_code) DO UPDATE SET
            region_name=excluded.region_name,
            district_name=excluded.district_name,
            updated_at=excluded.updated_at
    """, (rc, rn, dc, dn, stamp))


def _sync_regions(client: TourAPIClient, conn: sqlite3.Connection, stamp: str) -> tuple[int, int]:
    api_calls = 0
    regions = client.regions()
    api_calls += 1
    count = 0
    for region in regions:
        rc, rn = region["code"], region["name"]
        _upsert_region(conn, rc, rn, "", "", stamp)
        count += 1
        try:
            districts = client.districts(rc)
            api_calls += 1
        except Exception:
            districts = []
        for district in districts:
            _upsert_region(conn, rc, rn, district["code"], district["name"], stamp)
            count += 1
    return count, api_calls


def _sync_festivals(client: TourAPIClient, conn: sqlite3.Connection, stamp: str) -> tuple[int, int]:
    today = datetime.now(KST).date()
    start = today - timedelta(days=7)
    end = today + timedelta(days=90)
    first = client.festivals(start, end, rows=100, page=1, arrange="Q")
    total = int(first.get("total_count") or 0)
    pages = max(1, (total + 99) // 100)
    api_calls = 1
    rows = list(first.get("items") or [])
    for page in range(2, pages + 1):
        result = client.festivals(start, end, rows=100, page=page, arrange="Q")
        api_calls += 1
        rows.extend(result.get("items") or [])

    region_names, district_names = _region_maps(conn)
    for item in rows:
        rc = str(item.get("region_code") or "")
        dc = str(item.get("district_code") or "")
        conn.execute("""
            INSERT INTO public_events(
                source, source_id, content_type_id, title, start_date, end_date, address, tel,
                image, thumbnail, mapx, mapy, region_code, district_code, region_name, district_name,
                festival_type, progress_type, copyright_code, source_modified_at, synced_at
            ) VALUES('tourapi',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source, source_id) DO UPDATE SET
                content_type_id=excluded.content_type_id, title=excluded.title,
                start_date=excluded.start_date, end_date=excluded.end_date, address=excluded.address,
                tel=excluded.tel, image=excluded.image, thumbnail=excluded.thumbnail,
                mapx=excluded.mapx, mapy=excluded.mapy, region_code=excluded.region_code,
                district_code=excluded.district_code, region_name=excluded.region_name,
                district_name=excluded.district_name, festival_type=excluded.festival_type,
                progress_type=excluded.progress_type, copyright_code=excluded.copyright_code,
                source_modified_at=excluded.source_modified_at, synced_at=excluded.synced_at
        """, (
            str(item.get("content_id") or ""), str(item.get("content_type_id") or "15"),
            str(item.get("title") or ""), str(item.get("start_date") or ""), str(item.get("end_date") or ""),
            str(item.get("address") or ""), str(item.get("tel") or ""), str(item.get("image") or ""),
            str(item.get("thumbnail") or ""), str(item.get("mapx") or ""), str(item.get("mapy") or ""),
            rc, dc, region_names.get(rc, ""), district_names.get((rc, dc), ""),
            str(item.get("festival_type") or ""), str(item.get("progress_type") or ""),
            str(item.get("copyright_code") or ""), str(item.get("modified_time") or ""), stamp,
        ))

    # TourAPI 목록 응답에는 입장료가 없으므로, DB에 비용이 없는 행사만 detailIntro2에서 1회 보강합니다.
    for item in rows:
        content_id = str(item.get("content_id") or "")
        content_type_id = str(item.get("content_type_id") or "15")
        if not content_id:
            continue
        current = conn.execute(
            "SELECT price_text FROM public_events WHERE source='tourapi' AND source_id=?",
            (content_id,),
        ).fetchone()
        if current and str(current[0] or "").strip():
            continue
        try:
            payload = client.request("detailIntro2", {
                "contentId": content_id, "contentTypeId": content_type_id,
            }, ttl=21600)
            body = payload.get("response", {}).get("body", {}) if isinstance(payload, dict) else {}
            items_raw = body.get("items", {}).get("item", []) if isinstance(body, dict) else []
            if isinstance(items_raw, dict):
                items_raw = [items_raw]
            intro = items_raw[0] if items_raw else {}
            price = str(intro.get("usetimefestival") or "").strip()
            if price:
                conn.execute(
                    "UPDATE public_events SET price_text=? WHERE source='tourapi' AND source_id=?",
                    (price, content_id),
                )
                api_calls += 1
        except Exception:
            continue
    # 오래 전에 끝난 행사는 DB 비대화를 막되 최근 1년은 보존합니다.
    cutoff = (today - timedelta(days=365)).isoformat()
    conn.execute("DELETE FROM public_events WHERE end_date <> '' AND end_date < ?", (cutoff,))
    return len(rows), api_calls


def _persona_regions(conn: sqlite3.Connection) -> list[str]:
    values: list[str] = []
    try:
        rows = conn.execute("SELECT region_alias, region FROM user_personas WHERE COALESCE(region_alias,'')<>'' OR COALESCE(region,'')<>''").fetchall()
    except sqlite3.Error:
        return values
    seen: set[str] = set()
    for row in rows:
        value = str(row["region_alias"] or row["region"] or "").strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _sync_places(client: TourAPIClient, conn: sqlite3.Connection, stamp: str) -> tuple[int, int]:
    count = 0
    api_calls = 0
    for region_text in _persona_regions(conn):
        rc, rn, dc, dn = _resolve_from_db(conn, region_text)
        if not rc:
            continue
        result = client.places(rc, dc, page=1, rows=50, arrange="Q")
        api_calls += 1
        for item in result.get("items") or []:
            item_rc = str(item.get("region_code") or rc)
            item_dc = str(item.get("district_code") or dc)
            region_names, district_names = _region_maps(conn)
            conn.execute("""
                INSERT INTO public_places(
                    source, source_id, content_type_id, title, address, image, thumbnail, mapx, mapy,
                    region_code, district_code, region_name, district_name, synced_at
                ) VALUES('tourapi',?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source, source_id) DO UPDATE SET
                    content_type_id=excluded.content_type_id, title=excluded.title, address=excluded.address,
                    image=excluded.image, thumbnail=excluded.thumbnail, mapx=excluded.mapx, mapy=excluded.mapy,
                    region_code=excluded.region_code, district_code=excluded.district_code,
                    region_name=excluded.region_name, district_name=excluded.district_name, synced_at=excluded.synced_at
            """, (
                str(item.get("content_id") or ""), str(item.get("content_type_id") or ""),
                str(item.get("title") or ""), str(item.get("address") or ""), str(item.get("image") or ""),
                str(item.get("thumbnail") or ""), str(item.get("mapx") or ""), str(item.get("mapy") or ""),
                item_rc, item_dc, region_names.get(item_rc, rn), district_names.get((item_rc, item_dc), dn), stamp,
            ))
            count += 1
    return count, api_calls


def latest_sync_status() -> dict[str, Any]:
    migrate_public_events_tables()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM public_event_sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        event_count = conn.execute("SELECT COUNT(*) FROM public_events").fetchone()[0]
        place_count = conn.execute("SELECT COUNT(*) FROM public_places").fetchone()[0]
        region_count = conn.execute("SELECT COUNT(*) FROM public_event_regions").fetchone()[0]
        return {
            "latest": dict(row) if row else None,
            "db": {"events": event_count, "places": place_count, "regions": region_count},
            "scheduler_started": _SCHEDULER_STARTED,
        }
    finally:
        conn.close()


def already_synced_today() -> bool:
    conn = _connect()
    try:
        today = datetime.now(KST).date().isoformat()
        row = conn.execute(
            "SELECT 1 FROM public_event_sync_runs WHERE sync_date=? AND status='success' LIMIT 1", (today,)
        ).fetchone()
        return bool(row)
    finally:
        conn.close()


def sync_public_events_once(force: bool = False) -> dict[str, Any]:
    migrate_public_events_tables()
    if not force and already_synced_today():
        return {"ok": True, "skipped": True, "reason": "already_synced_today", **latest_sync_status()}
    if not _SYNC_LOCK.acquire(blocking=False):
        return {"ok": False, "skipped": True, "reason": "sync_lock_active"}
    started = datetime.now(KST)
    sync_date = started.date().isoformat()
    conn = _connect()
    run_id = None
    try:
        cur = conn.execute(
            "INSERT INTO public_event_sync_runs(started_at,status,sync_date,detail) VALUES(?,?,?,?)",
            (started.isoformat(timespec="seconds"), "running", sync_date, ""),
        )
        run_id = cur.lastrowid
        conn.commit()
        client = TourAPIClient()
        if not client.configured:
            raise PublicEventsError("TOUR_API_KEY is not configured")

        stamp = datetime.now(KST).isoformat(timespec="seconds")
        region_count, calls1 = _sync_regions(client, conn, stamp)
        conn.commit()
        event_count, calls2 = _sync_festivals(client, conn, stamp)
        conn.commit()
        place_count, calls3 = _sync_places(client, conn, stamp)
        conn.commit()
        finished = datetime.now(KST)
        detail = json.dumps({"window_days": {"past": 7, "future": 90}}, ensure_ascii=False)
        conn.execute("""
            UPDATE public_event_sync_runs
            SET finished_at=?, status='success', event_count=?, place_count=?, region_count=?, api_calls=?, detail=?
            WHERE id=?
        """, (finished.isoformat(timespec="seconds"), event_count, place_count, region_count, calls1+calls2+calls3, detail, run_id))
        conn.commit()
        return {"ok": True, "event_count": event_count, "place_count": place_count, "region_count": region_count, "api_calls": calls1+calls2+calls3}
    except Exception as exc:
        if run_id:
            try:
                conn.execute(
                    "UPDATE public_event_sync_runs SET finished_at=?, status='failed', detail=? WHERE id=?",
                    (datetime.now(KST).isoformat(timespec="seconds"), f"{type(exc).__name__}: {exc}"[:1000], run_id),
                )
                conn.commit()
            except Exception:
                pass
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()
        _SYNC_LOCK.release()


def _event_rows_for_region(conn: sqlite3.Connection, region_text: str, limit: int) -> list[sqlite3.Row]:
    rc, rn, dc, dn = _resolve_from_db(conn, region_text)
    if not rc:
        return []
    today = datetime.now(KST).date().isoformat()
    future = (datetime.now(KST).date() + timedelta(days=45)).isoformat()
    if dc:
        return conn.execute("""
            SELECT * FROM public_events
            WHERE region_code=? AND district_code=?
              AND (end_date='' OR end_date>=?) AND (start_date='' OR start_date<=?)
            ORDER BY CASE WHEN image<>'' THEN 0 ELSE 1 END, start_date ASC, source_modified_at DESC
            LIMIT ?
        """, (rc, dc, today, future, limit)).fetchall()
    return conn.execute("""
        SELECT * FROM public_events
        WHERE region_code=?
          AND (end_date='' OR end_date>=?) AND (start_date='' OR start_date<=?)
        ORDER BY CASE WHEN image<>'' THEN 0 ELSE 1 END, start_date ASC, source_modified_at DESC
        LIMIT ?
    """, (rc, today, future, limit)).fetchall()


def _place_rows_for_region(conn: sqlite3.Connection, region_text: str, limit: int) -> list[sqlite3.Row]:
    rc, rn, dc, dn = _resolve_from_db(conn, region_text)
    if not rc:
        return []
    if dc:
        return conn.execute("""
            SELECT * FROM public_places WHERE region_code=? AND district_code=?
            ORDER BY CASE WHEN image<>'' THEN 0 ELSE 1 END, title LIMIT ?
        """, (rc, dc, limit)).fetchall()
    return conn.execute("""
        SELECT * FROM public_places WHERE region_code=?
        ORDER BY CASE WHEN image<>'' THEN 0 ELSE 1 END, title LIMIT ?
    """, (rc, limit)).fetchall()


def build_public_event_context_from_db(region_text: str, limit: int = 3) -> str:
    migrate_public_events_tables()
    if not str(region_text or "").strip():
        return ""
    conn = _connect()
    try:
        events = _event_rows_for_region(conn, region_text, limit)
        places = _place_rows_for_region(conn, region_text, limit)
        if not events and not places:
            return ""
        rc, rn, dc, dn = _resolve_from_db(conn, region_text)
        sync = conn.execute("SELECT finished_at FROM public_event_sync_runs WHERE status='success' ORDER BY id DESC LIMIT 1").fetchone()
        lines = [
            "### [StoryMaker 지역 공공데이터 DB 기반 SEO 컨텍스트]",
            f"- 기준 지역: {' '.join(x for x in [rn, dn] if x) or region_text}",
            f"- DB 최근 동기화: {sync['finished_at'] if sync else '동기화 기록 없음'}",
            "- 원출처: 한국관광공사 TourAPI KorService2 / StoryMaker 일일 동기화 DB",
            "- 중요: 이 프롬프트 생성 시점에는 외부 TourAPI를 호출하지 않고 로컬 DB만 조회했습니다.",
        ]
        if events:
            lines += ["", "#### 현재/예정 지역 축제·행사"]
            for idx, row in enumerate(events, 1):
                period = " ~ ".join(x for x in [row["start_date"], row["end_date"]] if x)
                detail = " / ".join(x for x in [row["title"], period, row["address"]] if x)
                lines.append(f"{idx}. {detail}")
        if places:
            lines += ["", "#### 지역 관광·생활권 참고 장소"]
            for idx, row in enumerate(places, 1):
                detail = " / ".join(x for x in [row["title"], row["address"]] if x)
                lines.append(f"{idx}. {detail}")
        lines += [
            "", "#### Gemini 활용 지침",
            "1. 위 정보는 지역 생활 맥락과 검색의도를 이해하는 보조자료입니다. 업체가 행사에 참여·후원·협찬했다는 사실은 입력자료에 없으면 만들지 않습니다.",
            "2. 실제 포스팅 주제와 자연스럽게 연결될 때만 행사 1건 정도를 가볍게 언급하고, 연관성이 낮으면 지역명·동네명만 SEO에 활용합니다.",
            "3. 업체 서비스와 사용자가 입력한 실제 내용이 항상 글의 주인공이어야 합니다.",
            "4. 지역 + 서비스 + 실제 문제/목적 조합을 제목·첫 문단·소제목·해시태그에 자연스럽게 분산합니다.",
            "5. 방문객수·순위·후기·주차·할인 등 DB에 없는 사실을 지어내지 않습니다.",
            "6. 같은 지역명이나 행사명을 검색 노출 목적으로 반복 나열하지 않습니다.",
        ]
        return "\n".join(lines)
    finally:
        conn.close()


def _scheduler_loop() -> None:
    # 기동 직후에는 서비스 안정화를 기다린 뒤, 오늘 동기화가 없을 때만 실행합니다.
    time.sleep(20)
    while True:
        now = datetime.now(KST)
        if not already_synced_today() and (now.hour > 3 or (now.hour == 3 and now.minute >= 20)):
            sync_public_events_once(force=False)
        time.sleep(900)


def start_public_events_scheduler() -> None:
    global _SCHEDULER_STARTED
    if _SCHEDULER_STARTED:
        return
    migrate_public_events_tables()
    _SCHEDULER_STARTED = True
    thread = threading.Thread(target=_scheduler_loop, name="storymaker-public-events-sync", daemon=True)
    thread.start()
