from pathlib import Path
import re

ROOT = Path(r"F:\StoryMaker_beta")
worker_path = ROOT / "app" / "beta_gemini_worker.py"
js_path = ROOT / "static" / "beta-production.js"
html_path = ROOT / "static" / "production.html"
userjs_path = ROOT / "static" / "storymaker-beta-gemini-worker.user.js"

old_worker = worker_path.read_text(encoding="utf-8")
suffix_marker = "def read_thumb_state() -> dict[str, Any]:"
suffix = old_worker[old_worker.index(suffix_marker):]

worker_prefix = r'''from __future__ import annotations

import base64
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.beta_gemini import BetaGeminiRequest, beta_build_prompt, beta_parse_content

ROOT = Path(r"F:\StoryMaker_beta")
JOBS_DIR = ROOT / "data" / "jobs"
QUEUE_DIR = ROOT / "data" / "gemini_queue"
THUMB_STATE_PATH = ROOT / "data" / "beta_thumbnail_worker_state.json"
LOCK = threading.Lock()
REQUIRED_WORKER_ID = "tampermonkey-beta-v2-2.1.6"
ALLOWED_WORKER_IDS = {
    "tampermonkey-beta-v2-2.1.2",
    "tampermonkey-beta-v2-2.1.3",
    "tampermonkey-beta-v2-2.1.4",
    "tampermonkey-beta-v2-2.1.5",
    "tampermonkey-beta-v2-2.1.6",
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
    if worker_id not in ALLOWED_WORKER_IDS:
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
        if state.get("status") in ACTIVE_STATUSES:
            return state
    return {"status": "idle", "action": None, "updated_at": now_iso()}


def build_prompt_for_job(job_id: str) -> tuple[dict[str, Any], str]:
    _, _, result = load_job(job_id)
    payload = BetaGeminiRequest(
        business=result.get("business", {}),
        topic=result.get("topic", ""),
        image_count=max(1, len(result.get("assets", {}).get("images", []))),
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


def save_content(job_id: str, raw_text: str, source: str) -> dict[str, Any]:
    job_dir, result_path, result = load_job(job_id)
    image_count = max(1, len(result.get("assets", {}).get("images", [])))
    try:
        content = beta_parse_content(raw_text, image_count)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Gemini JSON 해석 실패: {exc}")

    content["provider"] = "gemini-web-worker"
    content["model"] = "gemini-web"
    content["podcast_script"] = content.get("script", "")
    result["content"] = content
    result["title"] = content.get("title") or result.get("title")
    result["status"] = "gemini_completed"
    result["progress"] = 100
    result["gemini"] = {
        "provider": "gemini-web-worker",
        "model": "gemini-web",
        "applied": True,
        "source": source,
        "completed_at": now_iso(),
    }

    channels_dir = job_dir / "channels"
    channels_dir.mkdir(parents=True, exist_ok=True)
    for key in content["channel_order"]:
        (channels_dir / f"{key}.txt").write_text(content["channels"][key]["content"] + "\n", encoding="utf-8")
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
            current.update({"status": "completed", "completed_at": result.get("gemini", {}).get("completed_at"), "error": None})
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
    return {"ok": True, "duplicate": False, "state": public_state(current)}


@beta_gemini_worker_router.get("/status")
def worker_status(job_id: str | None = Query(default=None)) -> dict[str, Any]:
    with LOCK:
        state = read_job_state(job_id) if job_id else next_worker_state()
        if state.get("status") == "claimed" and seconds_since(state.get("updated_at")) >= 55:
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
    return {"ok": True, "duplicate": False, "state": public_state(state)}


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
    return {"ok": True, "job": result}


'''

# thumbnail code must check all active Gemini jobs, not a removed global state file.
suffix = suffix.replace(
    '        gemini_state = read_state()\n        if gemini_state.get("action") == "GENERATE_BETA_GEMINI" and gemini_state.get("status") in {"pending", "claimed", "sent"}:',
    '        gemini_state = next_worker_state()\n        if gemini_state.get("action") == "GENERATE_BETA_GEMINI" and gemini_state.get("status") in ACTIVE_STATUSES:'
)
worker_path.write_text(worker_prefix + suffix, encoding="utf-8")

html = html_path.read_text(encoding="utf-8")
html = html.replace(
    '<div class="auto-actions"><button id="beta-gemini" type="submit">프롬프트 생성</button></div>',
    '<div class="auto-actions beta-gemini-actions"><button id="beta-gemini" type="submit">프롬프트 생성</button><button id="beta-gemini-retry" type="button" disabled>AI원고 생성</button></div>'
)
html = html.replace('<div class="actions"><button id="beta-gemini-retry" type="button" hidden>AI원고 생성</button></div>', '')
html = html.replace('.auto-actions{', '.beta-gemini-actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.beta-gemini-actions button{min-width:180px}.auto-actions{')
html = html.replace('beta-production.js?v=20260724-user-settings-music-1', 'beta-production.js?v=20260724-gemini-reliable-1')
html_path.write_text(html, encoding="utf-8")

js = js_path.read_text(encoding="utf-8")
# Build a fresh, deterministic Gemini control section while preserving unrelated renderer/UI logic.
js = js.replace("  let betaPromptAnimation = null;", "  let betaPromptAnimation = null;\n  let betaGeminiWatchTimer = null;\n  let betaGeminiLockedUntil = 0;\n  const BETA_GEMINI_LOCK_MS = 60000;")

create_old = re.search(r"  async function betaCreateJob\(event\) \{.*?\n  \}\n\n  async function betaInspect", js, flags=re.S)
if not create_old:
    raise SystemExit("betaCreateJob block not found")
create_new = r'''  function betaSetGeminiButtons({ promptDisabled = false, aiDisabled = true } = {}) {
    if (betaUi.gemini) betaUi.gemini.disabled = promptDisabled;
    if (betaUi.geminiRetry) {
      betaUi.geminiRetry.hidden = false;
      betaUi.geminiRetry.disabled = aiDisabled;
    }
  }

  function betaUnlockAiAfterTimeout() {
    betaGeminiLockedUntil = Date.now() + BETA_GEMINI_LOCK_MS;
    window.setTimeout(() => {
      if (Date.now() < betaGeminiLockedUntil) return;
      if (betaUi.geminiRetry) betaUi.geminiRetry.disabled = false;
      betaSetStatus('AI 응답이 지연되고 있습니다. 기존 작업은 계속 확인 중이며, 필요하면 AI원고 생성을 다시 누르세요.', 40);
      betaStartBackgroundGeminiWatch();
    }, BETA_GEMINI_LOCK_MS + 50);
  }

  function betaStartBackgroundGeminiWatch() {
    if (betaGeminiWatchTimer || !betaCurrentJobId) return;
    betaGeminiWatchTimer = window.setInterval(async () => {
      try {
        const status = await betaRequest(`/beta-api/gemini-worker/status?job_id=${encodeURIComponent(betaCurrentJobId)}`);
        const worker = status.data || {};
        if (worker.status === 'completed') {
          window.clearInterval(betaGeminiWatchTimer);
          betaGeminiWatchTimer = null;
          await betaCompleteGeminiUi();
        }
      } catch (_) {}
    }, 3000);
  }

  async function betaCreateJob(event) {
    event.preventDefault();
    if (!betaUi.images.files.length) {
      betaSetStatus('이미지를 한 장 이상 선택하세요.');
      return;
    }
    const body = new FormData();
    body.append('business_name', betaUi.businessName.value.trim());
    body.append('business_region', betaUi.businessRegion.value.trim());
    body.append('business_service', betaUi.businessService.value.trim());
    body.append('business_phone', betaUi.businessPhone.value.trim());
    body.append('topic', betaUi.topic.value.trim());
    for (const file of betaUi.images.files) body.append('images', file);
    for (const file of betaUi.videos.files) body.append('videos', file);
    betaSetGeminiButtons({ promptDisabled: true, aiDisabled: true });
    betaSetStatus('작업 공간과 AI 프롬프트를 준비하는 중...', 8);
    try {
      const data = await betaRequest('/beta-api/jobs', { method: 'POST', body });
      betaCurrentJobId = data.job.beta_job_id;
      sessionStorage.setItem('storymaker_beta_current_job', betaCurrentJobId);
      betaUi.jobId.textContent = betaCurrentJobId;
      betaShowContent(data.job);
      await betaRequest(`/beta-api/gemini-worker/jobs/${encodeURIComponent(betaCurrentJobId)}/prepare`, { method: 'POST' });
      betaSetStatus('프롬프트 준비 완료. 오른쪽 AI원고 생성 버튼을 한 번만 누르세요.', 15);
      betaSetGeminiButtons({ promptDisabled: false, aiDisabled: false });
    } catch (error) {
      betaSetStatus(`프롬프트 생성 실패: ${error.message}`);
      betaSetGeminiButtons({ promptDisabled: false, aiDisabled: true });
    }
  }

  async function betaInspect'''
js = js[:create_old.start()] + create_new + js[create_old.end():]

flow_old = re.search(r"  async function betaRetryGemini\(\) \{.*?\n  async function betaRenderJob", js, flags=re.S)
if not flow_old:
    raise SystemExit("Gemini flow block not found")
flow_new = r'''  async function betaCompleteGeminiUi() {
    betaStopPromptAnimation();
    const data = await betaRequest(`/beta-api/jobs/${encodeURIComponent(betaCurrentJobId)}`);
    betaShowContent(data.job);
    betaSetStatus('AI 원고 생성이 완료되었습니다. 채널별 결과를 확인하세요.', 100);
    betaGeminiLockedUntil = 0;
    betaSetGeminiButtons({ promptDisabled: false, aiDisabled: true });
    requestAnimationFrame(() => {
      betaUi.channelResults?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      betaUi.channelResults?.focus({ preventScroll: true });
    });
  }

  async function betaRetryGemini() {
    return betaGenerateGemini();
  }

  async function betaWaitForGemini() {
    const startedAt = Date.now();
    let sentAt = 0;
    while (Date.now() - startedAt < BETA_GEMINI_LOCK_MS) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const status = await betaRequest(`/beta-api/gemini-worker/status?job_id=${encodeURIComponent(betaCurrentJobId)}`);
      const worker = status.data || {};
      const workerStatus = worker.status || '대기 중';
      if (workerStatus === 'sent' && !sentAt) {
        sentAt = Date.now();
        betaStopPromptAnimation();
      }
      const progress = workerStatus === 'sent' ? 42 : workerStatus === 'claimed' ? 30 : workerStatus === 'pending' ? 22 : 18;
      if (!betaPromptAnimation || workerStatus === 'sent') betaSetStatus(`AI 웹 Worker 상태: ${workerStatus}`, progress);
      if (workerStatus === 'error') {
        betaStopPromptAnimation();
        betaGeminiLockedUntil = 0;
        betaSetGeminiButtons({ promptDisabled: false, aiDisabled: false });
        throw new Error(worker.error || 'AI Worker 처리 실패');
      }
      if (workerStatus === 'completed') {
        await betaCompleteGeminiUi();
        return true;
      }
    }
    betaStopPromptAnimation();
    betaSetGeminiButtons({ promptDisabled: false, aiDisabled: false });
    betaStartBackgroundGeminiWatch();
    return false;
  }

  async function betaGenerateGemini() {
    if (!betaCurrentJobId || !betaUi.geminiRetry) return;
    if (Date.now() < betaGeminiLockedUntil) return;
    betaSetGeminiButtons({ promptDisabled: true, aiDisabled: true });
    betaUnlockAiAfterTimeout();
    betaSetStatus('준비된 프롬프트를 AI 전송 창구에 등록하는 중...', 18);
    try {
      await betaRequest(`/beta-api/gemini-worker/jobs/${encodeURIComponent(betaCurrentJobId)}/queue`, { method: 'POST' });
      await betaStartPromptAnimation();
      await betaWaitForGemini();
    } catch (error) {
      betaGeminiLockedUntil = 0;
      betaSetStatus(`AI 원고 생성 실패: ${error.message}`);
      betaSetGeminiButtons({ promptDisabled: false, aiDisabled: false });
    }
  }

  async function betaRenderJob'''
js = js[:flow_old.start()] + flow_new + js[flow_old.end():]

js = js.replace("    betaUi.gemini.disabled = false;\n    try {", "    betaSetGeminiButtons({ promptDisabled: false, aiDisabled: true });\n    try {")
js = js.replace(
    "      betaSetStatus(order.length === 8 ? '저장된 AI SNS 8채널을 불러왔습니다.' : '현재 작업을 불러왔습니다. AI SNS 8채널 작성을 진행하세요.', order.length === 8 ? 25 : 10);",
    "      if (order.length === 8) {\n        betaSetStatus('저장된 AI SNS 8채널을 불러왔습니다.', 100);\n        betaSetGeminiButtons({ promptDisabled: false, aiDisabled: true });\n      } else {\n        await betaRequest(`/beta-api/gemini-worker/jobs/${encodeURIComponent(betaCurrentJobId)}/prepare`, { method: 'POST' });\n        betaSetStatus('현재 작업의 프롬프트가 준비되었습니다. AI원고 생성을 누르세요.', 15);\n        betaSetGeminiButtons({ promptDisabled: false, aiDisabled: false });\n      }"
)
js_path.write_text(js, encoding="utf-8")

userjs = userjs_path.read_text(encoding="utf-8")
userjs = userjs.replace('async function waitPromptBox(timeout = 30000)', 'async function waitPromptBox(timeout = 55000)')
userjs_path.write_text(userjs, encoding="utf-8")

print("PATCHED")
