from __future__ import annotations

import html
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.beta_auth import current_user_id, current_user_role
from app.beta_mp4_usage import enforce_generation_access
from app.beta_title import clean_beta_title, persist_beta_job_title

beta_gemini_router = APIRouter(prefix="/beta-api/gemini", tags=["beta-gemini"])

CHANNEL_ORDER = [
    ("BLOG", "블로그"),
    ("NAVER_PLACE", "플레이스"),
    ("GOOGLE_BUSINESS", "구글"),
    ("INSTAGRAM", "인스타"),
    ("CARROT", "당근"),
    ("CAROUSEL_7", "카드뉴스"),
    ("PODCAST_50", "팟캐스트50s"),
    ("PODCAST_80", "팟캐스트80s"),
]
CHANNEL_KEYS = [key for key, _ in CHANNEL_ORDER]
CHANNEL_LABELS = dict(CHANNEL_ORDER)
MAIN_BLOCK_KEYS = [
    "BLOG_TITLES",
    "BLOG_POST",
    "NAVER_PLACE_NEWS",
    "GOOGLE_BUSINESS_POST",
    "BLOG_HASHTAGS",
    "CARROT_TITLES",
    "CARROT_POST",
    "CARROT_HASHTAGS",
    "INSTAGRAM_POST",
    "INSTAGRAM_HASHTAGS",
    "CAROUSEL_7",
    "PODCAST_50",
    "PODCAST_80",
]


class BetaGeminiRequest(BaseModel):
    business: dict[str, str] = Field(default_factory=dict)
    topic: str
    image_count: int = 8
    weather_snapshot: dict[str, Any] | None = None


class BetaPromptTemplateUpdate(BaseModel):
    prompt: str


PROMPT_TEMPLATE_PATH = Path(os.getenv("STORYMAKER_BETA_PROMPT_TEMPLATE", str(Path(os.getenv("STORYMAKER_BETA_ROOT", "/home/bourne/StoryMaker_1/StoryMaker_beta")) / "data" / "admin_prompt_template.md")))
PROMPT_REQUIRED_VARIABLES = ("{{company}}", "{{region}}", "{{service}}", "{{phone}}", "{{source_text}}", "{{weather_block}}")


def beta_gemini_model() -> str:
    return (os.getenv("BETA_GEMINI_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()


def beta_gemini_key() -> str:
    return (os.getenv("BETA_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()


def beta_deepseek_key() -> str:
    return (os.getenv("DEEPSEEK_API_KEY") or "").strip()


def beta_nvidia_key() -> str:
    return (os.getenv("NVIDIA_API_KEY") or "").strip()


def beta_deepseek_model() -> str:
    return (os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-flash").strip()


def beta_nemotron_model() -> str:
    return (os.getenv("NEMOTRON_MODEL") or "nvidia/nemotron-3-ultra-550b-a55b").strip()


def beta_fallback_enabled() -> bool:
    return (os.getenv("AI_FALLBACK_ENABLED") or "true").strip().lower() in {"1", "true", "yes", "on"}


LOGGER = logging.getLogger("storymaker-beta.ai-provider")


def _prompt_region(region: str) -> str:
    """마이페이지 상세 지역은 보존하고 Gemini 프롬프트에는 광역 지역만 전달한다."""
    raw = str(region or "").strip()
    if not raw:
        return "지역 미등록"

    first = raw.split()[0]
    aliases = {
        "서울특별시": "서울",
        "부산광역시": "부산",
        "대구광역시": "대구",
        "인천광역시": "인천",
        "광주광역시": "광주",
        "대전광역시": "대전",
        "울산광역시": "울산",
        "세종특별자치시": "세종",
        "제주특별자치도": "제주",
        "경기도": "경기",
        "강원특별자치도": "강원",
        "충청북도": "충북",
        "충청남도": "충남",
        "전북특별자치도": "전북",
        "전라북도": "전북",
        "전라남도": "전남",
        "경상북도": "경북",
        "경상남도": "경남",
    }
    return aliases.get(first, first)


def beta_build_default_prompt(payload: BetaGeminiRequest) -> str:
    business = payload.business or {}
    company = str(business.get("name", "")).strip() or "업체명 미등록"
    region = _prompt_region(business.get("region"))
    service = str(business.get("service", "")).strip() or "서비스 미등록"
    phone = str(business.get("phone", "")).strip() or "미등록"
    source_text = str(payload.topic or "").strip()

    weather = payload.weather_snapshot or {}
    if weather and weather.get("available"):
        obs_time = weather.get("observed_at") or ""
        obs_text = str(obs_time)
        if "T" in obs_text:
            try:
                dt_obs = datetime.fromisoformat(obs_text)
                obs_text = f"{dt_obs.year}년 {dt_obs.month}월 {dt_obs.day}일 {dt_obs.hour}시"
            except Exception:
                obs_text = obs_text.replace("T", " ").rsplit(":", 1)[0] + "시"
        weather_block = f"""## 현재 날짜·기상 기준 정보
- 기준 시간대: {weather.get('timezone', 'Asia/Seoul')}
- 현재 날짜: {weather.get('date_text', '')}
- 현재 요일: {weather.get('weekday_text', '')}
- 현재 시각: {weather.get('time_text', '')}
- 현재 계절: {weather.get('season', '')}
- 기상 기준 지역: {_prompt_region(weather.get('region') or region)}
- 현재 날씨: {weather.get('condition', '')}
- 현재 기온: {weather.get('temperature_c', '')}℃
- 현재 습도: {weather.get('humidity_percent', '')}%
- 강수 상태: {weather.get('precipitation_status', '')}
- 강수량: {weather.get('precipitation_mm', 0)}mm
- 기상 관측 기준 시각: {obs_text}"""
    else:
        weather_block = f"""## 현재 날짜·기상 기준 정보
- 기준 시간대: {weather.get('timezone', 'Asia/Seoul')}
- 현재 날짜: {weather.get('date_text', '')}
- 현재 요일: {weather.get('weekday_text', '')}
- 현재 시각: {weather.get('time_text', '')}
- 현재 계절: {weather.get('season', '')}
- 기상 기준 지역: {_prompt_region(weather.get('region') or region)}
- 기상 정보: 기상 서버 정보를 불러오지 못함 (날씨 항목 추정 금지)"""

    gemini_rule_block = """## Gemini 날짜·기상 절대 준수 규칙 (최우선 강제 적용)
- [현재 날짜·기상 기준 정보]에 기재된 날짜(연/월/일), 요일, 시각, 계절, 기상정보가 현재 작성 시점의 유일한 기준이다.
- 입력 원문(기초 내용)에 '7월 16일', '목요일 새벽' 등 과거 날짜/요일/시각 표현이 있더라도, 본문 서두나 도입부 인사말에서 결코 그대로 복사/인용하지 말 것.
- 입력 원문에 과거 날짜가 있더라도 현재 도입부 날짜·요일은 반드시 서버가 제공한 [현재 날짜]와 [현재 요일]로 새로 구성할 것.
- 현재 날씨 및 기온 정보도 서버 기준 정보만 사용하며 원문의 과거 날씨 표현은 완전히 무시한다.
- 기상정보가 미제공된 경우 날씨 관련 항목을 지어내지 않는다."""

    persona = "\n".join(
        part for part in [
            f"업체명: {company}",
            f"대표 지역: {region}",
            f"주요 서비스: {service}",
            f"대표 전화번호: {phone}",
        ]
        if part
    )
    block_spec = "\n\n".join([
        "[BLOCK:BLOG_TITLES]\n추천 블로그 제목 5개",
        "[BLOCK:BLOG_POST]\n네이버 블로그 포스팅 1개",
        "[BLOCK:NAVER_PLACE_NEWS]\n네이버 스마트플레이스 소식 게시글 1개",
        "[BLOCK:GOOGLE_BUSINESS_POST]\n구글 마이비즈니스 게시글 1개",
        "[BLOCK:BLOG_HASHTAGS]\n블로그 해시태그 1줄",
        "[BLOCK:CARROT_TITLES]\n당근마켓 제목 5개",
        "[BLOCK:CARROT_POST]\n당근마켓 게시글 1개",
        "[BLOCK:CARROT_HASHTAGS]\n당근마켓 해시태그 1줄",
        "[BLOCK:INSTAGRAM_POST]\n인스타그램 캡션 1개",
        "[BLOCK:INSTAGRAM_HASHTAGS]\n인스타그램 해시태그 1줄",
        "[BLOCK:CAROUSEL_7]\n카드뉴스 7장용 마크다운 1개",
        "[BLOCK:PODCAST_50]\n캐릭터 팟캐스트 대본 50초 버전 1개",
        "[BLOCK:PODCAST_80]\n캐릭터 팟캐스트 대본 80초 버전 1개",
    ])

    return f"""# 콘텐츠 통합 패키지 생성 프롬프트 v3.6-stable

## 역할
당신은 한국 소상공인의 실제 현장 자료를 채널별 완성 콘텐츠로 재구성하는 StoryMaker 전문 작가입니다.
광고보다 경험담을 우선하고, 과장·반복·AI식 문장 구조를 피합니다.

## StoryMaker 생성 환경
- 업체명: {company}
- 글쓰기 스타일: 현장감 있는 네이버 블로그
- 블로그 본문 목표 길이: 약 1500자
- 선택 지역: {region}
- 주요 서비스: {service}
- 전화번호: {phone}

{weather_block}

{gemini_rule_block}

## 최우선 반영 규칙
- 업체명, 전화번호, 업체 페르소나, 입력 자료를 가장 우선합니다.
- 원문에 없는 수치, 자격, 경력, 후기, 고객 반응, 원인, 효과, 공법, 작업 결과를 지어내지 않습니다.
- 참고자료의 타사명, 전화번호, 수치, 후기, 고유 표현은 직접 사용하지 않습니다.
- 블로그 UI 문구, 프로필, URL, 조회수, 통계, 접기·펴기 같은 화면 문구는 제외합니다.
- 실제 입력자료와 업체 페르소나가 언제나 최우선입니다.

## 작업 목표
입력된 한 현장 자료를 채널별 성격에 맞게 다시 써서 13개 콘텐츠 블록을 완성합니다.
블로그는 긴 현장 이야기, 플레이스는 짧은 현장 소식, 구글은 전문 서비스 안내, 인스타는 감성 캡션, 당근은 동네 이웃 글처럼 작성합니다.

## 반드시 생성할 결과물
아래 13개 BLOCK을 순서대로 모두 작성합니다.
제목 5개, 블로그 본문, 플레이스, 구글, 해시태그, 당근, 인스타, 카드뉴스, 팟캐스트 50초/80초를 누락하지 않습니다.

## 최상위 출력 규칙
- 출력은 하나의 코드블록 안에만 작성합니다.
- 코드블록 밖 설명, 사과, 누락 고백, 상태 문구는 금지합니다.
- 아래 BLOCK 이름과 순서를 그대로 지키고, 각 블록에는 실제 완성 콘텐츠만 작성합니다.
- [BLOCK:BLOG_POST] 본문은 약 1500자 분량으로 작성합니다.
- BLOG_POST 다음에는 NAVER_PLACE_NEWS, GOOGLE_BUSINESS_POST를 바로 이어서 작성합니다.
- INSTAGRAM_POST 다음에는 INSTAGRAM_HASHTAGS, CAROUSEL_7, PODCAST_50, PODCAST_80을 이어서 작성합니다.

```content
{block_spec}
```

## 모바일 가독성 규칙
BLOG_POST, CARROT_POST
- 문장이 끝나면 줄바꿈을 2번 넣습니다.
- 모바일 가독성을 최우선으로 합니다.
- 한 문단은 1~3문장 이내로 유지합니다.
- 한 줄은 22자 전후를 기준으로 작성합니다.
- 단어 중간에서 줄을 끊지 않습니다.

NAVER_PLACE_NEWS, GOOGLE_BUSINESS_POST
- 문단 전환 시에만 줄바꿈을 1회 적용합니다.
- 너무 많은 줄바꿈을 넣지 않습니다.
- 250~450자 안에서 제목, 문제, 해결, 신뢰 포인트를 간결하게 작성합니다.

INSTAGRAM_POST
- 짧은 문장 중심으로 감성 문단을 구성합니다.
- 이모지는 1개 이상 4개 이하로만 사용합니다.
- 마지막 연락 영역에 업체명 단독 줄과 전화번호 단독 줄을 반드시 넣습니다.
- 해시태그는 INSTAGRAM_HASHTAGS 블록에만 작성합니다.

CAROUSEL_7
- 총 7장으로 작성합니다.
- 각 장은 `## 제목` 1줄과 본문 2~4줄로 작성합니다.
- 각 장 구분은 반드시 `---` 한 줄만 사용합니다.

## 공통 및 SEO 작성 규칙
실제 현장 전문가가 경험을 이야기하듯 작성합니다.
본문에는 아래 요소 중 최소 2개 이상을 자연스럽게 포함합니다.
- 고객의 첫마디
- 현장 풍경
- 작업자의 생각
- 작업 후 고객 반응
- 생활 속 공감
- 계절감
- 현장의 소리
- 현장의 온도감

### 키워드 밀도 및 지역 SEO 규칙
- 본문 전체에서 `[선택 지역명 + 주요 서비스]` 및 `[지역명 + 세부 업종/작업명]` 키워드 조합을 자연스러운 문맥으로 3~5회 적절히 반복 배치합니다. (예: 음식점, 카페, 미용실, 집수리, 청소, 세차, 병원 등 해당 업종 키워드에 맞게 적용)
- 입력 자료에 언급된 동 이름, 아파트 단지명, 건물/상권 명칭(예: 삼산동, 야음동, 성남동, 00아파트 등)을 본문 도입부와 본문에 명확히 명시하여 지역 SEO를 극대화합니다.

### 모바일 가독성 및 볼드체(Bold) 강조 규칙
- 독자가 훑어보아도(Scanning) 핵심을 파악할 수 있도록 각 업종 성격에 맞게 아래 항목에 `**굵은 표시**`를 10회 이상 자연스럽게 적용합니다:
  1) 고객의 핵심 문제/고민/원인/특징 (예: **손상모 컬 처짐**, **에어컨 곰팡이 냄새**, **가스쇼바 압력 마모** 등 업종별 핵심)
  2) 전문가의 핵심 솔루션/제공 서비스/결과 (예: **고압 스팀 분해 세척**, **프랑스산 버터 100% 사용**, **수평 정교 조정 및 부드러운 고정**)

## 전화번호 및 하단 문의(CTA) 규칙
- BLOG_POST, CARROT_POST, INSTAGRAM_POST, CAROUSEL_7, PODCAST_50, PODCAST_80에는 전화번호를 말미에 반드시 1회 넣습니다.
- BLOG_POST 최하단 문의 영역에는 단순히 전화번호만 적지 않고, "지역(동/건물명)과 원하시는 서비스/현장 사진을 문자로 먼저 보내주시면 더욱 빠른 상담 및 안내가 가능합니다." 문구와 함께 전화번호를 배치합니다.
- NAVER_PLACE_NEWS, GOOGLE_BUSINESS_POST에는 전화번호를 넣지 않습니다.
- 자연스러운 문의 또는 방문 유도 문장으로 마무리합니다.
- 한 채널 안에서 전화번호는 최대 1회만 사용합니다.
- 전화번호가 없거나 '미등록'이면 임의로 전화번호를 생성하지 않습니다.
- 전화번호: {phone}

## 블로그 규칙 (SEO 제목 및 해시태그 최적화)
- BLOG_TITLES 5개 제목 및 BLOG_POST 첫 줄 제목은 검색량이 많은 메인 검색어(`[지역명] + [동/상권명] + [업종/주요서비스/핵심작업]`)를 최우선으로 전진 배치합니다.
  (예시: "울산 삼산동 미용실 레이어드 펌...", "울산 성남동 카페 수제 타르트...", "울산 야음동 현관문 처짐 수리...")
- 수식어나 불필요한 서두 표현보다 사용자가 네이버/구글 검색창에 직접 입력할 핵심 검색어를 앞세워 제목을 만듭니다.
- BLOG_POST 첫 줄은 반드시 `# 제목` 형식으로 시작합니다.
- 본문 소제목은 `## 소제목`만 사용합니다.
- `## 소제목`은 최소 4개 이상 사용합니다.
- 마지막 문단에는 읽어주셔서 진심으로 감사합니다라는 마음속에서 나오는 맺음말을 자연스럽게 넣습니다.
- BLOG_HASHTAGS에는 메인 작업 태그 외에도, 해당 업종의 연관 서비스/메뉴 태그를 2~3개 추가하여 유입 범위를 확대합니다.
- 블로그 해시태그는 BLOG_HASHTAGS 블록에서만 출력합니다.

## 반드시 생성할 결과물
아래 13개 BLOCK을 순서대로 모두 작성합니다.
제목 5개, 블로그 본문, 플레이스, 구글, 해시태그, 당근, 인스타, 카드뉴스, 팟캐스트 50초/80초를 누락하지 않습니다.

## 최상위 출력 규칙
- 출력은 하나의 코드블록 안에만 작성합니다.
- 코드블록 밖 설명, 사과, 누락 고백, 상태 문구는 금지합니다.
- 아래 BLOCK 이름과 순서를 그대로 지키고, 각 블록에는 실제 완성 콘텐츠만 작성합니다.
- [BLOCK:BLOG_POST] 본문은 약 1500자 분량으로 작성합니다.
- BLOG_POST 다음에는 NAVER_PLACE_NEWS, GOOGLE_BUSINESS_POST를 바로 이어서 작성합니다.
- INSTAGRAM_POST 다음에는 INSTAGRAM_HASHTAGS, CAROUSEL_7, PODCAST_50, PODCAST_80을 이어서 작성합니다.

```content
{block_spec}
```

## 모바일 가독성 규칙
BLOG_POST, CARROT_POST
- 문장이 끝나면 줄바꿈을 2번 넣습니다.
- 모바일 가독성을 최우선으로 합니다.
- 한 문단은 1~3문장 이내로 유지합니다.
- 한 줄은 22자 전후를 기준으로 작성합니다.
- 단어 중간에서 줄을 끊지 않습니다.

NAVER_PLACE_NEWS, GOOGLE_BUSINESS_POST
- 문단 전환 시에만 줄바꿈을 1회 적용합니다.
- 너무 많은 줄바꿈을 넣지 않습니다.
- 250~450자 안에서 제목, 문제, 해결, 신뢰 포인트를 간결하게 작성합니다.

INSTAGRAM_POST
- 짧은 문장 중심으로 감성 문단을 구성합니다.
- 이모지는 1개 이상 4개 이하로만 사용합니다.
- 마지막 연락 영역에 업체명 단독 줄과 전화번호 단독 줄을 반드시 넣습니다.
- 해시태그는 INSTAGRAM_HASHTAGS 블록에만 작성합니다.

CAROUSEL_7
- 총 7장으로 작성합니다.
- 각 장은 `## 제목` 1줄과 본문 2~4줄로 작성합니다.
- 각 장 구분은 반드시 `---` 한 줄만 사용합니다.

## 공통 작성 규칙
실제 현장 전문가가 경험을 이야기하듯 작성합니다.
본문에는 아래 요소 중 최소 2개 이상을 자연스럽게 포함합니다.
- 고객의 첫마디
- 현장 풍경
- 작업자의 생각
- 작업 후 고객 반응
- 생활 속 공감
- 계절감
- 현장의 소리
- 현장의 온도감

핵심 키워드는 `**굵은 표시**`를 10회 이상 자연스럽게 사용합니다.
무작위 단어를 강조하지 말고 지역 + 서비스, 핵심 작업, 문제 증상, 원인, 해결 방법을 우선합니다.

## 전화번호 규칙
- BLOG_POST, CARROT_POST, INSTAGRAM_POST, CAROUSEL_7, PODCAST_50, PODCAST_80에는 전화번호를 말미에 반드시 1회 넣습니다.
- NAVER_PLACE_NEWS, GOOGLE_BUSINESS_POST에는 전화번호를 넣지 않습니다.
- 자연스러운 문의 또는 방문 유도 문장으로 마무리합니다.
- 한 채널 안에서 전화번호는 최대 1회만 사용합니다.
- 전화번호가 없거나 '미등록'이면 임의로 전화번호를 생성하지 않습니다.
- 전화번호: {phone}

## 블로그 규칙
- BLOG_TITLES는 실제 제목 5개를 번호 목록으로 작성합니다.
- BLOG_POST 첫 줄은 반드시 `# 제목` 형식으로 시작합니다.
- 본문 소제목은 `## 소제목`만 사용합니다.
- `## 소제목`은 최소 4개 이상 사용합니다.
- 마지막 문단에는 읽어주셔서 진심으로 감사합니다라는 마음속에서 나오는 맺음말을 자연스럽게 넣습니다.
- 블로그 해시태그는 BLOG_HASHTAGS 블록에서만 출력합니다.

## 플레이스 규칙
- NAVER_PLACE_NEWS에는 네이버 스마트플레이스 소식에 바로 붙여넣을 수 있는 글을 작성합니다.
- 첫 줄은 플레이스용 짧은 현장 소식 제목으로 다시 씁니다.
- 해시태그는 넣지 않습니다.
- 현장 상황 → 원인 확인 → 해결 내용 → 짧은 문의 유도 순서로 작성합니다.

## 구글 규칙
- GOOGLE_BUSINESS_POST에는 구글 마이비즈니스 게시글에 바로 붙여넣을 수 있는 글을 작성합니다.
- 해시태그, 이모지, 과장된 평점 표현은 넣지 않습니다.
- 지역과 서비스 현장 → 문제 확인 → 원인 → 해결 방식 → 서비스 범위 순서로 정리합니다.
- 플레이스보다 더 차분하고 정보성 있게 작성합니다.

## 인스타그램 규칙
- INSTAGRAM_POST는 짧고 강한 문장 중심으로 작성합니다.
- 첫 2줄 안에 시선을 잡는 문장을 넣습니다.
- 마지막 연락 영역 형식은 반드시 아래 순서를 지킵니다.
  1) {company}
  2) {phone}
- INSTAGRAM_HASHTAGS 블록에만 해시태그를 작성합니다.

## 당근마켓 규칙
- CARROT_TITLES는 제목 5개를 작성합니다.
- CARROT_POST는 500자 이상 800자 이하로 작성합니다.
- 동네 이웃이 읽는 글처럼 친근하고 편안한 말투로 작성합니다.
- 마지막에는 "단골을 맺어두시면 새로운 소식을 가장 먼저 받아보실 수 있어요." 문장을 자연스럽게 포함합니다.
- 당근 해시태그는 CARROT_HASHTAGS 블록에서만 출력합니다.

## 팟캐스트 규칙
- PODCAST_50은 한국어 TTS 기준 약 320~380자입니다.
- PODCAST_80은 한국어 TTS 기준 약 350~420자입니다.
- 화자 태그는 `[여성]`, `[남성]`만 사용합니다.
- 화자 태그는 한 줄에 단독으로 작성합니다.
- 첫 문장은 여성 진행자가 시작합니다.
- 여성과 남성의 대화 턴은 최소 8회 이상으로 재치 있는 대화로 구성합니다.
- 실제 대화처럼 질문, 공감, 설명, 마무리가 오가게 작성합니다.
- 사용할 수 있는 표현 예시는 오~~, 아아!!, 하하~, 정말이요???, 어머머??, 음~~, 맞아요!! 같은 짧은 반응입니다.
- PODCAST_50에는 이런 톤 표현을 3회에서 4회 정도 사용합니다.
- PODCAST_80에는 이런 톤 표현을 3회에서 6회 정도 사용합니다.
- 마지막 멘트에 업체명과 전화번호를 읽기 쉬운 말투로 반드시 1회 넣습니다.

## 업체 정보
### 업체명
{company}

### 업체 페르소나
{persona}

## 입력 자료
### 기초내용 입력
{source_text}

## 핵심 키워드
- {region}
- {service}
- {company}
"""


def _prompt_section(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    end_index = text.find(end, start_index + len(start)) if start_index >= 0 else -1
    if start_index < 0 or end_index < 0:
        return ""
    return text[start_index:end_index].rstrip()


def beta_default_prompt_template() -> str:
    sentinels = {
        "name": "__SM_COMPANY__",
        "region": "__SM_REGION__",
        "service": "__SM_SERVICE__",
        "phone": "__SM_PHONE__",
    }
    sample = beta_build_default_prompt(BetaGeminiRequest(
        business=sentinels,
        topic="__SM_SOURCE_TEXT__",
        image_count=8,
        weather_snapshot=None,
    ))
    weather = _prompt_section(sample, "## 현재 날짜·기상 기준 정보", "## Gemini")
    if weather:
        sample = sample.replace(weather, "{{weather_block}}", 1)
    replacements = {
        "__SM_COMPANY__": "{{company}}",
        "__SM_REGION__": "{{region}}",
        "__SM_SERVICE__": "{{service}}",
        "__SM_PHONE__": "{{phone}}",
        "__SM_SOURCE_TEXT__": "{{source_text}}",
    }
    for old, new in replacements.items():
        sample = sample.replace(old, new)
    return sample


def beta_render_prompt_template(template: str, payload: BetaGeminiRequest) -> str:
    business = payload.business or {}
    default_prompt = beta_build_default_prompt(payload)
    weather = _prompt_section(default_prompt, "## 현재 날짜·기상 기준 정보", "## Gemini")
    values = {
        "{{company}}": str(business.get("name") or "업체명 미등록").strip(),
        "{{region}}": _prompt_region(business.get("region")),
        "{{service}}": str(business.get("service") or "서비스 미등록").strip(),
        "{{phone}}": str(business.get("phone") or "미등록").strip(),
        "{{source_text}}": str(payload.topic or "").strip(),
        "{{weather_block}}": weather,
    }
    rendered = str(template or "")
    for key, value in values.items():
        rendered = rendered.replace(key, value)
    return rendered.strip()


def beta_build_prompt(payload: BetaGeminiRequest) -> str:
    if PROMPT_TEMPLATE_PATH.exists():
        try:
            template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8").strip()
            if template:
                return beta_render_prompt_template(template, payload)
        except OSError:
            LOGGER.exception("admin prompt template read failed")
    return beta_build_default_prompt(payload)


def _require_prompt_admin(request: Request) -> None:
    if current_user_role(request) != "admin":
        raise HTTPException(status_code=403, detail="관리자만 프롬프트를 관리할 수 있습니다.")


@beta_gemini_router.get("/admin/prompt")
def beta_admin_prompt_get(request: Request) -> dict[str, Any]:
    _require_prompt_admin(request)
    saved = PROMPT_TEMPLATE_PATH.exists()
    prompt = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8") if saved else beta_default_prompt_template()
    return {"ok": True, "prompt": prompt, "saved": saved, "required_variables": list(PROMPT_REQUIRED_VARIABLES)}


@beta_gemini_router.put("/admin/prompt")
def beta_admin_prompt_update(payload: BetaPromptTemplateUpdate, request: Request) -> dict[str, Any]:
    _require_prompt_admin(request)
    prompt = str(payload.prompt or "").strip()
    if len(prompt) < 500:
        raise HTTPException(status_code=422, detail="프롬프트 내용이 너무 짧습니다.")
    missing = [name for name in PROMPT_REQUIRED_VARIABLES if name not in prompt]
    if missing:
        raise HTTPException(status_code=422, detail="필수 변수가 누락되었습니다: " + ", ".join(missing))
    PROMPT_TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = PROMPT_TEMPLATE_PATH.with_suffix(".md.tmp")
    temp_path.write_text(prompt + "\n", encoding="utf-8")
    temp_path.replace(PROMPT_TEMPLATE_PATH)
    return {"ok": True, "saved": True, "size": len(prompt), "required_variables": list(PROMPT_REQUIRED_VARIABLES)}


def beta_extract_text(response: dict[str, Any]) -> str:
    try:
        parts = response["candidates"][0]["content"]["parts"]
        return "".join(str(part.get("text", "")) for part in parts).strip()
    except (KeyError, IndexError, TypeError):
        raise ValueError("Gemini 응답에서 텍스트를 찾지 못했습니다.")


def beta_extract_json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?", "", str(text or ""), flags=re.I).replace("```", "").strip()
    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    for match in re.finditer(r"\{", cleaned):
        try:
            value, _ = decoder.raw_decode(cleaned[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append(value)
    flat_key_map = {
        "blog": "BLOG",
        "naver_place": "NAVER_PLACE",
        "google_business": "GOOGLE_BUSINESS",
        "instagram": "INSTAGRAM",
        "carrot": "CARROT",
        "carousel_7": "CAROUSEL_7",
        "podcast_50": "PODCAST_50",
        "podcast_80": "PODCAST_80",
    }
    for candidate in reversed(candidates):
        channels = candidate.get("channels")
        if isinstance(channels, dict) and all(str(channels.get(key) or "").strip() for key in CHANNEL_KEYS):
            return candidate

        flat_channels = {
            channel_key: candidate.get(flat_key)
            for flat_key, channel_key in flat_key_map.items()
        }
        if all(str(flat_channels.get(key) or "").strip() for key in CHANNEL_KEYS):
            normalized = dict(candidate)
            normalized["channels"] = flat_channels
            normalized["thumbnail_prompt"] = (
                normalized.get("thumbnail_prompt")
                or normalized.get("THUMBNAIL_PROMPT")
                or ""
            )
            return normalized
    raise ValueError("AI 응답에서 유효한 SNS 8채널 JSON을 찾지 못했습니다.")




def beta_extract_blocks(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"```(?:text|markdown|json)?", "", str(text or ""), flags=re.I).replace("```", "").strip()
    names = ["TITLE", "DESCRIPTION", *CHANNEL_KEYS, *MAIN_BLOCK_KEYS, "THUMBNAIL_PROMPT"]
    found: dict[str, str] = {}

    # Gemini가 [BLOCK:NAME], [BLOCK : NAME], ## BLOCK:NAME처럼 조금 다르게
    # 출력해도 동일한 블록으로 인식한다.
    tag_pattern = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?\[?\s*BLOCK\s*[:：]\s*("
        + "|".join(re.escape(name) for name in names)
        + r")\s*\]?\s*$"
    )
    matches = list(tag_pattern.finditer(cleaned))
    for index, match in enumerate(matches):
        name = match.group(1).upper()
        body_start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        body = cleaned[body_start:end].strip()
        if body:
            found[name] = body

    if all(found.get(key) for key in CHANNEL_KEYS):
        return {
            "title": found.get("TITLE", "").strip(),
            "description": found.get("DESCRIPTION", "").strip(),
            "channels": {key: found[key] for key in CHANNEL_KEYS},
            "thumbnail_prompt": found.get("THUMBNAIL_PROMPT", "").strip(),
        }
    if all(found.get(key) for key in MAIN_BLOCK_KEYS):
        blog = "\n\n".join(
            part for part in [
                found.get("BLOG_TITLES", "").strip(),
                found.get("BLOG_POST", "").strip(),
                found.get("BLOG_HASHTAGS", "").strip(),
            ]
            if part
        ).strip()
        instagram = "\n\n".join(
            part for part in [
                found.get("INSTAGRAM_POST", "").strip(),
                found.get("INSTAGRAM_HASHTAGS", "").strip(),
            ]
            if part
        ).strip()
        carrot = "\n\n".join(
            part for part in [
                found.get("CARROT_TITLES", "").strip(),
                found.get("CARROT_POST", "").strip(),
                found.get("CARROT_HASHTAGS", "").strip(),
            ]
            if part
        ).strip()
        return {
            "title": found.get("TITLE", "").strip() or found.get("BLOG_TITLES", "").splitlines()[0].strip(),
            "description": found.get("DESCRIPTION", "").strip() or found.get("NAVER_PLACE_NEWS", "").splitlines()[0].strip(),
            "channels": {
                "BLOG": blog,
                "NAVER_PLACE": found["NAVER_PLACE_NEWS"],
                "GOOGLE_BUSINESS": found["GOOGLE_BUSINESS_POST"],
                "INSTAGRAM": instagram,
                "CARROT": carrot,
                "CAROUSEL_7": found["CAROUSEL_7"],
                "PODCAST_50": found["PODCAST_50"],
                "PODCAST_80": found["PODCAST_80"],
            },
            "source_blocks": {key: found[key] for key in MAIN_BLOCK_KEYS},
            "thumbnail_prompt": found.get("THUMBNAIL_PROMPT", "").strip(),
        }
    missing = [key for key in CHANNEL_KEYS if not found.get(key)]
    missing_main = [key for key in MAIN_BLOCK_KEYS if not found.get(key)]
    raise ValueError(
        "Gemini 응답에서 Beta 8채널 또는 본판 13개 BLOCK을 찾지 못했습니다. "
        + "8채널 누락: "
        + ", ".join(missing)
        + " / 13블록 누락: "
        + ", ".join(missing_main)
    )


def _inline_html(text: str) -> str:
    escaped = html.escape(str(text or ""), quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<strong>\1</strong>", escaped)
    return escaped


def beta_channel_rich_format(key: str, content: str) -> tuple[str, list[dict[str, str]]]:
    """채널 원문을 네이버 블로그 붙여넣기용 인라인 HTML과 구조화 블록으로 변환합니다."""
    lines = str(content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[dict[str, str]] = []
    html_parts: list[str] = []

    def esc(value: str) -> str:
        import html
        return html.escape(value, quote=False)

    def inline_bold(value: str) -> str:
        safe = esc(value)
        return re.sub(
            r"\*\*(.+?)\*\*",
            r'<strong style="font-weight:700;color:#111111;">\1</strong>',
            safe,
        )

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        normalized = re.sub(r"\s+", " ", line).strip()
        divider = bool(re.fullmatch(r"[-_=·•─━]{3,}", normalized))
        if divider:
            blocks.append({"type": "divider", "text": ""})
            html_parts.append('<div style="height:1px;background:#d9d9d9;margin:28px 0;"></div>')
            continue

        if normalized in {"본문", "블로그 본문", "추천 제목 5개", "추천 제목", "해시태그", "상담 안내"}:
            if normalized in {"본문", "블로그 본문"} and html_parts:
                blocks.append({"type": "divider", "text": ""})
                html_parts.append('<div style="height:1px;background:#d9d9d9;margin:30px 0;"></div>')
            blocks.append({"type": "heading", "text": normalized})
            html_parts.append(
                f'<p style="margin:26px 0 14px;font-size:24px;line-height:1.55;font-weight:700;color:#111111;">{esc(normalized)}</p>'
            )
            continue

        heading_level = 0
        heading_text = normalized
        if normalized.startswith("### "):
            heading_level = 3
            heading_text = normalized[4:].strip()
        elif normalized.startswith("## "):
            heading_level = 2
            heading_text = normalized[3:].strip()
        elif normalized.startswith("# "):
            heading_level = 2
            heading_text = normalized[2:].strip()
        elif normalized.startswith("**") and normalized.endswith("**") and len(normalized) > 4:
            heading_level = 3
            heading_text = normalized[2:-2].strip()
        elif key not in {"PODCAST_50", "PODCAST_80"} and len(normalized) <= 34 and not normalized.endswith((".", "다.", "요.", "니다.")):
            heading_level = 3

        if heading_level:
            blocks.append({"type": "heading", "text": heading_text})
            size = 24 if heading_level == 2 else 20
            margin_top = 30 if heading_level == 2 else 24
            html_parts.append(
                f'<p style="margin:{margin_top}px 0 12px;font-size:{size}px;line-height:1.55;font-weight:700;color:#111111;">{inline_bold(heading_text)}</p>'
            )
            continue

        if key in {"PODCAST_50", "PODCAST_80"} and re.match(r"^(여자|남자)\s*:", normalized):
            speaker, body = normalized.split(":", 1)
            blocks.append({"type": "dialogue", "text": normalized})
            html_parts.append(
                '<p style="margin:0 0 12px;font-size:17px;line-height:1.9;color:#222222;">'
                f'<strong style="font-weight:700;color:#111111;">{esc(speaker)}:</strong> {inline_bold(body.strip())}</p>'
            )
            continue
        if key in {"PODCAST_50", "PODCAST_80"} and re.fullmatch(r"\[(여성|남성)\]", normalized):
            blocks.append({"type": "speaker", "text": normalized})
            html_parts.append(
                f'<p style="margin:14px 0 6px;font-size:17px;line-height:1.8;color:#111111;font-weight:700;">{esc(normalized)}</p>'
            )
            continue

        blocks.append({"type": "paragraph", "text": normalized})
        html_parts.append(
            f'<p style="margin:0 0 18px;font-size:17px;line-height:1.95;color:#222222;word-break:keep-all;">{inline_bold(normalized)}</p>'
        )

    wrapper = (
        '<div style="font-family:Arial,Malgun Gothic,sans-serif;color:#222222;background:#ffffff;">'
        + "".join(html_parts)
        + "</div>"
    )
    return wrapper, blocks


def beta_parse_content(text: str, image_count: int) -> dict[str, Any]:
    try:
        data = beta_extract_json_object(text)
    except ValueError:
        data = beta_extract_blocks(text)
    raw_channels = data.get("channels")
    if not isinstance(raw_channels, dict):
        raise ValueError("Gemini 결과에 channels 객체가 필요합니다.")
    channels: dict[str, dict[str, Any]] = {}
    for key, label in CHANNEL_ORDER:
        value = raw_channels.get(key)
        if isinstance(value, dict):
            value = value.get("content") or value.get("text") or value.get("script") or ""
        content = str(value or "").strip()
        if not content:
            raise ValueError(f"{key} 채널 내용이 비어 있습니다.")
        rich_html, blocks = beta_channel_rich_format(key, content)
        channels[key] = {"key": key, "label": label, "content": content, "html": rich_html, "blocks": blocks}
    podcast_50 = channels["PODCAST_50"]["content"]
    podcast_80 = channels["PODCAST_80"]["content"]
    return {
        "title": str(data.get("title", "")).strip(),
        "description": str(data.get("description", "")).strip(),
        "channels": channels,
        "channel_order": CHANNEL_KEYS,
        "source_blocks": data.get("source_blocks", {}),
        "podcast_50": podcast_50,
        "podcast_80": podcast_80,
        "podcast_script": podcast_50,
        "script": podcast_50,
        "thumbnail_prompt": str(data.get("thumbnail_prompt", "")).strip(),
        "provider": "gemini",
        "model": beta_gemini_model(),
    }


def beta_call_gemini_only(payload: BetaGeminiRequest) -> dict[str, Any]:
    key = beta_gemini_key()
    if not key:
        raise HTTPException(status_code=503, detail="Beta 전용 Gemini API 키가 설정되지 않았습니다.")
    model = beta_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": beta_build_prompt(payload)}]}],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 16000,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise HTTPException(status_code=502, detail=f"Gemini API 오류 {exc.code}: {detail}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini 연결 실패: {exc}")
    content = beta_parse_content(beta_extract_text(raw), payload.image_count)
    content["provider"] = "gemini"
    content["model"] = model
    return content


def beta_extract_openai_text(response: dict[str, Any], provider: str) -> str:
    try:
        value = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"{provider} 응답에서 텍스트를 찾지 못했습니다.")
    if isinstance(value, list):
        value = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in value)
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{provider} 응답이 비어 있습니다.")
    return text


def beta_call_openai_provider(
    payload: BetaGeminiRequest,
    *,
    provider: str,
    url: str,
    key: str,
    model: str,
) -> dict[str, Any]:
    if not key:
        raise RuntimeError(f"{provider} API 키가 설정되지 않았습니다.")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": beta_build_prompt(payload)}],
        "temperature": 0.5,
        "max_tokens": 12000,
        "stream": False,
    }
    if provider == "deepseek":
        body["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"{provider} API 오류 {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"{provider} 연결 실패: {exc}") from exc
    content = beta_parse_content(beta_extract_openai_text(raw, provider), payload.image_count)
    content["provider"] = provider
    content["model"] = model
    return content


def beta_call_deepseek(payload: BetaGeminiRequest) -> dict[str, Any]:
    return beta_call_openai_provider(
        payload,
        provider="deepseek",
        url="https://api.deepseek.com/chat/completions",
        key=beta_deepseek_key(),
        model=beta_deepseek_model(),
    )


def beta_call_nemotron(payload: BetaGeminiRequest) -> dict[str, Any]:
    return beta_call_openai_provider(
        payload,
        provider="nemotron",
        url=(os.getenv("NVIDIA_API_BASE") or "https://integrate.api.nvidia.com/v1").rstrip("/") + "/chat/completions",
        key=beta_nvidia_key(),
        model=beta_nemotron_model(),
    )


def beta_call_ai(payload: BetaGeminiRequest) -> dict[str, Any]:
    providers = [("gemini", beta_call_gemini_only)]
    if beta_fallback_enabled():
        providers.extend([("nemotron", beta_call_nemotron), ("deepseek", beta_call_deepseek)])
    failures: list[str] = []
    for provider, caller in providers:
        started = time.monotonic()
        try:
            result = caller(payload)
            LOGGER.info("AI provider success provider=%s elapsed_ms=%d", provider, int((time.monotonic() - started) * 1000))
            result["fallback_attempts"] = failures.copy()
            return result
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            message = str(getattr(exc, "detail", exc))[:500]
            failures.append(f"{provider}: {message}")
            LOGGER.warning("AI provider failed provider=%s elapsed_ms=%d reason=%s", provider, elapsed_ms, message)
    raise HTTPException(status_code=502, detail="모든 AI Provider 호출이 실패했습니다. " + " | ".join(failures))


@beta_gemini_router.get("/status")
def beta_gemini_status() -> dict[str, Any]:
    return {
        "ok": True,
        "fallback_enabled": beta_fallback_enabled(),
        "providers": {
            "gemini": {"configured": bool(beta_gemini_key()), "model": beta_gemini_model()},
            "deepseek": {"configured": bool(beta_deepseek_key()), "model": beta_deepseek_model()},
            "nemotron": {"configured": bool(beta_nvidia_key()), "model": beta_nemotron_model()},
        },
        "key_exposed": False,
    }


@beta_gemini_router.post("/generate")
def beta_gemini_generate(payload: BetaGeminiRequest, request: Request) -> dict[str, Any]:
    enforce_generation_access(current_user_id(request), current_user_role(request))
    return {"ok": True, "content": beta_call_ai(payload)}


@beta_gemini_router.post("/jobs/{beta_job_id}/generate")
def beta_gemini_generate_for_job(beta_job_id: str, request: Request) -> dict[str, Any]:
    enforce_generation_access(current_user_id(request), current_user_role(request))
    if not beta_job_id.startswith("beta_") or any(ch not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-" for ch in beta_job_id):
        raise HTTPException(status_code=400, detail="잘못된 Beta 작업 ID입니다.")
    job_dir = Path(os.getenv("STORYMAKER_BETA_ROOT", "/home/bourne/StoryMaker_1/StoryMaker_beta")) / "data" / "jobs" / beta_job_id
    result_path = job_dir / "result.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Beta 작업을 찾을 수 없습니다.")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    payload = BetaGeminiRequest(
        business=result.get("business", {}),
        topic=result.get("topic", ""),
        image_count=max(1, len(result.get("assets", {}).get("images", []))),
        weather_snapshot=result.get("weather_snapshot"),
    )
    content = beta_call_ai(payload)
    cleaned_title = clean_beta_title(content.get("title") or result.get("title"), result.get("title") or "Beta 제작")
    content["title"] = cleaned_title
    result["content"] = content
    result["title"] = cleaned_title
    result["gemini"] = {
        "provider": content.get("provider", "gemini"),
        "model": content.get("model", beta_gemini_model()),
        "applied": True,
        "fallback_attempts": content.get("fallback_attempts", []),
    }
    channels_dir = job_dir / "channels"
    channels_dir.mkdir(parents=True, exist_ok=True)
    for key in content["channel_order"]:
        channel = content["channels"][key]
        (channels_dir / f"{key}.txt").write_text(channel["content"] + "\n", encoding="utf-8")
        (channels_dir / f"{key}.html").write_text(str(channel.get("html") or ""), encoding="utf-8")
    (job_dir / "podcast_50.txt").write_text(content["podcast_50"], encoding="utf-8")
    (job_dir / "podcast_80.txt").write_text(content["podcast_80"], encoding="utf-8")
    script = content["podcast_50"]
    (job_dir / "script.txt").write_text(script, encoding="utf-8")
    (job_dir / "podcast_script.txt").write_text(script, encoding="utf-8")
    thumbnail_prompt = str(content.get("thumbnail_prompt") or "").strip()
    if thumbnail_prompt:
        (job_dir / "thumbnail_prompt.md").write_text(thumbnail_prompt + "\n", encoding="utf-8")
    tmp = result_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(result_path)
    persist_beta_job_title(job_dir.parent.parent / "storymaker_beta.db", beta_job_id, cleaned_title)
    return {"ok": True, "job": result}
