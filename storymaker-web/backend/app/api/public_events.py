# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import get_current_user
from app.db.models import User
from app.integration.public_events import PublicEventsError, TourAPIClient
from app.integration.public_events_store import latest_sync_status, sync_public_events_once

router = APIRouter(prefix="/public-events")


def _client() -> TourAPIClient:
    return TourAPIClient()


@router.get("/status")
def status(current_user: User = Depends(get_current_user)):
    client = _client()
    return {
        "ok": True,
        "data": {
            "configured": client.configured,
            "source": "한국관광공사 TourAPI",
            "base_url": client.base_url,
            "sync": latest_sync_status(),
        },
    }


@router.post("/sync-now")
def sync_now(current_user: User = Depends(get_current_user)):
    if str(getattr(current_user, "role", "") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    result = sync_public_events_once(force=True)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error") or "동기화 실패")
    return {"ok": True, "data": result}


@router.get("/regions")
def regions(current_user: User = Depends(get_current_user)):
    try:
        return {"ok": True, "data": {"items": _client().regions()}}
    except PublicEventsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/districts")
def districts(
    region_code: str = Query(..., min_length=1, max_length=12),
    current_user: User = Depends(get_current_user),
):
    try:
        return {"ok": True, "data": {"items": _client().districts(region_code)}}
    except PublicEventsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/festivals")
def festivals(
    start_date: date | None = None,
    end_date: date | None = None,
    region_code: str = "",
    district_code: str = "",
    page: int = Query(1, ge=1, le=1000),
    rows: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    start = start_date or datetime.now().date()
    end = end_date or (start + timedelta(days=45))
    if end < start:
        raise HTTPException(status_code=422, detail="종료일은 시작일보다 빠를 수 없습니다.")
    try:
        data = _client().festivals(start, end, region_code, district_code, page, rows)
        return {"ok": True, "data": data}
    except PublicEventsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/places")
def places(
    region_code: str = "",
    district_code: str = "",
    page: int = Query(1, ge=1, le=1000),
    rows: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    try:
        data = _client().places(region_code, district_code, page, rows)
        return {"ok": True, "data": data}
    except PublicEventsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/festivals/{content_id}")
def festival_detail(
    content_id: str,
    content_type_id: str = Query("15", min_length=1, max_length=8),
    current_user: User = Depends(get_current_user),
):
    clean_id = "".join(ch for ch in content_id if ch.isdigit())
    if not clean_id:
        raise HTTPException(status_code=422, detail="올바른 행사 content_id가 필요합니다.")
    try:
        return {"ok": True, "data": _client().festival_detail(clean_id, content_type_id)}
    except PublicEventsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
