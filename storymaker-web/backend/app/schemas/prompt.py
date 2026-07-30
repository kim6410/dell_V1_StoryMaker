# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 프롬프트 빌더 스키마 모듈 (prompt.py)
"""
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class PromptRequest(BaseModel):
    """
    프롬프트 생성 요청 규격 스키마
    """
    company: str
    persona: str
    base_content: str
    reference_text: str
    keywords: List[str]
    style: str
    ai_preset: str
    region: Optional[str] = None
    region_alias: Optional[str] = ""
    industry_key: str = "general"
    tones: Optional[List[str]] = None
    blog_content_length: int = 1500
    phone_number: Optional[str] = ""


class PromptResponse(BaseModel):
    """
    프롬프트 생성 결과 응답 스키마
    """
    generated_prompt: str
    timing: Optional[Dict[str, Any]] = None
