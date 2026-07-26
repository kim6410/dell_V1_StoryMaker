from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


LabMode = Literal["chat", "translate", "prompt"]


class LabRequest(BaseModel):
    mode: LabMode = "chat"
    prompt: str = Field(min_length=1, max_length=4000)
    model: str = Field(min_length=1, max_length=180)
    source_language: str = Field(default="자동 감지", max_length=40)
    target_language: str = Field(default="영어", max_length=40)
    temperature: float = Field(default=0.35, ge=0.0, le=1.5)
    max_tokens: int = Field(default=2048, ge=64, le=4096)
    stream: bool = False

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not value:
            raise ValueError("질문 또는 요청을 입력해 주세요.")
        return value


class ModelItem(BaseModel):
    id: str
    name: str
    provider: str
    description: str
    preferred: bool = False


class LabResponse(BaseModel):
    ok: bool
    request_id: str
    status: str
    mode: LabMode
    model: str
    content: str = ""
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str | None = None
    error: str | None = None
    created_at: str
