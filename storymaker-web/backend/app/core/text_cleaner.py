# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드용 text_cleaner 모듈
기존 Tkinter UI 종속성이 제거된 순수 비즈니스 로직입니다.
"""
import re

def strip_markdown(text: str) -> str:
    """
    텍스트에서 마크다운 요소(#, ##, -, *, **, __, ``` 등)를 제거하여 순수 텍스트로 만듭니다.
    """
    text = re.sub(r"^#\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^###\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"^```[A-Za-z0-9_-]*\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return text.strip()


def remove_trailing_hashtag_lines(text: str) -> str:
    """
    본문 텍스트 마지막 부분에 연달아 나오는 해시태그 행을 제거합니다.
    """
    lines = (text or "").splitlines()
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        # 공백으로 나누었을 때 모든 토큰이 #으로 시작하면 해시태그 라인으로 간주
        if last.startswith("#") and all(token.startswith("#") for token in last.split()):
            lines.pop()
            continue
        break
    return "\n".join(lines).strip()


def normalize_podcast_block(text: str) -> str:
    """
    팟캐스트 대본 블록에서 화자 태그를 단독 행으로 정돈합니다.
    Supertonic 기본 화자 #M1~#M5, #F1~#F5는 그대로 보존합니다.
    구형 OpenAI 음성 태그만 웹 호환 태그로 보정합니다.
    """
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []

    speaker_pattern = re.compile(r"^(#(?:onyx|alloy|fable|nova|echo|shimmer|speech|M[1-5]|F[1-5]))\s*[:\-]?\s*(.*)$", re.IGNORECASE)

    def normalize_tag(tag: str) -> str:
        raw = tag.strip().lstrip("#")
        upper = raw.upper()
        if re.fullmatch(r"[MF][1-5]", upper):
            return f"#{upper}"
        low = raw.lower()
        if low in {"alloy", "onyx", "shimmer"}:
            return "#F1"
        return "#M1"

    for raw in lines:
        line = raw.strip()
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue

        m = speaker_pattern.match(line)
        if m:
            tag = normalize_tag(m.group(1))
            speech = m.group(2).strip()

            if out and out[-1] != "":
                out.append("")
            out.append(tag)
            if speech:
                out.append(speech)
            continue

        out.append(line)

    cleaned = []
    blank = False
    for line in out:
        if line == "":
            if not blank:
                cleaned.append(line)
            blank = True
        else:
            cleaned.append(line)
            blank = False

    return "\n".join(cleaned).strip()
