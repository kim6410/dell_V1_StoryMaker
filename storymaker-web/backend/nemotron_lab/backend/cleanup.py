from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .usage_store import clear_detailed_content, ensure_data_dirs


KST = ZoneInfo("Asia/Seoul")
_STARTED = False
_LOCK = threading.Lock()


def purge_daily_content() -> dict:
    ensure_data_dirs()
    result = clear_detailed_content()
    return {
        "ok": True,
        "scope": "nemotron-lab/data only",
        "usage_aggregate_preserved": True,
        "purged_at": datetime.now(KST).isoformat(timespec="seconds"),
        **result,
    }


def _seconds_until_next_purge() -> float:
    now = datetime.now(KST)
    target = now.replace(hour=23, minute=59, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


def _cleanup_loop() -> None:
    while True:
        time.sleep(_seconds_until_next_purge())
        try:
            purge_daily_content()
        except Exception as exc:
            print(f"[nemotron-lab] daily purge failed: {type(exc).__name__}: {exc}")
        time.sleep(65)


def start_cleanup_scheduler() -> None:
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        _STARTED = True
        ensure_data_dirs()
        thread = threading.Thread(target=_cleanup_loop, name="nemotron-lab-daily-purge", daemon=True)
        thread.start()
