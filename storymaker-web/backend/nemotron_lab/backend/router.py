from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse

from app.api.auth import get_current_user
from app.db.database import get_db
from app.db.models import User
from sqlalchemy.orm import Session

from .cleanup import purge_daily_content, start_cleanup_scheduler
from .persona_builder import build_persona_draft
from .schemas import LabRequest
from .service import NemotronLabService
from .tts_schemas import TtsRequest
from .tts_service import tts_service
from .usage_store import recent_requests, today_summary
from .chat_store import (
    list_conversations,
    create_conversation,
    get_conversation_messages,
    delete_conversation,
    add_message,
    update_conversation_title,
    save_user_persona,
    get_active_user_persona,
    deactivate_user_persona,
)
from .persona_builder import _clean_text, _json_list, build_persona_draft
from app.db.models import UserPersona


KST = ZoneInfo("Asia/Seoul")
router = APIRouter(prefix="/nemotron-lab", tags=["Nemotron Lab"])
service = NemotronLabService()
UI_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "frontend" / "v2-bridge.js"
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[int, deque[float]] = defaultdict(deque)
RATE_LIMIT_PER_HOUR = 60
WEATHER_SERVER_URL = "http://172.27.0.1:8010/weather_json"
WEATHER_KEYWORDS = (
    "날씨", "기온", "온도", "습도", "풍속", "바람", "우산",
    "강수", "폭염", "한파", "미세먼지", "초미세먼지",
)


def _is_weather_query(prompt: str) -> bool:
    text = re.sub(r"\s+", " ", str(prompt or "")).strip().lower()
    if not text:
        return False
    if any(keyword in text for keyword in WEATHER_KEYWORDS):
        return True
    return bool(re.search(r"(?:비|눈)\s*(?:가|는|도)?\s*(?:와|오|내리|올까|오나|오니)", text))


def _fetch_weather_sync(query: str, auto_select_first: bool = False) -> dict | None:
    url = f"{WEATHER_SERVER_URL}?{urlencode({'query': query})}"
    try:
        with urlopen(url, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        output = str(payload.get("output") or "")
        if auto_select_first and "여러 지역이 검색되었습니다" in output:
            choice_url = f"{WEATHER_SERVER_URL}?{urlencode({'query': '1번'})}"
            with urlopen(choice_url, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"[nemotron-lab] weather lookup failed: {type(exc).__name__}: {exc}")
        return None
    if not payload.get("ok") or not str(payload.get("output") or "").strip():
        return None
    return payload


def _has_explicit_weather_location(prompt: str) -> bool:
    text = re.sub(r"\s+", " ", str(prompt or "")).strip()
    if not text:
        return False
    if re.search(r"[가-힣]{1,12}(?:특별시|광역시|특별자치시|특별자치도|도|시|군|구|동|읍|면)\b", text):
        return True
    common_locations = (
        "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "제주",
        "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남",
        "남양주", "하남", "수원", "성남", "고양", "용인", "안산", "양주",
    )
    return any(location in text for location in common_locations)


async def _build_weather_context(prompt: str, user_region: str = "") -> str:
    if not _is_weather_query(prompt):
        return ""
    weather_query = str(prompt or "").strip()
    clean_region = re.sub(r"\s+", " ", str(user_region or "")).strip()
    use_user_region = bool(clean_region and not _has_explicit_weather_location(weather_query))
    if use_user_region:
        weather_query = f"{clean_region} {weather_query}"
    payload = await asyncio.to_thread(_fetch_weather_sync, weather_query, use_user_region)
    if not payload:
        return ""
    output = str(payload.get("output") or "").strip()
    return (
        "\n\n[실시간 날씨 서버 조회 결과]\n"
        f"{output}\n"
        "위 내용은 Dell Weather Server가 방금 조회한 실제 데이터입니다. "
        "수치와 예보를 임의로 바꾸거나 추측하지 말고, 사용자 질문에 필요한 내용만 자연스럽게 설명하세요. "
        "활성 페르소나가 있다면 해당 업종과 상황에 맞는 짧은 실무 조언을 덧붙이되, 날씨 데이터와 구분하세요."
    )


@router.get("/conversations")
async def read_conversations(current_user: User = Depends(get_current_user)) -> dict:
    return {"ok": True, "data": list_conversations(current_user.id)}


@router.post("/conversations")
async def create_new_conversation(request: Request, current_user: User = Depends(get_current_user)) -> dict:
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    title = str(body.get("title") or "새 대화").strip()
    return {"ok": True, "data": create_conversation(current_user.id, title)}


@router.get("/conversations/{conv_id}")
async def read_conversation_detail(conv_id: str, current_user: User = Depends(get_current_user)) -> dict:
    data = get_conversation_messages(conv_id, current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    return {"ok": True, "data": data}


@router.delete("/conversations/{conv_id}")
async def remove_conversation(conv_id: str, current_user: User = Depends(get_current_user)) -> dict:
    ok = delete_conversation(conv_id, current_user.id)
    return {"ok": ok, "message": "대화가 삭제되었습니다."}


@router.post("/conversations/{conv_id}/messages")
async def send_chat_message(
    conv_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _check_rate_limit(current_user.id)
    conv_data = get_conversation_messages(conv_id, current_user.id)
    if not conv_data:
        raise HTTPException(status_code=404, detail="존재하지 않는 대화입니다.")
    body = await request.json()
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="메시지 내용을 입력해 주세요.")
    
    model = str(body.get("model") or service.default_model).strip()
    temperature = float(body.get("temperature", 0.35))
    max_tokens = int(body.get("max_tokens", 2048))

    if db is None or not hasattr(db, "query"):
        from app.db.database import SessionLocal
        db = SessionLocal()

    user_persona_obj = (
        db.query(UserPersona)
        .filter(UserPersona.user_id == current_user.id)
        .order_by(UserPersona.is_default.desc(), UserPersona.updated_at.desc(), UserPersona.id.asc())
        .first()
    )
    mypage_info_text = ""
    if user_persona_obj:
        keywords = _json_list(user_persona_obj.keywords_json)
        tones = _json_list(user_persona_obj.default_tones_json)
        mypage_info_text = (
            f"[마이페이지 업체 기본 정보 (자동 적용)]\n"
            f"업체명: {user_persona_obj.company_name or '미등록'}\n"
            f"업종 코드: {user_persona_obj.industry_key or '일반'}\n"
            f"활동 지역: {user_persona_obj.region or '전국'}\n"
            f"주요 서비스: {', '.join(keywords[:10]) if keywords else _clean_text(user_persona_obj.content, 200)}\n"
            f"업체 소개: {_clean_text(user_persona_obj.content, 800)}\n"
            f"기본 선호 말투: {', '.join(tones) if tones else '친근하고 정중함'}\n"
            f"기본 콘텐츠 스타일: {user_persona_obj.default_style or '네이버 블로그'}\n"
            f"홈페이지: {user_persona_obj.website_url or '없음'}\n"
        )

    # 2. Fetch Active Custom Nemotron Persona (User approved, overrides defaults)
    active_persona = get_active_user_persona(current_user.id)
    active_persona_text = ""
    if active_persona and active_persona.get("persona"):
        p_info = active_persona["persona"]
        active_persona_text = (
            f"\n[사용자 승인 전담 네모트론 페르소나 (최우선 적용)]\n"
            f"역할: {p_info.get('role', '전담 마케터')}\n"
            f"사업 분야: {p_info.get('business', '')}\n"
            f"주요 서비스: {p_info.get('services', '')}\n"
            f"타깃 고객: {p_info.get('target_audience', '')}\n"
            f"활동 지역: {p_info.get('region', '')}\n"
            f"브랜드 강점: {p_info.get('strengths', '')}\n"
            f"답변 말투: {p_info.get('tone', '')}\n"
            f"콘텐츠 방향: {p_info.get('content_direction', '')}\n"
            f"피해야 할 표현: {p_info.get('avoid_phrases', '')}\n"
            f"작성 지침: {p_info.get('guideline', '')}\n"
        )

    system_prompt = (
        "당신은 StoryMaker 사용자를 돕는 전문 비즈니스 콘텐츠 AI 비서 '네모트론(Nemotron 3 Ultra)'입니다.\n"
        "아래 제공된 [마이페이지 업체 기본 정보] 및 [사용자 승인 전담 네모트론 페르소나]는 사용자가 사전에 등록한 본인의 실제 업체 프로필입니다.\n"
        "사용자가 '내 업체명', '내 활동 지역', '내 주요 서비스' 등을 질문하면 제공된 업체 프로필 정보를 직접 확인하여 정확하게 답변하세요.\n"
        "사용자가 요구하는 답변을 정확하고 친절하며 현실적으로 작성하되, 데이터에 없는 허위 사실은 지어내지 마세요.\n\n"
        f"{mypage_info_text}"
        f"{active_persona_text}"
    )

    weather_context = await _build_weather_context(
        prompt,
        user_persona_obj.region if user_persona_obj else "",
    )
    if weather_context:
        system_prompt += weather_context

    # 3. Assemble History Messages (Up to last 10 messages)
    raw_history = conv_data.get("messages", [])
    history_messages = []
    for msg in raw_history[-10:]:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            history_messages.append({"role": role, "content": content})

    # Save current user message to DB
    user_msg = add_message(conv_id, "user", prompt, 0)
    
    if len(raw_history) == 0:
        update_conversation_title(conv_id, prompt[:30])

    # Construct complete payload for NVIDIA API
    messages_payload = [{"role": "system", "content": system_prompt}] + history_messages + [{"role": "user", "content": prompt}]

    client_ip = request.client.host if request.client else "unknown"
    result = await service.execute_messages(
        messages=messages_payload,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        user_id=current_user.id,
        username=current_user.username,
        client_ip=client_ip
    )
    
    if result.get("ok") and result.get("content"):
        content = result.get("content")
        tokens = result.get("total_tokens", 0)
        bot_msg = add_message(conv_id, "assistant", content, tokens)
        return {"ok": True, "data": {"user_message": user_msg, "assistant_message": bot_msg, "meta": result}}
    else:
        err_msg = result.get("error") or "네모트론 모델 응답 처리에 실패했습니다."
        return {"ok": False, "message": err_msg}


@router.get("/persona/source-profile")
async def read_persona_source_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    draft = build_persona_draft(db, current_user.id)
    profile = draft.get("profile", {})
    sanitized = {
        "username": current_user.username,
        "company_name": profile.get("company_name", ""),
        "industry_key": profile.get("industry_key", "general"),
        "industry_label": profile.get("industry_label", ""),
        "region": profile.get("region", ""),
        "website_url": profile.get("website_url", ""),
        "services": profile.get("services", ""),
        "content_intro": profile.get("introduction", ""),
        "tones": profile.get("tones", ""),
        "content_style": profile.get("content_style", ""),
        "keywords": profile.get("keywords", "")
    }
    return {"ok": True, "data": sanitized}


@router.post("/persona/generate")
async def generate_user_persona(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    body = await request.json()
    approved = body.get("approved_profile", {})
    prompt_str = (
        "다음 사용자 마이페이지 업체 정보를 바탕으로 AI 업무 보조용 전담 페르소나 프로필을 설계해 주세요.\n"
        f"업체명: {approved.get('company_name', '미등록')}\n"
        f"업종: {approved.get('industry_label', approved.get('industry_key', '일반'))}\n"
        f"지역: {approved.get('region', '전국')}\n"
        f"주요 서비스: {approved.get('services', '')}\n"
        f"소개: {approved.get('content_intro', '')}\n"
        f"선호 말투: {approved.get('tones', '')}\n"
        f"주요 키워드: {approved.get('keywords', '')}\n\n"
        "다음 10개 필드를 가진 JSON 구조로 정제해서 출력해 주세요:\n"
        "{\n"
        '  "role": "사용자의 주요 역할 및 브랜딩 명칭",\n'
        '  "business": "핵심 사업 분야 및 대표 서비스 요약",\n'
        '  "services": "상세 시공 및 서비스 항목 목록",\n'
        '  "target_audience": "주요 타깃 고객층",\n'
        '  "region": "주요 활동 및 시공 지역",\n'
        '  "strengths": "브랜드 핵심 강점 및 차별화 신뢰 요소",\n'
        '  "tone": "답변 말투 및 어조 지침",\n'
        '  "content_direction": "콘텐츠 제작 방향 및 테마",\n'
        '  "avoid_phrases": "피해야 할 상술적/과장 표현",\n'
        '  "guideline": "콘텐츠 작성 시 필수 준수 지침"\n'
        "}"
    )
    lab_req = LabRequest(mode="chat", prompt=prompt_str, model=service.default_model, temperature=0.3)
    client_ip = request.client.host if request.client else "unknown"
    result = await service.execute(lab_req, current_user.id, current_user.username, client_ip)
    
    parsed = {}
    try:
        import json as _json
        raw = result.get("content", "")
        if "{" in raw and "}" in raw:
            json_str = raw[raw.find("{"):raw.rfind("}")+1]
            parsed = _json.loads(json_str)
        else:
            parsed = {
                "role": "전담 마케터",
                "business": approved.get("company_name", ""),
                "services": approved.get("services", ""),
                "target_audience": "지역 고객층",
                "region": approved.get("region", ""),
                "strengths": "신뢰성 및 풍부한 경험",
                "tone": "친근하고 전문적인 어조",
                "content_direction": "사례 중심 정보 전달",
                "avoid_phrases": "과장 광고 표현",
                "guideline": "자연스러운 한국어 작성"
            }
    except Exception:
        parsed = {
            "role": "전담 마케터",
            "business": approved.get("company_name", ""),
            "services": approved.get("services", ""),
            "target_audience": "지역 고객층",
            "region": approved.get("region", ""),
            "strengths": "신뢰성 및 풍부한 경험",
            "tone": "친근하고 전문적인 어조",
            "content_direction": "사례 중심 정보 전달",
            "avoid_phrases": "과장 광고 표현",
            "guideline": "자연스러운 한국어 작성"
        }
    
    return {"ok": True, "data": parsed, "raw": result.get("content")}


@router.get("/persona")
async def read_active_persona(current_user: User = Depends(get_current_user)) -> dict:
    persona = get_active_user_persona(current_user.id)
    return {"ok": True, "data": persona}


@router.post("/persona/save")
async def save_persona(request: Request, current_user: User = Depends(get_current_user)) -> dict:
    body = await request.json()
    persona_data = body.get("persona", {})
    comp = str(body.get("company_name", "")).strip()
    ind = str(body.get("industry_key", "general")).strip()
    reg = str(body.get("region", "")).strip()
    web = str(body.get("website_url", "")).strip()
    res = save_user_persona(current_user.id, comp, ind, reg, web, persona_data)
    return {"ok": True, "data": res, "message": "페르소나가 성공적으로 저장되었습니다."}


@router.post("/persona/deactivate")
async def deactivate_persona(current_user: User = Depends(get_current_user)) -> dict:
    deactivate_user_persona(current_user.id)
    return {"ok": True, "data": None, "message": "페르소나가 비활성화되었습니다."}


def _next_purge_at() -> str:
    now = datetime.now(KST)
    target = now.replace(hour=23, minute=59, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.isoformat(timespec="seconds")


def _check_rate_limit(user_id: int) -> None:
    now = time.time()
    cutoff = now - 3600
    with _RATE_LOCK:
        bucket = _RATE_BUCKETS[int(user_id)]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_PER_HOUR:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI 연구실 2는 사용자당 시간당 60회까지 테스트할 수 있습니다.",
            )
        bucket.append(now)


@router.get("/ui.js", include_in_schema=False)
async def read_ui_script() -> FileResponse:
    if not UI_SCRIPT_PATH.is_file():
        raise HTTPException(status_code=404, detail="AI 연구실 2 UI 파일을 찾을 수 없습니다.")
    return FileResponse(
        path=str(UI_SCRIPT_PATH),
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/status")
async def read_status(current_user: User = Depends(get_current_user)) -> dict:
    state = await service.status()
    return {
        "ok": True,
        "data": {
            **state,
            "usage": today_summary(),
            "next_purge_at": _next_purge_at(),
            "current_user": {
                "id": current_user.id,
                "username": current_user.username,
            },
        },
    }


@router.get("/persona-draft")
async def read_persona_draft(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return {
        "ok": True,
        "data": build_persona_draft(db, current_user.id),
    }


@router.get("/models")
async def read_models(
    refresh: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
) -> dict:
    models = await service.models(force=refresh)
    return {
        "ok": bool(models),
        "data": {
            "models": models,
            "default_model": service.default_model,
            "count": len(models),
        },
    }


@router.get("/usage")
async def read_usage(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "ok": True,
        "data": {
            "summary": today_summary(),
            "recent": recent_requests(limit=12, user_id=current_user.id),
            "next_purge_at": _next_purge_at(),
        },
    }


@router.get("/requests")
async def read_requests(
    limit: int = Query(default=12, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> dict:
    return {
        "ok": True,
        "data": recent_requests(limit=limit, user_id=current_user.id),
    }


@router.post("/execute")
async def execute_request(
    payload: LabRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    _check_rate_limit(current_user.id)
    client_ip = request.client.host if request.client else "unknown"
    result = await service.execute(
        request=payload,
        user_id=current_user.id,
        username=current_user.username,
        client_ip=client_ip,
    )
    if result.get("status") == "timeout":
        return {"ok": False, "data": result, "message": result.get("error")}
    if not result.get("ok"):
        return {"ok": False, "data": result, "message": result.get("error") or "요청에 실패했습니다."}
    return {"ok": True, "data": result, "message": "응답이 완료되었습니다."}


@router.get("/tts/voices")
async def read_tts_voices(
    refresh: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = await tts_service.voices(force=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:500]) from exc
    return {"ok": True, "data": data}


@router.post("/tts/synthesize")
async def synthesize_tts(
    payload: TtsRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    _check_rate_limit(current_user.id)
    client_ip = request.client.host if request.client else "unknown"
    try:
        audio, metadata = await tts_service.synthesize(
            request=payload,
            user_id=current_user.id,
            username=current_user.username,
            client_ip=client_ip,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:500]) from exc

    headers = {
        "Cache-Control": "no-store",
        "Content-Disposition": f'inline; filename="nemotron-tts-{metadata["request_id"]}.wav"',
        "X-Nemotron-Request-Id": str(metadata["request_id"]),
        "X-Nemotron-Latency-Ms": str(metadata["latency_ms"]),
        "X-Nemotron-Audio-Bytes": str(metadata["audio_bytes"]),
        "X-Nemotron-Language": str(metadata["language"]),
        "X-Nemotron-Voice": str(metadata["voice"] or "default"),
    }
    return StreamingResponse(iter([audio]), media_type="audio/wav", headers=headers)


@router.post("/purge")
async def purge_now(current_user: User = Depends(get_current_user)) -> dict:
    if getattr(current_user, "role", "user") != "admin":
        raise HTTPException(status_code=403, detail="관리자만 즉시 삭제할 수 있습니다.")
    return {"ok": True, "data": purge_daily_content()}


start_cleanup_scheduler()
