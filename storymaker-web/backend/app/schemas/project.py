# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 프로젝트 스키마 모듈 (project.py)
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ProjectBase(BaseModel):
    title: str
    company_id: int
    base_content: Optional[str] = None
    reference_text: Optional[str] = None
    keywords: Optional[List[str]] = None
    style: Optional[str] = None
    ai_preset: Optional[str] = None
    generated_prompt: Optional[str] = None
    raw_result: Optional[str] = None
    parsed_result_json: Optional[Dict[str, str]] = None


class ProjectCreate(ProjectBase):
    """
    프로젝트 생성 요청 스키마
    """
    pass


class ProjectUpdate(BaseModel):
    """
    프로젝트 업데이트 요청 스키마 (모든 필드 선택 가능)
    """
    title: Optional[str] = None
    company_id: Optional[int] = None
    base_content: Optional[str] = None
    reference_text: Optional[str] = None
    keywords: Optional[List[str]] = None
    style: Optional[str] = None
    ai_preset: Optional[str] = None
    generated_prompt: Optional[str] = None
    raw_result: Optional[str] = None
    parsed_result_json: Optional[Dict[str, str]] = None


class ProjectResponse(ProjectBase):
    """
    프로젝트 응답 스키마
    """
    id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ProjectBriefResponse(BaseModel):
    """
    프로젝트 목록 조회용 경량 응답 스키마
    """
    id: int
    company_id: int
    title: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
