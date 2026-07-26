# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 결과물 및 스크래퍼 스키마 모듈 (result.py)
"""
from pydantic import BaseModel
from typing import Dict

class ResultParseRequest(BaseModel):
    """
    결과물 파싱 요청 규격 스키마
    """
    raw_result: str


class ResultParseResponse(BaseModel):
    """
    결과물 파싱 응답 규격 스키마
    """
    blocks: Dict[str, str]
    cleaned_text: str


class BlogScrapeRequest(BaseModel):
    """
    네이버 블로그 스크래핑 요청 규격 스키마
    """
    url: str


class BlogScrapeResponse(BaseModel):
    """
    네이버 블로그 스크래핑 성공 응답 규격 스키마
    """
    url: str
    title: str
    text: str
