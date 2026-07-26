# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 업체 페르소나 스키마 모듈 (persona.py)
"""
from pydantic import BaseModel, Field

DEFAULT_PERSONA_TONES = ["따뜻함", "전문가", "친근함", "신뢰감", "현장감", "진정성", "차분함", "활기", "담백함", "순박함", "진지함"]

class PersonaBase(BaseModel):
    """
    페르소나 기본 스키마
    """
    content: str


class PersonaUpdate(PersonaBase):
    """
    페르소나 정보 저장/수정 요청 스키마
    """
    pass


class PersonaResponse(PersonaBase):
    """
    페르소나 정보 응답 스키마
    """
    company_id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UserPersonaUpsert(BaseModel):
    company_name: str = Field(default="", max_length=100)
    phone_number: str = Field(default="", max_length=30)
    website_url: str = Field(default="", max_length=500)
    region: str = Field(default="", max_length=50)
    industry_key: str = Field(default="general", max_length=50)
    default_style: str = Field(default="네이버 블로그", max_length=50)
    blog_content_length: int = Field(default=1500)
    default_tones: list[str] = Field(default_factory=lambda: DEFAULT_PERSONA_TONES.copy())
    keywords: list[str] = Field(default_factory=list)
    content: str = Field(default="", max_length=10000)
