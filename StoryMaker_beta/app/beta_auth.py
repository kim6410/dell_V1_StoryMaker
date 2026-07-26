from __future__ import annotations

import os
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException, Request, status

AUTH_ME_URL = os.getenv("STORYMAKER_V1_AUTH_ME_URL", "http://127.0.0.1:8011/v1-api/auth/me")
AUTH_TIMEOUT_SECONDS = float(os.getenv("STORYMAKER_BETA_AUTH_TIMEOUT", "3.0"))


def require_beta_login(request: Request) -> dict[str, Any]:
    """Validate the current StoryMaker V1 login session before exposing Beta data.

    Beta runs as an isolated service, but archive/job assets are user data.
    The V1 session remains the source of truth, so this bridge forwards only
    the incoming Cookie/Authorization headers to V1 /v1-api/auth/me and fails closed.
    """
    cookie = request.headers.get("cookie", "")
    authorization = request.headers.get("authorization", "")

    if not cookie and not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요한 서비스입니다.",
        )

    headers = {"Accept": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    if authorization:
        headers["Authorization"] = authorization

    auth_request = urllib.request.Request(AUTH_ME_URL, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(auth_request, timeout=AUTH_TIMEOUT_SECONDS) as response:
            if 200 <= response.status < 300:
                return {"authenticated": True, "status": response.status}
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="로그인이 필요한 서비스입니다.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="로그인 확인 서비스 응답이 올바르지 않습니다.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="로그인 확인 서비스를 사용할 수 없습니다.",
        ) from exc

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="로그인이 필요한 서비스입니다.",
    )
