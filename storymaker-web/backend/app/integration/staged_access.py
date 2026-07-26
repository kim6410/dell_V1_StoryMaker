# -*- coding: utf-8 -*-
"""Gate 5 staged production access guard.

The guard is intentionally independent from the one-click route. It reads a
small runtime JSON file on every request so an operator can disable staged
access without rebuilding or restarting the application.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status

from app.api.auth import get_optional_current_user
from app.db.models import User

_DEFAULT_RUNTIME_FLAG_FILE = Path(__file__).resolve().parents[2] / "runtime" / "staged_feature_flags.json"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_VALUES
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _as_int_set(value: Any) -> set[int]:
    if not isinstance(value, list):
        return set()
    result: set[int] = set()
    for item in value:
        try:
            result.add(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _as_str_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip().lower() for item in value if str(item).strip()}


def read_runtime_stage_flags() -> dict[str, Any]:
    """Return effective Gate 5 flags. All staged flags fail closed."""
    data: dict[str, Any] = {}
    path = Path(os.environ.get("STORYMAKER_STAGE_FLAGS_FILE", str(_DEFAULT_RUNTIME_FLAG_FILE)))
    try:
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
    except Exception:
        data = {}

    return {
        "enable_stage_generation": _as_bool(
            data.get("enable_stage_generation"),
            _env_bool("STORYMAKER_ENABLE_STAGE_GENERATION", False),
        ),
        "enable_stage_ui": _as_bool(
            data.get("enable_stage_ui"),
            _env_bool("STORYMAKER_ENABLE_STAGE_UI", False),
        ),
        "enable_stage_worker": _as_bool(
            data.get("enable_stage_worker"),
            _env_bool("STORYMAKER_ENABLE_STAGE_WORKER", False),
        ),
        "allowed_user_ids": _as_int_set(data.get("allowed_user_ids")),
        "allowed_usernames": _as_str_set(data.get("allowed_usernames")),
        "source": "runtime_file" if path.is_file() else "environment_or_default",
    }


def is_stage_test_user(user: Optional[User], flags: dict[str, Any]) -> bool:
    if user is None:
        return False
    if str(getattr(user, "role", "") or "").strip().lower() == "admin":
        return True
    try:
        if int(getattr(user, "id")) in flags["allowed_user_ids"]:
            return True
    except (TypeError, ValueError):
        pass
    username = str(getattr(user, "username", "") or "").strip().lower()
    return bool(username and username in flags["allowed_usernames"])


def require_staged_access(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> None:
    """Path-aware guard for both UI/user endpoints and frozen worker endpoints."""
    flags = read_runtime_stage_flags()
    path = request.url.path

    if "/worker/" in path:
        if not flags["enable_stage_generation"] or not flags["enable_stage_worker"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="STAGED_WORKER_DISABLED",
            )
        return

    if not flags["enable_stage_generation"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="STAGED_GENERATION_DISABLED",
        )
    if not is_stage_test_user(current_user, flags):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="STAGED_ACCESS_DENIED",
        )


def staged_access_status(current_user: Optional[User]) -> dict[str, Any]:
    flags = read_runtime_stage_flags()
    allowed = is_stage_test_user(current_user, flags)
    return {
        "ok": True,
        "stage_ui_visible": bool(
            allowed and flags["enable_stage_ui"] and flags["enable_stage_generation"]
        ),
        "stage_generation_enabled": bool(
            allowed and flags["enable_stage_generation"]
        ),
        "stage_worker_enabled": bool(flags["enable_stage_worker"]),
        "allowed": allowed,
        "flags_source": flags["source"],
    }
