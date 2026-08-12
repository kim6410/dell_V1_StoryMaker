# -*- coding: utf-8 -*-
"""StoryMaker V1 관리자용 Voicebox 어댑터.

브라우저가 Dell localhost:17493을 직접 호출하지 않도록 V1 Backend가
관리자 인증을 확인한 뒤 Voicebox REST API를 프록시한다.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.auth import get_admin_user
from app.db.models import User

router = APIRouter(prefix="/voicebox")

VOICEBOX_BASE_URL = os.getenv("STORYMAKER_VOICEBOX_URL", "http://172.27.0.1:17493").rstrip("/")
VOICEBOX_CONNECT_TIMEOUT = 2.0
VOICEBOX_GENERATE_TIMEOUT = 180.0


class VoiceboxChunkGenerateRequest(BaseModel):
    profile_id: str = Field(..., min_length=1, max_length=160)
    text: str = Field(..., min_length=1, max_length=5000)
    language: str = Field(default="ko", pattern="^(zh|en|ja|ko|de|fr|ru|pt|es|it|he|ar|da|el|fi|hi|ms|nl|no|pl|sv|sw|tr)$")
    engine: str = Field(default="qwen", pattern="^(qwen|qwen_custom_voice|luxtts|chatterbox|chatterbox_turbo|tada|kokoro)$")
    model_size: str | None = Field(default="0.6B", pattern="^(1\\.7B|0\\.6B|1B|3B)$")
    instruct: str | None = Field(default=None, max_length=500)
    seed: int | None = Field(default=None, ge=0)
    max_chunk_chars: int = Field(default=800, ge=100, le=5000)
    crossfade_ms: int = Field(default=50, ge=0, le=500)
    normalize: bool = True


def _upstream_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            return str(payload.get("detail") or payload.get("message") or payload)
    except Exception:
        pass
    text = (response.text or "").strip()
    return text[:500] or f"Voicebox upstream HTTP {response.status_code}"


@router.get("/health")
async def voicebox_health(_: User = Depends(get_admin_user)) -> dict[str, Any]:
    """Voicebox 독립 서버의 실제 연결 상태를 반환한다.

    엔진이 꺼져 있어도 V1 API 자체는 200을 반환하고 online=false로 표시한다.
    """
    try:
        timeout = httpx.Timeout(VOICEBOX_CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{VOICEBOX_BASE_URL}/health")
        return {
            "ok": True,
            "online": response.is_success,
            "upstream_status": response.status_code,
            "base_url": "localhost:17493",
        }
    except Exception as exc:
        return {
            "ok": True,
            "online": False,
            "upstream_status": None,
            "base_url": "localhost:17493",
            "reason": type(exc).__name__,
        }


@router.get("/profiles")
async def voicebox_profiles(_: User = Depends(get_admin_user)) -> dict[str, Any]:
    """Voicebox에 등록된 음성 프로필 목록을 관리자 UI에 전달한다."""
    try:
        timeout = httpx.Timeout(8.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{VOICEBOX_BASE_URL}/profiles")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Voicebox 엔진 연결 대기: {type(exc).__name__}") from exc

    if not response.is_success:
        raise HTTPException(status_code=502, detail=_upstream_error_detail(response))

    payload = response.json()
    profiles = payload if isinstance(payload, list) else []
    return {"ok": True, "profiles": profiles, "count": len(profiles)}


@router.post("/generate/chunk")
async def voicebox_generate_chunk(
    req: VoiceboxChunkGenerateRequest,
    _: User = Depends(get_admin_user),
) -> Response:
    """청크 하나를 Voicebox /generate/stream으로 생성하고 WAV를 그대로 반환한다."""
    payload = req.model_dump(exclude_none=True)
    try:
        timeout = httpx.Timeout(VOICEBOX_GENERATE_TIMEOUT, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{VOICEBOX_BASE_URL}/generate/stream", json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Voicebox 음성 생성 시간이 초과되었습니다.") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Voicebox 엔진 연결 대기: {type(exc).__name__}") from exc

    if not response.is_success:
        raise HTTPException(status_code=502, detail=_upstream_error_detail(response))

    content_type = response.headers.get("content-type") or "audio/wav"
    return Response(
        content=response.content,
        media_type=content_type.split(";")[0],
        headers={
            "Cache-Control": "no-store",
            "X-StoryMaker-Voicebox": "chunk-stream",
        },
    )
