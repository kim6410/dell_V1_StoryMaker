# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 데이터베이스 ORM 모델 정의 모듈 (models.py)
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, UniqueConstraint, Float
from sqlalchemy.orm import relationship
from app.db.database import Base

class Company(Base):
    """
    업체 정보 테이블 모델 (companies)
    """
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(String(20), nullable=False)
    updated_at = Column(String(20), nullable=False)

    # 1:1 역참조 관계 설정 (외래 키가 있는 쪽이 child, Company가 parent)
    persona = relationship("Persona", back_populates="company", uselist=False, cascade="all, delete-orphan")
    # 1:N 관계 설정 (업체 삭제 시 하위 프로젝트 처리: Set NULL 또는 연쇄 삭제)
    projects = relationship("Project", back_populates="company", cascade="all, delete-orphan")


class Persona(Base):
    """
    업체 페르소나 설명 테이블 모델 (personas)
    """
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(String(20), nullable=False)
    updated_at = Column(String(20), nullable=False)

    company = relationship("Company", back_populates="persona")


class User(Base):
    """
    사용자 정보 테이블 모델 (users)
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)  # admin, user 등
    tier = Column(String(20), default="free", nullable=False)  # free, paid 등
    wp_enabled = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(String(20), nullable=True)
    last_activity_at = Column(String(20), nullable=True)
    google_sub = Column(Text, unique=True, nullable=True)
    wordpress_user_id = Column(Integer, unique=True, nullable=True)
    avatar_url = Column(Text, nullable=True)
    auth_provider = Column(Text, default="local", nullable=False)
    created_at = Column(String(20), nullable=False)
    updated_at = Column(String(20), nullable=False)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
    personas = relationship("UserPersona", back_populates="user", cascade="all, delete-orphan")
    feature_requests = relationship("FeatureRequest", back_populates="user", cascade="all, delete-orphan")
    podcast_voice_setting = relationship("UserPodcastVoiceSetting", back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserPodcastVoiceSetting(Base):
    """사용자별 팟캐스트 목소리 선택 설정과 Shuffle Bag 상태입니다."""
    __tablename__ = "user_podcast_voice_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    male_voice = Column(String(10), nullable=True)
    female_voice = Column(String(10), nullable=True)
    male_bag_json = Column(Text, default="[]", nullable=False)
    female_bag_json = Column(Text, default="[]", nullable=False)
    created_at = Column(String(20), nullable=False)
    updated_at = Column(String(20), nullable=False)

    user = relationship("User", back_populates="podcast_voice_setting")


class UserPersona(Base):
    """마이페이지에서 관리하는 사용자별 업체 페르소나입니다."""
    __tablename__ = "user_personas"
    __table_args__ = (UniqueConstraint("user_id", "company_name", name="uq_user_persona_company"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_name = Column(String(100), nullable=False)
    phone_number = Column(String(30), nullable=False)
    website_url = Column(Text, default="", nullable=False)
    region = Column(String(100), default="", nullable=False)
    region_alias = Column(String(100), default="", nullable=False)
    industry_key = Column(String(50), default="general", nullable=False)
    default_style = Column(String(50), default="네이버 블로그", nullable=False)
    blog_content_length = Column(Integer, default=1500, nullable=False)
    default_tones_json = Column(Text, default="[]", nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    keywords_json = Column(Text, default="[]", nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(String(20), nullable=False)
    updated_at = Column(String(20), nullable=False)

    user = relationship("User", back_populates="personas")



class RegionOption(Base):
    """마이페이지 지역 선택 목록입니다."""
    __tablename__ = "region_options"
    __table_args__ = (UniqueConstraint("name", name="uq_region_options_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, index=True)
    parent_name = Column(String(50), default="", nullable=False)
    region_type = Column(String(20), default="province", nullable=False)  # province, metro, city, special
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(String(20), nullable=False)
    updated_at = Column(String(20), nullable=False)


class UserSession(Base):
    """
    사용자 접속 세션 정보 테이블 모델 (user_sessions)
    """
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    login_at = Column(String(20), nullable=False)
    logout_at = Column(String(20), nullable=True)
    last_seen_at = Column(String(20), nullable=False)
    duration_seconds = Column(Integer, default=0, nullable=False)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(String(20), nullable=False)

    user = relationship("User", back_populates="sessions")


class ActivityLog(Base):
    """
    사용자 활동 로그 테이블 모델 (activity_logs)
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True) # 비로그인 조인 등
    action = Column(String(50), nullable=False) # login, logout, project_create 등
    target_type = Column(String(50), nullable=True) # project, persona, company 등
    target_id = Column(Integer, nullable=True)
    metadata_json = Column(Text, nullable=True) # 액션별 상세 부가 정보 JSON화
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(String(20), nullable=False)

    user = relationship("User", back_populates="activity_logs")


class FeatureRequest(Base):
    """사용자가 상단 수정요청 버튼으로 남긴 개선 요청 게시판입니다."""
    __tablename__ = "feature_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), default="접수", nullable=False)
    admin_note = Column(Text, nullable=True)
    created_at = Column(String(20), nullable=False)
    updated_at = Column(String(20), nullable=False)

    user = relationship("User", back_populates="feature_requests")


class WeatherSnapshot(Base):
    """지역별 시간 단위 날씨 원본 저장 테이블입니다."""
    __tablename__ = "weather_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String(50), nullable=False, index=True)
    weather = Column(String(50), nullable=False)
    temperature = Column(Float, nullable=True)
    source = Column(String(50), default="prompt_builder", nullable=False)
    observed_at = Column(String(20), nullable=False, index=True)
    created_at = Column(String(20), nullable=False)


class WeatherDailySummary(Base):
    """지역별 날짜 단위 날씨 요약 저장 테이블입니다."""
    __tablename__ = "weather_daily_summaries"
    __table_args__ = (UniqueConstraint("region", "date", name="uq_weather_daily_region_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String(50), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)
    avg_temp = Column(Float, nullable=True)
    min_temp = Column(Float, nullable=True)
    max_temp = Column(Float, nullable=True)
    dominant_weather = Column(String(50), nullable=True)
    summary_text = Column(Text, nullable=True)
    created_at = Column(String(20), nullable=False)


class IndustryPromptTemplate(Base):
    """관리자 화면에서 수정 가능한 업종별 프롬프트 템플릿입니다."""
    __tablename__ = "industry_prompt_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    industry_key = Column(String(50), unique=True, index=True, nullable=False)
    label = Column(String(100), nullable=False)
    category = Column(String(100), default="기타", nullable=False)
    prompt_guidance = Column(Text, default="", nullable=False)
    content_flow = Column(Text, default="", nullable=False)
    keyword_hint = Column(Text, default="", nullable=False)
    tone_hint = Column(Text, default="", nullable=False)
    avoid_hint = Column(Text, default="", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(String(20), nullable=False)
    updated_at = Column(String(20), nullable=False)


class Project(Base):
    """
    마케팅 프로젝트 정보 테이블 모델 (projects)
    기초 정보, 생성 프롬프트, 13개 채널 결과 원문 및 파싱 결과를 통합 보관합니다.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # 하위 호환성을 위해 nullable=True로 유지
    title = Column(String(255), nullable=False)
    base_content = Column(Text, nullable=True)
    reference_text = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)             # 키워드 리스트를 JSON 포맷의 문자열로 저장
    style = Column(String(50), nullable=True)
    ai_preset = Column(String(50), nullable=True)
    generated_prompt = Column(Text, nullable=True)
    raw_result = Column(Text, nullable=True)
    parsed_result_json = Column(Text, nullable=True)    # 13개 채널별 파싱 데이터 dict를 JSON 포맷의 문자열로 저장
    created_at = Column(String(20), nullable=False)
    updated_at = Column(String(20), nullable=False)

    company = relationship("Company", back_populates="projects")
    user = relationship("User", back_populates="projects")
