from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .schemas import LabRequest
from .usage_store import record_request


KST = ZoneInfo("Asia/Seoul")
DEFAULT_MODEL = os.getenv("NEMOTRON_LAB_DEFAULT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("NEMOTRON_LAB_TIMEOUT_SECONDS", "75"))
MODEL_CACHE_SECONDS = int(os.getenv("NEMOTRON_LAB_MODEL_CACHE_SECONDS", "300"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("NEMOTRON_LAB_MAX_CONCURRENT", "3"))

_EXCLUDED_MODEL_MARKERS = (
    "embed", "rerank", "nvclip", "whisper", "audio", "speech", "tts",
    "image", "video", "vision-encoder", "ocr", "detector", "segment",
)


def _display_name(model_id: str) -> str:
    tail = model_id.split("/")[-1]
    replacements = {
        "nemotron-3-ultra-550b-a55b": "Nemotron 3 Ultra",
        "llama-3.1-nemotron-ultra-253b-v1": "Llama 3.1 Nemotron Ultra",
        "llama-3.1-nemotron-70b-instruct": "Llama 3.1 Nemotron 70B",
    }
    if tail in replacements:
        return replacements[tail]
    return " ".join(part.upper() if part in {"ai", "llm", "v1", "v2", "v3"} else part.capitalize() for part in tail.replace("_", "-").split("-") if part)


def _provider(model_id: str) -> str:
    return model_id.split("/", 1)[0] if "/" in model_id else "NVIDIA"


def _description(model_id: str) -> str:
    lowered = model_id.lower()
    if "nemotron-3-ultra" in lowered:
        return "대화·번역·장문 프롬프트 실험용 NVIDIA Nemotron 모델"
    if "nemotron" in lowered:
        return "NVIDIA Nemotron 계열 언어 모델"
    if "llama" in lowered:
        return "Llama 계열 범용 언어 모델"
    if "deepseek" in lowered:
        return "추론·코딩·장문 작업에 적합한 언어 모델"
    if "qwen" in lowered:
        return "다국어·요약·코딩 실험용 언어 모델"
    return "NVIDIA API Catalog에서 제공되는 텍스트 생성 모델"


def _extract_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    chunks.append(str(text))
        return "\n".join(chunks).strip()
    reasoning = message.get("reasoning_content") or message.get("reasoning")
    return str(reasoning or "").strip()


class NemotronLabService:
    def __init__(self) -> None:
        self.api_key = os.getenv("NVIDIA_API_KEY", "").strip()
        self.base_url = BASE_URL
        self.default_model = DEFAULT_MODEL
        self._models: list[dict[str, Any]] = []
        self._models_fetched_at = 0.0
        self._last_error: str | None = None
        self._last_connected_at: str | None = None
        self._semaphore = asyncio.Semaphore(max(1, MAX_CONCURRENT_REQUESTS))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "StoryMaker-Nemotron-Lab/1.0",
        }

    async def models(self, force: bool = False) -> list[dict[str, Any]]:
        if not self.enabled:
            self._last_error = "NVIDIA_API_KEY가 설정되지 않았습니다."
            return []
        now = time.monotonic()
        if self._models and not force and now - self._models_fetched_at < MODEL_CACHE_SECONDS:
            return self._models

        try:
            timeout = httpx.Timeout(20.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{self.base_url}/models", headers=self._headers())
                response.raise_for_status()
                payload = response.json()
            raw_items = payload.get("data", []) if isinstance(payload, dict) else []
            ids = sorted({str(item.get("id") or "").strip() for item in raw_items if isinstance(item, dict) and item.get("id")})
            text_ids = [model_id for model_id in ids if not any(marker in model_id.lower() for marker in _EXCLUDED_MODEL_MARKERS)]
            if self.default_model not in text_ids:
                text_ids.insert(0, self.default_model)
            preferred = [model_id for model_id in text_ids if "nemotron" in model_id.lower()]
            others = [model_id for model_id in text_ids if model_id not in preferred]
            ordered = preferred + others
            self._models = [
                {
                    "id": model_id,
                    "name": _display_name(model_id),
                    "provider": _provider(model_id),
                    "description": _description(model_id),
                    "preferred": model_id == self.default_model,
                }
                for model_id in ordered[:80]
            ]
            self._models_fetched_at = now
            self._last_error = None
            self._last_connected_at = datetime.now(KST).isoformat(timespec="seconds")
            return self._models
        except Exception as exc:
            self._last_error = f"모델 목록 조회 실패: {type(exc).__name__}: {str(exc)[:240]}"
            if not self._models:
                self._models = [{
                    "id": self.default_model,
                    "name": _display_name(self.default_model),
                    "provider": _provider(self.default_model),
                    "description": _description(self.default_model),
                    "preferred": True,
                }]
            return self._models

    async def status(self) -> dict[str, Any]:
        models = await self.models(force=False) if self.enabled else []
        return {
            "enabled": self.enabled,
            "status": "online" if self.enabled and not self._last_error else "offline",
            "base_url": self.base_url,
            "default_model": self.default_model,
            "model_count": len(models),
            "last_error": self._last_error,
            "last_connected_at": self._last_connected_at,
            "queue_isolated": True,
            "storymaker_worker_access": False,
            "gemini_worker_access": False,
            "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
            "timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "streaming_supported": False,
        }

    async def validate_model(self, model_id: str) -> bool:
        models = await self.models(force=False)
        return any(item.get("id") == model_id for item in models)

    def _messages(self, request: LabRequest) -> list[dict[str, str]]:
        if request.mode == "translate":
            system = (
                "당신은 전문 번역가입니다. 원문의 뜻, 감정, 고유명사와 문단 구조를 보존하면서 "
                f"{request.source_language} 원문을 {request.target_language}로 자연스럽게 번역하세요. "
                "설명이나 머리말 없이 번역문만 출력하세요."
            )
        elif request.mode == "prompt":
            system = (
                "당신은 프롬프트 실행 품질을 검증하는 언어 모델입니다. 사용자가 제공한 지시를 정확히 따르고, "
                "필요한 결과만 완성도 높게 출력하세요. 불필요한 자기소개나 메타 설명은 하지 마세요."
            )
        else:
            system = (
                "당신은 StoryMaker AI 연구실 2의 대화 모델입니다. 한국어 질문에는 자연스럽고 정확한 한국어로 답하고, "
                "사용자의 의도를 먼저 파악해 실용적인 답변을 제공하세요. 모르는 사실은 추측하지 마세요."
            )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": request.prompt},
        ]

    async def execute_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        user_id: int,
        username: str,
        client_ip: str,
    ) -> dict[str, Any]:
        request_id = f"nlab_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(KST).isoformat(timespec="seconds")
        started = time.perf_counter()
        status = "failed"
        content = ""
        error: str | None = None
        input_tokens = output_tokens = total_tokens = 0
        finish_reason: str | None = None

        if not self.enabled:
            error = "NVIDIA API 키가 연결되지 않았습니다."
        elif not await self.validate_model(model):
            error = "허용되지 않았거나 현재 계정에서 사용할 수 없는 모델입니다."
        else:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            try:
                async with self._semaphore:
                    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=15.0)
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers=self._headers(),
                            json=payload,
                        )
                if response.status_code >= 400:
                    detail = response.text[:600]
                    error = f"NVIDIA API 오류 {response.status_code}: {detail}"
                else:
                    data = response.json()
                    choices = data.get("choices") or []
                    choice = choices[0] if choices else {}
                    message = choice.get("message") or {}
                    content = _extract_text(message)
                    finish_reason = choice.get("finish_reason")
                    usage = data.get("usage") or {}
                    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
                    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
                    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
                    if content:
                        status = "completed"
                    else:
                        error = "모델 응답에 표시할 텍스트가 없습니다."
            except httpx.TimeoutException:
                status = "timeout"
                error = f"{int(REQUEST_TIMEOUT_SECONDS)}초 안에 응답하지 않아 요청을 종료했습니다."
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:500]}"

        latency_ms = round((time.perf_counter() - started) * 1000)
        last_prompt = messages[-1]["content"] if messages else ""
        record = {
            "request_id": request_id,
            "user_id": int(user_id),
            "username": username,
            "client_ip": client_ip,
            "mode": "chat",
            "model": model,
            "prompt": last_prompt,
            "response": content,
            "status": status,
            "error": error,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "finish_reason": finish_reason,
            "created_at": created_at,
        }
        record_request(record)
        return {
            "ok": status == "completed",
            "request_id": request_id,
            "status": status,
            "mode": "chat",
            "model": model,
            "content": content,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "finish_reason": finish_reason,
            "error": error,
            "created_at": created_at,
        }

    async def execute(self, request: LabRequest, user_id: int, username: str, client_ip: str) -> dict[str, Any]:
        request_id = f"nlab_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(KST).isoformat(timespec="seconds")
        started = time.perf_counter()
        status = "failed"
        content = ""
        error: str | None = None
        input_tokens = output_tokens = total_tokens = 0
        finish_reason: str | None = None

        if not self.enabled:
            error = "NVIDIA API 키가 연결되지 않았습니다."
        elif not await self.validate_model(request.model):
            error = "허용되지 않았거나 현재 계정에서 사용할 수 없는 모델입니다."
        else:
            payload = {
                "model": request.model,
                "messages": self._messages(request),
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": False,
            }
            try:
                async with self._semaphore:
                    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=15.0)
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers=self._headers(),
                            json=payload,
                        )
                if response.status_code >= 400:
                    detail = response.text[:600]
                    error = f"NVIDIA API 오류 {response.status_code}: {detail}"
                else:
                    data = response.json()
                    choices = data.get("choices") or []
                    choice = choices[0] if choices else {}
                    message = choice.get("message") or {}
                    content = _extract_text(message)
                    finish_reason = choice.get("finish_reason")
                    usage = data.get("usage") or {}
                    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
                    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
                    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
                    if content:
                        status = "completed"
                    else:
                        error = "모델 응답에 표시할 텍스트가 없습니다."
            except httpx.TimeoutException:
                status = "timeout"
                error = f"{int(REQUEST_TIMEOUT_SECONDS)}초 안에 응답하지 않아 요청을 종료했습니다."
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:500]}"

        latency_ms = round((time.perf_counter() - started) * 1000)
        record = {
            "request_id": request_id,
            "user_id": int(user_id),
            "username": username,
            "client_ip": client_ip,
            "mode": request.mode,
            "model": request.model,
            "prompt": request.prompt,
            "response": content,
            "status": status,
            "error": error,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "finish_reason": finish_reason,
            "created_at": created_at,
        }
        record_request(record)
        return {
            "ok": status == "completed",
            "request_id": request_id,
            "status": status,
            "mode": request.mode,
            "model": request.model,
            "content": content,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "finish_reason": finish_reason,
            "error": error,
            "created_at": created_at,
        }
