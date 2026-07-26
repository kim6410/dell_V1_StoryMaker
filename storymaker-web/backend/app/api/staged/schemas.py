# -*- coding: utf-8 -*-
"""
staged API Pydantic 스키마 정의
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class StagedJobCreate(BaseModel):
    project_title: str = Field(..., max_length=200)
    prompt: str = Field(..., max_length=102400)  # 100KB 제한

class StagedJobData(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str

class StagedJobResponse(BaseModel):
    ok: bool = True
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

class StagedWorkerClaimResponse(BaseModel):
    ok: bool = True
    data: Optional[Dict[str, Any]] = None

class StagedWorkerHeartbeat(BaseModel):
    claim_id: str = Field(..., max_length=100)
    worker_id: str = Field(..., max_length=100)

class StagedWorkerComplete(BaseModel):
    claim_id: str = Field(..., max_length=100)
    worker_id: str = Field(..., max_length=100)
    raw_text: str = Field(..., max_length=512000)  # 500KB 제한

class StagedWorkerFail(BaseModel):
    claim_id: str = Field(..., max_length=100)
    worker_id: str = Field(..., max_length=100)
    error_message: str = Field(..., max_length=5000)

class StagedJobCancel(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)
