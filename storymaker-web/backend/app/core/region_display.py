from __future__ import annotations

import re

_REGION_PREFIX_ALIASES = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원도",
    "강원도": "강원도",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전라북도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
}


def format_region_display(value: str | None) -> str:
    """Return the natural Korean display form while preserving lower-level names."""
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return ""
    for official, alias in _REGION_PREFIX_ALIASES.items():
        if text == official:
            return alias
        if text.startswith(official + " "):
            return alias + text[len(official):]
    return text


def format_region_text(value: str | None) -> str:
    """Replace official province/city prefixes anywhere in free-form text."""
    text = str(value or "")
    if not text:
        return ""
    for official, alias in _REGION_PREFIX_ALIASES.items():
        text = text.replace(official, alias)
    return text


def normalize_region_search_text(value: str | None) -> str:
    text = format_region_display(value).lower()
    return re.sub(r"\s+", "", text)
