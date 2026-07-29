from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
import json
import os
import sqlite3
import subprocess

from fastapi import HTTPException, status

BETA_ROOT = Path(os.getenv("STORYMAKER_BETA_ROOT", "/home/bourne/StoryMaker_1/StoryMaker_beta"))
BETA_DB = BETA_ROOT / "data" / "storymaker_beta.db"
V1_DB = Path(os.getenv("STORYMAKER_V1_DB", "/home/bourne/StoryMaker_1/database/storymaker.db"))
FFPROBE = Path(os.getenv("STORYMAKER_BETA_FFPROBE", "/usr/bin/ffprobe"))
FREE_MONTHLY_LIMIT = 20
USAGE_RESERVATION_TTL_SECONDS = 2 * 60 * 60


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_mp4_usage_table(connection: sqlite3.Connection | None = None) -> None:
    owns_connection = connection is None
    db = connection or sqlite3.connect(BETA_DB)
    try:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS beta_mp4_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                beta_job_id TEXT NOT NULL,
                owner_user_id INTEGER,
                output_type TEXT NOT NULL,
                mp4_status TEXT NOT NULL DEFAULT '',
                mp4_verified INTEGER NOT NULL DEFAULT 0,
                mp4_size_bytes INTEGER NOT NULL DEFAULT 0,
                mp4_duration_seconds REAL NOT NULL DEFAULT 0,
                mp4_width INTEGER NOT NULL DEFAULT 0,
                mp4_height INTEGER NOT NULL DEFAULT 0,
                mp4_codec TEXT NOT NULL DEFAULT '',
                mp4_relative_path TEXT NOT NULL DEFAULT '',
                mp4_validation_result TEXT NOT NULL DEFAULT '',
                mp4_created_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(beta_job_id, output_type)
            )
            """
        )
        columns = {str(row[1]) for row in db.execute("PRAGMA table_info(beta_mp4_usage)").fetchall()}
        if "credit_wallet_id" not in columns:
            db.execute("ALTER TABLE beta_mp4_usage ADD COLUMN credit_wallet_id INTEGER")
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_beta_mp4_usage_owner_created ON beta_mp4_usage(owner_user_id, mp4_created_at)"
        )
        if owns_connection:
            db.commit()
    finally:
        if owns_connection:
            db.close()


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_account_datetime(value: Any) -> datetime | None:
    """V1 DB의 시간대 없는 가입·결제 시각은 한국시간으로 해석합니다."""
    parsed = _parse_datetime(value)
    if not parsed:
        return None
    raw = str(value or "")
    if parsed.tzinfo == timezone.utc and not ("Z" in raw or "+" in raw[10:] or raw.endswith("+00:00")):
        naive = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return naive.replace(tzinfo=ZoneInfo("Asia/Seoul")).astimezone(timezone.utc)
    return parsed.astimezone(timezone.utc)


def _account_profile(user_id: int) -> dict[str, Any]:
    """V1 회원 가입일과 현재 요금제·갱신 만료일을 읽습니다."""
    default = {
        "plan_code": "free",
        "subscription_status": "inactive",
        "account_role": "user",
        "signup_at": None,
        "billing_period_end": None,
    }
    if not V1_DB.exists():
        return default
    with sqlite3.connect(f"file:{V1_DB}?mode=ro", uri=True, timeout=3) as connection:
        connection.row_factory = sqlite3.Row
        user = connection.execute(
            "SELECT created_at,tier,role FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        billing = connection.execute(
            "SELECT current_plan_code,subscription_status,current_period_ends_at "
            "FROM member_billing_profiles WHERE user_id=?",
            (user_id,),
        ).fetchone()
    plan_code = str(
        (billing["current_plan_code"] if billing else None)
        or (user["tier"] if user else None)
        or "free"
    ).strip().lower()
    return {
        "plan_code": plan_code,
        "subscription_status": str(billing["subscription_status"] if billing else "inactive").strip().lower(),
        "account_role": str(user["role"] if user else "user").strip().lower(),
        "signup_at": user["created_at"] if user else None,
        "billing_period_end": billing["current_period_ends_at"] if billing else None,
    }


def _signup_period(signup_at: datetime, now_dt: datetime) -> tuple[datetime, datetime]:
    """가입 시각을 기준으로 연속된 30일 이용기간을 계산합니다."""
    if now_dt < signup_at:
        return signup_at, signup_at + timedelta(days=30)
    period_index = int((now_dt - signup_at).total_seconds() // timedelta(days=30).total_seconds())
    period_start = signup_at + timedelta(days=period_index * 30)
    return period_start, period_start + timedelta(days=30)


def monthly_usage_summary(user_id: int, role: str = "user", now: datetime | None = None) -> dict[str, Any]:
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    else:
        now_dt = now_dt.astimezone(timezone.utc)
    profile = _account_profile(user_id)
    if str(role or "").lower() == "admin" or str(profile.get("account_role") or "").lower() == "admin":
        return {
            "unlimited": True, "access_allowed": True, "plan_code": "admin",
            "used": 0, "remaining": None, "limit": None,
            "period_start": None, "period_end": None,
        }

    signup_at = _parse_account_datetime(profile.get("signup_at"))
    if not signup_at:
        raise RuntimeError("사용자 가입일을 확인할 수 없습니다.")
    plan_code = str(profile.get("plan_code") or "free").lower()

    if plan_code != "free":
        return {
            "unlimited": True,
            "access_allowed": True,
            "expired": False,
            "plan_code": plan_code,
            "used": 0,
            "remaining": None,
            "limit": None,
            "period_start": signup_at.isoformat(),
            "period_end": None,
        }

    period_start, period_end = _signup_period(signup_at, now_dt)
    with sqlite3.connect(BETA_DB) as connection:
        ensure_mp4_usage_table(connection)
        rows = connection.execute(
            "SELECT mp4_created_at FROM beta_mp4_usage "
            "WHERE owner_user_id=? AND mp4_status='completed' AND mp4_verified=1",
            (user_id,),
        ).fetchall()
    used = sum(
        1 for row in rows
        if (created := _parse_datetime(row[0])) and period_start <= created < period_end
    )
    bonus_remaining = 0
    if V1_DB.exists():
        now_text = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(f"file:{V1_DB}?mode=ro", uri=True, timeout=3) as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(available_amount-reserved_amount),0) "
                "FROM video_credit_wallets "
                "WHERE user_id=? AND credit_type!='free_monthly' "
                "AND (expires_at IS NULL OR expires_at>?)",
                (user_id, now_text),
            ).fetchone()
        bonus_remaining = max(0, int((row or [0])[0] or 0))
    monthly_remaining = max(0, FREE_MONTHLY_LIMIT - used)
    return {
        "unlimited": False,
        "access_allowed": monthly_remaining > 0 or bonus_remaining > 0,
        "expired": False,
        "plan_code": "free",
        "used": used,
        "remaining": monthly_remaining + bonus_remaining,
        "monthly_remaining": monthly_remaining,
        "bonus_remaining": bonus_remaining,
        "limit": FREE_MONTHLY_LIMIT,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }


def enforce_generation_access(user_id: int, role: str) -> dict[str, Any]:
    """AI 원고 생성 직전에 무료 한도 또는 유료 이용기간 만료를 차단합니다."""
    summary = monthly_usage_summary(user_id, role)
    if summary.get("plan_code") == "admin":
        return summary
    if summary.get("plan_code") != "free":
        if not summary.get("access_allowed"):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="유료 이용기간 30일이 종료되었습니다. 이용기간을 갱신해 주세요.",
            )
        return summary
    if not summary.get("access_allowed"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"무료 30일 {FREE_MONTHLY_LIMIT}회와 추가 지급 횟수를 모두 사용했습니다.",
        )
    return summary


def enforce_monthly_limit(user_id: int, role: str, beta_job_id: str, output_type: str) -> dict[str, Any]:
    """기본 월 20회 소진 후에는 관리자 추가 지급 지갑을 1회 예약합니다."""
    if output_type not in {"archive", "shortform"}:
        raise ValueError("지원하지 않는 MP4 출력 유형입니다.")

    summary = monthly_usage_summary(user_id, role)
    if summary.get("unlimited"):
        return {**summary, "existing_usage": False, "reserved": False}

    period_start = _parse_datetime(summary.get("period_start"))
    period_end = _parse_datetime(summary.get("period_end"))
    if not period_start or not period_end:
        raise RuntimeError("사용량 집계 기간을 확인할 수 없습니다.")

    now_dt = datetime.now(timezone.utc)
    now_text = now_dt.isoformat()
    wallet_now_text = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    stale_before = (now_dt - timedelta(seconds=USAGE_RESERVATION_TTL_SECONDS)).isoformat()
    with sqlite3.connect(BETA_DB, timeout=30, isolation_level=None) as connection:
        ensure_mp4_usage_table(connection)
        connection.execute("ATTACH DATABASE ? AS v1db", (str(V1_DB),))
        connection.execute("BEGIN IMMEDIATE")
        try:
            stale_wallets = connection.execute(
                "SELECT credit_wallet_id FROM beta_mp4_usage "
                "WHERE mp4_status='reserved' AND mp4_verified=0 AND updated_at < ? "
                "AND credit_wallet_id IS NOT NULL",
                (stale_before,),
            ).fetchall()
            for (wallet_id,) in stale_wallets:
                connection.execute(
                    "UPDATE v1db.video_credit_wallets "
                    "SET reserved_amount=MAX(0,reserved_amount-1),updated_at=? WHERE id=?",
                    (wallet_now_text, int(wallet_id)),
                )
            connection.execute(
                "DELETE FROM beta_mp4_usage WHERE mp4_status='reserved' AND mp4_verified=0 AND updated_at < ?",
                (stale_before,),
            )

            existing = connection.execute(
                "SELECT mp4_status,mp4_verified,credit_wallet_id FROM beta_mp4_usage "
                "WHERE beta_job_id=? AND output_type=? LIMIT 1",
                (beta_job_id, output_type),
            ).fetchone()
            if existing:
                connection.commit()
                return {
                    **summary,
                    "existing_usage": bool(existing[0] == "completed" and int(existing[1] or 0) == 1),
                    "reserved": bool(existing[0] == "reserved"),
                    "credit_wallet_id": existing[2],
                }

            rows = connection.execute(
                "SELECT mp4_created_at,mp4_status,mp4_verified FROM beta_mp4_usage "
                "WHERE owner_user_id=? AND (mp4_status='reserved' OR (mp4_status='completed' AND mp4_verified=1))",
                (user_id,),
            ).fetchall()
            occupied = sum(
                1 for created_at, row_status, verified in rows
                if (created := _parse_datetime(created_at))
                and period_start <= created < period_end
                and (row_status == "reserved" or int(verified or 0) == 1)
            )

            credit_wallet_id = None
            if occupied >= FREE_MONTHLY_LIMIT:
                wallet = connection.execute(
                    "SELECT id FROM v1db.video_credit_wallets "
                    "WHERE user_id=? AND credit_type!='free_monthly' "
                    "AND available_amount-reserved_amount>0 "
                    "AND (expires_at IS NULL OR expires_at>?) "
                    "ORDER BY CASE WHEN expires_at IS NULL THEN 1 ELSE 0 END,expires_at ASC,id ASC LIMIT 1",
                    (user_id, wallet_now_text),
                ).fetchone()
                if not wallet:
                    connection.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail=f"무료 30일 {FREE_MONTHLY_LIMIT}회와 추가 지급 횟수를 모두 사용했습니다.",
                    )
                credit_wallet_id = int(wallet[0])
                connection.execute(
                    "UPDATE v1db.video_credit_wallets "
                    "SET reserved_amount=reserved_amount+1,updated_at=? WHERE id=?",
                    (wallet_now_text, credit_wallet_id),
                )

            connection.execute(
                """
                INSERT INTO beta_mp4_usage (
                    beta_job_id,owner_user_id,output_type,
                    mp4_status,mp4_verified,mp4_created_at,
                    created_at,updated_at,credit_wallet_id
                ) VALUES (?, ?, ?, 'reserved', 0, ?, ?, ?, ?)
                """,
                (beta_job_id, user_id, output_type, now_text, now_text, now_text, credit_wallet_id),
            )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.execute("DETACH DATABASE v1db")

    fresh = monthly_usage_summary(user_id, role)
    return {
        **fresh,
        "used": occupied,
        "existing_usage": False,
        "reserved": True,
        "credit_wallet_id": credit_wallet_id,
    }


def probe_mp4(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise ValueError("MP4 파일이 없습니다.")
    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise ValueError("MP4 파일 크기가 0입니다.")
    if not FFPROBE.exists():
        raise ValueError("ffprobe 실행 파일이 없습니다.")
    command = [
        str(FFPROBE),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height:format=duration",
        "-of", "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise ValueError(completed.stderr.strip() or "ffprobe 검증에 실패했습니다.")
    try:
        payload = json.loads(completed.stdout or "{}")
        stream = (payload.get("streams") or [{}])[0]
        duration = float((payload.get("format") or {}).get("duration") or 0)
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        codec = str(stream.get("codec_name") or "")
    except (TypeError, ValueError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError("MP4 메타데이터를 해석할 수 없습니다.") from exc
    if duration <= 0 or width <= 0 or height <= 0:
        raise ValueError("MP4 길이 또는 해상도가 올바르지 않습니다.")
    return {
        "mp4_status": "completed",
        "mp4_verified": 1,
        "mp4_size_bytes": size_bytes,
        "mp4_duration_seconds": round(duration, 3),
        "mp4_width": width,
        "mp4_height": height,
        "mp4_codec": codec,
        "mp4_validation_result": "verified",
    }


def record_verified_mp4(beta_job_id: str, output_type: str, path: Path) -> dict[str, Any]:
    if output_type not in {"archive", "shortform"}:
        raise ValueError("지원하지 않는 MP4 출력 유형입니다.")
    metadata = probe_mp4(path)
    created_at = now_iso()
    wallet_now_text = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    try:
        relative_path = str(path.resolve().relative_to(BETA_ROOT.resolve()))
    except ValueError:
        relative_path = str(path.resolve())
    with sqlite3.connect(BETA_DB, timeout=30, isolation_level=None) as connection:
        ensure_mp4_usage_table(connection)
        connection.execute("ATTACH DATABASE ? AS v1db", (str(V1_DB),))
        connection.execute("BEGIN IMMEDIATE")
        try:
            owner_row = connection.execute(
                "SELECT owner_user_id FROM beta_jobs WHERE beta_job_id=?",
                (beta_job_id,),
            ).fetchone()
            if owner_row is None:
                raise ValueError("Beta 작업 DB 기록을 찾을 수 없습니다.")
            owner_user_id = owner_row[0]
            existing = connection.execute(
                "SELECT mp4_status,mp4_verified,credit_wallet_id FROM beta_mp4_usage "
                "WHERE beta_job_id=? AND output_type=? LIMIT 1",
                (beta_job_id, output_type),
            ).fetchone()
            already_completed = bool(existing and existing[0] == "completed" and int(existing[1] or 0) == 1)
            credit_wallet_id = int(existing[2]) if existing and existing[2] is not None else None

            if credit_wallet_id is not None and not already_completed:
                changed = connection.execute(
                    "UPDATE v1db.video_credit_wallets "
                    "SET available_amount=available_amount-1,reserved_amount=MAX(0,reserved_amount-1),updated_at=? "
                    "WHERE id=? AND available_amount>0 AND reserved_amount>0",
                    (wallet_now_text, credit_wallet_id),
                ).rowcount
                if changed != 1:
                    raise RuntimeError("관리자 추가 지급 횟수 차감에 실패했습니다.")
                balance = connection.execute(
                    "SELECT COALESCE(SUM(available_amount-reserved_amount),0) "
                    "FROM v1db.video_credit_wallets WHERE user_id=? "
                    "AND (expires_at IS NULL OR expires_at>?)",
                    (owner_user_id, wallet_now_text),
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT INTO v1db.video_credit_ledger
                    (user_id,wallet_id,entry_type,amount,balance_after,source_ref,note,created_at)
                    VALUES (?,?,'use',-1,?,?,?,?)
                    """,
                    (
                        owner_user_id,
                        credit_wallet_id,
                        int(balance or 0),
                        f"beta:{output_type}:{beta_job_id}",
                        "Beta 동영상 제작 완료 추가 지급분 차감",
                        wallet_now_text,
                    ),
                )

            connection.execute(
                """
                INSERT INTO beta_mp4_usage (
                    beta_job_id,owner_user_id,output_type,
                    mp4_status,mp4_verified,mp4_size_bytes,
                    mp4_duration_seconds,mp4_width,mp4_height,
                    mp4_codec,mp4_relative_path,mp4_validation_result,
                    mp4_created_at,created_at,updated_at,credit_wallet_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(beta_job_id,output_type) DO UPDATE SET
                    owner_user_id=excluded.owner_user_id,
                    mp4_status=excluded.mp4_status,
                    mp4_verified=excluded.mp4_verified,
                    mp4_size_bytes=excluded.mp4_size_bytes,
                    mp4_duration_seconds=excluded.mp4_duration_seconds,
                    mp4_width=excluded.mp4_width,
                    mp4_height=excluded.mp4_height,
                    mp4_codec=excluded.mp4_codec,
                    mp4_relative_path=excluded.mp4_relative_path,
                    mp4_validation_result=excluded.mp4_validation_result,
                    mp4_created_at=excluded.mp4_created_at,
                    updated_at=excluded.updated_at,
                    credit_wallet_id=COALESCE(beta_mp4_usage.credit_wallet_id,excluded.credit_wallet_id)
                """,
                (
                    beta_job_id, owner_user_id, output_type,
                    metadata["mp4_status"], metadata["mp4_verified"], metadata["mp4_size_bytes"],
                    metadata["mp4_duration_seconds"], metadata["mp4_width"], metadata["mp4_height"],
                    metadata["mp4_codec"], relative_path, metadata["mp4_validation_result"],
                    created_at, created_at, created_at, credit_wallet_id,
                ),
            )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.execute("DETACH DATABASE v1db")
    return {
        "beta_job_id": beta_job_id,
        "owner_user_id": owner_user_id,
        "output_type": output_type,
        "credit_wallet_id": credit_wallet_id,
        **metadata,
        "mp4_relative_path": relative_path,
        "mp4_created_at": created_at,
    }
