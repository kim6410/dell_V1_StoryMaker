# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 키워드 추출 API 라우터 (keywords.py)
"""
from fastapi import APIRouter, HTTPException
from app.services import StoryMakerService
from app.schemas import KeywordExtractRequest, KeywordExtractResponse, CommonResponse

router = APIRouter()

@router.post("/extract-keywords", response_model=CommonResponse)
def extract_keywords(req: KeywordExtractRequest):
    """
    제공된 여러 텍스트 자원을 형태소 및 빈도수 기반 분석하여
    블랙리스트 필터링이 완료된 최적의 SEO 추천 키워드 리스트를 반환합니다.
    """
    try:
        keywords = StoryMakerService.extract_keywords(req)
        data = KeywordExtractResponse(keywords=keywords)
        return CommonResponse(ok=True, data=data, message="연관 키워드가 성공적으로 추출되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
