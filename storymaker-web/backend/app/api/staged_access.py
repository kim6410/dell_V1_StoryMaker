# -*- coding: utf-8 -*-
"""Gate 5 read-only staged availability endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.auth import get_optional_current_user
from app.db.models import User
from app.integration.staged_access import staged_access_status

router = APIRouter(prefix="/staged-access", tags=["Staged Access"])


@router.get("/status")
def get_staged_access_status(
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    return staged_access_status(current_user)
