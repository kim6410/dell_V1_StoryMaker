# -*- coding: utf-8 -*-
"""Admin API for Pattern Knowledge Engine."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_admin_user
from app.db.database import get_db
from app.db.models import User
from app.db import pattern_repository as repo
from app.schemas import CommonResponse
from app.services import pattern_knowledge_service as service

router = APIRouter()


class LearningTargetPayload(BaseModel):
    id: int | None = None
    company_name: str
    industry: str
    region: str
    primary_keywords: list[str] | str = []
    secondary_keywords: list[str] | str = []
    priority: str = "MEDIUM"
    is_active: bool = True
    next_run_at: str | None = None


@router.get("/pattern-knowledge/targets", response_model=CommonResponse)
def list_targets(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.list_learning_targets(db), message="")


@router.post("/pattern-knowledge/targets", response_model=CommonResponse)
def save_target(payload: LearningTargetPayload, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    try:
        return CommonResponse(ok=True, data=service.save_learning_target(db, payload.model_dump()), message="학습 대상이 저장되었습니다.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/pattern-knowledge/targets/{target_id}", response_model=CommonResponse)
def update_target(target_id: int, payload: LearningTargetPayload, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    data = payload.model_dump()
    data["id"] = target_id
    return CommonResponse(ok=True, data=service.save_learning_target(db, data), message="학습 대상이 수정되었습니다.")


@router.post("/pattern-knowledge/run-once", response_model=CommonResponse)
def run_once(target_id: int | None = None, admin: User = Depends(get_admin_user)):
    result = service.run_target_now(target_id)
    return CommonResponse(ok=bool(result.get("ok")), data=result, message="학습 실행 요청을 처리했습니다.")


@router.get("/pattern-knowledge/history", response_model=CommonResponse)
def history(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=repo.list_history(db, limit), message="")


@router.get("/pattern-knowledge/health", response_model=CommonResponse)
def health(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.health_status(db), message="")


@router.get("/pattern-knowledge/trends", response_model=CommonResponse)
def trends(days: int = Query(30, ge=7, le=90), keyword: str | None = None, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.trend_report(db, days, keyword), message="")


@router.get("/pattern-knowledge/keywords/discover", response_model=CommonResponse)
def discover(seed: str = Query(..., description="기준 키워드"), db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.discover_keywords(db, seed), message="추천 키워드를 생성했습니다.")


@router.get("/pattern-knowledge/snapshots", response_model=CommonResponse)
def snapshots(days: int = Query(30, ge=7, le=90), keyword: str | None = None, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=repo.recent_snapshots(db, days, keyword)[:100], message="")
