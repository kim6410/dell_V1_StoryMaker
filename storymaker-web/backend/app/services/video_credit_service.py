from __future__ import annotations

from calendar import monthrange
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session


FREE_MONTHLY_AMOUNT = 20


def _now_text(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _add_one_month(value: datetime) -> datetime:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def ensure_free_monthly_cycle(db: Session, user_id: int, role: str = "user", now: datetime | None = None) -> dict:
    now_dt = now or datetime.now()
    now_text = _now_text(now_dt)
    if str(role or "").lower() == "admin":
        return {"unlimited": True, "remaining": None, "period_start": None, "period_end": None}

    profile = db.execute(text(
        "SELECT current_plan_code,current_period_started_at,current_period_ends_at "
        "FROM member_billing_profiles WHERE user_id=:user_id"
    ), {"user_id": user_id}).mappings().first()
    if not profile:
        db.execute(text("""
            INSERT INTO member_billing_profiles
            (user_id,current_plan_code,subscription_status,free_signup_credit_given,created_at,updated_at)
            VALUES (:user_id,'free','inactive',1,:now,:now)
        """), {"user_id": user_id, "now": now_text})
        profile = {"current_plan_code": "free", "current_period_started_at": None, "current_period_ends_at": None}

    if str(profile.get("current_plan_code") or "free").lower() != "free":
        return credit_summary(db, user_id, role, now_dt)

    period_start = _parse_datetime(profile.get("current_period_started_at"))
    period_end = _parse_datetime(profile.get("current_period_ends_at"))
    if period_start is None or period_end is None or now_dt >= period_end:
        period_start = now_dt
        period_end = _add_one_month(period_start)
        start_text = _now_text(period_start)
        end_text = _now_text(period_end)
        source_ref = f"free_monthly:{user_id}:{period_start.strftime('%Y%m%d%H%M%S')}"
        db.execute(text("""
            UPDATE member_billing_profiles
            SET current_plan_code='free',subscription_status='inactive',
                current_period_started_at=:period_start,current_period_ends_at=:period_end,
                next_billing_at=:period_end,free_signup_credit_given=1,updated_at=:now
            WHERE user_id=:user_id
        """), {"user_id": user_id, "period_start": start_text, "period_end": end_text, "now": now_text})
        db.execute(text("""
            UPDATE video_credit_wallets
            SET expires_at=COALESCE(expires_at,:now),updated_at=:now
            WHERE user_id=:user_id AND credit_type='free_monthly'
              AND (expires_at IS NULL OR expires_at<=:now)
        """), {"user_id": user_id, "now": now_text})
        exists = db.execute(text(
            "SELECT id FROM video_credit_wallets WHERE user_id=:user_id AND source_ref=:source_ref LIMIT 1"
        ), {"user_id": user_id, "source_ref": source_ref}).first()
        if not exists:
            result = db.execute(text("""
                INSERT INTO video_credit_wallets
                (user_id,credit_type,available_amount,reserved_amount,expires_at,source_ref,created_at,updated_at)
                VALUES (:user_id,'free_monthly',:amount,0,:expires_at,:source_ref,:now,:now)
            """), {"user_id": user_id, "amount": FREE_MONTHLY_AMOUNT, "expires_at": end_text, "source_ref": source_ref, "now": now_text})
            wallet_id = result.lastrowid
            db.execute(text("""
                INSERT INTO video_credit_ledger
                (user_id,wallet_id,entry_type,amount,balance_after,source_ref,note,created_at)
                VALUES (:user_id,:wallet_id,'grant',:amount,:amount,:source_ref,'Free 월 20회 지급',:now)
            """), {"user_id": user_id, "wallet_id": wallet_id, "amount": FREE_MONTHLY_AMOUNT, "source_ref": source_ref, "now": now_text})
        db.flush()

    return credit_summary(db, user_id, role, now_dt)


def credit_summary(db: Session, user_id: int, role: str = "user", now: datetime | None = None) -> dict:
    if str(role or "").lower() == "admin":
        return {"unlimited": True, "remaining": None, "monthly_granted": None, "monthly_used": None}
    now_text = _now_text(now)
    profile = db.execute(text("""
        SELECT current_plan_code,current_period_started_at,current_period_ends_at,next_billing_at
        FROM member_billing_profiles WHERE user_id=:user_id
    """), {"user_id": user_id}).mappings().first() or {}
    row = db.execute(text("""
        SELECT
          COALESCE(SUM(CASE WHEN credit_type='free_monthly' THEN available_amount ELSE 0 END),0) AS monthly_available,
          COALESCE(SUM(CASE WHEN credit_type='free_monthly' THEN reserved_amount ELSE 0 END),0) AS monthly_reserved,
          COALESCE(SUM(CASE WHEN credit_type!='free_monthly' THEN available_amount-reserved_amount ELSE 0 END),0) AS bonus_remaining,
          COALESCE(SUM(available_amount-reserved_amount),0) AS remaining
        FROM video_credit_wallets
        WHERE user_id=:user_id AND (expires_at IS NULL OR expires_at>:now)
    """), {"user_id": user_id, "now": now_text}).mappings().first() or {}
    monthly_available = int(row.get("monthly_available") or 0)
    monthly_reserved = int(row.get("monthly_reserved") or 0)
    monthly_remaining = max(0, monthly_available - monthly_reserved)
    return {
        "unlimited": False,
        "plan_code": profile.get("current_plan_code") or "free",
        "period_start": profile.get("current_period_started_at"),
        "period_end": profile.get("current_period_ends_at"),
        "next_reset_at": profile.get("next_billing_at") or profile.get("current_period_ends_at"),
        "monthly_granted": FREE_MONTHLY_AMOUNT if str(profile.get("current_plan_code") or "free").lower() == "free" else monthly_available,
        "monthly_used": max(0, FREE_MONTHLY_AMOUNT - monthly_available),
        "monthly_reserved": monthly_reserved,
        "monthly_remaining": monthly_remaining,
        "bonus_remaining": int(row.get("bonus_remaining") or 0),
        "remaining": int(row.get("remaining") or 0),
    }


def reserve_credit(db: Session, user_id: int, role: str, job_type: str, job_id: str) -> dict:
    summary = ensure_free_monthly_cycle(db, user_id, role)
    if summary.get("unlimited"):
        return {"status": "unlimited", "job_type": job_type, "job_id": job_id}
    existing = db.execute(text(
        "SELECT * FROM video_credit_usage WHERE job_type=:job_type AND job_id=:job_id"
    ), {"job_type": job_type, "job_id": job_id}).mappings().first()
    if existing:
        return dict(existing)
    now = _now_text()
    wallet = db.execute(text("""
        SELECT id FROM video_credit_wallets
        WHERE user_id=:user_id AND available_amount-reserved_amount>0
          AND (expires_at IS NULL OR expires_at>:now)
        ORDER BY CASE WHEN credit_type='free_monthly' THEN 0 ELSE 1 END, expires_at ASC, id ASC
        LIMIT 1
    """), {"user_id": user_id, "now": now}).mappings().first()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="이번 달 무료 제작 20회를 모두 사용했습니다.")
    wallet_id = int(wallet["id"])
    db.execute(text("UPDATE video_credit_wallets SET reserved_amount=reserved_amount+1,updated_at=:now WHERE id=:wallet_id"), {"wallet_id": wallet_id, "now": now})
    db.execute(text("""
        INSERT INTO video_credit_usage
        (user_id,job_type,job_id,wallet_id,status,amount,reserved_at,created_at,updated_at)
        VALUES (:user_id,:job_type,:job_id,:wallet_id,'reserved',1,:now,:now,:now)
    """), {"user_id": user_id, "job_type": job_type, "job_id": job_id, "wallet_id": wallet_id, "now": now})
    db.flush()
    return {"status": "reserved", "wallet_id": wallet_id, "job_type": job_type, "job_id": job_id}


def consume_credit(db: Session, user_id: int, job_type: str, job_id: str) -> dict:
    usage = db.execute(text("""
        SELECT * FROM video_credit_usage
        WHERE user_id=:user_id AND job_type=:job_type AND job_id=:job_id
    """), {"user_id": user_id, "job_type": job_type, "job_id": job_id}).mappings().first()
    if not usage or usage.get("status") == "consumed":
        return dict(usage or {"status": "not_reserved"})
    if usage.get("status") != "reserved":
        return dict(usage)
    now = _now_text()
    wallet_id = int(usage["wallet_id"])
    db.execute(text("""
        UPDATE video_credit_wallets
        SET available_amount=available_amount-1,reserved_amount=MAX(0,reserved_amount-1),updated_at=:now
        WHERE id=:wallet_id AND available_amount>0
    """), {"wallet_id": wallet_id, "now": now})
    remaining = db.execute(text("""
        SELECT COALESCE(SUM(available_amount-reserved_amount),0)
        FROM video_credit_wallets WHERE user_id=:user_id AND (expires_at IS NULL OR expires_at>:now)
    """), {"user_id": user_id, "now": now}).scalar() or 0
    db.execute(text("""
        UPDATE video_credit_usage SET status='consumed',consumed_at=:now,updated_at=:now WHERE id=:id
    """), {"id": usage["id"], "now": now})
    db.execute(text("""
        INSERT INTO video_credit_ledger
        (user_id,wallet_id,entry_type,amount,balance_after,source_ref,note,created_at)
        VALUES (:user_id,:wallet_id,'use',-1,:balance,:source_ref,'동영상 제작 완료 차감',:now)
    """), {"user_id": user_id, "wallet_id": wallet_id, "balance": int(remaining), "source_ref": f"{job_type}:{job_id}", "now": now})
    db.flush()
    return {"status": "consumed", "remaining": int(remaining)}


def release_credit(db: Session, user_id: int, job_type: str, job_id: str) -> dict:
    usage = db.execute(text("""
        SELECT * FROM video_credit_usage
        WHERE user_id=:user_id AND job_type=:job_type AND job_id=:job_id
    """), {"user_id": user_id, "job_type": job_type, "job_id": job_id}).mappings().first()
    if not usage or usage.get("status") != "reserved":
        return dict(usage or {"status": "not_reserved"})
    now = _now_text()
    db.execute(text("UPDATE video_credit_wallets SET reserved_amount=MAX(0,reserved_amount-1),updated_at=:now WHERE id=:wallet_id"), {"wallet_id": usage["wallet_id"], "now": now})
    db.execute(text("UPDATE video_credit_usage SET status='released',released_at=:now,updated_at=:now WHERE id=:id"), {"id": usage["id"], "now": now})
    db.flush()
    return {"status": "released"}
