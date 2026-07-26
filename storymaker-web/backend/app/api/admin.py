# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 관리자 대시보드 API 라우터 (admin.py)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List
import re

from app.db.database import get_db
from app.db.models import User, Project, Company, Persona, UserPersona, UserSession, ActivityLog, IndustryPromptTemplate
from app.api.personas import serialize_user_persona
from app.api.auth import get_admin_user
from app.schemas import CommonResponse, UserStatusUpdateRequest, UserRoleUpdateRequest, UserTierUpdateRequest

router = APIRouter()

@router.get("/admin/users", response_model=CommonResponse)
def get_admin_users(
    sort_by: str = "join", # join (최근 가입순), activity (최근 활동순)
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 전체 가입자 목록 및 사용량 요약 지표를 조회합니다. (비밀번호 해시 제외)
    """
    try:
        query = db.query(User)
        if sort_by == "activity":
            query = query.order_by(User.last_activity_at.desc().nullslast(), User.id.desc())
        else:
            query = query.order_by(User.id.desc())
            
        users = query.all()
        
        # 시간 헬퍼
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")

        user_list = []
        for u in users:
            # 1. 기본 인프라 정보
            project_count = len(u.projects)
            
            # 2. 오늘/이번주/이번달 생성한 프로젝트 수
            projects_today = db.query(Project).filter(Project.user_id == u.id, Project.created_at >= today_str).count()
            projects_this_week = db.query(Project).filter(Project.user_id == u.id, Project.created_at >= this_week_start).count()
            projects_this_month = db.query(Project).filter(Project.user_id == u.id, Project.created_at >= this_month_start).count()

            # 3. 활동 로그 기반 종합 통계
            login_count = db.query(ActivityLog).filter(ActivityLog.user_id == u.id, ActivityLog.action == "login").count()
            prompt_count = db.query(ActivityLog).filter(ActivityLog.user_id == u.id, ActivityLog.action == "prompt_generate").count()
            parse_count = db.query(ActivityLog).filter(ActivityLog.user_id == u.id, ActivityLog.action == "result_parse").count()
            preview_count = db.query(ActivityLog).filter(ActivityLog.user_id == u.id, ActivityLog.action == "preview_open").count()

            user_list.append({
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "tier": u.tier,
                "wp_enabled": u.wp_enabled,
                "is_active": u.is_active,
                "project_count": project_count,
                "projects_today": projects_today,
                "projects_this_week": projects_this_week,
                "projects_this_month": projects_this_month,
                "created_at": u.created_at,
                "updated_at": u.updated_at,
                "last_login_at": u.last_login_at,
                "last_activity_at": u.last_activity_at,
                "login_count": login_count,
                "prompt_count": prompt_count,
                "parse_count": parse_count,
                "preview_count": preview_count
            })
            
        return CommonResponse(ok=True, data=user_list, message="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/stats", response_model=CommonResponse)
def get_admin_stats(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 사이트 전체 사용량 및 활동 로그 기반의 고도화된 통계 현황을 집계합니다.
    """
    try:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        one_week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")

        # 1. 회원 기본 통계
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        admin_users = db.query(User).filter(User.role == "admin").count()
        recent_join_count = db.query(User).filter(User.created_at >= one_week_ago).count()

        # 2. 활동 로그 기반 로그인 빈도 (고유 회원수)
        today_start_str = f"{today_str} 00:00:00"
        logins_today = db.query(ActivityLog.user_id).filter(ActivityLog.action == "login", ActivityLog.created_at >= today_start_str).distinct().count()
        logins_this_week = db.query(ActivityLog.user_id).filter(ActivityLog.action == "login", ActivityLog.created_at >= this_week_start).distinct().count()
        logins_this_month = db.query(ActivityLog.user_id).filter(ActivityLog.action == "login", ActivityLog.created_at >= this_month_start).distinct().count()

        # 3. 프로젝트 통계
        total_projects = db.query(Project).count()
        projects_today = db.query(Project).filter(Project.created_at >= today_str).count()
        projects_this_week = db.query(Project).filter(Project.created_at >= this_week_start).count()
        projects_this_month = db.query(Project).filter(Project.created_at >= this_month_start).count()
        recent_project_count = db.query(Project).filter(Project.created_at >= one_week_ago).count()

        # 4. 활동 로그 기반 파싱 및 프롬프트 생성 횟수
        total_parsed = db.query(ActivityLog).filter(ActivityLog.action == "result_parse").count()
        total_prompts = db.query(ActivityLog).filter(ActivityLog.action == "prompt_generate").count()

        # 5. 인프라 리소스 통계
        total_companies = db.query(Company).count()
        total_personas = db.query(Persona).count()

        stats_data = {
            "total_users": total_users,
            "active_users": active_users,
            "admin_users": admin_users,
            "total_projects": total_projects,
            "projects_today": projects_today,
            "projects_this_week": projects_this_week,
            "projects_this_month": projects_this_month,
            "total_companies": total_companies,
            "total_personas": total_personas,
            "recent_join_count": recent_join_count,
            "recent_project_count": recent_project_count,
            "logins_today": logins_today,
            "logins_this_week": logins_this_week,
            "logins_this_month": logins_this_month,
            "total_parsed": total_parsed,
            "total_prompts": total_prompts
        }
        return CommonResponse(ok=True, data=stats_data, message="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/users/{user_id}/projects", response_model=CommonResponse)
def get_user_projects(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 특정 가입자가 생성한 프로젝트 목록을 조회합니다.
    """
    try:
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            return CommonResponse(ok=False, data=None, message="존재하지 않는 사용자입니다.")
            
        projects = db.query(Project).filter(Project.user_id == user_id).order_by(Project.updated_at.desc()).all()
        
        proj_list = []
        for p in projects:
            proj_list.append({
                "project_id": p.id,
                "title": p.title,
                "company_name": p.company.name if p.company else "알 수 없음",
                "created_at": p.created_at,
                "updated_at": p.updated_at
            })
            
        return CommonResponse(ok=True, data=proj_list, message="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/users/{user_id}/history", response_model=CommonResponse)
def get_user_history(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 특정 사용자의 최근 세션 정보 및 활동 로그를 일괄 조회합니다.
    """
    try:
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            return CommonResponse(ok=False, data=None, message="존재하지 않는 사용자입니다.")
            
        # 최근 세션 15개
        sessions = db.query(UserSession).filter(UserSession.user_id == user_id).order_by(UserSession.id.desc()).limit(15).all()
        # 최근 활동 로그 30개
        logs = db.query(ActivityLog).filter(ActivityLog.user_id == user_id).order_by(ActivityLog.id.desc()).limit(30).all()
        
        session_list = []
        for s in sessions:
            session_list.append({
                "id": s.id,
                "login_at": s.login_at,
                "logout_at": s.logout_at,
                "last_seen_at": s.last_seen_at,
                "duration_seconds": s.duration_seconds,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent
            })
            
        log_list = []
        for l in logs:
            log_list.append({
                "id": l.id,
                "action": l.action,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "metadata_json": l.metadata_json,
                "ip_address": l.ip_address,
                "user_agent": l.user_agent,
                "created_at": l.created_at
            })
            
        return CommonResponse(ok=True, data={"sessions": session_list, "logs": log_list}, message="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/users/{user_id}/personas", response_model=CommonResponse)
def get_user_personas(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """관리자 전용: 특정 사용자가 마이페이지에 저장한 업체 페르소나를 조회합니다."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="존재하지 않는 사용자입니다.")
    personas = db.query(UserPersona).filter(UserPersona.user_id == user_id).order_by(UserPersona.updated_at.desc()).all()
    return CommonResponse(ok=True, data=[serialize_user_persona(p) for p in personas], message="")


@router.get("/admin/usage/daily", response_model=CommonResponse)
def get_daily_usage(
    days: int = 7,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 최근 N일의 일자별 종합 사용량(로그인수, 고유활동유저수, 프로젝트생성수, 프롬프트빌드수, 파싱수)을 집계합니다.
    """
    try:
        now = datetime.now()
        dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        dates.reverse() # 과거 날짜부터 오름차순 배치
        
        items = []
        for d in dates:
            d_start = f"{d} 00:00:00"
            d_end = f"{d} 23:59:59"
            
            # 1. 로그인 횟수
            logins = db.query(ActivityLog).filter(
                ActivityLog.action == "login",
                ActivityLog.created_at >= d_start,
                ActivityLog.created_at <= d_end
            ).count()
            
            # 2. 고유 활동 유저 수
            active_users = db.query(ActivityLog.user_id).filter(
                ActivityLog.created_at >= d_start,
                ActivityLog.created_at <= d_end
            ).distinct().count()
            
            # 3. 프로젝트 생성 수
            projects_created = db.query(Project).filter(
                Project.created_at >= d_start,
                Project.created_at <= d_end
            ).count()
            
            # 4. 프롬프트 생성 수
            prompts_generated = db.query(ActivityLog).filter(
                ActivityLog.action == "prompt_generate",
                ActivityLog.created_at >= d_start,
                ActivityLog.created_at <= d_end
            ).count()
            
            # 5. 파싱 완료 수
            results_parsed = db.query(ActivityLog).filter(
                ActivityLog.action == "result_parse",
                ActivityLog.created_at >= d_start,
                ActivityLog.created_at <= d_end
            ).count()
            
            items.append({
                "date": d,
                "logins": logins,
                "active_users": active_users,
                "projects_created": projects_created,
                "prompts_generated": prompts_generated,
                "results_parsed": results_parsed
            })
            
        return CommonResponse(ok=True, data={"days": days, "items": items}, message="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/usage/users", response_model=CommonResponse)
def get_user_usage_ranking(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 사용자별 사용량 종합 지표 랭킹을 집계합니다. (사용시간 기준 내림차순 정렬)
    """
    try:
        users = db.query(User).all()
        items = []
        for u in users:
            # 1. 프로젝트 수
            project_count = len(u.projects)
            
            # 2. 총 로그인 횟수
            login_count = db.query(ActivityLog).filter(
                ActivityLog.user_id == u.id,
                ActivityLog.action == "login"
            ).count()
            
            # 3. 총 프롬프트 생성 횟수
            prompt_count = db.query(ActivityLog).filter(
                ActivityLog.user_id == u.id,
                ActivityLog.action == "prompt_generate"
            ).count()
            
            # 4. 총 SNS별 분리 횟수
            parse_count = db.query(ActivityLog).filter(
                ActivityLog.user_id == u.id,
                ActivityLog.action == "result_parse"
            ).count()
            
            # 5. 총 사용 시간 합계 (초 단위)
            total_duration = db.query(func.sum(UserSession.duration_seconds)).filter(
                UserSession.user_id == u.id
            ).scalar() or 0
            
            items.append({
                "user_id": u.id,
                "username": u.username,
                "project_count": project_count,
                "login_count": login_count,
                "prompt_count": prompt_count,
                "parse_count": parse_count,
                "total_usage_seconds": int(total_duration)
            })
            
        # 총 사용시간(체류시간) 기준으로 정렬하되, 동률일 경우 프로젝트 수로 정렬
        items.sort(key=lambda x: (x["total_usage_seconds"], x["project_count"]), reverse=True)
        return CommonResponse(ok=True, data={"items": items}, message="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/users/{user_id}/status", response_model=CommonResponse)
def update_user_status(
    user_id: int,
    req: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 특정 가입자의 활성/비활성 상태를 제어합니다. (자기 자신 비활성화 방어 탑재)
    """
    try:
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="자기 자신의 계정은 비활성화할 수 없습니다."
            )
            
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            return CommonResponse(ok=False, data=None, message="대상 사용자를 찾을 수 없습니다.")
            
        target_user.is_active = req.is_active
        target_user.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
        db.refresh(target_user)
        
        status_txt = "활성화" if req.is_active else "비활성화"
        return CommonResponse(ok=True, data=None, message=f"사용자 계정이 성공적으로 {status_txt} 되었습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/users/{user_id}/role", response_model=CommonResponse)
def update_user_role(
    user_id: int,
    req: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 특정 가입자의 권한을 변경합니다. (마지막 남은 활성 admin 보호 방어 탑재)
    """
    try:
        if req.role not in ["admin", "user"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="올바르지 않은 권한 유형입니다. (admin 또는 user만 가능)"
            )
            
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            return CommonResponse(ok=False, data=None, message="대상 사용자를 찾을 수 없습니다.")
            
        # 마지막 활성 admin 계정 보호 로직
        if target_user.role == "admin" and req.role == "user":
            active_admin_count = db.query(User).filter(User.role == "admin", User.is_active == True).count()
            if active_admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="시스템에 최소 1명 이상의 활성화된 관리자 계정이 유지되어야 하므로 권한을 내릴 수 없습니다."
                )
                
        target_user.role = req.role
        target_user.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
        db.refresh(target_user)
        
        role_txt = "관리자" if req.role == "admin" else "일반 사용자"
        return CommonResponse(ok=True, data=None, message=f"사용자 권한이 {role_txt}(으)로 변경되었습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/users/{user_id}/tier", response_model=CommonResponse)
def update_user_tier(
    user_id: int,
    req: UserTierUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 특정 가입자의 등급(무료/결제) 상태를 제어합니다.
    """
    try:
        if req.tier not in ["free", "paid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="올바르지 않은 등급 유형입니다. (free 또는 paid만 가능)"
            )
            
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            return CommonResponse(ok=False, data=None, message="대상 사용자를 찾을 수 없습니다.")
            
        target_user.tier = req.tier
        target_user.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
        db.refresh(target_user)
        
        tier_txt = "결제 사용자" if req.tier == "paid" else "무료 사용자"
        return CommonResponse(ok=True, data=None, message=f"사용자 등급이 {tier_txt}(으)로 변경되었습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel


class IndustryTemplateUpdateRequest(BaseModel):
    label: str | None = None
    category: str | None = None
    prompt_guidance: str | None = None
    content_flow: str | None = None
    keyword_hint: str | None = None
    tone_hint: str | None = None
    avoid_hint: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class IndustryTemplateCreateRequest(IndustryTemplateUpdateRequest):
    industry_key: str


class BulkDeleteUsersRequest(BaseModel):
    user_ids: List[int]


def serialize_industry_template(item: IndustryPromptTemplate) -> dict:
    return {
        "id": item.id,
        "industry_key": item.industry_key,
        "label": item.label,
        "category": item.category,
        "prompt_guidance": item.prompt_guidance,
        "content_flow": item.content_flow,
        "keyword_hint": item.keyword_hint,
        "tone_hint": item.tone_hint,
        "avoid_hint": item.avoid_hint,
        "is_active": item.is_active,
        "sort_order": item.sort_order,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/admin/industry-templates", response_model=CommonResponse)
def get_industry_templates(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """관리자 전용: 업종별 프롬프트 템플릿 전체 목록을 조회합니다."""
    items = db.query(IndustryPromptTemplate).order_by(
        IndustryPromptTemplate.sort_order.asc(),
        IndustryPromptTemplate.id.asc()
    ).all()
    return CommonResponse(ok=True, data=[serialize_industry_template(item) for item in items], message="")


@router.post("/admin/industry-templates", response_model=CommonResponse)
def create_industry_template(
    req: IndustryTemplateCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """관리자 전용: 새 업종 프롬프트 템플릿을 추가합니다."""
    industry_key = re.sub(r"\s+", "_", (req.industry_key or "").strip().lower())
    if not industry_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="업종 키를 입력해 주세요.")
    exists = db.query(IndustryPromptTemplate).filter(IndustryPromptTemplate.industry_key == industry_key).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 존재하는 업종 키입니다.")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    max_sort = db.query(func.max(IndustryPromptTemplate.sort_order)).scalar() or 0
    item = IndustryPromptTemplate(
        industry_key=industry_key,
        label=(req.label or industry_key).strip(),
        category=(req.category or "공통").strip(),
        prompt_guidance=(req.prompt_guidance or "").strip(),
        content_flow=(req.content_flow or "").strip(),
        keyword_hint=(req.keyword_hint or "").strip(),
        tone_hint=(req.tone_hint or "").strip(),
        avoid_hint=(req.avoid_hint or "").strip(),
        is_active=True if req.is_active is None else bool(req.is_active),
        sort_order=int(req.sort_order) if req.sort_order is not None else int(max_sort) + 1,
        created_at=now_str,
        updated_at=now_str,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return CommonResponse(ok=True, data=serialize_industry_template(item), message="새 업종이 추가되었습니다.")


@router.get("/admin/industry-templates/{industry_key}", response_model=CommonResponse)
def get_industry_template(
    industry_key: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """관리자 전용: 특정 업종 프롬프트 템플릿을 조회합니다."""
    item = db.query(IndustryPromptTemplate).filter(IndustryPromptTemplate.industry_key == industry_key).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업종 템플릿을 찾을 수 없습니다.")
    return CommonResponse(ok=True, data=serialize_industry_template(item), message="")


@router.put("/admin/industry-templates/{industry_key}", response_model=CommonResponse)
def update_industry_template(
    industry_key: str,
    req: IndustryTemplateUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """관리자 전용: 특정 업종 프롬프트 템플릿을 수정합니다."""
    item = db.query(IndustryPromptTemplate).filter(IndustryPromptTemplate.industry_key == industry_key).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업종 템플릿을 찾을 수 없습니다.")

    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in {"label", "category", "prompt_guidance", "content_flow", "keyword_hint", "tone_hint", "avoid_hint"}:
            setattr(item, field, str(value or "").strip())
        elif field == "is_active":
            item.is_active = bool(value)
        elif field == "sort_order":
            try:
                item.sort_order = int(value)
            except Exception:
                item.sort_order = item.sort_order or 0
    item.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    db.refresh(item)
    return CommonResponse(ok=True, data=serialize_industry_template(item), message="업종 프롬프트 템플릿이 저장되었습니다.")


@router.post("/admin/industry-templates/{industry_key}/remove", response_model=CommonResponse)
def remove_industry_template(
    industry_key: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    item = db.query(IndustryPromptTemplate).filter(IndustryPromptTemplate.industry_key == industry_key).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업종 템플릿을 찾을 수 없습니다.")
    db.delete(item)
    db.commit()
    return CommonResponse(ok=True, data={"industry_key": industry_key}, message="업종이 삭제되었습니다.")


@router.post("/admin/users/bulk-delete", response_model=CommonResponse)
def bulk_delete_users(
    req: BulkDeleteUsersRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    관리자 전용: 선택된 여러 사용자 계정을 일괄 삭제합니다. (자기 자신 삭제 방지 및 최소 1명 이상의 활성 admin 유지 보호 탑재)
    """
    try:
        # 삭제 대상에서 자기 자신 제외
        target_ids = [uid for uid in req.user_ids if uid != admin_user.id]
        
        if not target_ids:
            return CommonResponse(ok=False, data=None, message="삭제할 대상 사용자가 없거나 자기 자신만 선택되었습니다.")
            
        # 삭제할 사용자들 조회
        users_to_delete = db.query(User).filter(User.id.in_(target_ids)).all()
        
        if not users_to_delete:
            return CommonResponse(ok=False, data=None, message="삭제할 대상 사용자를 찾을 수 없습니다.")
            
        # 마지막 남은 활성 admin 보호 검사
        admins_to_delete = [u for u in users_to_delete if u.role == "admin" and u.is_active]
        if admins_to_delete:
            total_active_admins = db.query(User).filter(User.role == "admin", User.is_active == True).count()
            if total_active_admins <= len(admins_to_delete):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="시스템에 최소 1명 이상의 활성화된 관리자 계정이 유지되어야 하므로 관리자 계정을 일괄 삭제할 수 없습니다."
                )
                
        deleted_count = 0
        for u in users_to_delete:
            db.delete(u)
            deleted_count += 1
            
        db.commit()
        return CommonResponse(ok=True, data={"deleted_count": deleted_count}, message=f"성공적으로 {deleted_count}명의 사용자 계정을 일괄 삭제하였습니다.")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
