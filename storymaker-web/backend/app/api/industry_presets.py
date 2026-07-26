# -*- coding: utf-8 -*-
"""
StoryMaker v2 업종 프리셋 프록시 API.

v2 브라우저는 WordPress REST API를 직접 호출하지 않습니다.
이 라우터가 로그인/권한을 확인한 뒤 WordPress storymaker/v1 원장 API로 서버 대 서버 중계합니다.
"""
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.api.wordpress import wp_config
from app.db.models import User

router = APIRouter()

INDUSTRY_META_KEYS = [
    "industry_key",
    "category",
    "industry_flow",
    "core_point",
    "keyword_hint",
    "tone_guide",
    "avoid_terms",
    "sample_prompt",
    "sort_order",
    "is_active",
    "visibility",
]


def _wp_storymaker_api_base() -> str:
    explicit = os.getenv("WORDPRESS_STORYMAKER_API_URL", "").rstrip("/")
    if explicit:
        return explicit
    api_url, _, _ = wp_config()
    if api_url.endswith("/wp/v2"):
        return api_url[: -len("/wp/v2")] + "/storymaker/v1"
    return api_url.rstrip("/").replace("/wp/v2", "/storymaker/v1")


def _storymaker_secret_header() -> Dict[str, str]:
    secret = os.getenv("WORDPRESS_STORYMAKER_SECRET_KEY", "").strip()
    return {"X-StoryMaker-Secret-Key": secret} if secret else {}


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 계정으로 로그인해야 업종 프리셋을 수정할 수 있습니다.")


def _safe_text(value: Any, limit: int = 20000) -> str:
    return str(value or "").strip()[:limit]


class IndustryPresetPayload(BaseModel):
    title: str = Field(default="", max_length=200)
    industry_key: str = Field(default="", max_length=120)
    category: str = Field(default="", max_length=120)
    industry_flow: str = Field(default="", max_length=20000)
    core_point: str = Field(default="", max_length=20000)
    keyword_hint: str = Field(default="", max_length=20000)
    tone_guide: str = Field(default="", max_length=20000)
    avoid_terms: str = Field(default="", max_length=20000)
    sample_prompt: str = Field(default="", max_length=50000)
    sort_order: int = 0
    is_active: bool = True
    visibility: str = Field(default="public", max_length=40)


class IndustryPresetOrderItem(BaseModel):
    id: int
    sort_order: int


def _to_wp_payload(req: IndustryPresetPayload) -> Dict[str, Any]:
    title = _safe_text(req.title, 200) or _safe_text(req.industry_key, 120) or "새 업종 프리셋"
    return {
        "title": title,
        "industry_key": _safe_text(req.industry_key, 120),
        "category": _safe_text(req.category, 120),
        "industry_flow": _safe_text(req.industry_flow),
        "core_point": _safe_text(req.core_point),
        "keyword_hint": _safe_text(req.keyword_hint),
        "tone_guide": _safe_text(req.tone_guide),
        "avoid_terms": _safe_text(req.avoid_terms),
        "sample_prompt": _safe_text(req.sample_prompt, 50000),
        "sort_order": int(req.sort_order or 0),
        "is_active": bool(req.is_active),
        "visibility": _safe_text(req.visibility, 40) or "public",
    }


async def _wp_request(method: str, path: str, *, json_payload: Optional[Any] = None, params: Optional[Dict[str, Any]] = None) -> Any:
    api_base = _wp_storymaker_api_base()
    _, username, app_password = wp_config()
    url = f"{api_base}/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(auth=(username, app_password), timeout=20) as client:
            response = await client.request(method, url, json=json_payload, params=params, headers=_storymaker_secret_header())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WordPress 업종 프리셋 API 연결 실패: {exc}")

    if response.status_code == 404:
        raise HTTPException(status_code=503, detail="WordPress 업종 프리셋 REST API가 아직 설치되지 않았습니다.")
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=f"WordPress 업종 프리셋 API 오류: {response.text[:1000]}")
    try:
        return response.json()
    except Exception:
        raise HTTPException(status_code=502, detail="WordPress 업종 프리셋 API 응답을 해석할 수 없습니다.")


@router.get("/industry-presets")
async def list_industry_presets(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
):
    data = await _wp_request("GET", "industry-presets", params={"active_only": "1" if active_only else "0"})
    return {"ok": True, "data": data, "message": "업종 프리셋 목록 조회 완료"}


@router.post("/industry-presets")
async def create_industry_preset(req: IndustryPresetPayload, current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    data = await _wp_request("POST", "industry-presets", json_payload=_to_wp_payload(req))
    return {"ok": True, "data": data, "message": "업종 프리셋 생성 완료"}


@router.put("/industry-presets/{preset_id}")
async def update_industry_preset(preset_id: int, req: IndustryPresetPayload, current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    data = await _wp_request("PUT", f"industry-presets/{preset_id}", json_payload=_to_wp_payload(req))
    return {"ok": True, "data": data, "message": "업종 프리셋 수정 완료"}


@router.put("/industry-presets/order")
async def update_industry_preset_order(items: List[IndustryPresetOrderItem], current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    data = await _wp_request("PUT", "industry-presets/order", json_payload=[item.model_dump() for item in items])
    return {"ok": True, "data": data, "message": "업종 프리셋 순서 저장 완료"}


@router.delete("/industry-presets/{preset_id}")
async def deactivate_industry_preset(preset_id: int, current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    data = await _wp_request("DELETE", f"industry-presets/{preset_id}")
    return {"ok": True, "data": data, "message": "업종 프리셋 비활성화 완료"}
