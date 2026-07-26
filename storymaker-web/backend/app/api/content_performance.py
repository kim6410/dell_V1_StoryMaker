# -*- coding: utf-8 -*-
"""Admin API for Content Performance Intelligence."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.auth import get_admin_user
from app.db.models import User
from app.db import performance_repository as repo
from app.schemas import CommonResponse
from app.services import performance_intelligence_service as service

router = APIRouter()


class ScorePayload(BaseModel):
    content_id: str | None = None
    title: str
    content_text: str = ""
    keyword: str = ""
    region: str = ""
    industry: str = ""
    meta_description: str = ""
    has_image_alt: bool = False
    trend_summary: str | None = None


class RankingPayload(BaseModel):
    keyword: str
    search_engine: str = "naver"
    ranking: int | None = None
    previous_ranking: int | None = None


@router.post("/content-performance/score", response_model=CommonResponse)
def score_content(payload: ScorePayload, admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.score_content(payload.model_dump()), message="성과 점수를 계산했습니다.")


@router.get("/content-performance/dashboard", response_model=CommonResponse)
def dashboard(admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.dashboard(), message="")


@router.get("/content-performance/health", response_model=CommonResponse)
def health(admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.health_status(), message="")


@router.get("/content-performance/trends", response_model=CommonResponse)
def trends(days: int = Query(30, ge=7, le=90), admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=repo.trend(days), message="")


@router.post("/content-performance/ranking", response_model=CommonResponse)
def ranking(payload: RankingPayload, admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.add_ranking(payload.model_dump()), message="검색 순위를 저장했습니다.")


@router.get("/content-performance/ranking", response_model=CommonResponse)
def ranking_history(keyword: str | None = None, limit: int = Query(100, ge=1, le=300), admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=repo.ranking_history(keyword, limit), message="")


@router.post("/content-performance/run-once", response_model=CommonResponse)
def run_once(admin: User = Depends(get_admin_user)):
    result = service.run_performance_once()
    return CommonResponse(ok=bool(result.get("ok")), data=result, message="성과 분석 실행 요청을 처리했습니다.")
