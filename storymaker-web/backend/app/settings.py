# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 설정 모듈 (settings.py)
Pydantic BaseSettings를 사용하여 환경변수 및 기본 경로들을 안전하게 관리합니다.
"""
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 환경 설정 (development, production)
    STORYMAKER_ENV: str = "development"
    
    # SQLite DB 경로
    STORYMAKER_DB_PATH: str = "/home/bourne/StoryMaker_1/database/storymaker.db"
    
    # 텍스트 페르소나 파일 디렉토리
    STORYMAKER_PERSONA_DIR: str = "/home/bourne/StoryMaker_1/personas"
    
    # 출력 파일 및 내보내기 디렉토리
    STORYMAKER_OUTPUT_DIR: str = "/home/bourne/StoryMaker_1/output_results"
    STORYMAKER_EXPORT_DIR: str = "/home/bourne/StoryMaker_1/exports"
    STORYMAKER_BACKUP_DIR: str = "/home/bourne/StoryMaker_1/backups"
    
    # 관리자 정보 (SaaS 마이그레이션 대비용)
    STORYMAKER_ADMIN_USER: str = ""
    STORYMAKER_ADMIN_PASSWORD: str = ""
    
    # JWT 설정
    STORYMAKER_JWT_SECRET: str = ""
    STORYMAKER_JWT_ALGORITHM: str = "HS256"
    STORYMAKER_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24시간
    
    # Google Identity Services OAuth 클라이언트 ID (미설정 시 Google 로그인 비활성)
    STORYMAKER_GOOGLE_CLIENT_ID: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# 어플리케이션 구동 시 필요한 모든 디렉토리 경로 자동 생성 보장
def ensure_directories():
    db_parent = Path(settings.STORYMAKER_DB_PATH).parent
    db_parent.mkdir(parents=True, exist_ok=True)
    
    Path(settings.STORYMAKER_PERSONA_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.STORYMAKER_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.STORYMAKER_EXPORT_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.STORYMAKER_BACKUP_DIR).mkdir(parents=True, exist_ok=True)

ensure_directories()
