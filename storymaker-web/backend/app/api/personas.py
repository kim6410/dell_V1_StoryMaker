# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 업체 페르소나 API 라우터 (personas.py)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from pathlib import Path
import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from app.db.database import get_db
from app.db.models import User, UserPersona
from app.api.auth import get_current_user
from app.services import StoryMakerService
from app.schemas import PersonaUpdate, PersonaResponse, CommonResponse
from app.schemas.persona import UserPersonaUpsert
from app.core.region_display import format_region_display
from app.core.phone_number import normalize_korean_phone_number

router = APIRouter()


def normalize_blog_content_length(value) -> int:
    try:
        parsed = int(value or 1500)
    except (TypeError, ValueError):
        parsed = 1500
    return parsed if parsed in {1200, 1500, 2000} else 1500


def serialize_user_persona(persona: UserPersona) -> dict:
    try:
        keywords = json.loads(persona.keywords_json or "[]")
    except (TypeError, json.JSONDecodeError):
        keywords = []
    try:
        default_tones = json.loads(getattr(persona, "default_tones_json", "[]") or "[]")
    except (TypeError, json.JSONDecodeError):
        default_tones = []
    return {
        "id": persona.id,
        "company_name": persona.company_name,
        "phone_number": normalize_korean_phone_number(persona.phone_number),
        "website_url": getattr(persona, "website_url", None) or "",
        "region": format_region_display(getattr(persona, "region", None) or ""),
        "region_alias": str(getattr(persona, "region_alias", "") or "").strip(),
        "industry_key": getattr(persona, "industry_key", None) or "general",
        "default_style": getattr(persona, "default_style", None) or "네이버 블로그",
        "blog_content_length": normalize_blog_content_length(getattr(persona, "blog_content_length", 1500)),
        "default_tones": default_tones,
        "is_default": bool(persona.is_default),
        "keywords": keywords,
        "content": persona.content,
        "created_at": persona.created_at,
        "updated_at": persona.updated_at,
    }


def clean_persona_payload(req: UserPersonaUpsert) -> tuple[str, str, str, str, str, str, str, int, list[str], list[str], str]:
    company_name = req.company_name.strip()
    phone_number = normalize_korean_phone_number(req.phone_number)
    website_url = (req.website_url or "").strip()
    region = format_region_display(req.region)
    region_alias = re.sub(r"\s+", " ", str(getattr(req, "region_alias", "") or "").strip())
    industry_candidates = {"general", "home_repair", "boiler_facility", "appliance_clean", "general_cleaning", "window_screen", "key_doorlock", "lighting_electric", "drain_unclog", "restaurant", "meat_korean", "bakery_dessert", "pub_bar", "mealkit_sidedish", "cafe", "workshop_class", "partyroom_studio", "beauty_wellness", "hair_salon", "nail_art", "skin_care", "fitness_pt", "body_massage", "car_repair", "car_detailing", "car_rental", "pet_beauty_hotel", "veterinary_clinic", "flower_shop", "kids_cafe", "real_estate", "education_academy", "study_cafe", "professional_service", "moving_service", "camping", "logistics", "copy_print_shop"}
    style_candidates = {"네이버 블로그", "티스토리", "인스타그램", "스레드", "브런치스토리", "워드프레스"}
    tone_candidates = {"따뜻함", "전문가", "친근함", "신뢰감", "현장감", "진정성", "차분함", "활기", "담백함", "순박함", "진지함"}
    industry_key = (req.industry_key or "general").strip()
    if industry_key not in industry_candidates:
        industry_key = "general"
    default_style = (getattr(req, "default_style", "") or "네이버 블로그").strip()
    if default_style not in style_candidates:
        default_style = "네이버 블로그"
    blog_content_length = normalize_blog_content_length(getattr(req, "blog_content_length", 1500))
    default_tones = []
    for tone in getattr(req, "default_tones", []) or []:
        cleaned_tone = str(tone).strip()
        if cleaned_tone in tone_candidates and cleaned_tone not in default_tones:
            default_tones.append(cleaned_tone)
    if not default_tones:
        default_tones = ["따뜻함", "전문가"]
    content = req.content.strip()
    keywords = []
    for keyword in req.keywords:
        cleaned = keyword.strip()
        if cleaned and cleaned not in keywords:
            keywords.append(cleaned)
    missing_fields = []
    if not company_name:
        missing_fields.append("업체명")
    if not region:
        missing_fields.append("지역")
    if not phone_number:
        missing_fields.append("전화번호")
    if not keywords:
        missing_fields.append("핵심 키워드")
    if len(content) < 10:
        missing_fields.append("페르소나 상세 설명")
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"필수 입력 항목을 확인해 주세요: {', '.join(missing_fields)}",
        )
    return company_name, phone_number, website_url, region, region_alias, industry_key, default_style, blog_content_length, default_tones[:11], keywords[:30], content


@router.get("/auth/personas", response_model=CommonResponse)
def list_my_personas(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    personas = db.query(UserPersona).filter(UserPersona.user_id == current_user.id).order_by(UserPersona.is_default.desc(), UserPersona.updated_at.desc()).all()
    if personas and not any(p.is_default for p in personas):
        personas[0].is_default = True
        db.commit()
        db.refresh(personas[0])
    return CommonResponse(ok=True, data=[serialize_user_persona(p) for p in personas], message="")


@router.post("/auth/personas", response_model=CommonResponse)
def create_my_persona(req: UserPersonaUpsert, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    company_name, phone_number, website_url, region, region_alias, industry_key, default_style, blog_content_length, default_tones, keywords, content = clean_persona_payload(req)
    if getattr(current_user, "username", "") == ("g" + "uest"):
        phone_number = "-".join(["010", "1234", "5678"])
    duplicate = db.query(UserPersona).filter(
        UserPersona.user_id == current_user.id,
        func.lower(UserPersona.company_name) == company_name.lower()
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="같은 업체명의 페르소나가 이미 있습니다.",
        )
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.query(UserPersona).filter(UserPersona.user_id == current_user.id).update({UserPersona.is_default: False})
    persona = UserPersona(user_id=current_user.id, company_name=company_name, phone_number=phone_number, website_url=website_url, region=region, region_alias=region_alias, industry_key=industry_key, default_style=default_style, blog_content_length=blog_content_length, default_tones_json=json.dumps(default_tones, ensure_ascii=False), is_default=True, keywords_json=json.dumps(keywords, ensure_ascii=False), content=content, created_at=stamp, updated_at=stamp)
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return CommonResponse(ok=True, data=serialize_user_persona(persona), message="페르소나가 저장되었습니다.")


@router.put("/auth/personas/{persona_id}", response_model=CommonResponse)
def update_my_persona(persona_id: int, req: UserPersonaUpsert, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    persona = db.query(UserPersona).filter(UserPersona.id == persona_id, UserPersona.user_id == current_user.id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="페르소나를 찾을 수 없습니다.")
    company_name, phone_number, website_url, region, region_alias, industry_key, default_style, blog_content_length, default_tones, keywords, content = clean_persona_payload(req)
    if getattr(current_user, "username", "") == ("g" + "uest"):
        phone_number = "-".join(["010", "1234", "5678"])
    duplicate = db.query(UserPersona).filter(
        UserPersona.user_id == current_user.id,
        UserPersona.id != persona_id,
        func.lower(UserPersona.company_name) == company_name.lower()
    ).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="같은 업체명의 페르소나가 이미 있습니다.")
    persona.company_name = company_name
    persona.phone_number = phone_number
    persona.website_url = website_url
    persona.region = region
    persona.region_alias = region_alias
    persona.industry_key = industry_key
    persona.default_style = default_style
    persona.blog_content_length = blog_content_length
    persona.default_tones_json = json.dumps(default_tones, ensure_ascii=False)
    db.query(UserPersona).filter(UserPersona.user_id == current_user.id, UserPersona.id != persona_id).update({UserPersona.is_default: False})
    persona.is_default = True
    persona.keywords_json = json.dumps(keywords, ensure_ascii=False)
    persona.content = content
    persona.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    db.refresh(persona)
    return CommonResponse(ok=True, data=serialize_user_persona(persona), message="페르소나가 수정되었습니다.")


PERSONA_TTS_CACHE_ROOT = Path(os.getenv("STORYMAKER_PERSONA_TTS_CACHE_DIR", "/app/app/static/tts_cache/personas"))
PERSONA_TTS_URL = os.getenv("STORYMAKER_TTS_URL", "http://host.docker.internal:8003/api/tts/persona")
PERSONA_TTS_API_KEY = os.getenv("SUPERTONIC_API_KEY", "")
PERSONA_TTS_VOICE = "F1"
PERSONA_TTS_SPEED = 1.3


def _persona_tts_cache_path(user_id: int, persona_id: int, content: str) -> Path:
    digest = hashlib.sha256(f"{PERSONA_TTS_VOICE}|{PERSONA_TTS_SPEED}|{content}".encode("utf-8")).hexdigest()
    return PERSONA_TTS_CACHE_ROOT / str(user_id) / f"persona_{persona_id}_{PERSONA_TTS_VOICE.lower()}_{digest}.wav"


def _generate_persona_tts(content: str, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "model": "supertonic-3",
        "input": content,
        "voice": PERSONA_TTS_VOICE,
        "response_format": "wav",
        "speed": PERSONA_TTS_SPEED,
    }, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "audio/wav"}
    if PERSONA_TTS_API_KEY:
        headers["Authorization"] = f"Bearer {PERSONA_TTS_API_KEY}"
    request = urllib.request.Request(
        PERSONA_TTS_URL,
        data=payload,
        headers=headers,
        method="POST",
    )
    temp_path = None
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            audio_data = response.read()
        if len(audio_data) < 44 or not audio_data.startswith(b"RIFF"):
            raise RuntimeError("TTS 서버가 올바른 WAV 파일을 반환하지 않았습니다.")
        with tempfile.NamedTemporaryFile(dir=target_path.parent, suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_path = Path(temp_file.name)
        temp_path.replace(target_path)
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", "replace")
        raise RuntimeError(f"TTS 서버 응답 오류: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("TTS 서버에 연결할 수 없습니다.") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@router.get("/auth/personas/{persona_id}/tts")
def play_persona_tts(
    persona_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    persona = db.query(UserPersona).filter(
        UserPersona.id == persona_id,
        UserPersona.user_id == current_user.id,
    ).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="페르소나를 찾을 수 없습니다.")

    content = (persona.content or "").strip()
    if len(content) < 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="재생할 페르소나 상세 설명이 없습니다.")

    cache_path = _persona_tts_cache_path(current_user.id, persona.id, content)
    cache_hit = cache_path.exists() and cache_path.stat().st_size >= 44
    print(f"[persona-tts] request user={current_user.id} persona={persona.id} cache_hit={cache_hit} path={cache_path}", flush=True)
    if not cache_hit:
        try:
            _generate_persona_tts(content, cache_path)
            print(f"[persona-tts] generated persona={persona.id} bytes={cache_path.stat().st_size}", flush=True)
        except RuntimeError as exc:
            print(f"[persona-tts] failed persona={persona.id} error={exc}", flush=True)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return FileResponse(
        path=str(cache_path),
        media_type="audio/wav",
        filename=f"persona-{persona.id}-{PERSONA_TTS_VOICE}.wav",
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-StoryMaker-TTS-Cache": "HIT" if cache_hit else "MISS",
            "X-StoryMaker-TTS-Voice": PERSONA_TTS_VOICE,
        },
    )


@router.put("/auth/personas/{persona_id}/default", response_model=CommonResponse)
def set_default_persona(persona_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    persona = db.query(UserPersona).filter(UserPersona.id == persona_id, UserPersona.user_id == current_user.id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="페르소나를 찾을 수 없습니다.")
    db.query(UserPersona).filter(UserPersona.user_id == current_user.id).update({UserPersona.is_default: False})
    persona.is_default = True
    db.commit()
    db.refresh(persona)
    return CommonResponse(ok=True, data=serialize_user_persona(persona), message="기본 페르소나로 설정되었습니다.")


@router.delete("/auth/personas/{persona_id}", response_model=CommonResponse)
def delete_my_persona(persona_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    persona = db.query(UserPersona).filter(UserPersona.id == persona_id, UserPersona.user_id == current_user.id).first()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="페르소나를 찾을 수 없습니다.")
    was_default = persona.is_default
    db.delete(persona)
    db.commit()
    if was_default:
        next_persona = db.query(UserPersona).filter(UserPersona.user_id == current_user.id).order_by(UserPersona.updated_at.desc()).first()
        if next_persona:
            next_persona.is_default = True
            db.commit()
    return CommonResponse(ok=True, data=None, message="페르소나가 삭제되었습니다.")

@router.get("/personas/{company_name}", response_model=CommonResponse)
def get_persona(company_name: str, db: Session = Depends(get_db)):
    """
    지정된 업체명을 기준으로 페르소나 프로필을 조회합니다.
    없을 경우 빈 프로필 규격(content="")을 반환하여 프론트엔드가 작성창을 띄울 수 있도록 지원합니다.
    """
    try:
        persona = StoryMakerService.get_persona(db, company_name)
        if not persona:
            # 빈 페르소나 데이터로 부드럽게 복구 및 응답
            return CommonResponse(
                ok=True, 
                data={"company_id": 0, "content": "", "created_at": "", "updated_at": ""}, 
                message="등록된 페르소나가 없으므로 신규 작성 상태로 응답합니다."
            )
            
        data = PersonaResponse.model_validate(persona)
        return CommonResponse(ok=True, data=data, message="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/personas/{company_name}", response_model=CommonResponse)
def save_persona(company_name: str, req: PersonaUpdate, db: Session = Depends(get_db)):
    """
    업체의 페르소나 정보를 저장(등록/수정)하고 파일 동기화를 트리거합니다.
    """
    try:
        persona = StoryMakerService.save_persona(db, company_name, req.content)
        data = PersonaResponse.model_validate(persona)
        return CommonResponse(ok=True, data=data, message="페르소나가 성공적으로 저장되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
