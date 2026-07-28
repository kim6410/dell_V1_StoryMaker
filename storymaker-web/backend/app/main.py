# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 진입점 모듈 (main.py)
"""
import os
import json
import base64
import hashlib
import hmac
import re
import urllib.request
import urllib.error
import threading
import time
from functools import wraps
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional, List
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import text
from app.db.database import engine, Base, SessionLocal, migrate_user_auth_columns, migrate_weather_tables, migrate_industry_prompt_templates, migrate_project_assets_table, migrate_region_options
from app.db.billing_migration import migrate_billing_credit_tables
from app.db.pattern_repository import migrate_pattern_tables
from app.db.performance_repository import migrate_performance_tables
from app.db.intelligence_repository import migrate_intelligence_tables
from app.db.mobile_one_shot_repository import migrate_mobile_one_shot_jobs_table
from app.db.content_asset_repository import migrate_content_archive_assets_table
from app.api.auth import get_current_user, get_optional_current_user
from app.db.models import User
from app.db.repositories import seed_admin_user
from app.services.common_archive_service import register_common_archive
from app.services.content_asset_service import backfill_recent_content_archive_assets
from app.services.weather_cache_service import cleanup_expired_weather_cache, ensure_weather_cache_db
from app.core.prompt_builder import REGION_WEATHER_QUERY_MAP, fetch_weather_and_temp

KST = ZoneInfo("Asia/Seoul")

from app.api.podcast import router as podcast_router
from app.api.slideshow import router as slideshow_router
try:
    from nemotron_lab.backend.router import router as nemotron_lab_router
except Exception as nemotron_lab_import_error:
    nemotron_lab_router = None
    print(f"[nemotron-lab] router disabled: {type(nemotron_lab_import_error).__name__}: {nemotron_lab_import_error}")
from app.api import (
    health_router,
    companies_router,
    personas_router,
    prompts_router,
    results_router,
    keywords_router,
    projects_router,
    scraper_router,
    auth_router,
    admin_router,
    admin_members_router,
    feature_requests_router,
    wordpress_router,
    content_ideas_router,
    pattern_knowledge_router,
    content_performance_router,
    ai_brain_router,
    assets_router,
    industry_presets_router,
    mobile_one_shot_router,
    content_board_router,
    local_exports_router
)
from app.api.content_board import start_content_board_retention_scheduler
from app.api.staged.router import router as staged_router
from app.api.staged_access import router as staged_access_router
from app.api.staged.storage import StagedStorage
from app.api.staged.service import StagedGenerationService
from app.integration.staged_access import read_runtime_stage_flags, staged_access_status
from app.services.pattern_knowledge_service import start_learning_scheduler
from app.services.performance_intelligence_service import start_performance_scheduler
from app.services.intelligence_service import start_brain_scheduler
from app.services.copy_studio_asset_service import group_copy_studio_assets, resolve_copy_studio_channel, resolve_copy_studio_tokens
from app.services.project_asset_service import backfill_project_output_assets
from app.services.content_integrity_service import restore_orphan_document_parents, backfill_missing_checksums, audit_missing_orphan_assets, normalize_completed_jobs
from app.services.content_storage_service import ensure_content_storage_schema

# 기존 users 테이블 보강 후 데이터베이스 테이블 자동 생성
migrate_user_auth_columns()
migrate_region_options()
migrate_weather_tables()
migrate_industry_prompt_templates()
migrate_project_assets_table()
migrate_pattern_tables()
migrate_performance_tables()
migrate_intelligence_tables()
migrate_mobile_one_shot_jobs_table()
migrate_content_archive_assets_table()
migrate_billing_credit_tables(engine)
ensure_content_storage_schema()
try:
    restore_orphan_document_parents()
    audit_missing_orphan_assets()
    normalize_completed_jobs()
    backfill_missing_checksums(limit=2000)
except Exception as exc:
    print(f"[content-integrity] startup maintenance skipped: {exc}")
try:
    backfill_recent_content_archive_assets(limit=200)
except Exception as exc:
    print(f"[content-assets] startup backfill skipped: {exc}")
Base.metadata.create_all(bind=engine)

# 기본 관리자(admin) 계정 자동 시딩
db = SessionLocal()
try:
    seed_admin_user(db)
finally:
    db.close()


app = FastAPI(
    title="StoryMaker Web API",
    version="1.0.0",
    description="FastAPI로 구축된 StoryMaker 비즈니스 코어 및 데이터 관리 API 서비스"
)


class WindowsV1ApiCompatMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if path == "/v1-api" or path.startswith("/v1-api/"):
                scope = dict(scope)
                scope["path"] = "/api" + path[len("/v1-api"):]
                scope["raw_path"] = scope["path"].encode("utf-8")
        await self.app(scope, receive, send)

app.add_middleware(WindowsV1ApiCompatMiddleware)

# Gate 5 staged service is isolated from the existing one-click service and DB.
# Runtime feature flags still fail closed, so registering the service alone does not expose it.
STAGED_DIR = Path(os.getenv(
    "STORYMAKER_STAGED_DIR",
    "/home/bourne/StoryMaker_1/output_results/staged_generation",
)).resolve()
app.state.staged_service = StagedGenerationService(StagedStorage(STAGED_DIR))

# CORS(Cross-Origin Resource Sharing) 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mystorymaker.net",
        "https://app.mystorymaker.net",
        "https://mystorymaker.duckdns.org",
        "https://app.mystorymaker.duckdns.org",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터들을 '/api' 접두사 하위에 일괄 등록
app.include_router(health_router, prefix="/api", tags=["Health Check"])
app.include_router(companies_router, prefix="/api", tags=["Companies"])
app.include_router(personas_router, prefix="/api", tags=["Personas"])
app.include_router(projects_router, prefix="/api", tags=["Projects"])
app.include_router(prompts_router, prefix="/api", tags=["Prompt Generation"])
app.include_router(results_router, prefix="/api", tags=["Result Parsing"])
app.include_router(keywords_router, prefix="/api", tags=["Keyword Extraction"])
app.include_router(scraper_router, prefix="/api", tags=["Scraper"])
app.include_router(auth_router, prefix="/api", tags=["Authentication"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])
app.include_router(admin_members_router, prefix="/api", tags=["Admin Members"])
app.include_router(feature_requests_router, prefix="/api", tags=["Feature Requests"])
app.include_router(wordpress_router, prefix="/api", tags=["WordPress"])
app.include_router(content_ideas_router, prefix="/api", tags=["Content Ideas"])
app.include_router(pattern_knowledge_router, prefix="/api", tags=["Pattern Knowledge"])
app.include_router(content_performance_router, prefix="/api", tags=["Content Performance"])
app.include_router(ai_brain_router, prefix="/api", tags=["AI Brain"])
app.include_router(assets_router, prefix="/api", tags=["Project Assets"])
app.include_router(industry_presets_router, prefix="/api", tags=["Industry Presets"])
app.include_router(mobile_one_shot_router, prefix="/api", tags=["Mobile One-Shot"])
app.include_router(staged_access_router, prefix="/api", tags=["Staged Access"])
app.include_router(staged_router, prefix="/api/staged", tags=["Staged Generation"])
app.include_router(content_board_router, prefix="/api", tags=["V2 Content Board"])
app.include_router(local_exports_router, prefix="/api", tags=["Local Exports"])
app.include_router(podcast_router, prefix="/api", tags=["Podcast"])
app.include_router(slideshow_router, prefix="/api", tags=["Slideshow"])
if nemotron_lab_router is not None:
    app.include_router(nemotron_lab_router, prefix="/api", tags=["Nemotron Lab"])


def _safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _build_weather_summary_text(region: str, avg_temp, min_temp, max_temp, dominant_weather: str) -> str:
    temp_part = "기온 데이터는 아직 충분하지 않습니다."
    if avg_temp is not None and min_temp is not None and max_temp is not None:
        temp_part = f"평균 {avg_temp:.1f}℃, 최저 {min_temp:.1f}℃, 최고 {max_temp:.1f}℃ 흐름입니다."
    weather_part = dominant_weather or "날씨 확인"
    return f"오늘 {region}은 {weather_part} 흐름이 가장 많이 관찰되었습니다. {temp_part} 콘텐츠에는 현재값보다 하루 동안의 날씨 흐름과 현장감을 자연스럽게 반영해 주세요."


def _refresh_weather_daily_summary(db, region: str, date_key: str, now_text: str) -> None:
    rows = db.execute(
        text("""
        SELECT weather, temperature
        FROM weather_snapshots
        WHERE region = :region AND substr(observed_at, 1, 10) = :date_key
        """),
        {"region": region, "date_key": date_key},
    ).fetchall()
    temps = [float(row[1]) for row in rows if row[1] is not None]
    weathers = [str(row[0]) for row in rows if row[0]]
    avg_temp = round(sum(temps) / len(temps), 1) if temps else None
    min_temp = round(min(temps), 1) if temps else None
    max_temp = round(max(temps), 1) if temps else None
    dominant_weather = Counter(weathers).most_common(1)[0][0] if weathers else None
    summary_text = _build_weather_summary_text(region, avg_temp, min_temp, max_temp, dominant_weather)
    existing = db.execute(
        text("SELECT id FROM weather_daily_summaries WHERE region = :region AND date = :date_key"),
        {"region": region, "date_key": date_key},
    ).fetchone()
    if existing:
        db.execute(
            text("""
            UPDATE weather_daily_summaries
            SET avg_temp = :avg_temp,
                min_temp = :min_temp,
                max_temp = :max_temp,
                dominant_weather = :dominant_weather,
                summary_text = :summary_text,
                created_at = :created_at
            WHERE region = :region AND date = :date_key
            """),
            {
                "avg_temp": avg_temp,
                "min_temp": min_temp,
                "max_temp": max_temp,
                "dominant_weather": dominant_weather,
                "summary_text": summary_text,
                "created_at": now_text,
                "region": region,
                "date_key": date_key,
            },
        )
    else:
        db.execute(
            text("""
            INSERT INTO weather_daily_summaries
            (region, date, avg_temp, min_temp, max_temp, dominant_weather, summary_text, created_at)
            VALUES (:region, :date_key, :avg_temp, :min_temp, :max_temp, :dominant_weather, :summary_text, :created_at)
            """),
            {
                "region": region,
                "date_key": date_key,
                "avg_temp": avg_temp,
                "min_temp": min_temp,
                "max_temp": max_temp,
                "dominant_weather": dominant_weather,
                "summary_text": summary_text,
                "created_at": now_text,
            },
        )


def collect_weather_snapshots_once() -> dict:
    now = datetime.now(KST)
    now_text = now.isoformat(timespec="seconds")
    date_key = now.strftime("%Y-%m-%d")
    regions = list(REGION_WEATHER_QUERY_MAP.keys())
    
    # 1. DB 세션 없이 먼저 모든 지역의 날씨 데이터를 네트워크로 조회합니다.
    weather_data = []
    for region in regions:
        try:
            weather, temperature = fetch_weather_and_temp(region)
            weather_data.append((region, weather, temperature))
        except Exception:
            weather_data.append((region, "맑음", "20"))
            
    # 2. 조회된 데이터를 바탕으로 짧고 빠른 단일 트랜잭션으로 DB에 기록합니다.
    saved = 0
    db = SessionLocal()
    try:
        for region, weather, temperature in weather_data:
            db.execute(
                text("""
                INSERT INTO weather_snapshots
                (region, weather, temperature, source, observed_at, created_at)
                VALUES (:region, :weather, :temperature, :source, :observed_at, :created_at)
                """),
                {
                    "region": region,
                    "weather": weather,
                    "temperature": _safe_float(temperature),
                    "source": "hourly_auto",
                    "observed_at": now_text,
                    "created_at": now_text,
                },
            )
            _refresh_weather_daily_summary(db, region, date_key, now_text)
            saved += 1
        db.commit()
        return {"ok": True, "saved": saved, "created_at": now_text}
    except Exception as exc:
        db.rollback()
        return {"ok": False, "error": str(exc), "saved": saved, "created_at": now_text}
    finally:
        db.close()


def _weather_collector_loop() -> None:
    while True:
        result = collect_weather_snapshots_once()
        try:
            app.state.latest_weather_collect_result = result
        except Exception:
            pass
        time.sleep(3600)


@app.on_event("startup")
def start_weather_collector() -> None:
    if getattr(app.state, "weather_collector_started", False):
        return
    app.state.weather_collector_started = True
    ensure_weather_cache_db()
    removed = cleanup_expired_weather_cache()
    app.state.latest_weather_collect_result = {
        "ok": True,
        "mode": "on_demand_latest_cache",
        "auto_collection": False,
        "expired_removed": removed,
    }
    start_learning_scheduler()
    start_performance_scheduler()
    start_brain_scheduler()
    start_content_board_retention_scheduler()


@app.get("/api/weather/collect-now")
def collect_weather_now():
    return {
        "ok": True,
        "mode": "on_demand_latest_cache",
        "auto_collection": False,
        "message": "전국 일괄 수집은 비활성화되어 있으며 사용자 요청 지역만 캐싱합니다.",
    }


@app.get("/api/weather/collect-status")
def read_weather_collect_status():
    return getattr(app.state, "latest_weather_collect_result", {"ok": True, "status": "not_run_yet"})


@app.get("/api/weather/snapshots")
def read_weather_snapshots(page: int = 1, page_size: int = 15, region: str = ""):
    safe_page = max(1, int(page or 1))
    safe_size = max(1, min(100, int(page_size or 15)))
    offset = (safe_page - 1) * safe_size
    db = SessionLocal()
    try:
        region = str(region or "").strip()
        region_aliases = {
            "서울특별시": "서울",
            "부산광역시": "부산",
            "대구광역시": "대구",
            "인천광역시": "인천",
            "광주광역시": "광주",
            "대전광역시": "대전",
            "울산광역시": "울산",
            "세종특별자치시": "세종",
            "경기도": "경기",
            "강원특별자치도": "강원",
            "강원도": "강원",
            "충청북도": "충청",
            "충청남도": "충청",
            "전북특별자치도": "전라",
            "전라북도": "전라",
            "전라남도": "전라",
            "경상북도": "경북",
            "경상남도": "경남",
            "제주특별자치도": "제주",
        }
        region = region_aliases.get(region, region)
        region_like = f"%{region}%"
        total = int(db.execute(
            text("SELECT COUNT(*) FROM weather_snapshots WHERE (:region = '' OR region LIKE :region_like)"),
            {"region": region, "region_like": region_like},
        ).scalar() or 0)
        rows = db.execute(
            text("""
                SELECT id, region, weather, temperature, observed_at
                FROM weather_snapshots
                WHERE (:region = '' OR region LIKE :region_like)
                ORDER BY id DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": safe_size, "offset": offset, "region": region, "region_like": region_like},
        ).mappings().all()
        return {
            "ok": True,
            "region": region,
            "page": safe_page,
            "page_size": safe_size,
            "total": total,
            "total_pages": max(1, (total + safe_size - 1) // safe_size),
            "items": [dict(row) for row in rows],
        }
    finally:
        db.close()


@app.get("/v1/weather")
@app.get("/v1/weather/")
def read_weather_admin_page():
    weather_path = os.path.join(static_dir, "v1", "weather.html")
    return FileResponse(
        weather_path,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/beta/profile")
def read_beta_v1_profile(current_user: Optional[User] = Depends(get_optional_current_user)):
    """Return the signed-in V1 user's default business profile for isolated Beta UI."""
    if current_user is None:
        return {"ok": True, "authenticated": False, "profile": None}

    db = SessionLocal()
    try:
        row = db.execute(
            text("""
                SELECT company_name, phone_number, region, industry_key, content
                FROM user_personas
                WHERE user_id = :user_id
                ORDER BY is_default DESC, updated_at DESC, id DESC
                LIMIT 1
            """),
            {"user_id": current_user.id},
        ).mappings().first()
        if not row:
            return {"ok": True, "authenticated": True, "profile": None}

        industry_labels = {
            "general": "일반 서비스업",
            "home_repair": "집수리·인테리어",
            "boiler_facility": "보일러·설비",
            "appliance_clean": "가전 청소",
            "general_cleaning": "종합 청소",
            "window_screen": "방충망",
            "key_doorlock": "열쇠·도어락",
            "lighting_electric": "조명·전기",
            "drain_unclog": "하수구·배관",
            "restaurant": "음식점",
            "logistics": "물류·3PL",
        }
        industry_key = str(row.get("industry_key") or "general").strip()
        return {
            "ok": True,
            "authenticated": True,
            "role": str(current_user.role or "user").strip().lower(),
            "profile": {
                "name": str(row.get("company_name") or "").strip(),
                "region": str(row.get("region") or "").strip(),
                "service": industry_labels.get(industry_key, industry_key if industry_key != "general" else "일반 서비스업"),
                "phone": str(row.get("phone_number") or "").strip(),
            },
        }
    finally:
        db.close()


@app.get("/v1/storymaker-gemini-worker-v1.user.js")
def read_storymaker_v1_gemini_worker_userscript():
    userscript_path = os.path.join(static_dir, "v1", "storymaker-gemini-worker-v1.user.js")
    return FileResponse(
        userscript_path,
        media_type="application/javascript; charset=utf-8",
        headers={
            "Content-Disposition": 'inline; filename="storymaker-gemini-worker-v1.user.js"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )




@app.get("/api/weather/snapshots")
def read_weather_snapshots(page: int = 1, page_size: int = 15, region: str = ""):
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 15)))
    offset = (page - 1) * page_size
    db = SessionLocal()
    try:
        region = str(region or "").strip()
        region_like = f"%{region}%"
        total = int(db.execute(
            text("SELECT COUNT(*) FROM weather_snapshots WHERE (:region = '' OR region LIKE :region_like)"),
            {"region": region, "region_like": region_like},
        ).scalar() or 0)
        rows = db.execute(
            text("""
                SELECT id, region, weather, temperature, observed_at
                FROM weather_snapshots
                WHERE (:region = '' OR region LIKE :region_like)
                ORDER BY observed_at DESC, id DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": page_size, "offset": offset, "region": region, "region_like": region_like},
        ).mappings().all()
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "ok": True,
            "region": region,
            "items": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    finally:
        db.close()


def _safe_asset_token(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or "")).strip("_")[:80]


def _public_output_url(path: Path, output_root: Path) -> str:
    rel = path.relative_to(output_root).as_posix()
    return f"/data/output_results/{rel}"


def _guess_asset_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    parent = path.parent.name.lower()
    if suffix in {".mp4", ".mov", ".webm", ".m4v"}:
        return "video"
    if "thumbnail" in name or "thumb" in name or "thumbnail" in parent or "thumbnails" in path.as_posix().lower():
        return "thumbnail"
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return "image"
    return "file"


def _read_copy_studio_asset_rows(project_id: int, project_key: Optional[str] = None, user_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Copy Studio용 활성 자산을 project_assets DB에서만 조회합니다."""
    db = SessionLocal()
    try:
        where = ["is_active = 1", "status = 'READY'"]
        params: dict[str, Any] = {}
        scope_conditions = []
        if project_id:
            scope_conditions.append("project_id = :project_id")
            params["project_id"] = project_id
        if project_key:
            scope_conditions.append("project_key = :project_key")
            params["project_key"] = project_key
        if scope_conditions:
            where.append("(" + " OR ".join(scope_conditions) + ")")
        if user_id is not None:
            where.append("user_id = :user_id")
            params["user_id"] = user_id
        rows = db.execute(text(f"""
            SELECT *
            FROM project_assets
            WHERE {' AND '.join(where)}
            ORDER BY display_order ASC, created_at DESC, id DESC
        """), params).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


def _backfill_copy_studio_assets(project_id: int, project_key: Optional[str] = None, project_title: Optional[str] = None) -> dict[str, Any]:
    db = SessionLocal()
    try:
        project = db.execute(text("SELECT id, user_id, title FROM projects WHERE id = :project_id"), {"project_id": project_id}).mappings().first()
        result = backfill_project_output_assets(
            db,
            project_id=project_id,
            user_id=(project or {}).get("user_id") or "default_user",
            project_key=project_key or "",
            project_title=project_title or (project or {}).get("title") or "",
        )
        if result.get("inserted"):
            db.commit()
        return result
    finally:
        db.close()


class CopyStudioResolveAssetsRequest(BaseModel):
    project_id: int
    project_key: Optional[str] = None
    channel: str = "naver_blog"
    content: str
    title: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


@app.get("/api/copy-studio/project-assets/{project_id}")
def read_copy_studio_project_assets(
    project_id: int,
    channel: str = "naver_blog",
    project_title: Optional[str] = None,
    project_key: Optional[str] = None,
):
    """멀티채널 Copy Studio 산출물을 project_assets DB 기준으로 조회합니다."""
    try:
        # ponytail: existing naver copy API is authless; keep user filtering optional until frontend auth contract is confirmed.
        _backfill_copy_studio_assets(project_id=project_id, project_key=project_key, project_title=project_title)
        rows = _read_copy_studio_asset_rows(project_id=project_id, project_key=project_key)
        grouped = group_copy_studio_assets(rows)
        payload = resolve_copy_studio_channel(channel, "", rows)
        return {
            "ok": True,
            "source": "project_assets_db",
            "channel": channel,
            "data": {
                "project_id": project_id,
                "project_title": project_title,
                "project_key": project_key,
                **grouped,
                "channel_payload": payload.get("channel_payload", {}),
            }
        }
    except Exception as exc:
        return {"ok": False, "source": "project_assets_db", "channel": channel, "message": str(exc), "data": {"images": [], "videos": [], "thumbnails": [], "all": [], "token_map": {}, "channel_payload": {}}}


@app.post("/api/copy-studio/resolve-assets")
def resolve_copy_studio_asset_tokens(req: CopyStudioResolveAssetsRequest):
    """본문의 asset token을 채널별 출력 형태로 치환합니다."""
    try:
        rows = _read_copy_studio_asset_rows(project_id=req.project_id, project_key=req.project_key)
        grouped = group_copy_studio_assets(rows)
        resolved = resolve_copy_studio_channel(req.channel, req.content, rows, req.title or "", req.meta or {})
        return {
            "ok": True,
            "source": "project_assets_db",
            "channel": req.channel,
            "data": {
                "project_id": req.project_id,
                "project_key": req.project_key,
                "assets": grouped,
                **resolved,
            }
        }
    except Exception as exc:
        return {"ok": False, "source": "project_assets_db", "channel": req.channel, "message": str(exc), "data": None}


@app.get("/api/naver-blog-copy/project-assets/{project_id}")
def read_naver_blog_project_assets(project_id: int, project_title: Optional[str] = None, project_key: Optional[str] = None):
    """Copy Studio 산출물을 project_assets DB 기준으로 조회합니다.

    기존 output_results 폴더 스캔 방식은 중복·누락 가능성이 있어 사용하지 않습니다.
    """
    try:
        _backfill_copy_studio_assets(project_id=project_id, project_key=project_key, project_title=project_title)
        rows = _read_copy_studio_asset_rows(project_id=project_id, project_key=project_key)
        grouped = group_copy_studio_assets(rows)
        return {
            "ok": True,
            "source": "project_assets_db",
            "data": {
                "project_id": project_id,
                "project_title": project_title,
                "project_key": project_key,
                **grouped,
            }
        }
    except Exception as exc:
        return {"ok": False, "source": "project_assets_db", "message": str(exc), "data": {"images": [], "videos": [], "thumbnails": [], "all": [], "token_map": {}}}


@app.post("/api/naver-blog-copy/resolve-assets")
def resolve_naver_blog_asset_tokens(req: CopyStudioResolveAssetsRequest):
    """본문의 [[IMAGE:ROLE]] / [IMAGE_ROLE] 토큰을 DB 자산으로 치환합니다."""
    try:
        rows = _read_copy_studio_asset_rows(project_id=req.project_id, project_key=req.project_key)
        grouped = group_copy_studio_assets(rows)
        resolved = resolve_copy_studio_tokens(req.content, rows)
        return {
            "ok": True,
            "source": "project_assets_db",
            "data": {
                "project_id": req.project_id,
                "project_key": req.project_key,
                "assets": grouped,
                **resolved,
            }
        }
    except Exception as exc:
        return {"ok": False, "source": "project_assets_db", "message": str(exc), "data": None}


def _format_prompt_for_worker(text_value: str) -> str:
    value = str(text_value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value:
        return ""

    section_titles = [
        "역할", "StoryMaker 생성 환경", "StoryMaker 생활 배경 엔진", "콘텐츠 감성",
        "오늘의 날짜와 생활 맥락", "현재 시간대와 생활 흐름", "오늘의 현장 날씨",
        "최근 일주일 날씨 흐름", "지역 정보", "업종별 작성 흐름", "SEO 강도",
        "브랜드 톤", "최우선 반영 규칙", "작업 목표", "반드시 생성할 결과물",
        "최상위 출력 규칙", "모바일 가독성 규칙", "공통 작성 규칙", "블로그 규칙",
        "플레이스 규칙", "구글 규칙", "인스타그램 규칙", "당근마켓 규칙",
        "카드뉴스 규칙", "팟캐스트 규칙", "업체 정보", "입력 자료", "최종 점검 규칙", "중요",
    ]
    sub_titles = [
        "사람다운 문체", "굵은 표시 규칙", "전화번호 규칙", "업체명", "업체 페르소나",
        "기초내용 입력", "참고자료", "핵심 키워드", "[AI Brain Recommendation Summary]", "[압축 참고자료]",
    ]

    value = re.sub(r"#+\s*$", "", value, flags=re.MULTILINE)
    value = value.replace("```content", "\n\n```content\n")
    value = re.sub(r"\s*```\s*$", "\n```", value)

    for title in section_titles:
        value = re.sub(r"\s*##\s*" + re.escape(title) + r"\s*", "\n\n## " + title + "\n\n", value)
    for title in sub_titles:
        value = re.sub(r"\s*#{2,3}\s*" + re.escape(title) + r"\s*", "\n\n### " + title + "\n\n", value)

    value = re.sub(r"\s*(\[BLOCK:[A-Z0-9_]+\])\s*", r"\n\n\1\n", value)
    value = re.sub(r"([가-힣A-Za-z0-9).])(-\s+)", r"\1\n\2", value)
    value = re.sub(r"(작성 원칙|작성 참고|주의|전체 원칙|예시)(-\s+)", r"\1\n\2", value)
    value = re.sub(r"(BLOG_POST, CARROT_POST|NAVER_PLACE_NEWS, GOOGLE_BUSINESS_POST|INSTAGRAM_POST|CAROUSEL_7|PODCAST_50, PODCAST_80)(-\s+)", r"\1\n\2", value)
    value = re.sub(r"(대표 지역|우선 활용 지역|생활권 예시|입력자료와 페르소나에서 감지된 지역 후보)([^\n])", r"\1\n\2", value)
    value = re.sub(r"(업종:|업종 분류:|작성 흐름:|핵심 포인트:|키워드 힌트:|문체 힌트:|피해야 할 표현:)", r"\n\1", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    lines = [line.rstrip() for line in value.split("\n")]
    return "\n".join(lines).strip() + "\n"


def _looks_like_storymaker_prompt(text_value: str) -> bool:
    value = str(text_value or "")
    prompt_markers = (
        "## 역할",
        "## StoryMaker 생성 환경",
        "## 반드시 생성할 결과물",
        "## 최상위 출력 규칙",
        "## 모바일 가독성 규칙",
        "콘텐츠 통합 패키지 생성 프롬프트",
    )
    prompt_score = sum(1 for marker in prompt_markers if marker in value)
    has_result_block = bool(re.search(r"\[BLOCK:(BLOG_TITLES|BLOG_POST|NAVER_PLACE_NEWS|GOOGLE_BUSINESS_POST|INSTAGRAM_POST|PODCAST_50|PODCAST_80)\]", value))
    return prompt_score >= 2 and not has_result_block


def _looks_like_storymaker_result(text_value: str) -> bool:
    value = str(text_value or "").strip()
    if not value or _looks_like_storymaker_prompt(value):
        return False

    result_blocks = (
        "BLOG_TITLES",
        "BLOG_POST",
        "NAVER_PLACE_NEWS",
        "GOOGLE_BUSINESS_POST",
        "INSTAGRAM_POST",
        "CARROT_POST",
        "PODCAST_50",
        "PODCAST_80",
    )
    found = sum(1 for name in result_blocks if f"[BLOCK:{name}]" in value)

    # Gemini 코드 스니펫 추출이 앞부분만 잡히더라도 BLOG_POST를 포함한
    # 정상 결과 BLOCK이 2개 이상이면 실제 콘텐츠 결과로 인정한다.
    has_blog_post = "[BLOCK:BLOG_POST]" in value
    return (found >= 2 and has_blog_post) or (found >= 1 and len(value) >= 1200)


class TestPromptSnapshotRequest(BaseModel):
    generated_prompt: str
    project_title: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class TestResultPackageRequest(BaseModel):
    result_text: Optional[str] = None
    result_raw: Optional[str] = None
    result_clean: Optional[str] = None
    result_json: Optional[Dict[str, Any]] = None
    job_id: Optional[str] = None
    project_title: Optional[str] = None
    source: Optional[str] = "firefox-worker"


class TestThumbnailResultRequest(BaseModel):
    job_id: str
    project_title: Optional[str] = None
    image_url: Optional[str] = None
    image_urls: Optional[list[str]] = None
    image_data_urls: Optional[list[str]] = None
    final_image_data_url: Optional[str] = None
    selected_image_index: Optional[int] = None
    selected_image_count: Optional[int] = None
    source_job_id: Optional[str] = None
    result_text: Optional[str] = None
    source: Optional[str] = "gemini-worker"


class TestTriggerStartRequest(BaseModel):
    job_id: Optional[str] = None
    project_title: Optional[str] = None
    action: Optional[str] = "GENERATE_CHATGPT"
    prompt_path: Optional[str] = None


class TestTriggerAckRequest(BaseModel):
    job_id: str
    status: Optional[str] = "claimed"
    worker_id: Optional[str] = "firefox-worker"
    error: Optional[str] = None


_TEST_TRIGGER_ACK_LOCK = threading.Lock()


def _serialize_test_trigger_ack(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with _TEST_TRIGGER_ACK_LOCK:
            return func(*args, **kwargs)
    return wrapper


@app.post("/api/test/prompt-snapshot")
def save_test_prompt_snapshot(req: TestPromptSnapshotRequest):
    """
    TEST ONLY: /storymaker-test?test_mode=1 화면에서 통합 프롬프트를 임시 파일로 저장한다.
    운영 /storymaker 화면에서는 프론트가 이 API를 호출하지 않는다.
    """

    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    snapshot_root = output_root / "test_prompt_snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    safe_title = "test_prompt"
    if req.project_title:
        safe_title = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in req.project_title.strip())[:60] or "test_prompt"
    job_dir = snapshot_root / f"{stamp}_{safe_title}"
    job_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = job_dir / "prompt_for_chatgpt.md"
    meta_path = job_dir / "snapshot.json"
    latest_path = snapshot_root / "latest.json"
    latest_prompt_path = snapshot_root / "latest_prompt.md"

    timing = {"pc_handoff_start_at": datetime.now().isoformat(timespec="milliseconds")}
    prompt_text = _format_prompt_for_worker(req.generated_prompt)
    timing["pc_prompt_formatted_at"] = datetime.now().isoformat(timespec="milliseconds")
    prompt_path.write_text(prompt_text, encoding="utf-8")
    latest_prompt_path.write_text(prompt_text, encoding="utf-8")
    timing["pc_latest_prompt_written_at"] = datetime.now().isoformat(timespec="milliseconds")
    meta = {
        "ok": True,
        "created_at": now.isoformat(timespec="seconds"),
        "username": "test-mode",
        "project_title": req.project_title,
        "prompt_for_chatgpt": str(prompt_path),
        "latest_prompt_path": str(latest_prompt_path),
        "snapshot_json": str(meta_path),
        "payload": req.payload or {},
        "timing": timing,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    timing["pc_latest_json_written_at"] = datetime.now().isoformat(timespec="milliseconds")
    return {"ok": True, "data": meta}


@app.get("/api/test/job-prompt/{job_id}")
def read_test_job_prompt(job_id: str):
    """현재 작업 ID에 정확히 대응하는 프롬프트만 반환한다."""
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    prompt_path: Optional[Path] = None

    if re.fullmatch(r"mob-[0-9]{14}-[a-f0-9]{8}", job_id):
        matches = list((output_root / "mobile_one_shot").glob(f"*/{job_id}/prompt_for_chatgpt.md"))
        if len(matches) == 1:
            prompt_path = matches[0]
    elif re.fullmatch(r"thumbnail_[0-9]{8}_[0-9]{6}_mobile", job_id):
        candidate = output_root / "test_thumbnail_jobs" / job_id / "thumbnail_prompt.md"
        if candidate.exists():
            prompt_path = candidate

    if not prompt_path or not prompt_path.exists():
        return {"ok": False, "message": "job prompt not found", "job_id": job_id, "data": None}

    prompt_text = prompt_path.read_text(encoding="utf-8")
    return {
        "ok": True,
        "job_id": job_id,
        "prompt": prompt_text,
        "data": {"job_id": job_id, "prompt": prompt_text, "prompt_path": str(prompt_path)},
    }


@app.get("/api/test/latest-prompt")
def read_latest_test_prompt():
    """
    TEST ONLY: 가장 최근 테스트 통합 프롬프트 파일 내용을 반환한다.
    Firefox/ChatGPT 자동화는 이 API만 호출하면 최신 프롬프트를 받을 수 있다.
    """
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    snapshot_root = output_root / "test_prompt_snapshots"

    # 기존 Worker가 latest API를 호출하더라도 현재 모바일 trigger의 job_id를 우선한다.
    trigger_path = output_root / "test_triggers" / "trigger_status.json"
    if trigger_path.exists():
        try:
            trigger = json.loads(trigger_path.read_text(encoding="utf-8"))
            trigger_job_id = str(trigger.get("job_id") or "").strip()
            trigger_status = str(trigger.get("status") or "").lower()
            if trigger_job_id and (trigger_job_id.startswith("mob-") or trigger_job_id.endswith("_mobile")) and trigger_status in {"pending", "claimed", "prompt_sent", "sent", "uploaded"}:
                exact = read_test_job_prompt(trigger_job_id)
                if exact.get("ok"):
                    return exact
        except Exception:
            pass

    latest_path = snapshot_root / "latest.json"
    if not latest_path.exists():
        return {"ok": False, "message": "latest.json not found", "data": None}

    try:
        meta = json.loads(latest_path.read_text(encoding="utf-8"))
        prompt_path = Path(meta.get("prompt_for_chatgpt") or "")
        if not prompt_path.exists():
            # 컨테이너 경로가 아닌 호스트 경로가 기록된 경우를 대비한 보정
            candidate = snapshot_root / Path(str(prompt_path)).name
            if candidate.exists():
                prompt_path = candidate
        if not prompt_path.exists():
            return {"ok": False, "message": f"prompt file not found: {prompt_path}", "data": meta}

        prompt_text = prompt_path.read_text(encoding="utf-8")
        project_name = meta.get("project_title") or "새 프로젝트"
        data = {
            "created_at": meta.get("created_at"),
            "project_title": project_name,
            "project_name": project_name,
            "prompt_path": str(prompt_path),
            "snapshot_json": meta.get("snapshot_json"),
            "prompt": prompt_text,
            "prompt_length": len(prompt_text),
        }
        return {
            "ok": True,
            "project_name": project_name,
            "prompt": prompt_text,
            "prompt_length": len(prompt_text),
            "data": data,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "message": str(exc), "data": None}


@app.post("/api/test/trigger-start")
def start_test_trigger(
    req: TestTriggerStartRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    TEST ONLY: StoryMaker 테스트 화면이 Firefox 워커에게 새 작업 시작 신호를 남긴다.
    워커는 /api/test/trigger-status를 폴링해서 새 job_id를 감지한다.
    """
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    trigger_root = output_root / "test_triggers"
    trigger_root.mkdir(parents=True, exist_ok=True)
    snapshot_root = output_root / "test_prompt_snapshots"
    latest_prompt_path = snapshot_root / "latest_prompt.md"

    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    raw_job_id = req.job_id or f"storymaker_test_{stamp}"
    safe_job_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(raw_job_id))[:80] or f"storymaker_test_{stamp}"
    prompt_path = req.prompt_path or str(latest_prompt_path)

    trigger = {
        "ok": True,
        "status": "pending",
        "action": req.action or "GENERATE_CHATGPT",
        "job_id": safe_job_id,
        "project_title": req.project_title or "새 프로젝트",
        "prompt_path": prompt_path,
        "created_at": now.isoformat(timespec="seconds"),
        "claimed_at": None,
        "worker_id": None,
        "user_id": current_user.id if current_user else None,
        "username": current_user.username if current_user else None,
    }
    trigger_file = trigger_root / "trigger_status.json"
    trigger_file.write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "data": trigger}


@app.get("/api/test/trigger-status")
def read_test_trigger_status():
    """
    TEST ONLY: Firefox 워커가 현재 대기 중인 작업 신호를 조회한다.
    파일이 없으면 idle을 반환한다.
    """
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    trigger_file = output_root / "test_triggers" / "trigger_status.json"
    if not trigger_file.exists():
        return {"ok": True, "status": "idle", "data": None}
    try:
        trigger = json.loads(trigger_file.read_text(encoding="utf-8"))
        trigger_status = str(trigger.get("status") or "pending").lower()
        created_at = str(trigger.get("created_at") or trigger.get("claimed_at") or "").strip()
        if trigger_status in {"pending", "claimed", "uploaded", "prompt_sent", "sent"} and created_at:
            try:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                now_dt = datetime.now(created_dt.tzinfo) if created_dt.tzinfo else datetime.now()
                if (now_dt - created_dt).total_seconds() > 1800:
                    trigger["status"] = "expired"
                    trigger["expired_at"] = now_dt.isoformat(timespec="seconds")
                    trigger["last_error"] = "작업 대기 시간이 30분을 초과하여 자동 만료되었습니다."
                    trigger_file.write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
                    trigger_status = "expired"
            except Exception:
                pass
        return {"ok": True, "status": trigger_status, "data": trigger}
    except Exception as exc:
        return {"ok": False, "status": "error", "error": str(exc), "message": str(exc), "data": None}


@app.post("/api/test/trigger-ack")
@_serialize_test_trigger_ack
def ack_test_trigger(req: TestTriggerAckRequest):
    """
    TEST ONLY: Firefox 워커가 작업을 집었다고 표시한다.
    중복 실행 방지용이며, 완료 결과는 /api/test/result-package로 저장한다.
    """
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    trigger_file = output_root / "test_triggers" / "trigger_status.json"
    if not trigger_file.exists():
        return {"ok": False, "message": "trigger_status.json not found", "data": None}
    try:
        if req.job_id.startswith("storymaker_e2e_") and "tampermonkey" in (req.worker_id or "").lower():
            return {"ok": False, "message": "E2E jobs cannot be claimed by real browser worker."}

        trigger = json.loads(trigger_file.read_text(encoding="utf-8"))
        if trigger.get("job_id") != req.job_id:
            return {"ok": False, "message": "job_id mismatch", "data": trigger}

        current_status = trigger.get("status", "pending")
        next_status = req.status or "claimed"
        now_text = datetime.now().isoformat(timespec="seconds")

        if next_status == "claimed" and current_status != "pending":
            return {"ok": False, "message": f"job already {current_status}", "data": trigger}
        if next_status in ("uploaded", "prompt_sent", "sent") and current_status not in ("pending", "claimed", "uploaded", "prompt_sent", "sent"):
            return {"ok": False, "message": f"job already {current_status}", "data": trigger}
        if next_status == "retry_pending":
            if trigger.get("action") != "GENERATE_GEMINI_THUMBNAIL":
                return {"ok": False, "message": "retry_pending is thumbnail-only", "data": trigger}
            attempts = int(trigger.get("attempt_count") or 0)
            if attempts >= 3:
                trigger["status"] = "failed"
                trigger["failed_at"] = now_text
                trigger["last_error"] = (req.error or "thumbnail prompt send failed")[:500]
                trigger_file.write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"ok": False, "message": "thumbnail retry limit reached", "data": trigger}
            trigger["status"] = "pending"
            trigger["worker_id"] = None
            trigger["claimed_at"] = None
            trigger["uploaded_at"] = None
            trigger["prompt_sent_at"] = None
            trigger["last_error"] = (req.error or "thumbnail prompt send failed")[:500]
            trigger["retry_queued_at"] = now_text
            trigger_file.write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "data": trigger}

        trigger["status"] = next_status
        trigger["worker_id"] = req.worker_id or "firefox-worker"
        if next_status == "claimed":
            trigger["attempt_count"] = int(trigger.get("attempt_count") or 0) + 1
            trigger["claimed_at"] = now_text
        elif next_status == "uploaded":
            trigger["uploaded_at"] = now_text
        elif next_status == "prompt_sent":
            trigger["prompt_sent_at"] = now_text
            trigger["sent_at"] = now_text
        elif next_status == "sent":
            trigger["sent_at"] = now_text
        trigger_file.write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")

        return {"ok": True, "data": trigger}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "message": str(exc), "data": None}
@app.post("/api/test/worker-log")
def post_worker_log(req: dict):
    msg = req.get("message", "")
    print(f"[Worker Log] {msg}")
    try:
        output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
        result_root = output_root / "test_result_packages"
        result_root.mkdir(parents=True, exist_ok=True)
        log_file = result_root / "worker_debug.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} - {msg}\n")
    except Exception:
        pass
    return {"ok": True}


@app.post("/api/test/thumbnail-job-auto")
def create_thumbnail_job_auto():
    root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    
    latest_result_package_path = None
    test_result_dir = root / "test_result_packages"
    if test_result_dir.exists():
        try:
            packages = []
            for p in test_result_dir.iterdir():
                if p.is_dir() and not p.name.startswith("thumbnail_"):
                    pkg_json = p / "result_package.json"
                    if pkg_json.exists():
                        packages.append(pkg_json)
            if packages:
                packages.sort(key=lambda x: x.parent.name, reverse=True)
                latest_result_package_path = packages[0]
        except Exception as e:
            print(f"Error scanning result packages: {e}")

    if not latest_result_package_path or not latest_result_package_path.exists():
        return {"ok": False, "message": "No main result package found"}
        
    try:
        package_data = json.loads(latest_result_package_path.read_text(encoding="utf-8"))
        result_text = package_data.get("result_text") or ""
        project_title = package_data.get("project_title") or "자동 썸네일"
        
        instagram_post = ""
        business_name = ""
        phone = ""
        keywords = ""
        
        import re
        match = re.search(r'\[BLOCK:INSTAGRAM_POST\]\s*\n(.*?)(?=\n\[BLOCK:|\Z)', result_text, re.DOTALL)
        if match:
            instagram_post = match.group(1).strip()
        
        phone_match = re.search(r'\b\d{2,4}-\d{3,4}-\d{4}\b', result_text)
        if phone_match:
            phone = phone_match.group(0)
        
        biz_match = re.search(r'\b\d{2,4}-\d{3,4}-\d{4}\s*\(\s*([^)]+)\s*\)', result_text)
        if biz_match:
            business_name = biz_match.group(1).strip()
        if not business_name:
            hashtag_match = re.search(r'\[BLOCK:INSTAGRAM_HASHTAGS\]\s*\n#([^\s#]+)', result_text)
            if hashtag_match:
                business_name = hashtag_match.group(1).strip()
        
        hashtags_match = re.search(r'\[BLOCK:INSTAGRAM_HASHTAGS\]\s*\n(.*?)(?=\n\[BLOCK:|\Z)', result_text, re.DOTALL)
        if hashtags_match:
            tags = re.findall(r'#([^\s#]+)', hashtags_match.group(1))
            filtered_tags = [t for t in tags if t != business_name]
            keywords = ", ".join(filtered_tags[:4])
            
        # Get the latest images from the latest thumbnail job
        image_urls = []
        latest_thumbnail_json = test_result_dir / "latest_thumbnail.json"
        if latest_thumbnail_json.exists():
            try:
                thumb_data = json.loads(latest_thumbnail_json.read_text(encoding="utf-8"))
                image_urls = thumb_data.get("image_urls") or []
            except Exception:
                pass
                
        if not image_urls:
            thumb_jobs_dir = root / "test_thumbnail_jobs"
            if thumb_jobs_dir.exists():
                jobs = [d for d in thumb_jobs_dir.iterdir() if d.is_dir()]
                if jobs:
                    jobs.sort(key=lambda x: x.name, reverse=True)
                    input_images_dir = jobs[0] / "input_images"
                    if input_images_dir.exists():
                        image_urls = [f"/data/output_results/test_thumbnail_jobs/{jobs[0].name}/input_images/{f.name}" for f in input_images_dir.iterdir() if f.is_file()]
                        
        image_lines = "\n".join(["- " + url for url in image_urls])
        
        now = datetime.now()
        job_id = "thumbnail_" + now.strftime("%Y%m%d_%H%M%S") + "_auto"
        job_dir = root / "test_thumbnail_jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        prompt = f"""[썸네일 제작 요청]

첨부된 이미지들을 참고해서 인스타그램용 9:16 세로형 썸네일 이미지를 만들어줘.

[업체 정보]
상호: {business_name}
전화번호: {phone}
키워드: {keywords}

[인스타그램 게시글 참고 문안]
{instagram_post}

[디자인 지시]
- 위 인스타그램 문안의 핵심 메시지를 반영해줘.
- 상호, 키워드, 전화번호가 모바일에서 잘 보이게 구성해줘.
- 현장 사진의 실제 분위기를 살려줘.
- 과장된 광고 느낌보다 지역 소상공인 현장감이 느껴지게 만들어줘.
- 글자는 너무 많이 넣지 말고 핵심 문구 중심으로 배치해줘.

참고 이미지:
{image_lines}
"""
        prompt_path = job_dir / "thumbnail_prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        
        trigger_dir = root / "test_triggers"
        trigger_dir.mkdir(parents=True, exist_ok=True)
        trigger = {
            "ok": True,
            "status": "pending",
            "action": "GENERATE_GEMINI_THUMBNAIL",
            "job_id": job_id,
            "project_title": project_title,
            "prompt_path": str(prompt_path),
            "created_at": now.isoformat(timespec="seconds"),
            "claimed_at": None,
            "worker_id": None,
            "image_urls": image_urls,
        }
        (trigger_dir / "trigger_status.json").write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
        
        latest = {
            "ok": True,
            "status": "pending",
            "job_id": job_id,
            "project_title": project_title,
            "image_count": len(image_urls),
            "image_urls": image_urls,
            "created_at": trigger["created_at"],
        }
        (test_result_dir / "latest_thumbnail.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return {"ok": True, "job_id": job_id}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}





def resolve_final_thumbnail_data_url(req: TestThumbnailResultRequest) -> str:
    candidates = []
    if req.final_image_data_url:
        candidates.append(req.final_image_data_url)
    candidates.extend(req.image_data_urls or [])
    candidates = [str(value or "").strip() for value in candidates if str(value or "").strip()]
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise HTTPException(status_code=400, detail="exactly one final thumbnail data url is required")
    return unique[0]


def write_thumbnail_error_state(job_id: str, message: str) -> None:
    safe_job_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(job_id))[:80] or "unknown"
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    job_dir = output_root / "test_result_packages" / safe_job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": False,
        "status": "failed",
        "job_id": safe_job_id,
        "error": str(message or "thumbnail save failed")[:500],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (job_dir / "thumbnail_error.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@app.post("/api/test/thumbnail-result")
def save_test_thumbnail_result(req: TestThumbnailResultRequest):
    """
    TEST ONLY: Gemini Worker가 선택한 최종 릴스/숏츠 썸네일 1장만 저장한다.
    """
    try:
        return _save_test_thumbnail_result(req)
    except HTTPException as exc:
        write_thumbnail_error_state(req.job_id, str(exc.detail))
        raise
    except Exception as exc:
        write_thumbnail_error_state(req.job_id, "thumbnail save failed")
        raise HTTPException(status_code=500, detail="thumbnail save failed") from exc


def _save_test_thumbnail_result(req: TestThumbnailResultRequest):
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    result_root = output_root / "test_result_packages"
    result_root.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    safe_job_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(req.job_id))[:80] or now.strftime("%Y%m%d_%H%M%S")
    job_dir = result_root / safe_job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    data_url = resolve_final_thumbnail_data_url(req)
    match = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", data_url)
    if not match:
        raise HTTPException(status_code=400, detail="invalid thumbnail data url")

    mime = match.group(1).lower()
    ext_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/webp": "webp",
    }
    if mime not in ext_map:
        raise HTTPException(status_code=400, detail=f"unsupported thumbnail mime: {mime}")

    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid thumbnail base64") from exc
    if len(raw) < 1024:
        raise HTTPException(status_code=400, detail="thumbnail image is too small")

    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(raw)) as img:
            img.verify()
        with Image.open(BytesIO(raw)) as img:
            width, height = img.size
            fmt = (img.format or ext_map[mime]).lower()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="thumbnail image validation failed") from exc

    ratio = height / width if width else 0
    if width < 300 or height < 500 or ratio < 1.5:
        raise HTTPException(status_code=400, detail="thumbnail image dimensions are invalid")

    ext = ext_map[mime]
    img_path = job_dir / f"gemini_final_thumbnail.{ext}"
    img_path.write_bytes(raw)

    safe_project = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(req.project_title or "default_project"))[:80] or "default_project"
    safe_user = "default_user"
    user_thumb_dir = output_root / "users" / safe_user / "projects" / safe_project / "thumbnails"
    user_thumb_dir.mkdir(parents=True, exist_ok=True)
    dst_path = user_thumb_dir / f"gemini_final_thumbnail.{ext}"
    dst_path.write_bytes(raw)

    # V1 모바일 딸깍 작업과 썸네일 전용 작업을 source_job_id로 직접 연결한다.
    # V2처럼 최종 결과를 해당 작업의 media 폴더에 물질화해야 미리보기와 보관함이 같은 파일을 본다.
    source_mobile_job_id = str(req.source_job_id or "").strip()
    if re.fullmatch(r"mob-[0-9]{14}-[a-f0-9]{8}", source_mobile_job_id, re.IGNORECASE):
        mobile_matches = list((output_root / "mobile_one_shot").glob(f"*/{source_mobile_job_id}/result.json"))
        if len(mobile_matches) == 1:
            mobile_result_path = mobile_matches[0]
            mobile_job_dir = mobile_result_path.parent
            mobile_media_dir = mobile_job_dir / "media"
            mobile_media_dir.mkdir(parents=True, exist_ok=True)
            mobile_thumbnail_path = mobile_media_dir / "thumbnail.jpg"
            mobile_thumbnail_path.write_bytes(raw)
            try:
                mobile_data = json.loads(mobile_result_path.read_text(encoding="utf-8"))
            except Exception:
                mobile_data = {"job_id": source_mobile_job_id}
            mobile_media = mobile_data.setdefault("media", {})
            mobile_thumbnail_url = f"/v1-api/mobile/one-shot/jobs/{source_mobile_job_id}/files/thumbnail"
            mobile_media.update({
                "thumbnail_status": "thumbnail_done",
                "thumbnail_job_id": safe_job_id,
                "thumbnail_path": str(mobile_thumbnail_path),
                "thumbnail_url": mobile_thumbnail_url,
                "thumbnail_preview_url": mobile_thumbnail_url,
                "thumbnail_download_url": mobile_thumbnail_url,
                "thumbnail_saved": True,
                "thumbnail_size": len(raw),
                "thumbnail_saved_at": now.isoformat(timespec="seconds"),
                "message": "Gemini 최종 썸네일을 작업 폴더에 저장했습니다.",
            })
            mobile_result_path.write_text(json.dumps(mobile_data, ensure_ascii=False, indent=2), encoding="utf-8")

    final_url = f"/data/output_results/users/{safe_user}/projects/{safe_project}/thumbnails/{dst_path.name}"

    payload = {
        "ok": True,
        "status": "thumbnail_ready",
        "created_at": now.isoformat(timespec="seconds"),
        "job_id": safe_job_id,
        "source_job_id": str(req.source_job_id or "").strip(),
        "project_title": req.project_title,
        "user_id": safe_user,
        "project_id": safe_project,
        "source": req.source or "gemini-worker",
        "image_url": final_url,
        "image_urls": [final_url],
        "final_image_url": final_url,
        "download_url": final_url,
        "preview_url": final_url,
        "source_image_urls": list(dict.fromkeys([u for u in ([req.image_url] + (req.image_urls or [])) if u])),
        "saved_files": [str(img_path)],
        "saved_public_urls": [final_url],
        "user_project_files": [str(dst_path)],
        "user_project_urls": [final_url],
        "result_text": req.result_text or "",
        "image_count": 1,
        "selected_image_index": req.selected_image_index if req.selected_image_index is not None else 0,
        "selected_image_count": req.selected_image_count if req.selected_image_count is not None else 1,
        "width": width,
        "height": height,
        "ratio": ratio,
        "format": fmt,
        "download_note": "Gemini 최종 생성 썸네일 1장만 저장합니다.",
    }

    thumb_json = job_dir / "reels_thumbnail_url.json"
    latest_json = result_root / "latest_thumbnail.json"
    thumb_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 릴스/숏츠 썸네일 완료 후 기존 공용 보관함 항목에 URL만 병합한다.
    try:
        content_id_file = job_dir / "content_id.txt"
        archive_group_key = content_id_file.read_text(encoding="utf-8").strip() if content_id_file.exists() else ""
        user_id_match = re.search(r"_(\d+)$", safe_job_id)
        if archive_group_key and user_id_match:
            from app.services.common_archive_service import register_common_archive

            register_common_archive(
                user_id=int(user_id_match.group(1)),
                source="shortform-thumbnail",
                source_job_id=safe_job_id,
                archive_group_key=archive_group_key,
                title=req.project_title or archive_group_key,
                status="thumbnail_completed",
                media={
                    "thumbnail_url": final_url,
                    "image_url": final_url,
                    "final_image_url": final_url,
                    "thumbnail_status": "thumbnail_done",
                },
                extra={"thumbnail_job_id": safe_job_id},
            )
    except Exception as archive_exc:
        print(f"[thumbnail archive sync warning] {archive_exc}")

    return {
        "ok": True,
        "status": payload["status"],
        "job_id": safe_job_id,
        "image_url": payload["image_url"],
        "image_urls": payload["image_urls"],
        "final_image_url": payload["final_image_url"],
        "download_url": payload["download_url"],
        "preview_url": payload["preview_url"],
        "saved_public_urls": payload["saved_public_urls"],
        "data_path": str(thumb_json),
        "public_json_url": f"/data/output_results/test_result_packages/{safe_job_id}/reels_thumbnail_url.json",
        "data": payload,
    }


@app.get("/api/test/thumbnail-result/latest")
def read_latest_test_thumbnail_result():
    """
    TEST ONLY: 가장 최근 Gemini 썸네일 결과 URL을 조회한다.
    """
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    result_root = output_root / "test_result_packages"
    latest_json = result_root / "latest_thumbnail.json"
    if not latest_json.exists():
        error_files = sorted(result_root.glob("*/thumbnail_error.json"), key=lambda path: path.stat().st_mtime, reverse=True) if result_root.exists() else []
        if error_files:
            error_payload = json.loads(error_files[0].read_text(encoding="utf-8"))
            return {"ok": False, "status": "failed", "job_id": error_payload.get("job_id"), "error": error_payload.get("error"), "data": None}
        return {"ok": True, "status": "pending", "data": None}
    try:
        payload = json.loads(latest_json.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "status": payload.get("status", "thumbnail_ready"),
            "job_id": payload.get("job_id"),
            "image_url": payload.get("image_url"),
            "image_urls": payload.get("image_urls", []),
            "final_image_url": payload.get("final_image_url") or ((payload.get("saved_public_urls") or [None])[-1]),
            "data": payload,
        }
    except Exception as exc:
        return {"ok": False, "status": "error", "error": str(exc), "message": str(exc), "data": None}


@app.get("/api/test/thumbnail-result/{job_id}")
def read_test_thumbnail_result(job_id: str):
    """TEST ONLY: 지정한 Gemini 썸네일 작업의 결과를 반환한다."""
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    safe_job_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(job_id))[:80]
    if not safe_job_id or safe_job_id != job_id:
        raise HTTPException(status_code=400, detail="invalid thumbnail job_id")
    result_json = output_root / "test_result_packages" / safe_job_id / "reels_thumbnail_url.json"
    error_json = output_root / "test_result_packages" / safe_job_id / "thumbnail_error.json"
    if not result_json.exists():
        if error_json.exists():
            error_payload = json.loads(error_json.read_text(encoding="utf-8"))
            return {"ok": False, "status": "failed", "job_id": safe_job_id, "error": error_payload.get("error"), "data": None}
        return {"ok": True, "status": "pending", "job_id": safe_job_id, "data": None}
    try:
        payload = json.loads(result_json.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "status": payload.get("status", "thumbnail_ready"),
            "job_id": payload.get("job_id") or safe_job_id,
            "image_url": payload.get("image_url"),
            "image_urls": payload.get("image_urls", []),
            "final_image_url": payload.get("final_image_url") or ((payload.get("saved_public_urls") or [None])[-1]),
            "download_url": payload.get("download_url"),
            "preview_url": payload.get("preview_url"),
            "data": payload,
        }
    except Exception as exc:
        return {"ok": False, "status": "error", "job_id": safe_job_id, "error": str(exc), "message": str(exc), "data": None}


@app.post("/api/test/result-package")
def save_test_result_package(
    req: TestResultPackageRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    TEST ONLY: Firefox 워커가 ChatGPT 결과를 백엔드 파일로 저장한다.
    StoryMaker 테스트 화면은 latest 조회 API를 3초 폴링해서 결과를 바인딩할 수 있다.
    """
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    result_root = output_root / "test_result_packages"
    result_root.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    job_id = req.job_id or stamp
    safe_job_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(job_id))[:80] or stamp

    if safe_job_id.startswith("storymaker_e2e_") and "tampermonkey" in (req.source or "").lower():
        return {"ok": False, "message": "E2E jobs cannot be saved by real browser worker."}

    raw_text = req.result_raw if req.result_raw is not None else (req.result_text or "")
    clean_text = req.result_clean if req.result_clean is not None else (req.result_text or "")

    # 에러 상태 판정
    is_error = "error" in (req.source or "").lower() or clean_text.startswith("[ERROR]")

    # 썸네일 작업은 이미지 결과를 전용 /api/test/thumbnail-result에서 저장한다.
    # 일반 StoryMaker BLOCK 형식 검증을 적용하면 이미지 생성이 끝난 뒤 전용 저장 전에 차단된다.
    if not is_error and not _looks_like_storymaker_result(clean_text):
        is_error = True
        if _looks_like_storymaker_prompt(clean_text):
            clean_text = "[ERROR] Gemini Worker가 생성 결과가 아니라 프롬프트 원문을 반환했습니다. SNS 데이터 입력을 차단했습니다."
        else:
            clean_text = "[ERROR] Gemini Worker 결과가 StoryMaker 콘텐츠 BLOCK 형식이 아닙니다. SNS 데이터 입력을 차단했습니다."

    if is_error:
        error_data = {
            "ok": False,
            "status": "failed",
            "job_id": safe_job_id,
            "project_title": req.project_title,
            "error": clean_text,
            "created_at": now.isoformat(timespec="seconds")
        }
        error_path = result_root / "latest_error.json"
        error_path.write_text(json.dumps(error_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # trigger_status.json 파일 상태를 failed로 업데이트
        trigger_file = output_root / "test_triggers" / "trigger_status.json"
        if trigger_file.exists():
            try:
                trigger = json.loads(trigger_file.read_text(encoding="utf-8"))
                if trigger.get("job_id") == safe_job_id:
                    if trigger.get("status") not in ("sent", "completed"):
                        trigger["status"] = "failed"
                        trigger["error"] = clean_text
                        trigger["failed_at"] = error_data["created_at"]
                        trigger_file.write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        return {"ok": True, "message": "Captured error status.", "data": error_data}

    job_dir = result_root / safe_job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "ok": True,
        "created_at": now.isoformat(timespec="seconds"),
        "job_id": safe_job_id,
        "project_title": req.project_title,
        "source": req.source or "firefox-worker",
        "result_text": clean_text,
        "result_raw_length": len(raw_text),
        "result_clean_length": len(clean_text),
        "result_json": req.result_json or {},
    }

    result_path = job_dir / "result_package.json"
    raw_path = job_dir / "result_raw.md"
    clean_path = job_dir / "result_clean.md"
    result_md_path = job_dir / "result.md"
    status_path = result_root / "result_status.json"
    latest_path = result_root / "latest.json"
    raw_path.write_text(raw_text, encoding="utf-8")
    clean_path.write_text(clean_text, encoding="utf-8")
    result_md_path.write_text(clean_text, encoding="utf-8")
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    status = {
        "ok": True,
        "status": "completed",
        "created_at": payload["created_at"],
        "job_id": safe_job_id,
        "project_title": req.project_title,
        "result_package_path": str(result_path),
        "result_raw_path": str(raw_path),
        "result_clean_path": str(clean_path),
    }
    archive_info = None
    archive_user_id = current_user.id if current_user else None
    if not archive_user_id:
        try:
            trigger_file_for_user = output_root / "test_triggers" / "trigger_status.json"
            if trigger_file_for_user.exists():
                trigger_payload_for_user = json.loads(trigger_file_for_user.read_text(encoding="utf-8"))
                if trigger_payload_for_user.get("job_id") == safe_job_id:
                    archive_user_id = trigger_payload_for_user.get("user_id")
        except Exception:
            archive_user_id = None
    if archive_user_id:
        try:
            archive_info = register_common_archive(
                user_id=archive_user_id,
                source="storymaker-main",
                source_job_id=safe_job_id,
                title=req.project_title or payload.get("project_title") or "새 글 만들기",
                status="completed",
                raw_result=payload.get("result_text") or "",
                extra={
                    "result_package_path": str(result_path),
                    "result_raw_path": str(raw_path),
                    "result_clean_path": str(clean_path),
                    "source": req.source or "firefox-worker",
                },
            )
            if archive_info.get("ok"):
                status["archive_job_id"] = archive_info.get("archive_job_id")
                status["archive_result_path"] = archive_info.get("archive_result_path")
        except Exception as exc:
            status["archive_error"] = str(exc)[:300]

    # 썸네일 보조 작업은 단계별 글 결과의 공용 latest 포인터를 덮어쓰지 않는다.
    # 단계별 화면은 이 포인터로 현재 글 결과를 수신하므로 storymaker_main_* 결과만 유지해야 한다.
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    trigger_file = output_root / "test_triggers" / "trigger_status.json"
    if trigger_file.exists():
        try:
            trigger = json.loads(trigger_file.read_text(encoding="utf-8"))
            if trigger.get("job_id") == safe_job_id:
                trigger["status"] = "completed"
                trigger["completed_at"] = payload["created_at"]
                trigger["result_package_path"] = str(result_path)
                trigger_file.write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return {"ok": True, "data": {**status, "result_text_length": len(payload["result_text"])}}


@app.get("/api/test/result-package/latest")
def read_latest_test_result_package():
    """
    TEST ONLY: 가장 최근 Firefox 워커 저장 결과를 반환한다.
    아직 결과가 없으면 status=pending 형태로 반환한다.
    """
    output_root = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    result_root = output_root / "test_result_packages"

    # 최근 트리거 상태 확인
    trigger_file = output_root / "test_triggers" / "trigger_status.json"
    trigger_status = "pending"
    trigger_job_id = None
    if trigger_file.exists():
        try:
            trg = json.loads(trigger_file.read_text(encoding="utf-8"))
            trigger_status = trg.get("status", "pending")
            trigger_job_id = trg.get("job_id")
        except Exception:
            pass

    # 최신 에러 파일 확인
    error_path = result_root / "latest_error.json"
    latest_error = None
    if error_path.exists():
        try:
            latest_error = json.loads(error_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 만약 현재 트리거가 failed이고 에러의 job_id가 트리거의 job_id와 일치하면 failed 리턴
    if trigger_status == "failed" and latest_error and latest_error.get("job_id") == trigger_job_id:
        return {
            "ok": True,
            "status": "failed",
            "job_id": trigger_job_id,
            "error": latest_error.get("error", "알 수 없는 에러 발생"),
            "data": latest_error,
        }

    latest_path = result_root / "latest.json"
    if not latest_path.exists():
        if trigger_status == "failed" and latest_error:
            return {
                "ok": True,
                "status": "failed",
                "job_id": latest_error.get("job_id"),
                "error": latest_error.get("error", "알 수 없는 에러 발생"),
                "data": latest_error,
            }
        return {"ok": True, "status": trigger_status, "job_id": trigger_job_id, "data": None}

    try:
        status = json.loads(latest_path.read_text(encoding="utf-8"))
        latest_job_id = str(status.get("job_id") or "").strip()
        current_job_id = str(trigger_job_id or "").strip()
        if current_job_id and trigger_status in {"pending", "claimed", "uploaded", "prompt_sent", "sent", "expired"} and latest_job_id != current_job_id:
            return {
                "ok": True,
                "status": trigger_status,
                "job_id": current_job_id,
                "message": "현재 작업 결과를 기다리는 중입니다.",
                "data": None,
            }
        # 만약 최근 트리거 상태가 failed이면, completed가 아닌 failed를 리턴해줘야 함
        if trigger_status == "failed" and trigger_job_id == status.get("job_id") and latest_error:
            return {
                "ok": True,
                "status": "failed",
                "job_id": trigger_job_id,
                "error": latest_error.get("error", "알 수 없는 에러 발생"),
                "data": latest_error,
            }

        result_path = Path(status.get("result_package_path") or "")
        if not result_path.exists():
            return {"ok": True, "status": "pending", "message": "result file not ready", "data": status}
        result = json.loads(result_path.read_text(encoding="utf-8"))
        clean_path_val = status.get("result_clean_path")
        if clean_path_val and isinstance(result, dict):
            result["result_clean_path"] = clean_path_val

        return {
            "ok": True,
            "status": "completed",
            "job_id": status.get("job_id"),
            "project_title": status.get("project_title"),
            "result_text": result.get("result_text", ""),
            "result_json": result.get("result_json", {}),
            "result_clean_path": clean_path_val,
            "data": result,
        }
    except Exception as exc:
        return {"ok": False, "status": "error", "error": str(exc), "message": str(exc), "data": None}

@app.get("/api/finance")
def get_todays_finance():
    import time
    import urllib.parse
    import urllib.request

    now = time.time()
    cache = getattr(app.state, "finance_cache", None)
    if cache and now - cache.get("ts", 0) < 600:
        return cache.get("payload")

    symbols = {
        "usd_krw": "USDKRW=X",
        "nasdaq": "^IXIC",
        "kosdaq": "^KQ11",
        "gold": "GC=F",
    }
    results = {}
    try:
        for key, sym in symbols.items():
            encoded = urllib.parse.quote(sym, safe="")
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range=5d&interval=1d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as res:
                raw = json.loads(res.read().decode("utf-8"))
            result = raw.get("chart", {}).get("result", [{}])[0]
            quote = result.get("indicators", {}).get("quote", [{}])[0]
            closes = [v for v in quote.get("close", []) if isinstance(v, (int, float))]
            if closes:
                current = closes[-1]
                prev = closes[-2] if len(closes) > 1 else current
                change = current - prev
                percent = (change / prev * 100) if prev else 0
                results[key] = {
                    "price": round(current, 2),
                    "change": round(change, 2),
                    "change_percent": round(percent, 2),
                }
            else:
                results[key] = {"price": 0, "change": 0, "change_percent": 0}
        payload = {"status": "success", "data": results}
        app.state.finance_cache = {"ts": now, "payload": payload}
        return payload
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": results}


# ------------------------------------------------------------------------------
# MVP 정적 HTML 리소스 서빙 설정
# ------------------------------------------------------------------------------

# 일반 UI 정적 파일은 캐시를 차단하되, 대용량 브라우저 TTS 모델은 하루 동안 재사용한다.
class NoCacheStaticFiles(StaticFiles):
    _BLOCKED_BACKUP_MARKERS = (
        ".backup_",
        ".before_",
        ".bak_",
        ".old_",
        "~",
    )

    async def get_response(self, path: str, scope):
        # 운영 정적 디렉터리에 남아 있는 과거 백업·임시 파일은 외부에 제공하지 않는다.
        normalized_path = str(path or "").replace("\\", "/").lower()
        filename = normalized_path.rsplit("/", 1)[-1]
        if any(marker in filename for marker in self._BLOCKED_BACKUP_MARKERS):
            raise HTTPException(status_code=404, detail="Not Found")
        return await super().get_response(path, scope)

    def is_not_modified(self, response_headers, request_headers) -> bool:
        # 기존 UI 자산은 즉시 갱신되도록 304 응답을 사용하지 않는다.
        return False

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        full_path = str(args[0] if args else kwargs.get("full_path", "")).replace("\\", "/")

        if "/v1/" in full_path or "/browser-tts/" in full_path:
            response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        if "/browser-tts/" in full_path:
            response.headers["Cache-Control"] = "public, max-age=86400"
            if "Pragma" in response.headers:
                del response.headers["Pragma"]
            if "Expires" in response.headers:
                del response.headers["Expires"]
        else:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

# 정적 리소스 파일 시스템 경로 획득
static_dir = os.path.join(os.path.dirname(__file__), "static")

# 사용자가 정적 V1 폴더 루트로 접속해도 실제 V1 화면으로 안내한다.
@app.get("/static/v1", include_in_schema=False)
@app.get("/static/v1/", include_in_schema=False)
def redirect_static_v1_root():
    return RedirectResponse(url="/v1/", status_code=307)

# /static 경로 마운트 시 커스텀 클래스 적용
app.mount("/static", NoCacheStaticFiles(directory=static_dir), name="static")

OUTPUT_RESULTS_ROOT = Path(
    os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results")
).resolve()


def _output_result_owner_id(relative_path: str) -> Optional[int]:
    """Return the DB owner for result paths whose ownership can be proven."""
    parts = Path(relative_path).parts
    if not parts:
        return None

    job_id = None
    query = None
    params: dict[str, Any] = {}

    if parts[0] == "mobile_one_shot" and len(parts) >= 3:
        job_id = parts[2]
        query = "SELECT user_id FROM mobile_one_shot_jobs WHERE job_id = :job_id LIMIT 1"
        params["job_id"] = job_id
    elif parts[0] == "storymaker_main_uploads" and len(parts) >= 2:
        job_id = parts[1]
        query = "SELECT user_id FROM content_archive_assets WHERE source_job_id = :job_id LIMIT 1"
        params["job_id"] = job_id
    elif parts[0] == "test_result_packages" and len(parts) >= 2:
        job_id = parts[1]
        query = "SELECT user_id FROM content_archive_assets WHERE source_job_id = :job_id LIMIT 1"
        params["job_id"] = job_id

    if not query:
        return None

    db = SessionLocal()
    try:
        row = db.execute(text(query), params).first()
        return int(row[0]) if row and row[0] is not None else None
    finally:
        db.close()


@app.get("/data/output_results/{relative_path:path}", include_in_schema=False)
def read_protected_output_result(
    relative_path: str,
    current_user: User = Depends(get_current_user),
):
    """Serve legacy output URLs while requiring authentication and known-owner checks."""
    requested = (OUTPUT_RESULTS_ROOT / relative_path).resolve()
    try:
        requested.relative_to(OUTPUT_RESULTS_ROOT)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not Found")

    if not requested.is_file():
        raise HTTPException(status_code=404, detail="Not Found")

    owner_id = _output_result_owner_id(relative_path)
    is_admin = str(getattr(current_user, "role", "") or "").lower() == "admin"
    if owner_id is not None and int(current_user.id) != owner_id and not is_admin:
        raise HTTPException(status_code=403, detail="이 결과 파일에 접근할 권한이 없습니다.")

    return FileResponse(
        requested,
        filename=None,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/api/test/webgpu-tts-check", include_in_schema=False)
def webgpu_tts_check_page():
    test_file = os.path.join(static_dir, "v1", "webgpu-tts-check.html")
    if not os.path.exists(test_file):
        raise HTTPException(status_code=404, detail="WebGPU TTS test page not found")
    return FileResponse(
        test_file,
        media_type="text/html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/v1/staged")
@app.get("/v1/staged/")
def read_storymaker_staged_page(
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    flags = read_runtime_stage_flags()
    if not flags["enable_stage_ui"] or not flags["enable_stage_generation"]:
        raise HTTPException(status_code=404, detail="STAGED_UI_NOT_AVAILABLE")
    staged_path = os.path.join(static_dir, "v1", "staged.html")
    return FileResponse(
        staged_path,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
        },
    )


@app.get("/v1")
@app.get("/v1/")
@app.get("/app/v1")
@app.get("/app/v1/")
def read_storymaker_v2(
    page: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    StoryMaker v2 React 앱을 별도 경로로 서빙합니다.
    기존 v1 /storymaker 화면은 건드리지 않습니다.
    Nemotron Lab은 독립 정적 화면으로 분기하며 로그인 사용자에게만 제공합니다.
    """
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    if page == "nemotronLab":
        lab_file = "index.html" if current_user else "locked.html"
        return FileResponse(os.path.join(static_dir, "v1", "nemotron-lab", lab_file), headers=headers)

    index_path = os.path.join(static_dir, "v1", "index.html")
    html = Path(index_path).read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers=headers)


# 브라우저 루트(/) 접속 시 MVP 단일 페이지 반환
@app.get("/")
@app.get("/dashboard")
@app.get("/dashboard/")
@app.get("/app")
@app.get("/app/")
def read_root():
    """
    브라우저 접속 시 MVP 단일 페이지 어플리케이션 dashboard.html을 서빙하며,
    브라우저 캐싱을 강력 차단하는 헤더를 실어 보냅니다.
    """
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "dashboard.html"), headers=headers)


@app.get("/storymaker")
@app.get("/app/storymaker")
@app.get("/app/storymaker/")
def read_storymaker(request: Request):
    action = str(request.query_params.get("action") or "").strip().lower()
    if action in {"login", "register", "join", "password", "lostpassword", "mypage", "admin"}:
        query = request.url.query
        target = "/v1/"
        if query:
            target = f"{target}?{query}"
        return RedirectResponse(url=target, status_code=307)

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "index.html"), headers=headers)


@app.get("/podcast")
@app.get("/app/podcast")
@app.get("/app/podcast/")
def read_podcast_app():
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "podcast.html"), headers=headers)


@app.get("/slideshow")
@app.get("/app/slideshow")
@app.get("/app/slideshow/")
def read_slideshow_app():
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "slideshow.html"), headers=headers)


# ------------------------------------------------------------------------------
# TEST ONLY: StoryMaker 복제 테스트 화면
# 제거 시 아래 라우트 블록과 static/index.html, common_nav.js의 TEST ONLY 버튼 블록만 삭제하면 된다.
# 운영 /storymaker 라우트와 index.html에는 영향이 없다.
# ------------------------------------------------------------------------------
# retired route removed
def read_storymaker_test():
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "index.html"), headers=headers)


from fastapi import Response

@app.get("/userscript/storymaker-chatgpt-worker.user.js")
def get_tampermonkey_userscript():
    """
    TEST ONLY: Tampermonkey가 유저스크립트 설치 화면을 정상적으로 기동할 수 있도록
    올바른 MIME 타입 및 Content-Disposition 헤더와 함께 스크립트 소스를 반환합니다.
    """
    userscript_path = Path(static_dir) / "storymaker-chatgpt-worker.user.js"
    if not userscript_path.exists():
        raise HTTPException(status_code=404, detail="Userscript file not found")
    
    content = userscript_path.read_text(encoding="utf-8")
    
    headers = {
        "Content-Disposition": 'inline; filename="storymaker-chatgpt-worker.user.js"',
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    
    return Response(
        content=content,
        media_type="text/javascript",
        headers=headers
    )


@app.get("/userscript/blocked-legacy-storymaker-gemini-worker.user.js", include_in_schema=False)
def get_gemini_tampermonkey_userscript():
    """
    Tampermonkey Gemini Worker 설치용 URL.
    기존 chatgpt 이름의 URL은 호환용으로 유지하고, 신규 기본 배포 경로는 이 라우트를 사용한다.
    """
    userscript_path = Path(static_dir) / "storymaker-gemini-worker.user.js"
    if not userscript_path.exists():
        raise HTTPException(status_code=404, detail="Userscript file not found")

    content = userscript_path.read_text(encoding="utf-8")

    headers = {
        "Content-Disposition": 'inline; filename="storymaker-gemini-worker.user.js"',
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    return Response(
        content=content,
        media_type="text/javascript",
        headers=headers
    )


BETA_INTERNAL_ORIGIN = os.getenv("STORYMAKER_BETA_INTERNAL_ORIGIN", "http://172.27.0.1:8021").rstrip("/")
BETA_INTERNAL_AUTH_SECRET = (os.getenv("BETA_INTERNAL_AUTH_SECRET") or "").strip()


def _beta_signed_user_headers(current_user: User) -> dict[str, str]:
    if not BETA_INTERNAL_AUTH_SECRET:
        raise HTTPException(status_code=503, detail="Beta 내부 인증키가 설정되지 않았습니다.")
    timestamp = str(int(time.time()))
    role = str(getattr(current_user, "role", "user") or "user").strip().lower()
    user_id = int(current_user.id)
    payload = f"{user_id}|{role}|{timestamp}".encode("utf-8")
    signature = hmac.new(BETA_INTERNAL_AUTH_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return {
        "X-StoryMaker-User-Id": str(user_id),
        "X-StoryMaker-User-Role": role,
        "X-StoryMaker-Auth-Time": timestamp,
        "X-StoryMaker-Auth-Signature": signature,
    }


def _require_beta_user(current_user: User | None) -> User:
    if current_user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return current_user


def _rewrite_beta_payload(content: bytes, content_type: str) -> bytes:
    safe_type = str(content_type or "").lower()
    if not any(token in safe_type for token in ("text/", "javascript", "json", "xml")):
        return content
    try:
        text_value = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    text_value = text_value.replace("/beta-static", "/v1/beta-static")
    text_value = text_value.replace("/beta-api", "/v1/beta-api")
    text_value = text_value.replace("/beta/production", "/v1/beta/production")
    text_value = text_value.replace("/beta/archive", "/v1/beta/archive")
    return text_value.encode("utf-8")


async def _proxy_beta_request(request: Request, upstream_path: str, current_user: User | None = None):
    target_url = BETA_INTERNAL_ORIGIN + upstream_path
    if request.url.query:
        target_url += "?" + request.url.query
    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length", "connection", "accept-encoding"}
    }
    if upstream_path.startswith("/beta-api"):
        headers.update(_beta_signed_user_headers(_require_beta_user(current_user)))
    upstream_request = urllib.request.Request(
        target_url,
        data=body if body else None,
        headers=headers,
        method=request.method,
    )
    try:
        with urllib.request.urlopen(upstream_request, timeout=120) as upstream:
            payload = upstream.read()
            content_type = upstream.headers.get("Content-Type", "application/octet-stream")
            payload = _rewrite_beta_payload(payload, content_type)
            response_headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
            for header_name in (
                "Content-Range",
                "Accept-Ranges",
                "Content-Disposition",
                "ETag",
                "Last-Modified",
            ):
                header_value = upstream.headers.get(header_name)
                if header_value:
                    response_headers[header_name] = header_value
            return Response(
                content=payload,
                status_code=upstream.status,
                media_type=content_type.split(";", 1)[0],
                headers=response_headers,
            )
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        content_type = exc.headers.get("Content-Type", "application/json")
        payload = _rewrite_beta_payload(payload, content_type)
        return Response(content=payload, status_code=exc.code, media_type=content_type.split(";", 1)[0])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Dell Beta 연결 실패: {exc}")


@app.api_route("/v1/beta/{beta_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_beta_page(request: Request, beta_path: str):
    return await _proxy_beta_request(request, "/beta/" + beta_path)


@app.api_route("/v1/beta-api/{beta_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_beta_api(
    request: Request,
    beta_path: str,
    current_user: User | None = Depends(get_optional_current_user),
):
    return await _proxy_beta_request(request, "/beta-api/" + beta_path, current_user)


@app.api_route("/v1/beta-static/{beta_path:path}", methods=["GET", "POST", "OPTIONS"])
async def proxy_beta_static(request: Request, beta_path: str):
    return await _proxy_beta_request(request, "/beta-static/" + beta_path)


@app.api_route("/beta-api/{beta_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], include_in_schema=False)
async def proxy_beta_api_legacy(
    request: Request,
    beta_path: str,
    current_user: User | None = Depends(get_optional_current_user),
):
    return await _proxy_beta_request(request, "/beta-api/" + beta_path, current_user)


@app.api_route("/beta-static/{beta_path:path}", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
async def proxy_beta_static_legacy(request: Request, beta_path: str):
    return await _proxy_beta_request(request, "/beta-static/" + beta_path)


@app.get("/podcast")
def read_podcast():
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "podcast.html"), headers=headers)


@app.get("/slideshow")
def read_slideshow():
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "slideshow.html"), headers=headers)


@app.get("/about")
def read_about():
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "about.html"), headers=headers)


@app.get("/queue-monitor")
def read_queue_monitor():
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "queue-monitor.html"), headers=headers)


# 관리자 애널리틱스 접속 시 index.html 반환
@app.get("/admin/analytics")
def read_admin_analytics():
    """
    관리자 애널리틱스 메뉴로 직접 접근 시에도 index.html을 반환하며,
    브라우저 캐싱을 강력 차단하는 헤더를 실어 보냅니다.
    """
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
    }
    return FileResponse(os.path.join(static_dir, "index.html"), headers=headers)
