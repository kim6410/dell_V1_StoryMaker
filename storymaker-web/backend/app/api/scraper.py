# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 네이버 블로그 크롤러 API 라우터 (scraper.py)
"""
from fastapi import APIRouter, HTTPException
from app.services.scrape_service import scrape_naver_blog
from app.schemas import BlogScrapeRequest, BlogScrapeResponse, CommonResponse

router = APIRouter()

@router.post("/scrape-blog", response_model=CommonResponse)
def scrape_blog(req: BlogScrapeRequest):
    """
    네이버 블로그 URL을 전달받아 본문 및 제목 텍스트를 크롤링하여 구조화된 DTO 형태로 반환합니다.
    크롤링 실패 시 예외 스택을 던지는 대신 ok=False 응답을 반환하여 프론트엔드의 수동 입력 폴백을 유도합니다.
    """
    try:
        result = scrape_naver_blog(req.url)
        if not result["ok"]:
            return CommonResponse(ok=False, data=None, message=result["error"])
            
        data = BlogScrapeResponse(
            url=req.url,
            title=result["title"],
            text=result["text"]
        )
        return CommonResponse(ok=True, data=data, message="블로그 크롤링이 정상 완료되었습니다.")
    except Exception as e:
        # 500 에러를 뿜는 대신 부드럽게 에러 응답을 감싸서 내려보냄
        return CommonResponse(ok=False, data=None, message=f"크롤러 작동 실패: {str(e)}")
