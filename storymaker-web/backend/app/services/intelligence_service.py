# -*- coding: utf-8 -*-
"""AI Content Intelligence Brain service.

This is a rule engine that combines Pattern and Performance summaries.
It does not store raw prompts, raw generated content, HTML, images, or JSON.
"""
import re
import threading
import time
from collections import Counter
from datetime import datetime

from app.db import intelligence_repository as repo

_scheduler_started = False
_scheduler_lock = threading.Lock()


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def score_prompt(payload: dict) -> dict:
    prompt = str(payload.get("prompt_text") or "")
    keyword = str(payload.get("keyword") or "")
    region = str(payload.get("region") or "")
    industry = str(payload.get("industry") or "")
    cta_words = ["문의", "예약", "전화", "상담", "방문", "댓글", "카카오"]
    emotion_words = ["안심", "따뜻", "믿", "편안", "고민", "도움", "만족", "정성"]
    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", prompt)
    unique_ratio = len(set(words)) / max(len(words), 1)
    keyword_count = prompt.count(keyword) if keyword else 0
    region_count = prompt.count(region) if region else 0
    cta_count = sum(prompt.count(w) for w in cta_words)
    emotion_count = sum(prompt.count(w) for w in emotion_words)
    sentences = [s for s in re.split(r"[.!?\n。]+", prompt) if s.strip()]
    avg_sentence_len = sum(len(s.strip()) for s in sentences) / max(len(sentences), 1)

    seo_score = _clamp(55 + min(keyword_count * 8, 25) + min(region_count * 6, 20))
    human_score = _clamp(70 + (10 if 20 <= avg_sentence_len <= 55 else -10) + int(unique_ratio * 15))
    emotion_score = _clamp(55 + min(emotion_count * 8, 35))
    readability = _clamp(100 - max(0, int(avg_sentence_len) - 45))
    repetition_score = _clamp(int(unique_ratio * 100))
    local_score = _clamp(50 + min(region_count * 12, 45))
    cta_score = _clamp(45 + min(cta_count * 15, 45))
    keyword_density = _clamp(40 + min(keyword_count * 12, 50))
    overall_score = _clamp(round((seo_score + human_score + emotion_score + readability + repetition_score + local_score + cta_score + keyword_density) / 8))

    feedback = []
    if local_score < 70:
        feedback.append("지역성이 부족합니다.")
    if cta_score < 70:
        feedback.append("CTA가 약합니다.")
    if emotion_score < 70:
        feedback.append("감성 표현이 부족합니다.")
    if repetition_score < 55:
        feedback.append("키워드 반복률이 높습니다.")
    if cta_count and not re.search(r"(문의|예약|전화).{0,40}$", prompt):
        feedback.append("전화번호 위치가 부자연스럽습니다.")
    if not feedback:
        feedback.append("현재 Prompt 품질은 안정적입니다.")

    result = {
        "prompt_id": payload.get("prompt_id"),
        "keyword": keyword,
        "region": region,
        "industry": industry,
        "seo_score": seo_score,
        "human_score": human_score,
        "emotion_score": emotion_score,
        "readability": readability,
        "repetition_score": repetition_score,
        "local_score": local_score,
        "cta_score": cta_score,
        "keyword_density": keyword_density,
        "overall_score": overall_score,
        "feedback": feedback,
    }
    result["id"] = repo.insert_prompt_score(result)
    if industry:
        repo.upsert_industry_learning(
            industry,
            best_pattern="지역 문제 → 해결 과정 → 결과 → 문의",
            best_cta="마지막 문단 전화/예약 1회",
            best_emotion="안심, 신뢰, 생활 불편 공감",
            best_keyword=keyword,
            score=overall_score,
        )
    return result


def evolve_prompt() -> dict:
    try:
        from app.db.database import SessionLocal
        from app.db import pattern_repository
        db = SessionLocal()
        try:
            pattern_rows = pattern_repository.recent_snapshots(db, 30)
        finally:
            db.close()
    except Exception:
        pattern_rows = []
    try:
        from app.db import performance_repository
        performance_rows = performance_repository.feedback_summaries(5)
    except Exception:
        performance_rows = []

    pattern_styles = Counter(r.get("style_type") for r in pattern_rows if r.get("style_type"))
    pattern_cta = Counter(r.get("cta_type") for r in pattern_rows if r.get("cta_type"))
    best_pattern = pattern_styles.most_common(1)[0][0] if pattern_styles else "문제 해결형"
    best_cta = pattern_cta.most_common(1)[0][0] if pattern_cta else "마지막 문의 CTA"
    perf_summary = performance_rows[0]["feedback_summary"] if performance_rows else "성과 데이터가 충분하지 않습니다."
    summary = f"Best Pattern: {best_pattern}\nBest CTA: {best_cta}\nPerformance: {perf_summary[:500]}"
    recommendation = "지역명을 4회 이상 자연스럽게 활용하고, 후킹 문장을 먼저 사용하며, 전화번호는 마지막에 1회만 넣으세요."
    score = 80 if pattern_rows or performance_rows else 50
    evolution_id = repo.insert_prompt_evolution(summary, recommendation, score)
    return {"id": evolution_id, "summary": summary, "recommendation": recommendation, "score": score}


def recommendation_summary() -> str:
    evolution = repo.prompt_evolution(1)
    learning = repo.industry_learning(5)
    lines = ["### [AI Brain Recommendation Summary]", "자가 학습 요약만 참고합니다. 원문은 포함하지 않습니다."]
    if evolution:
        lines.append(evolution[0]["summary"])
        lines.append(f"Recommendation: {evolution[0]['recommendation']}")
    for item in learning:
        lines.append(f"- {item['industry']}: Pattern {item.get('best_pattern')} / CTA {item.get('best_cta')} / Emotion {item.get('best_emotion')}")
    return "\n".join(lines) if len(lines) > 2 else ""


def dashboard() -> dict:
    scores = repo.recent_prompt_scores(100)
    feedback = repo.recent_feedback(20)
    learning = repo.industry_learning(20)
    evolution = repo.prompt_evolution(10)
    trend10 = repo.quality_trend(10)
    trend30 = repo.quality_trend(30)
    best_industry = learning[0]["industry"] if learning else "-"
    worst = min(scores, key=lambda s: s.get("overall_score") or 0) if scores else None
    best = max(scores, key=lambda s: s.get("overall_score") or 0) if scores else None
    return {
        "overall_score": trend30.get("avg_overall", 0),
        "prompt_quality": trend10,
        "learning_status": "active" if scores or learning or evolution else "empty",
        "best_pattern": evolution[0]["summary"] if evolution else "-",
        "worst_pattern": worst,
        "best_industry": best_industry,
        "prompt_evolution": evolution,
        "recommendation": evolution[0]["recommendation"] if evolution else "학습 데이터가 더 필요합니다.",
        "quality_trend": {"last10": trend10, "last30": trend30, "last100": repo.quality_trend(100)},
        "todays_learning": feedback[:5],
        "best_prompt": best,
        "industry_learning": learning,
    }


def health_status() -> dict:
    data = repo.health()
    data["engines"] = {
        "pattern_engine": "connected",
        "performance_engine": "connected",
        "brain_engine": "running",
        "repository": "content_intelligence.db",
        "scheduler": "05:30",
        "api": "ok",
    }
    data["scheduler"] = {
        "started": _scheduler_started,
        "lock_active": _scheduler_lock.locked(),
        "window": "05:30",
    }
    return data


def run_brain_once() -> dict:
    if not _scheduler_lock.acquire(blocking=False):
        return {"ok": False, "message": "brain scheduler lock active"}
    try:
        evolution = evolve_prompt()
        quality_trend = {
            "last10": repo.quality_trend(10, persist=True),
            "last30": repo.quality_trend(30, persist=True),
            "last100": repo.quality_trend(100, persist=True),
        }
        return {"ok": True, "evolution": evolution, "quality_trend": quality_trend}
    finally:
        _scheduler_lock.release()


def _scheduler_loop() -> None:
    while True:
        now = datetime.now()
        if now.hour == 5 and now.minute >= 30:
            run_brain_once()
        time.sleep(1800)


def start_brain_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    thread = threading.Thread(target=_scheduler_loop, daemon=True)
    thread.start()
