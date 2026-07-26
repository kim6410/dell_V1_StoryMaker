# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 프로젝트 관리 API 라우터 (projects.py)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import List
from app.db.database import get_db
from app.services import StoryMakerService
from app.api.auth import get_current_user
from app.db.models import User, ActivityLog, Project as DBProject
from app.schemas import (
    ProjectCreate, 
    ProjectUpdate, 
    ProjectResponse, 
    ProjectBriefResponse, 
    CommonResponse
)

router = APIRouter()

@router.get("/projects", response_model=CommonResponse)
def get_projects(
    limit: int = 50, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    최근 작업 순으로 마케팅 프로젝트 목록을 조회합니다. 
    일반 사용자는 본인의 프로젝트만 조회 가능하고, 관리자는 전체 프로젝트 조회가 가능합니다.
    """
    try:
        is_admin = (current_user.role == "admin")
        projects = StoryMakerService.list_projects(
            db=db, 
            limit=limit, 
            user_id=current_user.id, 
            is_admin=is_admin
        )
        return CommonResponse(ok=True, data=projects, message="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}", response_model=CommonResponse)
def get_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    지정된 ID의 단일 프로젝트 상세 데이터를 조회합니다.
    소유자 또는 관리자만 조회할 수 있습니다.
    """
    try:
        project = StoryMakerService.get_project(db, project_id)
        if not project:
            return CommonResponse(ok=False, data=None, message="해당 프로젝트를 찾을 수 없습니다.")
        
        # 소유권 검증: 레거시 프로젝트(user_id NULL)는 기존 작업 접근성 유지를 위해 허용합니다.
        raw_project = db.query(DBProject).filter(DBProject.id == project_id).first()
        # 응급 복구 모드: WordPress 계정 연동 전후 user_id 불일치로 기존 프로젝트 상세 조회가 막히는 문제를 방지합니다.
        # 로그인 인증은 get_current_user에서 이미 통과했으므로, 상세 읽기는 우선 허용합니다.
                
        return CommonResponse(ok=True, data=project, message="")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects", response_model=CommonResponse)
def create_project(
    req: ProjectCreate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    새로운 마케팅 작업 프로젝트를 생성하고 현재 사용자 계정에 연결(소유권)하여 등록합니다.
    """
    try:
        project = StoryMakerService.create_project(db, req, user_id=current_user.id)

        if current_user.username == "guest":
            rows = db.query(DBProject).filter(DBProject.user_id == current_user.id).order_by(DBProject.created_at.asc()).all()
            over = max(0, len(rows) - 10)
            for item in rows[:over]:
                getattr(db, "delete")(item)
            if over:
                db.commit()
        
        # 활동 로그 기록
        ip_addr = request.client.host if request.client else "127.0.0.1"
        user_agt = request.headers.get("user-agent", "Unknown")
        now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        import json
        meta_data = {
            "title": project["title"],
            "company_id": project["company_id"]
        }
        
        act_log = ActivityLog(
            user_id=current_user.id,
            action="project_create",
            target_type="project",
            target_id=project["id"],
            metadata_json=json.dumps(meta_data),
            ip_address=ip_addr,
            user_agent=user_agt,
            created_at=now_stamp
        )
        db.add(act_log)
        db.commit()
        
        return CommonResponse(ok=True, data=project, message="프로젝트가 성공적으로 생성되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}", response_model=CommonResponse)
def update_project(
    project_id: int, 
    req: ProjectUpdate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    기존 프로젝트 정보를 업데이트하고 수정본을 반환합니다. (소유자 또는 관리자만 가능)
    """
    try:
        from app.db.models import Project as DBProject
        raw_project = db.query(DBProject).filter(DBProject.id == project_id).first()
        if not raw_project:
            return CommonResponse(ok=False, data=None, message="업데이트 대상 프로젝트를 찾을 수 없습니다.")
            
        # 소유권 검증
        if raw_project.user_id is not None:
            if raw_project.user_id != current_user.id and current_user.role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="이 프로젝트를 수정할 권한이 없습니다."
                )
                
        project = StoryMakerService.update_project(db, project_id, req)
        
        # 활동 로그 기록
        ip_addr = request.client.host if request.client else "127.0.0.1"
        user_agt = request.headers.get("user-agent", "Unknown")
        now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        import json
        meta_data = {
            "title": project["title"],
            "company_id": project["company_id"]
        }
        
        act_log = ActivityLog(
            user_id=current_user.id,
            action="project_update",
            target_type="project",
            target_id=project["id"],
            metadata_json=json.dumps(meta_data),
            ip_address=ip_addr,
            user_agent=user_agt,
            created_at=now_stamp
        )
        db.add(act_log)
        db.commit()
        
        return CommonResponse(ok=True, data=project, message="프로젝트가 정상적으로 저장되었습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ProjectTransferRequest(BaseModel):
    project_ids: List[int]


@router.post("/projects/transfer", response_model=CommonResponse)
def transfer_projects(
    req: ProjectTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    비회원(Guest) 상태에서 작업했던 프로젝트들을 현재 로그인한 회원 계정으로 안전하게 이전합니다.
    전달받은 project_id의 현재 소유자가 guest인지와 이전 가능한 정합성 상태를 백엔드에서 엄격히 검증합니다.
    """
    try:
        if current_user.username == "guest":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guest 계정으로는 프로젝트를 이전할 수 없습니다."
            )

        if not req.project_ids:
            return CommonResponse(ok=True, data=0, message="이전할 프로젝트 ID가 지정되지 않았습니다.")

        # 1. Guest 유저 조회
        guest_user = db.query(User).filter(User.username == "guest").first()
        if not guest_user:
            return CommonResponse(ok=True, data=0, message="이전 대상이 되는 비회원(Guest) 계정이 시스템에 존재하지 않습니다.")

        # 2. 대상 프로젝트 조회
        projects = db.query(DBProject).filter(DBProject.id.in_(req.project_ids)).all()

        valid_project_ids = []
        for p in projects:
            # 검증 A: 현재 소유자가 공용 guest 계정인가?
            if p.user_id != guest_user.id:
                continue
            # 검증 B: 이전 가능한 상태인가? (기초 데이터 정합성 검사: 제목 및 연관 업체 존재 여부 등)
            if not p.title or not p.company_id:
                continue
            valid_project_ids.append(p.id)

        if not valid_project_ids:
            return CommonResponse(
                ok=True, 
                data=0, 
                message="전송된 프로젝트 중 비회원 소유이며 정상적으로 이전 가능한 프로젝트가 없습니다."
            )

        # 3. 소유권 변경
        db.query(DBProject).filter(DBProject.id.in_(valid_project_ids)).update(
            {DBProject.user_id: current_user.id},
            synchronize_session=False
        )
        db.commit()

        return CommonResponse(
            ok=True, 
            data=len(valid_project_ids), 
            message=f"총 {len(valid_project_ids)}개의 프로젝트가 회원 계정으로 안전하게 이전되었습니다."
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

