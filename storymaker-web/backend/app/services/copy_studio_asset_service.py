# -*- coding: utf-8 -*-
"""Naver Blog Copy Studio asset resolver.

project_assets DB를 Copy Studio 미리보기와 본문 토큰 치환에 맞게 변환한다.
"""
from __future__ import annotations

import html
import re
from typing import Any

from app.services.project_asset_service import make_anchor_tag, normalize_asset_type, normalize_role, to_editor_asset_response

TOKEN_PATTERN = re.compile(r"\[\[(IMAGE|VIDEO|THUMBNAIL):([A-Za-z0-9_-]+)\]\]|\[(IMAGE|VIDEO|THUMBNAIL)_([A-Za-z0-9_-]+)\]")


def copy_studio_asset_item(row: dict[str, Any]) -> dict[str, Any]:
    """project_assets row를 기존 Copy Studio 프론트 호환 형태로 변환합니다."""
    base = to_editor_asset_response(row)
    public_url = row.get("public_url") or base.get("public_url") or ""
    asset_type = normalize_asset_type(row.get("asset_type", "image"))
    role = normalize_role(row.get("role", ""), asset_type)
    item = {
        **base,
        "kind": asset_type,
        "url": public_url,
        "name": row.get("stored_filename") or row.get("original_filename") or "asset",
        "size": row.get("file_size") or 0,
        "role": role,
        "token": f"[[{_token_kind(asset_type)}:{role}]]",
        "legacy_token": make_anchor_tag(role, asset_type),
        "modified_at": row.get("updated_at") or row.get("created_at") or "",
        "score": 100,
    }
    return item


def _token_kind(asset_type: str) -> str:
    kind = normalize_asset_type(asset_type)
    if kind == "video":
        return "VIDEO"
    if kind == "thumbnail":
        return "THUMBNAIL"
    return "IMAGE"


def group_copy_studio_assets(rows: list[dict[str, Any]]) -> dict[str, Any]:
    items = [copy_studio_asset_item(row) for row in rows]
    images = [item for item in items if item["kind"] == "image"]
    videos = [item for item in items if item["kind"] == "video"]
    thumbnails = [item for item in items if item["kind"] == "thumbnail"]
    token_map = {}
    for item in items:
        for token in (item.get("token"), item.get("legacy_token")):
            if token and token not in token_map:
                token_map[token] = item
    return {
        "images": images,
        "videos": videos,
        "thumbnails": thumbnails,
        "all": items,
        "token_map": token_map,
    }


def build_asset_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        item = copy_studio_asset_item(row)
        kind = _token_kind(item.get("asset_type") or item.get("kind") or "image")
        role = normalize_role(item.get("role", ""), item.get("asset_type") or item.get("kind") or "image")
        lookup.setdefault((kind, role), item)
    return lookup


def make_naver_insert_marker(item: dict[str, Any]) -> str:
    """네이버 블로그 수동 업로드용 복붙 안내 문구를 만듭니다."""
    kind = _token_kind(item.get("asset_type") or item.get("kind") or "image")
    filename = str(item.get("stored_filename") or item.get("name") or item.get("original_filename") or "StoryMaker_asset")
    alt_text = str(item.get("alt_text") or item.get("caption") or filename)
    if kind == "VIDEO":
        label = "영상 삽입"
        desc_label = "영상 설명"
    elif kind == "THUMBNAIL":
        label = "썸네일 삽입"
        desc_label = "이미지 설명(ALT)"
    else:
        label = "이미지 삽입"
        desc_label = "이미지 설명(ALT)"
    return f"\n\n[{label}: {filename}]\n▲ {desc_label}: {alt_text}\n"


def make_missing_marker(token: str) -> str:
    return f"\n\n[이미지 필요: {token}]\n▲ 이미지 설명(ALT): 아직 연결된 project_assets 자산이 없습니다.\n"


def render_asset_html(item: dict[str, Any], token: str) -> str:
    kind = _token_kind(item.get("asset_type") or item.get("kind") or "image")
    url = html.escape(str(item.get("preview_url") or item.get("url") or item.get("public_url") or ""), quote=True)
    alt = html.escape(str(item.get("alt_text") or item.get("name") or "StoryMaker asset"), quote=True)
    caption_raw = item.get("caption") or item.get("alt_text") or ""
    caption = html.escape(str(caption_raw), quote=False)
    token_attr = html.escape(token, quote=True)
    role_attr = html.escape(str(item.get("role") or ""), quote=True)
    if kind == "VIDEO":
        return (
            f'<figure class="sm-copy-asset sm-copy-asset-video" data-token="{token_attr}" data-role="{role_attr}">'
            f'<video src="{url}" controls preload="metadata"></video>'
            f'<figcaption>{caption}</figcaption>'
            f'</figure>'
        )
    asset_class = "sm-copy-asset-thumbnail" if kind == "THUMBNAIL" else "sm-copy-asset-image"
    return (
        f'<figure class="sm-copy-asset {asset_class}" data-token="{token_attr}" data-role="{role_attr}">'
        f'<img src="{url}" alt="{alt}" loading="lazy">'
        f'<figcaption>{caption}</figcaption>'
        f'</figure>'
    )


def resolve_copy_studio_tokens(content: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """본문의 [[IMAGE:ROLE]] / [IMAGE_ROLE] 토큰을 활성 project_assets로 치환합니다."""
    body = str(content or "")
    lookup = build_asset_lookup(rows)
    resolved: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    def replace(match: re.Match[str]) -> str:
        kind = (match.group(1) or match.group(3) or "IMAGE").upper()
        role_asset_type = "video" if kind == "VIDEO" else "thumbnail" if kind == "THUMBNAIL" else "image"
        role = normalize_role(match.group(2) or match.group(4) or "", role_asset_type)
        token = match.group(0)
        item = lookup.get((kind, role))
        if not item:
            missing.append({"token": token, "kind": kind, "role": role})
            return f'<div class="sm-copy-asset-missing" data-token="{html.escape(token, quote=True)}">{html.escape(token)} 에셋 없음</div>'
        resolved.append({
            "token": token,
            "kind": kind,
            "role": role,
            "asset_id": item.get("id"),
            "filename": item.get("stored_filename") or item.get("name") or item.get("original_filename"),
            "preview_url": item.get("preview_url") or item.get("url") or item.get("public_url"),
            "alt_text": item.get("alt_text", ""),
            "insert_marker": make_naver_insert_marker(item),
        })
        return render_asset_html(item, token)

    safe_body = html.escape(body).replace("\n", "<br>")
    rendered_html = TOKEN_PATTERN.sub(replace, safe_body)
    text_with_urls = body
    for item in missing:
        text_with_urls = text_with_urls.replace(item["token"], make_missing_marker(item["token"]))
    for item in resolved:
        text_with_urls = text_with_urls.replace(item["token"], item["insert_marker"])
    return {
        "content": body,
        "rendered_html": rendered_html,
        "text_with_urls": text_with_urls,
        "resolved_tokens": resolved,
        "missing_tokens": missing,
    }


def render_wordpress_asset_html(item: dict[str, Any], token: str) -> str:
    kind = _token_kind(item.get("asset_type") or item.get("kind") or "image")
    url = html.escape(str(item.get("preview_url") or item.get("url") or item.get("public_url") or ""), quote=True)
    alt = html.escape(str(item.get("alt_text") or item.get("name") or "StoryMaker asset"), quote=True)
    if kind == "VIDEO":
        return f'<video src="{url}" controls preload="metadata"></video>'
    return f'<img src="{url}" alt="{alt}" loading="lazy">'


def resolve_wordpress_tokens(content: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """WordPress 본문 HTML을 깨지 않도록 원문 HTML 안의 asset token만 치환합니다."""
    body = str(content or "")
    lookup = build_asset_lookup(rows)
    resolved: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    def replace(match: re.Match[str]) -> str:
        kind = (match.group(1) or match.group(3) or "IMAGE").upper()
        role_asset_type = "video" if kind == "VIDEO" else "thumbnail" if kind == "THUMBNAIL" else "image"
        role = normalize_role(match.group(2) or match.group(4) or "", role_asset_type)
        token = match.group(0)
        item = lookup.get((kind, role))
        if not item:
            missing.append({"token": token, "kind": kind, "role": role})
            return f'<!-- missing asset: {html.escape(token)} -->'
        resolved.append({
            "token": token,
            "kind": kind,
            "role": role,
            "asset_id": item.get("id"),
            "filename": item.get("stored_filename") or item.get("name") or item.get("original_filename"),
            "preview_url": item.get("preview_url") or item.get("url") or item.get("public_url"),
            "alt_text": item.get("alt_text", ""),
        })
        return render_wordpress_asset_html(item, token)

    rendered_html = TOKEN_PATTERN.sub(replace, body)
    return {
        "content": body,
        "rendered_html": rendered_html,
        "text_with_urls": rendered_html,
        "resolved_tokens": resolved,
        "missing_tokens": missing,
    }


def build_instagram_reels_payload(rows: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    items = [copy_studio_asset_item(row) for row in rows]
    videos = [item for item in items if item.get("kind") == "video"]
    thumbnails = [item for item in items if item.get("kind") == "thumbnail" or item.get("role") == "THUMBNAIL"]
    video = next((item for item in videos if item.get("role") == "SHORTFORM"), None) or (videos[0] if videos else {})
    thumbnail = next((item for item in thumbnails if item.get("role") == "THUMBNAIL"), None) or (thumbnails[0] if thumbnails else {})
    meta = meta or {}
    caption = str(meta.get("caption") or "")
    hashtags = str(meta.get("hashtags") or "")
    copy_text = "\n\n".join(part for part in (caption, hashtags) if part)
    return {
        "video_url": video.get("url", ""),
        "video_filename": video.get("name", ""),
        "thumbnail_url": thumbnail.get("url", ""),
        "thumbnail_filename": thumbnail.get("name", ""),
        "caption": caption,
        "hashtags": hashtags,
        "copy_text": copy_text,
    }


def resolve_copy_studio_channel(
    channel: str,
    content: str,
    rows: list[dict[str, Any]],
    title: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    channel_key = str(channel or "naver_blog").strip().lower()
    if channel_key == "wordpress":
        resolved = resolve_wordpress_tokens(content, rows)
    else:
        resolved = resolve_copy_studio_tokens(content, rows)
    resolved["channel_payload"] = build_instagram_reels_payload(rows, meta) if channel_key == "instagram_reels" else {}
    return resolved
