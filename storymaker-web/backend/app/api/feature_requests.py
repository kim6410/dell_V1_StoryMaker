# -*- coding: utf-8 -*-
"""StoryMaker 수정요청 게시판 API."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import FeatureRequest, User, ActivityLog
from app.api.auth import get_current_user, get_admin_user
from app.schemas import CommonResponse

router = APIRouter()


class FeatureRequestCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    content: str = Field(..., min_length=5, max_length=5000)


class FeatureRequestStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=20)
    admin_note: Optional[str] = Field(default=None, max_length=3000)


def serialize_feature_request(item: FeatureRequest) -> dict:
    return {
        "id": item.id,
        "user_id": item.user_id,
        "username": item.user.username if item.user else "알 수 없음",
        "title": item.title,
        "content": item.content,
        "status": item.status,
        "admin_note": item.admin_note,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.post("/feature-requests", response_model=CommonResponse)
def create_feature_request(
    req: FeatureRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """현재 로그인 사용자가 수정요청을 등록합니다."""
    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item = FeatureRequest(
        user_id=current_user.id,
        title=req.title.strip(),
        content=req.content.strip(),
        status="접수",
        admin_note=None,
        created_at=now_stamp,
        updated_at=now_stamp,
    )
    db.add(item)
    db.flush()

    ip_addr = request.client.host if request.client else "127.0.0.1"
    user_agt = request.headers.get("user-agent", "Unknown")
    db.add(ActivityLog(
        user_id=current_user.id,
        action="feature_request_create",
        target_type="feature_request",
        target_id=item.id,
        metadata_json=None,
        ip_address=ip_addr,
        user_agent=user_agt,
        created_at=now_stamp,
    ))
    db.commit()
    db.refresh(item)
    return CommonResponse(ok=True, data=serialize_feature_request(item), message="수정요청이 접수되었습니다.")


@router.get("/feature-requests", response_model=CommonResponse)
def list_my_feature_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """현재 로그인 사용자가 등록한 요청사항과 관리자 답변을 최신순으로 조회합니다."""
    items = (
        db.query(FeatureRequest)
        .filter(FeatureRequest.user_id == current_user.id)
        .order_by(FeatureRequest.id.desc())
        .limit(300)
        .all()
    )
    return CommonResponse(ok=True, data=[serialize_feature_request(item) for item in items], message="")


@router.get("/admin/feature-requests", response_model=CommonResponse)
def list_feature_requests(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """관리자 전용: 수정요청 게시판 목록을 조회합니다."""
    query = db.query(FeatureRequest).order_by(FeatureRequest.id.desc())
    if status_filter:
        query = query.filter(FeatureRequest.status == status_filter)
    items = query.limit(300).all()
    return CommonResponse(ok=True, data=[serialize_feature_request(item) for item in items], message="")


@router.put("/admin/feature-requests/{request_id}", response_model=CommonResponse)
def update_feature_request_status(
    request_id: int,
    req: FeatureRequestStatusUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """관리자 전용: 수정요청 상태와 관리자 메모를 수정합니다."""
    allowed = ["접수", "처리중", "완료", "보류"]
    if req.status not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="상태값은 접수, 처리중, 완료, 보류 중 하나여야 합니다.")

    item = db.query(FeatureRequest).filter(FeatureRequest.id == request_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="수정요청을 찾을 수 없습니다.")

    normalized_note = req.admin_note.strip() if req.admin_note else None
    # 관리자 답변이 등록되면 사용자 목록과 상세 화면의 상태를 자동으로 완료 처리합니다.
    item.status = "완료" if normalized_note else req.status
    item.admin_note = normalized_note
    item.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    db.refresh(item)
    message = "관리자 답변이 등록되어 상태가 완료로 변경되었습니다." if normalized_note else "수정요청 상태가 변경되었습니다."
    return CommonResponse(ok=True, data=serialize_feature_request(item), message=message)
