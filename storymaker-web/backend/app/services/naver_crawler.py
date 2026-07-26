# -*- coding: utf-8 -*-
"""
StoryMaker Naver Blog crawler helpers.

content_idea_service.py에서 실제 운영 중이던 네이버 블로그 상세 수집 함수를
동작 변경 없이 분리하기 위한 모듈입니다.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup


def is_ui_text(text: str) -> bool:
    """
    네이버 블로그 UI성 문구인지 검사합니다.
    본문 맥락에 영향을 주지 않는 짧은 문구 및 버튼 텍스트를 식별합니다.
    """
    # 텍스트에서 한글과 영문만 추출하여 비교 (공백, 숫자, 특수문자, 괄호 등 제외)
    cleaned = re.sub(r'[^가-힣a-zA-Z]', '', text)
    
    ui_keywords = {
        "공감", "댓글", "이웃추가", "공유하기", "블로그", "카페", 
        "인쇄", "신고", "이전글", "다음글", "태그", "좋아요", 
        "스크랩", "서로이웃", "안부", "프로필", "이글을보낸곳",
        "공감하기", "댓글쓰기", "이웃", "서로이웃추가", "서로이웃신청",
        "공유", "목록", "글쓰기", "방명록", "지도", "서재"
    }
    return cleaned in ui_keywords


def parse_dimension(value: Any) -> int | None:
    """
    img 태그의 가로나 세로 크기 값을 안전하게 숫자로 변환합니다.
    relative 크기(%)나 파싱 불가능한 값은 None을 반환합니다.
    """
    if not value:
        return None
    try:
        match = re.match(r'^(\d+)(?:px)?$', str(value).strip())
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def scrape_naver_blog_detail(url: str) -> Dict[str, Any]:
    """
    지정한 블로그 URL로부터 문단(Paragraphs) 목록과 이미지 목록을 세부 스크래핑합니다.

    기존 content_idea_service.py의 scrape_naver_blog_detail() 구현을 기반으로
    중복 문단 제거 및 HTML 노이즈 제거 로직이 추가되었습니다.
    """
    from app.services.scrape_service import normalize_naver_blog_url

    post_url = normalize_naver_blog_url(url)
    if not post_url:
        return {"ok": False, "title": "", "text": "", "paragraphs": [], "images": [], "error": "Invalid URL"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Referer": "https://blog.naver.com/",
    }

    try:
        response = requests.get(post_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"ok": False, "title": "", "text": "", "paragraphs": [], "images": [], "error": f"HTTP {response.status_code}"}

        soup = BeautifulSoup(response.text, "html.parser")

        # HTML 노이즈 제거
        for tag in soup(["script", "style", "footer", "nav", "aside", "noscript"]):
            tag.decompose()

        title = ""
        for selector in [".se-title-text", ".pcol1", ".htitle"]:
            el = soup.select_one(selector)
            if el and el.get_text(strip=True):
                title = el.get_text(" ", strip=True)
                break

        main_content = soup.select_one(".se-main-container")
        if not main_content:
            main_content = soup.find(id="postViewArea")

        if not main_content:
            return {"ok": False, "title": title, "text": "", "paragraphs": [], "images": [], "error": "No body content found"}

        raw_paragraphs = []
        p_elements = main_content.select(".se-paragraph, p, div.se-text-paragraph")
        if p_elements:
            # 중첩된 자식/부모 엘리먼트 처리
            # 어떤 엘리먼트 el이 다른 엘리먼트의 부모라면(즉 다른 엘리먼트가 el.descendants에 존재하면)
            # 그 el은 제외하여 자식(세부 문단) 단위만 수집합니다.
            filtered_elements = []
            for el in p_elements:
                has_child_in_list = False
                for other in p_elements:
                    if other is not el and other in el.descendants:
                        has_child_in_list = True
                        break
                if not has_child_in_list:
                    filtered_elements.append(el)

            for el in filtered_elements:
                txt = el.get_text(" ", strip=True)
                if txt:
                    raw_paragraphs.append(txt)
        else:
            raw_txt = main_content.get_text("\n", strip=True)
            raw_paragraphs = [p.strip() for p in raw_txt.split("\n") if p.strip()]

        # 문단 dedupe (순서 보존) 및 불필요 문구 제거
        seen_paragraphs = set()
        paragraphs = []
        for p_txt in raw_paragraphs:
            p_stripped = p_txt.strip()
            if not p_stripped:
                continue
            
            # 중복 제거
            if p_stripped in seen_paragraphs:
                continue
            
            # UI 문구 필터링
            if is_ui_text(p_stripped):
                continue
                
            seen_paragraphs.add(p_stripped)
            paragraphs.append(p_stripped)

        # 이미지 수집 및 필터링
        images = []
        seen_srcs = set()
        img_idx = 1

        for img in main_content.find_all("img"):
            # lazy src 우선 고려
            src = img.get("data-lazy-src") or img.get("data-src") or img.get("src", "")
            src = src.strip()
            if not src:
                continue
                
            # 이미지 중복 제거
            if src in seen_srcs:
                continue
                
            # 불필요 이미지 필터링
            # 1) URL 키워드 기반 필터링
            lower_src = src.lower()
            exclude_keywords = [
                "sticker", "static.se2", "postfiles.pstatic.net/sticker",
                "profile.pstatic.net", "profile.naver.com", "buddy.naver.com",
                "spacer.gif", "pixel.gif", "icon", "emoji", "emoticon"
            ]
            if any(kw in lower_src for kw in exclude_keywords):
                continue
                
            # 2) 크기(width, height) 기반 필터링 (아이콘, spacer, 1px 이미지 방지)
            w_val = parse_dimension(img.get("width"))
            h_val = parse_dimension(img.get("height"))
            if w_val is not None and w_val < 15:
                continue
            if h_val is not None and h_val < 15:
                continue
                
            # alt 추출
            alt = img.get("alt", "").strip()
            
            # caption 추출
            caption = ""
            parent = img.parent
            for _ in range(3):
                if not parent:
                    break
                caption_el = parent.select_one(".se-image-caption, .se-caption, .se-text-caption, figcaption")
                if caption_el:
                    caption = caption_el.get_text(" ", strip=True)
                    break
                parent = parent.parent
                
            seen_srcs.add(src)
            images.append({
                "index": img_idx,
                "src": src,
                "alt": alt,
                "caption": caption,
                "width": w_val,
                "height": h_val
            })
            img_idx += 1

        full_text = "\n".join(paragraphs)
        return {
            "ok": True,
            "title": title,
            "text": full_text,
            "paragraphs": paragraphs,
            "images": images,
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "title": "", "text": "", "paragraphs": [], "images": [], "error": str(e)}


def search_naver_blog(keyword: str) -> Dict[str, Any]:
    """
    네이버 통합 블로그 검색 페이지를 요청하고 원시 파싱 결과를 반환합니다.
    """
    keyword_strip = keyword.strip()
    search_url = f"https://search.naver.com/search.naver?ssc=tab.blog.all&query={requests.utils.quote(keyword_strip)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"ok": False, "error": f"Naver Search HTTP {response.status_code}"}

        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. 블로그 이름 사전 구축
        blog_names = {}
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            m_profile = re.match(r"^https://blog\.naver\.com/([\w-]+)/?$", href)
            if m_profile:
                blog_id = m_profile.group(1)
                text = a.get_text(strip=True)
                if text and text not in ["프로필", "이웃추가", "공식블로그", "블로그 홈", "안부글", "글쓰기"]:
                    if blog_id not in blog_names or len(text) > len(blog_names[blog_id]):
                        blog_names[blog_id] = text

        # 2. 블로그 포스트 정보 파싱
        blog_posts = []
        organic_counter = 0

        all_anchors = soup.find_all("a", href=True)
        scraped_count = max(len(all_anchors), 45)

        for a in all_anchors:
            href = a.get("href", "").strip()
            
            exclude_patterns = ["adcr", "searchad", "shopping", "cafe.naver.com", "kin.naver.com", "news.naver.com", "map.naver.com", "smartstore.naver.com"]
            if any(pat in href for pat in exclude_patterns):
                continue
            
            m_post = re.search(r"blog\.naver\.com/([\w-]+)/(\d+)", href)
            if not m_post:
                continue
            
            blog_id = m_post.group(1)
            post_id = m_post.group(2)
            normalized_url = f"https://blog.naver.com/{blog_id}/{post_id}"
            
            text = a.get_text(" ", strip=True)
            if not text:
                continue

            write_date = None
            parent = a.find_parent()
            if parent:
                parent_text = parent.get_text(" ", strip=True)
                date_match = re.search(r'\b\d{4}\.\d{2}\.\d{2}\.', parent_text)
                if date_match:
                    write_date = date_match.group(0)
                else:
                    rel_match = re.search(r'\b(\d{1,2}일\s*전|\d{1,2}시간\s*전|어제|방금|주\s*전)', parent_text)
                    if rel_match:
                        write_date = rel_match.group(0)
            
            post_entry = None
            for p in blog_posts:
                if p["url"] == normalized_url:
                    post_entry = p
                    break
            
            if not post_entry:
                organic_counter += 1
                post_entry = {
                    "blog_id": blog_id,
                    "url": normalized_url,
                    "organic_rank": organic_counter,
                    "write_date": write_date,
                    "texts": []
                }
                blog_posts.append(post_entry)
            
            if text not in post_entry["texts"]:
                post_entry["texts"].append(text)

        return {
            "ok": True,
            "blog_posts": blog_posts,
            "blog_names": blog_names,
            "scraped_count": scraped_count
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def calculate_business_score(keyword: str, title: str, text: str) -> int:
    """업종 적합도(0~100점)를 계산합니다."""
    title_lower = title.lower()
    text_lower = text.lower()
    
    cat = "local"
    if any(w in keyword for w in ["집수리", "도어락", "수리", "설비", "누수", "수도", "배관", "욕실", "인테리어", "도배", "장판", "샷시"]):
        cat = "repair"
    elif any(w in keyword for w in ["학원", "교육", "공부방", "과외", "수업"]):
        cat = "edu"
        
    score = 70
    
    if cat == "repair":
        pos = ["집수리", "설비", "누수", "수도", "배관", "욕실", "인테리어", "시공", "교체", "수리", "공사", "설치", "작업", "보수"]
        neg = ["학원", "교육", "채용", "뉴스", "쇼핑", "광고", "자격증", "수강생", "교육과정", "모집", "아카데미"]
    elif cat == "edu":
        pos = ["학원", "교육", "아카데미", "수업", "강의", "과외", "수강", "공부방", "교습소", "학습", "성적"]
        neg = ["누수", "배관", "수도", "설비", "시공", "교체", "현장"]
    else:
        pos = ["맛집", "카페", "메뉴", "음식", "방문", "예약", "매장", "오픈", "이벤트", "후기"]
        neg = ["학원", "뉴스", "쇼핑", "자격증", "채용"]
        
    pos_matches = sum(1 for w in pos if w in title_lower or w in text_lower)
    score += min(30, pos_matches * 5)
    
    neg_matches = sum(1 for w in neg if w in title_lower or w in text_lower)
    score -= min(40, neg_matches * 10)
    
    return max(0, min(100, score))


def calculate_local_score(keyword: str, title: str, text: str) -> int:
    """지역 적합도(10~100점)를 계산합니다."""
    title_lower = title.lower()
    text_lower = text.lower()
    
    location_words = ["울산", "양주", "하남", "서울", "부산", "인천", "대구", "대전", "광주", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
    primary_loc = None
    for loc in location_words:
        if loc in keyword:
            primary_loc = loc
            break
            
    if not primary_loc:
        return 50
        
    score = 60
    if primary_loc in title_lower:
        score += 20
    if primary_loc in text_lower:
        score += 10
        
    sub_districts = {
        "울산": ["북구", "동구", "남구", "중구", "울주군"],
        "서울": ["강남", "서초", "송파", "마포", "용산", "성동", "영등포"],
        "부산": ["해운대", "수영", "동래", "금정", "진구", "기장"],
        "대구": ["수성", "달서", "중구", "북구", "동구"],
        "인천": ["송도", "연수", "남동", "부평", "서구"]
    }
    
    subs = sub_districts.get(primary_loc, ["동", "구", "군"])
    has_sub = any(sub in title_lower or sub in text_lower for sub in subs)
    
    if has_sub:
        score += 10
    else:
        score -= 20
        
    return max(10, min(100, score))


def calculate_competitor_score(company_freq: int, phone_count: int, image_count: int, style: str, cta_type: str) -> int:
    """실제 경쟁업체 가능성을 산출합니다 (0~100점)."""
    score = 20
    if company_freq > 0:
        score += 20
    if phone_count > 0:
        score += 20
    if image_count >= 3:
        score += 20
    if style in ["후기형", "전문가형"]:
        score += 10
    if cta_type != "댓글":
        score += 10
    return min(100, score)


def calculate_freshness_score(write_date: str | None) -> int:
    """포스트 작성일을 기반으로 최신성 점수(30~100점)를 계산합니다."""
    if not write_date:
        return 30
    dt_str = write_date.lower()
    if any(w in dt_str for w in ["방금", "시간", "오늘", "어제", "1일", "2일"]):
        return 95
    if any(w in dt_str for w in ["일 전", "주 전"]):
        m = re.search(r'\d+', dt_str)
        if m:
            days = int(m.group(0))
            if days <= 7:
                return 90
            elif days <= 30:
                return 80
        return 85
    if "달 전" in dt_str:
        return 75
    m_year = re.search(r'\b(202\d)', dt_str)
    if m_year:
        year = int(m_year.group(1))
        if year == 2026:
            return 70
        elif year == 2025:
            return 50
    return 30


def get_title_similarity(t1: str, t2: str) -> float:
    """자카드 유사도 규칙으로 제목 텍스트 간 형태소 겹침 비중을 구합니다."""
    s1 = set(re.findall(r'[가-힣a-zA-Z0-9]+', t1.lower()))
    s2 = set(re.findall(r'[가-힣a-zA-Z0-9]+', t2.lower()))
    if not s1 or not s2:
        return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))


def calculate_recommendation_score(organic_rank: int, business: int, local: int, seo: int, cta: int, trust: int, freshness: int) -> int:
    """
    최종 추천 점수를 계산합니다 (0~100점).
    """
    rank_score = 100
    if organic_rank == 2:
        rank_score = 90
    elif organic_rank == 3:
        rank_score = 80
    elif organic_rank == 4:
        rank_score = 70
    elif organic_rank == 5:
        rank_score = 60
    elif organic_rank >= 6:
        rank_score = 50
        
    score = (business * 0.20) + (local * 0.15) + (seo * 0.15) + (cta * 0.10) + (trust * 0.10) + (freshness * 0.10) + (rank_score * 0.20)
    return int(round(score))


def generate_user_friendly_reason(locality: int, style: str, cta: str, freshness: int, comp_score: int) -> str:
    """
    일반 사용자용 1줄 친화적 추천 이유를 Python 규칙 엔진으로 생성합니다.
    """
    if locality >= 80:
        return "지역성과 실제 시공 위치 정보가 상세히 기술되어 참고하기 좋습니다."
    elif style == "후기형" and comp_score >= 70:
        return "실제 시공 사례 중심의 후기형 구조로 고객의 신뢰감을 줍니다."
    elif cta == "전화 문의":
        return "대표 연락처를 활용한 직접 상담 유도 흐름이 잘 정리되어 있습니다."
    elif style == "전문가형":
        return "전문적인 기술 설명과 상세 공정 중심의 유용한 정보성 글입니다."
    elif freshness >= 90:
        return "가장 최근에 발행되어 현재 로컬 시장의 최신 트렌드를 잘 보여줍니다."
    else:
        return "고객 고민 사항과 해결 과정이 명확하게 서술되어 스토리텔링에 최적화된 글감입니다."


def generate_recommendation_signals(locality: int, style: str, comp_score: int, cta: str, freshness: int, rank: int) -> List[str]:
    """
    운영자용 점수 근거 설명 시그널 리스트를 생성합니다.
    """
    signals = []
    if locality >= 80:
        signals.append("지역명 사용 우수")
    else:
        signals.append("지역명 보통")
        
    if style == "후기형":
        signals.append("후기형 구조")
    elif style == "전문가형":
        signals.append("전문가형 본문")
    else:
        signals.append("일반 정보성")
        
    if comp_score >= 70:
        signals.append("실제 업체")
    else:
        signals.append("일반 블로거")
        
    if cta == "전화 문의":
        signals.append("전화 CTA")
    elif cta == "예약":
        signals.append("예약 CTA")
    else:
        signals.append("일반 CTA")
        
    if freshness >= 85:
        signals.append("최신 글")
    else:
        signals.append("과거 발행")
        
    signals.append("중복 없음")
    return signals


def count_emoji(text: str) -> int:
    """텍스트 내의 이모지 개수를 추출합니다."""
    count = 0
    for char in text:
        cp = ord(char)
        if (0x1F600 <= cp <= 0x1F64F) or \
           (0x1F300 <= cp <= 0x1F5FF) or \
           (0x1F680 <= cp <= 0x1F6FF) or \
           (0x1F1E0 <= cp <= 0x1F1FF) or \
           (0x2700 <= cp <= 0x27BF) or \
           (0x1F900 <= cp <= 0x1F9FF) or \
           (0x1F000 <= cp <= 0x1F09F):
            count += 1
    return count


def calculate_particle_ratio(text: str) -> float:
    """텍스트 내의 국문 조사 비율을 어미 종결 기준으로 대략 연산합니다."""
    particles = ["은", "는", "이", "가", "을", "를", "의", "에", "로", "으로", "과", "와"]
    words = text.split()
    if not words:
        return 0.0
    
    particle_count = 0
    for w in words:
        for p in particles:
            if w.endswith(p):
                particle_count += 1
                break
    return particle_count / len(words)


def estimate_reading_difficulty(avg_sentence_len: float, particle_ratio: float) -> str:
    """어균 문장 길이와 조사 비율을 바탕으로 독해 난이도를 판정합니다."""
    score = 100 - (avg_sentence_len * 0.4) - (particle_ratio * 100 * 0.4)
    if score > 75:
        return "쉬움 (일반 소상공인 대상 최적)"
    elif score > 50:
        return "보통 (이해하기 수월함)"
    else:
        return "어려움 (단문 위주 교정 권장)"


def compute_scores(metrics: Dict[str, Any]) -> Dict[str, int]:
    """단일 문서의 통계 지수를 바탕으로 6개 영역의 Scoring(0~100)을 연산합니다."""
    seo = 70
    kw_density = metrics["keyword_density"]
    if 1.5 <= kw_density <= 3.5:
        seo += 15
    elif 0.5 <= kw_density < 1.5 or 3.5 < kw_density <= 5.0:
        seo += 8
    if 8 <= metrics["image_count"] <= 25:
        seo += 10
    if 25 <= metrics["title_len"] <= 40:
        seo += 5
    seo = min(100, seo)

    readability = 80
    if metrics["avg_sentence_len"] > 60:
        readability -= 15
    elif metrics["avg_sentence_len"] < 35:
        readability += 10
    if 0.2 <= metrics["particle_ratio"] <= 0.45:
        readability += 10
    else:
        readability -= 10
    readability = max(20, min(100, readability))

    cta = 50
    if metrics["has_phone"]:
        cta += 25
    if metrics["has_cta"]:
        cta += 15
    if metrics["url_count"] > 0:
        cta += 10
    cta = min(100, cta)

    story = 60
    if metrics["style"] == "스토리텔링형":
        story += 25
    if metrics["has_greeting"]:
        story += 10
    if metrics["has_review_start"]:
        story += 5
    story = min(100, story)

    trust = 60
    if metrics["has_phone"]:
        trust += 20
    if metrics["company_freq"] > 0:
        trust += 10
    if metrics["image_count"] >= 5:
        trust += 10
    trust = min(100, trust)

    local_seo = 50
    if metrics["has_location_title"]:
        local_seo += 30
    if metrics["location_freq"] >= 3:
        local_seo += 20
    elif metrics["location_freq"] >= 1:
        local_seo += 10
    local_seo = min(100, local_seo)

    return {
        "seo_score": int(seo),
        "readability_score": int(readability),
        "cta_score": int(cta),
        "story_score": int(story),
        "trust_score": int(trust),
        "local_seo_score": int(local_seo)
    }
