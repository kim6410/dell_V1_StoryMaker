# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 보안 및 인증 유틸리티 모듈 (security.py)
비밀번호 Argon2id 해싱 및 레거시 SHA-256 검증, JWT 토큰 관리 기능을 제공합니다.
"""
import hashlib
import hmac
import re

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from datetime import datetime, timedelta
from app.settings import settings


# 신규 비밀번호는 Argon2id로 저장합니다.
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)
_LEGACY_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_LEGACY_PASSWORD_SALT = "storymaker_salt_2026_"


def _legacy_hash_password(password: str) -> str:
    """기존 고정 salt SHA-256 해시 검증 전용. 신규 저장에는 사용하지 않습니다."""
    return hashlib.sha256((_LEGACY_PASSWORD_SALT + password).encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """비밀번호를 Argon2id 해시로 변환합니다."""
    return _PASSWORD_HASHER.hash(password)


def is_legacy_password_hash(hashed_password: str) -> bool:
    """기존 SHA-256 해시 형식인지 확인합니다."""
    return bool(_LEGACY_SHA256_RE.fullmatch(str(hashed_password or "")))


def password_hash_needs_upgrade(hashed_password: str) -> bool:
    """레거시 또는 현재 정책보다 약한 해시인지 확인합니다."""
    value = str(hashed_password or "")
    if is_legacy_password_hash(value):
        return True
    if not value.startswith("$argon2"):
        return True
    try:
        return _PASSWORD_HASHER.check_needs_rehash(value)
    except (InvalidHashError, ValueError):
        return True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Argon2id와 마이그레이션 기간의 기존 SHA-256 해시를 검증합니다."""
    value = str(hashed_password or "")
    if is_legacy_password_hash(value):
        return hmac.compare_digest(_legacy_hash_password(plain_password), value.lower())
    if not value.startswith("$argon2"):
        return False
    try:
        return bool(_PASSWORD_HASHER.verify(value, plain_password))
    except (VerifyMismatchError, VerificationError, InvalidHashError, ValueError):
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """사용자 정보가 담긴 JWT Access Token을 생성합니다."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.STORYMAKER_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.STORYMAKER_JWT_SECRET,
        algorithm=settings.STORYMAKER_JWT_ALGORITHM,
    )
    return encoded_jwt


def verify_access_token(token: str) -> dict | None:
    """JWT Access Token을 검증하고 페이로드를 반환합니다."""
    try:
        payload = jwt.decode(
            token,
            settings.STORYMAKER_JWT_SECRET,
            algorithms=[settings.STORYMAKER_JWT_ALGORITHM],
        )
        return payload
    except jwt.PyJWTError:
        return None
