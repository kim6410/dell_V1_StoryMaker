from __future__ import annotations
import os

import base64
import json
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.beta_gemini import CHANNEL_KEYS, BetaGeminiRequest, beta_build_prompt, beta_parse_content

ROOT = Path(os.getenv("STORYMAKER_BETA_ROOT", "/home/bourne/StoryMaker_1/StoryMaker_beta"))
JOBS_DIR = ROOT / "data" / "jobs"
QUEUE_DIR = ROOT / "data" / "gemini_queue"
THUMB_STATE_PATH = ROOT / "data" / "beta_thumbnail_worker_state.json"
LOCK = threading.Lock()
REQUIRED_WORKER_ID = "tampermonkey-beta-v2-2.1.17"
ALLOWED_WORKER_IDS = {
    "tampermonkey-beta-v2-2.1.2",
    "tampermonkey-beta-v2-2.1.3",
    "tampermonkey-beta-v2-2.1.4",
    "tampermonkey-beta-v2-2.1.5",
    "tampermonkey-beta-v2-2.1.6",
    "tampermonkey-beta-v2-2.1.7",
    "tampermonkey-beta-v2-2.1.8",
    "tampermonkey-beta-v2-2.1.9",
    "tampermonkey-beta-v2-2.1.10",
}
ACTIVE_STATUSES = {"pending", "claimed", "sent"}

beta_gemini_worker_router = APIRouter(prefix="/beta-api/gemini-worker", tags=["beta-gemini-worker"])


class ThumbnailResult(BaseModel):
    job_id: str
    worker_id: str = ""
    data_url: str


class WorkerAck(BaseModel):
    job_id: str
    status: str = "claimed"
    worker_id: str = ""
    error: str | None = None


class WorkerResult(BaseModel):
    job_id: str
    result_text: str
    result_raw: str | None = None
    source: str = "beta-gemini-web-worker"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def seconds_since(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())
    except Exception:
        return 0.0


def validate_worker(worker_id: str) -> None:
    if worker_id != REQUIRED_WORKER_ID and worker_id not in ALLOWED_WORKER_IDS:
        raise HTTPException(status_code=426, detail=f"구형 Beta Worker는 차단되었습니다. {REQUIRED_WORKER_ID}를 설치하세요.")


def valid_job_id(job_id: str) -> bool:
    return bool(job_id.startswith("beta_") and re.fullmatch(r"[A-Za-z0-9_-]+", job_id))


def load_job(job_id: str) -> tuple[Path, Path, dict[str, Any]]:
    if not valid_job_id(job_id):
        raise HTTPException(status_code=400, detail="잘못된 Beta 작업 ID입니다.")
    job_dir = JOBS_DIR / job_id
    result_path = job_dir / "result.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Beta 작업을 찾을 수 없습니다.")
    return job_dir, result_path, json.loads(result_path.read_text(encoding="utf-8"))


def queue_state_path(job_id: str) -> Path:
    if not valid_job_id(job_id):
        raise HTTPException(status_code=400, detail="잘못된 Beta 작업 ID입니다.")
    return QUEUE_DIR / f"{job_id}.json"


def read_job_state(job_id: str) -> dict[str, Any]:
    path = queue_state_path(job_id)
    if not path.exists():
        return {"job_id": job_id, "status": "idle", "action": "GENERATE_BETA_GEMINI", "updated_at": now_iso()}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"job_id": job_id, "status": "idle", "action": "GENERATE_BETA_GEMINI", "updated_at": now_iso()}


def write_job_state(state: dict[str, Any]) -> None:
    job_id = str(state.get("job_id") or "")
    path = queue_state_path(job_id)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in state.items() if k != "prompt"}


def all_queue_states() -> list[dict[str, Any]]:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for path in QUEUE_DIR.glob("beta_*.json"):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    rows.sort(key=lambda item: str(item.get("queued_at") or item.get("updated_at") or ""))
    return rows


def next_worker_state() -> dict[str, Any]:
    for state in all_queue_states():
        if state.get("status") not in ACTIVE_STATUSES:
            continue
        job_id = str(state.get("job_id") or "")
        result_path = JOBS_DIR / job_id / "result.json"
        if not job_id or not result_path.exists():
            state["status"] = "error"
            state["error"] = "Beta 작업 폴더가 없어 대기열에서 제외되었습니다."
            state["retry_available"] = False
            state["orphaned_at"] = now_iso()
            write_job_state(state)
            continue
        return state
    return {"status": "idle", "action": None, "updated_at": now_iso()}


def build_prompt_for_job(job_id: str) -> tuple[dict[str, Any], str]:
    _, _, result = load_job(job_id)
    payload = BetaGeminiRequest(
        business=result.get("business", {}),
        topic=result.get("topic", ""),
        image_count=max(1, len(result.get("assets", {}).get("images", []))),
        weather_snapshot=result.get("weather_snapshot"),
    )
    return result, beta_build_prompt(payload)


def update_job_progress(job_id: str, status: str, progress: int, error: str | None = None) -> None:
    job_dir, _, _ = load_job(job_id)
    state_path = job_dir / "state.json"
    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    state.update({"beta_job_id": job_id, "status": status, "progress": progress, "updated_at": now_iso(), "last_error": error})
    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(state_path)


def call_gemini_api_raw(prompt: str, *, json_mode: bool = False) -> str:
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("BETA_GEMINI_API_KEY") or "").strip()
    model = (os.getenv("GEMINI_MODEL") or os.getenv("BETA_GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    generation_config: dict[str, Any] = {
        "temperature": 0.2 if json_mode else 0.5,
        "maxOutputTokens": 7000 if json_mode else 16000,
    }
    if json_mode:
        generation_config.update({
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "required": ["title", "description", "channels"],
                "properties": {
                    "title": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "channels": {
                        "type": "OBJECT",
                        "required": CHANNEL_KEYS,
                        "properties": {key: {"type": "STRING"} for key in CHANNEL_KEYS},
                    },
                },
            },
        })
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1600]
        raise RuntimeError(f"Gemini API 오류 {exc.code}: {detail}") from exc
    parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text") or "") for part in parts).strip()
    if not text:
        raise RuntimeError("Gemini API 응답 본문이 비어 있습니다.")
    return text


def build_thumbnail_prompt_for_job(result: dict[str, Any]) -> str:
    business = result.get("business") or {}
    content = result.get("content") or {}
    title = str(content.get("title") or result.get("title") or "").strip()
    description = str(content.get("description") or "").strip()
    return f"""StoryMaker Beta 썸네일 프롬프트 전용 요청입니다.

업체명: {str(business.get('name') or '').strip()}
지역: {str(business.get('region') or '').strip()}
주요 서비스: {str(business.get('service') or '').strip()}
전화번호: {str(business.get('phone') or '').strip()}
콘텐츠 제목: {title}
콘텐츠 설명: {description}
원문: {str(result.get('topic') or '').strip()}

위 사실만 사용해 9:16 세로형 썸네일 이미지 생성 프롬프트를 250~450자로 작성하세요.
업체명과 전화번호를 정확히 표시하도록 지시하고, 메인 문구·배경 장면·레이아웃·가독성·톤앤매너를 구체적으로 작성하세요.
원문에 없는 인물, 수치, 자격, 후기, 결과는 만들지 마세요.
설명이나 머리말 없이 썸네일 프롬프트 본문만 출력하세요."""


def save_thumbnail_prompt(job_id: str, prompt: str) -> None:
    job_dir, result_path, result = load_job(job_id)
    value = str(prompt or "").strip()
    if not value:
        raise RuntimeError("분리 생성된 썸네일 프롬프트가 비어 있습니다.")
    result.setdefault("content", {})["thumbnail_prompt"] = value
    prompt_path = job_dir / "thumbnail_prompt.md"
    prompt_path.write_text(value + "\n", encoding="utf-8")
    result.setdefault("assets", {})["thumbnail_prompt"] = str(prompt_path)
    tmp = result_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(result_path)


def run_thumbnail_stage(job_id: str) -> None:
    try:
        time.sleep(5)
        _, _, refreshed_result = load_job(job_id)
        thumbnail_prompt = call_gemini_api_raw(build_thumbnail_prompt_for_job(refreshed_result))
        save_thumbnail_prompt(job_id, thumbnail_prompt)
        queue_thumbnail(job_id)
    except Exception as exc:
        # 썸네일 단계 실패는 8채널 원고 완료 상태를 되돌리지 않는다.
        message = str(exc)[:1600]
        try:
            job_dir, result_path, result = load_job(job_id)
            result.setdefault("thumbnail", {})["prompt_error"] = message
            result["thumbnail"]["prompt_failed_at"] = now_iso()
            tmp = result_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(result_path)
        except Exception:
            pass


def start_thumbnail_stage(job_id: str) -> None:
    threading.Thread(
        target=run_thumbnail_stage,
        args=(job_id,),
        daemon=True,
        name=f"beta-thumbnail-prompt-{job_id}",
    ).start()


def run_api_job(job_id: str) -> None:
    try:
        result, prompt = build_prompt_for_job(job_id)
        business = result.get("business") or {}
        required = {
            "업체명": business.get("name"),
            "대표 지역": business.get("region"),
            "주요 서비스": business.get("service"),
            "전화번호": business.get("phone"),
            "원문": result.get("topic"),
        }
        missing = [label for label, value in required.items() if not str(value or "").strip()]
        if missing:
            raise RuntimeError("Gemini 전송 필수값 누락: " + ", ".join(missing))
        with LOCK:
            state = read_job_state(job_id)
            if state.get("status") == "completed":
                return
            state.update({"status": "claimed", "worker_id": "backend-gemini-api", "claimed_at": now_iso(), "error": None})
            write_job_state(state)
            update_job_progress(job_id, "gemini_claimed", 30, None)
        raw_text = call_gemini_api_raw(prompt, json_mode=False)
        save_content(job_id, raw_text, "beta-gemini-api")
        with LOCK:
            state = read_job_state(job_id)
            state.update({
                "status": "completed",
                "worker_id": "backend-gemini-api",
                "completed_at": now_iso(),
                "error": None,
                "retry_available": False,
            })
            state.pop("prompt", None)
            write_job_state(state)
        start_thumbnail_stage(job_id)
    except Exception as exc:
        message = str(exc)[:1600]
        with LOCK:
            state = read_job_state(job_id)
            state.update({"status": "error", "worker_id": "backend-gemini-api", "error": message, "retry_available": True})
            write_job_state(state)
            update_job_progress(job_id, "gemini_error", 0, message)


def start_api_job(job_id: str) -> None:
    threading.Thread(target=run_api_job, args=(job_id,), daemon=True, name=f"beta-gemini-{job_id}").start()


def save_content(job_id: str, raw_text: str, source: str) -> dict[str, Any]:
    job_dir, result_path, result = load_job(job_id)
    image_count = max(1, len(result.get("assets", {}).get("images", [])))
    try:
        content = beta_parse_content(raw_text, image_count)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Gemini JSON 해석 실패: {exc}")

    api_model = (os.getenv("GEMINI_MODEL") or os.getenv("BETA_GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
    provider = "gemini-api" if source == "beta-gemini-api" else "gemini-web-worker"
    model_name = api_model if provider == "gemini-api" else "gemini-web"
    content["provider"] = provider
    content["model"] = model_name
    content["podcast_script"] = content.get("script", "")
    result["content"] = content
    result["title"] = content.get("title") or result.get("title")
    result["status"] = "gemini_completed"
    result["progress"] = 100
    result["gemini"] = {
        "provider": provider,
        "model": model_name,
        "applied": True,
        "source": source,
        "completed_at": now_iso(),
    }

    channels_dir = job_dir / "channels"
    channels_dir.mkdir(parents=True, exist_ok=True)
    for key in content["channel_order"]:
        channel = content["channels"][key]
        (channels_dir / f"{key}.txt").write_text(channel["content"] + "\n", encoding="utf-8")
        (channels_dir / f"{key}.html").write_text(str(channel.get("html") or ""), encoding="utf-8")
    (job_dir / "podcast_50.txt").write_text(content["podcast_50"], encoding="utf-8")
    (job_dir / "podcast_80.txt").write_text(content["podcast_80"], encoding="utf-8")
    script = content["podcast_50"]
    (job_dir / "script.txt").write_text(script, encoding="utf-8")
    (job_dir / "podcast_script.txt").write_text(script, encoding="utf-8")
    thumbnail_prompt = str(content.get("thumbnail_prompt") or "").strip()
    if thumbnail_prompt:
        (job_dir / "thumbnail_prompt.md").write_text(thumbnail_prompt + "\n", encoding="utf-8")
        result.setdefault("assets", {})["thumbnail_prompt"] = str(job_dir / "thumbnail_prompt.md")
    (job_dir / "gemini_raw.txt").write_text(raw_text, encoding="utf-8")

    tmp = result_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(result_path)
    update_job_progress(job_id, "gemini_completed", 100, None)
    return result


@beta_gemini_worker_router.post("/jobs/{job_id}/prepare")
def prepare_job(job_id: str) -> dict[str, Any]:
    result, prompt = build_prompt_for_job(job_id)
    with LOCK:
        current = read_job_state(job_id)
        if current.get("status") == "completed" or result.get("gemini", {}).get("applied") is True:
            current.update({
                "status": "completed",
                "completed_at": result.get("gemini", {}).get("completed_at"),
                "error": None,
                "retry_available": False,
            })
            current.pop("prompt", None)
            write_job_state(current)
            return {"ok": True, "state": public_state(current)}
        if current.get("status") in ACTIVE_STATUSES:
            return {"ok": True, "state": public_state(current)}
        state = {
            "job_id": job_id,
            "project_title": result.get("title") or result.get("topic") or "Beta 프로젝트",
            "status": "prompt_ready",
            "action": "GENERATE_BETA_GEMINI",
            "prompt": prompt,
            "error": None,
            "worker_id": None,
            "prepared_at": now_iso(),
            "queued_at": current.get("queued_at"),
            "attempt_count": int(current.get("attempt_count", 0) or 0),
        }
        write_job_state(state)
        update_job_progress(job_id, "prompt_ready", 15, None)
    return {"ok": True, "state": public_state(state)}


@beta_gemini_worker_router.post("/jobs/{job_id}/queue")
def queue_job(job_id: str) -> dict[str, Any]:
    result, prompt = build_prompt_for_job(job_id)
    with LOCK:
        current = read_job_state(job_id)
        if result.get("gemini", {}).get("applied") is True or current.get("status") == "completed":
            current.update({"status": "completed", "error": None})
            write_job_state(current)
            return {"ok": True, "duplicate": True, "state": public_state(current)}
        if current.get("status") in ACTIVE_STATUSES:
            return {"ok": True, "duplicate": True, "state": public_state(current)}
        current.update({
            "job_id": job_id,
            "project_title": result.get("title") or result.get("topic") or "Beta 프로젝트",
            "status": "pending",
            "action": "GENERATE_BETA_GEMINI",
            "prompt": current.get("prompt") or prompt,
            "error": None,
            "worker_id": None,
            "queued_at": now_iso(),
            "attempt_count": int(current.get("attempt_count", 0) or 0) + 1,
            "retry_available": False,
        })
        write_job_state(current)
        update_job_progress(job_id, "gemini_pending", 20, None)
    return {"ok": True, "duplicate": False, "state": public_state(current), "worker": "browser-gemini-worker"}


@beta_gemini_worker_router.post("/jobs/{job_id}/api")
def api_job(job_id: str) -> dict[str, Any]:
    result, prompt = build_prompt_for_job(job_id)
    with LOCK:
        current = read_job_state(job_id)
        if result.get("gemini", {}).get("applied") is True or current.get("status") == "completed":
            current.update({"status": "completed", "error": None})
            write_job_state(current)
            return {"ok": True, "duplicate": True, "state": public_state(current)}
        if current.get("status") in ACTIVE_STATUSES:
            return {"ok": True, "duplicate": True, "state": public_state(current)}
        current.update({
            "job_id": job_id,
            "project_title": result.get("title") or result.get("topic") or "Beta 프로젝트",
            "status": "pending",
            "action": "GENERATE_BETA_GEMINI_API",
            "prompt": current.get("prompt") or prompt,
            "error": None,
            "worker_id": "backend-gemini-api",
            "queued_at": now_iso(),
            "attempt_count": int(current.get("attempt_count", 0) or 0) + 1,
            "retry_available": False,
            "ai_provider": "api",
        })
        write_job_state(current)
        update_job_progress(job_id, "gemini_api_pending", 20, None)
    start_api_job(job_id)
    return {"ok": True, "duplicate": False, "state": public_state(current), "worker": "backend-gemini-api"}


@beta_gemini_worker_router.get("/status")
def worker_status(job_id: str | None = Query(default=None)) -> dict[str, Any]:
    with LOCK:
        state = read_job_state(job_id) if job_id else next_worker_state()
        if state.get("status") == "claimed" and state.get("worker_id") != "backend-gemini-api" and seconds_since(state.get("updated_at")) >= 55:
            retry_count = int(state.get("auto_retry_count", 0) or 0)
            if retry_count < 2:
                state["status"] = "pending"
                state["worker_id"] = None
                state["error"] = None
                state["auto_retry_count"] = retry_count + 1
                state["retry_reason"] = "claimed_timeout"
                write_job_state(state)
            else:
                state["status"] = "error"
                state["error"] = "Gemini 입력창 전송이 지연되었습니다. AI 원고 생성 버튼을 다시 눌러 재시도하세요."
                state["retry_available"] = True
                write_job_state(state)
                update_job_progress(str(state.get("job_id")), "gemini_error", 0, state["error"])
        data = public_state(state)
    data["required_worker_id"] = REQUIRED_WORKER_ID
    data["queue_depth"] = sum(1 for item in all_queue_states() if item.get("status") in ACTIVE_STATUSES)
    return {"ok": True, "data": data}


@beta_gemini_worker_router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str) -> dict[str, Any]:
    load_job(job_id)
    with LOCK:
        state = read_job_state(job_id)
        if state.get("status") in ACTIVE_STATUSES:
            return {"ok": True, "duplicate": True, "state": public_state(state)}
        if not state.get("prompt"):
            _, prompt = build_prompt_for_job(job_id)
            state["prompt"] = prompt
        state.update({
            "job_id": job_id,
            "status": "pending",
            "action": "GENERATE_BETA_GEMINI",
            "worker_id": None,
            "error": None,
            "retry_available": False,
            "manual_retry_count": int(state.get("manual_retry_count", 0) or 0) + 1,
            "queued_at": now_iso(),
            "retried_at": now_iso(),
        })
        write_job_state(state)
        update_job_progress(job_id, "gemini_pending", 20, None)
    start_api_job(job_id)
    return {"ok": True, "duplicate": False, "state": public_state(state), "worker": "backend-gemini-api"}


@beta_gemini_worker_router.get("/prompt/{job_id}")
def worker_prompt(job_id: str) -> dict[str, Any]:
    state = read_job_state(job_id)
    prompt = str(state.get("prompt") or "")
    if not prompt:
        _, prompt = build_prompt_for_job(job_id)
    return {"ok": True, "job_id": job_id, "prompt": prompt, "status": state.get("status")}


@beta_gemini_worker_router.post("/ack")
def worker_ack(payload: WorkerAck) -> dict[str, Any]:
    validate_worker(payload.worker_id)
    with LOCK:
        state = read_job_state(payload.job_id)
        if state.get("status") == "completed":
            return {"ok": True, "status": "completed", "worker_id": payload.worker_id}
        if payload.status == "claimed" and state.get("status") not in {"pending", "claimed"}:
            raise HTTPException(status_code=409, detail="현재 작업은 전송 대기 상태가 아닙니다.")
        state["status"] = payload.status
        state["worker_id"] = payload.worker_id
        state["error"] = payload.error
        if payload.status == "sent":
            state["sent_at"] = now_iso()
            update_job_progress(payload.job_id, "gemini_sent", 40, None)
        elif payload.status == "claimed":
            state["claimed_at"] = now_iso()
            update_job_progress(payload.job_id, "gemini_claimed", 30, None)
        elif payload.status == "error":
            state["retry_available"] = True
            update_job_progress(payload.job_id, "gemini_error", 0, payload.error)
        write_job_state(state)
    return {"ok": True, "status": payload.status, "worker_id": payload.worker_id}


@beta_gemini_worker_router.post("/result")
def worker_result(payload: WorkerResult) -> dict[str, Any]:
    result = save_content(payload.job_id, payload.result_text, payload.source)
    with LOCK:
        state = read_job_state(payload.job_id)
        state["status"] = "completed"
        state["completed_at"] = now_iso()
        state["error"] = None
        state["retry_available"] = False
        state.pop("prompt", None)
        write_job_state(state)

    thumbnail_queue: dict[str, Any]
    try:
        thumbnail_queue = queue_thumbnail(payload.job_id)
    except HTTPException as exc:
        thumbnail_queue = {"ok": False, "detail": str(exc.detail)}
    return {"ok": True, "job": result, "thumbnail_queue": thumbnail_queue}


def read_thumb_state() -> dict[str, Any]:
    if not THUMB_STATE_PATH.exists():
        return {"status": "idle", "action": None, "updated_at": now_iso()}
    try:
        return json.loads(THUMB_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "idle", "action": None, "updated_at": now_iso()}


def write_thumb_state(state: dict[str, Any]) -> None:
    THUMB_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
    tmp = THUMB_STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(THUMB_STATE_PATH)


@beta_gemini_worker_router.post("/jobs/{job_id}/thumbnail/queue")
def queue_thumbnail(job_id: str) -> dict[str, Any]:
    job_dir, _, result = load_job(job_id)
    prompt = str(result.get("content", {}).get("thumbnail_prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="AI 썸네일 프롬프트가 없습니다.")
    full_prompt = (
        prompt
        + "\n\n첨부된 실제 현장 이미지를 참고하여 위 지시대로 9:16 세로형 썸네일 이미지를 생성하세요. "
          "설명문이나 코드 없이 이미지 결과만 생성하세요."
    )
    source_images = list((result.get("assets") or {}).get("images") or [])[:3]
    image_urls = [f"/beta-api/browser/jobs/{job_id}/image/{index}" for index in range(1, len(source_images) + 1)]
    with LOCK:
        current = read_thumb_state()
        if current.get("job_id") == job_id and current.get("status") in {"pending", "claimed", "uploaded", "sent", "completed"}:
            return {"ok": True, "state": {k: v for k, v in current.items() if k != "prompt"}}
        state = {
            "action": "GENERATE_BETA_THUMBNAIL",
            "job_id": job_id,
            "status": "pending",
            "prompt": full_prompt,
            "image_urls": image_urls,
            "worker_id": None,
            "error": None,
            "queued_at": now_iso(),
        }
        write_thumb_state(state)
    return {"ok": True, "state": {k: v for k, v in state.items() if k != "prompt"}}


@beta_gemini_worker_router.get("/thumbnail/status")
def thumbnail_status() -> dict[str, Any]:
    with LOCK:
        gemini_state = next_worker_state()
        if gemini_state.get("action") == "GENERATE_BETA_GEMINI" and gemini_state.get("status") in ACTIVE_STATUSES:
            return {
                "ok": True,
                "data": {
                    "status": "idle",
                    "action": None,
                    "deferred_for_gemini_job_id": gemini_state.get("job_id"),
                    "updated_at": now_iso(),
                },
            }
        state = read_thumb_state()
        return {"ok": True, "data": state}


@beta_gemini_worker_router.post("/thumbnail/ack")
def thumbnail_ack(payload: WorkerAck) -> dict[str, Any]:
    validate_worker(payload.worker_id)
    with LOCK:
        state = read_thumb_state()
        if state.get("job_id") != payload.job_id:
            raise HTTPException(status_code=409, detail="다른 썸네일 작업입니다.")
        state["status"] = payload.status
        state["worker_id"] = payload.worker_id
        state["error"] = payload.error
        write_thumb_state(state)
    return {"ok": True}


@beta_gemini_worker_router.post("/thumbnail/result")
def thumbnail_result(payload: ThumbnailResult) -> dict[str, Any]:
    validate_worker(payload.worker_id)
    job_dir, result_path, result = load_job(payload.job_id)
    match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", payload.data_url, flags=re.I | re.S)
    if not match:
        raise HTTPException(status_code=400, detail="올바른 이미지 데이터가 아닙니다.")
    ext = "jpg" if match.group(1).lower() in {"jpeg", "jpg"} else match.group(1).lower()
    try:
        raw = base64.b64decode(match.group(2), validate=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"썸네일 디코딩 실패: {exc}")
    if len(raw) < 10_000:
        raise HTTPException(status_code=400, detail="썸네일 이미지가 너무 작습니다.")
    out = job_dir / "output"
    out.mkdir(exist_ok=True)
    target = out / f"thumbnail.{ext}"
    target.write_bytes(raw)
    # archive API expects thumbnail.jpg; normalize through ffmpeg only when needed
    final = out / "thumbnail.jpg"
    if target != final:
        import subprocess
        ffmpeg = Path(os.getenv("STORYMAKER_BETA_FFMPEG", "/usr/bin/ffmpeg"))
        subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(target), str(final)], check=True)
    else:
        final = target
    result.setdefault("assets", {})["thumbnail"] = str(final)
    result.setdefault("thumbnail", {})["source"] = "gemini-web-worker"
    tmp = result_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(result_path)
    with LOCK:
        state = read_thumb_state()
        state.update({"status": "completed", "worker_id": payload.worker_id, "thumbnail": str(final), "error": None})
        write_thumb_state(state)
    return {"ok": True, "thumbnail": str(final)}
