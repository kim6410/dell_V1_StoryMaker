# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 API 라우터 패키지 초기화
"""

from .health import router as health_router
from .companies import router as companies_router
from .personas import router as personas_router
from .prompts import router as prompts_router
from .results import router as results_router
from .keywords import router as keywords_router
from .projects import router as projects_router
from .scraper import router as scraper_router
from .auth import router as auth_router
from .admin import router as admin_router
from .admin_members import router as admin_members_router
from .admin_deploy import router as deploy_router
admin_router.include_router(deploy_router)
from .feature_requests import router as feature_requests_router
from .wordpress import router as wordpress_router
from .content_ideas import router as content_ideas_router
from .pattern_knowledge import router as pattern_knowledge_router
from .content_performance import router as content_performance_router
from .ai_brain import router as ai_brain_router
from .assets import router as assets_router
from .industry_presets import router as industry_presets_router
from .mobile_one_shot import router as mobile_one_shot_router
from .content_board import router as content_board_router
from .local_exports import router as local_exports_router
from .admin_deploy import router as deploy_router

__all__ = [
    "health_router",
    "companies_router",
    "personas_router",
    "prompts_router",
    "results_router",
    "keywords_router",
    "projects_router",
    "scraper_router",
    "auth_router",
    "admin_router",
    "admin_members_router",
    "wordpress_router",
    "content_ideas_router",
    "pattern_knowledge_router",
    "content_performance_router",
    "ai_brain_router",
    "assets_router",
    "industry_presets_router",
    "mobile_one_shot_router",
    "content_board_router",
    "local_exports_router"
]
