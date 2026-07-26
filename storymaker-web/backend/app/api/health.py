# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 헬스 체크 API 라우터 (health.py)
"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def get_health():
    """
    서버 헬스 상태 확인 엔드포인트
    """
    return {
        "status": "ok",
        "service": "storymaker-web"
    }
