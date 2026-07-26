from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")
DATA_ROOT = Path(os.getenv("NEMOTRON_LAB_DATA_DIR", "/opt/nemotron_lab/data"))
CONVERSATION_DIR = DATA_ROOT / "conversations"
USAGE_DIR = DATA_ROOT / "usage"
LOG_DIR = DATA_ROOT / "logs"
TOTALS_PATH = USAGE_DIR / "daily_totals.json"
_LOCK = threading.RLock()


def ensure_data_dirs() -> None:
    for directory in (CONVERSATION_DIR, USAGE_DIR, LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _today_key() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def record_request(record: dict[str, Any]) -> None:
    ensure_data_dirs()
    request_id = str(record.get("request_id") or "unknown")
    safe_id = "".join(ch for ch in request_id if ch.isalnum() or ch in "-_")[:100] or "unknown"
    with _LOCK:
        _write_json(CONVERSATION_DIR / f"{safe_id}.json", record)
        with (LOG_DIR / f"{_today_key()}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        totals = _read_json(TOTALS_PATH, {})
        day = totals.setdefault(_today_key(), {
            "requests": 0,
            "success": 0,
            "failed": 0,
            "timeouts": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "latency_ms_sum": 0,
        })
        day["requests"] += 1
        status = str(record.get("status") or "failed")
        if status == "completed":
            day["success"] += 1
        else:
            day["failed"] += 1
        if status == "timeout":
            day["timeouts"] += 1
        day["input_tokens"] += int(record.get("input_tokens") or 0)
        day["output_tokens"] += int(record.get("output_tokens") or 0)
        day["total_tokens"] += int(record.get("total_tokens") or 0)
        day["latency_ms_sum"] += int(record.get("latency_ms") or 0)
        _write_json(TOTALS_PATH, totals)


def today_summary() -> dict[str, Any]:
    ensure_data_dirs()
    with _LOCK:
        totals = _read_json(TOTALS_PATH, {})
        day = dict(totals.get(_today_key(), {}))
    requests = int(day.get("requests") or 0)
    latency_sum = int(day.get("latency_ms_sum") or 0)
    return {
        "date": _today_key(),
        "requests": requests,
        "success": int(day.get("success") or 0),
        "failed": int(day.get("failed") or 0),
        "timeouts": int(day.get("timeouts") or 0),
        "input_tokens": int(day.get("input_tokens") or 0),
        "output_tokens": int(day.get("output_tokens") or 0),
        "total_tokens": int(day.get("total_tokens") or 0),
        "average_latency_ms": round(latency_sum / requests) if requests else 0,
    }


def recent_requests(limit: int = 12, user_id: int | None = None) -> list[dict[str, Any]]:
    ensure_data_dirs()
    items: list[dict[str, Any]] = []
    with _LOCK:
        files = sorted(CONVERSATION_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in files:
            payload = _read_json(path, {})
            if not isinstance(payload, dict):
                continue
            if user_id is not None and int(payload.get("user_id") or 0) != int(user_id):
                continue
            items.append({
                "request_id": payload.get("request_id"),
                "mode": payload.get("mode"),
                "model": payload.get("model"),
                "status": payload.get("status"),
                "latency_ms": int(payload.get("latency_ms") or 0),
                "input_tokens": int(payload.get("input_tokens") or 0),
                "output_tokens": int(payload.get("output_tokens") or 0),
                "total_tokens": int(payload.get("total_tokens") or 0),
                "prompt_preview": str(payload.get("prompt") or "")[:120],
                "response_preview": str(payload.get("response") or "")[:180],
                "error": payload.get("error"),
                "created_at": payload.get("created_at"),
            })
            if len(items) >= max(1, min(limit, 50)):
                break
    return items


def clear_detailed_content() -> dict[str, int]:
    ensure_data_dirs()
    deleted_conversations = 0
    deleted_logs = 0
    with _LOCK:
        for path in CONVERSATION_DIR.glob("*"):
            if path.is_file() and path.name != ".gitkeep":
                path.unlink(missing_ok=True)
                deleted_conversations += 1
        for path in LOG_DIR.glob("*"):
            if path.is_file() and path.name != ".gitkeep":
                path.unlink(missing_ok=True)
                deleted_logs += 1
    return {
        "deleted_conversations": deleted_conversations,
        "deleted_logs": deleted_logs,
    }
