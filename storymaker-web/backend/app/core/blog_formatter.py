# -*- coding: utf-8 -*-
"""
StoryMaker 네이버 블로그 모바일 가독성 포맷터

역할:
- AI가 만든 BLOG_POST를 네이버 블로그 모바일 가독성에 맞게 후처리합니다.
- 문장 끝에는 빈 줄을 넣고, 긴 줄은 단어 단위로 22자 전후에서 줄바꿈합니다.
- [핵심], [포인트], [실무 팁] 라벨은 박스 없이 강조 라벨로 변환합니다.

주의:
- [BLOCK:...] 구조는 result_parser에서 분리된 뒤 BLOG_POST 내용에만 적용하는 것을 전제로 합니다.
- HTML 박스는 네이버 붙여넣기에서 유지가 불안정하므로 사용하지 않습니다.
"""
from __future__ import annotations

import re

DEFAULT_LINE_LIMIT = 22

LABELS = ("핵심", "포인트", "실무 팁")


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("#") or stripped.startswith("##")


def _is_hashtag_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return stripped.startswith("#") and not stripped.startswith("# ")


def _is_html_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("<") and stripped.endswith(">")


def _is_list_line(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^(\d+\.|[-*•])\s+", stripped))


def _is_podcast_speaker(line: str) -> bool:
    return bool(re.match(r"^#[MF][1-5]\b", line.strip()))


def _normalize_marker_label(label: str) -> str:
    """
    라벨 표시 형식.
    네이버에서 style이 일부 제거되어도 strong/em은 상대적으로 살아남을 가능성이 높습니다.
    """
    return (
        f'<span class="storymaker-marker-label" '
        f'style="font-size:1.16em;font-weight:700;">'
        f'<strong><em>"{label}"</em></strong>'
        f'</span>'
    )


def _split_marker(line: str) -> tuple[str | None, str]:
    """
    [핵심] 내용 / [포인트] 내용 / [실무 팁] 내용을 감지합니다.
    """
    stripped = line.strip()
    m = re.match(r"^\[(핵심|포인트|실무 팁)\]\s*(.*)$", stripped)
    if not m:
        return None, line
    return m.group(1), m.group(2).strip()


def _wrap_words(text: str, limit: int = DEFAULT_LINE_LIMIT) -> str:
    """
    공백 기준 단어 단위 줄바꿈.
    단어 중간은 절대 자르지 않습니다.
    """
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""

    words = text.split(" ")
    lines: list[str] = []
    current = ""

    for word in words:
        if not current:
            current = word
            continue

        candidate = f"{current} {word}"
        if len(candidate) <= limit:
            current = candidate
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return "\n".join(lines)


def _split_sentences(text: str) -> list[str]:
    """
    한국어/영문 문장부호 기준 문장 분리.
    마침표, 물음표, 느낌표 뒤에서 나누되 소수점/URL은 깊게 다루지 않습니다.
    """
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []

    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _format_plain_paragraph(text: str, limit: int = DEFAULT_LINE_LIMIT) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return ""

    chunks = []
    for sentence in sentences:
        chunks.append(_wrap_words(sentence, limit=limit))
    return "\n\n".join(chunks)


def _format_marker_block(label: str, content: str, limit: int = DEFAULT_LINE_LIMIT) -> str:
    """
    [핵심] / [포인트] / [실무 팁]을 박스 없이 강조 라벨 + 본문으로 변환.
    """
    label_html = _normalize_marker_label(label)
    body = _format_plain_paragraph(content, limit=limit) if content else ""
    if body:
        return f"{label_html}\n\n{body}"
    return label_html


def _clean_blank_lines(text: str) -> str:
    """
    빈 줄은 최대 1개 빈 줄, 즉 개행 2개까지만 유지.
    """
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_naver_blog(text: str, line_limit: int = DEFAULT_LINE_LIMIT) -> str:
    """
    네이버 블로그용 모바일 가독성 포맷터.

    적용:
    - BLOG_POST 본문
    - 긴 문장 단어 단위 줄바꿈
    - 문장 사이 빈 줄
    - [핵심], [포인트], [실무 팁] 라벨 강조

    제외:
    - 제목(#, ##)
    - 해시태그 라인
    - HTML 라인
    - 리스트 라인
    - 팟캐스트 화자 태그
    """
    if not text:
        return ""

    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []

    buffer: list[str] = []

    def flush_buffer() -> None:
        nonlocal buffer
        if not buffer:
            return
        paragraph = " ".join(x.strip() for x in buffer if x.strip())
        if paragraph:
            out.append(_format_plain_paragraph(paragraph, limit=line_limit))
        buffer = []

    for raw in raw_lines:
        line = raw.strip()

        if not line:
            flush_buffer()
            if out and out[-1] != "":
                out.append("")
            continue

        marker, marker_body = _split_marker(line)
        if marker:
            flush_buffer()
            out.append(_format_marker_block(marker, marker_body, limit=line_limit))
            out.append("")
            continue

        if (
            _is_heading(line)
            or _is_hashtag_line(line)
            or _is_html_line(line)
            or _is_list_line(line)
            or _is_podcast_speaker(line)
        ):
            flush_buffer()
            out.append(line)
            out.append("")
            continue

        buffer.append(line)

    flush_buffer()

    return _clean_blank_lines("\n".join(out))


# 하위 호환용 별칭
format_blog_mobile = format_naver_blog


MOBILE_FORMAT_TARGET_BLOCKS = {
    "BLOG_POST",
    "CARROT_POST",
    "INSTAGRAM_POST",
    "NAVER_PLACE_NEWS",
    "GOOGLE_BUSINESS_POST",
}


def format_blocks_for_mobile(blocks: dict, line_limit: int = DEFAULT_LINE_LIMIT) -> dict:
    """
    result_parser에서 호출하는 블록 단위 모바일 포맷터입니다.

    기존 result_parser는 app.core.blog_formatter.format_blocks_for_mobile을
    import하도록 되어 있었지만, 실제 blog_formatter.py에는 이 함수가 없어
    환경에 따라 조용히 fallback 처리될 수 있었습니다.

    WORDPRESS_SEO는 HTML 구조가 깨질 수 있어 여기서는 건드리지 않습니다.
    """
    formatted = dict(blocks or {})
    for name in MOBILE_FORMAT_TARGET_BLOCKS:
        if name in formatted and formatted.get(name):
            formatted[name] = format_naver_blog(str(formatted[name]), line_limit=line_limit)
    return formatted
