# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 사용자 인증 API 라우터 및 의존성 주입 모듈 (auth.py)
"""
from fastapi import APIRouter, Depends, HTTPException, Security, status, Request, Response, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime
import json
import secrets
import os
import time
import hashlib
import ipaddress
import threading
from collections import defaultdict, deque
from typing import Optional
from pydantic import BaseModel
import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from app.db.database import get_db
from app.db.repositories import get_user_by_username, create_user
from app.db.models import User, UserSession, ActivityLog, UserPersona, IndustryPromptTemplate, RegionOption
from app.core.security import verify_password, create_access_token, verify_access_token, hash_password
from app.core.region_display import format_region_display, normalize_region_search_text
from app.schemas import CommonResponse
from app.schemas.user import (
    GoogleCredentialRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    UserChangePasswordRequest,
    UserJoinRequest,
    UserSettingsUpdateRequest,
)
from app.settings import settings

router = APIRouter()
security_scheme = HTTPBearer(auto_error=False)


AUTH_COOKIE_NAME = "storymaker_token"
AUTH_COOKIE_DOMAIN = ".mystorymaker.net"
LOCAL_CONNECT_TTL_SECONDS = 300
_LOCAL_CONNECT_CODES: dict[str, dict] = {}

LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 5 * 60
PASSWORD_RESET_LIMIT = 3
PASSWORD_RESET_WINDOW_SECONDS = 15 * 60
_RATE_LIMIT_EVENTS: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = threading.Lock()
_TRUSTED_PROXY_PEERS = {"127.0.0.1", "::1", "172.27.0.1", "192.168.0.32"}


def _client_ip(request: Request) -> str:
    """직접 접속 IP를 기본으로 사용하고, 지정된 프록시를 거친 경우에만 X-Forwarded-For를 신뢰합니다."""
    peer_ip = request.client.host if request.client else "127.0.0.1"
    if peer_ip not in _TRUSTED_PROXY_PEERS:
        return peer_ip

    forwarded_for = request.headers.get("x-forwarded-for", "")
    for candidate in forwarded_for.split(","):
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return peer_ip


def _rate_subject(value: str) -> str:
    normalized = (value or "").strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _prune_rate_events(events: deque[float], now: float, window_seconds: int) -> None:
    cutoff = now - window_seconds
    while events and events[0] <= cutoff:
        events.popleft()


def _check_rate_limit(scope: str, keys: list[str], limit: int, window_seconds: int) -> None:
    now = time.time()
    retry_after = 1
    with _RATE_LIMIT_LOCK:
        for key in keys:
            events = _RATE_LIMIT_EVENTS[(scope, key)]
            _prune_rate_events(events, now, window_seconds)
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                    headers={"Retry-After": str(retry_after)},
                )


def _record_rate_event(scope: str, keys: list[str], window_seconds: int) -> None:
    now = time.time()
    with _RATE_LIMIT_LOCK:
        for key in keys:
            events = _RATE_LIMIT_EVENTS[(scope, key)]
            _prune_rate_events(events, now, window_seconds)
            events.append(now)


def _clear_rate_events(scope: str, keys: list[str]) -> None:
    with _RATE_LIMIT_LOCK:
        for key in keys:
            _RATE_LIMIT_EVENTS.pop((scope, key), None)


def _consume_rate_limit(scope: str, keys: list[str], limit: int, window_seconds: int) -> None:
    _check_rate_limit(scope, keys, limit, window_seconds)
    _record_rate_event(scope, keys, window_seconds)


class LocalConnectStartRequest(BaseModel):
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    scope: Optional[str] = "local_worker"


class LocalConnectExchangeRequest(BaseModel):
    code: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None


def _cleanup_local_connect_codes() -> None:
    now = time.time()
    expired = [code for code, item in _LOCAL_CONNECT_CODES.items() if float(item.get("expires_at", 0)) < now or item.get("used")]
    for code in expired:
        _LOCAL_CONNECT_CODES.pop(code, None)


def _auth_cookie_scope(request: Request | None) -> tuple[str | None, bool]:
    """공개 HTTPS와 V1 로컬 접속 환경에 맞는 쿠키 범위를 반환합니다."""
    if request is None:
        return AUTH_COOKIE_DOMAIN, True
    hostname = str(request.url.hostname or "").strip().lower()
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    scheme = forwarded_proto or str(request.url.scheme or "").lower()
    is_public_domain = hostname == "mystorymaker.net" or hostname.endswith(".mystorymaker.net")
    return (AUTH_COOKIE_DOMAIN if is_public_domain else None), scheme == "https"


def _set_auth_cookie(response: Response, token: str, request: Request | None = None) -> None:
    domain, secure = _auth_cookie_scope(request)
    cookie_options = {
        "key": AUTH_COOKIE_NAME,
        "value": token,
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
        "max_age": 60 * 60 * 24 * 7,
        "path": "/",
    }
    if domain:
        cookie_options["domain"] = domain
    response.set_cookie(**cookie_options)


def _clear_auth_cookie(response: Response, request: Request | None = None) -> None:
    domain, secure = _auth_cookie_scope(request)
    cookie_options = {
        "key": AUTH_COOKIE_NAME,
        "path": "/",
        "httponly": True,
        "secure": secure,
        "samesite": "lax",
    }
    if domain:
        cookie_options["domain"] = domain
    response.delete_cookie(**cookie_options)



def _issue_login_response(user: User, request: Request, db: Session, response: Response, action: str = "login") -> CommonResponse:
    """로컬/Google 로그인에 공통인 세션 기록과 JWT 발급을 수행합니다."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비활성화된 계정입니다. 관리자에게 문의하세요."
        )

    ip_addr = request.client.host if request.client else "127.0.0.1"
    user_agt = request.headers.get("user-agent", "Unknown")
    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user.last_login_at = now_stamp
    user.last_activity_at = now_stamp

    session = UserSession(
        user_id=user.id,
        login_at=now_stamp,
        last_seen_at=now_stamp,
        duration_seconds=0,
        ip_address=ip_addr,
        user_agent=user_agt,
        created_at=now_stamp
    )
    db.add(session)
    db.flush()
    db.add(ActivityLog(
        user_id=user.id,
        action=action,
        target_type="user",
        target_id=user.id,
        metadata_json=None,
        ip_address=ip_addr,
        user_agent=user_agt,
        created_at=now_stamp
    ))
    db.commit()
    db.refresh(user)
    db.refresh(session)

    access_token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "session_id": session.id
    })
    _set_auth_cookie(response, access_token, request)
    user_resp = UserResponse.model_validate(user)
    user_resp.project_count = len(user.projects)
    token_resp = TokenResponse(access_token=access_token, user=user_resp)
    return CommonResponse(ok=True, data=token_resp.model_dump(), message="로그인에 성공하였습니다.")

def get_current_user(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),
    storymaker_token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    db: Session = Depends(get_db)
) -> User:
    """
    HTTP Bearer 토큰을 파싱하여 현재 로그인된 유저를 확인하는 의존성 주입용 함수입니다.
    비활성화된(is_active=False) 유저는 접근을 즉시 거부하며, 성공 시 활동 일시(last_activity_at)를 실시간 갱신합니다.
    추가로 접속 시간(duration)과 마지막 활동 시각(last_seen_at)을 실시간 추정/업데이트합니다.
    """
    token = credentials.credentials if credentials else storymaker_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요한 서비스입니다."
        )
    payload = verify_access_token(token)
    if not payload or "username" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 유효하지 않거나 만료되었습니다."
        )
        
    if credentials and not storymaker_token:
        _set_auth_cookie(response, token, request)

    username = payload["username"]
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자 계정입니다."
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비활성화된 계정입니다. 관리자에게 문의하세요."
        )
        
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # session_id는 모든 인증 토큰의 필수 클레임이다.
    # 세션 레코드가 없거나 로그아웃된 토큰은 즉시 거부한다.
    session_id = payload.get("session_id")
    if not session_id:
        _clear_auth_cookie(response, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session-bound authentication token is required."
        )
    session_rec = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session_rec or session_rec.logout_at:
        _clear_auth_cookie(response, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Logged out or expired session."
        )
    session_rec.last_seen_at = now_str
    try:
        login_dt = datetime.strptime(session_rec.login_at, "%Y-%m-%d %H:%M:%S")
        diff = datetime.now() - login_dt
        session_rec.duration_seconds = max(0, int(diff.total_seconds()))
    except Exception:
        pass
        
    # 인증 API 호출 시 실시간 활동 시간 기록
    user.last_activity_at = now_str
    db.commit()
    db.refresh(user)
    
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),
    storymaker_token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    db: Session = Depends(get_db)
) -> User | None:
    """
    비회원 허용 API에서 사용하는 선택 인증 의존성입니다.
    토큰이 없거나 유효하지 않으면 예외를 던지지 않고 None을 반환합니다.
    토큰이 정상인 경우에는 로그인 사용자 정보를 반환하고 활동 시각을 갱신합니다.
    """
    token = credentials.credentials if credentials else storymaker_token
    if not token:
        return None

    payload = verify_access_token(token)
    if not payload or "username" not in payload:
        return None

    user = get_user_by_username(db, payload["username"])
    if not user or not user.is_active:
        return None

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session_id = payload.get("session_id")
    if not session_id:
        return None
    session_rec = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session_rec or session_rec.logout_at:
        return None
    session_rec.last_seen_at = now_str
    try:
        login_dt = datetime.strptime(session_rec.login_at, "%Y-%m-%d %H:%M:%S")
        diff = datetime.now() - login_dt
        session_rec.duration_seconds = max(0, int(diff.total_seconds()))
    except Exception:
        pass

    user.last_activity_at = now_str
    db.commit()
    db.refresh(user)
    return user



def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    현재 사용자가 관리자(admin)인지 확인하는 의존성 주입용 함수입니다.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 작업을 수행할 권한이 없습니다. (관리자 전용)"
        )
    return current_user


@router.post("/auth/local-connect/start", response_model=CommonResponse)
def start_local_worker_connect(
    req: LocalConnectStartRequest,
    current_user: User = Depends(get_current_user),
):
    """로그인된 웹 사용자가 Local Worker 연결을 시작할 때 1회용 코드를 발급합니다."""
    _cleanup_local_connect_codes()
    code = secrets.token_urlsafe(32)
    now = time.time()
    device_id = (req.device_id or "").strip()[:80]
    device_name = (req.device_name or "").strip()[:120]
    scope = (req.scope or "local_worker").strip()[:40]
    _LOCAL_CONNECT_CODES[code] = {
        "user_id": current_user.id,
        "username": current_user.username,
        "device_id": device_id,
        "device_name": device_name,
        "scope": scope,
        "created_at": now,
        "expires_at": now + LOCAL_CONNECT_TTL_SECONDS,
        "used": False,
    }
    return CommonResponse(
        ok=True,
        data={
            "code": code,
            "expires_in": LOCAL_CONNECT_TTL_SECONDS,
            "open_url": f"storymaker-local://auth?code={code}",
            "scope": scope,
        },
        message="Local Worker 연결 코드가 발급되었습니다.",
    )


@router.post("/auth/local-exchange", response_model=CommonResponse)
def exchange_local_worker_code(
    req: LocalConnectExchangeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Local Worker가 1회용 연결 코드를 서버 토큰으로 교환합니다."""
    _cleanup_local_connect_codes()
    code = (req.code or "").strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="연결 코드가 필요합니다.")
    item = _LOCAL_CONNECT_CODES.pop(code, None)
    if not item or float(item.get("expires_at", 0)) < time.time() or item.get("used"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="연결 코드가 만료되었거나 유효하지 않습니다.")
    user = db.query(User).filter(User.id == int(item["user_id"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자 계정을 확인할 수 없습니다.")

    ip_addr = request.client.host if request.client else "127.0.0.1"
    user_agt = request.headers.get("user-agent", "StoryMakerLocal")
    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user.last_login_at = now_stamp
    user.last_activity_at = now_stamp
    session = UserSession(
        user_id=user.id,
        login_at=now_stamp,
        last_seen_at=now_stamp,
        duration_seconds=0,
        ip_address=ip_addr,
        user_agent=f"LocalWorker {user_agt}"[:255],
        created_at=now_stamp,
    )
    db.add(session)
    db.flush()
    db.add(ActivityLog(
        user_id=user.id,
        action="local_worker_connect",
        target_type="user",
        target_id=user.id,
        metadata_json=json.dumps({
            "device_id": (req.device_id or item.get("device_id") or "")[:80],
            "device_name": (req.device_name or item.get("device_name") or "")[:120],
            "scope": item.get("scope") or "local_worker",
        }, ensure_ascii=False),
        ip_address=ip_addr,
        user_agent=user_agt,
        created_at=now_stamp,
    ))
    db.commit()
    db.refresh(user)
    db.refresh(session)

    access_token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "session_id": session.id,
        "client": "local_worker",
    })
    user_resp = UserResponse.model_validate(user)
    user_resp.project_count = len(user.projects)
    return CommonResponse(
        ok=True,
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_resp.model_dump(),
            "session_id": session.id,
            "scope": item.get("scope") or "local_worker",
        },
        message="Local Worker 연결이 완료되었습니다.",
    )


@router.post("/auth/login", response_model=CommonResponse)
def login(req: UserLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """
    아이디와 비밀번호를 검증하고 JWT 액세스 토큰을 발급하며, user_sessions 세션 개설 및 활동 로그를 기록합니다.
    일반 회원은 WordPress REST API를 통해 인증하고, guest 계정은 로컬에서 즉시 인증을 유지합니다.
    """
    username = req.username.strip()
    client_ip = _client_ip(request)
    login_rate_keys = [f"ip:{client_ip}", f"account:{_rate_subject(username)}"]
    _check_rate_limit(
        "login_failure",
        login_rate_keys,
        LOGIN_FAILURE_LIMIT,
        LOGIN_FAILURE_WINDOW_SECONDS,
    )
    
    # 1. Guest 로그인 처리
    if username == "guest" and req.password == username:
        user = get_user_by_username(db, username)
        if not user:
            user = create_user(db, username, username, role="user")
            user.wp_enabled = False
            db.commit()
            db.refresh(user)
        _clear_rate_events("login_failure", login_rate_keys)
        return _issue_login_response(user, request, db, response)

    # 2. WordPress 로그인 처리
    wp_api_url = os.getenv("WORDPRESS_API_URL", "https://mystorymaker.net/wp-json/wp/v2").rstrip("/")
    wp_base = wp_api_url.split('/wp-json/')[0] if '/wp-json/' in wp_api_url else "https://mystorymaker.net"
    wp_login_url = f"{wp_base}/wp-json/storymaker/v1/login"

    try:
        with httpx.Client(timeout=10) as client:
            wp_resp = client.post(wp_login_url, json={
                "username": username,
                "password": req.password
            })
            if wp_resp.status_code != 200:
                _record_rate_event(
                    "login_failure",
                    login_rate_keys,
                    LOGIN_FAILURE_WINDOW_SECONDS,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="아이디 또는 비밀번호가 일치하지 않습니다."
                )
            wp_data = wp_resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"WordPress 인증 서버와 통신할 수 없습니다: {exc}"
        )

    wp_user_id = wp_data.get("user_id")
    wp_username = wp_data.get("username", username)
    wp_roles = wp_data.get("roles", [])

    if not wp_user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WordPress 인증 응답이 올바르지 않습니다."
        )

    # wordpress_user_id 기준으로 사용자 조회
    user = db.query(User).filter(User.wordpress_user_id == wp_user_id).first()
    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_role = "admin" if "administrator" in wp_roles else "user"

    if not user:
        # 하위 호환성: 기존에 동일한 username의 로컬 계정이 있었는지 확인
        user = get_user_by_username(db, wp_username)
        if user:
            user.wordpress_user_id = wp_user_id
            user.auth_provider = "wordpress"
            user.role = target_role
            user.updated_at = now_stamp
        else:
            # 동적으로 신규 회원 레코드 생성
            user = User(
                username=wp_username,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                role=target_role,
                tier="free",
                wp_enabled=True,
                is_active=True,
                wordpress_user_id=wp_user_id,
                auth_provider="wordpress",
                created_at=now_stamp,
                updated_at=now_stamp
            )
            db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # WordPress 계정정보(username, role) 변경에 대응해 동기화 처리
        user.username = wp_username
        user.role = target_role
        user.updated_at = now_stamp
        db.commit()
        db.refresh(user)

    _clear_rate_events("login_failure", login_rate_keys)
    return _issue_login_response(user, request, db, response)


@router.get("/auth/google/config", response_model=CommonResponse)
def google_login_config():
    """프런트엔드에 공개 가능한 GIS 클라이언트 설정 상태를 반환합니다."""
    client_id = settings.STORYMAKER_GOOGLE_CLIENT_ID.strip()
    return CommonResponse(
        ok=True,
        data={"enabled": bool(client_id), "client_id": client_id or None},
        message=""
    )


@router.post("/auth/google", response_model=CommonResponse)
def google_login(req: GoogleCredentialRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Google ID 토큰을 검증하고 기존 계정을 연결하거나 신규 계정을 생성합니다."""
    client_id = settings.STORYMAKER_GOOGLE_CLIENT_ID.strip()
    if not client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google 로그인이 설정되지 않았습니다.")

    try:
        claims = google_id_token.verify_oauth2_token(
            req.credential,
            google_requests.Request(),
            client_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 Google 인증 토큰입니다.") from exc

    google_sub = str(claims.get("sub", "")).strip()
    email = str(claims.get("email", "")).strip().lower()
    name = str(claims.get("name", "")).strip()
    picture = str(claims.get("picture", "")).strip() or None
    if not google_sub or not email or claims.get("email_verified") is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="확인된 이메일을 가진 Google 계정이 필요합니다.")

    user = db.query(User).filter(User.google_sub == google_sub).first()
    if not user:
        # 기존 StoryMaker에는 email 컬럼이 없으므로 username이 이메일인 계정을 연결 대상으로 봅니다.
        user = db.query(User).filter(User.username.ilike(email)).first()
        if user and user.google_sub and user.google_sub != google_sub:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이 이메일은 다른 Google 계정에 연결되어 있습니다.")

    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if user:
        user.google_sub = google_sub
        user.avatar_url = picture
        user.auth_provider = "google" if user.auth_provider != "local" else "local+google"
        user.updated_at = now_stamp
    else:
        user = User(
            username=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="user",
            is_active=True,
            google_sub=google_sub,
            avatar_url=picture,
            auth_provider="google",
            created_at=now_stamp,
            updated_at=now_stamp
        )
        db.add(user)
    db.commit()
    db.refresh(user)

    response = _issue_login_response(user, request, db, response, action="google_login")
    if response.data and name:
        response.data["google_profile"] = {"name": name, "email": email, "picture": picture}
    return response


@router.get("/auth/me", response_model=CommonResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    현재 로그인된 사용자의 상세 정보를 반환합니다.
    """
    user_resp = UserResponse.model_validate(current_user)
    user_resp.project_count = len(current_user.projects)
    return CommonResponse(ok=True, data=user_resp.model_dump(), message="")


@router.post("/auth/join", response_model=CommonResponse)
def join(req: UserJoinRequest, request: Request, db: Session = Depends(get_db)):
    """
    회원가입 요청을 처리하던 라우터였으나, WordPress 연동 개편에 따라 호출이 원천 차단됩니다.
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="회원가입은 WordPress를 통해서만 가능합니다. 해당 페이지로 이동하여 진행해 주세요."
    )


class PasswordResetRequest(BaseModel):
    login: str


@router.post("/auth/password-reset-request", response_model=CommonResponse)
def request_password_reset(req: PasswordResetRequest, request: Request):
    """WordPress 코어를 통해 비밀번호 재설정 메일 발송을 요청합니다."""
    login = (req.login or "").strip()
    if not login:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이메일 또는 사용자명을 입력해 주세요.",
        )

    client_ip = _client_ip(request)
    reset_rate_keys = [f"ip:{client_ip}", f"account:{_rate_subject(login)}"]
    _consume_rate_limit(
        "password_reset_request",
        reset_rate_keys,
        PASSWORD_RESET_LIMIT,
        PASSWORD_RESET_WINDOW_SECONDS,
    )

    wp_api_url = os.getenv("WORDPRESS_API_URL", "https://mystorymaker.net/wp-json/wp/v2").rstrip("/")
    wp_base = wp_api_url.split("/wp-json/")[0] if "/wp-json/" in wp_api_url else "https://mystorymaker.net"
    lost_url = f"{wp_base}/wp-login.php?action=lostpassword"

    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            client.get(lost_url)
            wp_response = client.post(
                lost_url,
                data={
                    "user_login": login,
                    "redirect_to": "",
                    "wp-submit": "새 비밀번호 얻기",
                },
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="비밀번호 재설정 메일 서버에 연결할 수 없습니다.",
        ) from exc

    body_text = wp_response.text or ""
    mail_failure_markers = (
        "이메일을 보낼 수 없습니다",
        "The email could not be sent",
        "wp_mail_failed",
    )
    if wp_response.status_code >= 500 or any(marker in body_text for marker in mail_failure_markers):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="비밀번호 재설정 메일을 발송하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        )

    return CommonResponse(
        ok=True,
        data=None,
        message="입력한 정보와 일치하는 계정이 있으면 비밀번호 재설정 메일을 발송했습니다. 메일함과 스팸함을 확인해 주세요.",
    )


@router.put("/auth/change-password", response_model=CommonResponse)
def change_password(
    req: UserChangePasswordRequest, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    현재 로그인된 유저의 비밀번호를 변경하고 비밀번호 변경 활동 로그를 기록합니다.
    """
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 일치하지 않습니다."
        )
        
    current_user.password_hash = hash_password(req.new_password)
    db.commit()
    db.refresh(current_user)
    
    # 비밀번호 변경 활동 로그 기록
    ip_addr = request.client.host if request.client else "127.0.0.1"
    user_agt = request.headers.get("user-agent", "Unknown")
    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    act_log = ActivityLog(
        user_id=current_user.id,
        action="password_change",
        target_type="user",
        target_id=current_user.id,
        metadata_json=None,
        ip_address=ip_addr,
        user_agent=user_agt,
        created_at=now_stamp
    )
    db.add(act_log)
    db.commit()
    
    return CommonResponse(ok=True, data=None, message="비밀번호가 안전하게 변경되었습니다. 다시 로그인해 주세요.")


@router.post("/auth/logout", response_model=CommonResponse)
def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    사용자 세션을 명시적으로 만료시키고 로그아웃 처리를 수행하며 사용시간을 최종 계산하여 활동 로그에 저장합니다.
    """
    token = credentials.credentials if credentials else request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        _clear_auth_cookie(response, request)
        return CommonResponse(ok=True, data=None, message="이미 로그아웃된 상태입니다.")

    payload = verify_access_token(token)
    
    ip_addr = request.client.host if request.client else "127.0.0.1"
    user_agt = request.headers.get("user-agent", "Unknown")
    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if payload and "session_id" in payload:
        session_id = payload["session_id"]
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if session and not session.logout_at:
            session.logout_at = now_stamp
            session.last_seen_at = now_stamp
            
            # 최종 사용시간(duration) 계산
            try:
                login_dt = datetime.strptime(session.login_at, "%Y-%m-%d %H:%M:%S")
                diff = datetime.now() - login_dt
                session.duration_seconds = max(0, int(diff.total_seconds()))
            except Exception:
                pass
            db.commit()
            
    # 로그아웃 활동 로그 기록
    act_log = ActivityLog(
        user_id=current_user.id,
        action="logout",
        target_type="user",
        target_id=current_user.id,
        metadata_json=None,
        ip_address=ip_addr,
        user_agent=user_agt,
        created_at=now_stamp
    )
    db.add(act_log)
    db.commit()
    
    _clear_auth_cookie(response, request)
    return CommonResponse(ok=True, data=None, message="안전하게 로그아웃되었습니다.")


from pydantic import BaseModel
from typing import Optional

class ActivityLogCreateRequest(BaseModel):
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    metadata_json: Optional[str] = None

@router.post("/activity-log", response_model=CommonResponse)
def create_activity_log(
    req: ActivityLogCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    프론트엔드 액션(미리보기 열기, HTML 복사, 외부 플랫폼 바로가기 등)에 대한 사용자 활동 로그를 데이터베이스에 안전하게 수집합니다.
    """
    try:
        ip_addr = request.client.host if request.client else "127.0.0.1"
        user_agt = request.headers.get("user-agent", "Unknown")
        now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 보안 방어: 민감 데이터가 유입될 수 있는 액션은 메타데이터 강제 초기화
        clean_metadata = req.metadata_json
        if req.action in ["password_change", "login", "join"]:
            clean_metadata = None
            
        act_log = ActivityLog(
            user_id=current_user.id,
            action=req.action,
            target_type=req.target_type,
            target_id=req.target_id,
            metadata_json=clean_metadata,
            ip_address=ip_addr,
            user_agent=user_agt,
            created_at=now_stamp
        )
        db.add(act_log)
        db.commit()
        
        return CommonResponse(ok=True, data=None, message="활동 로그가 정상적으로 수집되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UserPersonaRequest(BaseModel):
    company_name: str
    phone_number: str = ""
    website_url: str = ""
    region: str = ""
    industry_key: str = "general"
    keywords: list[str] = []
    content: str = ""


def _persona_to_dict(persona: UserPersona) -> dict:
    try:
        keywords = json.loads(persona.keywords_json or "[]")
        if not isinstance(keywords, list):
            keywords = []
    except Exception:
        keywords = []
    return {
        "id": persona.id,
        "company_name": persona.company_name,
        "phone_number": persona.phone_number,
        "website_url": persona.website_url,
        "region": getattr(persona, "region", "") or "",
        "industry_key": persona.industry_key,
        "is_default": persona.is_default,
        "keywords": keywords,
        "content": persona.content,
        "created_at": persona.created_at,
        "updated_at": persona.updated_at,
    }


@router.get("/auth/industry-templates", response_model=CommonResponse)
def list_user_industry_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    items = db.query(IndustryPromptTemplate).filter(
        IndustryPromptTemplate.is_active == True
    ).order_by(
        IndustryPromptTemplate.sort_order.asc(),
        IndustryPromptTemplate.id.asc()
    ).all()
    data = [{
        "industry_key": item.industry_key,
        "label": item.label,
        "category": item.category or "공통",
        "sort_order": item.sort_order or 0,
    } for item in items]
    return CommonResponse(ok=True, data=data, message="")


@router.get("/auth/regions", response_model=CommonResponse)
def list_user_region_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    items = db.query(RegionOption).filter(
        RegionOption.is_active == True
    ).order_by(
        RegionOption.sort_order.asc(),
        RegionOption.id.asc()
    ).all()
    data = [{
        "id": item.id,
        "name": item.name,
        "parent_name": item.parent_name or "",
        "region_type": item.region_type or "province",
        "sort_order": item.sort_order or 0,
    } for item in items]
    return CommonResponse(ok=True, data=data, message="")


@router.get("/auth/regions/search", response_model=CommonResponse)
def search_legal_districts(
    q: str = "",
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = str(q or "").strip()
    if len(query.replace(" ", "")) < 2:
        return CommonResponse(ok=True, data=[], message="두 글자 이상 입력해 주세요.")
    safe_limit = max(1, min(int(limit or 20), 30))
    tokens = [token for token in query.split() if token]
    compact = normalize_region_search_text(query)
    where_parts = ["selectable=1", "is_active=1"]
    params: dict[str, object] = {"limit": safe_limit, "compact": f"%{compact}%", "exact": query}
    for index, token in enumerate(tokens):
        key = f"token_{index}"
        where_parts.append(f"(full_name LIKE :{key} OR search_text LIKE :{key})")
        params[key] = f"%{token}%"
    rows = db.execute(text(f"""
        SELECT legal_code, full_name, short_name, sido, sigungu, locality, region_type
        FROM legal_districts
        WHERE {' AND '.join(where_parts)}
        ORDER BY
          CASE WHEN short_name=:exact THEN 0 WHEN short_name LIKE :exact_prefix THEN 1 ELSE 2 END,
          length(full_name), full_name
        LIMIT :limit
    """), {**params, "exact_prefix": f"{query}%"}).mappings().all()
    data = [{
        "legal_code": row["legal_code"],
        "full_name": row["full_name"],
        "display_name": format_region_display(row["full_name"]),
        "short_name": row["short_name"],
        "sido": row["sido"],
        "sigungu": row["sigungu"],
        "locality": row["locality"],
        "region_type": row["region_type"],
    } for row in rows]
    return CommonResponse(ok=True, data=data, message="")


# DISABLED duplicate route: canonical implementation lives in api/personas.py
# @router.get("/auth/personas", response_model=CommonResponse)
def list_user_personas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    personas = db.query(UserPersona).filter(UserPersona.user_id == current_user.id).order_by(UserPersona.is_default.desc(), UserPersona.updated_at.desc()).all()
    return CommonResponse(ok=True, data=[_persona_to_dict(p) for p in personas], message="")


# DISABLED duplicate route: canonical implementation lives in api/personas.py
# @router.post("/auth/personas", response_model=CommonResponse)
def create_user_persona(
    req: UserPersonaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company_name = req.company_name.strip()
    region = (req.region or "").strip()
    if not company_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="업체명은 필수입니다.")
    if not region:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지역은 필수입니다.")
    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    has_default = db.query(UserPersona).filter(UserPersona.user_id == current_user.id, UserPersona.is_default == True).first()
    persona = UserPersona(
        user_id=current_user.id,
        company_name=company_name,
        phone_number=(req.phone_number or "").strip(),
        website_url=(req.website_url or "").strip(),
        region=region,
        industry_key=(req.industry_key or "general").strip() or "general",
        keywords_json=json.dumps(req.keywords or [], ensure_ascii=False),
        content=(req.content or "").strip(),
        is_default=not bool(has_default),
        created_at=now_stamp,
        updated_at=now_stamp,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return CommonResponse(ok=True, data=_persona_to_dict(persona), message="페르소나가 저장되었습니다.")


# DISABLED duplicate route: canonical implementation lives in api/personas.py
# @router.put("/auth/personas/{persona_id}", response_model=CommonResponse)
def update_user_persona(
    persona_id: int,
    req: UserPersonaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    persona = db.query(UserPersona).filter(UserPersona.id == persona_id, UserPersona.user_id == current_user.id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="페르소나를 찾을 수 없습니다.")
    company_name = req.company_name.strip()
    region = (req.region or "").strip()
    if not company_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="업체명은 필수입니다.")
    if not region:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지역은 필수입니다.")
    persona.company_name = company_name
    persona.phone_number = (req.phone_number or "").strip()
    persona.website_url = (req.website_url or "").strip()
    persona.region = region
    persona.industry_key = (req.industry_key or "general").strip() or "general"
    persona.keywords_json = json.dumps(req.keywords or [], ensure_ascii=False)
    persona.content = (req.content or "").strip()
    persona.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    db.refresh(persona)
    return CommonResponse(ok=True, data=_persona_to_dict(persona), message="페르소나가 수정되었습니다.")


# DISABLED duplicate route: canonical implementation lives in api/personas.py
# @router.put("/auth/personas/{persona_id}/default", response_model=CommonResponse)
def set_default_user_persona(
    persona_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    persona = db.query(UserPersona).filter(UserPersona.id == persona_id, UserPersona.user_id == current_user.id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="페르소나를 찾을 수 없습니다.")
    db.query(UserPersona).filter(UserPersona.user_id == current_user.id).update({UserPersona.is_default: False}, synchronize_session=False)
    persona.is_default = True
    persona.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    db.refresh(persona)
    return CommonResponse(ok=True, data=_persona_to_dict(persona), message="기본 페르소나가 변경되었습니다.")


# DISABLED duplicate route: canonical implementation lives in api/personas.py
# @router.delete("/auth/personas/{persona_id}", response_model=CommonResponse)
def delete_user_persona(
    persona_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    persona = db.query(UserPersona).filter(UserPersona.id == persona_id, UserPersona.user_id == current_user.id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="페르소나를 찾을 수 없습니다.")
    was_default = persona.is_default
    db.delete(persona)
    db.commit()
    if was_default:
        next_persona = db.query(UserPersona).filter(UserPersona.user_id == current_user.id).order_by(UserPersona.updated_at.desc()).first()
        if next_persona:
            next_persona.is_default = True
            db.commit()
    return CommonResponse(ok=True, data=None, message="페르소나가 삭제되었습니다.")


@router.put("/auth/settings", response_model=CommonResponse)
def update_settings(
    req: UserSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    현재 로그인된 사용자의 설정을 업데이트합니다 (예: 워드프레스 사용 여부 토글).
    """
    try:
        current_user.wp_enabled = req.wp_enabled
        current_user.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
        db.refresh(current_user)
        
        user_resp = UserResponse.model_validate(current_user)
        user_resp.project_count = len(current_user.projects)
        return CommonResponse(ok=True, data=user_resp.model_dump(), message="설정이 성공적으로 저장되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
