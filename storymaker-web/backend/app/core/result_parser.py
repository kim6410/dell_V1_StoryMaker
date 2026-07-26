# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드용 result_parser 모듈
기존 Tkinter UI 종속성이 제거된 순수 비즈니스 로직입니다.
"""
import re

try:
    # FastAPI 패키지 실행 환경
    from app.core.blog_formatter import format_blocks_for_mobile
except Exception:  # pragma: no cover - 로컬 단독 테스트/구버전 배포 대비
    try:
        from blog_formatter import format_blocks_for_mobile
    except Exception:  # pragma: no cover
        def format_blocks_for_mobile(blocks: dict, line_limit: int = 22) -> dict:
            return dict(blocks or {})

RESULT_BLOCK_LABELS = {
    "BLOG_TITLES": "추천 블로그 제목",
    "BLOG_POST": "블로그 포스팅",
    "CARROT_TITLES": "당근마켓 제목",
    "CARROT_POST": "당근마켓 게시글",
    "PODCAST_50": "팟캐스트 50초",
    "PODCAST_80": "팟캐스트 80초",
    "INSTAGRAM_POST": "인스타 캡션",
    "INSTAGRAM_HASHTAGS": "인스타 해시태그",
    "CAROUSEL_7": "캐러셀 7장",
    "NAVER_PLACE_NEWS": "네이버플레이스 소식",
    "GOOGLE_BUSINESS_POST": "구글마이비즈니스 소식",
    "BLOG_HASHTAGS": "블로그 해시태그",
    "CARROT_HASHTAGS": "당근 해시태그",
    "WORDPRESS_SEO": "WordPress SEO",
}

def extract_primary_code_block(text: str) -> str:
    """
    ChatGPT 응답 텍스트에서 ```content ``` 또는 ```형식의 주 코드 블록을 추출합니다.
    """
    match = re.search(r"```(?:[A-Za-z0-9_-]+)?\s*\n(.*?)```", text, flags=re.DOTALL)
    return match.group(1).strip() if match else text.strip()



PLACEHOLDER_ONLY_VALUES = {
    "확인 완료",
    "완료",
    "작성 완료",
    "생성 완료",
    "출력 완료",
    "ok",
    "okay",
    "done",
}


def _is_placeholder_content(value: str) -> bool:
    """
    AI가 실제 콘텐츠 대신 상태 메시지만 반환한 경우를 감지합니다.
    """
    compact = re.sub(r"\s+", "", (value or "").strip()).lower()
    return compact in {re.sub(r"\s+", "", v).lower() for v in PLACEHOLDER_ONLY_VALUES}


def _normalize_wordpress_seo_block(content: str) -> str:
    """
    WORDPRESS_SEO 블록 내부의 흔들리는 라벨 형식을 보정합니다.

    허용/보정 예:
    [WordPress 제목]: 값  -> - WordPress 제목: 값
    WordPress 제목: 값    -> - WordPress 제목: 값
    - WordPress 제목: 값  -> - WordPress 제목: 값
    """
    if not content:
        return content

    labels = [
        "WordPress 제목",
        "Slug",
        "포커스 키워드",
        "SEO 제목",
        "메타 설명",
        "카테고리",
        "태그",
        "대표 이미지 ALT",
        "OG 제목",
        "OG 설명",
        "본문 HTML",
    ]

    label_pattern = "|".join(re.escape(label) for label in labels)
    line_pattern = re.compile(
        rf"^\s*(?:[-*]\s*)?\[?\s*({label_pattern})\s*\]?\s*:\s*(.*)$"
    )

    normalized_lines = []
    extracted = {}

    for line in content.splitlines():
        match = line_pattern.match(line)
        if match:
            label = match.group(1)
            value = match.group(2).strip()
            extracted[label] = value
            normalized_lines.append(f"- {label}: {value}")
        else:
            normalized_lines.append(line.rstrip())

    # 비어 있는 공유/SEO 항목은 이미 있는 값으로 안전 보강합니다.
    wp_title = extracted.get("WordPress 제목", "").strip()
    focus_keyword = extracted.get("포커스 키워드", "").strip()
    meta_desc = extracted.get("메타 설명", "").strip()

    replacements = {}
    if extracted.get("SEO 제목", "") == "" and focus_keyword:
        replacements["SEO 제목"] = f"{focus_keyword} | SNS AI Studio"
    if extracted.get("OG 제목", "") == "" and wp_title:
        replacements["OG 제목"] = wp_title
    if extracted.get("OG 설명", "") == "" and meta_desc:
        replacements["OG 설명"] = meta_desc

    if replacements:
        repaired = []
        for line in normalized_lines:
            replaced = False
            for label, value in replacements.items():
                if re.match(rf"^\s*-\s*{re.escape(label)}\s*:\s*$", line):
                    repaired.append(f"- {label}: {value}")
                    replaced = True
                    break
            if not replaced:
                repaired.append(line)
        normalized_lines = repaired

    return "\n".join(normalized_lines).strip()


def _normalize_parsed_blocks(parsed: dict) -> dict:
    """
    파싱 결과를 화면 출력 전에 한 번 더 안전하게 정리합니다.
    """
    cleaned = {}
    for name, value in (parsed or {}).items():
        value = (value or "").strip()

        # 실제 콘텐츠가 아니라 상태 메시지만 있는 경우,
        # 조용히 빈 값으로 만들면 화면에는 태그만 남아 원인 파악이 어려워집니다.
        # 따라서 블록별 오류 문구를 남겨 프론트/사용자가 즉시 문제를 알 수 있게 합니다.
        if _is_placeholder_content(value):
            cleaned[name] = (
                f"[생성 실패] {name} 블록에 실제 콘텐츠가 아니라 "
                f"상태 문구만 반환되었습니다. AI 결과 원문을 확인하거나 다시 생성하세요."
            )
            continue

        if name == "WORDPRESS_SEO":
            value = _normalize_wordpress_seo_block(value)

        cleaned[name] = value

    return cleaned


def parse_result_blocks(text: str) -> tuple:
    """
    ChatGPT의 원문 결과 텍스트를 받아 각 [BLOCK:블록명] 단위로 파싱하여 딕셔너리로 반환합니다.
    
    Returns:
        tuple: (parsed_blocks_dict, extracted_body_str)
    """
    body = extract_primary_code_block(text)
    # 블록 라벨 앞뒤 공백, BLOCK : NAME 처럼 약간 흔들린 형식도 허용합니다.
    pattern = re.compile(r"^\s*\[\s*BLOCK\s*:\s*([A-Z0-9_]+)\s*\]\s*$", flags=re.MULTILINE)
    matches = list(pattern.finditer(body))
    if not matches:
        return {}, body

    parsed = {}
    for idx, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        value = body[start:end].strip()

        # 같은 BLOCK이 뒤에서 다시 나오더라도,
        # 첫 번째 정상 콘텐츠를 상태 문구가 덮어쓰지 못하게 방어합니다.
        if name in parsed:
            if _is_placeholder_content(value):
                continue
            if parsed.get(name) and not _is_placeholder_content(parsed.get(name)):
                continue

        parsed[name] = value

    # AI가 실제 콘텐츠 대신 "확인 완료" 같은 상태 메시지만 반환하거나,
    # WORDPRESS_SEO 라벨 형식을 흔들어도 화면 출력 전에 1차 보정합니다.
    parsed = _normalize_parsed_blocks(parsed)

    # AI 모델이 줄바꿈 규칙을 지키지 않아도,
    # StoryMaker가 최종 파싱 단계에서 모바일 가독성을 강제 보정합니다.
    # 적용 대상은 blog_formatter.py에서 관리합니다.
    parsed = format_blocks_for_mobile(parsed, line_limit=22)

    return parsed, body


def join_result_blocks(block_names: list, block_values: dict) -> str:
    """
    여러 블록 이름 리스트와 값 딕셔너리를 받아 마크다운 포맷으로 합쳐서 반환합니다.
    """
    chunks = []
    for block_name in block_names:
        content = (block_values.get(block_name) or "").strip()
        if not content:
            continue
        label = RESULT_BLOCK_LABELS.get(block_name, block_name)
        chunks.append(f"## {label}\n\n{content}")
        
    return "\n\n".join(chunks).strip()
