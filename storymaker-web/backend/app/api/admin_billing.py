# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import get_admin_user
from app.db.database import get_db
from app.db.models import User
from app.schemas import CommonResponse

router = APIRouter()


class AdminBillingPlanUpdate(BaseModel):
    plan_code: str


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    return user


def _ensure_profile(db: Session, user: User, plan_code: str = "free") -> bool:
    exists = db.execute(text("SELECT 1 FROM member_billing_profiles WHERE user_id=:user_id"), {"user_id": user.id}).first()
    if exists:
        return False
    now = _now()
    db.execute(text("""
        INSERT INTO member_billing_profiles (
            user_id, current_plan_code, subscription_status,
            current_period_started_at, created_at, updated_at
        ) VALUES (:user_id, :plan_code, :status, :now, :now, :now)
    """), {"user_id": user.id, "plan_code": plan_code, "status": "free" if plan_code == "free" else "active", "now": now})
    return True


def _credit_totals(db: Session, user_id: int) -> dict:
    row = db.execute(text("""
        SELECT COALESCE(SUM(available_amount),0) AS available,
               COALESCE(SUM(reserved_amount),0) AS reserved
        FROM video_credit_wallets WHERE user_id=:user_id
    """), {"user_id": user_id}).mappings().first()
    wallets = db.execute(text("""
        SELECT id, credit_type, available_amount, reserved_amount, expires_at, source_ref, created_at
        FROM video_credit_wallets WHERE user_id=:user_id ORDER BY id DESC
    """), {"user_id": user_id}).mappings().all()
    return {"available": int(row["available"] or 0), "reserved": int(row["reserved"] or 0), "wallets": [dict(item) for item in wallets]}


@router.get("/admin/members/{user_id}/billing", response_model=CommonResponse)
def get_member_billing(user_id: int, db: Session = Depends(get_db), admin_user: User = Depends(get_admin_user)):
    user = _get_user(db, user_id)
    profile = db.execute(text("""
        SELECT mbp.user_id, mbp.current_plan_code AS plan_code, mbp.subscription_status,
               mbp.current_period_started_at, mbp.current_period_ends_at, mbp.next_billing_at,
               mbp.free_signup_credit_given, mbp.free_signup_credit_given_at,
               mbp.profile_completed_reward_given, mbp.profile_completed_reward_given_at,
               mbp.admin_note, sp.name AS plan_name, sp.monthly_price_krw,
               sp.base_video_credits, sp.business_limit, sp.rollover_percent,
               sp.retention_days, sp.addon_purchase_allowed
        FROM member_billing_profiles mbp
        LEFT JOIN subscription_plans sp ON sp.code=mbp.current_plan_code
        WHERE mbp.user_id=:user_id
    """), {"user_id": user_id}).mappings().first()
    plans = db.execute(text("""
        SELECT code, name, monthly_price_krw, base_video_credits, business_limit,
               rollover_percent, retention_days, addon_purchase_allowed
        FROM subscription_plans WHERE is_active=1 ORDER BY sort_order, id
    """)).mappings().all()
    addons = db.execute(text("SELECT * FROM addon_purchases WHERE user_id=:user_id ORDER BY id DESC"), {"user_id": user_id}).mappings().all()
    rewards = db.execute(text("SELECT * FROM community_reward_submissions WHERE user_id=:user_id ORDER BY id DESC"), {"user_id": user_id}).mappings().all()
    return CommonResponse(ok=True, data={
        "user": {"id": user.id, "username": user.username, "role": user.role, "legacy_tier": user.tier},
        "billing_profile": dict(profile) if profile else None,
        "plans": [dict(row) for row in plans],
        "credits": _credit_totals(db, user_id),
        "addon_purchases": [dict(row) for row in addons],
        "community_rewards": [dict(row) for row in rewards],
        "needs_billing_profile": profile is None,
    }, message="")


@router.post("/admin/members/{user_id}/billing/profile", response_model=CommonResponse)
def create_member_billing_profile(user_id: int, db: Session = Depends(get_db), admin_user: User = Depends(get_admin_user)):
    user = _get_user(db, user_id)
    if user.role == "admin":
        return CommonResponse(ok=True, data={"created": False}, message="관리자 계정은 무제한으로 처리됩니다.")
    created = _ensure_profile(db, user)
    db.commit()
    return CommonResponse(ok=True, data={"created": created}, message="과금 프로필을 생성했습니다." if created else "이미 과금 프로필이 있습니다.")


@router.post("/admin/members/{user_id}/billing/free-signup-credit", response_model=CommonResponse)
def grant_free_signup_credit(user_id: int, db: Session = Depends(get_db), admin_user: User = Depends(get_admin_user)):
    user = _get_user(db, user_id)
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="관리자 계정에는 Free 횟수를 지급하지 않습니다.")
    _ensure_profile(db, user, "free")
    profile = db.execute(text("SELECT free_signup_credit_given FROM member_billing_profiles WHERE user_id=:user_id"), {"user_id": user_id}).mappings().first()
    if profile and profile["free_signup_credit_given"]:
        raise HTTPException(status_code=409, detail="Free 최초 횟수가 이미 지급되었습니다.")
    now = _now()
    result = db.execute(text("""
        INSERT INTO video_credit_wallets (user_id, credit_type, available_amount, reserved_amount, source_ref, created_at, updated_at)
        VALUES (:user_id, 'free_signup', 20, 0, 'free_signup_once', :now, :now)
    """), {"user_id": user_id, "now": now})
    wallet_id = result.lastrowid
    db.execute(text("""
        INSERT INTO video_credit_ledger (user_id, wallet_id, entry_type, amount, balance_after, source_ref, note, created_at)
        VALUES (:user_id, :wallet_id, 'grant', 20, 20, 'free_signup_once', 'Free 최초 20회 지급', :now)
    """), {"user_id": user_id, "wallet_id": wallet_id, "now": now})
    db.execute(text("""
        UPDATE member_billing_profiles SET free_signup_credit_given=1,
            free_signup_credit_given_at=:now, updated_at=:now WHERE user_id=:user_id
    """), {"user_id": user_id, "now": now})
    db.commit()
    return CommonResponse(ok=True, data={"amount": 20, "balance": _credit_totals(db, user_id)["available"]}, message="Free 최초 20회를 지급했습니다.")


@router.put("/admin/members/{user_id}/billing/plan", response_model=CommonResponse)
def update_billing_plan(user_id: int, req: AdminBillingPlanUpdate, db: Session = Depends(get_db), admin_user: User = Depends(get_admin_user)):
    user = _get_user(db, user_id)
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="관리자 계정은 요금제 변경 대상이 아닙니다.")
    plan_code = req.plan_code.strip().lower()
    plan = db.execute(text("SELECT * FROM subscription_plans WHERE code=:code AND is_active=1"), {"code": plan_code}).mappings().first()
    if not plan:
        raise HTTPException(status_code=400, detail="유효하지 않은 요금제입니다.")
    _ensure_profile(db, user, plan_code)
    current = db.execute(text("""
        SELECT current_plan_code, current_period_ends_at
        FROM member_billing_profiles WHERE user_id=:user_id
    """), {"user_id": user_id}).mappings().first()
    if current and current["current_plan_code"] == plan_code and current["current_period_ends_at"]:
        try:
            if datetime.fromisoformat(str(current["current_period_ends_at"]).replace(" ", "T")) > datetime.now():
                db.commit()
                return CommonResponse(
                    ok=True,
                    data={"plan_code": plan_code, "unchanged": True, "next_billing_at": current["current_period_ends_at"]},
                    message="같은 요금제의 이용 기간이 남아 있어 기본 횟수를 다시 지급하지 않았습니다.",
                )
        except ValueError:
            pass
    now_dt = datetime.now()
    now = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    ends_at = None if plan_code == "free" else (now_dt + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(text("""
        UPDATE member_billing_profiles SET current_plan_code=:plan_code,
            subscription_status=:subscription_status, current_period_started_at=:now,
            current_period_ends_at=:ends_at, next_billing_at=:ends_at, updated_at=:now
        WHERE user_id=:user_id
    """), {"plan_code": plan_code, "subscription_status": "free" if plan_code == "free" else "active", "now": now, "ends_at": ends_at, "user_id": user_id})
    base_amount = int(plan["base_video_credits"] or 0)
    if base_amount > 0:
        db.execute(text("""
            INSERT INTO video_credit_wallets (user_id, credit_type, available_amount, reserved_amount, expires_at, source_ref, created_at, updated_at)
            VALUES (:user_id, 'plan_base', :amount, 0, :expires_at, :source_ref, :now, :now)
        """), {"user_id": user_id, "amount": base_amount, "expires_at": ends_at, "source_ref": f"plan:{plan_code}:{now}", "now": now})
    db.commit()
    return CommonResponse(ok=True, data={"plan_code": plan_code, "plan_name": plan["name"], "base_video_credits": base_amount, "next_billing_at": ends_at}, message=f"{plan['name']} 요금제로 변경했습니다.")
