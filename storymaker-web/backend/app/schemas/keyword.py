# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 키워드 추출 스키마 모듈 (keyword.py)
"""
from pydantic import BaseModel
from typing import List, Tuple, Any

class KeywordExtractRequest(BaseModel):
    """
    키워드 추출 요청 규격 스키마
    """
    texts: List[str]


class KeywordExtractResponse(BaseModel):
    """
    키워드 추출 응답 규격 스키마
    """
    keywords: List[Any]  # [(키워드, 빈도수), ...] 구조가 직렬화된 형태
