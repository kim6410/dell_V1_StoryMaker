# -*- coding: utf-8 -*-
"""한국 전화번호 표시 및 TTS 발음 정규화."""
from __future__ import annotations

import re


DIGIT_KO = {
    "0": "공", "1": "일", "2": "이", "3": "삼", "4": "사",
    "5": "오", "6": "육", "7": "칠", "8": "팔", "9": "구",
}


def normalize_korean_phone_number(value: str | None) -> str:
    """입력 형식과 관계없이 지원 전화번호를 표준 하이픈 형식으로 반환합니다."""
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)

    if len(digits) == 12 and digits.startswith("0507"):
        return f"{digits[:4]}-{digits[4:8]}-{digits[8:]}"
    if len(digits) == 11 and digits.startswith("010"):
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if len(digits) == 10 and digits.startswith("02"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return raw


def phone_numbers_for_tts(text: str | None) -> str:
    """전화번호만 숫자별 한국어 발음으로 바꿉니다."""
    pattern = re.compile(
        r"(?<!\d)(?:0507[-.\s]?\d{4}[-.\s]?\d{4}|01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}|0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4})(?!\d)"
    )

    def read_digits(value: str) -> str:
        return "".join(DIGIT_KO.get(ch, ch) for ch in value)

    def convert(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) == 12 and digits.startswith("0507"):
            groups = (digits[:4], digits[4:8], digits[8:])
        elif len(digits) == 11:
            groups = (digits[:3], digits[3:7], digits[7:])
        elif len(digits) == 10 and digits.startswith("02"):
            groups = (digits[:2], digits[2:6], digits[6:])
        elif len(digits) == 10:
            groups = (digits[:3], digits[3:6], digits[6:])
        else:
            groups = (digits,)
        return ", ".join(read_digits(group) for group in groups)

    return pattern.sub(convert, str(text or ""))
