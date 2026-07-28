# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드용 prompt_builder 모듈
"""
import json
import os
import re
import sqlite3
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from app.settings import settings
from app.core.region_display import format_region_display, format_region_text
from app.services.weather_cache_service import get_or_fetch_weather


KST = ZoneInfo("Asia/Seoul")
WORKSPACE_ROOT = Path("/workspace")
WEATHER_DIR_CANDIDATES = [
    WORKSPACE_ROOT / "Weather",
    Path("/home/bourne/Weather"),
]
WEATHER_PYTHON_CANDIDATES = [
    Path("/home/bourne/Weather/.venv/bin/python"),
    WORKSPACE_ROOT / "Weather" / ".venv" / "bin" / "python",
    Path("python3"),
]

REGION_WEATHER_QUERY_MAP = {
    "서울": "서울특별시",
    "인천": "인천광역시",
    "경기": "경기도 수원시",
    "강원": "강원도 춘천시",
    "대전": "대전광역시",
    "충청": "충청북도 청주시",
    "광주": "광주광역시",
    "전라": "전라북도 전주시",
    "대구": "대구광역시",
    "경북": "경상북도 안동시",
    "부산": "부산광역시",
    "울산": "울산광역시",
    "경남": "경상남도 창원시",
    "제주": "제주특별자치도 제주시",
    "양양": "강원도 양양군",
    "인천광역시 강화군 강화읍": "인천광역시 강화군 강화읍",
    "인천광역시 강화군 불은면": "인천광역시 강화군 불은면",
    "울산광역시 울주군 언양읍": "울산광역시 울주군 언양읍",
    "울산광역시 울주군 서생면": "울산광역시 울주군 서생면",
    "경기도 남양주시 진접읍": "경기도 남양주시 진접읍",
    "경기도 하남시 미사1동": "경기도 하남시 미사1동",
}

REGION_SUBAREAS_MAP = {
    "서울": "강남구, 서초구, 송파구, 마포구, 용산구, 성동구, 영등포구, 강서구, 종로구, 성북구, 마포구 공덕동, 영등포구 여의도동, 마포구 상암동",
    "인천": "부평구, 남동구, 연수구, 미추홀구, 서구, 계양구, 연수구 송도동, 서구 청라동, 남동구 구월동, 부평구 부평동",
    "경기": "수원시, 성남시 분당구, 일산동구, 고양시, 용인시, 부천시, 안산시, 안양시, 화성시 동탄, 평택시, 김포시",
    "강원": "춘천시, 원주시, 강릉시, 동해시, 속초시, 삼척시, 홍천군, 평창군, 강릉시 포남동, 춘천시 퇴계동",
    "대전": "서구, 유성구, 중구, 동구, 대덕구, 서구 둔산동, 유성구 신성동, 중구 은행동",
    "충청": "천안시, 아산시, 청주시, 충주시, 제천시, 서산시, 당진시, 공주시, 세종시, 천안시 불당동, 청주시 복대동",
    "광주": "북구, 광산구, 서구, 남구, 동구, 서구 상무지구, 광산구 수완동, 남구 봉선동",
    "전라": "전주시 완산구, 전주시 덕진구, 익산시, 군산시, 여수시, 순천시, 목포시, 광양시, 전주시 효자동, 여수시 학동",
    "대구": "수성구, 달서구, 북구, 동구, 서구, 남구, 중구, 수성구 범어동, 달서구 상인동, 동구 신천동",
    "경북": "포항시 남구, 포항시 북구, 구미시, 경주시, 안동시, 경산시, 김천시, 포항시 이동, 경주시 황성동",
    "부산": "해운대구, 부산진구, 동래구, 금정구, 연제구, 수영구, 남구, 사상구, 사하구, 부산진구 서면, 해운대구 센텀시티, 해운대구 마린시티",
    "울산": "북구, 호계동, 매곡동, 송정동, 연암동, 천곡동, 화봉동, 남구, 중구, 울주군, 동구",
    "경남": "창원시 의창구, 창원시 성산구, 창원시 마산회원구, 창원시 마산합포구, 창원시 진해구, 김해시, 양산시, 진주시, 거제시, 통영시",
    "제주": "제주시, 서귀포시, 제주시 애월읍, 제주시 연동, 제주시 노형동, 제주시 이도동, 제주시 아라동, 서귀포시 영어교육도시",
    "양양": "양양읍, 서면, 현북면, 현남면, 강현면, 손양면, 현북면 하조대, 강현면 낙산",
}

WEATHER_STATE_KO_MAP = {
    "clear-night": "맑음",
    "cloudy": "흐림",
    "fog": "안개",
    "hail": "우박",
    "lightning": "번개",
    "lightning-rainy": "뇌우",
    "partlycloudy": "구름많음",
    "pouring": "강한 비",
    "rainy": "비",
    "snowy": "눈",
    "snowy-rainy": "비 또는 눈",
    "sunny": "맑음",
    "windy": "바람",
    "windy-variant": "강한 바람",
    "exceptional": "기상 특이사항",
}

DEFAULT_HA_WEATHER_ENTITY_ID = "weather.naver_weather_hanamsi_nalssi_hanamsi"
DEFAULT_WEATHER_TOOL_URL = "http://host.docker.internal:8010/weather_json"
DEFAULT_FOOTER_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
FOOTER_WEATHER_REGION_MAP = {"서울": ("서울", 37.5665, 126.9780), "부산": ("부산", 35.1796, 129.0756), "울산": ("울산", 35.5384, 129.3114), "대구": ("대구", 35.8714, 128.6014), "대전": ("대전", 36.3504, 127.3845), "광주": ("광주", 35.1595, 126.8526), "인천": ("인천", 37.4563, 126.7052), "제주": ("제주", 33.4996, 126.5312), "경기": ("수원", 37.2636, 127.0286), "강원": ("춘천", 37.8813, 127.7298)}
FOOTER_WEATHER_CODE_MAP = {0: "맑음", 1: "대체로 맑음", 2: "부분적으로 흐림", 3: "흐림", 61: "비", 63: "비", 65: "강한 비", 71: "눈", 73: "눈", 75: "강한 눈", 80: "소나기", 81: "소나기", 82: "강한 소나기", 95: "뇌우"}
REGION_ALIAS_MAP = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전북특별자치도": "전북", "전라북도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주",
}
REGION_NOISE_WORDS = {
    "하수구", "배수구", "싱크대", "욕실", "화장실", "변기", "반드시", "가능하면", "조심하시", "보내시", "생각하면",
    "울산하수구", "울산배관내시", "내시경검사", "고압세척", "배관내시", "문의하시", "확인하시",
}


def normalize_region_alias(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    compact = re.sub(r"\s+", "", raw)
    if compact in REGION_ALIAS_MAP:
        return REGION_ALIAS_MAP[compact]
    return format_region_display(raw)


def build_region_lookup_candidates(region: str) -> list[str]:
    base = str(region or "").strip()
    normalized = normalize_region_alias(base)
    variants = [base, normalized]
    for full, short in REGION_ALIAS_MAP.items():
        if base == full or normalized == short or base == short:
            variants.extend([short, full])
    result: list[str] = []
    for item in variants:
        item = str(item or "").strip()
        if item and item not in result:
            result.append(item)
    return result or [base]


def build_preset_header(ai_preset: str) -> str:
    preset = (ai_preset or "").strip().lower()
    if preset == "chatgpt":
        return "당신은 지역 기반 소상공인 콘텐츠 패키지를 한 번에 정확하게 생성하는 전문 콘텐츠 작가입니다. 반드시 모든 항목을 빠짐없이 생성하세요."
    if preset == "gemini":
        return "당신은 지역 소상공인 브랜딩, 네이버 SEO, 실전형 콘텐츠 작성에 강한 콘텐츠 제작자입니다. 지정된 모든 항목을 완성형으로 출력하세요."
    if preset == "claude":
        return "당신은 사람 냄새 나는 서사와 실용 정보를 동시에 살리는 콘텐츠 작가입니다. 구조화된 결과물을 완성형으로 출력하세요."
    return "당신은 입력된 자료를 빠짐없이 반영해 통합 콘텐츠 패키지를 생성하는 AI 작성 도우미입니다."


def build_style_guidance(style: str) -> str:
    guides = {
        "스토리형": "문제 발생 → 현장 확인 → 원인 분석 → 해결 → 마무리 흐름으로 작성합니다.",
        "정보형": "유용한 팁, 절차, 체크리스트 중심으로 작성합니다.",
        "설득형": "고객의 문제를 짚고 우리 서비스가 해답인 이유를 설득력 있게 작성합니다.",
        "대화형": "독자와 이야기하듯 친근하고 편안하게 작성합니다.",
        "뉴스형": "핵심 요약과 객관적 정보 전달 중심으로 작성합니다.",
    }
    return guides.get((style or "").strip(), "현장 사례 중심으로 친근하고 설득력 있게 작성합니다.")


def build_emotion_weight_guidance(selected_emotions: list[str], emotion_map: dict) -> str:
    """선택 감성은 강하게, 미선택 감성은 보조 톤으로 낮게 표시합니다."""
    selected = [emotion for emotion in selected_emotions if emotion in emotion_map]
    lines = []
    for emotion in emotion_map.keys():
        if emotion in selected:
            stars = "★★★★★"
            prefix = "주요 감성"
        elif emotion == "친근함":
            stars = "★★☆☆☆"
            prefix = "보조 감성"
        else:
            stars = "★☆☆☆☆"
            prefix = "배경 감성"
        lines.append(f"- {emotion} {stars} ({prefix}): {emotion_map[emotion]}")
    return "\n".join(lines)


def _format_industry_template_row(row) -> str:
    """DB 업종 템플릿 1개 행을 프롬프트 블록 문자열로 변환합니다."""
    label = str(row["label"] or "업종 미지정").strip()
    category = str(row["category"] or "기타").strip()
    prompt_guidance = str(row["prompt_guidance"] or "").strip()
    content_flow = str(row["content_flow"] or "").strip()
    keyword_hint = str(row["keyword_hint"] or "").strip()
    tone_hint = str(row["tone_hint"] or "").strip()
    avoid_hint = str(row["avoid_hint"] or "").strip()

    lines = [
        f"업종: {label}",
        f"업종 분류: {category}",
    ]
    if content_flow:
        lines.append(f"작성 흐름: {content_flow}")
    if prompt_guidance:
        lines.append("핵심 포인트:")
        lines.append(f"- {prompt_guidance}")
    if keyword_hint:
        lines.append(f"키워드 힌트: {keyword_hint}")
    if tone_hint:
        lines.append(f"문체 힌트: {tone_hint}")
    if avoid_hint:
        lines.append(f"피해야 할 표현: {avoid_hint}")
    return "\n".join(lines)


def _fetch_industry_guidance_from_db(industry_key: str) -> str:
    """industry_prompt_templates 테이블에서 활성 업종 프롬프트를 조회합니다. 실패 시 빈 문자열을 반환합니다."""
    key = (industry_key or "general").strip() or "general"
    try:
        db_path = str(settings.STORYMAKER_DB_PATH)
        with sqlite3.connect(db_path, timeout=2) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT label, category, prompt_guidance, content_flow, keyword_hint, tone_hint, avoid_hint
                FROM industry_prompt_templates
                WHERE industry_key = ? AND is_active = 1
                LIMIT 1
                """,
                (key,),
            ).fetchone()
            if row:
                return _format_industry_template_row(row)
            if key != "general":
                fallback = conn.execute(
                    """
                    SELECT label, category, prompt_guidance, content_flow, keyword_hint, tone_hint, avoid_hint
                    FROM industry_prompt_templates
                    WHERE industry_key = 'general' AND is_active = 1
                    LIMIT 1
                    """
                ).fetchone()
                if fallback:
                    return _format_industry_template_row(fallback)
    except Exception:
        return ""
    return ""


def build_industry_guidance(industry_key: str = "general") -> str:
    """
    업종별 작성 흐름을 반환합니다.
    1순위: DB industry_prompt_templates
    2순위: 코드 내 기본 fallback
    """
    db_guidance = _fetch_industry_guidance_from_db(industry_key)
    if db_guidance:
        return db_guidance

    guides = {
        "home_repair": """업종: 집수리/인테리어
작성 흐름: 고객 불편 → 현장 방문 → 원인 진단 → 작업 과정 → 결과 → 관리 팁 → 브랜드 마무리
핵심 포인트:
- 문제 증상, 원인, 안전 확인, 작업 결과를 구체적으로 작성합니다.
- 단순 홍보보다 실제 현장 해결 과정을 중심에 둡니다.
- 전기, 누수, 욕실, 도배, 장판, 조명 등 서비스별 핵심 키워드를 자연스럽게 반영합니다.""",
        "restaurant": """업종: 음식점
작성 흐름: 계절감 → 메뉴 소개 → 식재료 → 조리 과정 → 맛 표현 → 손님 반응 → 재방문 유도
핵심 포인트:
- 현장 수리 표현 대신 음식, 온도, 향, 식감, 손님 분위기를 중심으로 작성합니다.
- 메뉴명, 지역명, 식사 상황, 방문 이유를 자연스럽게 연결합니다.
- 과장된 맛 표현보다 실제 손님이 느낄 만한 경험을 우선합니다.""",
        "cafe": """업종: 카페
작성 흐름: 공간 분위기 → 향 → 음료 → 디저트 → 머무는 시간 → 감성 마무리
핵심 포인트:
- 커피 향, 좌석, 조명, 대화, 여유 같은 감각적 요소를 살립니다.
- 사진으로 떠올릴 수 있는 공간 묘사를 짧게 넣습니다.
- 방문 이유와 재방문 포인트를 자연스럽게 제안합니다.""",
        "camping": """업종: 캠핑장
작성 흐름: 도착 → 풍경 → 시설 → 체험 → 야경 → 추억 → 예약 유도
핵심 포인트:
- 계절, 날씨, 자연 풍경, 가족·연인·친구 체험을 중심으로 작성합니다.
- 시설 안내는 딱딱한 목록보다 이용 장면으로 풀어냅니다.
- 방문 후 남는 감정과 추억을 자연스럽게 강조합니다.""",
        "logistics": """업종: 물류/3PL
작성 흐름: 입고 → 보관 → 포장 → 출고 → 배송 안정성 → 고객사 효율
핵심 포인트:
- 정확성, 오배송 감소, 출고 속도, 재고 관리, 비용 효율을 중심으로 작성합니다.
- 감성보다 신뢰, 시스템, 운영 안정성을 우선합니다.
- 쇼핑몰 운영자가 겪는 현실적인 문제와 해결 효과를 연결합니다.""",
        "general": """업종: 일반 소상공인
작성 흐름: 문제 상황 → 해결 과정 → 결과 → 고객 가치 → 마무리
핵심 포인트:
- 입력자료와 업체 페르소나를 우선하여 업종에 맞게 유연하게 작성합니다.
- 특정 업종 표현을 억지로 끼워 넣지 않습니다.
- 지역, 고객 문제, 해결 가치, 재방문 또는 문의 유도를 자연스럽게 연결합니다.""",
    }
    key = (industry_key or "general").strip()
    return guides.get(key, guides["general"])


def build_seo_guidance(seo_level: str = "균형") -> str:
    level = (seo_level or "균형").strip()
    if level == "자연스럽게":
        return """SEO 강도: 자연스럽게
- 키워드를 과하게 반복하지 않습니다.
- 문맥, 현장감, 사람이 쓴 듯한 자연스러움을 우선합니다.
- 제목과 첫 문단에만 핵심 키워드를 부드럽게 배치합니다."""
    if level == "강하게":
        return """SEO 강도: 강하게
- 지역 + 서비스 조합을 제목, 소제목, 첫 문단, 중간 문단에 분산 배치합니다.
- 핵심 키워드를 굵은 표시와 소제목에 적극 반영합니다.
- 단, 키워드 나열이나 어색한 반복은 피합니다."""
    return """SEO 강도: 균형
- 지역명, 서비스명, 핵심 키워드를 제목, 소제목, 본문에 자연스럽게 분산합니다.
- 굵은 표시는 핵심 키워드와 문제·원인·해결 표현 중심으로 사용합니다.
- 검색 최적화와 사람이 읽는 자연스러움의 균형을 유지합니다."""


def build_brand_tone_guidance(brand_tone: str = "업체 페르소나 우선") -> str:
    return f"""브랜드 톤: {brand_tone or '업체 페르소나 우선'}
- 업체 페르소나의 말투, 경력, 차별점, 피해야 할 표현을 가장 우선합니다.
- 감성 레벨은 문장의 분위기와 온도를 조절합니다.
- 글쓰기 스타일은 전체 전개 구조를 결정합니다.
- 업종별 작성 흐름은 콘텐츠의 뼈대를 잡는 용도로만 사용합니다."""


def _block(name: str, desc: str) -> str:
    return f"[BLOCK:{name}]\n{desc}"


def _fetch_footer_style_weather_summary(region: str) -> str:
    item = FOOTER_WEATHER_REGION_MAP.get(str(region or "").strip())
    if not item:
        return ""
    label, lat, lon = item
    try:
        params = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code", "timezone": "Asia/Seoul"})
        with urllib.request.urlopen(DEFAULT_FOOTER_WEATHER_URL + "?" + params, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        current = payload.get("current") or {}
        temp = current.get("temperature_2m")
        code = current.get("weather_code")
        if temp is None:
            return ""
        state = FOOTER_WEATHER_CODE_MAP.get(code, "날씨 확인")
        return "오늘 " + label + "은 " + state + "입니다. 현재 기온은 " + str(temp) + "도입니다. 이 날씨를 자연스럽게 활용하여 블로그와 SNS 콘텐츠에 계절감과 현장감을 더해 주세요."
    except Exception:
        return ""


def _extract_weather_summary(weather_text: str) -> str:
    text = re.sub(r"\s+", " ", str(weather_text or "")).strip()
    if not text:
        return "날씨 서버 응답 없음"

    low_match = re.search(r"(?:최저|아침\s*최저|최저기온)\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*도?", text)
    high_match = re.search(r"(?:최고|낮\s*최고|최고기온)\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*도?", text)
    state_match = re.search(r"(맑음|구름많음|구름 많음|흐림|비|소나기|눈|비 또는 눈|안개|황사|폭염|한파)", text)

    parts = []
    if state_match:
        parts.append(f"날씨 상태: {state_match.group(1)}")
    if low_match:
        parts.append(f"최저기온: {low_match.group(1)}도")
    if high_match:
        parts.append(f"최고기온: {high_match.group(1)}도")

    if parts:
        return " / ".join(parts)
    return text[:600]


def _extract_weather_tool_answer(data: dict) -> str:
    for key in ("answer", "output", "text", "message"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    raw = data.get("raw")
    if isinstance(raw, dict):
        for key in ("answer", "output", "text", "message"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def _fetch_direct_weather_tool_summary(region: str) -> str:
    weather_tool_url = os.getenv("WEATHER_TOOL_URL", DEFAULT_WEATHER_TOOL_URL).strip()
    if not weather_tool_url:
        return ""

    region_name = str(region or "").strip()
    weather_query_region = REGION_WEATHER_QUERY_MAP.get(region_name, region_name)
    query = f"{weather_query_region} 오늘 날씨"

    try:
        url = weather_tool_url + "?" + urllib.parse.urlencode({"query": query})
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        answer = _extract_weather_tool_answer(payload)
        return _extract_weather_summary(answer) if answer else ""
    except Exception:
        return ""


def _fetch_ha_weather_summary(region: str):
    ha_url = os.getenv("HA_URL", "").rstrip("/")
    ha_token = os.getenv("HA_TOKEN", "").strip()
    entity_id = os.getenv("HA_WEATHER_ENTITY_ID", DEFAULT_HA_WEATHER_ENTITY_ID).strip()

    if not ha_url or not ha_token or not entity_id:
        return ""

    try:
        req = urllib.request.Request(
            f"{ha_url}/api/states/{entity_id}",
            headers={
                "Authorization": f"Bearer {ha_token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=5, context=None) as response:
            payload = json.loads(response.read().decode("utf-8"))

        state = str(payload.get("state") or "").strip()
        attrs = payload.get("attributes") or {}
        state_ko = WEATHER_STATE_KO_MAP.get(state, state)
        temperature = attrs.get("temperature")
        unit = attrs.get("temperature_unit") or "°C"
        friendly = attrs.get("friendly_name") or entity_id
        region_label = str(region or "").strip() or friendly

        parts = []
        if state_ko:
            parts.append(f"날씨 상태: {state_ko}")
        if temperature is not None:
            parts.append(f"현재기온: {temperature}{unit}")

        if parts:
            return f"HA 기준 {region_label} 날씨 / " + " / ".join(parts)
        return ""
    except Exception:
        return ""


def _find_weather_file() -> Path | None:
    for weather_dir in WEATHER_DIR_CANDIDATES:
        weather_file = weather_dir / "weather.py"
        if weather_file.exists():
            return weather_file
    return None


def _find_weather_python() -> str:
    for python_path in WEATHER_PYTHON_CANDIDATES:
        if str(python_path) == "python3":
            return "python3"
        if python_path.exists():
            return str(python_path)
    return "python3"


def fetch_region_weather_summary(region: str) -> str:
    region_name = str(region or "").strip()
    if not region_name:
        return ""

    footer_summary = _fetch_footer_style_weather_summary(region_name)
    if footer_summary:
        return footer_summary

    direct_summary = _fetch_direct_weather_tool_summary(region_name)
    if direct_summary:
        return direct_summary

    ha_summary = _fetch_ha_weather_summary(region_name)
    if ha_summary:
        return ha_summary

    weather_file = _find_weather_file()
    if not weather_file:
        return "Weather 모듈 파일을 찾지 못했습니다. 선택 지역만 참고합니다."

    weather_query_region = REGION_WEATHER_QUERY_MAP.get(region_name, region_name)
    query = f"{weather_query_region} 오늘 날씨"
    try:
        result = subprocess.run(
            [_find_weather_python(), str(weather_file), query],
            cwd=str(weather_file.parent),
            capture_output=True,
            text=True,
            timeout=12,
            shell=False,
        )
        output = (result.stdout or "").strip()
        if not output and result.stderr:
            return "Weather 모듈 실행 결과가 비어 있습니다. 선택 지역만 참고합니다."
        return _extract_weather_summary(output)
    except subprocess.TimeoutExpired:
        return "Weather 모듈 조회 시간이 초과되었습니다. 선택 지역만 참고합니다."
    except Exception:
        return "Weather 모듈 실행 실패. 선택 지역만 참고합니다."


def _fetch_weather_and_temp_uncached(region: str) -> tuple[str, str]:
    """
    지정된 지역의 날씨 상태와 기온을 조회하여 반환합니다.
    실패 시 기본값을 반환합니다.
    """
    region_name = str(region or "").strip()
    if not region_name:
        return "맑음", "20"

    # 1. Open-Meteo (Footer Style)
    item = FOOTER_WEATHER_REGION_MAP.get(region_name)
    if item:
        label, lat, lon = item
        try:
            params = urllib.parse.urlencode({
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
                "timezone": "Asia/Seoul"
            })
            url = DEFAULT_FOOTER_WEATHER_URL + "?" + params
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            current = payload.get("current") or {}
            temp = current.get("temperature_2m")
            code = current.get("weather_code")
            if temp is not None:
                state = FOOTER_WEATHER_CODE_MAP.get(code, "맑음")
                return state, str(temp)
        except Exception:
            pass

    # 2. Naver Weather Tool
    weather_tool_url = os.getenv("WEATHER_TOOL_URL", DEFAULT_WEATHER_TOOL_URL).strip()
    if weather_tool_url:
        weather_query_region = REGION_WEATHER_QUERY_MAP.get(region_name, region_name)
        query = f"{weather_query_region} 오늘 날씨"
        try:
            url = weather_tool_url + "?" + urllib.parse.urlencode({"query": query})
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            answer = _extract_weather_tool_answer(payload)
            if answer:
                # Weather 8010 출력은 `지금 34.6도`, `13시 33도 흐림` 형식입니다.
                temp_match = re.search(r"(?:현재|현재기온|기온|지금)\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*도?", answer)
                if not temp_match:
                    temp_match = re.search(r"(?:최저|아침\s*최저|최저기온|최고|낮\s*최고|최고기온)\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*도?", answer)

                # `비 없음`이나 뒤쪽 안내 문구를 현재 날씨로 오인하지 않고 첫 시간대 상태를 우선합니다.
                hourly_state_match = re.search(
                    r"\b\d{1,2}시\s+-?\d+(?:\.\d+)?도\s+(맑음|대체로 맑음|구름많음|구름 많음|흐림|비|소나기|눈|비 또는 눈|안개|황사|폭염|한파)",
                    answer,
                )
                state_match = hourly_state_match
                if not state_match:
                    state_text = re.sub(r"비\s*없음", "", answer)
                    state_match = re.search(r"(맑음|대체로 맑음|구름많음|구름 많음|흐림|소나기|비 또는 눈|눈|비|안개|황사|폭염|한파)", state_text)
                state_val = state_match.group(1) if state_match else "날씨 확인"
                temp_val = temp_match.group(1) if temp_match else "20"
                return state_val, temp_val
        except Exception:
            pass

    # 3. HA Weather
    ha_url = os.getenv("HA_URL", "").rstrip("/")
    ha_token = os.getenv("HA_TOKEN", "").strip()
    entity_id = os.getenv("HA_WEATHER_ENTITY_ID", DEFAULT_HA_WEATHER_ENTITY_ID).strip()
    if ha_url and ha_token and entity_id:
        try:
            req = urllib.request.Request(
                f"{ha_url}/api/states/{entity_id}",
                headers={
                    "Authorization": f"Bearer {ha_token}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            state = str(payload.get("state") or "").strip()
            attrs = payload.get("attributes") or {}
            state_ko = WEATHER_STATE_KO_MAP.get(state, "맑음")
            temperature = attrs.get("temperature")
            if temperature is not None:
                return state_ko, str(temperature)
        except Exception:
            pass

    # 4. Weather Python Script
    weather_file = _find_weather_file()
    if weather_file:
        weather_query_region = REGION_WEATHER_QUERY_MAP.get(region_name, region_name)
        query = f"{weather_query_region} 오늘 날씨"
        try:
            result = subprocess.run(
                [_find_weather_python(), str(weather_file), query],
                cwd=str(weather_file.parent),
                capture_output=True,
                text=True,
                timeout=12,
                shell=False,
            )
            output = (result.stdout or "").strip()
            if output:
                state_match = re.search(r"(맑음|구름많음|구름 많음|흐림|비|소나기|눈|비 또는 눈|안개|황사|폭염|한파)", output)
                temp_match = re.search(r"(?:현재|현재기온|기온)\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*도?", output)
                if not temp_match:
                    temp_match = re.search(r"(?:최저|아침\s*최저|최저기온|최고|낮\s*최고|최고기온)\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*도?", output)
                state_val = state_match.group(1) if state_match else "맑음"
                temp_val = temp_match.group(1) if temp_match else "20"
                return state_val, temp_val
        except Exception:
            pass

    return "맑음", "20"


def fetch_weather_and_temp(region: str) -> tuple[str, str]:
    """사용자 요청 지역의 최신 날씨를 요청형 캐시로 조회합니다."""
    try:
        return get_or_fetch_weather(region, _fetch_weather_and_temp_uncached)
    except Exception:
        return "맑음", "20"


def _format_temp_range(min_temp, max_temp) -> str:
    try:
        if min_temp is not None and max_temp is not None:
            return f"{float(min_temp):.1f}~{float(max_temp):.1f}℃"
    except Exception:
        pass
    return ""


def _build_weather_story_sentence(region: str, weather_label: str, avg_temp=None, min_temp=None, max_temp=None) -> str:
    """DB 날씨 데이터를 LLM이 바로 활용하기 좋은 자연 문장으로 변환합니다."""
    region_name = str(region or "").strip() or "선택 지역"
    weather = str(weather_label or "날씨 확인").strip()
    temp_range = _format_temp_range(min_temp, max_temp)

    if temp_range:
        if weather in ("맑음", "대체로 맑음", "구름많음", "구름 많음"):
            return (
                f"오늘 {region_name}은 하루 동안 {weather} 흐름이 이어졌습니다.\n"
                f"기온은 {temp_range} 사이를 오가며 현장 이동과 작업 분위기를 자연스럽게 담기 좋은 하루였습니다.\n"
                "콘텐츠에는 숫자 설명보다 오늘 하루의 날씨 흐름과 현장감을 자연스럽게 녹여 주세요."
            )
        if weather in ("비", "소나기", "강한 비", "장마"):
            return (
                f"오늘 {region_name}은 비가 오거나 습한 흐름이 이어졌습니다.\n"
                f"기온은 {temp_range} 사이였고, 이동과 작업 환경에 신경이 필요한 하루였습니다.\n"
                "콘텐츠에는 비 오는 날의 불편함, 습도, 안전 점검 같은 생활감을 자연스럽게 연결해 주세요."
            )
        if weather in ("눈", "강한 눈", "비 또는 눈", "한파"):
            return (
                f"오늘 {region_name}은 차갑고 조심스러운 날씨 흐름이 이어졌습니다.\n"
                f"기온은 {temp_range} 사이였고, 실내외 온도 차와 안전 관리가 더 중요하게 느껴지는 하루였습니다.\n"
                "콘텐츠에는 추운 날씨 속 생활 불편과 관리 팁을 자연스럽게 반영해 주세요."
            )
        if weather in ("흐림", "부분적으로 흐림", "안개", "강한 바람", "바람"):
            return (
                f"오늘 {region_name}은 {weather} 분위기가 이어진 하루였습니다.\n"
                f"기온은 {temp_range} 사이를 오가며 차분한 현장 분위기를 만들었습니다.\n"
                "콘텐츠에는 날씨를 설명하듯 쓰기보다 현장의 공기와 분위기로 자연스럽게 표현해 주세요."
            )

    if avg_temp is not None:
        try:
            return (
                f"오늘 {region_name}은 {weather} 흐름이 가장 많이 관찰되었습니다.\n"
                f"평균 기온은 {float(avg_temp):.1f}℃ 안팎으로, 오늘의 생활 분위기를 콘텐츠에 자연스럽게 담기 좋은 날이었습니다.\n"
                "콘텐츠에는 현재값보다 하루 동안의 날씨 흐름과 현장감을 우선 반영해 주세요."
            )
        except Exception:
            pass

    return (
        f"오늘 {region_name}은 {weather} 흐름이 관찰되었습니다.\n"
        "오늘의 날씨 분위기를 숫자보다 생활감과 현장감 중심으로 자연스럽게 반영해 주세요."
    )


def _compose_weather_summary_from_daily(region: str, avg_temp, min_temp, max_temp, dominant_weather: str) -> str:
    return _build_weather_story_sentence(region, dominant_weather or "날씨 확인", avg_temp, min_temp, max_temp)


def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def build_calendar_context(now: datetime) -> str:
    """오늘 날짜, 요일, 월말/월초, 계절감을 사람다운 문장으로 변환합니다."""
    weekday_map = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    month = now.month
    day = now.day
    weekday = weekday_map[now.weekday()]

    if month in (3, 4, 5):
        season = "봄"
        season_mood = "환기와 정리, 새 단장을 떠올리기 좋은 계절입니다."
    elif month in (6, 7, 8):
        season = "여름"
        season_mood = "더위, 습기, 장마, 에어컨 사용처럼 생활 불편이 도드라지기 쉬운 계절입니다."
    elif month in (9, 10, 11):
        season = "가을"
        season_mood = "선선한 공기 속에서 집과 가게를 정돈하기 좋은 계절입니다."
    else:
        season = "겨울"
        season_mood = "추위, 난방, 결로, 실내 관리가 중요하게 느껴지는 계절입니다."

    if day <= 7:
        month_flow = "월초의 새 출발 분위기가 있습니다."
    elif day >= 24:
        month_flow = "월말로 접어들며 한 달을 정리하는 분위기가 있습니다."
    else:
        month_flow = "한 달의 흐름이 무르익는 시기입니다."

    if weekday == "월요일":
        weekday_mood = "한 주가 시작되는 날이라 작은 불편도 미루지 않고 정리하려는 마음이 생기기 쉽습니다."
    elif weekday == "금요일":
        weekday_mood = "주말을 앞두고 집과 가게를 정리하려는 분들이 늘어나는 날입니다."
    elif weekday in ("토요일", "일요일"):
        weekday_mood = "주말이라 가족과 함께 생활 공간을 살펴보는 시간이 많아지는 날입니다."
    else:
        weekday_mood = "평일의 흐름 속에서 일상적인 불편을 조용히 해결하기 좋은 날입니다."

    return (
        f"오늘은 {now.year}년 {month}월 {day}일 {weekday}입니다.\n"
        f"현재 계절은 {season}이며, {season_mood}\n"
        f"{month_flow}\n"
        f"{weekday_mood}"
    )


def build_time_context(now: datetime) -> tuple[str, str, str]:
    """시간대를 세분화하고 생활 흐름 문장을 함께 반환합니다.
    전달된 now 값이 서버/캐시/UTC 영향으로 어긋나도, 프롬프트 생성 순간의 한국시간을 다시 기준으로 삼습니다.
    """
    try:
        now = datetime.now(KST)
    except Exception:
        pass
    hour = now.hour
    if 0 <= hour < 5:
        return "새벽", "대부분의 생활 공간이 조용해지는 시간입니다.", "불편을 크게 말하기보다 조용히 쌓여 있던 생활 문제를 떠올리게 작성해 주세요."
    if 5 <= hour < 7:
        return "이른 아침", "하루가 막 시작되고 집 안의 작은 움직임이 살아나는 시간입니다.", "아침 공기와 하루의 시작을 자연스럽게 담아 주세요."
    if 7 <= hour < 9:
        return "출근 시간", "출근과 등교 준비로 집 안의 수도, 조명, 욕실 사용이 많아지는 시간입니다.", "바쁜 아침에 느끼는 생활 불편을 자연스럽게 연결해 주세요."
    if 9 <= hour < 12:
        return "오전", "현장 방문과 상담이 본격적으로 시작되기 좋은 시간입니다.", "활기찬 오전 분위기와 작업 준비감을 반영해 주세요."
    if 12 <= hour < 14:
        return "점심 무렵", "잠시 숨을 고르며 오전 작업을 정리하고 오후 일정을 준비하는 시간입니다.", "생활 속 현실감과 잠깐의 여유를 부드럽게 담아 주세요."
    if 14 <= hour < 17:
        return "오후", "하루 중 현장의 온도와 피로감이 가장 잘 느껴지는 시간입니다.", "오후의 현장감, 작업자의 집중, 고객의 기다림을 자연스럽게 표현해 주세요."
    if 17 <= hour < 19:
        return "늦은 오후", "작업을 마무리하고 결과를 확인하기 좋은 시간입니다.", "작업 전후 변화와 하루가 정리되는 느낌을 살려 주세요."
    if 19 <= hour < 21:
        return "저녁", "퇴근 후 가족이 집에 모이고 생활 공간의 불편을 다시 느끼는 시간입니다.", "하루를 마무리하는 저녁 분위기와 집 안의 생활감을 담아 주세요."
    if 21 <= hour < 23:
        return "밤", "집 안이 조용해지고 하루 동안 보이지 않던 불편이 눈에 들어오는 시간입니다.", "차분한 밤의 공기와 오늘의 날씨를 자연스럽게 활용해 주세요."
    return "늦은 밤", "하루가 거의 정리되고 조용한 공기만 남는 시간입니다.", "과하게 들뜨지 말고 조용하고 사람다운 마무리감을 살려 주세요."


def build_industry_life_context(industry_key: str, time_of_day: str) -> str:
    """업종과 시간대를 연결해 오늘 사람들이 무엇을 하고 있을지 알려줍니다."""
    key = (industry_key or "general").strip()
    if key in ("home_repair", "boiler_facility", "appliance_clean", "general_cleaning", "window_screen", "key_doorlock", "lighting_electric", "drain_unclog"):
        return (
            f"{time_of_day}에는 집 안의 수도, 욕실, 조명, 배수, 냄새, 결로 같은 작은 불편이 더 또렷하게 느껴질 수 있습니다.\n"
            "콘텐츠는 고객이 실제로 겪는 생활 장면에서 시작하고, 작업 과정은 차분하게 설명합니다."
        )
    if key in ("restaurant", "meat_korean", "cafe", "bakery_dessert", "pub_bar", "mealkit_sidedish"):
        return (
            f"{time_of_day}에는 식사, 간식, 모임, 퇴근길 방문처럼 생활 동선이 콘텐츠의 배경이 됩니다.\n"
            "콘텐츠는 맛 설명보다 방문 이유와 그 시간의 분위기를 먼저 살립니다."
        )
    if key == "camping":
        return (
            f"{time_of_day}에는 하늘, 바람, 불빛, 가족의 대화처럼 자연 속 장면이 콘텐츠의 배경이 됩니다.\n"
            "콘텐츠는 시설 설명보다 그곳에서 머무는 사람의 기분을 먼저 살립니다."
        )
    if key in ("beauty_wellness", "hair_salon", "nail_art", "skin_care", "fitness_pt", "body_massage"):
        return (
            f"{time_of_day}에는 스스로를 돌보고 정리하려는 마음이 콘텐츠의 배경이 됩니다.\n"
            "콘텐츠는 변화의 과장보다 상담, 관리 과정, 편안함을 중심으로 풀어갑니다."
        )
    return (
        f"{time_of_day}의 생활 흐름을 배경으로 고객이 왜 지금 이 서비스를 떠올리는지 자연스럽게 연결합니다.\n"
        "콘텐츠는 설명보다 실제 생활 장면과 해결 과정을 우선합니다."
    )


def fetch_recent_weather_trend_for_prompt(region: str, days: int = 7) -> str:
    """최근 일주일 일별 날씨 요약 DB를 평균해 요즘 날씨 흐름을 사람다운 문장으로 만듭니다."""
    region_name = str(region or "").strip()
    if not region_name:
        return "최근 날씨 흐름은 선택 지역이 없어 반영하지 않습니다."

    try:
        db_path = str(settings.STORYMAKER_DB_PATH)
        with sqlite3.connect(db_path, timeout=2) as conn:
            conn.row_factory = sqlite3.Row
            lookup_regions = build_region_lookup_candidates(region_name)
            placeholders = ",".join("?" for _ in lookup_regions)
            table_columns = {row[1] for row in conn.execute("PRAGMA table_info(weather_daily_summaries)").fetchall()}
            humidity_column = next((col for col in ["avg_humidity", "humidity", "relative_humidity", "avg_relative_humidity"] if col in table_columns), None)
            humidity_select = f", {humidity_column} AS avg_humidity" if humidity_column else ", NULL AS avg_humidity"
            rows = conn.execute(
                f"""
                SELECT date, avg_temp, min_temp, max_temp, dominant_weather{humidity_select}
                FROM weather_daily_summaries
                WHERE region IN ({placeholders})
                ORDER BY date DESC
                LIMIT ?
                """,
                (*lookup_regions, int(days)),
            ).fetchall()
    except Exception:
        return "최근 일주일 날씨 DB를 읽지 못했습니다. 오늘 날씨와 계절감만 자연스럽게 참고해 주세요."

    if not rows:
        return "최근 일주일 날씨 데이터가 아직 충분하지 않습니다. 오늘 날씨와 계절감만 자연스럽게 참고해 주세요."

    avg_values = [_safe_float(row["avg_temp"]) for row in rows]
    min_values = [_safe_float(row["min_temp"]) for row in rows]
    max_values = [_safe_float(row["max_temp"]) for row in rows]
    humidity_values = [_safe_float(row["avg_humidity"]) for row in rows]
    avg_values = [v for v in avg_values if v is not None]
    min_values = [v for v in min_values if v is not None]
    max_values = [v for v in max_values if v is not None]
    humidity_values = [v for v in humidity_values if v is not None]

    weather_counts = {}
    for row in rows:
        weather = str(row["dominant_weather"] or "").strip()
        if weather:
            weather_counts[weather] = weather_counts.get(weather, 0) + 1
    dominant = max(weather_counts.items(), key=lambda item: item[1])[0] if weather_counts else "날씨 확인"

    lines = [f"최근 {len(rows)}일 동안 {region_name}의 날씨 흐름을 함께 참고합니다."]
    if avg_values:
        lines.append(f"평균 기온은 약 {sum(avg_values) / len(avg_values):.1f}℃ 안팎입니다.")
    if humidity_values:
        lines.append(f"최근 평균 습도는 약 {sum(humidity_values) / len(humidity_values):.0f}% 수준입니다.")
    if min_values and max_values:
        week_min = min(min_values)
        week_max = max(max_values)
        avg_gap = sum((mx - mn) for mn, mx in zip(min_values, max_values)) / max(1, min(len(min_values), len(max_values)))
        lines.append(f"최근 최저는 {week_min:.1f}℃, 최고는 {week_max:.1f}℃ 수준이었습니다.")
        if week_max >= 33:
            lines.append("최근 최고기온이 높아 더위와 실내 관리, 냉방 사용을 떠올리기 쉬운 흐름입니다.")
        elif week_max >= 30:
            lines.append("최근 낮 기온이 제법 높아 오후 시간대에는 더위와 피로감이 느껴질 수 있습니다.")
        elif week_min <= 0:
            lines.append("최근 낮은 기온이 이어져 난방, 결로, 실내외 온도 차를 자연스럽게 연결할 수 있습니다.")

        if avg_gap >= 10:
            lines.append("아침저녁과 낮의 일교차가 큰 편이라 생활 공간 관리 이야기를 자연스럽게 풀기 좋습니다.")
        elif avg_gap >= 7:
            lines.append("하루 안에서도 온도 차가 어느 정도 느껴져 시간대별 생활감을 살리기 좋습니다.")

    if dominant:
        lines.append(f"가장 자주 관찰된 날씨 흐름은 {dominant}입니다.")
    lines.append("이 내용은 숫자 나열이 아니라 '요즘 날씨가 이렇다'는 생활 배경으로만 부드럽게 활용합니다.")
    return "\n".join(lines)


def compact_reference_text_for_prompt(text: str, max_chars: int = 3200) -> str:
    """크롤링 참고자료의 반복 문장과 과도한 해시태그를 줄여 프롬프트 비대를 방지합니다."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    lines = []
    seen = set()
    hashtag_count = 0
    for line in raw.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        if cleaned.startswith("#"):
            hashtag_count += 1
            if hashtag_count > 2:
                continue
        key = cleaned[:140]
        if key in seen:
            continue
        seen.add(key)
        lines.append(cleaned)
        if sum(len(item) + 1 for item in lines) >= max_chars:
            break
    compacted = "\n".join(lines).strip()
    return compacted[:max_chars].rstrip()


def fetch_pattern_summary_for_prompt(keywords: list, region: str = "", industry_key: str = "", days: int = 30) -> str:
    """Fetch recent Pattern DB summaries only; never raw blog text."""
    try:
        from app.db.database import SessionLocal
        from app.db import pattern_repository as pattern_repo
    except Exception:
        return ""

    seed_keywords = [str(k).strip() for k in (keywords or []) if str(k).strip()]
    if not seed_keywords and region:
        seed_keywords = [str(region).strip()]
    if not seed_keywords:
        return ""

    db = SessionLocal()
    try:
        rows = []
        for keyword in seed_keywords[:3]:
            rows.extend(pattern_repo.recent_snapshots(db, days, keyword)[:3])
        if not rows:
            return ""
        lines = ["### [최근 Pattern DB 요약]", "최근 누적 패턴만 참고합니다. 원문/HTML/본문은 포함하지 않습니다."]
        seen = set()
        for row in rows[:6]:
            summary = str(row.get("pattern_summary") or "").strip()
            if not summary or summary in seen:
                continue
            seen.add(summary)
            lines.append(f"- 키워드: {row.get('keyword')} / 스타일: {row.get('style_type')} / CTA: {row.get('cta_type')} / 추천점수: {row.get('recommendation_score')}")
            lines.append(summary[:700])
        return "\n".join(lines).strip()
    except Exception:
        return ""
    finally:
        db.close()


def fetch_performance_summary_for_prompt() -> str:
    """Fetch performance feedback summaries only; never raw content."""
    try:
        from app.services.performance_intelligence_service import prompt_feedback_summary
        return prompt_feedback_summary()
    except Exception:
        return ""


def fetch_ai_brain_summary_for_prompt() -> str:
    """Fetch AI Brain recommendation summary only; never raw content."""
    try:
        from app.services.intelligence_service import recommendation_summary
        return recommendation_summary()
    except Exception:
        return ""


def fetch_weather_context_for_prompt(region: str) -> tuple[str, str, str]:
    """
    제미나이 프롬프트용 최신 날씨 문장을 반환합니다.
    1순위: weather_cache.db의 60분 이내 최신 캐시
    2순위: 캐시가 없거나 만료되면 요청형 외부 조회 후 최신 캐시 저장
    3순위: 외부 조회 실패 시 weather_cache.db의 직전 캐시
    4순위: 모든 조회가 실패하면 안전한 기본 안내 문장
    """
    region_name = str(region or "").strip()
    if not region_name:
        return "오늘 날씨 정보는 아직 충분하지 않습니다. 기본 날씨값을 참고해 자연스럽게 작성해 주세요.", "날씨 확인", "20"

    try:
        weather, temperature = fetch_weather_and_temp(region_name)
        weather_val = str(weather or "날씨 확인").strip()
        temp_val = str(temperature or "20").strip()
        context = (
            f"오늘 {region_name}의 날씨는 {weather_val}입니다. "
            f"현재 기온은 {temp_val}℃입니다. "
            "날씨를 길게 설명하지 말고 오늘의 공기와 현장 분위기에 자연스럽게 반영해 주세요."
        )
        return context, weather_val, temp_val
    except Exception:
        return (
            f"오늘 {region_name}의 최신 날씨를 확인하지 못했습니다. "
            "계절감과 시간대 흐름만 자연스럽게 반영해 주세요.",
            "날씨 확인",
            "20",
        )


def _extract_korean_region_candidates(*texts: str) -> list[str]:
    """업체 정보와 입력자료에서 실제 지역 후보를 안전하게 추출합니다."""
    joined = "\n".join(str(t or "") for t in texts)
    candidates: list[str] = []
    known_regions = [
        "서울", "인천", "경기", "강원", "대전", "충청", "광주", "전라", "대구", "경북", "부산", "울산", "경남", "제주", "양양",
        "안산", "하남", "성남", "수원", "고양", "용인", "부천", "화성", "평택", "김포", "경주", "포항", "창원", "김해", "양산",
    ]
    for name in known_regions:
        if name and name in joined and name not in candidates:
            candidates.append(name)

    # 시/군/구/동/읍/면 단위 후보는 오탐이 많으므로 생활권 목록 또는 알려진 지역명만 통과시킵니다.
    allowed_detail_regions = set(known_regions)
    for area_list in REGION_SUBAREAS_MAP.values():
        for item in area_list.split(","):
            cleaned = item.strip()
            if cleaned:
                allowed_detail_regions.add(cleaned)
    for match in re.findall(r"[가-힣]{2,}(?:시|군|구|동|읍|면)", joined):
        normalized = normalize_region_alias(match)
        if match in REGION_NOISE_WORDS or normalized in REGION_NOISE_WORDS:
            continue
        if match not in allowed_detail_regions and normalized not in allowed_detail_regions:
            continue
        candidate = normalized if normalized in allowed_detail_regions else match
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates[:12]


def _normalize_primary_region(region_value: str, *context_texts: str) -> str:
    """프론트 기본값보다 사용자 입력/페르소나의 실제 지역을 우선합니다."""
    raw_region = str(region_value or "").strip()
    invalid_region_values = {"", "chatgpt", "gemini", "claude", "balanced", "default", "general", "지역 선택 없음", "선택 안함"}
    candidates = _extract_korean_region_candidates(*context_texts)

    # 명시 지역이 실제 후보와 충돌하면 실제 입력/페르소나 후보를 우선합니다.
    if raw_region.lower() in invalid_region_values:
        return candidates[0] if candidates else ""

    if raw_region == "서울" and candidates and not any(c in ("서울", "강남구", "서초구", "송파구", "마포구", "용산구", "성동구", "영등포구", "강서구", "종로구", "성북구") for c in candidates[:4]):
        return candidates[0]

    if raw_region:
        return raw_region
    return candidates[0] if candidates else ""


def _build_region_context(region_name: str, persona: str, base_content: str, keywords: list) -> tuple[str, str, str, str]:
    """지역 정보 모듈을 사용자 데이터 기반으로 생성합니다."""
    keyword_text = " ".join(str(k or "") for k in (keywords or []))
    candidates = _extract_korean_region_candidates(persona, base_content, keyword_text)
    primary = normalize_region_alias(region_name) or (normalize_region_alias(candidates[0]) if candidates else "")
    subareas = REGION_SUBAREAS_MAP.get(primary, "") if primary else ""

    # 입력자료의 실제 동/아파트/생활권 후보를 우선 예시로 씁니다.
    detail_candidates = []
    for candidate in candidates:
        normalized_candidate = normalize_region_alias(candidate)
        if normalized_candidate and normalized_candidate != primary and normalized_candidate not in detail_candidates:
            detail_candidates.append(normalized_candidate)
    if subareas:
        for item in [v.strip() for v in subareas.split(",") if v.strip()]:
            if item not in detail_candidates:
                detail_candidates.append(item)

    # 지역 충돌 방어: 울산/안산/양양 등 실제 지역이 있는데 서울 생활권을 끼워 넣지 않습니다.
    if primary != "서울":
        detail_candidates = [c for c in detail_candidates if c not in {"강남구", "서초구", "송파구", "마포구", "용산구", "성동구", "영등포구", "강서구", "종로구", "성북구", "공덕동", "여의도동", "상암동"}]

    first_area = detail_candidates[0] if detail_candidates else primary
    life_examples = "\n".join(detail_candidates[1:9]) if len(detail_candidates) > 1 else (primary or "업체 활동 지역")
    return primary, first_area, life_examples, "\n".join(candidates)


def build_life_context_manifest(now: datetime, region_name: str, weather_context_text: str, recent_weather_trend: str) -> str:
    """모든 업종에 적용 가능한 감성형 생활 배경 엔진입니다."""
    weekday_map = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    month = int(now.month)
    if month in (3, 4, 5):
        season_label = "봄"
    elif month == 6:
        season_label = "초여름"
    elif month in (7, 8):
        season_label = "한여름"
    elif month in (9, 10, 11):
        season_label = "가을"
    else:
        season_label = "겨울"
    time_of_day, _, _ = build_time_context(now)
    date_phrase = f"{now.month}월 {now.day}일 {season_label}, {weekday_map[now.weekday()]} {time_of_day}입니다."
    return f"""오늘의 생활 배경은 콘텐츠 첫머리에 자연스럽게만 녹입니다.
- 지역: {region_name or '업체 활동 지역'}
- 오늘 날씨: {date_phrase} {weather_context_text}
- 최근 흐름: {recent_weather_trend}

작성 원칙
- 날짜, 계절, 시간대, 날씨는 설명문으로 길게 쓰지 말고 현장 장면에 짧게 반영합니다.
- 실제 입력자료와 업체 페르소나를 최우선으로 합니다.
- 특정 업종 표현을 억지로 넣지 말고 고객 불편, 현장 확인, 해결 과정 중심으로 씁니다."""
    return f"""당신은 단순히 글을 생성하는 도구가 아닙니다.
오늘이라는 하루를 살아가는 사람들의 생활을 기록하는 작가입니다.

계절이 바뀌면 사람들의 생각도 달라지고,
날씨가 변하면 행동도 달라집니다.
아침과 저녁은 분위기가 다르고,
월초와 월말은 사람들의 마음도 다릅니다.

이 콘텐츠는 업체를 광고처럼 앞세우지 않습니다.
먼저 오늘의 공기, 계절의 온도, 시간대의 리듬, 사람들의 생활 장면을 이해합니다.
그다음 업체가 필요한 순간에 자연스럽게 등장해야 합니다.

독자는 광고를 읽었다고 느끼기보다,
자기 생활과 닮은 따뜻한 이야기를 읽었다고 느껴야 합니다.

오늘의 지역 배경: {region_name or '업체 활동 지역'}
오늘의 날씨 배경: {weather_context_text}
최근 흐름: {recent_weather_trend}

작성 원칙
- 날씨와 계절은 설명하지 말고 장면으로 녹입니다.
- 숫자보다 공기, 빛, 습도감, 바람, 사람의 움직임을 우선합니다.
- 월초라면 새 출발과 정리의 마음을 은근히 담습니다.
- 월말이라면 미뤄둔 일과 마무리의 마음을 은근히 담습니다.
- 업종이 무엇이든 특정 업종 표현을 억지로 넣지 않습니다.
- 실제 입력자료와 업체 페르소나가 언제나 최우선입니다."""


def build_prompt_markdown(company: str, persona: str, base_content: str, reference_text: str, keywords: list, style: str, ai_preset: str, emotion_levels=None, region=None, industry_key="general", blog_content_length=1500, phone_number="") -> str:
    region_name = normalize_region_alias(_normalize_primary_region(region, persona, base_content, " ".join(str(k or "") for k in (keywords or []))))
    try:
        blog_length = int(blog_content_length or 1500)
    except (TypeError, ValueError):
        blog_length = 1500
    if blog_length not in (1200, 1500, 2000):
        blog_length = 1500
    preset_header = build_preset_header("")
    style_guidance = build_style_guidance(style)

    emotion_map = {
        "따뜻함": "고객의 불편을 먼저 공감하고 배려가 느껴지는 부드러운 문장을 사용합니다.",
        "전문가": "정확한 용어, 원인 진단, 작업 과정, 안전 확인을 분명하게 설명합니다.",
        "친근함": "동네 이웃과 대화하듯 편안하고 자연스러운 표현을 사용합니다.",
        "신뢰감": "과장보다 확인된 사실, 책임감, 사후 안내를 중심으로 믿을 수 있는 문장을 사용합니다.",
        "현장감": "현장의 증상, 소리, 냄새, 작업 순서, 전후 변화를 실제 장면처럼 구체적으로 담습니다.",
        "진정성": "광고처럼 꾸미기보다 고객 불편을 해결하려는 마음과 책임 있는 태도를 담백하게 표현합니다.",
        "차분함": "침착하고 안정적인 어조로 과장 없이 신뢰감을 줍니다.",
        "활기": "문장 흐름에 생동감을 주되 과하게 들뜨지 않게 밝고 적극적인 분위기를 더합니다.",
        "담백함": "불필요한 수식과 감탄을 줄이고 핵심을 쉽고 간결하게 전달합니다.",
        "순박함": "꾸밈없는 동네 말투와 솔직한 표현으로 편안하고 사람 냄새 나는 인상을 줍니다.",
        "진지함": "문제 원인, 안전, 책임, 재발 방지를 무게감 있게 다룹니다.",
    }
    if isinstance(emotion_levels, str):
        emotion_candidates = [v.strip() for v in emotion_levels.replace("/", ",").replace("|", ",").split(",")]
    elif isinstance(emotion_levels, (list, tuple, set)):
        emotion_candidates = [str(v).strip() for v in emotion_levels]
    else:
        emotion_candidates = []
    selected_emotions = []
    for emotion in emotion_candidates:
        if emotion in emotion_map and emotion not in selected_emotions:
            selected_emotions.append(emotion)
    if not selected_emotions:
        selected_emotions = ["따뜻함", "전문가"]
    selected_emotions = selected_emotions[:11]
    emotion_summary = ", ".join(selected_emotions)
    emotion_guidance = build_emotion_weight_guidance(selected_emotions, emotion_map)

    industry_guidance = build_industry_guidance(industry_key)
    seo_level = "균형"
    seo_guidance = build_seo_guidance(seo_level)
    brand_tone = "업체 페르소나 우선"
    brand_tone_guidance = build_brand_tone_guidance(brand_tone)

    compact_reference_text = compact_reference_text_for_prompt(reference_text)
    pattern_summary = fetch_pattern_summary_for_prompt(keywords, region_name, industry_key)
    performance_summary = fetch_performance_summary_for_prompt()
    brain_summary = fetch_ai_brain_summary_for_prompt()
    reference_parts = []
    if pattern_summary:
        reference_parts.append(pattern_summary)
    if performance_summary:
        reference_parts.append(performance_summary)
    if brain_summary:
        reference_parts.append(brain_summary)
    if compact_reference_text:
        reference_parts.append(f"### [압축 참고자료]\n{compact_reference_text}")
    reference_block = "\n\n".join(reference_parts) if reference_parts else "(참고자료 없음)"
    prompt_persona = format_region_text(persona.strip())
    normalized_keywords = [format_region_text(str(k).strip()) for k in (keywords or []) if str(k).strip()]
    keyword_lines = "\n".join([f"- {k}" for k in normalized_keywords]) if normalized_keywords else "(핵심 키워드 없음)"

    # 날짜, 요일, 계절, 시간대, 생활 흐름 자동 생성
    now = datetime.now(KST)
    calendar_context = build_calendar_context(now)
    time_of_day, life_time_context, time_description = build_time_context(now)
    industry_life_context = build_industry_life_context(industry_key, time_of_day)

    # 세부 지역 조회: 프론트 기본값보다 업체 페르소나/기초내용/키워드의 실제 지역을 우선합니다.
    # DB에는 '울산광역시'처럼 저장되어 있어도 프롬프트 표시명은 '울산'처럼 짧게 정리합니다.
    primary_region, first_area, life_examples, extracted_region_text = _build_region_context(region_name, persona, base_content, keywords)
    if primary_region:
        region_name = normalize_region_alias(primary_region)
    else:
        region_name = normalize_region_alias(region_name)
    region_subareas = life_examples or f"{region_name} 주변 지역 및 생활권"

    # 날씨 및 기온 조회: DB 조회는 '울산광역시'와 '울산' 별칭을 함께 확인합니다.
    weather_context_text, weather, temperature = fetch_weather_context_for_prompt(region_name)
    recent_weather_trend = fetch_recent_weather_trend_for_prompt(region_name)

    # 모든 업종에 공통 적용되는 감성형 생활 배경 엔진
    life_context_manifest = build_life_context_manifest(now, region_name, weather_context_text, recent_weather_trend)

    # 전화번호 추출: 인자로 전달된 phone_number가 있으면 최우선 적용
    phone_val = (phone_number or "").strip()
    if not phone_val:
        phone_match = re.search(r"대표\s*전화번호\s*:\s*([^\n]+)", persona)
        if phone_match:
            phone_val = phone_match.group(1).strip()
        else:
            general_match = re.search(r"\b\d{2,4}-\d{3,4}-\d{4}\b", persona + "\n" + base_content)
            if general_match:
                phone_val = general_match.group(0).strip()

    # phone_number가 없으면 “전화번호” placeholder 대신 “미등록”
    if not phone_val:
        phone_val = "미등록"

    phone_number = phone_val

    naver_place_block = "NAVER" + "_" + "PLACE" + "_" + "NEWS"
    google_block = "GOOGLE" + "_" + "BUSINESS" + "_" + "POST"

    block_spec = "\n\n".join([
        _block("BLOG_TITLES", "추천 블로그 제목 5개"),
        _block("BLOG_POST", "네이버 블로그 포스팅 1개"),
        _block(naver_place_block, "네이버 스마트플레이스 소식 게시글 1개"),
        _block(google_block, "구글 마이비즈니스 게시글 1개"),
        _block("BLOG_HASHTAGS", "블로그 해시태그 1줄"),
        _block("CARROT_TITLES", "당근마켓 제목 5개"),
        _block("CARROT_POST", "당근마켓 게시글 1개"),
        _block("CARROT_HASHTAGS", "당근마켓 해시태그 1줄"),
        _block("INSTAGRAM_POST", "인스타그램 캡션 1개"),
        _block("INSTAGRAM_HASHTAGS", "인스타그램 해시태그 1줄"),
        _block("CAROUSEL_7", "카드뉴스 7장용 마크다운 1개"),
        _block("PODCAST_50", "캐릭터 팟캐스트 대본 50초 버전 1개"),
        _block("PODCAST_80", "캐릭터 팟캐스트 대본 80초 버전 1개"),
    ])

    return f"""# 콘텐츠 통합 패키지 생성 프롬프트 v3.6-stable

## 역할
{preset_header}

## StoryMaker 생성 환경
- 업체명: {company}
- 글쓰기 스타일: {style}
- 블로그 본문 목표 길이: 약 {blog_length}자
- 스타일 지침: {style_guidance}
- 감성 레벨: {emotion_summary}
- 선택 지역: {region_name or '지역 선택 없음'}

## StoryMaker 생활 배경 엔진
{life_context_manifest}

## 콘텐츠 감성
선택 감성: {emotion_summary}
{emotion_guidance}
문체, 어휘, 문장 호흡, 고객 응대감, 브랜드 마무리에 자연스럽게 반영합니다.

## 현재 시간대와 생활 흐름
현재는 {time_of_day}입니다.
{industry_life_context}
{time_description}

작성 참고
- 날짜, 계절, 시간대, 오늘 날씨, 최근 흐름은 위 생활 배경 엔진을 참고하되 반복 설명하지 않습니다.
- 숫자보다 현장의 공기, 고객 불편, 작업자의 움직임으로 표현합니다.
- 실제 입력자료와 업체 페르소나를 항상 우선합니다.

## 지역 정보
대표 지역
{region_name}

우선 활용 지역
{first_area or region_name}

생활권 예시
{life_examples}

입력자료와 페르소나에서 감지된 지역 후보
{extracted_region_text or '(감지된 세부 지역 없음)'}

작성 참고
- 대표 지역, 시·군·구, 읍·면·동, 주변 생활권을 실제 현장 경험처럼 섞어 씁니다.
- 같은 지역명 반복이나 억지 나열은 피합니다.

## 업종별 작성 흐름
{industry_guidance}

## SEO 강도
{seo_guidance}

## 브랜드 톤
{brand_tone_guidance}

## 최우선 반영 규칙
- 업체명, 전화번호, 페르소나, 기초내용을 가장 우선합니다.
- 업종별 작성 흐름은 보조 지침이며, 업체 페르소나와 실제 입력자료가 더 중요합니다.
- 참고자료는 문체, 전개 방식, 공감 포인트만 참고합니다.
- 참고자료의 타사명, 전화번호, 수치, 후기, 고유 표현은 직접 사용하지 않습니다.
- 존재하지 않는 수치, 인증, 후기, 성과를 지어내지 않습니다.

## 작업 목표
입력된 한 현장 자료를 채널별 성격에 맞게 다시 써서 13개 콘텐츠 블록을 완성합니다.
블로그는 긴 현장 이야기, 플레이스는 짧은 현장 소식, 구글은 전문 서비스 안내, 인스타는 감성 캡션, 당근은 동네 이웃 글처럼 작성합니다.

## 반드시 생성할 결과물
아래 13개 BLOCK을 순서대로 모두 작성합니다.
제목 5개, 블로그 본문, 플레이스, 구글, 해시태그, 당근, 인스타, 카드뉴스, 팟캐스트 50초/80초를 누락하지 않습니다.

## 최상위 출력 규칙
- 출력은 하나의 코드블록 안에만 작성합니다.
- [BLOCK:BLOG_POST] 본문은 약 {blog_length}자 분량으로 작성합니다. 선택값보다 지나치게 짧거나 길게 쓰지 마세요.
- 코드블록 밖 설명, 사과, 누락 고백, 상태 문구는 금지합니다.
- 아래 BLOCK 이름과 순서를 그대로 지키고, 각 블록에는 실제 완성 콘텐츠만 작성합니다.
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

{naver_place_block}, {google_block}
- 문단 전환 시에만 줄바꿈을 1회 적용합니다.
- 너무 많은 줄바꿈을 넣지 않습니다.
- 250~450자 안에서 제목, 문제, 해결, 신뢰 포인트를 간결하게 작성합니다.

INSTAGRAM_POST
- 짧은 문장 중심으로 감성 문단을 구성합니다.
- 이모지는 1개 이상 4개 이하로만 사용합니다.
- 마지막 연락 영역에 업체명 단독 줄과 전화번호 단독 줄을 반드시 넣습니다.
- 해시태그는 INSTAGRAM_HASHTAGS 블록에만 작성합니다.

CAROUSEL_7
- 슬라이드별 짧은 문장으로 작성합니다.
- 한 장당 2~4줄을 넘기지 않습니다.

PODCAST_50, PODCAST_80
- 줄바꿈보다 남성/여성 화자 턴 구분을 우선합니다.
- 실제 대화처럼 질문, 공감, 설명, 마무리가 오가게 작성합니다.

## 공통 작성 규칙

### 사람다운 문체
실제 현장 전문가가 경험을 이야기하듯 작성합니다.
광고보다 경험담을 우선하고, 과장·반복·AI식 문장 구조를 피합니다.
문장 길이와 표현을 자연스럽게 섞습니다.

본문에는 아래 요소 중 최소 2개 이상을 자연스럽게 포함합니다.
- 고객의 첫마디
- 현장 풍경
- 작업자의 생각
- 작업 후 고객 반응
- 생활 속 공감
- 계절감
- 현장의 소리
- 현장의 온도감

예시
"고칠 수 있을까요?" 고객님의 첫마디였습니다.
스위치를 켜는 순간 방 안이 환해지자 고객님 표정도 한결 밝아졌습니다.

단, 억지 대사는 만들지 말고 기초내용과 현장 상황에 어울릴 때만 사용합니다.

### 굵은 표시 규칙
핵심 키워드는 `**굵은 표시**`를 8회 이상 자연스럽게 사용합니다.
무작위 단어를 강조하지 말고 아래 우선순위에만 적용합니다.

1순위: 지역 + 서비스
예: `**울산 북구 전기수리**`

2순위: 핵심 작업
예: `**스위치 교체**`, `**LED 조명 교체**`

3순위: 문제 증상
예: `**전등 깜빡임**`, `**누전 증상**`

4순위: 원인
예: `**배선 접촉 불량**`, `**스위치 접점 노후**`

5순위: 해결 방법
예: `**배선 재체결**`, `**안정기 교체**`

6순위: 입력된 핵심 키워드 목록에 있는 단어

주의
- 한 문장 전체를 통째로 굵게 만들지 않습니다.
- 굵은 표시 안의 단어 묶음은 중간 줄바꿈 없이 한 줄 안에서 완성합니다.

### 전화번호 규칙
BLOG_POST
- 마지막 CTA에 전화번호 1회 허용

CARROT_POST
- 마지막 CTA에 전화번호 1회 허용

INSTAGRAM_POST
- 마지막 문의 영역에 업체명 풀네임과 전화번호를 반드시 1회 작성

{naver_place_block}, {google_block}
- 전화번호 직접 반복보다 부드러운 문의 유도를 우선합니다.
- 필요 시 마지막에 1회만 사용합니다.

CAROUSEL_7
- 7장 마지막 장에만 전화번호 1회 허용

PODCAST_50, PODCAST_80
- 마지막 멘트에 업체명과 전화번호를 읽기 쉬운 말투로 반드시 1회 넣습니다.
- 숫자를 지나치게 빠르게 나열하지 말고 TTS가 자연스럽게 읽을 수 있게 표현합니다.

전체 원칙
- BLOG_POST, CARROT_POST, INSTAGRAM_POST, CAROUSEL_7, PODCAST_50, PODCAST_80에는 전화번호를 말미에 반드시 1회 넣습니다.
- {naver_place_block}, {google_block}은 플랫폼 특성상 자연스러운 문의 유도를 우선하고 필요할 때만 말미에 1회 넣습니다.
- 한 채널 안에서 전화번호는 최대 1회만 사용합니다.
- 본문 중간 전화번호는 금지합니다.
- 전화번호가 없거나 '미등록'이면 임의로 전화번호를 생성하지 않습니다. 010-1234-5678 같은 가짜/예시 번호 사용을 절대 금지합니다. 전화번호가 '미등록'이면 번호 기재를 생략하거나 '전화 또는 메시지로 문의 바랍니다' 등으로 자연스럽게 문구를 대체해야 하며, 어떠한 경우에도 임의의 번호를 만들어 기재하지 마십시오.
- 전화번호: {phone_number}

## 블로그 규칙
- BLOG_TITLES는 실제 제목 5개를 번호 목록으로 작성합니다.
- BLOG_POST는 약 {blog_length}자 분량을 목표로 작성합니다. 선택값보다 지나치게 길게 늘리지 않습니다.
- 첫 줄은 반드시 `# 제목` 형식으로 시작합니다.
- 본문 소제목은 `## 소제목`만 사용합니다.
- `## 소제목`은 최소 4개 이상 사용합니다.
- 마지막 문단에는 읽어주셔서 진심으로 감사합니다라는 마음속에서 나오는 맺음말을 자연스럽게 넣습니다.
- 블로그 해시태그는 BLOG_HASHTAGS 블록에서만 출력합니다.

## 플레이스 규칙
- {naver_place_block}에는 네이버 스마트플레이스 소식에 바로 붙여넣을 수 있는 글을 작성합니다.
- 250~450자 안팎으로 작성합니다.
- 첫 줄은 블로그 제목을 그대로 복사하지 말고, 플레이스용 짧은 현장 소식 제목으로 다시 씁니다.
- 해시태그는 넣지 않습니다.
- 지역명, 서비스명, 핵심 문제를 첫 문단에 자연스럽게 넣습니다.
- 현장 상황 → 원인 확인 → 해결 내용 → 짧은 문의 유도 순서로 작성합니다.
- 블로그 요약처럼 보이지 않게 사장님이 오늘 소식을 직접 올린 느낌으로 씁니다.

## 구글 규칙
- {google_block}에는 구글 마이비즈니스 게시글에 바로 붙여넣을 수 있는 글을 작성합니다.
- 250~450자 안팎으로 작성합니다.
- 첫 줄은 블로그 제목을 그대로 복사하지 말고, 구글용 전문 서비스 제목으로 다시 씁니다.
- 해시태그, 이모지, 과장된 평점 표현은 넣지 않습니다.
- 지역과 서비스 현장 → 문제 확인 → 원인 → 해결 방식 → 서비스 범위 순서로 정리합니다.
- 업체 소개는 짧게 쓰고, 전문성·정확성·현장 대응력을 중심으로 씁니다.
- 플레이스보다 더 차분하고 정보성 있게 작성합니다.

## 인스타그램 규칙
- INSTAGRAM_POST는 짧고 강한 문장 중심으로 작성합니다.
- 첫 2줄 안에 시선을 잡는 문장을 넣습니다.
- INSTAGRAM_POST에는 이모지를 1개 이상 4개 이하로 자연스럽게 사용합니다.
- INSTAGRAM_POST 마지막 연락 영역에는 반드시 업체명 풀네임을 전화번호 바로 위 줄에 단독으로 작성합니다.
- INSTAGRAM_POST 마지막 연락 영역 형식은 반드시 아래 순서를 지킵니다.
  1) {company}
  2) {phone_number}
- INSTAGRAM_POST에서 전화번호를 작성할 경우 업체명 없이 전화번호만 단독으로 쓰면 실패입니다.
- INSTAGRAM_POST 마지막 연락 영역에는 `문의:`, `연락처:`, `전화:` 같은 라벨을 붙이지 않습니다.
- 인스타그램 해시태그는 INSTAGRAM_HASHTAGS 블록에서만 출력합니다.

## 당근마켓 규칙
- CARROT_TITLES는 제목 5개를 작성합니다.
- CARROT_POST는 500자 이상 800자 이하로 작성합니다.
- 당근마켓 비즈프로필 소식은 동네 이웃이 읽는 글입니다.
- 블로그보다 훨씬 친근하고 편안한 말투로 작성합니다.
- "~해요", "~했답니다", "편하게 말씀해 주세요"처럼 이웃에게 이야기하듯 자연스럽게 작성합니다.
- 광고 문장보다 생활 속 이야기와 실제 현장 소식처럼 작성합니다.
- 마지막에는 "단골을 맺어두시면 새로운 소식을 가장 먼저 받아보실 수 있어요." 문장을 자연스럽게 포함합니다.
- 당근 해시태그는 CARROT_HASHTAGS 블록에서만 출력합니다.

## 카드뉴스 규칙
- CAROUSEL_7은 총 7장으로 작성합니다.
- 각 장은 `## 제목` 1줄과 본문 2~4줄로 작성합니다.
- 각 장 구분은 반드시 `---` 한 줄만 사용합니다.

## 팟캐스트 규칙
- PODCAST_50은 한국어 TTS 기준 약 320~380자입니다.
- PODCAST_80은 한국어 TTS 기준 약 350~420자입니다.
- 화자 태그는 `[여성]`, `[남성]`만 사용합니다.
- 첫 문장은 여성 진행자가 시작합니다.
- 화자 태그는 한 줄에 단독으로 작성합니다.
- 여성과 남성의 대화 턴은 최소 8회 이상으로 재치 있는 대화로 구성합니다.
- 한 사람이 길게 말하지 않고 질문, 공감, 설명, 마무리가 자연스럽게 오가도록 작성합니다.
- 팟캐스트는 실제 대화처럼 들려야 하므로 감탄사와 말맛을 살리는 문장부호를 자연스럽게 사용합니다.
- 사용할 수 있는 표현 예시는 오~~, 아아!!, 하하~, 정말이요???, 어머머??, 음~~, 맞아요!! 같은 짧은 반응입니다.
- 물결표, 물음표, 느낌표는 감정이 바뀌는 지점에만 적당히 사용합니다.
- PODCAST_50에는 이런 톤 표현을 3회에서 4회 정도 사용합니다.
- PODCAST_80에는 이런 톤 표현을 3회에서 6회 정도 사용합니다.
- 단, 예능처럼 과장하지 말고 업체 페르소나와 업종 분위기에 맞게 조절합니다.
- TTS가 자연스럽게 읽을 수 있도록 짧은 호흡의 대화를 우선합니다.

## 업체 정보
### 업체명
{company}

### 업체 페르소나
{prompt_persona}

## 입력 자료
### 기초내용 입력
{base_content.strip()}

### 참고자료
{reference_block}

### 핵심 키워드
{keyword_lines}

## 최종 점검 규칙
- 13개 BLOCK이 모두 있는지 확인합니다.
- BLOG_POST 다음에 플레이스와 구글 블록이 바로 이어지는지 확인합니다.
- 인스타 상호/전화, 카드뉴스 7장, 팟캐스트 50초/80초가 빠지지 않았는지 확인합니다.
- 플레이스와 구글에는 해시태그를 넣지 않습니다.
- 상태 문구가 아니라 실제 완성 콘텐츠만 출력합니다.
- 어긋난 부분은 스스로 고친 뒤 최종본만 출력합니다.

## 중요
- 업체 페르소나와 기초내용을 최우선으로 합니다.
- 업종 흐름은 뼈대일 뿐이며 입력자료와 충돌하면 입력자료를 우선합니다.
- 전화번호는 각 채널 마지막 안내에서만 1회 사용합니다.
- 같은 단어, 지역명, 문장 구조, 표현을 반복하지 않습니다.
- 실제 사람이 현장에서 겪고 쓴 글처럼 자연스럽게 이어갑니다.
"""
