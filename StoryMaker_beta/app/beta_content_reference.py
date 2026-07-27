# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.beta_auth import current_user_id

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "content_reference"
HISTORY_DIR = DATA_DIR / "history"
CACHE_DIR = DATA_DIR / "cache"
for directory in (DATA_DIR, HISTORY_DIR, CACHE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/beta-api/content-reference", tags=["beta-content-reference"])

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7",
    "Referer": "https://blog.naver.com/",
}

class ScrapeRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


def _normalize_naver_url(url: str) -> str:
    value = html.unescape(str(url or "").strip())
    if not value:
        return ""
    if "PostView.naver" in value:
        return value
    parsed = urlparse(value)
    if parsed.netloc.endswith("blog.naver.com"):
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[1].isdigit():
            return f"https://blog.naver.com/PostView.naver?blogId={parts[0]}&logNo={parts[1]}"
        query = parse_qs(parsed.query)
        blog_id = (query.get("blogId") or [""])[0]
        log_no = (query.get("logNo") or [""])[0]
        if blog_id and log_no:
            return f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
    match = re.search(r"blog\.naver\.com/([\w.-]+)/([0-9]+)", value)
    if match:
        return f"https://blog.naver.com/PostView.naver?blogId={match.group(1)}&logNo={match.group(2)}"
    return ""


def _clean_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    noise = ("공감", "댓글", "블로그", "카테고리", "이웃추가", "본문 기타 기능", "공유하기", "신고하기")
    for raw in lines:
        line = re.sub(r"\s+", " ", str(raw or "")).strip()
        if len(line) < 2 or line in noise:
            continue
        if any(line == token for token in noise):
            continue
        key = re.sub(r"[^0-9A-Za-z가-힣]", "", line).lower()
        if not key or key in seen:
            continue
        # 상위 div 전체문장과 하위 span 문장의 중복을 완화합니다.
        if any(len(key) > 25 and (key in old or old in key) for old in seen if len(old) > 25):
            continue
        seen.add(key)
        cleaned.append(line)
    return cleaned


def _scrape(url: str) -> dict:
    post_url = _normalize_naver_url(url)
    if not post_url:
        raise HTTPException(status_code=400, detail="올바른 네이버 블로그 글 주소를 입력하세요.")
    try:
        response = requests.get(post_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"블로그 페이지를 불러오지 못했습니다: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    title = ""
    for selector in (".se-title-text", ".pcol1", ".htitle", "meta[property='og:title']"):
        node = soup.select_one(selector)
        if node:
            title = (node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)) or ""
            if title:
                break

    container = None
    for selector in (".se-main-container", "#postViewArea", ".se_component_wrap", ".post-view"):
        container = soup.select_one(selector)
        if container:
            break
    if not container:
        raise HTTPException(status_code=422, detail="블로그 본문 영역을 찾지 못했습니다.")

    lines: list[str] = []
    # 새 에디터는 문단 단위를 우선 사용해 상하위 태그 중복을 줄입니다.
    nodes = container.select(".se-text-paragraph, .se-module-text, p")
    if not nodes:
        nodes = container.find_all(["p", "span", "div"])
    for node in nodes:
        text = node.get_text(" ", strip=True)
        if text:
            lines.append(text)
    for image in container.find_all("img"):
        alt = str(image.get("alt") or "").strip()
        if alt and len(alt) > 2:
            lines.append(f"사진 설명: {alt}")

    clean = _clean_lines(lines)
    text = "\n\n".join(clean).strip()
    if len(text) < 30:
        raise HTTPException(status_code=422, detail="활용할 수 있는 본문 내용이 충분하지 않습니다.")
    return {
        "title": title.strip() or "네이버 블로그 참고글",
        "url": url,
        "normalized_url": post_url,
        "text": text[:12000],
        "length": min(len(text), 12000),
    }


def _record(user_id: int, action: str, payload: dict) -> None:
    path = HISTORY_DIR / f"user_{user_id}.jsonl"
    row = {"at": datetime.now(timezone.utc).isoformat(), "action": action, **payload}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


@router.get("/search")
def search_reference(request: Request, q: str = Query(min_length=2, max_length=120), limit: int = Query(5, ge=1, le=10)):
    search_url = f"https://search.naver.com/search.naver?where=blog&query={quote_plus(q.strip())}"
    try:
        response = requests.get(search_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"검색 결과를 불러오지 못했습니다: {exc}") from exc
    soup = BeautifulSoup(response.text, "html.parser")
    items: list[dict] = []
    seen: set[str] = set()
    for anchor in soup.select("a"):
        href = html.unescape(str(anchor.get("href") or ""))
        if "blog.naver.com/" not in href or "PostList" in href:
            continue
        normalized = _normalize_naver_url(href)
        if not normalized or normalized in seen:
            continue
        title = anchor.get_text(" ", strip=True)
        if len(title) < 3:
            continue
        seen.add(normalized)
        items.append({"title": title[:160], "url": href, "normalized_url": normalized})
        if len(items) >= limit:
            break
    user_id = current_user_id(request)
    _record(user_id, "search", {"query": q.strip(), "count": len(items)})
    return {"ok": True, "query": q.strip(), "items": items}


@router.post("/scrape")
def scrape_reference(payload: ScrapeRequest, request: Request):
    item = _scrape(payload.url)
    user_id = current_user_id(request)
    _record(user_id, "scrape", {"title": item["title"], "url": item["url"], "length": item["length"]})
    return {"ok": True, "item": item}
