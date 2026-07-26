# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 공통 API 스키마 모듈 (common.py)
"""
from pydantic import BaseModel
from typing import Any, Optional

class CommonResponse(BaseModel):
    """
    백엔드 API의 표준 공통 응답 포맷
    """
    ok: bool = True
    data: Optional[Any] = None
    message: str = ""


class CompanyBase(BaseModel):
    """
    업체 정보 기본 스키마
    """
    name: str


class CompanyCreate(CompanyBase):
    """
    업체 등록 요청 스키마
    """
    pass


class CompanyResponse(CompanyBase):
    """
    업체 정보 응답 스키마
    """
    id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
