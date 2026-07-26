from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SupportedTtsLanguage = Literal[
    "en-US",
    "es-US",
    "fr-FR",
    "de-DE",
    "zh-CN",
    "vi-VN",
    "it-IT",
    "hi-IN",
    "ja-JP",
]


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: SupportedTtsLanguage = "en-US"
    voice: str = Field(default="", max_length=180)
    sample_rate_hz: Literal[22050, 44100] = 44100
