# -*- coding: utf-8 -*-
"""StoryMaker 프로젝트 산출물 공통 저장 유틸.

Mission 7 기준:
- 프로젝트 산출물을 users/{user_id}/projects/{project_key}/... 구조에 저장
- project_assets DB에 버전, 상태, source, tags, 활성 여부를 기록
- 같은 asset_group_key로 새 버전을 저장하면 기존 버전을 비활성화
- 에디터가 즉시 사용할 anchor_tag / preview_url 응답 생성
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import random
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

STANDARD_ROLE_SETS = {
    "interior": ["COVER", "BEFORE", "AFTER", "DETAIL", "MAP"],
    "home_repair": ["COVER", "BEFORE", "AFTER", "DETAIL", "MAP"],
    "optical": ["COVER", "INTERIOR", "EXAM", "PRODUCT", "OWNER"],
    "store": ["COVER", "INTERIOR", "PRODUCT", "OWNER", "MAP"],
    "restaurant": ["COVER", "INTERIOR", "MENU", "FOOD", "MAP"],
    "default": ["COVER", "INTERIOR", "PRODUCT", "OWNER", "MAP", "DETAIL", "GENERAL"],
}

ROLE_KO = {
    "COVER": "대표 이미지",
    "INTERIOR": "매장 실내",
    "EXAM": "정밀 시력 검사",
    "PRODUCT": "제품",
    "OWNER": "원장님",
    "BEFORE": "시공 전",
    "AFTER": "시공 후",
    "DETAIL": "상세 작업",
    "MAP": "찾아오는 길",
    "MENU": "메뉴",
    "FOOD": "음식",
    "SHORTFORM": "숏폼 영상",
    "THUMBNAIL": "대표 썸네일",
    "GENERAL": "현장 이미지",
    "PENDING": "미지정 이미지",
}

VALID_STATUSES = {"READY", "PROCESSING", "FAILED", "DELETED"}
VALID_SOURCES = {"UPLOAD", "AI", "SLIDESHOW", "THUMBNAIL", "VIDEO", "IMPORT"}

SOURCE_ALIASES = {
    "upload": "UPLOAD",
    "uploaded": "UPLOAD",
    "user_upload": "UPLOAD",
    "slideshow": "SLIDESHOW",
    "slideshow_upload": "SLIDESHOW",
    "slide": "SLIDESHOW",
    "thumbnail": "THUMBNAIL",
    "thumbnail_input_upload": "THUMBNAIL",
    "thumb": "THUMBNAIL",
    "video": "VIDEO",
    "movie": "VIDEO",
    "ai": "AI",
    "gemini": "AI",
    "chatgpt": "AI",
    "import": "IMPORT",
    "legacy": "IMPORT",
}

ALT_TEMPLATES = [
    "{company}에서 촬영한 {role_ko} 사진입니다.",
    "{company} {keyword} 안내에 활용하기 좋은 {role_ko} 이미지입니다.",
    "{company}의 실제 분위기를 보여주는 {role_ko} 사진입니다.",
    "{keyword} 콘텐츠에 어울리는 {company} {role_ko} 모습입니다.",
    "{company}에서 확인할 수 있는 {role_ko} 전경입니다.",
    "{company} 방문 전 참고하기 좋은 {role_ko} 사진입니다.",
    "{keyword} 관련 정보를 설명하기 위한 {company} {role_ko} 이미지입니다.",
    "{company}의 전문성을 보여주는 {role_ko} 장면입니다.",
    "{company} 현장감을 담은 {keyword} 관련 {role_ko} 사진입니다.",
    "{company} 서비스를 이해하기 쉽게 보여주는 {role_ko} 이미지입니다.",
    "{keyword} 상담에 참고하기 좋은 {company} {role_ko} 장면입니다.",
    "{company}의 신뢰감을 전달하는 {role_ko} 사진입니다.",
    "{company}에서 제공하는 {keyword} 관련 {role_ko} 모습입니다.",
    "{company} 블로그 원고에 사용할 {role_ko} 이미지입니다.",
    "{keyword} 정보를 자연스럽게 설명하는 {company} {role_ko} 사진입니다.",
    "{company}의 고객 안내에 활용할 수 있는 {role_ko} 장면입니다.",
    "{company} 콘텐츠 패키지용 {role_ko} 이미지입니다.",
    "{keyword} 검색 이용자를 위한 {company} {role_ko} 사진입니다.",
    "{company}의 현장과 분위기를 함께 보여주는 {role_ko} 이미지입니다.",
    "{company} 소개 글에 적합한 {keyword} 관련 {role_ko} 사진입니다.",
]

FOLDER_MAP = {
    "image": "images",
    "video": "videos",
    "thumbnail": "thumbnails",
}


def safe_token(value: Any, fallback: str = "asset", max_len: int = 80) -> str:
    text_value = str(value or "").strip()
    text_value = re.sub(r"\s+", "_", text_value)
    text_value = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", text_value)
    text_value = re.sub(r"_+", "_", text_value).strip("_")
    return (text_value or fallback)[:max_len]


def normalize_asset_type(asset_type: str) -> str:
    kind = str(asset_type or "image").lower().strip()
    if kind in {"thumb", "thumbnail", "thumbnails"}:
        return "thumbnail"
    if kind in {"mp4", "movie", "video", "videos"}:
        return "video"
    return "image"


def normalize_role(role: str, asset_type: str = "image") -> str:
    value = safe_token(role or "", fallback="")
    if value:
        return value.upper()
    return {"image": "GENERAL", "video": "SHORTFORM", "thumbnail": "THUMBNAIL"}.get(asset_type, "GENERAL")


def normalize_status(status: str) -> str:
    value = str(status or "READY").strip().upper()
    return value if value in VALID_STATUSES else "READY"


def normalize_source(source: str, asset_type: str = "image") -> str:
    raw = str(source or "").strip()
    if not raw:
        if normalize_asset_type(asset_type) == "video":
            return "VIDEO"
        if normalize_asset_type(asset_type) == "thumbnail":
            return "THUMBNAIL"
        return "UPLOAD"
    upper = raw.upper()
    if upper in VALID_SOURCES:
        return upper
    lowered = raw.lower()
    if lowered in SOURCE_ALIASES:
        return SOURCE_ALIASES[lowered]
    if "slide" in lowered:
        return "SLIDESHOW"
    if "thumb" in lowered:
        return "THUMBNAIL"
    if "video" in lowered or "mp4" in lowered:
        return "VIDEO"
    if "ai" in lowered or "gemini" in lowered:
        return "AI"
    if "import" in lowered or "legacy" in lowered:
        return "IMPORT"
    return "UPLOAD"


def normalize_tags(tags: str | Iterable[Any] | None) -> str:
    if tags is None:
        return ""
    if isinstance(tags, str):
        raw_items = re.split(r"[,#\n]+", tags)
    else:
        raw_items = [str(item) for item in tags]
    cleaned: list[str] = []
    for item in raw_items:
        token = str(item or "").strip().strip("#")
        token = re.sub(r"\s+", " ", token)
        if token and token not in cleaned:
            cleaned.append(token[:40])
    return ", ".join(cleaned[:20])


def split_keyword_candidates(value: Any, limit: int = 20) -> list[str]:
    raw = str(value or "")
    if not raw:
        return []
    chunks = re.split(r"[,#\n\r\t|/]+", raw)
    result: list[str] = []
    for chunk in chunks:
        cleaned = re.sub(r"\s+", " ", str(chunk or "").strip())
        cleaned = re.sub(r"^[\-:;·•]+|[\-:;·•]+$", "", cleaned).strip()
        if not cleaned or cleaned.isdigit() or len(cleaned) < 2:
            continue
        token = safe_token(cleaned, "", 24)
        if token and token not in result:
            result.append(token)
        if len(result) >= limit:
            break
    return result


def choose_asset_keyword(
    *,
    prompt_keywords: Any = "",
    project_keywords: Any = "",
    user_keywords: Any = "",
    industry_keywords: Any = "",
    fallback: Any = "",
) -> str:
    """저장 파일명에 들어갈 SEO 키워드를 빠르게 확정합니다.

    파일명 생성 때문에 업로드/렌더링이 느려지지 않도록 외부 호출 없이
    이미 전달된 문자열 후보만 정리합니다. 최후에는 fallback 자체를 safe_token으로
    강제 변환해 파일명에 빈 키워드가 들어가지 않게 막습니다.
    """
    for source in (prompt_keywords, project_keywords, user_keywords, industry_keywords, fallback):
        candidates = [item for item in split_keyword_candidates(source) if item and item != "키워드"]
        if candidates:
            return random.choice(candidates)
    forced = safe_token(fallback, "", 24)
    return forced or "SEO키워드"


def get_standard_roles(industry_key: str = "default") -> list[str]:
    key = str(industry_key or "default").strip().lower()
    return STANDARD_ROLE_SETS.get(key) or STANDARD_ROLE_SETS["default"]


def get_role_ko(role: str) -> str:
    normalized = normalize_role(role)
    return ROLE_KO.get(normalized, normalized)


def make_alt_text(company_name: str, keyword: str, role: str) -> str:
    company = str(company_name or "업체").strip()
    key = str(keyword or "서비스").strip()
    role_value = normalize_role(role)
    role_ko = get_role_ko(role_value)
    return random.choice(ALT_TEMPLATES).format(company=company, keyword=key, role=role_value, role_ko=role_ko)


def make_asset_caption(company_name: str, keyword: str, role: str) -> str:
    company = str(company_name or "업체").strip()
    key = str(keyword or "서비스").strip()
    role_ko = get_role_ko(role)
    return f"{company} {key} 콘텐츠용 {role_ko}"


def merge_asset_tags(tags: str | Iterable[Any] | None, company_name: str, keyword: str, role: str) -> str:
    base = normalize_tags(tags)
    extra = normalize_tags([keyword, company_name, get_role_ko(role)])
    return normalize_tags([base, extra])


def make_project_asset_filename(
    original_filename: str,
    company_name: str,
    keyword: str,
    role: str,
    asset_type: str,
    sequence: int | None = None,
    version: int | None = None,
) -> str:
    ext = Path(original_filename or "").suffix.lower()
    kind = normalize_asset_type(asset_type)
    if not ext:
        ext = ".mp4" if kind == "video" else ".png" if kind == "thumbnail" else ".jpg"
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    seq = f"_{int(sequence):03d}" if sequence is not None else ""
    ver = f"_v{int(version):02d}" if version and int(version) > 1 else ""
    return f"{safe_token(company_name, '업체')}_{safe_token(keyword, '키워드')}_{safe_token(role, kind).upper()}{seq}{ver}_{date_str}{ext}"


def make_asset_group_key(file_bytes: bytes | None = None, original_filename: str = "", provided_key: str | None = None) -> str:
    if provided_key:
        return safe_token(provided_key, "asset_group", 100)
    if file_bytes:
        digest = hashlib.sha256(file_bytes).hexdigest()[:24]
        return f"asset_{digest}"
    base = safe_token(original_filename or uuid.uuid4().hex, "asset_group", 70)
    return f"asset_{base}_{uuid.uuid4().hex[:8]}"[:100]


def get_asset_dir(output_root: Path, user_id: Any, project_key: str, asset_type: str) -> Path:
    safe_user = safe_token(user_id or "default_user", "default_user")
    legacy_key = f"legacy_{datetime.now().strftime('%Y%m%d')}"
    safe_project = safe_token(project_key or legacy_key, "project")
    sub_folder = FOLDER_MAP.get(asset_type, "images")
    return output_root / "users" / safe_user / "projects" / safe_project / sub_folder


def build_public_url(output_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(output_root).as_posix()
    return f"/data/output_results/{rel}"


def make_anchor_tag(role: str, asset_type: str = "image") -> str:
    kind = normalize_asset_type(asset_type)
    role_value = normalize_role(role, kind)
    if kind == "video":
        return f"[VIDEO_{role_value}]"
    if kind == "thumbnail":
        return f"[THUMBNAIL_{role_value}]"
    return f"[IMAGE_{role_value}]"


def to_editor_asset_response(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": asset.get("id"),
        "user_id": asset.get("user_id"),
        "project_id": asset.get("project_id"),
        "project_key": asset.get("project_key"),
        "asset_group_key": asset.get("asset_group_key", ""),
        "version": asset.get("version", 1),
        "is_active": bool(asset.get("is_active", True)),
        "status": asset.get("status", "READY"),
        "source": asset.get("source", "UPLOAD"),
        "tags": asset.get("tags", ""),
        "role": asset.get("role"),
        "asset_type": asset.get("asset_type"),
        "anchor_tag": make_anchor_tag(asset.get("role", ""), asset.get("asset_type", "image")),
        "alt_text": asset.get("alt_text", ""),
        "caption": asset.get("caption", ""),
        "company_name": asset.get("company_name", ""),
        "keyword": asset.get("keyword", ""),
        "original_filename": asset.get("original_filename", ""),
        "file_size": asset.get("file_size", 0),
        "mime_type": asset.get("mime_type", ""),
        "created_at": asset.get("created_at", ""),
        "updated_at": asset.get("updated_at", ""),
        "preview_url": asset.get("public_url", ""),
        "public_url": asset.get("public_url", ""),
        "relative_path": asset.get("relative_path", ""),
        "stored_filename": asset.get("stored_filename", ""),
        "display_order": asset.get("display_order", 0),
    }


def _next_asset_version(db: Session, *, user_id: Any, project_key: str, asset_group_key: str) -> int:
    row = db.execute(text("""
        SELECT MAX(version) AS max_version
        FROM project_assets
        WHERE user_id = :user_id
          AND project_key = :project_key
          AND asset_group_key = :asset_group_key
    """), {
        "user_id": user_id,
        "project_key": safe_token(project_key, "project"),
        "asset_group_key": asset_group_key,
    }).mappings().first()
    current = int((row or {}).get("max_version") or 0)
    return current + 1


def _deactivate_previous_versions(db: Session, *, user_id: Any, project_key: str, asset_group_key: str, now_text: str) -> None:
    db.execute(text("""
        UPDATE project_assets
        SET is_active = 0,
            updated_at = :updated_at
        WHERE user_id = :user_id
          AND project_key = :project_key
          AND asset_group_key = :asset_group_key
          AND is_active = 1
    """), {
        "updated_at": now_text,
        "user_id": user_id,
        "project_key": safe_token(project_key, "project"),
        "asset_group_key": asset_group_key,
    })


def save_project_asset(
    *,
    db: Session | None = None,
    output_root: str | Path | None = None,
    user_id: Any = "default_user",
    username: str = "",
    project_id: int | None = None,
    project_key: str = "",
    file_bytes: bytes,
    original_filename: str,
    asset_type: str,
    role: str = "",
    company_name: str = "",
    keyword: str = "",
    prompt_keywords: Any = "",
    project_keywords: Any = "",
    user_keywords: Any = "",
    industry_keywords: Any = "",
    caption: str = "",
    mime_type: str = "",
    source: str = "UPLOAD",
    status: str = "READY",
    tags: str | Iterable[Any] | None = None,
    asset_group_key: str | None = None,
    version: int | None = None,
    is_active: bool = True,
    sequence: int | None = None,
    display_order: int = 0,
    deactivate_previous: bool = True,
) -> dict[str, Any]:
    kind = normalize_asset_type(asset_type)
    role_value = normalize_role(role, kind)
    source_value = normalize_source(source, kind)
    status_value = normalize_status(status)
    root = Path(output_root or os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    user_id = user_id or "default_user"
    project_key = safe_token(project_key or f"legacy_{datetime.now().strftime('%Y%m%d')}", "project")
    group_key = make_asset_group_key(file_bytes, original_filename, asset_group_key)
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chosen_keyword = choose_asset_keyword(
        prompt_keywords=prompt_keywords,
        project_keywords=project_keywords or keyword,
        user_keywords=user_keywords,
        industry_keywords=industry_keywords,
        fallback=keyword or project_key or company_name or kind,
    )

    if db is not None and version is None:
        version_value = _next_asset_version(db, user_id=user_id, project_key=project_key, asset_group_key=group_key)
    else:
        version_value = int(version or 1)

    if db is not None and deactivate_previous and is_active and version_value > 1:
        _deactivate_previous_versions(db, user_id=user_id, project_key=project_key, asset_group_key=group_key, now_text=now_text)

    target_dir = get_asset_dir(root, user_id, project_key, kind)
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = make_project_asset_filename(original_filename, company_name, chosen_keyword, role_value, kind, sequence, version_value)
    target_path = target_dir / stored_filename
    if target_path.exists():
        stamp = datetime.now().strftime("%H%M%S")
        target_path = target_dir / f"{target_path.stem}_{stamp}{target_path.suffix}"
        stored_filename = target_path.name

    target_path.write_bytes(file_bytes)
    guessed_mime = mime_type or mimetypes.guess_type(stored_filename)[0] or ("video/mp4" if kind == "video" else "image/jpeg")
    payload = {
        "user_id": user_id,
        "username": username or "",
        "project_id": project_id,
        "project_key": project_key,
        "asset_group_key": group_key,
        "version": version_value,
        "is_active": 1 if is_active else 0,
        "asset_type": kind,
        "role": role_value,
        "original_filename": original_filename or stored_filename,
        "stored_filename": stored_filename,
        "relative_path": target_path.relative_to(root).as_posix(),
        "public_url": build_public_url(root, target_path),
        "company_name": company_name or "",
        "keyword": chosen_keyword or "",
        "alt_text": make_alt_text(company_name, chosen_keyword, role_value),
        "caption": caption or make_asset_caption(company_name, chosen_keyword, role_value),
        "mime_type": guessed_mime,
        "file_size": len(file_bytes),
        "display_order": int(display_order or 0),
        "status": status_value,
        "source": source_value,
        "tags": merge_asset_tags(tags, company_name, chosen_keyword, role_value),
        "created_at": now_text,
        "updated_at": now_text,
    }

    if db is not None:
        result = db.execute(text("""
            INSERT INTO project_assets
            (user_id, username, project_id, project_key, asset_group_key, version, is_active, asset_type, role, original_filename, stored_filename, relative_path, public_url, company_name, keyword, alt_text, caption, mime_type, file_size, display_order, status, source, tags, created_at, updated_at)
            VALUES
            (:user_id, :username, :project_id, :project_key, :asset_group_key, :version, :is_active, :asset_type, :role, :original_filename, :stored_filename, :relative_path, :public_url, :company_name, :keyword, :alt_text, :caption, :mime_type, :file_size, :display_order, :status, :source, :tags, :created_at, :updated_at)
        """), payload)
        try:
            payload["id"] = result.lastrowid
        except Exception:
            payload["id"] = None
    return payload


def save_new_version_asset(**kwargs: Any) -> dict[str, Any]:
    """동일 asset_group_key의 기존 활성 에셋을 내리고 새 버전을 저장합니다."""
    if not kwargs.get("asset_group_key"):
        raise ValueError("asset_group_key is required for save_new_version_asset")
    kwargs["deactivate_previous"] = True
    kwargs["is_active"] = True
    return save_project_asset(**kwargs)


def backfill_project_output_assets(
    db: Session,
    *,
    output_root: str | Path | None = None,
    user_id: Any = "default_user",
    username: str = "",
    project_id: int | None = None,
    project_key: str = "",
    project_title: str = "",
    legacy_user: str = "default_user",
) -> dict[str, Any]:
    """기존 output_results/users/default_user/projects 산출물을 project_assets에 멱등 등록합니다."""
    root = Path(output_root or os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
    projects_root = root / "users" / safe_token(legacy_user, "default_user") / "projects"
    if not projects_root.exists():
        return {"ok": True, "folder": None, "inserted": 0, "skipped": 0, "files": 0}

    wanted = [project_key, project_title]
    wanted += [safe_token(value, "project") for value in wanted if value]
    folder = None
    for name in dict.fromkeys(value for value in wanted if value):
        candidate = projects_root / name
        if candidate.is_dir():
            folder = candidate
            break
    if folder is None:
        normalized = {safe_token(value, "project") for value in wanted if value}
        folder = next((p for p in projects_root.iterdir() if p.is_dir() and safe_token(p.name, "project") in normalized), None)
    if folder is None:
        return {"ok": True, "folder": None, "inserted": 0, "skipped": 0, "files": 0}

    media_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".webm", ".m4v"}
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in media_exts)
    if not files:
        return {"ok": True, "folder": folder.name, "inserted": 0, "skipped": 0, "files": 0}

    existing_rows = db.execute(text("""
        SELECT relative_path, public_url
        FROM project_assets
    """)).mappings().all()
    existing = {row["relative_path"] for row in existing_rows} | {row["public_url"] for row in existing_rows}

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    key = safe_token(project_key or project_title or folder.name, "project")
    inserted = skipped = image_no = 0
    for idx, path in enumerate(files):
        rel = path.relative_to(root).as_posix()
        url = build_public_url(root, path)
        if rel in existing or url in existing:
            skipped += 1
            continue
        kind = "video" if path.suffix.lower() in {".mp4", ".mov", ".webm", ".m4v"} else ("thumbnail" if "thumb" in path.as_posix().lower() else "image")
        if kind == "image":
            image_no += 1
            role = "COVER" if image_no == 1 else f"IMAGE_{image_no}"
        else:
            role = "SHORTFORM" if kind == "video" else "THUMBNAIL"
        payload = {
            "user_id": user_id or "default_user",
            "username": username or "",
            "project_id": project_id,
            "project_key": key,
            "asset_group_key": f"import_{hashlib.sha1(rel.encode('utf-8')).hexdigest()[:24]}",
            "version": 1,
            "is_active": 1,
            "asset_type": kind,
            "role": role,
            "original_filename": path.name,
            "stored_filename": path.name,
            "relative_path": rel,
            "public_url": url,
            "company_name": "",
            "keyword": "",
            "alt_text": make_alt_text("", "", role),
            "caption": "",
            "mime_type": mimetypes.guess_type(path.name)[0] or ("video/mp4" if kind == "video" else "image/png"),
            "file_size": path.stat().st_size,
            "display_order": idx,
            "status": "READY",
            "source": "IMPORT",
            "tags": "legacy-backfill",
            "created_at": now_text,
            "updated_at": now_text,
        }
        db.execute(text("""
            INSERT INTO project_assets
            (user_id, username, project_id, project_key, asset_group_key, version, is_active, asset_type, role, original_filename, stored_filename, relative_path, public_url, company_name, keyword, alt_text, caption, mime_type, file_size, display_order, status, source, tags, created_at, updated_at)
            VALUES
            (:user_id, :username, :project_id, :project_key, :asset_group_key, :version, :is_active, :asset_type, :role, :original_filename, :stored_filename, :relative_path, :public_url, :company_name, :keyword, :alt_text, :caption, :mime_type, :file_size, :display_order, :status, :source, :tags, :created_at, :updated_at)
        """), payload)
        existing.update({rel, url})
        inserted += 1
    return {"ok": True, "folder": folder.name, "inserted": inserted, "skipped": skipped, "files": len(files)}


def update_project_asset_metadata(
    db: Session,
    *,
    asset_id: int,
    user_id: Any,
    role: str | None = None,
    alt_text: str | None = None,
    caption: str | None = None,
    tags: str | Iterable[Any] | None = None,
    display_order: int | None = None,
    status: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any] | None:
    """Drag & Drop 후 role, 태그, 정렬, 상태를 수정하기 위한 공통 메타데이터 업데이트 헬퍼."""
    updates: list[str] = ["updated_at = :updated_at"]
    params: dict[str, Any] = {
        "asset_id": asset_id,
        "user_id": user_id,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if role is not None:
        updates.append("role = :role")
        params["role"] = normalize_role(role)
        if alt_text is None:
            row = db.execute(text("SELECT company_name, keyword FROM project_assets WHERE id = :asset_id AND user_id = :user_id"), params).mappings().first()
            if row:
                updates.append("alt_text = :alt_text")
                params["alt_text"] = make_alt_text(row.get("company_name", ""), row.get("keyword", ""), params["role"])
    if alt_text is not None:
        updates.append("alt_text = :alt_text")
        params["alt_text"] = alt_text
    if caption is not None:
        updates.append("caption = :caption")
        params["caption"] = caption
    if tags is not None:
        updates.append("tags = :tags")
        params["tags"] = normalize_tags(tags)
    if display_order is not None:
        updates.append("display_order = :display_order")
        params["display_order"] = int(display_order)
    if status is not None:
        updates.append("status = :status")
        params["status"] = normalize_status(status)
    if is_active is not None:
        updates.append("is_active = :is_active")
        params["is_active"] = 1 if is_active else 0

    db.execute(text(f"""
        UPDATE project_assets
        SET {', '.join(updates)}
        WHERE id = :asset_id
          AND user_id = :user_id
    """), params)
    row = db.execute(text("SELECT * FROM project_assets WHERE id = :asset_id AND user_id = :user_id"), params).mappings().first()
    return dict(row) if row else None


def soft_delete_project_asset(
    db: Session,
    *,
    asset_id: int,
    user_id: Any,
) -> dict[str, Any] | None:
    """실제 파일은 지우지 않고 DB에서 휴지통 상태로 전환합니다."""
    params = {
        "asset_id": asset_id,
        "user_id": user_id,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    db.execute(text("""
        UPDATE project_assets
        SET status = 'DELETED',
            is_active = 0,
            updated_at = :updated_at
        WHERE id = :asset_id
          AND user_id = :user_id
          AND status != 'DELETED'
    """), params)
    row = db.execute(text("SELECT * FROM project_assets WHERE id = :asset_id AND user_id = :user_id"), params).mappings().first()
    return dict(row) if row else None


def restore_project_asset(
    db: Session,
    *,
    asset_id: int,
    user_id: Any,
) -> dict[str, Any] | None:
    """삭제된 자산을 복구하되, 같은 프로젝트/role의 기존 활성 자산은 먼저 비활성화합니다."""
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base_params = {
        "asset_id": asset_id,
        "user_id": user_id,
        "updated_at": now_text,
    }
    row = db.execute(text("""
        SELECT *
        FROM project_assets
        WHERE id = :asset_id
          AND user_id = :user_id
    """), base_params).mappings().first()
    if not row:
        return None

    role_value = normalize_role(row.get("role", ""), row.get("asset_type", "image"))
    conflict_params: dict[str, Any] = {
        "asset_id": asset_id,
        "user_id": user_id,
        "role": role_value,
        "updated_at": now_text,
    }
    scope_conditions = [
        "user_id = :user_id",
        "id != :asset_id",
        "role = :role",
        "is_active = 1",
    ]
    if row.get("project_id") is not None:
        scope_conditions.append("project_id = :project_id")
        conflict_params["project_id"] = row.get("project_id")
    elif row.get("project_key"):
        scope_conditions.append("project_key = :project_key")
        conflict_params["project_key"] = row.get("project_key")
    else:
        scope_conditions.append("project_id IS NULL")
        scope_conditions.append("(project_key IS NULL OR project_key = '')")

    db.execute(text(f"""
        UPDATE project_assets
        SET is_active = 0,
            updated_at = :updated_at
        WHERE {' AND '.join(scope_conditions)}
    """), conflict_params)

    restore_params = {
        "asset_id": asset_id,
        "user_id": user_id,
        "role": role_value,
        "updated_at": now_text,
    }
    db.execute(text("""
        UPDATE project_assets
        SET status = 'READY',
            is_active = 1,
            role = :role,
            updated_at = :updated_at
        WHERE id = :asset_id
          AND user_id = :user_id
    """), restore_params)
    restored = db.execute(text("SELECT * FROM project_assets WHERE id = :asset_id AND user_id = :user_id"), restore_params).mappings().first()
    return dict(restored) if restored else None


def read_project_assets(
    db: Session,
    user_id: Any,
    project_id: int | None = None,
    project_key: str | None = None,
    active_only: bool = True,
    status: str | None = "READY",
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"user_id": user_id}
    where = ["user_id = :user_id"]
    if project_id is not None:
        where.append("project_id = :project_id")
        params["project_id"] = project_id
    if project_key:
        where.append("project_key = :project_key")
        params["project_key"] = safe_token(project_key, "project")
    if active_only:
        where.append("is_active = 1")
    if status:
        where.append("status = :status")
        params["status"] = normalize_status(status)
    rows = db.execute(text(f"""
        SELECT *
        FROM project_assets
        WHERE {' AND '.join(where)}
        ORDER BY display_order ASC, created_at DESC, id DESC
    """), params).mappings().all()
    return [dict(row) for row in rows]
