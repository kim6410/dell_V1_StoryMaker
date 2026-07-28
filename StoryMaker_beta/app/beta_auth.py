from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
import time
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

ROOT = Path(os.getenv("STORYMAKER_BETA_ROOT", "/home/bourne/StoryMaker_1/StoryMaker_beta"))
DB_PATH = ROOT / "data" / "storymaker_beta.db"
AUTH_SECRET = (os.getenv("BETA_INTERNAL_AUTH_SECRET") or "").strip()
AUTH_WINDOW_SECONDS = 300
JOB_PATH_PATTERN = re.compile(r"/jobs/(beta_[0-9A-Za-z_-]+)(?:/|$)")


def _signature(user_id: int, role: str, timestamp: str) -> str:
    payload = f"{user_id}|{role}|{timestamp}".encode("utf-8")
    return hmac.new(AUTH_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def require_signed_user(request: Request) -> tuple[int, str]:
    if not AUTH_SECRET:
        raise HTTPException(status_code=503, detail="Beta 내부 인증키가 설정되지 않았습니다.")

    raw_user_id = (request.headers.get("x-storymaker-user-id") or "").strip()
    role = (request.headers.get("x-storymaker-user-role") or "user").strip().lower()
    timestamp = (request.headers.get("x-storymaker-auth-time") or "").strip()
    supplied = (request.headers.get("x-storymaker-auth-signature") or "").strip().lower()

    try:
        user_id = int(raw_user_id)
        issued_at = int(timestamp)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Beta 사용자 인증정보가 없습니다.")

    if user_id <= 0 or abs(int(time.time()) - issued_at) > AUTH_WINDOW_SECONDS:
        raise HTTPException(status_code=401, detail="Beta 사용자 인증정보가 만료되었습니다.")

    expected = _signature(user_id, role, timestamp)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Beta 내부 사용자 서명이 올바르지 않습니다.")

    request.state.storymaker_user_id = user_id
    request.state.storymaker_user_role = role
    return user_id, role


def current_user_id(request: Request) -> int:
    value = getattr(request.state, "storymaker_user_id", None)
    if not isinstance(value, int) or value <= 0:
        value, _ = require_signed_user(request)
    return value


def current_user_role(request: Request) -> str:
    role = getattr(request.state, "storymaker_user_role", None)
    if not role:
        _, role = require_signed_user(request)
    return str(role).lower()


def require_job_owner(request: Request, job_id: str) -> None:
    user_id = current_user_id(request)
    role = current_user_role(request)
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            "SELECT owner_user_id FROM beta_jobs WHERE beta_job_id=?",
            (job_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Beta 작업을 찾을 수 없습니다.")
    if role == "admin":
        return
    owner_user_id = row[0]
    if owner_user_id is None or int(owner_user_id) != user_id:
        raise HTTPException(status_code=404, detail="Beta 작업을 찾을 수 없습니다.")


async def enforce_beta_user_isolation(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/beta-api") or path == "/beta-api/health":
        return await call_next(request)

    try:
        require_signed_user(request)
        match = JOB_PATH_PATTERN.search(path)
        if match:
            require_job_owner(request, match.group(1))
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {},
        )
    return await call_next(request)
