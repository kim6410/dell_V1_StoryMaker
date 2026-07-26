# -*- coding: utf-8 -*-
"""Content Performance Intelligence Engine.

Rule engine only. Raw content is scored in memory and never stored.
"""
import re
import threading
import time
from collections import Counter
from datetime import datetime

from app.db import performance_repository as repo

_scheduler_started = False
_scheduler_lock = threading.Lock()


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def score_content(payload: dict) -> dict:
    title = str(payload.get("title") or "")
    content = str(payload.get("content_text") or "")
    keyword = str(payload.get("keyword") or "")
    region = str(payload.get("region") or "")
    industry = str(payload.get("industry") or "")
    meta_description = str(payload.get("meta_description") or "")

    combined = f"{title}\n{content}"
    keyword_count = combined.count(keyword) if keyword else 0
    location_count = combined.count(region) if region else 0
    subheading_count = len(re.findall(r"(^|\n)\s{0,3}(#{2,4}\s+|[0-9]+\.|[가-힣A-Za-z ]{2,20}:)", content))
    sentences = [s for s in re.split(r"[.!?\n。]+", content) if s.strip()]
    avg_sentence_len = sum(len(s.strip()) for s in sentences) / max(len(sentences), 1)
    cta_words = ["문의", "예약", "전화", "상담", "방문", "댓글", "카카오"]
    cta_hits = sum(combined.count(w) for w in cta_words)
    has_internal_link = bool(re.search(r"https?://|/blog|/post|/contact", content))

    seo_score = _clamp(55 + (15 if 18 <= len(title) <= 45 else 0) + min(keyword_count * 5, 20) + (10 if subheading_count >= 2 else 0))
    keyword_coverage = _clamp(40 + min(keyword_count * 12, 45) + (15 if keyword and keyword in title else 0))
    cta_quality = _clamp(45 + min(cta_hits * 12, 45) + (10 if re.search(r"(문의|예약|전화).{0,20}$", content) else 0))
    readability = _clamp(100 - max(0, int(avg_sentence_len) - 35) * 2)
    local_seo = _clamp(45 + min(location_count * 12, 45) + (10 if region and region in title else 0))
    industry_match = _clamp(50 + (35 if industry and industry in combined else 0) + (15 if keyword and keyword in combined else 0))
    seasonal_match = _clamp(65 + (10 if any(w in combined for w in ["여름", "겨울", "장마", "휴가", "연말", "새해"]) else 0))
    pattern_match = _clamp(60 + (10 if subheading_count else 0) + (10 if cta_hits else 0) + (10 if location_count else 0))
    trend_match = _clamp(65 + (10 if payload.get("trend_summary") else 0))
    duplicate_risk = _clamp(30 if len(set(re.findall(r"[가-힣A-Za-z0-9]{2,}", combined))) < 30 else 10)

    performance_score = _clamp(round((
        seo_score + keyword_coverage + cta_quality + readability + local_seo +
        industry_match + seasonal_match + pattern_match + trend_match + (100 - duplicate_risk)
    ) / 10))

    improvements = []
    if location_count < 2:
        improvements.append("지역명이 부족합니다.")
    if cta_quality < 70:
        improvements.append("CTA가 약합니다.")
    if subheading_count < 2:
        improvements.append("소제목이 부족합니다.")
    if keyword_count < 2:
        improvements.append("첫 문단 키워드 밀도가 낮습니다.")
    if not has_internal_link:
        improvements.append("내부 링크가 없습니다.")
    if len(meta_description) and not (70 <= len(meta_description) <= 160):
        improvements.append("메타 설명 길이를 조정하세요.")
    if not improvements:
        improvements.append("현재 구조는 성과 기준을 충족합니다.")

    seo_intelligence = {
        "title_length": len(title),
        "has_location": bool(region and region in title),
        "keyword_count": keyword_count,
        "subheading_count": subheading_count,
        "cta_position": "후반" if cta_hits and re.search(r"(문의|예약|전화).{0,40}$", content) else "분산/없음",
        "has_internal_link": has_internal_link,
        "has_image_alt": bool(payload.get("has_image_alt", False)),
        "meta_description_length": len(meta_description),
    }
    performance_summary = "\n".join([
        "## Content Performance Pattern Summary",
        f"- Keyword: {keyword}",
        f"- Performance Score: {performance_score}",
        f"- SEO: {seo_score}, CTA: {cta_quality}, Local SEO: {local_seo}",
        f"- Winning Pattern: title {len(title)} chars / subheadings {subheading_count} / CTA {seo_intelligence['cta_position']}",
        "- Improvements: " + " / ".join(improvements),
    ])

    result = {
        "content_id": payload.get("content_id"),
        "title": title[:200],
        "keyword": keyword,
        "region": region,
        "industry": industry,
        "performance_score": performance_score,
        "seo_score": seo_score,
        "keyword_coverage": keyword_coverage,
        "cta_quality": cta_quality,
        "readability": readability,
        "local_seo": local_seo,
        "industry_match": industry_match,
        "seasonal_match": seasonal_match,
        "pattern_match": pattern_match,
        "trend_match": trend_match,
        "duplicate_risk": duplicate_risk,
        "seo_intelligence": seo_intelligence,
        "improvements": improvements,
        "improvement_summary": " / ".join(improvements),
        "performance_summary": performance_summary,
    }
    score_id = repo.insert_score(result)
    result["id"] = score_id
    return result


def add_ranking(payload: dict) -> dict:
    return repo.insert_ranking(
        str(payload.get("keyword") or ""),
        str(payload.get("search_engine") or "naver"),
        payload.get("ranking"),
        payload.get("previous_ranking"),
    )


def dashboard() -> dict:
    scores = repo.recent_scores(50)
    top = sorted(scores, key=lambda x: x.get("performance_score") or 0, reverse=True)[:10]
    needs = [s for s in scores if (s.get("performance_score") or 0) < 70][:10]
    trend = repo.trend(30)
    return {
        "average_performance_score": trend.get("avg_performance_score", 0),
        "average_seo_score": trend.get("avg_seo_score", 0),
        "ranking_changes": repo.ranking_history(limit=10),
        "pattern_success_rate": round(sum(1 for s in scores if (s.get("pattern_match") or 0) >= 70) / max(len(scores), 1) * 100, 1),
        "trend_score": trend.get("trend_score", 0),
        "recent_improvements": repo.recent_improvements(10),
        "top_content": top,
        "needs_improvement": needs,
    }


def prompt_feedback_summary() -> str:
    rows = repo.feedback_summaries(5)
    if not rows:
        return ""
    lines = ["### [최신 Performance Summary]", "성과가 좋은 콘텐츠의 패턴 요약만 참고합니다. 원문은 포함하지 않습니다."]
    for row in rows:
        lines.append(f"- {row.get('feedback_summary')}")
    return "\n".join(lines)


def health_status() -> dict:
    data = repo.health()
    data["scheduler"] = {
        "started": _scheduler_started,
        "lock_active": _scheduler_lock.locked(),
        "window": "05:00-05:30",
        "sequence": "02 learning -> 03 pattern -> 04 trend -> 05 performance -> 05:30 feedback",
    }
    return data


def run_performance_once() -> dict:
    if not _scheduler_lock.acquire(blocking=False):
        return {"ok": False, "message": "performance scheduler lock active"}
    try:
        # ponytail: no raw source crawl here; scheduled job rolls up repository state.
        trend = repo.trend(30)
        return {"ok": True, "trend": trend, "feedback_count": len(repo.feedback_summaries(20))}
    finally:
        _scheduler_lock.release()


def _scheduler_loop() -> None:
    while True:
        now = datetime.now()
        if now.hour == 5:
            run_performance_once()
        time.sleep(1800)


def start_performance_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    thread = threading.Thread(target=_scheduler_loop, daemon=True)
    thread.start()
