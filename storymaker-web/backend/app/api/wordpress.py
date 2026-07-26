# -*- coding: utf-8 -*-
"""
StoryMaker WordPress 자동 초안 등록 API

환경변수 예:
WORDPRESS_API_URL=http://storymaker_wp/wp-json/wp/v2
WORDPRESS_USERNAME=admin
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
"""
import os
from typing import List, Dict

import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.db.models import User

router = APIRouter()


def check_wordpress_access(user: User):
    if user.role != "admin" and user.tier != "paid":
        raise HTTPException(
            status_code=403,
            detail="워드프레스 연동 기능은 결제 사용자(Premium) 이상만 사용 가능합니다."
        )
    if not user.wp_enabled:
        raise HTTPException(
            status_code=403,
            detail="마이페이지 설정에서 워드프레스 연동 기능이 비활성화되어 있습니다. 설정에서 활성화 후 사용해 주세요."
        )


class WordPressDraftRequest(BaseModel):
    title: str = Field(default="", max_length=300)
    slug: str = Field(default="", max_length=300)
    content: str = Field(default="", min_length=1, max_length=300_000)
    excerpt: str = Field(default="", max_length=500)
    status: str = Field(default="draft", pattern=r"^(draft|pending|private|publish)$")
    tags_text: str = Field(default="", max_length=2000)
    categories_text: str = Field(default="", max_length=1000)
    meta_description: str = Field(default="", max_length=500)
    focus_keyword: str = Field(default="", max_length=200)
    featured_image_alt: str = Field(default="", max_length=300)


class StoryMakerBlocksDraftRequest(BaseModel):
    """StoryMaker 결과 블록을 그대로 받아 WordPress 초안으로 변환합니다."""

    blocks: Dict[str, str] = Field(default_factory=dict)
    status: str = Field(default="draft", pattern=r"^(draft|pending|private|publish)$")
    categories_text: str = Field(default="", max_length=1000)


def wp_config() -> tuple[str, str, str]:
    api_url = os.getenv("WORDPRESS_API_URL", "").rstrip("/")
    username = os.getenv("WORDPRESS_USERNAME", "")
    app_password = os.getenv("WORDPRESS_APP_PASSWORD", "")
    if not api_url or not username or not app_password:
        raise HTTPException(
            status_code=503,
            detail="WordPress API 설정이 없습니다. WORDPRESS_API_URL, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD를 설정하세요.",
        )
    return api_url, username, app_password


def split_terms(text: str) -> List[str]:
    raw = (text or "").replace("#", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def clean_text(text: str) -> str:
    return (text or "").replace("오박사만능인테리어_테스트", "오박사만능인테리어").strip()


def clean_post_content(html: str) -> str:
    content = clean_text(html)
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def first_blog_title(titles_text: str) -> str:
    for line in (titles_text or "").splitlines():
        title = line.strip().lstrip("-• ").strip()
        if len(title) > 2 and title[0].isdigit() and title[1] in [".", ")"]:
            title = title[2:].strip()
        if title:
            return clean_text(title)
    return ""


def simple_excerpt(text: str, limit: int = 160) -> str:
    cleaned = clean_post_content(text)
    for token in ["<br>", "<br/>", "<br />", "</p>", "</h2>", "</h3>"]:
        cleaned = cleaned.replace(token, "\n")
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit].strip()


def storymaker_blocks_to_wp_request(req: StoryMakerBlocksDraftRequest) -> WordPressDraftRequest:
    blocks = req.blocks or {}
    blog_titles = blocks.get("BLOG_TITLES", "")
    blog_post = blocks.get("BLOG_POST", "")
    instagram_post = blocks.get("INSTAGRAM_POST", "")
    carrot_post = blocks.get("CARROT_POST", "")
    tags_text = ", ".join([
        blocks.get("BLOG_HASHTAGS", ""),
        blocks.get("INSTAGRAM_HASHTAGS", ""),
        blocks.get("CARROT_HASHTAGS", ""),
    ]).strip(", ")

    title = first_blog_title(blog_titles) or "StoryMaker 자동 생성 초안"
    content_parts = [clean_post_content(blog_post)]
    if instagram_post.strip():
        content_parts.append("<hr>\n<h2>인스타그램 게시글</h2>\n" + clean_post_content(instagram_post))
    if carrot_post.strip():
        content_parts.append("<hr>\n<h2>당근마켓 게시글</h2>\n" + clean_post_content(carrot_post))
    content = "\n\n".join([part for part in content_parts if part.strip()])
    if not content:
        raise HTTPException(status_code=400, detail="BLOG_POST 블록이 비어 있어 WordPress 초안 등록을 할 수 없습니다.")

    return WordPressDraftRequest(
        title=title,
        content=content,
        excerpt=simple_excerpt(blog_post),
        status=req.status,
        tags_text=tags_text,
        categories_text=req.categories_text,
        meta_description=simple_excerpt(blog_post, 155),
        focus_keyword=title.split(",")[0].strip()[:200],
        featured_image_alt=title,
    )


async def ensure_term(client: httpx.AsyncClient, api_url: str, taxonomy: str, name: str) -> int | None:
    if not name:
        return None
    try:
        search_resp = await client.get(f"{api_url}/{taxonomy}", params={"search": name, "per_page": 100})
        if search_resp.status_code >= 400:
            raise HTTPException(status_code=search_resp.status_code, detail=f"WordPress {taxonomy} 조회 실패: {search_resp.text}")
        for item in search_resp.json():
            if str(item.get("name", "")).strip().lower() == name.strip().lower():
                return int(item["id"])

        create_resp = await client.post(f"{api_url}/{taxonomy}", json={"name": name})
        if create_resp.status_code == 400 and "term_exists" in create_resp.text:
            retry_resp = await client.get(f"{api_url}/{taxonomy}", params={"search": name, "per_page": 100})
            if retry_resp.status_code >= 400:
                raise HTTPException(status_code=retry_resp.status_code, detail=f"WordPress {taxonomy} 재조회 실패: {retry_resp.text}")
            for item in retry_resp.json():
                if str(item.get("name", "")).strip().lower() == name.strip().lower():
                    return int(item["id"])
        if create_resp.status_code >= 400:
            raise HTTPException(status_code=create_resp.status_code, detail=f"WordPress {taxonomy} 생성 실패: {create_resp.text}")
        return int(create_resp.json()["id"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WordPress {taxonomy} 처리 실패: {exc}")


@router.get("/wordpress/health")
async def wordpress_health(current_user: User = Depends(get_current_user)):
    check_wordpress_access(current_user)
    api_url, username, app_password = wp_config()
    auth = (username, app_password)
    async with httpx.AsyncClient(auth=auth, timeout=10) as client:
        try:
            resp = await client.get(f"{api_url}/users/me")
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            data = resp.json()
            return {
                "ok": True,
                "api_url": api_url,
                "user": data.get("name") or data.get("slug") or username,
                "message": "WordPress REST API 연결 정상",
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"WordPress API 연결 실패: {exc}")


@router.post("/wordpress/draft")
async def create_wordpress_draft(req: WordPressDraftRequest, current_user: User = Depends(get_current_user)):
    check_wordpress_access(current_user)
    api_url, username, app_password = wp_config()
    content = clean_post_content(req.content)
    if not content:
        raise HTTPException(status_code=400, detail="WordPress 본문 HTML이 비어 있습니다.")

    title = clean_text(req.title) or "제목 없음"
    excerpt = clean_text(req.excerpt or req.meta_description)
    meta_description = clean_text(req.meta_description)
    focus_keyword = clean_text(req.focus_keyword)
    featured_image_alt = clean_text(req.featured_image_alt)
    slug = clean_text(req.slug)

    auth = (username, app_password)
    async with httpx.AsyncClient(auth=auth, timeout=30) as client:
        category_ids = []
        category_warnings = []
        for name in split_terms(req.categories_text):
            try:
                term_id = await ensure_term(client, api_url, "categories", clean_text(name))
                if term_id:
                    category_ids.append(term_id)
            except HTTPException as exc:
                category_warnings.append(str(exc.detail))

        tag_ids = []
        tag_warnings = []
        for name in split_terms(req.tags_text):
            try:
                term_id = await ensure_term(client, api_url, "tags", clean_text(name))
                if term_id:
                    tag_ids.append(term_id)
            except HTTPException as exc:
                tag_warnings.append(str(exc.detail))

        payload = {
            "title": title,
            "content": content,
            "status": req.status or "draft",
        }
        if slug:
            payload["slug"] = slug
        if excerpt:
            payload["excerpt"] = excerpt
        if category_ids:
            payload["categories"] = category_ids
        if tag_ids:
            payload["tags"] = tag_ids

        # Yoast/RankMath 등 플러그인별 메타키가 다를 수 있어 우선 안전한 custom meta로 저장합니다.
        # REST API에 등록되지 않은 meta key는 WordPress가 무시할 수 있지만 글 생성에는 영향 없습니다.
        payload["meta"] = {
            "storymaker_meta_description": meta_description,
            "storymaker_focus_keyword": focus_keyword,
            "storymaker_featured_image_alt": featured_image_alt,
            "rank_math_title": title,
            "rank_math_description": meta_description or excerpt,
            "rank_math_focus_keyword": focus_keyword,
            "rank_math_facebook_title": title,
            "rank_math_facebook_description": meta_description or excerpt,
            "rank_math_twitter_title": title,
            "rank_math_twitter_description": meta_description or excerpt,
        }

        try:
            resp = await client.post(f"{api_url}/posts", json=payload)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=f"WordPress 글 생성 실패: {resp.text}")
            data = resp.json()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"WordPress 글 생성 처리 실패: {exc}")

    post_id = int(data.get("id", 0))
    link = data.get("link", "")
    edit_link = ""
    if link:
        edit_link = link

    return {
        "id": post_id,
        "link": link,
        "edit_link": edit_link,
        "status": data.get("status", "draft"),
        "message": "WordPress 초안 등록 완료",
        "warnings": {
            "categories": category_warnings,
            "tags": tag_warnings,
        },
    }


@router.post("/wordpress/draft-from-blocks")
async def create_wordpress_draft_from_blocks(req: StoryMakerBlocksDraftRequest, current_user: User = Depends(get_current_user)):
    """BLOG_TITLES, BLOG_POST, INSTAGRAM_POST, CARROT_POST 블록을 WordPress 초안으로 등록합니다."""
    check_wordpress_access(current_user)
    draft_req = storymaker_blocks_to_wp_request(req)
    result = await create_wordpress_draft(draft_req, current_user=current_user)
    if isinstance(result, dict):
        result["source"] = "storymaker_blocks"
        result["mapped_title"] = draft_req.title
    return result
