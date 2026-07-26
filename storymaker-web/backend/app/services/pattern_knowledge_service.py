# -*- coding: utf-8 -*-
"""Pattern Knowledge Engine service.

AI is not used here. Search, analysis, snapshots, trends, and discovery are
rule/data operations built on the existing Content Idea Engine.
"""
import re
import threading
import time
from collections import Counter
from datetime import datetime
from typing import Any

from app.db.database import SessionLocal
from app.db import pattern_repository as repo
from app.services.content_idea_service import search_naver_blog_ideas, analyze_naver_blog_ideas

_scheduler_started = False
_scheduler_lock = threading.Lock()


def list_learning_targets(db):
    return repo.list_targets(db)


def save_learning_target(db, payload: dict) -> dict:
    if not payload.get("company_name") or not payload.get("industry") or not payload.get("region"):
        raise ValueError("company_name, industry, region are required")
    return repo.upsert_target(db, payload)


def _keywords_for_target(target: dict) -> list[str]:
    seen = set()
    result = []
    for kw in (target.get("primary_keywords") or []) + (target.get("secondary_keywords") or []):
        clean = str(kw).strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    if not result and target.get("region") and target.get("industry"):
        result.append(f"{target['region']} {target['industry']}")
    return result


def _title_pattern(title: str) -> str:
    if "?" in title:
        return "질문형"
    if any(ch.isdigit() for ch in title):
        return "숫자형"
    if any(word in title for word in ["후기", "내돈내산", "리뷰"]):
        return "후기형"
    if any(word in title for word in ["비교", "추천", "BEST"]):
        return "비교/추천형"
    return "정보형"


def _snapshot_from_item(target: dict, keyword: str, item: dict, text_block: str, cache_status: str, analysis_version: str) -> dict:
    score = item.get("score") or {}
    details = item.get("analysis_details") or {}
    seo = details.get("seo") or {}
    return {
        "collected_at": repo.now_iso(),
        "target_id": target.get("id"),
        "company_name": target.get("company_name"),
        "keyword": keyword,
        "region": target.get("region"),
        "industry": target.get("industry"),
        "organic_rank": item.get("organic_rank") or item.get("rank"),
        "recommendation_score": item.get("recommendation_score"),
        "business_score": item.get("business_score"),
        "local_score": item.get("locality_score"),
        "seo_score": score.get("relevance"),
        "cta_score": score.get("cta_score"),
        "trust_score": score.get("trust_score"),
        "freshness_score": item.get("freshness_score") or score.get("freshness"),
        "style_type": item.get("style_type"),
        "title_pattern": _title_pattern(item.get("title", "")),
        "keyword_frequency": seo.get("keyword_freq"),
        "location_frequency": seo.get("location_freq"),
        "cta_type": item.get("cta_type"),
        "pattern_summary": text_block,
        "analysis_version": analysis_version,
        "cache_status": cache_status,
    }


def run_learning_target(db, target: dict) -> dict:
    history_id = repo.start_history(db, target.get("id"))
    collected = 0
    analyzed = 0
    try:
        for keyword in _keywords_for_target(target):
            search_res = search_naver_blog_ideas(keyword, 5)
            analysis_res = analyze_naver_blog_ideas(keyword)
            text_block = analysis_res.get("text_block", "")
            for item in search_res.get("items", []):
                repo.insert_snapshot(db, _snapshot_from_item(
                    target,
                    keyword,
                    item,
                    text_block,
                    search_res.get("cache_status", "-"),
                    search_res.get("analysis_version", "2.0"),
                ))
                collected += 1
            analyzed += 1
        db.commit()
        repo.finish_history(db, history_id, "success", collected, analyzed)
        if target.get("id"):
            repo.update_target_run(db, target["id"], True, target.get("priority", "MEDIUM"))
        return {"ok": True, "target_id": target.get("id"), "collected": collected, "analyzed": analyzed}
    except Exception as exc:
        db.rollback()
        repo.finish_history(db, history_id, "failed", collected, analyzed, str(exc))
        if target.get("id"):
            repo.update_target_run(db, target["id"], False, target.get("priority", "MEDIUM"))
        return {"ok": False, "target_id": target.get("id"), "collected": collected, "analyzed": analyzed, "error": str(exc)}


def run_due_targets_once() -> dict:
    now = datetime.now()
    if not (2 <= now.hour < 5):
        return {"ok": True, "skipped": True, "reason": "outside learning window", "window": "02:00-05:00"}
    if not _scheduler_lock.acquire(blocking=False):
        return {"ok": True, "skipped": True, "reason": "scheduler lock active"}
    try:
        db = SessionLocal()
        try:
            results = [run_learning_target(db, target) for target in repo.due_targets(db, repo.now_iso())]
            return {"ok": True, "skipped": False, "results": results}
        finally:
            db.close()
    finally:
        _scheduler_lock.release()


def run_target_now(target_id: int | None = None) -> dict:
    if not _scheduler_lock.acquire(blocking=False):
        return {"ok": False, "message": "scheduler lock active"}
    try:
        db = SessionLocal()
        try:
            targets = repo.list_targets(db)
            if target_id:
                targets = [t for t in targets if t["id"] == target_id]
            results = [run_learning_target(db, t) for t in targets[:1]]
            return {"ok": True, "results": results}
        finally:
            db.close()
    finally:
        _scheduler_lock.release()


def trend_report(db, days: int = 30, keyword: str | None = None) -> dict:
    rows = repo.recent_snapshots(db, days, keyword)
    if not rows:
        return {"period_days": days, "count": 0, "trends": []}
    style = Counter(r.get("style_type") for r in rows if r.get("style_type"))
    cta = Counter(r.get("cta_type") for r in rows if r.get("cta_type"))
    title = Counter(r.get("title_pattern") for r in rows if r.get("title_pattern"))
    avg = lambda key: round(sum((r.get(key) or 0) for r in rows) / max(len(rows), 1), 1)
    return {
        "period_days": days,
        "count": len(rows),
        "top_style": style.most_common(1)[0][0] if style else "-",
        "top_cta": cta.most_common(1)[0][0] if cta else "-",
        "top_title_pattern": title.most_common(1)[0][0] if title else "-",
        "avg_recommendation_score": avg("recommendation_score"),
        "avg_location_frequency": avg("location_frequency"),
        "by_industry": dict(Counter(r.get("industry") for r in rows if r.get("industry"))),
        "trends": [
            f"{style.most_common(1)[0][0]} 증가" if style else "스타일 데이터 부족",
            f"{cta.most_common(1)[0][0]} CTA 우세" if cta else "CTA 데이터 부족",
            f"지역명 평균 {avg('location_frequency')}회",
            f"추천점수 평균 {avg('recommendation_score')}점",
        ],
    }


def discover_keywords(db, seed_keyword: str) -> dict:
    seed = seed_keyword.strip()
    rows = repo.recent_snapshots(db, 90, seed.split()[0] if seed else None)
    words = Counter()
    region = seed.split()[0] if seed else ""
    for row in rows:
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", " ".join([row.get("keyword") or "", row.get("title_pattern") or "", row.get("style_type") or "", row.get("cta_type") or ""])):
            if token not in seed:
                words[token] += 1
    defaults = ["문수리", "욕실 리모델링", "누수", "수도배관", "현관문 수리"]
    candidates = [f"{region} {w}".strip() for w, _ in words.most_common(8)]
    for item in defaults:
        kw = f"{region} {item}".strip()
        if kw not in candidates:
            candidates.append(kw)
    candidates = candidates[:10]
    for kw in candidates:
        repo.insert_discovered_keyword(db, seed, kw)
    db.commit()
    return {"seed_keyword": seed, "candidates": candidates}


def health_status(db) -> dict:
    status = repo.health(db)
    status["scheduler"] = {
        "started": _scheduler_started,
        "lock_active": _scheduler_lock.locked(),
        "window": "02:00-05:00",
        "mode": "sequential",
    }
    return status


def _scheduler_loop() -> None:
    while True:
        run_due_targets_once()
        time.sleep(1800)


def start_learning_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    thread = threading.Thread(target=_scheduler_loop, daemon=True)
    thread.start()
