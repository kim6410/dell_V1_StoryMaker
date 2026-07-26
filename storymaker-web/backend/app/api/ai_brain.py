# -*- coding: utf-8 -*-
"""Admin API for AI Content Intelligence Brain."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import get_admin_user
from app.db.models import User
from app.schemas import CommonResponse
from app.services import intelligence_service as service

router = APIRouter()


class PromptScorePayload(BaseModel):
    prompt_id: str | None = None
    prompt_text: str = ""
    keyword: str = ""
    region: str = ""
    industry: str = ""


@router.post("/ai-brain/score", response_model=CommonResponse)
def score_prompt(payload: PromptScorePayload, admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.score_prompt(payload.model_dump()), message="Prompt Intelligence Score를 계산했습니다.")


@router.post("/ai-brain/evolve", response_model=CommonResponse)
def evolve(admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.evolve_prompt(), message="Prompt Evolution을 생성했습니다.")


@router.get("/ai-brain/dashboard", response_model=CommonResponse)
def dashboard(admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.dashboard(), message="")


@router.get("/ai-brain/health", response_model=CommonResponse)
def health(admin: User = Depends(get_admin_user)):
    return CommonResponse(ok=True, data=service.health_status(), message="")


@router.post("/ai-brain/run-once", response_model=CommonResponse)
def run_once(admin: User = Depends(get_admin_user)):
    result = service.run_brain_once()
    return CommonResponse(ok=bool(result.get("ok")), data=result, message="AI Brain 실행 요청을 처리했습니다.")
