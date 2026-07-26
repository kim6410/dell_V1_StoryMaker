from __future__ import annotations

import os
import re
import time
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .tts_schemas import TtsRequest
from .usage_store import record_request


KST = ZoneInfo("Asia/Seoul")
TTS_MODEL_ID = "nvidia/magpie-tts-multilingual"
DEFAULT_FUNCTION_ID = "877104f7-e885-42b9-8de8-f6e4c6303969"
VOICE_CACHE_SECONDS = int(os.getenv("NEMOTRON_LAB_TTS_VOICE_CACHE_SECONDS", "600"))
TTS_TIMEOUT_SECONDS = float(os.getenv("NEMOTRON_LAB_TTS_TIMEOUT_SECONDS", "120"))

LANGUAGE_LABELS = {
    "en-US": "영어(미국)",
    "es-US": "스페인어(미국)",
    "fr-FR": "프랑스어",
    "de-DE": "독일어",
    "zh-CN": "중국어(간체)",
    "vi-VN": "베트남어",
    "it-IT": "이탈리아어",
    "hi-IN": "힌디어",
    "ja-JP": "일본어",
}


class NvidiaTtsService:
    def __init__(self) -> None:
        self.api_key = os.getenv("NVIDIA_API_KEY", "").strip()
        self.function_id = os.getenv("NVIDIA_MAGPIE_TTS_FUNCTION_ID", DEFAULT_FUNCTION_ID).strip()
        self._voices: list[str] = []
        self._voices_fetched_at = 0.0
        self._last_error: str | None = None
        self._last_connected_at: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.function_id)

    @property
    def base_url(self) -> str:
        return f"https://{self.function_id}.invocation.api.nvcf.nvidia.com"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json, audio/wav, application/octet-stream",
            "User-Agent": "StoryMaker-Nemotron-Lab-TTS/1.0",
        }

    @staticmethod
    def _collect_voices(value: Any, output: set[str]) -> None:
        if isinstance(value, str):
            if value.startswith("Magpie-"):
                output.add(value)
            return
        if isinstance(value, list):
            for item in value:
                NvidiaTtsService._collect_voices(item, output)
            return
        if isinstance(value, dict):
            for item in value.values():
                NvidiaTtsService._collect_voices(item, output)

    @staticmethod
    def _voice_language(voice: str) -> str:
        parts = voice.split(".")
        if len(parts) < 2:
            return ""
        raw_code = parts[1]
        normalized = {code.upper(): code for code in LANGUAGE_LABELS}
        return normalized.get(raw_code.upper(), raw_code)

    async def voices(self, force: bool = False) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("NVIDIA TTS API 설정이 없습니다.")

        now = time.monotonic()
        if self._voices and not force and now - self._voices_fetched_at < VOICE_CACHE_SECONDS:
            return self._voice_payload()

        timeout = httpx.Timeout(30.0, connect=15.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(
                    f"{self.base_url}/v1/audio/list_voices",
                    headers=self._headers(),
                )
            if response.status_code >= 400:
                raise RuntimeError(f"NVIDIA TTS 음성 목록 오류 {response.status_code}: {response.text[:300]}")
            payload = response.json()
            found: set[str] = set()
            self._collect_voices(payload, found)
            self._voices = sorted(found)
            self._voices_fetched_at = now
            self._last_error = None
            self._last_connected_at = datetime.now(KST).isoformat(timespec="seconds")
            return self._voice_payload()
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            raise

    def _voice_payload(self) -> dict[str, Any]:
        grouped: dict[str, list[str]] = {code: [] for code in LANGUAGE_LABELS}
        for voice in self._voices:
            code = self._voice_language(voice)
            if code in grouped:
                grouped[code].append(voice)
        return {
            "enabled": self.enabled,
            "model": TTS_MODEL_ID,
            "function_id_configured": bool(self.function_id),
            "voice_count": len(self._voices),
            "voices": self._voices,
            "languages": [
                {
                    "code": code,
                    "label": label,
                    "voices": grouped.get(code, []),
                }
                for code, label in LANGUAGE_LABELS.items()
            ],
            "last_error": self._last_error,
            "last_connected_at": self._last_connected_at,
        }

    async def synthesize(
        self,
        request: TtsRequest,
        user_id: int,
        username: str,
        client_ip: str,
    ) -> tuple[bytes, dict[str, Any]]:
        if not self.enabled:
            raise RuntimeError("NVIDIA TTS API 설정이 없습니다.")
        if re.search(r"[ㄱ-ㅎㅏ-ㅣ가-힣]", request.text):
            raise RuntimeError("Magpie Multilingual은 한국어를 지원하지 않습니다. 지원 언어로 번역한 뒤 다시 요청해 주세요.")

        request_id = f"ntts_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(KST).isoformat(timespec="seconds")
        started = time.perf_counter()
        status = "failed"
        error: str | None = None
        audio = b""

        form = {
            "text": request.text,
            "language": request.language,
            "encoding": "LINEAR_PCM",
            "sample_rate_hz": str(request.sample_rate_hz),
        }
        if request.voice:
            form["voice"] = request.voice

        try:
            timeout = httpx.Timeout(TTS_TIMEOUT_SECONDS, connect=20.0)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(
                    f"{self.base_url}/v1/audio/synthesize",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "audio/wav, application/octet-stream",
                        "User-Agent": "StoryMaker-Nemotron-Lab-TTS/1.0",
                    },
                    data=form,
                )
            if response.status_code >= 400:
                raise RuntimeError(f"NVIDIA TTS 합성 오류 {response.status_code}: {response.text[:500]}")
            content_type = response.headers.get("content-type", "").lower()
            if not response.content:
                raise RuntimeError("NVIDIA TTS가 빈 오디오를 반환했습니다.")
            if "audio" not in content_type and not response.content.startswith(b"RIFF"):
                raise RuntimeError(f"예상하지 못한 TTS 응답 형식입니다: {content_type or 'unknown'}")
            audio = response.content
            status = "completed"
            self._last_error = None
            self._last_connected_at = datetime.now(KST).isoformat(timespec="seconds")
        except httpx.TimeoutException:
            status = "timeout"
            error = f"{int(TTS_TIMEOUT_SECONDS)}초 안에 TTS 응답이 완료되지 않았습니다."
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
            self._last_error = error

        latency_ms = round((time.perf_counter() - started) * 1000)
        record_request({
            "request_id": request_id,
            "user_id": int(user_id),
            "username": username,
            "client_ip": client_ip,
            "mode": "tts",
            "model": TTS_MODEL_ID,
            "prompt": request.text,
            "response": f"[audio/wav {len(audio)} bytes]" if audio else "",
            "status": status,
            "error": error,
            "latency_ms": latency_ms,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "finish_reason": "audio_complete" if status == "completed" else None,
            "created_at": created_at,
        })

        if status != "completed":
            raise RuntimeError(error or "TTS 합성에 실패했습니다.")

        metadata = {
            "request_id": request_id,
            "model": TTS_MODEL_ID,
            "language": request.language,
            "voice": request.voice,
            "sample_rate_hz": request.sample_rate_hz,
            "latency_ms": latency_ms,
            "audio_bytes": len(audio),
            "created_at": created_at,
        }
        return audio, metadata


tts_service = NvidiaTtsService()
