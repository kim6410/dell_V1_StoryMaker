# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 네이버 블로그 크롤링 서비스 모듈 (scrape_service.py)
"""
import re
import requests
from bs4 import BeautifulSoup

def normalize_naver_blog_url(url: str) -> str:
    """
    네이버 블로그의 일반 모바일/PC URL을 iframe 내부 포스트 뷰어 주소로 표준화합니다.
    """
    if "PostView.naver" in url:
        return url

    # blog.naver.com/아이디/글번호 패턴 매칭
    match = re.search(r"blog\.naver\.com/([\w-]+)/(\d+)", url)
    if not match:
        return ""

    blog_id = match.group(1)
    log_no = match.group(2)
    return f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"


def clean_lines(lines: list) -> list:
    """
    추출된 텍스트 리스트의 불필요한 공백을 정돈하고 중복 행을 거릅니다.
    """
    cleaned = []
    seen = set()
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        if line in seen:
            continue
        seen.add(line)
        cleaned.append(line)
    return cleaned


def scrape_naver_blog(url: str) -> dict:
    """
    네이버 블로그 주소로부터 제목 및 본문 텍스트를 크롤링하여 반환합니다.
    
    Returns:
        dict: {"ok": bool, "title": str, "text": str, "error": str}
    """
    post_url = normalize_naver_blog_url(url)
    if not post_url:
        return {"ok": False, "title": "", "text": "", "error": "올바른 네이버 블로그 URL 형식이 아닙니다."}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://blog.naver.com/",
    }

    try:
        response = requests.get(post_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return {"ok": False, "title": "", "text": "", "error": f"페이지를 불러오지 못했습니다. (Status: {response.status_code})"}

        soup = BeautifulSoup(response.text, "html.parser")

        # 블로그 제목 추출 (여러 스크랩 버전 대응)
        title = ""
        for selector in [".se-title-text", ".pcol1", ".htitle"]:
            el = soup.select_one(selector)
            if el and el.get_text(strip=True):
                title = el.get_text(" ", strip=True)
                break

        # 본문 영역 파악
        main_content = soup.select_one(".se-main-container")
        if not main_content:
            main_content = soup.find(id="postViewArea")

        if not main_content:
            return {"ok": False, "title": "", "text": "", "error": "블로그 본문 영역을 찾지 못했습니다."}

        lines = []
        # 스마트에디터/구버전 태그를 순회하며 텍스트 추출
        candidates = main_content.find_all(["p", "span", "div"])
        for node in candidates:
            text = node.get_text(" ", strip=True)
            if text:
                lines.append(text)

        # 보조 데이터용 이미지 Alt 수집
        for img in main_content.find_all("img"):
            alt = img.get("alt")
            if alt:
                lines.append(f"[사진 설명 Alt] {alt}")

        cleaned = clean_lines(lines)
        full_text = "\n".join(cleaned)

        return {
            "ok": True,
            "title": title,
            "text": full_text,
            "error": ""
        }

    except Exception as e:
        return {"ok": False, "title": "", "text": "", "error": f"크롤링 중 서버 장애 발생: {str(e)}"}
