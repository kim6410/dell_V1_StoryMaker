# -*- coding: utf-8 -*-
"""StoryMaker V2 독립 회원관리 API.

기존 제작 API, Queue, Worker와 분리된 관리자 전용 회원·페르소나 관리 기능입니다.
"""
from datetime import datetime
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.api.auth import get_admin_user
from app.api.personas import clean_persona_payload, serialize_user_persona
from app.db.database import get_db
from app.db.models import Project, User, UserPersona
from app.schemas import CommonResponse
from app.schemas.persona import UserPersonaUpsert
from pydantic import BaseModel


class AdminPersonaUpdate(UserPersonaUpsert):
    is_default: bool = False


class BillingPlanChangeRequest(BaseModel):
    plan_code: str


class BillingAddonCreditRequest(BaseModel):
    quantity: int = 30
    price_krw: int = 4900


router = APIRouter()


def _fetch_wordpress_users() -> tuple[list[dict], str | None]:
    api_url = os.getenv("WORDPRESS_API_URL", "").rstrip("/")
    username = os.getenv("WORDPRESS_USERNAME", "")
    app_password = os.getenv("WORDPRESS_APP_PASSWORD", "")
    if not api_url or not username or not app_password:
        return [], "WordPress API 설정 없음"

    users: list[dict] = []
    page = 1
    try:
        with httpx.Client(auth=(username, app_password), timeout=15.0) as client:
            while page <= 20:
                response = client.get(
                    f"{api_url}/users",
                    params={"context": "edit", "per_page": 100, "page": page, "orderby": "id", "order": "asc"},
                )
                if response.status_code == 400 and "rest_user_invalid_page_number" in response.text:
                    break
                response.raise_for_status()
                batch = response.json()
                if not isinstance(batch, list):
                    return [], "WordPress 사용자 응답 형식 오류"
                users.extend(batch)
                total_pages = int(response.headers.get("X-WP-TotalPages", "1") or 1)
                if page >= total_pages or not batch:
                    break
                page += 1
        return users, None
    except Exception as exc:
        return [], f"WordPress 조회 실패: {exc}"



def _table_exists(db: Session, table_name: str) -> bool:
    row = db.execute(
        text("select name from sqlite_master where type='table' and name=:name"),
        {"name": table_name},
    ).first()
    return row is not None


def _first_mapping(db: Session, sql: str, params: dict) -> dict | None:
    row = db.execute(text(sql), params).mappings().first()
    return dict(row) if row else None



def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _require_billable_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="회원을 찾을 수 없습니다.")
    if user.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="관리자 계정은 과금 조작 대상에서 제외합니다.")
    return user


def _plan_by_code(db: Session, plan_code: str) -> dict:
    plan = _first_mapping(db, "select * from subscription_plans where code=:code and is_active=1", {"code": plan_code})
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="요금제를 찾을 수 없습니다.")
    return plan


def _ensure_billing_profile(db: Session, user_id: int, plan_code: str = "free") -> dict:
    profile = _first_mapping(db, "select * from member_billing_profiles where user_id=:user_id", {"user_id": user_id})
    if profile:
        return profile
    now = _now_text()
    db.execute(text("insert into member_billing_profiles (user_id,current_plan_code,subscription_status,free_signup_credit_given,created_at,updated_at) values (:user_id,:plan_code,'inactive',0,:now,:now)"), {"user_id": user_id, "plan_code": plan_code, "now": now})
    db.flush()
    return _first_mapping(db, "select * from member_billing_profiles where user_id=:user_id", {"user_id": user_id}) or {}


def _grant_wallet_credit(db: Session, user_id: int, amount: int, credit_type: str, source_ref: str, note: str) -> None:
    now = _now_text()
    db.execute(text("insert into video_credit_wallets (user_id,credit_type,available_amount,reserved_amount,source_ref,created_at,updated_at) values (:user_id,:credit_type,:amount,0,:source_ref,:now,:now)"), {"user_id": user_id, "credit_type": credit_type, "amount": int(amount), "source_ref": source_ref, "now": now})
    wallet_id = db.execute(text("select last_insert_rowid()")).scalar()
    balance = _credit_totals(db, user_id)["remaining"]
    db.execute(text("insert into video_credit_ledger (user_id,wallet_id,entry_type,amount,balance_after,source_ref,note,created_at) values (:user_id,:wallet_id,'grant',:amount,:balance,:source_ref,:note,:now)"), {"user_id": user_id, "wallet_id": wallet_id, "amount": int(amount), "balance": int(balance), "source_ref": source_ref, "note": note, "now": now})


def _credit_totals(db: Session, user_id: int) -> dict:
    if not _table_exists(db, "video_credit_wallets"):
        return {"total_granted": 0, "total_used": 0, "remaining": 0}
    row = _first_mapping(
        db,
        """
        select
          coalesce(sum(available_amount + reserved_amount), 0) as total_granted,
          coalesce(sum(reserved_amount), 0) as total_used,
          coalesce(sum(available_amount), 0) as remaining
        from video_credit_wallets
        where user_id = :user_id
        """,
        {"user_id": user_id},
    ) or {}
    return {
        "total_granted": int(row.get("total_granted") or 0),
        "total_used": int(row.get("total_used") or 0),
        "remaining": int(row.get("remaining") or 0),
    }


def _billing_summary(db: Session, user: User) -> dict:
    fallback_plan = (getattr(user, "tier", None) or "free").strip() or "free"
    profile = None
    plan = None
    if _table_exists(db, "member_billing_profiles"):
        profile = _first_mapping(db, "select * from member_billing_profiles where user_id = :user_id", {"user_id": user.id})
    plan_code = (profile or {}).get("current_plan_code") or fallback_plan
    if _table_exists(db, "subscription_plans"):
        plan = _first_mapping(db, "select * from subscription_plans where code = :code", {"code": plan_code})
    credits = _credit_totals(db, user.id)
    plan_items = []
    if _table_exists(db, "subscription_plans"):
        rows = db.execute(text("select code,name,monthly_price_krw,base_video_credits,business_limit,rollover_percent,archive_item_limit,addon_purchase_allowed from subscription_plans where is_active=1 order by sort_order, id")).mappings().all()
        plan_items = [dict(row) for row in rows]
    base_credits = int((plan or {}).get("base_video_credits") or 0)
    carryover_percent = int((plan or {}).get("rollover_percent") or 0)
    archive_item_limit = None if str(user.role or "").lower() == "admin" else int((plan or {}).get("archive_item_limit") or 10)
    return {
        "user_id": user.id,
        "username": user.username,
        "plan_code": plan_code,
        "plan_name": (plan or {}).get("name") or plan_code,
        "subscription_status": (profile or {}).get("subscription_status") or "inactive",
        "current_period_started_at": (profile or {}).get("current_period_started_at"),
        "current_period_ends_at": (profile or {}).get("current_period_ends_at"),
        "free_signup_credit_given": bool((profile or {}).get("free_signup_credit_given") or False),
        "base_video_credits": base_credits,
        "total_granted": credits["total_granted"],
        "total_used": credits["total_used"],
        "remaining_credits": credits["remaining"],
        "carryover_percent": carryover_percent,
        "archive_item_limit": archive_item_limit,
        "archive_unlimited": archive_item_limit is None,
        "addon_allowed": bool((plan or {}).get("addon_purchase_allowed") or False),
        "plans": plan_items,
        "readonly": False,
    }


@router.get("/admin/members", response_model=CommonResponse)
def get_admin_members(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    persona_counts = dict(
        db.query(UserPersona.user_id, func.count(UserPersona.id))
        .group_by(UserPersona.user_id)
        .all()
    )
    project_counts = dict(
        db.query(Project.user_id, func.count(Project.id))
        .group_by(Project.user_id)
        .all()
    )

    users = db.query(User).order_by(User.id.desc()).all()
    primary_personas = {}
    for persona in db.query(UserPersona).order_by(UserPersona.is_default.desc(), UserPersona.id.asc()).all():
        primary_personas.setdefault(persona.user_id, persona)

    items = []
    for user in users:
        wp_id = user.wordpress_user_id
        primary_persona = primary_personas.get(user.id)
        items.append(
            {
                "status": "linked_id" if wp_id is not None else "local_only",
                "wordpress": {
                    "id": wp_id,
                    "username": user.username if wp_id is not None else None,
                    "exists": None,
                    "source": "local_link",
                },
                "storymaker": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "tier": user.tier,
                    "auth_provider": user.auth_provider,
                    "is_active": bool(user.is_active),
                    "created_at": user.created_at,
                    "last_login_at": user.last_login_at,
                "project_count": int(db.query(func.count(Project.id)).filter(Project.user_id == user.id).scalar() or 0),
                    "last_activity_at": user.last_activity_at,
                },
                "persona_count": int(persona_counts.get(user.id, 0)),
                "primary_persona": {
                    "company_name": primary_persona.company_name if primary_persona else None,
                    "phone_number": primary_persona.phone_number if primary_persona else None,
                    "region": primary_persona.region if primary_persona else None,
                    "industry_key": primary_persona.industry_key if primary_persona else None,
                } if primary_persona else None,
                "project_count": int(project_counts.get(user.id, 0)),
            }
        )

    wp_users, wp_error = _fetch_wordpress_users()
    wp_by_id = {int(user.get("id")): user for user in wp_users if user.get("id") is not None}
    local_wp_ids = set()

    for item in items:
        wp_id = item["wordpress"]["id"]
        if wp_id is None:
            continue
        local_wp_ids.add(int(wp_id))
        live = wp_by_id.get(int(wp_id))
        if live:
            item["status"] = "linked_ok"
            item["wordpress"] = {
                "id": live.get("id"),
                "username": live.get("username") or live.get("slug") or item["storymaker"]["username"],
                "name": live.get("name"),
                "email": live.get("email"),
                "roles": live.get("roles") or [],
                "registered_date": live.get("registered_date"),
                "exists": True,
                "source": "wordpress_live",
            }
        elif wp_users:
            item["status"] = "wordpress_missing"
            item["wordpress"]["exists"] = False
            item["wordpress"]["source"] = "wordpress_live"

    for wp_id, live in wp_by_id.items():
        if wp_id in local_wp_ids:
            continue
        items.append(
            {
                "status": "wordpress_only",
                "wordpress": {
                    "id": live.get("id"),
                    "username": live.get("username") or live.get("slug"),
                    "name": live.get("name"),
                    "email": live.get("email"),
                    "roles": live.get("roles") or [],
                    "registered_date": live.get("registered_date"),
                    "exists": True,
                    "source": "wordpress_live",
                },
                "storymaker": None,
                "persona_count": 0,
                "project_count": 0,
            }
        )

    linked_count = sum(1 for item in items if item["status"] == "linked_ok") if wp_users else sum(1 for item in items if item.get("wordpress", {}).get("id") is not None and item.get("storymaker"))
    local_only_count = sum(1 for item in items if item["status"] == "local_only")
    wordpress_missing_count = sum(1 for item in items if item["status"] == "wordpress_missing")
    wordpress_only_count = sum(1 for item in items if item["status"] == "wordpress_only")
    persona_user_count = sum(1 for item in items if item.get("persona_count", 0) > 0)

    return CommonResponse(
        ok=True,
        data={
            "summary": {
                "wordpress_linked_ids": linked_count,
                "storymaker_users": len(users),
                "linked_ids": linked_count,
                "local_only": local_only_count,
                "wordpress_missing": wordpress_missing_count if wp_users else None,
                "wordpress_only": wordpress_only_count if wp_users else None,
                "wordpress_users": len(wp_users) if wp_users else None,
                "persona_users": persona_user_count,
            },
            "items": items,
            "wordpress_live_connected": bool(wp_users),
            "wordpress_live_error": wp_error,
            "readonly": False,
        },
        message="",
    )


@router.get("/admin/members/{user_id}/billing-summary", response_model=CommonResponse)
def get_member_billing_summary(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
    return CommonResponse(ok=True, data=_billing_summary(db, user), message="")


@router.get("/admin/members/{user_id}/personas", response_model=CommonResponse)
def get_member_personas(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

    personas = (
        db.query(UserPersona)
        .filter(UserPersona.user_id == user_id)
        .order_by(UserPersona.is_default.desc(), UserPersona.updated_at.desc())
        .all()
    )
    return CommonResponse(
        ok=True,
        data={
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "tier": user.tier,
                "wordpress_user_id": user.wordpress_user_id,
                "created_at": user.created_at,
                "last_login_at": user.last_login_at,
            },
            "personas": [serialize_user_persona(persona) for persona in personas],
        },
        message="",
    )


@router.put("/admin/members/{user_id}/personas/{persona_id}", response_model=CommonResponse)
def update_member_persona(
    user_id: int,
    persona_id: int,
    req: AdminPersonaUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    persona = (
        db.query(UserPersona)
        .filter(UserPersona.id == persona_id, UserPersona.user_id == user_id)
        .first()
    )
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="페르소나를 찾을 수 없습니다.")

    (
        company_name,
        phone_number,
        website_url,
        region,
        industry_key,
        default_style,
        blog_content_length,
        default_tones,
        keywords,
        content,
    ) = clean_persona_payload(req)

    duplicate = (
        db.query(UserPersona)
        .filter(
            UserPersona.user_id == user_id,
            UserPersona.id != persona_id,
            func.lower(UserPersona.company_name) == company_name.lower(),
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="같은 업체명의 페르소나가 이미 있습니다.")

    import json

    persona.company_name = company_name
    persona.phone_number = phone_number
    persona.website_url = website_url
    persona.region = region
    persona.industry_key = industry_key
    persona.default_style = default_style
    persona.blog_content_length = blog_content_length
    persona.default_tones_json = json.dumps(default_tones, ensure_ascii=False)
    persona.keywords_json = json.dumps(keywords, ensure_ascii=False)
    persona.content = content
    if req.is_default:
        db.query(UserPersona).filter(
            UserPersona.user_id == user_id,
            UserPersona.id != persona_id,
        ).update({UserPersona.is_default: False}, synchronize_session=False)
        persona.is_default = True
    persona.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db.commit()
    db.refresh(persona)

    return CommonResponse(
        ok=True,
        data=serialize_user_persona(persona),
        message="페르소나가 저장되었습니다.",
    )

@router.post("/admin/members/{user_id}/billing/free-signup-credit", response_model=CommonResponse)
def grant_member_free_signup_credit(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    user = _require_billable_user(db, user_id)
    profile = _ensure_billing_profile(db, user.id, "free")
    if bool(profile.get("free_signup_credit_given")):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Free 최초 20회는 이미 지급되었습니다.")
    _grant_wallet_credit(db, user.id, 20, "free_signup", "free_signup_credit", "Free 최초 20회 지급")
    now = _now_text()
    db.execute(text("update member_billing_profiles set current_plan_code=coalesce(current_plan_code,'free'), free_signup_credit_given=1, free_signup_credit_given_at=:now, updated_at=:now where user_id=:user_id"), {"user_id": user.id, "now": now})
    db.commit()
    return CommonResponse(ok=True, data=_billing_summary(db, user), message="Free 최초 20회를 지급했습니다.")


@router.put("/admin/members/{user_id}/billing/plan", response_model=CommonResponse)
def change_member_billing_plan(
    user_id: int,
    req: BillingPlanChangeRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    user = _require_billable_user(db, user_id)
    plan_code = (req.plan_code or "").strip().lower()
    plan = _plan_by_code(db, plan_code)
    profile = _ensure_billing_profile(db, user.id, plan_code)
    current_plan = profile.get("current_plan_code")
    now = _now_text()
    db.execute(text("update member_billing_profiles set current_plan_code=:plan_code, subscription_status=:status, current_period_started_at=:now, current_period_ends_at=null, updated_at=:now where user_id=:user_id"), {"user_id": user.id, "plan_code": plan_code, "status": "active" if plan_code != "free" else "inactive", "now": now})
    grant_amount = int(plan.get("base_video_credits") or 0)
    if current_plan != plan_code and grant_amount > 0:
        _grant_wallet_credit(db, user.id, grant_amount, "plan_base", f"plan:{plan_code}", f"{plan.get('name') or plan_code} 기본 제공량 지급")
    db.commit()
    return CommonResponse(ok=True, data=_billing_summary(db, user), message="요금제를 변경했습니다.")


@router.post("/admin/members/{user_id}/billing/addon-credit", response_model=CommonResponse)
def grant_member_addon_credit(
    user_id: int,
    req: BillingAddonCreditRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    user = _require_billable_user(db, user_id)
    profile = _ensure_billing_profile(db, user.id, "free")
    plan = _plan_by_code(db, str(profile.get("current_plan_code") or "free"))
    if not bool(plan.get("addon_purchase_allowed")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="추가충전은 유료 회원만 가능합니다.")
    quantity = int(req.quantity or 30)
    price = int(req.price_krw or 4900)
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="충전 수량이 올바르지 않습니다.")
    now = _now_text()
    source_ref = f"addon:{now}:{quantity}"
    _grant_wallet_credit(db, user.id, quantity, "addon", source_ref, f"추가충전 {quantity}회 / {price:,}원")
    db.execute(text("insert into addon_purchases (user_id,credits,price_krw,status,purchased_at,created_at,updated_at) values (:user_id,:credits,:price,'paid',:now,:now,:now)"), {"user_id": user.id, "credits": quantity, "price": price, "now": now})
    db.commit()
    return CommonResponse(ok=True, data=_billing_summary(db, user), message="추가충전을 지급했습니다.")

