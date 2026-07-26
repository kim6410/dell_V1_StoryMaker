# -*- coding: utf-8 -*-
"""StoryMaker 공통 콘텐츠 보관함 브리지.

새 글, 팟캐스트, 숏폼처럼 서로 다른 작업 흐름에서 나온 결과를 하나의
공통 제작 식별자(archive_group_key) 기준으로 합쳐 저장합니다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx

from app.db.mobile_one_shot_repository import (
    list_mobile_one_shot_result_paths,
    upsert_mobile_one_shot_job,
)
from app.db.database import SessionLocal
from app.db.models import UserPersona
from app.services.content_asset_service import sync_content_archive_assets

KST = ZoneInfo("Asia/Seoul")
KST_DATE_FORMAT = "%Y%m%d"
TERMINAL_STATUSES = {
    "completed",
    "done",
    "complete",
    "podcast_completed",
    "shortform_completed",
    "thumbnail_done",
    "thumbnail_ready",
}
GENERIC_TITLE_PREFIXES = (
    "팟캐스트 ·",
    "숏폼 ·",
    "썸네일 ·",
    "podcast ·",
    "shortform ·",
)
PC_PODCAST_START_DELAY_SECONDS = 0.2
_PC_PODCAST_WRITE_LOCK = threading.Lock()


def _now() -> datetime:
    """KST 기준의 timezone 없는 datetime을 반환합니다.

    기존 DB/프론트가 timezone 없는 문자열을 사용하므로 저장 형식은 유지하되,
    값 자체는 반드시 한국시간으로 맞춥니다.
    """
    return datetime.now(KST).replace(tzinfo=None)


def _output_root() -> Path:
    return Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))


def _default_persona_payload(user_id: int) -> dict[str, Any] | None:
    """PC 보관함 파일명에 사용할 기본 업체명만 사용자 DB에서 읽습니다."""
    db = SessionLocal()
    try:
        persona = (
            db.query(UserPersona)
            .filter(UserPersona.user_id == int(user_id))
            .order_by(UserPersona.is_default.desc(), UserPersona.updated_at.desc())
            .first()
        )
        if not persona or not str(persona.company_name or "").strip():
            return None
        return {
            "id": persona.id,
            "company_name": str(persona.company_name).strip(),
            "business_name": str(persona.company_name).strip(),
        }
    finally:
        db.close()


def _pc_podcast_script(data: dict[str, Any]) -> str:
    outputs = data.get("outputs") or {}
    return str(
        outputs.get("podcast50")
        or outputs.get("PODCAST_50")
        or outputs.get("podcast80")
        or outputs.get("PODCAST_80")
        or ""
    ).strip()


def _write_pc_podcast_claim(claim_file: Path, payload: dict[str, Any]) -> None:
    temp_file = claim_file.with_suffix(".json.tmp")
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(claim_file)


def _run_pc_podcast_once(
    *,
    result_file: Path,
    claim_file: Path,
    user_id: int,
    source_job_id: str,
) -> None:
    claim = {
        "owner": "pc-backend",
        "source_job_id": source_job_id,
        "status": "submitting",
        "started_at": _now().isoformat(timespec="milliseconds"),
    }
    _write_pc_podcast_claim(claim_file, claim)
    try:
        with _PC_PODCAST_WRITE_LOCK:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            media = data.setdefault("media", {})
            if media.get("podcast_job_id") or media.get("mp3_url") or media.get("mp3_path"):
                claim.update({"status": "existing", "podcast_job_id": media.get("podcast_job_id")})
                _write_pc_podcast_claim(claim_file, claim)
                return
            script = _pc_podcast_script(data)
        if not script:
            claim.update({"status": "script_missing"})
            _write_pc_podcast_claim(claim_file, claim)
            return

        # 지연 import로 common_archive_service <-> podcast 모듈 순환 import를 피합니다.
        from app.api.podcast import (
            PODCAST_ARCHIVE_GROUP_KEYS,
            load_or_create_voice_setting,
            normalize_podcast_speaker_tags,
            resolve_voice_selection,
        )
        from app.db.database import SessionLocal
        from app.db.models import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                raise RuntimeError("PC podcast user not found")
            setting = load_or_create_voice_setting(db, user)
            voice_selection = resolve_voice_selection(db, user, setting.male_voice, setting.female_voice)
        finally:
            db.close()

        normalized_script = normalize_podcast_speaker_tags(
            script,
            voice_selection["male_voice"],
            voice_selection["female_voice"],
        )
        api_url = os.getenv("PODCAST_API_URL", "http://host.docker.internal:8003").rstrip("/")
        api_key = os.getenv("SUPERTONIC_API_KEY", "")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        response = httpx.post(
            f"{api_url}/api/podcast/run",
            data={
                "project_key": source_job_id,
                "script": normalized_script,
                "male_voice": voice_selection["male_voice"],
                "female_voice": voice_selection["female_voice"],
                "speed": "1.3",
                "music_random": "true",
                # PC 화면의 10% 값. Supertonic 내부 단위는 0.0~1.0이다.
                "music_volume": "0.1",
                "voice_volume": "1.0",
                "tts_engine": "supertonic",
            },
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        podcast_data = response.json()
        podcast_job_id = str(podcast_data.get("job_id") or "").strip()
        if not podcast_job_id:
            raise RuntimeError("PC podcast response has no job_id")

        with _PC_PODCAST_WRITE_LOCK:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            media = data.setdefault("media", {})
            # 원자 claim 때문에 여기에는 한 작업 ID만 기록될 수 있습니다.
            if not media.get("podcast_job_id"):
                media.update({
                    "status": "podcast_submitted",
                    "podcast_status": "submitted",
                    "podcast_job_id": podcast_job_id,
                    "project_key": source_job_id,
                    "message": "PC 백엔드가 팟캐스트 생성을 시작했습니다.",
                })
                timing = data.setdefault("pipeline", {}).setdefault("timing", {})
                timing["pc_podcast_submit_at"] = _now().isoformat(timespec="milliseconds")
                timing["pc_podcast_owner"] = "backend"
                temp_file = result_file.with_suffix(".json.tmp")
                temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                temp_file.replace(result_file)
        PODCAST_ARCHIVE_GROUP_KEYS[podcast_job_id] = source_job_id
        claim.update({
            "status": "submitted",
            "podcast_job_id": podcast_job_id,
            "submitted_at": _now().isoformat(timespec="milliseconds"),
            "voice_selection": voice_selection,
            "music_random": True,
            "music_volume_percent": 10,
            "music_volume_internal": 0.1,
        })
        _write_pc_podcast_claim(claim_file, claim)
    except Exception as exc:
        # 모호한 네트워크 실패에서 자동 재시도하면 실제로 접수된 작업을 중복 생성할 수 있다.
        claim.update({"status": "failed", "error": str(exc)[:500]})
        _write_pc_podcast_claim(claim_file, claim)
        with _PC_PODCAST_WRITE_LOCK:
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
                data.setdefault("extra", {})["pc_podcast_start_error"] = str(exc)[:500]
                temp_file = result_file.with_suffix(".json.tmp")
                temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                temp_file.replace(result_file)
            except Exception:
                pass


def _schedule_pc_podcast_once(
    *,
    data: dict[str, Any],
    result_file: Path,
    user_id: int,
) -> None:
    source_job_id = str(data.get("source_job_id") or data.get("archive_group_key") or "").strip()
    if (
        str(data.get("source") or "").strip() != "storymaker-main"
        or not source_job_id.startswith("storymaker_main_")
        or not _pc_podcast_script(data)
    ):
        return
    media = data.get("media") or {}
    if media.get("podcast_job_id") or media.get("mp3_url") or media.get("mp3_path"):
        return

    claim_file = result_file.parent / "pc_podcast_claim.json"
    try:
        descriptor = os.open(str(claim_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(descriptor)
    except FileExistsError:
        return
    timer = threading.Timer(
        PC_PODCAST_START_DELAY_SECONDS,
        _run_pc_podcast_once,
        kwargs={
            "result_file": result_file,
            "claim_file": claim_file,
            "user_id": int(user_id),
            "source_job_id": source_job_id,
        },
    )
    timer.daemon = True
    timer.start()


def _clean_text(value: Any, limit: int = 2000) -> str:
    return str(value or "").strip()[:limit]


def _parse_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(KST).replace(tzinfo=None)
        return parsed
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S", "%Y%m%d_%H%M%S"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None


def _datetime_from_epoch_text(value: Any) -> Optional[datetime]:
    """pipeline-1783936241635 같은 epoch millisecond를 KST로 변환합니다."""
    match = re.search(r"(?<!\d)(1\d{12})(?!\d)", str(value or ""))
    if not match:
        return None
    try:
        epoch_seconds = int(match.group(1)) / 1000.0
        return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).astimezone(KST).replace(tzinfo=None)
    except Exception:
        return None


def _created_datetime(source_job_id: str, media: dict[str, Any], extra: dict[str, Any], now: datetime) -> datetime:
    # 브라우저 pipeline ID의 epoch 시간이 가장 정확하며 UTC→KST 변환도 명확합니다.
    for candidate in (
        extra.get("archive_created_at"),
        extra.get("source_created_at"),
        extra.get("created_at"),
        media.get("created_at"),
        media.get("submitted_at"),
    ):
        parsed = _parse_datetime(candidate)
        if parsed is not None:
            return parsed
    for candidate in (
        extra.get("pipeline_id"),
        extra.get("project_key"),
        media.get("pipeline_id"),
        media.get("project_key"),
        source_job_id,
    ):
        parsed = _datetime_from_epoch_text(candidate)
        if parsed is not None:
            return parsed

    # 기존 storymaker_main_YYYYMMDDHHMMSS는 서버 UTC에서 만들어진 값이므로
    # 그대로 로컬시간으로 해석하지 않습니다. 등록 시점의 KST를 기준으로 저장합니다.
    return now


def _archive_job_id(group_key: str, created_at: datetime, user_id: int) -> str:
    stamp = created_at.strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha1(f"{user_id}:{group_key}".encode("utf-8")).hexdigest()[:8]
    return f"mob-{stamp}-{digest}"


def _extract_block(raw: str, block_name: str) -> str:
    text = str(raw or "")
    start_tag = f"[BLOCK:{block_name}]"
    start = text.find(start_tag)
    if start < 0:
        return ""
    rest = text[start + len(start_tag):]
    next_match = re.search(r"\n\s*\[BLOCK:[A-Z0-9_]+\]", rest)
    return (rest[: next_match.start()] if next_match else rest).strip()


def _first_title(value: str) -> str:
    for raw_line in str(value or "").splitlines():
        line = raw_line.strip().lstrip("-• ").strip()
        line = re.sub(r"^\d+[.)]\s*", "", line).strip()
        line = re.sub(r"^제목\s*[:：]\s*", "", line).strip()
        if line and len(line) >= 4:
            return line[:120]
    return ""


def _build_outputs(raw_result: str, explicit_outputs: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    outputs = dict(explicit_outputs or {})
    raw = str(raw_result or "")
    block_map = {
        "blog_titles": "BLOG_TITLES",
        "blog_post": "BLOG_POST",
        "blog_hashtags": "BLOG_HASHTAGS",
        "instagram": "INSTAGRAM_POST",
        "place": "NAVER_PLACE_NEWS",
        "google_business": "GOOGLE_BUSINESS_POST",
        "carrot": "CARROT_POST",
        "cardnews": "CAROUSEL_7",
        "podcast50": "PODCAST_50",
        "podcast80": "PODCAST_80",
    }
    for key, block_name in block_map.items():
        if not str(outputs.get(key) or "").strip():
            block = _extract_block(raw, block_name)
            if block:
                outputs[key] = block
    if not str(outputs.get("blog") or "").strip():
        blog_parts = [
            str(outputs.get("blog_titles") or "").strip(),
            str(outputs.get("blog_post") or "").strip(),
            str(outputs.get("blog_hashtags") or "").strip(),
        ]
        outputs["blog"] = "\n\n".join(part for part in blog_parts if part).strip() or raw[:5000]
    return outputs


def _merge_nonempty(old: Any, new: Any) -> Any:
    if isinstance(old, dict) or isinstance(new, dict):
        result = dict(old or {}) if isinstance(old, dict) else {}
        for key, value in (new or {}).items() if isinstance(new, dict) else []:
            if isinstance(value, dict):
                result[key] = _merge_nonempty(result.get(key), value)
            elif isinstance(value, list):
                if value:
                    result[key] = value
            elif value not in (None, ""):
                result[key] = value
        return result
    return new if new not in (None, "") else old


def _collect_group_keys(value: Any, found: Optional[list[str]] = None) -> list[str]:
    result = found if found is not None else []
    interesting = {
        "archive_group_key",
        "production_id",
        "root_job_id",
        "parent_job_id",
        "content_id",
        "pipeline_id",
        "project_key",
        "target_folder_id",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if key in interesting:
                clean = _clean_text(item, 180)
                if clean and clean not in result:
                    result.append(clean)
            if isinstance(item, (dict, list)):
                _collect_group_keys(item, result)
    elif isinstance(value, list):
        for item in value:
            _collect_group_keys(item, result)
    return result


def _collect_project_keys(value: Any, found: Optional[list[str]] = None) -> list[str]:
    result = found if found is not None else []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "project_key":
                clean = _clean_text(item, 180)
                if clean and clean not in result:
                    result.append(clean)
            elif isinstance(item, (dict, list)):
                _collect_project_keys(item, result)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                _collect_project_keys(item, result)
    return result


def _read_archive(path_text: str) -> tuple[Optional[Path], dict[str, Any]]:
    try:
        path = Path(path_text).expanduser().resolve()
        allowed = (_output_root() / "mobile_one_shot").resolve()
        if path.name != "result.json" or allowed not in path.parents or not path.is_file():
            return None, {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return path, data if isinstance(data, dict) else {}
    except Exception:
        return None, {}


def _recent_archives(user_id: int, limit: int = 50) -> list[tuple[Path, dict[str, Any]]]:
    items: list[tuple[Path, dict[str, Any]]] = []
    for path_text in list_mobile_one_shot_result_paths(user_id, limit):
        path, data = _read_archive(path_text)
        if path is not None and data:
            items.append((path, data))
    return items


def _source_seen(data: dict[str, Any], source: str, source_job_id: str) -> bool:
    if str(data.get("source") or "") == source and str(data.get("source_job_id") or "") == source_job_id:
        return True
    pipeline = data.get("pipeline") or {}
    for item in pipeline.get("sources") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("source") or "") == source and str(item.get("external_job_id") or "") == source_job_id:
            return True
    return False


def _archive_datetime(data: dict[str, Any]) -> Optional[datetime]:
    return _parse_datetime(data.get("created_at"))


def _find_existing_archive(
    *,
    user_id: int,
    source: str,
    source_job_id: str,
    group_keys: list[str],
    archive_job_id: Optional[str],
    now: datetime,
) -> tuple[Optional[Path], dict[str, Any]]:
    recent = _recent_archives(user_id)

    # 1. 명시적 ID와 동일 작업 재조회는 항상 같은 레코드를 사용합니다.
    for path, data in recent:
        if archive_job_id and str(data.get("job_id") or "") == archive_job_id:
            return path, data
        if _source_seen(data, source, source_job_id):
            return path, data

    # 2. 공통 제작 식별자 또는 pipeline/project key가 같으면 병합합니다.
    key_set = {key for key in group_keys if key}
    if key_set:
        for path, data in recent:
            existing_keys = set(_collect_group_keys(data))
            existing_group = _clean_text(data.get("archive_group_key"), 180)
            if existing_group:
                existing_keys.add(existing_group)
            if key_set.intersection(existing_keys):
                return path, data

    # 3. 딸깍 제작 직후 자동 팟캐스트/숏폼은 루트 글 레코드에 합칩니다.
    #    수동 팟캐스트가 엉뚱한 글에 붙지 않도록, 루트가 미디어 진행 상태이거나
    #    최근 30분 안의 storymaker-main 레코드인 경우만 후보로 사용합니다.
    if source in {"podcast", "shortform", "thumbnail"}:
        candidates: list[tuple[datetime, Path, dict[str, Any]]] = []
        for path, data in recent:
            root_source = str(data.get("source") or "")
            created = _archive_datetime(data)
            if root_source != "storymaker-main" or created is None:
                continue
            if created > now + timedelta(minutes=3) or now - created > timedelta(minutes=30):
                continue
            media = data.get("media") or {}
            pipeline = data.get("pipeline") or {}
            media_status = str(media.get("status") or media.get("podcast_status") or "").lower()
            has_handoff = bool(
                media_status in {"podcast_running", "running", "queued", "waiting", "script_missing"}
                or pipeline.get("timing")
                or media.get("podcast_job_id")
                or media.get("project_key")
            )
            if has_handoff:
                candidates.append((created, path, data))
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            return candidates[0][1], candidates[0][2]

    return None, {}


def _choose_title(old_title: str, new_title: str, outputs: dict[str, Any], raw_result: str, source_job_id: str) -> str:
    old_clean = _clean_text(old_title, 120)
    new_clean = _clean_text(new_title, 120)
    if old_clean and not old_clean.lower().startswith(GENERIC_TITLE_PREFIXES):
        return old_clean
    if new_clean and not new_clean.lower().startswith(GENERIC_TITLE_PREFIXES):
        return new_clean
    return (
        old_clean
        or _first_title(str(outputs.get("blog_titles") or ""))
        or _first_title(raw_result)
        or new_clean
        or source_job_id
    )[:120]


def _image_count_from_payload(value: Any) -> int:
    best = 0
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"image_count", "source_image_count", "success"}:
                try:
                    best = max(best, int(item or 0))
                except Exception:
                    pass
            elif key in {"images", "image_urls", "assets", "project_assets"} and isinstance(item, list):
                best = max(best, len(item))
            if isinstance(item, (dict, list)):
                best = max(best, _image_count_from_payload(item))
    elif isinstance(value, list):
        # log, sources 같은 일반 배열 길이를 이미지 개수로 오인하지 않습니다.
        # 이미지 관련 키의 배열 길이는 위 dict 분기에서만 계산합니다.
        for item in value:
            if isinstance(item, (dict, list)):
                best = max(best, _image_count_from_payload(item))
    return best


def register_common_archive(
    *,
    user_id: Optional[int],
    source: str,
    source_job_id: str,
    title: Optional[str] = None,
    status: str = "completed",
    raw_result: str = "",
    outputs: Optional[dict[str, Any]] = None,
    media: Optional[dict[str, Any]] = None,
    extra: Optional[dict[str, Any]] = None,
    image_count: int = 0,
    archive_job_id: Optional[str] = None,
    archive_group_key: Optional[str] = None,
) -> dict[str, Any]:
    """외부 작업 결과를 공통 제작 식별자 기준으로 한 게시물에 병합합니다."""
    if not user_id:
        return {"ok": False, "reason": "missing_user"}

    source = _clean_text(source, 80) or "unknown"
    source_job_id = _clean_text(source_job_id, 160) or source
    incoming_media = dict(media or {})
    incoming_extra = dict(extra or {})
    now = _now()

    group_keys: list[str] = []
    explicit_group = _clean_text(archive_group_key, 180)
    if explicit_group:
        group_keys.append(explicit_group)
    for key in _collect_group_keys({"media": incoming_media, "extra": incoming_extra}):
        if key not in group_keys:
            group_keys.append(key)
    if source == "storymaker-main" and source_job_id not in group_keys:
        group_keys.insert(0, source_job_id)

    existing_path, existing = _find_existing_archive(
        user_id=int(user_id),
        source=source,
        source_job_id=source_job_id,
        group_keys=group_keys,
        archive_job_id=archive_job_id,
        now=now,
    )

    root_source = str(existing.get("source") or "") or source
    root_source_job_id = str(existing.get("source_job_id") or "") or source_job_id
    if root_source == "storymaker-main" and root_source_job_id.startswith("storymaker_main_") and source in {"podcast", "shortform"}:
        incoming_project_keys = _collect_project_keys({"media": incoming_media, "extra": incoming_extra})
        if incoming_project_keys and root_source_job_id not in incoming_project_keys:
            return {
                "ok": False,
                "reason": "pc_project_key_mismatch",
                "expected_project_key": root_source_job_id,
                "received_project_keys": incoming_project_keys,
                "archive_job_id": existing.get("job_id"),
                "result_path": str(existing_path) if existing_path else "",
            }

    created_dt = _archive_datetime(existing) if existing else None
    if created_dt is None:
        created_dt = _created_datetime(source_job_id, incoming_media, incoming_extra, now)

    existing_group = _clean_text(existing.get("archive_group_key"), 180) if existing else ""
    group_key = existing_group or explicit_group or (group_keys[0] if group_keys else source_job_id)
    archive_id = (
        _clean_text(existing.get("job_id"), 80)
        if existing
        else _clean_text(archive_job_id, 80) or _archive_job_id(group_key, created_dt, int(user_id))
    )

    if existing_path is not None:
        result_file = existing_path
        job_dir = existing_path.parent
        date_key = str(existing.get("created_date") or job_dir.parent.name or created_dt.strftime(KST_DATE_FORMAT))
    else:
        date_key = created_dt.strftime(KST_DATE_FORMAT)
        job_dir = _output_root() / "mobile_one_shot" / date_key / archive_id
        job_dir.mkdir(parents=True, exist_ok=True)
        result_file = job_dir / "result.json"

    old_outputs = dict(existing.get("outputs") or {})
    new_outputs = _build_outputs(raw_result, outputs)
    merged_outputs = _merge_nonempty(old_outputs, new_outputs)
    merged_raw = str(raw_result or "").strip() or str(existing.get("raw_result") or "")
    resolved_title = _choose_title(
        str(existing.get("memo") or ""),
        str(title or ""),
        merged_outputs,
        merged_raw,
        source_job_id,
    )

    merged_media = _merge_nonempty(existing.get("media") or {}, incoming_media)
    merged_extra = dict(existing.get("extra") or {})
    stages = dict(merged_extra.get("stages") or {})
    if incoming_extra:
        stages[source] = _merge_nonempty(stages.get(source) or {}, incoming_extra)
    merged_extra = _merge_nonempty(merged_extra, incoming_extra)
    if stages:
        merged_extra["stages"] = stages

    pipeline = dict(existing.get("pipeline") or {})
    sources = [item for item in pipeline.get("sources") or [] if isinstance(item, dict)]
    source_entry = {
        "source": source,
        "external_job_id": source_job_id,
        "registered_at": now.isoformat(timespec="seconds"),
    }
    if not any(
        str(item.get("source") or "") == source
        and str(item.get("external_job_id") or "") == source_job_id
        for item in sources
    ):
        sources.append(source_entry)
    pipeline["sources"] = sources
    pipeline["group_keys"] = list(dict.fromkeys([group_key, *group_keys]))
    pipeline["latest_source"] = source
    pipeline["latest_external_job_id"] = source_job_id
    pipeline["registered_at"] = pipeline.get("registered_at") or now.isoformat(timespec="seconds")

    merged_image_count = max(
        int(existing.get("image_count") or 0),
        int(image_count or 0),
        _image_count_from_payload(incoming_extra),
        _image_count_from_payload(incoming_media),
        _image_count_from_payload(existing.get("images") or []),
    )

    created_at = created_dt.strftime("%Y-%m-%d %H:%M:%S")
    current_status = _clean_text(status, 80) or str(existing.get("status") or "completed")
    resolved_persona = existing.get("persona")
    if not isinstance(resolved_persona, dict) or not str(resolved_persona.get("company_name") or "").strip():
        try:
            resolved_persona = _default_persona_payload(int(user_id))
        except Exception:
            resolved_persona = existing.get("persona")
    has_text = bool(merged_raw.strip() or any(str(value or "").strip() for value in merged_outputs.values()))
    has_mp3 = bool(merged_media.get("mp3_url") or merged_media.get("mp3_path"))
    has_mp4 = bool(merged_media.get("mp4_url") or merged_media.get("mp4_path") or merged_media.get("preview_mp4_url"))
    has_thumbnail = bool(merged_media.get("thumbnail_url") or merged_media.get("thumbnail_path"))
    completed_at = now.isoformat(timespec="seconds") if (
        current_status.lower() in TERMINAL_STATUSES or has_text or has_mp3 or has_mp4 or has_thumbnail
    ) else None

    data: dict[str, Any] = {
        **existing,
        "job_id": archive_id,
        "archive_group_key": group_key,
        "created_date": date_key,
        "source_job_id": root_source_job_id,
        "source": root_source,
        "latest_source": source,
        "latest_source_job_id": source_job_id,
        "status": current_status,
        "created_at": created_at,
        "updated_at": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Seoul",
        "user_bucket": str(user_id),
        "memo": resolved_title,
        "memo_length": len(resolved_title),
        "image_count": merged_image_count,
        "keywords": list(existing.get("keywords") or []),
        "persona": resolved_persona,
        "outputs": merged_outputs,
        "raw_result": merged_raw,
        "media": merged_media,
        "pipeline": pipeline,
        "extra": merged_extra,
    }

    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "images").mkdir(parents=True, exist_ok=True)
    (job_dir / "media").mkdir(parents=True, exist_ok=True)
    temp_file = result_file.with_suffix(".json.tmp")
    temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(result_file)

    # V1 PC 브라우저 팟캐스트가 먼저 browser_running 소유권을 잡도록 합니다.
    # 서버 팟캐스트는 명시적으로 폴백을 켠 경우에만 예약합니다.
    if os.getenv("V1_PC_PODCAST_BACKEND_FALLBACK_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}:
        _schedule_pc_podcast_once(
            data=data,
            result_file=result_file,
            user_id=int(user_id),
        )

    # PC V2 StoryMaker jobs do not call the mobile /podcast-started route.
    # Reuse the proven mobile thumbnail starter whenever the shared archive is updated.
    pc_source_job_id = str(data.get("source_job_id") or data.get("archive_group_key") or "").strip()
    if pc_source_job_id.startswith("storymaker_main_") and str(data.get("latest_source") or "").strip() == "shortform":
        try:
            from app.api.mobile_one_shot import _start_thumbnail_job, _sync_storymaker_main_images

            data = _sync_storymaker_main_images(data, result_file)
            data = _start_thumbnail_job(data, result_file)
            merged_image_count = _image_count_from_payload(data)
        except Exception as exc:
            data.setdefault("extra", {})["pc_thumbnail_start_error"] = str(exc)[:300]
            temp_file = result_file.with_suffix(".json.tmp")
            temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_file.replace(result_file)

    upsert_mobile_one_shot_job(
        job_id=archive_id,
        user_id=int(user_id),
        persona_id=None,
        status=current_status,
        memo=resolved_title[:2000],
        created_date=date_key,
        result_path=str(result_file),
        image_count=merged_image_count,
        has_text=has_text,
        has_mp3=has_mp3,
        has_mp4=has_mp4,
        has_thumbnail=has_thumbnail,
        error_message="",
        created_at=created_at,
        updated_at=now.isoformat(timespec="seconds"),
        completed_at=completed_at,
    )

    try:
        sync_content_archive_assets(
            user_id=int(user_id),
            archive_job_id=archive_id,
            archive_group_key=group_key,
            source_menu=source,
            source_job_id=source_job_id,
            payload={"media": incoming_media, "extra": incoming_extra},
            metadata=data,
            result_dir=job_dir,
        )
    except Exception:
        # 미디어 DB 등록 실패가 원본 제작 완료를 되돌리지는 않도록 분리합니다.
        pass

    return {
        "ok": True,
        "archive_job_id": archive_id,
        "archive_group_key": group_key,
        "archive_result_path": str(result_file),
        "title": resolved_title,
        "merged": bool(existing),
    }
