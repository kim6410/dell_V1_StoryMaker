# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드용 keyword_extractor 모듈
기존 Tkinter UI 종속성이 제거된 순수 비즈니스 로직입니다.
"""
import re
from collections import Counter

KEYWORD_MIN_LEN = 2
KEYWORD_BLACKLIST = {
    "그리고", "하지만", "그래서", "정말", "이번", "여기", "저기", "그냥", "내용", "작업", "작성",
    "참고자료", "기초내용", "입력", "예정", "사용", "포함", "자연스럽게", "중심", "현장", "기반",
    "있는", "하는", "하게", "하기", "대한", "또한", "위해", "또는", "이후", "가장", "많은",
    "때문", "통해", "형태", "부분", "경우", "정도", "우리", "업체", "고객", "블로그", "당근",
    "포스팅", "콘텐츠", "키워드", "프롬프트", "소상공인", "지역", "설명", "문장", "문단", "제목",
    "입니다", "있습니다", "합니다", "되어", "되는", "같은", "실제로", "바로", "이렇게", "저희"
}

def extract_keyword_candidates(*texts: str) -> list:
    """
    여러 기초 자료 텍스트들로부터 빈도수 기반 키워드 추천 후보 리스트를 추출하여 반환합니다.
    형태소 분석 대신 정규식을 기반으로 간결하게 단어를 추출하며, 블랙리스트를 필터링합니다.
    
    Returns:
        list: [(키워드, 빈도수), ...] 형태의 리스트 (빈도수 기준 내림차순 정렬)
    """
    combined = "\n".join(t for t in texts if t)
    if not combined.strip():
        return []

    # 한글, 영문, 숫자, + # 기호가 포함된 단어 토큰 추출
    tokens = re.findall(r"[가-힣A-Za-z0-9+#]{2,}", combined)
    cleaned = []
    for token in tokens:
        token = token.strip("#").strip()
        if len(token) < KEYWORD_MIN_LEN:
            continue
        if token.isdigit():
            continue
        if token in KEYWORD_BLACKLIST:
            continue
        cleaned.append(token)

    counts = Counter(cleaned)
    # 빈도수 기준 내림차순 정렬하여 반환
    return counts.most_common()
