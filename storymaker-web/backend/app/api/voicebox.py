# -*- coding: utf-8 -*-
"""StoryMaker V1 관리자용 Voicebox 어댑터.

브라우저가 Dell localhost:17493을 직접 호출하지 않도록 V1 Backend가
관리자 인증을 확인한 뒤 Voicebox REST API를 프록시한다.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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


async def _free_gpu_for_engine(client: httpx.AsyncClient, engine: str, model_size: str | None) -> None:
    """GTX1060 6GB에서 동시에 여러 Qwen TTS 모델이 상주하지 않게 정리한다.

    모델 파일은 삭제하지 않고 Voicebox unload API로 GPU 메모리만 반환한다.
    """
    size = model_size or "0.6B"
    desired = None
    if engine == "qwen":
        desired = f"qwen-tts-{size}"
    elif engine == "qwen_custom_voice":
        desired = f"qwen-custom-voice-{size}"

    candidates = (
        "qwen-tts-0.6B",
        "qwen-tts-1.7B",
        "qwen-custom-voice-0.6B",
        "qwen-custom-voice-1.7B",
    )
    for model_name in candidates:
        if model_name == desired:
            continue
        try:
            await client.post(f"{VOICEBOX_BASE_URL}/models/{model_name}/unload")
        except Exception:
            pass


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


@router.post("/profiles/clone")
async def voicebox_create_clone_profile(
    name: str = Form(..., min_length=1, max_length=100),
    reference_text: str = Form(..., min_length=1, max_length=1000),
    engine: str = Form(default="qwen", pattern="^(qwen|chatterbox|luxtts)$"),
    file: UploadFile = File(...),
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """관리자가 자신의 음성 샘플을 업로드해 Voicebox cloned profile을 만든다."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="음성 샘플 파일이 비어 있습니다.")
    if len(audio_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="음성 샘플은 50MB 이하만 등록할 수 있습니다.")

    profile_payload = {
        "name": name.strip(),
        "description": "StoryMaker V1 VoiceBox 사용자 음성 복제 프로필",
        "language": "ko",
        "voice_type": "cloned",
        "default_engine": engine,
    }

    profile_id: str | None = None
    try:
        timeout = httpx.Timeout(60.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            profile_response = await client.post(f"{VOICEBOX_BASE_URL}/profiles", json=profile_payload)
            if not profile_response.is_success:
                raise HTTPException(status_code=502, detail=_upstream_error_detail(profile_response))

            profile = profile_response.json()
            profile_id = str(profile.get("id") or "").strip()
            if not profile_id:
                raise HTTPException(status_code=502, detail="Voicebox 프로필 ID를 받지 못했습니다.")

            files = {
                "file": (
                    file.filename or "voice-sample.wav",
                    audio_bytes,
                    file.content_type or "application/octet-stream",
                )
            }
            sample_response = await client.post(
                f"{VOICEBOX_BASE_URL}/profiles/{profile_id}/samples",
                data={"reference_text": reference_text.strip()},
                files=files,
            )
            if not sample_response.is_success:
                try:
                    await client.delete(f"{VOICEBOX_BASE_URL}/profiles/{profile_id}")
                except Exception:
                    pass
                raise HTTPException(status_code=502, detail=_upstream_error_detail(sample_response))

            return {
                "ok": True,
                "profile": profile,
                "sample": sample_response.json(),
            }
    except HTTPException:
        raise
    except Exception as exc:
        if profile_id:
            try:
                async with httpx.AsyncClient(timeout=8.0) as cleanup_client:
                    await cleanup_client.delete(f"{VOICEBOX_BASE_URL}/profiles/{profile_id}")
            except Exception:
                pass
        raise HTTPException(status_code=503, detail=f"Voicebox 음성 등록 실패: {type(exc).__name__}") from exc


@router.post("/generate/start")
async def voicebox_generate_start(
    req: VoiceboxChunkGenerateRequest,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Voicebox 비동기 생성 작업을 시작하고 generation id를 반환한다."""
    payload = req.model_dump(exclude_none=True)
    try:
        timeout = httpx.Timeout(12.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            await _free_gpu_for_engine(client, req.engine, req.model_size)
            response = await client.post(f"{VOICEBOX_BASE_URL}/generate", json=payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Voicebox 엔진 연결 대기: {type(exc).__name__}") from exc

    if not response.is_success:
        raise HTTPException(status_code=502, detail=_upstream_error_detail(response))

    data = response.json()
    return {
        "ok": True,
        "generation_id": data.get("id"),
        "status": data.get("status") or "generating",
        "created_at": data.get("created_at"),
    }


@router.get("/generate/{generation_id}/status")
async def voicebox_generate_status(
    generation_id: str,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Voicebox 생성 작업의 실제 상태를 반환한다."""
    try:
        timeout = httpx.Timeout(8.0, connect=3.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{VOICEBOX_BASE_URL}/history/{generation_id}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Voicebox 상태 확인 지연: {type(exc).__name__}") from exc

    if not response.is_success:
        raise HTTPException(status_code=502, detail=_upstream_error_detail(response))

    data = response.json()
    return {
        "ok": True,
        "generation_id": generation_id,
        "status": data.get("status") or "generating",
        "duration": data.get("duration") or 0,
        "error": data.get("error"),
        "audio_ready": bool(data.get("audio_path")),
    }


@router.get("/generate/{generation_id}/audio")
async def voicebox_generate_audio(
    generation_id: str,
    _: User = Depends(get_admin_user),
) -> Response:
    """완료된 Voicebox 생성 음원을 관리자 Studio로 전달한다."""
    try:
        timeout = httpx.Timeout(30.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{VOICEBOX_BASE_URL}/audio/{generation_id}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Voicebox 오디오 수신 지연: {type(exc).__name__}") from exc

    if not response.is_success:
        raise HTTPException(status_code=502, detail=_upstream_error_detail(response))

    return Response(
        content=response.content,
        media_type=(response.headers.get("content-type") or "audio/wav").split(";")[0],
        headers={"Cache-Control": "no-store"},
    )


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
            await _free_gpu_for_engine(client, req.engine, req.model_size)
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
