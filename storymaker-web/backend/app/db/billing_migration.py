from sqlalchemy import inspect, text


def migrate_billing_credit_tables(engine) -> None:
    """Create the idempotent tables/indexes used by monthly video credits."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "video_credit_usage" not in inspector.get_table_names():
            connection.execute(text("""
                CREATE TABLE video_credit_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    job_type TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    wallet_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'reserved',
                    amount INTEGER NOT NULL DEFAULT 1,
                    reserved_at TEXT,
                    consumed_at TEXT,
                    released_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_video_credit_usage_job "
            "ON video_credit_usage(job_type, job_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_video_credit_usage_user_status "
            "ON video_credit_usage(user_id, status)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_video_credit_wallets_user_expiry "
            "ON video_credit_wallets(user_id, expires_at)"
        ))

        # 기존 Free 전환 시 지급된 plan:free 20회를 새로 더 지급하지 않고
        # 현재 월 기본량으로 재분류한다. 이미 free_monthly가 있으면 건드리지 않는다.
        connection.execute(text("""
            UPDATE member_billing_profiles
            SET current_period_started_at = COALESCE(current_period_started_at, datetime('now', 'localtime')),
                current_period_ends_at = COALESCE(current_period_ends_at, datetime('now', 'localtime', '+1 month')),
                next_billing_at = COALESCE(next_billing_at, datetime('now', 'localtime', '+1 month')),
                updated_at = datetime('now', 'localtime')
            WHERE lower(COALESCE(current_plan_code, 'free')) = 'free'
        """))
        connection.execute(text("""
            UPDATE video_credit_wallets
            SET credit_type = 'free_monthly',
                expires_at = COALESCE(
                    (SELECT current_period_ends_at
                     FROM member_billing_profiles
                     WHERE member_billing_profiles.user_id = video_credit_wallets.user_id),
                    datetime('now', 'localtime', '+1 month')
                ),
                source_ref = 'free_monthly:migrated:' || user_id || ':' || id,
                updated_at = datetime('now', 'localtime')
            WHERE id IN (
                SELECT candidate.id
                FROM video_credit_wallets AS candidate
                JOIN member_billing_profiles AS profile ON profile.user_id = candidate.user_id
                WHERE lower(COALESCE(profile.current_plan_code, 'free')) = 'free'
                  AND candidate.credit_type = 'plan_base'
                  AND candidate.source_ref = 'plan:free'
                  AND candidate.available_amount <= 20
                  AND NOT EXISTS (
                      SELECT 1 FROM video_credit_wallets AS monthly
                      WHERE monthly.user_id = candidate.user_id
                        AND monthly.credit_type = 'free_monthly'
                  )
                GROUP BY candidate.user_id
            )
        """))
