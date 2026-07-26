import asyncio
import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool

from app.api.auth import get_current_user
from app.db.database import get_db
from app.db.models import User, UserPodcastVoiceSetting
from app.services.common_archive_service import register_common_archive

router = APIRouter()
API_URL = os.getenv("PODCAST_API_URL", "http://storymaker-v1-podcast:8003").rstrip("/")
MUSIC_LIBRARY_DIR = Path(os.getenv("STORYMAKER_MUSIC_LIBRARY_DIR", "/data/music")).resolve()
MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
MALE_VOICES = ["M1", "M2", "M3", "M4", "M5"]
FEMALE_VOICES = ["F1", "F2", "F3", "F4", "F5"]
SHUFFLE_VALUE = "__shuffle__"
# 작업 완료 조회가 반복되어도 최초 딸깍 제작물과 같은 보관함 행을 갱신하기 위한 연결표입니다.
PODCAST_ARCHIVE_GROUP_KEYS: dict[str, str] = {}


class PodcastVoiceSettingsRequest(BaseModel):
    male_voice: str | None = None
    female_voice: str | None = None


class PodcastRequest(BaseModel):
    project_key: str = Field(min_length=1, max_length=120, pattern=r"^[^/\\]+$")
    archive_group_key: str = Field(default="", max_length=180)
    script: str = Field(min_length=1, max_length=100_000)
    male_voice: str = SHUFFLE_VALUE
    female_voice: str = SHUFFLE_VALUE
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    music_random: bool = True
    music_file: str = ""
    music_volume: float = Field(default=0.3, ge=0, le=1)
    voice_volume: float = Field(default=1.0, ge=0, le=2)
    tts_engine: str = "supertonic"


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_voice(value: str | None, allowed: list[str]) -> str | None:
    voice = (value or "").strip().upper()
    if voice in {"", SHUFFLE_VALUE.upper(), "SHUFFLE", "RANDOM"}:
        return None
    if voice not in allowed:
        raise HTTPException(status_code=422, detail="지원하지 않는 목소리 값입니다.")
    return voice


def load_or_create_voice_setting(db: Session, user: User) -> UserPodcastVoiceSetting:
    setting = db.query(UserPodcastVoiceSetting).filter(UserPodcastVoiceSetting.user_id == user.id).first()
    if setting:
        return setting
    stamp = now_iso()
    setting = UserPodcastVoiceSetting(
        user_id=user.id,
        male_voice=None,
        female_voice=None,
        male_bag_json="[]",
        female_bag_json="[]",
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def next_from_shuffle_bag(raw_bag: str | None, allowed: list[str]) -> tuple[str, str]:
    try:
        bag = json.loads(raw_bag or "[]")
        if not isinstance(bag, list):
            bag = []
    except Exception:
        bag = []
    bag = [v for v in bag if v in allowed]
    if not bag:
        bag = allowed[:]
        random.shuffle(bag)
    selected = bag.pop(0)
    return selected, json.dumps(bag, ensure_ascii=False)


def resolve_voice_selection(db: Session, user: User, male_voice: str | None, female_voice: str | None) -> dict:
    setting = load_or_create_voice_setting(db, user)
    selected_male = normalize_voice(male_voice, MALE_VOICES)
    selected_female = normalize_voice(female_voice, FEMALE_VOICES)

    setting.male_voice = selected_male
    setting.female_voice = selected_female

    if selected_male:
        male_final = selected_male
        male_mode = "Fixed"
    else:
        male_final, setting.male_bag_json = next_from_shuffle_bag(setting.male_bag_json, MALE_VOICES)
        male_mode = "Shuffle"

    if selected_female:
        female_final = selected_female
        female_mode = "Fixed"
    else:
        female_final, setting.female_bag_json = next_from_shuffle_bag(setting.female_bag_json, FEMALE_VOICES)
        female_mode = "Shuffle"

    setting.updated_at = now_iso()
    db.commit()

    return {
        "male_voice": male_final,
        "female_voice": female_final,
        "male_mode": male_mode,
        "female_mode": female_mode,
    }


def serialize_voice_setting(setting: UserPodcastVoiceSetting) -> dict:
    return {
        "male_voice": setting.male_voice or "",
        "female_voice": setting.female_voice or "",
        "male_mode": "Fixed" if setting.male_voice else "Shuffle",
        "female_mode": "Fixed" if setting.female_voice else "Shuffle",
    }


def normalize_phone_numbers_for_tts(text: str) -> str:
    """TTS 엔진에 넘기기 전 전화번호만 한국어 발음으로 변환합니다.
    SRT와 화면 저장용 원본 대본은 바꾸지 않습니다.
    예: 010-8284-5584 -> 공일공, 팔이팔사, 오오팔사
    """
    import re

    digit_ko = {
        "0": "공", "1": "일", "2": "이", "3": "삼", "4": "사",
        "5": "오", "6": "육", "7": "칠", "8": "팔", "9": "구",
    }

    def read_digits(value: str) -> str:
        return "".join(digit_ko.get(ch, ch) for ch in value)

    phone_pattern = re.compile(r"(?<!\\d)(01[016789])[-.\\s]?(\\d{3,4})[-.\\s]?(\\d{4})(?!\\d)")

    def repl(match: re.Match) -> str:
        first, middle, last = match.groups()
        return f"{read_digits(first)}, {read_digits(middle)}, {read_digits(last)}"

    return phone_pattern.sub(repl, text or "")


def normalize_podcast_speaker_tags(script: str, male_voice: str, female_voice: str) -> str:
    """
    StoryMaker 표시용 화자 태그를 실제 TTS 엔진 화자 태그로 변환합니다.

    지원 입력:
    [남성] / [여성]
    [남성]: 대사 / [여성] 대사
    #M / #F
    #M1~#M5 / #F1~#F5
    #M1 대사 / #F1 대사

    출력 원칙:
    #M1, #F1 같은 화자 태그는 반드시 단독 행으로 분리합니다.
    podcast_generator.pyw는 화자 태그가 대사와 같은 줄에 붙으면 세그먼트 파싱에 실패할 수 있습니다.
    """
    male = (male_voice or "M1").strip().upper()
    female = (female_voice or "F1").strip().upper()
    if not re.fullmatch(r"M[1-5]", male):
        male = "M1"
    if not re.fullmatch(r"F[1-5]", female):
        female = "F1"

    text = (script or "").replace("\r\n", "\n").replace("\r", "\n")

    # StoryMaker 대본 형식([여성], [남성])을 먼저 표준 화자 태그로 치환합니다.
    # 태그가 단독 행이든 대사 앞에 붙어 있든 모두 줄 분리되도록 처리합니다.
    text = re.sub(r"\s*\[\s*남성\s*\]\s*[:：\-–—]?\s*", f"\n#{male}\n", text)
    text = re.sub(r"\s*\[\s*여성\s*\]\s*[:：\-–—]?\s*", f"\n#{female}\n", text)

    # #M, #F, #M1~#M5, #F1~#F5 형태도 단독 행으로 강제 분리합니다.
    # 예: '#F1 안녕하세요 #M1 반갑습니다' -> '#F1\n안녕하세요\n#M1\n반갑습니다'
    def replace_hash_tag(match: re.Match) -> str:
        raw = match.group(1).upper()
        if raw == "M":
            voice = male
        elif raw == "F":
            voice = female
        elif raw.startswith("M"):
            voice = male
        else:
            voice = female
        return f"\n#{voice}\n"

    text = re.sub(r"\s*#(M[1-5]?|F[1-5]?)\s*[:：\-–—]?\s*", replace_hash_tag, text, flags=re.IGNORECASE)

    # 빈 줄은 정리하되, 화자 태그와 대사는 명확히 분리합니다.
    cleaned_lines = []
    previous_blank = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if cleaned_lines and not previous_blank:
                cleaned_lines.append("")
                previous_blank = True
            continue
        cleaned_lines.append(stripped)
        previous_blank = False

    normalized = "\n".join(cleaned_lines).strip()

    # 혹시 모든 정리 후에도 화자 태그와 대사가 같은 줄에 남는 예외를 한 번 더 방어합니다.
    normalized = re.sub(r"(^|\n)(#(?:M|F)[1-5])\s+", r"\1\2\n", normalized)
    return normalized


def upstream_headers():
    key = os.getenv("SUPERTONIC_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Podcast API key is not configured")
    return {"Authorization": f"Bearer {key}"}


def upstream_error(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        detail = exc.response.text
        raise HTTPException(status_code=exc.response.status_code, detail=detail)
    raise HTTPException(status_code=502, detail=f"Podcast API connection failed: {exc}")


@router.get("/podcast/public/music/manifest")
def public_podcast_music_manifest():
    if not MUSIC_LIBRARY_DIR.exists() or not MUSIC_LIBRARY_DIR.is_dir():
        return {"ok": True, "count": 0, "items": []}
    items = []
    for path in sorted(MUSIC_LIBRARY_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in MUSIC_EXTENSIONS:
            continue
        stat = path.stat()
        items.append({
            "name": path.name,
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
            "download_url": f"/api/podcast/public/music/file/{quote(path.name, safe='')}",
        })
    return {"ok": True, "count": len(items), "items": items}


@router.get("/podcast/public/music/file/{filename}")
def public_podcast_music_file(filename: str):
    safe_name = Path(filename).name
    if safe_name != filename or Path(safe_name).suffix.lower() not in MUSIC_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Music file not found")
    path = (MUSIC_LIBRARY_DIR / safe_name).resolve()
    if path.parent != MUSIC_LIBRARY_DIR or not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Music file not found")
    media_type = "audio/mpeg" if path.suffix.lower() == ".mp3" else "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/podcast/music/manifest")
def podcast_music_manifest(_: User = Depends(get_current_user)):
    if not MUSIC_LIBRARY_DIR.exists() or not MUSIC_LIBRARY_DIR.is_dir():
        return {"ok": True, "count": 0, "items": []}
    items = []
    for path in sorted(MUSIC_LIBRARY_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in MUSIC_EXTENSIONS:
            continue
        stat = path.stat()
        items.append({
            "name": path.name,
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
            "download_url": f"/api/podcast/music/file/{quote(path.name, safe='')}",
        })
    return {"ok": True, "count": len(items), "items": items}


@router.get("/podcast/music/file/{filename}")
def podcast_music_file(filename: str, _: User = Depends(get_current_user)):
    safe_name = Path(filename).name
    if safe_name != filename or Path(safe_name).suffix.lower() not in MUSIC_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Music file not found")
    path = (MUSIC_LIBRARY_DIR / safe_name).resolve()
    if path.parent != MUSIC_LIBRARY_DIR or not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Music file not found")
    media_type = "audio/mpeg" if path.suffix.lower() == ".mp3" else "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/podcast/health")
def podcast_health():
    try:
        response = httpx.get(f"{API_URL}/health", timeout=5)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)


@router.get("/podcast/voice-settings")
def get_podcast_voice_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    setting = load_or_create_voice_setting(db, current_user)
    return serialize_voice_setting(setting)


@router.put("/podcast/voice-settings")
def update_podcast_voice_settings(
    req: PodcastVoiceSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    setting = load_or_create_voice_setting(db, current_user)
    setting.male_voice = normalize_voice(req.male_voice, MALE_VOICES)
    setting.female_voice = normalize_voice(req.female_voice, FEMALE_VOICES)
    setting.updated_at = now_iso()
    db.commit()
    db.refresh(setting)
    return serialize_voice_setting(setting)


@router.post("/podcast/public/run")
def run_public_podcast(req: PodcastRequest):
    """로그인 없는 공개 체험용 TTS/BGM 작업 요청.

    회원 설정·DB·공통 보관함에는 기록하지 않고 기존 Podcast 엔진만 안전하게 재사용합니다.
    """
    try:
        payload = req.model_dump()
        male_requested = normalize_voice(payload.get("male_voice"), MALE_VOICES)
        female_requested = normalize_voice(payload.get("female_voice"), FEMALE_VOICES)
        payload["male_voice"] = male_requested or random.choice(MALE_VOICES)
        payload["female_voice"] = female_requested or random.choice(FEMALE_VOICES)
        payload["script"] = normalize_podcast_speaker_tags(
            payload.get("script", ""),
            payload["male_voice"],
            payload["female_voice"],
        )
        response = httpx.post(
            f"{API_URL}/api/podcast/run",
            data=payload,
            headers=upstream_headers(),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        data["project_key"] = req.project_key
        data["voice_selection"] = {
            "male_voice": payload["male_voice"],
            "female_voice": payload["female_voice"],
            "male_mode": "Fixed" if male_requested else "Shuffle",
            "female_mode": "Fixed" if female_requested else "Shuffle",
        }
        return data
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)


@router.get("/podcast/public/jobs/{job_id}")
def public_podcast_job(job_id: str):
    try:
        response = httpx.get(
            f"{API_URL}/api/jobs/{quote(job_id, safe='')}",
            headers=upstream_headers(),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("result"):
            project_key = data["result"].get("project_key", data.get("project_key", ""))
            encoded = quote(project_key, safe="")
            data["result"].update({
                "mp3_url": f"/api/podcast/public/media/{encoded}/mp3",
                "srt_url": f"/api/podcast/public/media/{encoded}/srt",
                "thumbnail_url": data["result"].get("thumbnail_url"),
            })
        return data
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)


@router.get("/podcast/public/media/{project_key}/{kind}")
def public_podcast_media(project_key: str, kind: str):
    if kind not in {"mp3", "srt"}:
        raise HTTPException(status_code=404, detail="Unsupported media type")
    try:
        response = httpx.get(
            f"{API_URL}/media/podcast/{quote(project_key, safe='')}/{kind}",
            headers=upstream_headers(),
            timeout=120,
        )
        response.raise_for_status()
        media_type = response.headers.get("content-type") or ("audio/mpeg" if kind == "mp3" else "text/plain; charset=utf-8")
        disposition = "inline" if kind == "mp3" else "attachment"
        return Response(
            response.content,
            media_type=media_type,
            headers={
                "Content-Type": media_type,
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(project_key, safe='')}.{kind}",
                "Cache-Control": "no-store",
            },
        )
    except httpx.HTTPError as exc:
        upstream_error(exc)


@router.post("/podcast/run")
async def run_podcast(
    req: PodcastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payload = req.model_dump()
        voice_selection = resolve_voice_selection(
            db,
            current_user,
            payload.get("male_voice"),
            payload.get("female_voice"),
        )
        payload["male_voice"] = voice_selection["male_voice"]
        payload["female_voice"] = voice_selection["female_voice"]
        payload["script"] = normalize_podcast_speaker_tags(
            payload.get("script", ""),
            payload.get("male_voice", "M1"),
            payload.get("female_voice", "F1"),
        )
        
        def _send_request():
            return httpx.post(
                f"{API_URL}/api/podcast/run",
                data=payload,
                headers=upstream_headers(),
                timeout=30,
            )
            
        response = await run_in_threadpool(_send_request)
        response.raise_for_status()
        data = response.json()
        data["project_key"] = req.project_key
        data["voice_selection"] = voice_selection
        archive_group_key = str(req.archive_group_key or "").strip()[:180]
        podcast_job_id = str(data.get("job_id") or "").strip()
        if archive_group_key and podcast_job_id:
            PODCAST_ARCHIVE_GROUP_KEYS[podcast_job_id] = archive_group_key
        data["archive_group_key"] = archive_group_key
        return data
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)


@router.get("/podcast/jobs/{job_id}")
def podcast_job(job_id: str, current_user: User = Depends(get_current_user)):
    try:
        response = httpx.get(
            f"{API_URL}/api/jobs/{quote(job_id, safe='')}",
            headers=upstream_headers(),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        
        # 종결 상태인 경우 메모리 누수를 방지하기 위해 전역 딕셔너리에서 키를 pop
        status = str(data.get("status") or "").lower()
        if status in {"completed", "failed", "cancelled"}:
            if status != "completed":
                PODCAST_ARCHIVE_GROUP_KEYS.pop(job_id, None)
                
        if data.get("result"):
            project_key = data["result"].get("project_key", data.get("project_key", ""))
            encoded = quote(project_key, safe="")
            data["result"].update({
                "mp3_url": f"/api/podcast/media/{encoded}/mp3",
                "srt_url": f"/api/podcast/media/{encoded}/srt",
                "thumbnail_url": data["result"].get("thumbnail_url"),
            })
            try:
                archive_info = register_common_archive(
                    user_id=current_user.id,
                    source="podcast",
                    source_job_id=job_id,
                    archive_group_key=PODCAST_ARCHIVE_GROUP_KEYS.get(job_id, "") or project_key,
                    title=f"팟캐스트 · {project_key}",
                    status="podcast_completed",
                    raw_result=str(data["result"].get("script") or ""),
                    outputs={"podcast50": str(data["result"].get("script") or "")},
                    media={
                        "mp3_url": data["result"].get("mp3_url"),
                        "srt_url": data["result"].get("srt_url"),
                        "thumbnail_url": data["result"].get("thumbnail_url"),
                    },
                    extra={"podcast_job": data},
                )
                if archive_info.get("ok"):
                    data["result"]["archive_job_id"] = archive_info.get("archive_job_id")
                    # 보관함에 최종 등록 성공했으므로 전역 딕셔너리에서 키 삭제
                    PODCAST_ARCHIVE_GROUP_KEYS.pop(job_id, None)
            except Exception:
                pass
        return data
    except (httpx.HTTPError, ValueError) as exc:
        upstream_error(exc)


@router.get("/podcast/media/{project_key}/{kind}")
def podcast_media(project_key: str, kind: str, _: User = Depends(get_current_user)):
    if kind not in {"mp3", "srt"}:
        raise HTTPException(status_code=404, detail="Unsupported media type")
    try:
        response = httpx.get(
            f"{API_URL}/media/podcast/{quote(project_key, safe='')}/{kind}",
            headers=upstream_headers(),
            timeout=120,
        )
        response.raise_for_status()
        # ponytail: in-memory proxy is enough for podcast files; stream if files become large.
        media_type = response.headers.get("content-type") or ("audio/mpeg" if kind == "mp3" else "text/plain; charset=utf-8")
        disposition = "inline" if kind == "mp3" else "attachment"
        return Response(
            response.content,
            media_type=media_type,
            headers={
                "Content-Type": media_type,
                "Content-Disposition":
                    f"{disposition}; filename*=UTF-8''{quote(project_key, safe='')}.{kind}",
                "Cache-Control": "no-store",
            },
        )
    except httpx.HTTPError as exc:
        upstream_error(exc)
