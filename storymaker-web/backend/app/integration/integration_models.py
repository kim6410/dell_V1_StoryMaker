# -*- coding: utf-8 -*-
"""Data contracts for the disconnected Gate 4 integration layer."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GenerationMode(str, Enum):
    ONECLICK = "oneclick"
    STAGED = "staged"


class DispatchStatus(str, Enum):
    PREVIEW_ONLY = "preview_only"
    BLOCKED_BY_FLAG = "blocked_by_flag"
    READY_FOR_FUTURE_WIRING = "ready_for_future_wiring"


class DispatcherRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=200)
    project_title: str = Field(..., min_length=1, max_length=200)
    prompt: str = Field(..., min_length=1, max_length=102400)
    generation_mode: GenerationMode = GenerationMode.ONECLICK
    meta_info: dict[str, Any] = Field(default_factory=dict)


class DispatcherResponse(BaseModel):
    ok: bool
    requested_mode: GenerationMode
    selected_mode: GenerationMode | None = None
    status: DispatchStatus
    dispatch_executed: bool = False
    job_id: str | None = None
    reason: str | None = None
