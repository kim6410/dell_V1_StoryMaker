# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 보안 및 인증 유틸리티 모듈 (security.py)
hashlib을 사용한 안전한 패스워드 해싱 및 pyjwt를 사용한 JWT 토큰 관리 기능을 제공합니다.
"""
import hashlib
import jwt
from datetime import datetime, timedelta
from app.settings import settings

def hash_password(password: str) -> str:
    """
    비밀번호를 SHA-256 해시값으로 변환합니다.
    """
    # 단순 해시 충돌 및 사전 차단을 위해 고정된 salt 추가
    salt = "storymaker_salt_2026_"
    hash_obj = hashlib.sha256((salt + password).encode("utf-8"))
    return hash_obj.hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    입력된 비밀번호가 저장된 해시값과 일치하는지 검증합니다.
    """
    return hash_password(plain_password) == hashed_password


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    사용자 정보가 담긴 JWT Access Token을 생성합니다.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.STORYMAKER_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.STORYMAKER_JWT_SECRET, 
        algorithm=settings.STORYMAKER_JWT_ALGORITHM
    )
    return encoded_jwt


def verify_access_token(token: str) -> dict | None:
    """
    JWT Access Token을 검증하고 페이로드를 복호화하여 반환합니다.
    만료되었거나 손상된 경우 None을 반환합니다.
    """
    try:
        payload = jwt.decode(
            token, 
            settings.STORYMAKER_JWT_SECRET, 
            algorithms=[settings.STORYMAKER_JWT_ALGORITHM]
        )
        return payload
    except jwt.PyJWTError:
        return None
