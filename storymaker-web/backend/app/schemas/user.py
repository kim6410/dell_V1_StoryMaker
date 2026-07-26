# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 사용자 및 인증 스키마 모듈 (user.py)
"""
from pydantic import BaseModel
from typing import Optional

class UserLoginRequest(BaseModel):
    """
    로그인 요청 스키마
    """
    username: str
    password: str


class UserResponse(BaseModel):
    """
    사용자 정보 응답 스키마
    """
    id: int
    username: str
    role: str
    tier: str = "free"
    wp_enabled: bool = True
    is_active: bool
    last_login_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    avatar_url: Optional[str] = None
    auth_provider: str = "local"
    created_at: str
    updated_at: str
    project_count: Optional[int] = 0

    class Config:
        from_attributes = True


class UserStatusUpdateRequest(BaseModel):
    """
    사용자 상태(활성/비활성) 수정 요청 스키마
    """
    is_active: bool


class UserRoleUpdateRequest(BaseModel):
    """
    사용자 권한(admin/user) 수정 요청 스키마
    """
    role: str


class UserTierUpdateRequest(BaseModel):
    """
    사용자 등급(free/paid) 수정 요청 스키마
    """
    tier: str


class UserSettingsUpdateRequest(BaseModel):
    """
    사용자 설정 수정 요청 스키마 (워드프레스 켜기/끄기)
    """
    wp_enabled: bool


class TokenResponse(BaseModel):
    """
    인증 완료 토큰 응답 스키마
    """
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserChangePasswordRequest(BaseModel):
    """
    비밀번호 변경 요청 스키마
    """
    current_password: str
    new_password: str


class UserJoinRequest(BaseModel):
    """
    회원가입 요청 스키마
    """
    username: str
    password: str
    invite_code: Optional[str] = None


class GoogleCredentialRequest(BaseModel):
    """Google Identity Services가 반환한 ID 토큰입니다."""
    credential: str
