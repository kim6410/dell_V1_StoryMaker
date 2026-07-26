# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 블로그 글감 찾기 API 라우터 (content_ideas.py)
"""
from fastapi import APIRouter, HTTPException, Query
from app.services.content_idea_service import search_naver_blog_ideas, extract_naver_blog_idea, analyze_naver_blog_ideas
from app.schemas import CommonResponse

router = APIRouter()

@router.get("/content-ideas/naver-blog/search", response_model=CommonResponse)
def search_blog_ideas(keyword: str = Query(..., description="검색 키워드"), limit: int = Query(5, description="노출 개수")):
    """
    키워드를 기반으로 참고용 네이버 블로그 글감 목록을 반환합니다.
    """
    try:
        result = search_naver_blog_ideas(keyword, limit)
        if not result["ok"]:
            return CommonResponse(ok=False, data=None, message="검색 도중 에러가 발생했습니다.")
        return CommonResponse(ok=True, data=result, message="성공적으로 블로그 글감을 검색했습니다.")
    except Exception as e:
        return CommonResponse(ok=False, data=None, message=f"API 에러: {str(e)}")

@router.get("/content-ideas/naver-blog/extract", response_model=CommonResponse)
def extract_blog_idea(url: str = Query(..., description="네이버 블로그 포스트 주소")):
    """
    개별 블로그 주소를 바탕으로 핵심 내용 요약 및 출처 정보를 추출하여 글감 DTO로 반환합니다.
    """
    try:
        result = extract_naver_blog_idea(url)
        if not result["ok"]:
            return CommonResponse(ok=False, data=None, message="블로그 글감 분석에 실패했습니다.")
        return CommonResponse(ok=True, data=result, message="성공적으로 블로그 글감을 분석했습니다.")
    except Exception as e:
        return CommonResponse(ok=False, data=None, message=f"API 에러: {str(e)}")

@router.get("/content-ideas/naver-blog/analyze", response_model=CommonResponse)
def analyze_blog_ideas(keyword: str = Query(..., description="분석 키워드")):
    """
    네이버 블로그 검색결과의 제목과 스니펫 요약을 분석하여
    주제 빈도, 핵심어, 고민 키워드, 추천 글 방향 및 프롬프트 블록을 생성해 반환합니다.
    """
    try:
        result = analyze_naver_blog_ideas(keyword)
        if not result["ok"]:
            return CommonResponse(ok=False, data=None, message="글감 분석에 실패했습니다.")
        return CommonResponse(ok=True, data=result, message="성공적으로 블로그 글감을 분석했습니다.")
    except Exception as e:
        return CommonResponse(ok=False, data=None, message=f"API 에러: {str(e)}")
