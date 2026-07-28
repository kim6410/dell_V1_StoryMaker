# -*- coding: utf-8 -*-
"""법정동·행정동·기상청 격자 매핑 서비스.

법정동 DB와 기상청 행정구역 격자 CSV를 결합해 모든 선택 지역을
최대한 정확한 nx/ny 격자로 연결합니다. 운영 조회는 SQLite 인덱스를
사용하며 원본 TXT/CSV를 매 요청마다 읽지 않습니다.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.settings import settings

KST = ZoneInfo("Asia/Seoul")
CACHE_DB_PATH = Path(settings.STORYMAKER_DB_PATH).with_name("weather_cache.db")
KMA_GRID_CSV_CANDIDATES = [
    Path("/data/kma_location_grid_simplified.csv"),
    Path(settings.STORYMAKER_DB_PATH).with_name("kma_location_grid_simplified.csv"),
    Path("/home/bourne/Weather/kma_location_grid_simplified.csv"),
]
WEATHER_CONFIG_CANDIDATES = [
    Path("/data/weather_server_config.json"),
    Path(settings.STORYMAKER_DB_PATH).with_name("weather_server_config.json"),
    Path("/home/bourne/Weather/weather_server_config.json"),
]

_PROVINCE_CANONICAL = {
    "서울": "서울특별시", "서울시": "서울특별시",
    "부산": "부산광역시", "부산시": "부산광역시",
    "대구": "대구광역시", "대구시": "대구광역시",
    "인천": "인천광역시", "인천시": "인천광역시",
    "광주": "광주광역시", "광주시": "광주광역시",
    "대전": "대전광역시", "대전시": "대전광역시",
    "울산": "울산광역시", "울산시": "울산광역시",
    "세종": "세종특별자치시", "세종시": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도", "강원도": "강원특별자치도",
    "충북": "충청북도", "충남": "충청남도",
    "전북": "전북특별자치도", "전라북도": "전북특별자치도",
    "전남": "전라남도", "경북": "경상북도", "경남": "경상남도",
    "제주": "제주특별자치도", "제주도": "제주특별자치도",
}


def _connect() -> sqlite3.Connection:
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def normalize_region_name(value: str) -> str:
    text = re.sub(r"[\s·ㆍ]+", " ", str(value or "")).strip()
    text = text.replace("．", ".")
    parts = text.split()
    if parts and parts[0] in _PROVINCE_CANONICAL:
        parts[0] = _PROVINCE_CANONICAL[parts[0]]
    return " ".join(parts)


def compact_region_name(value: str) -> str:
    return re.sub(r"[^0-9가-힣]", "", normalize_region_name(value))


def _locality_stem(value: str) -> str:
    text = compact_region_name(value)
    text = re.sub(r"(읍|면|동|가|리)$", "", text)
    return text


def ensure_region_grid_tables() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS weather_grid_locations (
                admin_code TEXT PRIMARY KEY,
                sido TEXT NOT NULL,
                sigungu TEXT NOT NULL DEFAULT '',
                eupmyeondong TEXT NOT NULL DEFAULT '',
                full_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                nx INTEGER NOT NULL,
                ny INTEGER NOT NULL,
                latitude REAL,
                longitude REAL,
                updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ux_weather_grid_locations_full
                ON weather_grid_locations(normalized_name);
            CREATE INDEX IF NOT EXISTS ix_weather_grid_locations_district
                ON weather_grid_locations(sido, sigungu);
            CREATE INDEX IF NOT EXISTS ix_weather_grid_locations_grid
                ON weather_grid_locations(nx, ny);

            CREATE TABLE IF NOT EXISTS legal_weather_grid_map (
                legal_code TEXT PRIMARY KEY,
                legal_full_name TEXT NOT NULL,
                legal_normalized_name TEXT NOT NULL,
                legal_compact_name TEXT NOT NULL,
                region_type TEXT NOT NULL,
                target_admin_code TEXT NOT NULL,
                target_full_name TEXT NOT NULL,
                nx INTEGER NOT NULL,
                ny INTEGER NOT NULL,
                match_method TEXT NOT NULL,
                confidence REAL NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_legal_weather_grid_normalized
                ON legal_weather_grid_map(legal_normalized_name);
            CREATE INDEX IF NOT EXISTS ix_legal_weather_grid_compact
                ON legal_weather_grid_map(legal_compact_name);
            CREATE INDEX IF NOT EXISTS ix_legal_weather_grid_grid
                ON legal_weather_grid_map(nx, ny);

            CREATE TABLE IF NOT EXISTS weather_region_aliases (
                alias_key TEXT PRIMARY KEY,
                alias_name TEXT NOT NULL,
                target_admin_code TEXT NOT NULL,
                target_full_name TEXT NOT NULL,
                nx INTEGER NOT NULL,
                ny INTEGER NOT NULL,
                match_method TEXT NOT NULL,
                confidence REAL NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_weather_region_alias_target
                ON weather_region_aliases(target_admin_code);
            """
        )
        conn.commit()


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _load_kma_rows() -> list[dict]:
    path = _first_existing(KMA_GRID_CSV_CANDIDATES)
    if path is None:
        raise FileNotFoundError("kma_location_grid_simplified.csv not found")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _load_manual_aliases() -> dict[str, str]:
    path = _first_existing(WEATHER_CONFIG_CANDIDATES)
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in (payload.get("aliases") or {}).items()}
    except Exception:
        return {}


def rebuild_region_grid_mapping() -> dict:
    """원본 DB와 CSV를 읽어 매핑 테이블을 원자적으로 재구축합니다."""
    ensure_region_grid_tables()
    now_text = datetime.now(KST).isoformat(timespec="seconds")
    kma_rows = _load_kma_rows()

    main = sqlite3.connect(str(settings.STORYMAKER_DB_PATH), timeout=10)
    main.row_factory = sqlite3.Row
    try:
        legal_rows = [dict(row) for row in main.execute(
            """
            SELECT legal_code, full_name, sido, sigungu, locality,
                   region_type, selectable, is_active
            FROM legal_districts
            WHERE is_active = 1
            ORDER BY legal_code
            """
        )]
    finally:
        main.close()

    prepared: list[dict] = []
    seen_kma_names: set[str] = set()
    for row in kma_rows:
        full = normalize_region_name(row.get("full_name") or "")
        if not full or not row.get("nx") or not row.get("ny"):
            continue
        # 원본 CSV의 동일 지역명 중복(예: 이어도)은 같은 격자 한 건만 유지합니다.
        if full in seen_kma_names:
            continue
        seen_kma_names.add(full)
        prepared.append({
            "admin_code": str(row.get("admin_code") or ""),
            "sido": normalize_region_name(row.get("sido") or ""),
            "sigungu": str(row.get("sigungu") or "").strip(),
            "eupmyeondong": str(row.get("eupmyeondong") or "").strip(),
            "full_name": full,
            "normalized_name": full,
            "nx": int(float(row["nx"])),
            "ny": int(float(row["ny"])),
            "latitude": float(row["lat"]) if row.get("lat") else None,
            "longitude": float(row["lon"]) if row.get("lon") else None,
        })

    by_full = {row["normalized_name"]: row for row in prepared}
    by_compact = defaultdict(list)
    by_district = defaultdict(list)
    by_sigungu = defaultdict(list)
    district_rows = {}
    province_rows = {}
    for row in prepared:
        by_compact[compact_region_name(row["full_name"])].append(row)
        key = (row["sido"], row["sigungu"])
        by_district[key].append(row)
        if row["sigungu"]:
            by_sigungu[row["sigungu"]].append(row)
        if row["sigungu"] and not row["eupmyeondong"]:
            district_rows[key] = row
        if not row["sigungu"] and not row["eupmyeondong"]:
            province_rows[row["sido"]] = row

    mappings: list[dict] = []
    mapped_target_by_legal_name: dict[str, dict] = {}
    method_counts = Counter()

    def choose(legal: dict) -> tuple[dict | None, str, float]:
        full = normalize_region_name(legal["full_name"])
        exact = by_full.get(full)
        if exact:
            return exact, "exact", 1.0

        compact_matches = by_compact.get(compact_region_name(full), [])
        if len(compact_matches) == 1:
            return compact_matches[0], "normalized", 0.99

        tokens = full.split()
        region_type = str(legal.get("region_type") or "")

        # 리 단위는 반드시 부모 읍·면 격자를 공유합니다.
        if region_type == "ri" and len(tokens) >= 2:
            parent = " ".join(tokens[:-1])
            target = by_full.get(parent)
            if target:
                return target, "parent_eupmyeon", 0.98
            parent_matches = by_compact.get(compact_region_name(parent), [])
            if len(parent_matches) == 1:
                return parent_matches[0], "parent_eupmyeon_normalized", 0.97
            mapped_parent = mapped_target_by_legal_name.get(parent)
            if mapped_parent:
                return mapped_parent, "parent_legal_mapping", 0.96

        sido = normalize_region_name(legal.get("sido") or "")
        sigungu = str(legal.get("sigungu") or "").strip()
        locality = str(legal.get("locality") or "").strip()
        district_source = by_district.get((sido, sigungu), [])
        if not district_source and sigungu:
            # 광역 명칭이 기상청 기준과 달라도 시군구가 전국에서 유일하면 그 기존 체계를 사용합니다.
            sigungu_rows = by_sigungu.get(sigungu, [])
            sigungu_sidos = {r["sido"] for r in sigungu_rows}
            if len(sigungu_sidos) == 1:
                district_source = sigungu_rows
        candidates = [r for r in district_source if r["eupmyeondong"]]

        # 광역 명칭이 달라도 부모 읍면 이름이 동일하면 해당 기상청 격자를 사용합니다.
        if region_type == "ri" and len(tokens) >= 2 and candidates:
            parent_locality = tokens[-2]
            exact_parent = [r for r in candidates if compact_region_name(r["eupmyeondong"]) == compact_region_name(parent_locality)]
            if len(exact_parent) == 1:
                return exact_parent[0], "parent_eupmyeon_sigungu", 0.96

        if locality and candidates:
            exact_locality = [r for r in candidates if compact_region_name(r["eupmyeondong"]) == compact_region_name(locality)]
            if len(exact_locality) == 1:
                return exact_locality[0], "sigungu_exact_locality", 0.95

        # 복합 행정동: 청운동/효자동 -> 청운효자동처럼 같은 구 안에서 유일한 포함 관계만 채택합니다.
        stem = _locality_stem(locality)
        if stem and len(stem) >= 2:
            fuzzy = []
            for row in candidates:
                admin_stem = _locality_stem(row["eupmyeondong"])
                if stem in admin_stem or (len(admin_stem) >= 2 and admin_stem in stem):
                    fuzzy.append(row)
            unique_codes = {r["admin_code"]: r for r in fuzzy}
            if len(unique_codes) == 1:
                return next(iter(unique_codes.values())), "compound_admin_alias", 0.90

        # 불명확한 법정동은 동일 시군구 대표 격자로 안전하게 폴백합니다.
        district = district_rows.get((sido, sigungu))
        if not district and district_source:
            district_candidates = [r for r in district_source if not r["eupmyeondong"]]
            if len(district_candidates) == 1:
                district = district_candidates[0]
        if district:
            method = "district_fallback" if district["sido"] == sido else "sigungu_district_fallback"
            return district, method, 0.60 if method == "district_fallback" else 0.55
        province = province_rows.get(sido)
        if province:
            return province, "province_fallback", 0.40
        if sido == "전남광주통합특별시":
            special = province_rows.get("광주광역시") or province_rows.get("전라남도")
            if special:
                return special, "special_province_fallback", 0.30
        return None, "unmatched", 0.0

    for legal in legal_rows:
        target, method, confidence = choose(legal)
        method_counts[method] += 1
        if not target:
            continue
        mapped_target_by_legal_name[normalize_region_name(legal["full_name"])] = target
        mappings.append({
            "legal_code": str(legal["legal_code"]),
            "legal_full_name": str(legal["full_name"]),
            "legal_normalized_name": normalize_region_name(legal["full_name"]),
            "legal_compact_name": compact_region_name(legal["full_name"]),
            "region_type": str(legal.get("region_type") or ""),
            "target_admin_code": target["admin_code"],
            "target_full_name": target["full_name"],
            "nx": target["nx"],
            "ny": target["ny"],
            "match_method": method,
            "confidence": confidence,
            "verified": 1 if confidence >= 0.97 else 0,
        })

    alias_rows: dict[str, dict] = {}

    def add_alias(alias: str, target: dict, method: str, confidence: float) -> None:
        alias_name = normalize_region_name(alias)
        if not alias_name:
            return
        for key in {alias_name, compact_region_name(alias_name)}:
            if not key:
                continue
            current = alias_rows.get(key)
            row = {
                "alias_key": key,
                "alias_name": alias_name,
                "target_admin_code": target["admin_code"],
                "target_full_name": target["full_name"],
                "nx": target["nx"], "ny": target["ny"],
                "match_method": method, "confidence": confidence,
            }
            if current is None or confidence > current["confidence"]:
                alias_rows[key] = row

    for row in prepared:
        add_alias(row["full_name"], row, "kma_name", 1.0)
    target_by_code = {row["admin_code"]: row for row in prepared}
    for row in mappings:
        target = target_by_code.get(row["target_admin_code"])
        if target:
            add_alias(row["legal_full_name"], target, row["match_method"], row["confidence"])

    # 짧은 이름은 전국에서 하나의 대상만 가리키는 경우에만 자동 별칭으로 허용합니다.
    short_candidates = defaultdict(dict)
    mapping_by_legal_code = {row["legal_code"]: row for row in mappings}
    for legal in legal_rows:
        mapped = mapping_by_legal_code.get(str(legal["legal_code"]))
        if not mapped:
            continue
        locality = str(legal.get("locality") or "").strip()
        if locality:
            short_candidates[normalize_region_name(locality)][mapped["target_admin_code"]] = mapped
    for short_name, targets in short_candidates.items():
        if len(targets) == 1:
            mapped = next(iter(targets.values()))
            target = target_by_code.get(mapped["target_admin_code"])
            if target:
                add_alias(short_name, target, "unique_short_alias", min(0.85, mapped["confidence"]))

    for alias, canonical in _load_manual_aliases().items():
        target = by_full.get(normalize_region_name(canonical))
        if target:
            add_alias(alias, target, "manual_weather_alias", 1.0)
            # 짧은 수동 별칭은 대상의 시도·시군구를 붙인 전체 주소형 별칭도 생성합니다.
            alias_normalized = normalize_region_name(alias)
            if alias_normalized and " " not in alias_normalized and target.get("sigungu"):
                add_alias(
                    f"{target['sido']} {target['sigungu']} {alias_normalized}",
                    target,
                    "manual_weather_alias_full",
                    1.0,
                )

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM weather_grid_locations")
        conn.execute("DELETE FROM legal_weather_grid_map")
        conn.execute("DELETE FROM weather_region_aliases")
        conn.executemany(
            """
            INSERT INTO weather_grid_locations
            (admin_code,sido,sigungu,eupmyeondong,full_name,normalized_name,nx,ny,latitude,longitude,updated_at)
            VALUES (:admin_code,:sido,:sigungu,:eupmyeondong,:full_name,:normalized_name,:nx,:ny,:latitude,:longitude,:updated_at)
            """,
            [{**row, "updated_at": now_text} for row in prepared],
        )
        conn.executemany(
            """
            INSERT INTO legal_weather_grid_map
            (legal_code,legal_full_name,legal_normalized_name,legal_compact_name,region_type,
             target_admin_code,target_full_name,nx,ny,match_method,confidence,verified,updated_at)
            VALUES (:legal_code,:legal_full_name,:legal_normalized_name,:legal_compact_name,:region_type,
                    :target_admin_code,:target_full_name,:nx,:ny,:match_method,:confidence,:verified,:updated_at)
            """,
            [{**row, "updated_at": now_text} for row in mappings],
        )
        conn.executemany(
            """
            INSERT INTO weather_region_aliases
            (alias_key,alias_name,target_admin_code,target_full_name,nx,ny,match_method,confidence,updated_at)
            VALUES (:alias_key,:alias_name,:target_admin_code,:target_full_name,:nx,:ny,:match_method,:confidence,:updated_at)
            """,
            [{**row, "updated_at": now_text} for row in alias_rows.values()],
        )
        conn.commit()

    return {
        "ok": True,
        "kma_locations": len(prepared),
        "legal_rows": len(legal_rows),
        "mapped_rows": len(mappings),
        "unmatched_rows": len(legal_rows) - len(mappings),
        "aliases": len(alias_rows),
        "unique_grids": len({(r['nx'], r['ny']) for r in prepared}),
        "methods": dict(sorted(method_counts.items())),
        "updated_at": now_text,
    }


def resolve_region_grid(region: str) -> dict | None:
    """법정동명·행정동명·검증된 별칭을 기상청 격자로 변환합니다."""
    ensure_region_grid_tables()
    normalized = normalize_region_name(region)
    compact = compact_region_name(region)
    if not normalized:
        return None
    with _connect() as conn:
        # 검증된 수동 별칭과 정확한 기상청 명칭을 일반 법정동 폴백보다 우선합니다.
        row = conn.execute(
            """
            SELECT alias_name AS requested_name, target_full_name, nx, ny,
                   target_admin_code, match_method, confidence
            FROM weather_region_aliases
            WHERE alias_key IN (?, ?)
            ORDER BY confidence DESC LIMIT 1
            """,
            (normalized, compact),
        ).fetchone()
        if not row:
            row = conn.execute(
                """
                SELECT legal_full_name AS requested_name, target_full_name, nx, ny,
                       target_admin_code, match_method, confidence
                FROM legal_weather_grid_map
                WHERE legal_normalized_name = ? OR legal_compact_name = ?
                ORDER BY confidence DESC LIMIT 1
                """,
                (normalized, compact),
            ).fetchone()
    return dict(row) if row else None


def mapping_status() -> dict:
    ensure_region_grid_tables()
    with _connect() as conn:
        counts = {
            "kma_locations": conn.execute("SELECT COUNT(*) FROM weather_grid_locations").fetchone()[0],
            "legal_mappings": conn.execute("SELECT COUNT(*) FROM legal_weather_grid_map").fetchone()[0],
            "aliases": conn.execute("SELECT COUNT(*) FROM weather_region_aliases").fetchone()[0],
            "unique_grids": conn.execute("SELECT COUNT(*) FROM (SELECT nx,ny FROM weather_grid_locations GROUP BY nx,ny)").fetchone()[0],
        }
        methods = {row[0]: row[1] for row in conn.execute(
            "SELECT match_method, COUNT(*) FROM legal_weather_grid_map GROUP BY match_method ORDER BY COUNT(*) DESC"
        )}
    return {**counts, "methods": methods}
