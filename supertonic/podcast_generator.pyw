# -*- coding: utf-8 -*-
# supertonic_podcast_generator_v2_m1f5.py
"""
Supertonic3 팟캐스트 생성기 v2.0
- Supertonic 기본 화자: M1~M5, F1~F5
- M1~F5 기본 화자 매핑 + 화자별 속도 조절
- Supertonic3 기본 화자 기반 팟캐스트 생성
- AI 프롬프트 최적화 (문장부호 완전 정복)
- 설정값 자동 저장
- 음악 미리듣기 지원 (볼륨 30% 정상화)
- MP3 생성 오류 수정 완료
- 도움말 팝업 버튼 추가
- 감정 태그 삽입 UI 추가
- 도움말 외부 TXT 파일 분리
- 통합 플레이어 위치 최적화
- TTS 설정 영역 확장 (100%)
- 사람 목소리 볼륨 조절 추가
- 실시간 미리듣기 (TTS+음악 믹싱)
"""

from __future__ import annotations

# ===== 🔥 콘솔 숨김 코드 추가 =====
import sys
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass
# =================================

import os
import sys
import re
import time
import json
import random
import threading
import tempfile
import subprocess
import asyncio
import traceback
import shutil
import math
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
if "--no-gui" in sys.argv:
    tk = filedialog = messagebox = ctk = pygame = None
else:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import customtkinter as ctk
    import pygame
import numpy as np

# =============================================================================
# DPI 인식 설정 (Windows)
# =============================================================================
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# =============================================================================
# 설정 및 상수
# =============================================================================
@dataclass
class Config:
    """프로그램 설정"""
    SCRIPT_DIR: str = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
    OUTPUT_DIR: str = ""
    MUSIC_DIR: str = ""
    CACHE_DIR: str = ""
    
    # OpenAI 설정
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    
    # 오디오 설정
    SAMPLE_RATE: int = 48000
    INTRO_MUSIC: float = 0.1
    OUTRO_MUSIC: float = 5.0
    FADE_IN: float = 0.5
    FADE_OUT: float = 5.0
    MUSIC_VOLUME: float = 0.15  # 기본 음악 볼륨 15% (슬라이더 체감이 나도록 상향)
    VOICE_VOLUME: float = 1.60   # 사람 목소리 기본 볼륨 160%
    
    # TTS 설정
    DEFAULT_SPEED: float = 1.0
    DEFAULT_PITCH: int = 0
    DEFAULT_VOLUME: int = 0
    MIN_TEXT_LENGTH: int = 3
    TTS_ENGINE: str = "supertonic"

    # Supertonic 3 로컬 TTS 설정
    # - 설치/서버 기준 경로는 /home/bourne/StoryMaker_1/Supertonic3 로 고정합니다.
    # - 권장 구조: /home/bourne/StoryMaker_1/Supertonic3/.venv에서 supertonic serve를 먼저 실행하고,
    #   이 프로그램은 HTTP로 127.0.0.1:7788을 호출합니다.
    # - 서버가 꺼져 있으면 같은 PC의 Python 환경에 supertonic 패키지가 있을 때 SDK 직접 호출로 자동 fallback합니다.
    # - RTX 3060 Ti 강제 사용은 Supertonic serve/ONNX Runtime/WebGPU 지원 경로 확인 후 별도 적용해야 합니다.
    SUPERTONIC_HOME: str = "/home/bourne/StoryMaker_1/Supertonic3"
    SUPERTONIC_SERVER_URL: str = "http://127.0.0.1:7789"
    SUPERTONIC_USE_SERVER_FIRST: bool = True
    SUPERTONIC_LANG: str = "ko"
    SUPERTONIC_TOTAL_STEPS: int = 8
    SUPERTONIC_DEFAULT_MALE: str = "M1"
    SUPERTONIC_DEFAULT_FEMALE: str = "F1"
    SUPERTONIC_FALLBACK_MALE: str = "M1"
    SUPERTONIC_FALLBACK_FEMALE: str = "F1"
    
    # 병렬 처리 설정
    MAX_CONCURRENT_TTS: int = 3

    # Supertonic 안정화 설정
    # 속도를 너무 높이면 일부 문장이 잘리는 경우가 있어 내부 상한을 둡니다.
    SUPERTONIC_MIN_SPEED: float = 0.85
    SUPERTONIC_MAX_SPEED: float = 1.30
    TTS_CHUNK_SILENCE_MS: int = 90
    TTS_MIN_CHUNK_DURATION: float = 0.30
    
    # 폰트 설정
    FONT_FAMILY: str = "Malgun Gothic"  # 강제 고정
    
    # ===== Supertonic3 기본 화자 설정 =====
    # 실제로 구분되는 기본 화자는 M1~M5, F1~F5입니다.
    # 화면에는 사람이름을 함께 보여주지만, TTS 생성에는 M1/F1 같은 ID만 전달합니다.
    CAST_MEMBERS: list = field(default_factory=lambda: [
        "M1", "M2", "M3", "M4", "M5", "F1", "F2", "F3", "F4", "F5"
    ])

    VOICE_DISPLAY_NAMES: dict = field(default_factory=lambda: {
        "M1": "James",
        "M2": "Liam",
        "M3": "Noah",
        "M4": "William",
        "M5": "Ethan",
        "F1": "Olivia",
        "F2": "Ava",
        "F3": "Emma",
        "F4": "Mia",
        "F5": "Sophia",
    })

    CAT_ALIASES: dict = field(default_factory=lambda: {
        "M1": ["M1", "James"],
        "M2": ["M2", "Liam"],
        "M3": ["M3", "Noah"],
        "M4": ["M4", "William"],
        "M5": ["M5", "Ethan"],
        "F1": ["F1", "Olivia"],
        "F2": ["F2", "Ava"],
        "F3": ["F3", "Emma"],
        "F4": ["F4", "Mia"],
        "F5": ["F5", "Sophia"],
    })

    CAT_GENDERS: dict = field(default_factory=lambda: {
        "M1": "male", "M2": "male", "M3": "male", "M4": "male", "M5": "male",
        "F1": "female", "F2": "female", "F3": "female", "F4": "female", "F5": "female",
    })

    CAT_VOICE_MAPPING: dict = field(default_factory=lambda: {
        "M1": "M1", "M2": "M2", "M3": "M3", "M4": "M4", "M5": "M5",
        "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4", "F5": "F5",
    })

    CAT_SPEED_MAPPING: dict = field(default_factory=lambda: {
        "M1": 1.00,
        "M2": 1.02,
        "M3": 0.98,
        "M4": 1.05,
        "M5": 0.96,
        "F1": 1.03,
        "F2": 1.05,
        "F3": 1.00,
        "F4": 0.98,
        "F5": 0.97,
    })

    # Edge/OpenAI 호환용 보정값입니다. Supertonic3에서는 속도 위주로 사용합니다.
    CAT_EDGE_STYLE: dict = field(default_factory=lambda: {
        "M1": {"speed": 1.00, "pitch": -1, "volume": 0},
        "M2": {"speed": 1.02, "pitch": 1, "volume": 0},
        "M3": {"speed": 0.98, "pitch": -2, "volume": 0},
        "M4": {"speed": 1.05, "pitch": 2, "volume": 1},
        "M5": {"speed": 0.96, "pitch": -3, "volume": 0},
        "F1": {"speed": 1.03, "pitch": 2, "volume": 1},
        "F2": {"speed": 1.05, "pitch": 3, "volume": 1},
        "F3": {"speed": 1.00, "pitch": 1, "volume": 0},
        "F4": {"speed": 0.98, "pitch": 0, "volume": 0},
        "F5": {"speed": 0.97, "pitch": 2, "volume": -1},
    })

    VOICE_TO_CAT: dict = field(default_factory=lambda: {
        "M1": "M1", "M2": "M2", "M3": "M3", "M4": "M4", "M5": "M5",
        "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4", "F5": "F5",
    })

    CAT_DESCRIPTIONS: dict = field(default_factory=lambda: {
        "M1": "남성 기본 화자 1 / James",
        "M2": "남성 기본 화자 2 / Liam",
        "M3": "남성 기본 화자 3 / Noah",
        "M4": "남성 기본 화자 4 / William",
        "M5": "남성 기본 화자 5 / Ethan",
        "F1": "여성 기본 화자 1 / Olivia",
        "F2": "여성 기본 화자 2 / Ava",
        "F3": "여성 기본 화자 3 / Emma",
        "F4": "여성 기본 화자 4 / Mia",
        "F5": "여성 기본 화자 5 / Sophia",
    })

    def get_voice_display_name(self, name: str) -> str:
        voice_id = self.normalize_cat_name(name)
        display = self.VOICE_DISPLAY_NAMES.get(voice_id, voice_id)
        return f"{voice_id} - {display}" if display != voice_id else voice_id

    def normalize_cat_name(self, name: str) -> str:
        """M1~F5 또는 표시 이름(James 등)을 실제 voice_id로 정규화"""
        raw = (name or "").strip()
        raw = raw.split(" - ", 1)[0].strip() if " - " in raw else raw
        raw_upper = raw.upper()
        for cat_name, aliases in self.CAT_ALIASES.items():
            alias_upper = [str(a).upper() for a in aliases]
            if raw_upper == cat_name.upper() or raw_upper in alias_upper:
                return cat_name
        return raw

    def get_cat_gender(self, name: str) -> str:
        return self.CAT_GENDERS.get(self.normalize_cat_name(name), "male")

    def get_cat_edge_style(self, name: str) -> Dict[str, float]:
        cat_name = self.normalize_cat_name(name)
        return self.CAT_EDGE_STYLE.get(cat_name, {"speed": 1.0, "pitch": 0, "volume": 0})

    def __post_init__(self):
        self.OUTPUT_DIR = os.path.join(self.SCRIPT_DIR, "output", "팟캐스트")
        self.MUSIC_DIR = os.path.join(self.SCRIPT_DIR, "음악")
        self.CACHE_DIR = os.path.join(self.SCRIPT_DIR, "tts_cache")
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.MUSIC_DIR, exist_ok=True)
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        
        self._load_api_key()
    
    def _load_api_key(self):
        key_file = os.path.join(self.SCRIPT_DIR, "openai_key.txt")
        if os.path.exists(key_file):
            try:
                with open(key_file, 'r', encoding='utf-8') as f:
                    self.OPENAI_API_KEY = f.read().strip()
            except:
                pass

CONFIG = Config()

# =============================================================================
# 폰트 관리 클래스 (강제 고정)
# =============================================================================
class FontManager:
    def __init__(self):
        self.font_family = "Malgun Gothic"
        self.font_cache = {}
        self.font_sizes = {
            'title': 22, 'subtitle': 17, 'heading': 16,
            'body': 12, 'small': 10, 'button_large': 15,
            'button_normal': 13, 'button_small': 11, 'subtitle_large': 15
        }
        print(f"[FONT] 한글 폰트 강제 고정: {self.font_family}")
    
    def get_font(self, size_key: str = 'body', weight: str = "normal") -> ctk.CTkFont:
        cache_key = f"{size_key}_{weight}"
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]
        
        size = self.font_sizes.get(size_key, 14)
        try:
            font = ctk.CTkFont(family=self.font_family, size=size, weight=weight)
        except:
            font = ctk.CTkFont(size=size, weight=weight)
        
        self.font_cache[cache_key] = font
        return font
    
    def get_custom_font(self, size: int, weight: str = "normal") -> ctk.CTkFont:
        cache_key = f"custom_{size}_{weight}"
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]
        
        try:
            font = ctk.CTkFont(family=self.font_family, size=size, weight=weight)
        except:
            font = ctk.CTkFont(size=size, weight=weight)
        
        self.font_cache[cache_key] = font
        return font

# =============================================================================
# UI 테마 - 명시적 색상 정의 (부모 영향 차단)
# =============================================================================
COLOR_THEME = {
    "primary": "#1E4A7A", 
    "primary_hover": "#2A5F9A",
    "background": "#0A1428", 
    "surface": "#1A2740",
    "surface_light": "#25344F", 
    "text_primary": "#FFFFFF",      # 흰색
    "text_secondary": "#A0B8D0",    # 부드러운 회청색
    "text_accent": "#7AC7FF",       # 하늘색
    "success": "#2FB87E", 
    "warning": "#F59E0B",
    "error": "#FF4444", 
    "border": "#3A5680",
    "progress": "#4AA0E0"
}

# =============================================================================
# OpenAI TTS 음성 설정
# =============================================================================
OPENAI_ALL_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

OPENAI_VOICE_DESC = {
    "alloy": "균형 잡힌 중립적 음성",
    "echo": "남성적이고 깊은 음성",
    "fable": "영국식 악센트의 따뜻한 음성",
    "onyx": "남성적이고 자신감 있는 음성",
    "nova": "여성적이고 밝은 음성",
    "shimmer": "여성적이고 맑은 음성"
}

# =============================================================================
# Supertonic 3 TTS 음성 설정
# =============================================================================
SUPERTONIC_ALL_VOICES = ["M1", "M2", "M3", "M4", "M5", "F1", "F2", "F3", "F4", "F5"]

SUPERTONIC_VOICE_DESC = {
    "M1": "남성 기본 화자 1 / James",
    "M2": "남성 기본 화자 2 / Liam",
    "M3": "남성 기본 화자 3 / Noah",
    "M4": "남성 기본 화자 4 / William",
    "M5": "남성 기본 화자 5 / Ethan",
    "F1": "여성 기본 화자 1 / Olivia",
    "F2": "여성 기본 화자 2 / Ava",
    "F3": "여성 기본 화자 3 / Emma",
    "F4": "여성 기본 화자 4 / Mia",
    "F5": "여성 기본 화자 5 / Sophia",
}

SUPERTONIC_CAT_VOICE_MAPPING = {v: v for v in SUPERTONIC_ALL_VOICES}

# Supertonic 직접 화자 태그용 성별 매핑
# 예: #M1 / #F1 같은 화자 태그를 정확히 인식하기 위한 기준표입니다.
# 실제 Supertonic 음성 이름 그대로 넘기기 위한 기준표입니다.
SUPERTONIC_VOICE_GENDER = {
    "M1": "male", "M2": "male", "M3": "male", "M4": "male", "M5": "male",
    "F1": "female", "F2": "female", "F3": "female", "F4": "female", "F5": "female",
}

# =============================================================================
# 효과 설정
# =============================================================================
EFFECT_PRESETS = {
    'cheerful': {'speed': 1.15, 'pitch': 6, 'volume': 3, 'desc': '밝고 활기차게'},
    'calm': {'speed': 0.85, 'pitch': -4, 'volume': -1, 'desc': '차분하게'},
    'serious': {'speed': 0.9, 'pitch': -3, 'volume': 2, 'desc': '진지하게'},
    'excited': {'speed': 1.25, 'pitch': 10, 'volume': 4, 'desc': '흥분해서'},
    'whisper': {'speed': 0.85, 'pitch': 2, 'volume': -12, 'desc': '속삭이듯'},
    'left': {'pan': -0.8, 'desc': '왼쪽에서'},
    'right': {'pan': 0.8, 'desc': '오른쪽에서'},
    'echo': {'afilter': 'aecho=0.8:0.88:60:0.4', 'desc': '메아리'},
    'reverb': {'afilter': 'aecho=0.8:0.85:50:0.3', 'desc': '잔향'},
}

# =============================================================================
# AI 프롬프트 예제
# =============================================================================
AI_PROMPT_EXAMPLE = """#M1
안녕하세요. 오늘의 팟캐스트를 시작합니다.

#F1
반갑습니다! 오늘은 수퍼토닉 쓰리 기본 화자를 테스트해볼게요오오!!!

#M2
대본은 이렇게 샵 기호 뒤에 화자 ID를 쓰면 됩니다.

#F2
감정을 살리고 싶다면... 말줄임표, 느낌표!!! 그리고 길게 늘인 표현을 사용해보세요오오~~~

#M3
속도를 올리면 조금 더 경쾌해지고, 낮추면 차분한 느낌이 납니다.

#F3
단, 속도를 너무 높이면 일부 문장이 끊길 수 있으니 1.10 이하를 권장합니다.

#M4
캐시가 켜져 있으면 같은 문장과 같은 화자는 다시 생성하지 않고 저장된 음성을 재사용합니다.

#F4
그래서 반복되는 인트로와 마무리 멘트는 두 번째부터 훨씬 빨라집니다!

#M5
지금까지 남성 기본 화자 테스트였습니다.

#F5
이제 여성 기본 화자까지 모두 확인했습니다. 다음 방송에서 만나요오오!!!
"""

# =============================================================================
# 샘플 TTS 텍스트
# =============================================================================
SAMPLE_TTS_TEXT = "안녕하세요. 이것은 샘플 TTS 음성입니다. 현재 설정된 속도와 볼륨으로 들리고 있습니다."


# =============================================================================
# Supertonic3 감정 태그 / 외부 도움말
# =============================================================================
# 실제 테스트 기준으로 안정적으로 먹는 감정 태그와
# 태그 효과가 약하거나 동작하지 않는 항목을 분리합니다.
# - <surprise>, <throatclear>는 일부 Supertonic3 로컬 서버 버전에서 효과가 적용되지 않거나
#   그대로 읽히는 경우가 있어 기본 버튼은 자연어 문구 삽입 방식으로 처리합니다.
EMOTION_TAGS = [
    ("laugh", "웃음"),
    ("breath", "숨"),
    ("sigh", "한숨"),
    ("scream", "비명"),
    ("sad", "슬픔"),
    ("angry", "화남"),
    ("cough", "기침"),
    ("yawn", "하품"),
    ("surprise_text", "놀람문구"),
    ("throatclear_text", "에헴문구"),
]

EMOTION_INSERT_TEXT = {
    "surprise_text": "와아아!!! ",
    "throatclear_text": "에헴, ",
}

EMOTION_BUTTON_TEXT = {
    "surprise_text": "와아아!!!",
    "throatclear_text": "에헴,",
}

# SRT에는 음성 제어용 태그가 보이면 안 되므로 자막 생성 시 제거합니다.
# 혹시 사용자가 직접 <surprise>, <throatclear>를 입력해도 자막에서는 깔끔하게 빠집니다.
TTS_CONTROL_TAG_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9_-]*)>")

DEFAULT_HELP_TEXT = """📌 Supertonic3 팟캐스트 생성기 도움말
═══════════════════════════════════════════════════════════

1. 대본 입력 방법
───────────────────────────────────────────────────────
화자는 줄 맨 앞에 #M1, #F1처럼 입력합니다.
그 다음 줄부터 해당 화자가 읽을 대사를 입력합니다.

예시:
#M1
안녕하세요. 오늘의 팟캐스트를 시작합니다.

#F1
반갑습니다! 오늘 주제가 정말 기대되는데요오오!!!

지원 화자:
M1, M2, M3, M4, M5
F1, F2, F3, F4, F5

표시 이름:
M1 - James
M2 - Liam
M3 - Noah
M4 - William
M5 - Ethan
F1 - Olivia
F2 - Ava
F3 - Emma
F4 - Mia
F5 - Sophia

2. 감정 표현을 살리는 법
───────────────────────────────────────────────────────
TTS는 문장부호, 글자 반복, 감정 태그에 민감하게 반응합니다.

기본:
정말 놀랐어요.

감정 강조:
정말요오오오???
와아아아아!!! 대박이에요!!!!!
흐으으으... 이건 조금 아쉽네요...

권장 표현:
...  여운, 망설임, 감정선
!!!  놀람, 기쁨, 강조
???  질문, 당황
~~~  부드러운 여운
아아아, 와아아, 흐으으  감정 확대

3. 감정 태그 삽입
───────────────────────────────────────────────────────
대본 입력창 위의 감정 버튼을 누르면 커서 위치에 태그가 자동으로 삽입됩니다.

지원 태그:
<laugh>        웃음
<breath>       숨소리
와아아!!!       놀람 문구 대체 삽입
<sigh>         한숨
<scream>       비명
에헴,          목 가다듬기 문구 대체 삽입
<sad>          슬픔
<angry>        화남
<cough>        기침
<yawn>         하품

사용 예시:
#F1
안녕하세요오오!! <laugh> 오늘은 정말 반가워요!

#M1
<breath> 잠깐 숨을 고르고... 다시 이야기해보겠습니다.

#F2
와아아!!! 이건 정말 놀라운데요?

#M2
<angry> 오늘은 조금 단호하게 말해야겠습니다.

주의:
감정 태그는 #F1, #M1 같은 화자 태그 아래의 실제 대사 안에 넣습니다.
감정 태그를 너무 많이 넣으면 음성이 과장되거나 어색해질 수 있습니다.

4. 다국어 자동 인식
───────────────────────────────────────────────────────
Supertonic3는 문장의 언어를 자동으로 인식합니다.

따라서 별도의 언어 설정 없이
한국어, 영어, 일본어, 프랑스어, 독일어, 스페인어 등 여러 언어를 하나의 대본 안에서 함께 사용할 수 있습니다.

예시:
#F1
안녕하세요. 오늘 팟캐스트에 오신 것을 환영합니다.

#M1
Hello everyone. Thank you for joining us today.

#F2
こんにちは。今日はよろしくお願いします。

#M2
Bonjour. Merci beaucoup.

#F3
Guten Tag. Schön, dass Sie da sind.

#M3
Hola amigos. Bienvenidos a nuestro programa.

혼합 사용 예시:
#F1
안녕하세요.
Today we will talk about Artificial Intelligence.
そして未来の技術についても話してみましょう。

활용 예시:
다국어 팟캐스트
외국어 학습 콘텐츠
여행 회화 콘텐츠
글로벌 뉴스 브리핑
언어별 발음 테스트

주의:
언어마다 발음 품질 차이가 있을 수 있습니다.
중국어, 태국어 등 일부 언어는 버전에 따라 품질 차이가 발생할 수 있으므로 직접 테스트하는 것이 좋습니다.

5. 속도 조절
───────────────────────────────────────────────────────
전체 속도는 모든 화자에게 공통 적용됩니다.
화자별 속도는 각 M1~F5 카드의 슬라이더에서 조절합니다.

최종 속도 계산:
화자별 속도 × 전체 속도

예시:
F1 화자별 속도 = 1.10
전체 속도 = 1.50
최종 재생 속도 = 1.65배

추천 범위:
화자별 0.90 ~ 1.10
전체 0.80 ~ 2.00

속도가 높을수록 전체 길이는 짧아지고,
속도가 낮을수록 자연스럽고 차분한 분위기가 됩니다.

6. 캐시 사용
───────────────────────────────────────────────────────
캐시를 켜면 같은 화자, 같은 문장, 같은 속도의 음성을 다시 생성하지 않고 재사용합니다.
반복되는 인트로, 마무리 멘트, 안내 문구는 두 번째부터 매우 빨라집니다.

속도나 감정 태그가 달라지면 다른 음성으로 판단되어 새로 생성될 수 있습니다.

7. 파일명 저장
───────────────────────────────────────────────────────
타이틀을 입력하지 않아도 자동으로 날짜와 시간 파일명이 생성됩니다.
예:
2026-01-07_153045.mp3

직접 이름을 쓰면 다음처럼 저장됩니다.
예:
podcast_2026-01-07_153045.mp3

8. 짧은 테스트 대본
───────────────────────────────────────────────────────
#M1
안녕하세요. 저는 엠 원입니다.

#F1
안녕하세요오오!!! 저는 에프 원입니다! <laugh>

#M2
<breath> 속도를 조금 바꾸면 말의 분위기도 달라집니다.

#F2
<surprise> 와아아아!!! 감정 표현도 한번 확인해볼게요오오~~~

═══════════════════════════════════════════════════════════
"""

# =============================================================================
# TTS 캐시 클래스
# =============================================================================
class TTSCache:
    def __init__(self):
        self.cache_dir = CONFIG.CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        self.hits = 0
        self.misses = 0
    
    def _get_cache_key(self, text: str, voice: str, speed: float, effects: tuple) -> str:
        effects_str = ','.join(sorted(effects)) if effects else 'none'
        key_data = f"{text}_{voice}_{speed:.2f}_{effects_str}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    def get(self, text: str, voice: str, speed: float, effects: List[str]) -> Optional[str]:
        cache_key = self._get_cache_key(text, voice, speed, tuple(sorted(effects)))
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.wav")
        
        if os.path.exists(cache_path):
            self.hits += 1
            return cache_path
        
        self.misses += 1
        return None
    
    def save(self, text: str, voice: str, speed: float, effects: List[str], file_path: str) -> str:
        cache_key = self._get_cache_key(text, voice, speed, tuple(sorted(effects)))
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.wav")
        shutil.copy2(file_path, cache_path)
        return cache_path
    
    def get_stats(self) -> str:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return f"캐시 히트: {self.hits}회, 미스: {self.misses}회, 적중률: {hit_rate:.1f}%"

# =============================================================================
# FFmpeg / subprocess 실행 유틸리티
# =============================================================================
def get_hidden_subprocess_kwargs() -> Dict[str, Any]:
    """Windows에서 ffmpeg/ffprobe 실행 시 커맨드 창이 뜨지 않도록 옵션 반환"""
    kwargs: Dict[str, Any] = {}
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs

def run_subprocess_hidden(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """모든 subprocess.run 호출을 한곳에서 처리"""
    hidden_kwargs = get_hidden_subprocess_kwargs()
    hidden_kwargs.update(kwargs)
    return subprocess.run(cmd, **hidden_kwargs)

class FFmpegUtils:
    @staticmethod
    def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        try:
            result = run_subprocess_hidden(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if check and result.returncode != 0:
                print(f"[ERROR] FFmpeg 오류: {result.stderr}")
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
            return result
        except Exception as e:
            raise RuntimeError(f"FFmpeg 실행 오류: {e}")

    @staticmethod
    def get_duration(file_path: str) -> float:
        try:
            result = run_subprocess_hidden(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                capture_output=True, text=True
            )
            return float(result.stdout.strip()) if result.returncode == 0 else 0.0
        except:
            return 0.0

# =============================================================================
# 임시 파일 관리자
# =============================================================================
class TempFileManager:
    def __init__(self):
        self.files = []
        self.dirs = []
        runtime_root = Path(__file__).resolve().parent / "temp" / "podcast_runtime"
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.runtime_dir = tempfile.mkdtemp(
            prefix=f"podcast_{os.getpid()}_",
            dir=str(runtime_root),
        )
        self.dirs.append(self.runtime_dir)
    
    def create_temp_file(self, suffix: str = ".tmp") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix, dir=self.runtime_dir)
        os.close(fd)
        self.files.append(path)
        return path
    
    def create_temp_dir(self) -> str:
        path = tempfile.mkdtemp(dir=self.runtime_dir)
        self.dirs.append(path)
        return path
    
    def cleanup(self):
        for file in self.files:
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except:
                pass
        for dir_path in reversed(self.dirs):
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            except:
                pass
        self.files.clear()
        self.dirs.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.cleanup()

# =============================================================================
# 도움말 팝업 클래스
# =============================================================================
class HelpPopup:
    def __init__(self, parent):
        self.popup = tk.Toplevel(parent)
        self.popup.title("📚 전체 도움말")
        self.popup.geometry("640x680")
        self.popup.configure(bg="#1a1e2a")
        
        self.popup.transient(parent)
        self.popup.grab_set()
        
        self.setup_ui()
        
    def setup_ui(self):
        title_frame = tk.Frame(self.popup, bg="#2c3e50", height=40)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        
        tk.Label(title_frame, text="📚 팟캐스트 생성기 전체 도움말", 
                font=("Malgun Gothic", 16, "bold"),
                fg="white", bg="#2c3e50").pack(side="left", padx=15, pady=5)
        
        tk.Button(title_frame, text="✕ 닫기", 
                 command=self.popup.destroy,
                 bg="#e74c3c", fg="white",
                 font=("Malgun Gothic", 10, "bold"),
                 relief="flat", cursor="hand2",
                 width=8).pack(side="right", padx=10, pady=5)
        
        text_frame = tk.Frame(self.popup, bg="#1a1e2a")
        text_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.text = tk.Text(text_frame, wrap="word", 
                           bg="#0a0e14", fg="#dbe5f0",
                           font=("Consolas", 11),
                           insertbackground="white",
                           relief="flat", bd=2,
                           padx=10, pady=10)
        self.text.pack(fill="both", expand=True)
        
        scrollbar = tk.Scrollbar(self.text)
        scrollbar.pack(side="right", fill="y")
        self.text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.text.yview)
        
        self.load_help_content()
        
        btn_frame = tk.Frame(self.popup, bg="#1a1e2a", height=40)
        btn_frame.pack(fill="x")
        btn_frame.pack_propagate(False)
        
        tk.Button(btn_frame, text="📋 전체 복사", 
                 command=self.copy_all,
                 bg="#3498db", fg="white",
                 font=("Malgun Gothic", 10),
                 relief="flat", cursor="hand2",
                 width=15).pack(side="left", padx=10, pady=5)
        
        tk.Label(btn_frame, text="드래그하여 원하는 부분만 복사할 수 있습니다",
                font=("Malgun Gothic", 9),
                fg="#A0B8D0", bg="#1a1e2a").pack(side="right", padx=10)
    
    def load_help_content(self):
        help_path = os.path.join(CONFIG.SCRIPT_DIR, "help_supertonic3_podcast.txt")
        try:
            if not os.path.exists(help_path):
                with open(help_path, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_HELP_TEXT)
            with open(help_path, "r", encoding="utf-8") as f:
                help_text = f.read()
        except Exception as e:
            help_text = DEFAULT_HELP_TEXT + f"\n\n[도움말 파일 로드 실패: {e}]"

        self.text.insert("1.0", help_text)
        self.text.config(state="normal")
    
    def copy_all(self):
        self.text.clipboard_clear()
        self.text.clipboard_append(self.text.get("1.0", "end-1c"))
        messagebox.showinfo("복사 완료", "전체 도움말이 클립보드에 복사되었습니다.")

# =============================================================================
# 파일명 생성 헬퍼 함수
# =============================================================================
def extract_title_from_script(script_text: str) -> str:
    """스크립트 첫 줄에서 제목 추출 (패턴 제거)"""
    lines = script_text.strip().split('\n')
    if not lines:
        return "podcast"


def sanitize_output_filename(name: str) -> str:
    """윈도우 파일명에 맞게 정리"""
    name = (name or "").strip()
    name = re.sub(r'[\\/:*?"<>|]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name
    
    first_line = lines[0].strip()
    
    # 패턴 제거 (사이 내용만 추출)
    patterns = [
        (r'^/#\s*(.+?)\s*/#$', r'\1'),     # /# 제목 #/
        (r'^<!--\s*(.+?)\s*-->$', r'\1'),  # <!-- 제목 -->
        (r'^#(.+)$', r'\1'),                # #제목 (출연자 태그와 구분)
    ]
    
    for pattern, repl in patterns:
        match = re.match(pattern, first_line)
        if match:
            title = match.group(1).strip()
            # 출연자 이름이 아니면 제목으로 사용
            if title not in CONFIG.CAST_MEMBERS:
                return re.sub(r'[^\w\s-]', '', title).replace(' ', '_')[:50]
    
    # 패턴이 없으면 첫 줄에서 특수문자 제거
    return re.sub(r'[^\w\s-]', '', first_line).replace(' ', '_')[:50] or "podcast"

# =============================================================================
# 메인 애플리케이션
# =============================================================================
class PodcastGenerator:
    def __init__(self, cli_mode=False, cli_args=None, embed_mode=False, parent=None):
        self.cli_mode = cli_mode
        self.cli_args = cli_args
        self.embed_mode = embed_mode
        
        # 생성 취소 플래그
        self.generation_cancelled = False
        
        # 미리듣기 관련 변수
        self.preview_playing = False
        self.preview_stop = False
        self.preview_thread = None
        self.preview_lock = threading.Lock()
        
        if embed_mode and parent:
            self.window = parent
            self.font_manager = FontManager()
            self.compact_mode = True
            self.font_manager.font_sizes.update({
                'title': 20, 'subtitle': 16, 'heading': 16,
                'body': 12, 'small': 11, 'button_large': 20,
                'button_normal': 13, 'button_small': 12, 'subtitle_large': 15
            })
        elif not cli_mode:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            
            self.font_manager = FontManager()
            self.compact_mode = False
            
            self.window = ctk.CTk()
            self.window.title("🎙️ Supertonic3 팟캐스트 생성기 v2.0")
            self.window.geometry("1600x900")
            self.window.protocol("WM_DELETE_WINDOW", self.quit_program)
        
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except:
            print("[WARNING] pygame mixer 초기화 실패")
        
        if not hasattr(self, "compact_mode"):
            self.compact_mode = False

        self.temp_manager = TempFileManager()
        self.tts_cache = TTSCache()
        
        self.current_audio_file = None
        self.current_srt_file = None
        self.subtitle_thread = None
        self.subtitle_running = False
        self.subtitle_data = ""
        self.subtitle_subs = None
        self.subtitle_start_time = 0
        self.selected_music_file = None
        self.music_preview_playing = False
        self.player_playing = False
        self.player_paused = False
        self.player_total_duration = 0.0
        self.player_started_at = 0.0
        self.player_pause_started_at = 0.0
        self.player_pause_accumulated = 0.0
        self.player_volume = ctk.DoubleVar(value=1.0) if not cli_mode else None
        self.player_timer_running = False
        self.last_subtitle_text = ""
        
        if not cli_mode:
            self.male_voice = ctk.StringVar(value="ko-KR-InJoonNeural")
            self.female_voice = ctk.StringVar(value="ko-KR-SunHiNeural")
            self.tts_engine = ctk.StringVar(value="supertonic")
            self.supertonic_male_voice = ctk.StringVar(value=CONFIG.SUPERTONIC_DEFAULT_MALE)
            self.supertonic_female_voice = ctk.StringVar(value=CONFIG.SUPERTONIC_DEFAULT_FEMALE)
            self.openai_male_voice = ctk.StringVar(value="nova")
            self.openai_female_voice = ctk.StringVar(value="nova")
            self.openai_api_key = ctk.StringVar(value=CONFIG.OPENAI_API_KEY)
            
            self.speed = ctk.DoubleVar(value=CONFIG.DEFAULT_SPEED)
            self.pitch = ctk.IntVar(value=CONFIG.DEFAULT_PITCH)
            self.volume = ctk.IntVar(value=CONFIG.DEFAULT_VOLUME)
            self.voice_volume = ctk.DoubleVar(value=CONFIG.VOICE_VOLUME)  # 사람 목소리 볼륨
            self.music_volume = ctk.DoubleVar(value=CONFIG.MUSIC_VOLUME)
            self.fade_in = ctk.DoubleVar(value=CONFIG.FADE_IN)
            self.fade_out = ctk.DoubleVar(value=CONFIG.FADE_OUT)
            
            self.music_folder = ctk.StringVar(value=CONFIG.MUSIC_DIR)
            self.music_file_var = ctk.StringVar(value="파일을 선택하세요")
            self.output_filename_var = ctk.StringVar(value="")
            self.random_music = ctk.BooleanVar(value=True)
            self.generate_subtitles = ctk.BooleanVar(value=True)
            self.music_files = []
            
            self.cat_voice_vars = {}
            self.cat_speed_vars = {}
            for cat_name in CONFIG.CAST_MEMBERS:
                self.cat_voice_vars[cat_name] = ctk.StringVar(
                    value=CONFIG.CAT_VOICE_MAPPING.get(cat_name, cat_name)
                )
                self.cat_speed_vars[cat_name] = ctk.DoubleVar(
                    value=CONFIG.CAT_SPEED_MAPPING.get(cat_name, 1.0)
                )
        
        self.start_time = None
        self.check_gpu()
        self.settings_file = os.path.join(CONFIG.SCRIPT_DIR, "settings.json")
        
        if not cli_mode:
            self.load_settings()
            self.setup_ui()
            self.refresh_music_list()
            self.on_player_volume_change()
    
    def check_gpu(self):
        try:
            result = run_subprocess_hidden(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, errors='ignore'
            )
            self.use_nvenc = "h264_nvenc" in result.stdout
            print(f"[INFO] GPU 가속: {'ON' if self.use_nvenc else 'OFF'}")
        except:
            self.use_nvenc = False

    def get_project_folder(self):
        project_folder = os.path.join(CONFIG.SCRIPT_DIR, "PROJECT")
        os.makedirs(project_folder, exist_ok=True)
        return project_folder

    def add_slider(self, parent, label, var, from_, to, suffix="", command=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            frame, 
            text=label,
            font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_secondary"],
            width=100
        ).pack(side="left", padx=(0, 10))

        # 슬라이더 미세 조정 개선
        # - 사람 목소리(0.0~2.0): 0.01 단위 느낌으로 촘촘하게
        # - 음악 볼륨(0.0~1.0): 더 세밀하게 조절 가능하도록 촘촘하게
        if suffix == "%":
            if to <= 1.0:
                step_count = int(round((to - from_) / 0.01))
            else:
                step_count = int(round((to - from_) / 0.01))
        else:
            step_count = int(round((to - from_) / 0.1))
        step_count = max(step_count, 1)
        
        slider = ctk.CTkSlider(
            frame,
            from_=from_,
            to=to,
            variable=var,
            command=command,
            number_of_steps=step_count,
            fg_color=COLOR_THEME["surface"],
            progress_color=COLOR_THEME["progress"],
            height=16,
            width=200
        )
        slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        if suffix == "%":
            value_label = ctk.CTkLabel(
                frame,
                text=f"{int(var.get()*100)}%",
                font=self.font_manager.get_font('body', 'bold'),
                text_color=COLOR_THEME["text_accent"],
                width=50
            )
        else:
            value_label = ctk.CTkLabel(
                frame,
                text=f"{var.get():.1f}{suffix}",
                font=self.font_manager.get_font('body', 'bold'),
                text_color=COLOR_THEME["text_accent"],
                width=50
            )
        value_label.pack(side="right")
        
        def update_value(value):
            if suffix == "%":
                value_label.configure(text=f"{int(float(value)*100)}%")
            else:
                value_label.configure(text=f"{float(value):.1f}{suffix}")
            if command:
                command(value)
            self.save_settings()
        
        slider.configure(command=update_value)
        
        return slider

    def setup_ui(self):
        outer_pad_x = 8 if self.compact_mode else 14
        outer_pad_y = 6 if self.compact_mode else 10
        title_height = 34 if self.compact_mode else 42
        section_gap = 6 if self.compact_mode else 8

        main = ctk.CTkFrame(self.window, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=outer_pad_x, pady=outer_pad_y)
        
        title_frame = ctk.CTkFrame(main, fg_color="transparent", height=title_height)
        title_frame.pack(fill="x", pady=(0, section_gap))
        
        ctk.CTkLabel(
            title_frame, 
            text="🎙️ Supertonic3 팟캐스트 생성기 v2.0",
            font=self.font_manager.get_font('title', 'bold'),
            text_color="#0B2A56"  # 아주 진한 청색
        ).pack(side="left")
        
        right_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        right_frame.pack(side="right")
        
        gpu_text = "🚀 GPU 가속" if self.use_nvenc else "💻 CPU"
        ctk.CTkLabel(
            right_frame,
            text=gpu_text,
            font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["success"] if self.use_nvenc else COLOR_THEME["warning"]
        ).pack(side="left", padx=10)
        
        help_btn = ctk.CTkButton(
            right_frame,
            text="📚 도움말",
            command=self.show_help,
            width=72 if self.compact_mode else 80,
            height=28 if self.compact_mode else 30,
            font=self.font_manager.get_font('button_small'),
            fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            text_color=COLOR_THEME["text_primary"]
        )
        help_btn.pack(side="left", padx=5)
        
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(fill="both", expand=True)
        
        if self.compact_mode:
            content.grid_columnconfigure(0, weight=33)
            content.grid_columnconfigure(1, weight=67)
        else:
            content.grid_columnconfigure(0, weight=3)
            content.grid_columnconfigure(1, weight=7)
        content.grid_rowconfigure(0, weight=1)
        
        # ===== 왼쪽 패널 =====
        left_panel = ctk.CTkFrame(content, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6 if self.compact_mode else 10))
        
        left_panel.grid_rowconfigure(0, weight=0)  # 버튼 프레임
        left_panel.grid_rowconfigure(1, weight=0)  # 타이틀
        left_panel.grid_rowconfigure(2, weight=0)  # 감정 태그 툴바
        if self.compact_mode:
            left_panel.grid_rowconfigure(3, weight=6)  # 스크립트 입력
            left_panel.grid_rowconfigure(4, weight=4)  # 통합 플레이어
        else:
            left_panel.grid_rowconfigure(3, weight=8)  # 스크립트 입력 (80%)
            left_panel.grid_rowconfigure(4, weight=2)  # 통합 플레이어 (20%)
        left_panel.grid_columnconfigure(0, weight=1)
        
        # 상단 버튼 프레임
        button_frame = ctk.CTkFrame(left_panel, fg_color="transparent", height=42 if self.compact_mode else 50)
        button_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8 if self.compact_mode else 10))
        button_frame.grid_columnconfigure((0,1,2,3), weight=1)
        
        ctk.CTkButton(
            button_frame, text="🆕 신규작성", command=self.new_project,
            height=34 if self.compact_mode else 40, font=self.font_manager.get_font('button_normal'),
            fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            text_color=COLOR_THEME["text_primary"]
        ).grid(row=0, column=0, padx=5, sticky="ew")
        
        ctk.CTkButton(
            button_frame, text="📂 불러오기", command=self.load_project,
            height=34 if self.compact_mode else 40, font=self.font_manager.get_font('button_normal'),
            fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            text_color=COLOR_THEME["text_primary"]
        ).grid(row=0, column=1, padx=5, sticky="ew")
        
        ctk.CTkButton(
            button_frame, text="💾 저장", command=self.save_project,
            height=34 if self.compact_mode else 40, font=self.font_manager.get_font('button_normal'),
            fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            text_color=COLOR_THEME["text_primary"]
        ).grid(row=0, column=2, padx=5, sticky="ew")
        
        ctk.CTkButton(
            button_frame, text="📄 예제", command=self.load_example,
            height=34 if self.compact_mode else 40, font=self.font_manager.get_font('button_normal'),
            fg_color=COLOR_THEME["warning"], hover_color="#D97706",
            text_color=COLOR_THEME["text_primary"]
        ).grid(row=0, column=3, padx=5, sticky="ew")
        
        # 스크립트 입력 타이틀 + 파일명 입력
        title_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        title_row.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        title_row.grid_columnconfigure(1, weight=1)

        title_label = ctk.CTkLabel(
            title_row,
            text="📝 스크립트 입력",
            font=self.font_manager.get_font('heading', 'bold'),
            text_color=COLOR_THEME["text_accent"]
        )
        title_label.grid(row=0, column=0, sticky="w")

        filename_wrap = ctk.CTkFrame(title_row, fg_color="transparent")
        filename_wrap.grid(row=0, column=1, sticky="e", padx=(10, 0))

        ctk.CTkLabel(
            filename_wrap,
            text="타이틀 입력",
            font=self.font_manager.get_font('body', 'bold'),
            text_color=COLOR_THEME["text_secondary"]
        ).pack(side="left", padx=(0, 8))

        self.output_filename_entry = ctk.CTkEntry(
            filename_wrap,
            textvariable=self.output_filename_var,
            width=260 if not self.compact_mode else 180,
            height=34 if not self.compact_mode else 30,
            placeholder_text="비워두면 날짜/시간 자동 저장",
            font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_primary"],
            fg_color=COLOR_THEME["surface_light"]
        )
        self.output_filename_entry.pack(side="left")

        # 감정 태그 삽입 툴바 - 화면을 타이트하게 쓰기 위해 2줄 버튼 그리드로 구성
        emotion_frame = ctk.CTkFrame(left_panel, fg_color=COLOR_THEME["surface"], corner_radius=10)
        emotion_frame.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        for col in range(6):
            emotion_frame.grid_columnconfigure(col, weight=1)

        ctk.CTkLabel(
            emotion_frame,
            text="감정 삽입",
            font=self.font_manager.get_font('small', 'bold'),
            text_color=COLOR_THEME["text_accent"],
            width=70
        ).grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(8, 4), pady=5)

        for idx, (tag, label) in enumerate(EMOTION_TAGS):
            row = idx // 5
            col = (idx % 5) + 1
            ctk.CTkButton(
                emotion_frame,
                text=EMOTION_BUTTON_TEXT.get(tag, f"<{tag}>"),
                command=lambda t=tag: self.insert_emotion_tag(t),
                height=25 if self.compact_mode else 27,
                width=86 if self.compact_mode else 104,
                font=self.font_manager.get_font('button_small', 'bold'),
                fg_color=COLOR_THEME["surface_light"],
                hover_color=COLOR_THEME["primary_hover"],
                text_color="#F5D06F"
            ).grid(row=row, column=col, sticky="ew", padx=3, pady=3)
        
        # 스크립트 입력창 (위쪽 빈공간 활용)
        self.text_input = ctk.CTkTextbox(
            left_panel, 
            border_width=2, 
            border_color=COLOR_THEME["border"],
            font=self.font_manager.get_font('body'), 
            wrap="word", 
            corner_radius=10,
            fg_color=COLOR_THEME["surface"],
            text_color=COLOR_THEME["text_primary"]
        )
        self.text_input.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        
        # ===== 통합 플레이어 =====
        player_frame = ctk.CTkFrame(left_panel, fg_color=COLOR_THEME["surface"], corner_radius=15)
        player_frame.grid(row=4, column=0, sticky="nsew")
        player_frame.grid_rowconfigure(2, weight=1)
        player_frame.grid_columnconfigure(0, weight=1)
        
        player_title = ctk.CTkLabel(
            player_frame, text="🎧 통합 플레이어",
            font=self.font_manager.get_font('subtitle', 'bold'),
            text_color=COLOR_THEME["text_accent"]
        )
        player_title.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 10))
        
        self.current_file_label = ctk.CTkLabel(
            player_frame, text="[대기] 파일을 선택하세요",
            font=self.font_manager.get_font('small'),
            text_color=COLOR_THEME["text_secondary"]
        )
        self.current_file_label.grid(row=0, column=0, sticky="e", padx=15, pady=(15, 10))
        
        control_frame = ctk.CTkFrame(player_frame, fg_color="transparent")
        control_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(10, 8))
        control_frame.grid_columnconfigure((0,1,2), weight=1)
        
        self.play_btn = ctk.CTkButton(
            control_frame, text="▶ 재생", command=self.toggle_playback,
            height=34, fg_color="#3B82F6", hover_color="#2563EB",
            font=self.font_manager.get_font('button_normal', 'bold'), state="disabled",
            text_color=COLOR_THEME["text_primary"]
        )
        self.play_btn.grid(row=0, column=0, padx=5, sticky="ew")
        
        self.stop_btn = ctk.CTkButton(
            control_frame, text="⏹ 중지", command=self.stop_playback,
            height=34, fg_color="#EF4444", hover_color="#DC2626",
            font=self.font_manager.get_font('button_normal', 'bold'), state="disabled",
            text_color=COLOR_THEME["text_primary"]
        )
        self.stop_btn.grid(row=0, column=1, padx=5, sticky="ew")
        
        ctk.CTkButton(
            control_frame, text="📂 폴더 열기", command=self.open_file_dialog,
            height=34, fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            font=self.font_manager.get_font('button_normal'),
            text_color=COLOR_THEME["text_primary"]
        ).grid(row=0, column=2, padx=5, sticky="ew")

        player_info_frame = ctk.CTkFrame(player_frame, fg_color="transparent")
        player_info_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 8))
        player_info_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            player_info_frame, text="🔊 플레이어 볼륨",
            font=self.font_manager.get_font('small'),
            text_color=COLOR_THEME["text_secondary"]
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.player_volume_slider = ctk.CTkSlider(
            player_info_frame, from_=0.0, to=1.0, variable=self.player_volume,
            fg_color=COLOR_THEME["surface"], progress_color=COLOR_THEME["progress"], height=14,
            command=self.on_player_volume_change
        )
        self.player_volume_slider.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        self.player_volume_label = ctk.CTkLabel(
            player_info_frame, text=f"{int(self.player_volume.get()*100)}%",
            font=self.font_manager.get_font('small', 'bold'), text_color=COLOR_THEME["text_accent"], width=50
        )
        self.player_volume_label.grid(row=0, column=2, sticky="e")

        self.player_time_label = ctk.CTkLabel(
            player_info_frame, text="진행 00:00 / 전체 00:00 / 남음 00:00",
            font=self.font_manager.get_font('small'), text_color=COLOR_THEME["text_secondary"]
        )
        self.player_time_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        
        # 실시간 자막 영역 (싱크 맞춰 한 줄씩 표시)
        subtitle_frame = ctk.CTkFrame(player_frame, fg_color=COLOR_THEME["surface_light"], corner_radius=10)
        subtitle_frame.grid(row=3, column=0, sticky="nsew", padx=15, pady=(0, 10))
        subtitle_frame.grid_rowconfigure(0, weight=1)
        subtitle_frame.grid_columnconfigure(0, weight=1)
        
        self.subtitle_text = ctk.CTkLabel(
            subtitle_frame,
            text="🎵 재생 중인 파일의 자막이 여기에 표시됩니다",
            font=self.font_manager.get_custom_font(18, 'bold'),
            text_color=COLOR_THEME["text_accent"],
            wraplength=500,
            justify="center"
        )
        self.subtitle_text.grid(row=0, column=0, padx=20, pady=20)

        full_srt_frame = ctk.CTkFrame(player_frame, fg_color=COLOR_THEME["surface_light"], corner_radius=10)
        full_srt_frame.grid(row=4, column=0, sticky="nsew", padx=15, pady=(0, 15))
        full_srt_frame.grid_rowconfigure(1, weight=1)
        full_srt_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            full_srt_frame, text="전체 SRT 자막",
            font=self.font_manager.get_font('body', 'bold'), text_color=COLOR_THEME["text_accent"]
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 8))

        self.subtitle_all_text = ctk.CTkTextbox(
            full_srt_frame,
            height=140,
            font=self.font_manager.get_font('small'),
            fg_color=COLOR_THEME["surface"],
            text_color=COLOR_THEME["text_primary"],
            wrap="word",
            corner_radius=8
        )
        self.subtitle_all_text.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.subtitle_all_text.insert("1.0", "SRT 파일을 열면 전체 자막이 여기에 표시됩니다")
        self.subtitle_all_text.configure(state="disabled")
        
        # ===== 오른쪽 패널 (TTS 설정 100%) =====
        right_panel = ctk.CTkFrame(content, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(6 if self.compact_mode else 10, 0))
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        
        tts_frame = ctk.CTkFrame(right_panel, fg_color=COLOR_THEME["surface"], corner_radius=15)
        tts_frame.grid(row=0, column=0, sticky="nsew")
        tts_frame.grid_columnconfigure(0, weight=1)
        
        tts_scroll = ctk.CTkScrollableFrame(tts_frame, fg_color="transparent")
        tts_scroll.pack(fill="both", expand=True, padx=10 if self.compact_mode else 12, pady=8 if self.compact_mode else 10)
        row_label_width = 92 if self.compact_mode else 100
        row_height = 30 if self.compact_mode else 32

        # TTS 엔진 설정 제목
        ctk.CTkLabel(
            tts_scroll, text="🔊 TTS 엔진 설정",
            font=self.font_manager.get_font('heading', 'bold'),
            text_color=COLOR_THEME["text_accent"]
        ).pack(anchor="w", pady=(0, 15))
        
        # 엔진 선택
        engine_row = ctk.CTkFrame(tts_scroll, fg_color="transparent")
        engine_row.pack(fill="x", pady=8)
        
        ctk.CTkLabel(
            engine_row, text="엔진:", font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_secondary"], width=row_label_width
        ).pack(side="left")
        
        engine_combo = ctk.CTkComboBox(
            engine_row, values=["supertonic (로컬)", "openai (고품질)", "edge (무료)"],
            variable=self.tts_engine, height=row_height,
            font=self.font_manager.get_font('body'),
            command=self.on_tts_engine_change,
            text_color=COLOR_THEME["text_primary"],
            fg_color=COLOR_THEME["surface_light"],
            button_color=COLOR_THEME["primary"],
            button_hover_color=COLOR_THEME["primary_hover"],
            dropdown_fg_color=COLOR_THEME["surface_light"],
            dropdown_text_color=COLOR_THEME["text_primary"],
            width=220 if self.compact_mode else 300
        )
        engine_combo.pack(side="left", padx=10, fill="x", expand=True)
        
        # API 키 프레임
        self.api_frame = ctk.CTkFrame(tts_scroll, fg_color="transparent")
        self.api_frame.pack(fill="x", pady=8)
        
        api_row = ctk.CTkFrame(self.api_frame, fg_color="transparent")
        api_row.pack(fill="x")
        
        ctk.CTkLabel(
            api_row, text="API 키:", font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_secondary"], width=row_label_width
        ).pack(side="left")
        
        api_entry = ctk.CTkEntry(
            api_row, textvariable=self.openai_api_key,
            height=row_height, placeholder_text="sk-...", show="*",
            font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_primary"],
            fg_color=COLOR_THEME["surface_light"],
            placeholder_text_color=COLOR_THEME["text_secondary"]
        )
        api_entry.pack(side="left", padx=10, fill="x", expand=True)
        
        ctk.CTkButton(
            api_row, text="저장", command=self.save_openai_key,
            width=72 if self.compact_mode else 80, height=row_height, fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            font=self.font_manager.get_font('button_small'),
            text_color=COLOR_THEME["text_primary"]
        ).pack(side="left", padx=5)
        
        # Supertonic 3 로컬 TTS 음성 프레임
        self.supertonic_frame = ctk.CTkFrame(tts_scroll, fg_color="transparent")

        st_male_row = ctk.CTkFrame(self.supertonic_frame, fg_color="transparent")
        st_male_row.pack(fill="x", pady=5)
        ctk.CTkLabel(st_male_row, text="👨 ST 남성:", font=self.font_manager.get_font('body'),
                    text_color=COLOR_THEME["text_secondary"], width=row_label_width).pack(side="left")
        self.supertonic_male_combo = ctk.CTkComboBox(
            st_male_row, values=SUPERTONIC_ALL_VOICES,
            variable=self.supertonic_male_voice, height=30,
            font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_primary"],
            fg_color=COLOR_THEME["surface_light"],
            button_color=COLOR_THEME["primary"],
            button_hover_color=COLOR_THEME["primary_hover"]
        )
        self.supertonic_male_combo.pack(side="left", padx=5, fill="x", expand=True)

        st_female_row = ctk.CTkFrame(self.supertonic_frame, fg_color="transparent")
        st_female_row.pack(fill="x", pady=5)
        ctk.CTkLabel(st_female_row, text="👩 ST 여성:", font=self.font_manager.get_font('body'),
                    text_color=COLOR_THEME["text_secondary"], width=row_label_width).pack(side="left")
        self.supertonic_female_combo = ctk.CTkComboBox(
            st_female_row, values=SUPERTONIC_ALL_VOICES,
            variable=self.supertonic_female_voice, height=30,
            font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_primary"],
            fg_color=COLOR_THEME["surface_light"],
            button_color=COLOR_THEME["primary"],
            button_hover_color=COLOR_THEME["primary_hover"]
        )
        self.supertonic_female_combo.pack(side="left", padx=5, fill="x", expand=True)

        st_hint = ctk.CTkLabel(
            self.supertonic_frame,
            text="Supertonic 3는 로컬 CPU 기반 기본 동작입니다. GPU 사용은 ONNX/WebGPU 환경 구성에 따라 별도 확인이 필요합니다.",
            font=self.font_manager.get_font('small'),
            text_color=COLOR_THEME["text_secondary"],
            wraplength=360 if self.compact_mode else 520,
            justify="left"
        )
        st_hint.pack(anchor="w", padx=5, pady=(4, 8))

        # Edge TTS 음성 프레임
        self.edge_frame = ctk.CTkFrame(tts_scroll, fg_color="transparent")
        
        male_row = ctk.CTkFrame(self.edge_frame, fg_color="transparent")
        male_row.pack(fill="x", pady=5)
        
        ctk.CTkLabel(male_row, text="👨 남성:", font=self.font_manager.get_font('body'),
                    text_color=COLOR_THEME["text_secondary"], width=row_label_width).pack(side="left")
        
        self.male_combo = ctk.CTkComboBox(
            male_row, values=["ko-KR-InJoonNeural", "ko-KR-HyunsuNeural"],
            variable=self.male_voice, height=35, 
            font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_primary"],
            fg_color=COLOR_THEME["surface_light"],
            button_color=COLOR_THEME["primary"],
            button_hover_color=COLOR_THEME["primary_hover"]
        )
        self.male_combo.pack(side="left", padx=5, fill="x", expand=True)
        
        female_row = ctk.CTkFrame(self.edge_frame, fg_color="transparent")
        female_row.pack(fill="x", pady=5)
        
        ctk.CTkLabel(female_row, text="👩 여성:", font=self.font_manager.get_font('body'),
                    text_color=COLOR_THEME["text_secondary"], width=row_label_width).pack(side="left")
        
        self.female_combo = ctk.CTkComboBox(
            female_row, values=["ko-KR-SunHiNeural", "ko-KR-JiMinNeural"],
            variable=self.female_voice, height=35, 
            font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_primary"],
            fg_color=COLOR_THEME["surface_light"],
            button_color=COLOR_THEME["primary"],
            button_hover_color=COLOR_THEME["primary_hover"]
        )
        self.female_combo.pack(side="left", padx=5, fill="x", expand=True)
        
        # 속도 조절 슬라이더
        speed_frame = ctk.CTkFrame(tts_scroll, fg_color="transparent")
        speed_frame.pack(fill="x", pady=16)
        
        ctk.CTkLabel(
            speed_frame, text="🎚️ 속도 조절",
            font=self.font_manager.get_font('heading', 'bold'),
            text_color=COLOR_THEME["text_accent"]
        ).pack(anchor="w", pady=(0, 10))
        
        self.add_slider(speed_frame, "속도", self.speed, 0.5, 2.0, "배")
        
        # 사람 목소리 볼륨 슬라이더 (신규)
        voice_volume_frame = ctk.CTkFrame(tts_scroll, fg_color="transparent")
        voice_volume_frame.pack(fill="x", pady=16)
        
        ctk.CTkLabel(
            voice_volume_frame, text="🔊 사람 목소리 볼륨",
            font=self.font_manager.get_font('heading', 'bold'),
            text_color=COLOR_THEME["text_accent"]
        ).pack(anchor="w", pady=(0, 10))
        
        self.add_slider(voice_volume_frame, "볼륨", self.voice_volume, 0.8, 2.2, "%")
        
        # ===== 음악 설정 =====
        music_section = ctk.CTkFrame(tts_scroll, fg_color=COLOR_THEME["surface_light"], corner_radius=15)
        music_section.pack(fill="x", pady=18, padx=4 if self.compact_mode else 5)
        
        music_title_row = ctk.CTkFrame(music_section, fg_color="transparent")
        music_title_row.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            music_title_row, text="🎵 음악 설정",
            font=self.font_manager.get_font('heading', 'bold'),
            text_color=COLOR_THEME["text_accent"]
        ).pack(side="left")

        self.random_check = ctk.CTkCheckBox(
            music_title_row, text="랜덤 선택", variable=self.random_music,
            command=self.toggle_random_music, font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_secondary"],
            fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            checkmark_color=COLOR_THEME["text_primary"]
        )
        self.random_check.pack(side="left", padx=18)

        music_content = ctk.CTkFrame(music_section, fg_color="transparent")
        music_content.pack(fill="x", padx=20, pady=(0, 20))
        
        self.add_slider(music_content, "음악 볼륨", self.music_volume, 0.0, 1.0, "%")
        
        # 폴더 선택
        folder_row = ctk.CTkFrame(music_content, fg_color="transparent")
        folder_row.pack(fill="x", pady=8)
        
        ctk.CTkLabel(
            folder_row, text="폴더:", font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_secondary"], width=row_label_width
        ).pack(side="left")
        
        folder_entry = ctk.CTkEntry(
            folder_row, textvariable=self.music_folder,
            height=row_height, placeholder_text="음악 폴더 경로",
            font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_primary"],
            fg_color=COLOR_THEME["surface_light"]
        )
        folder_entry.pack(side="left", padx=10, fill="x", expand=True)
        
        ctk.CTkButton(
            folder_row, text="찾기", command=self.browse_music_folder,
            width=72 if self.compact_mode else 80, height=row_height, font=self.font_manager.get_font('button_small'),
            fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            text_color=COLOR_THEME["text_primary"]
        ).pack(side="left")
        
        # 파일 선택
        file_row = ctk.CTkFrame(music_content, fg_color="transparent")
        file_row.pack(fill="x", pady=8)
        
        ctk.CTkLabel(
            file_row, text="파일:", font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_secondary"], width=row_label_width
        ).pack(side="left")
        
        self.file_entry = ctk.CTkEntry(
            file_row, textvariable=self.music_file_var,
            height=row_height, font=self.font_manager.get_font('body'), state="readonly",
            text_color=COLOR_THEME["text_primary"],
            fg_color=COLOR_THEME["surface_light"]
        )
        self.file_entry.pack(side="left", padx=10, fill="x", expand=True)
        
        ctk.CTkButton(
            file_row, text="선택", command=self.select_music_file_dialog,
            width=72 if self.compact_mode else 80, height=row_height, font=self.font_manager.get_font('button_small'),
            fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            text_color=COLOR_THEME["text_primary"]
        ).pack(side="left", padx=2)
        
        # 미리듣기 버튼 (샘플 TTS + 음악 동시 재생)
        preview_row = ctk.CTkFrame(music_content, fg_color="transparent")
        preview_row.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            preview_row, text="미리듣기:", font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_secondary"], width=row_label_width
        ).pack(side="left")
        
        btn_frame = ctk.CTkFrame(preview_row, fg_color="transparent")
        btn_frame.pack(side="left", padx=10)
        
        self.preview_btn = ctk.CTkButton(
            btn_frame, text="▶ 샘플 듣기", command=self.toggle_sample_preview,
            width=108 if self.compact_mode else 130, height=row_height, fg_color="#3B82F6", hover_color="#2563EB",
            font=self.font_manager.get_font('button_small'),
            text_color=COLOR_THEME["text_primary"]
        )
        self.preview_btn.pack(side="left", padx=2)
        
        self.preview_stop_btn = ctk.CTkButton(
            btn_frame, text="⏹ 중지", command=self.stop_sample_preview,
            width=72 if self.compact_mode else 88, height=row_height, fg_color="#EF4444", hover_color="#DC2626",
            font=self.font_manager.get_font('button_small'), state="disabled",
            text_color=COLOR_THEME["text_primary"]
        )
        self.preview_stop_btn.pack(side="left", padx=2)
        
        # 음악 목록
        list_frame = ctk.CTkFrame(music_content, fg_color="transparent")
        list_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            list_frame, text="폴더 내 음악 파일:", font=self.font_manager.get_font('body', 'bold'),
            text_color=COLOR_THEME["text_secondary"]
        ).pack(anchor="w")
        
        music_list_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        music_list_frame.pack(fill="x", pady=5)
        
        self.music_listbox = tk.Listbox(
            music_list_frame, height=4 if self.compact_mode else 5, bg="#2a2a2a", fg="white",
            selectbackground=COLOR_THEME["primary"],
            font=(CONFIG.FONT_FAMILY, 11)
        )
        self.music_listbox.pack(side="left", fill="x", expand=True)
        
        ctk.CTkButton(
            music_list_frame, text="▶", command=self.preview_selected_from_list,
            width=40, height=35, font=self.font_manager.get_font('button_small'),
            fg_color=COLOR_THEME["primary"],
            hover_color=COLOR_THEME["primary_hover"],
            text_color=COLOR_THEME["text_primary"]
        ).pack(side="right", padx=2)
        
        self.music_listbox.bind('<<ListboxSelect>>', self.on_music_select)
        
        # 페이드 설정
        fade_frame = ctk.CTkFrame(music_content, fg_color="transparent")
        fade_frame.pack(fill="x", pady=12)
        
        self.add_slider(fade_frame, "페이드 인", self.fade_in, 0.0, 5.0, "초")
        self.add_slider(fade_frame, "페이드 아웃", self.fade_out, 0.0, 5.0, "초")
        
        # ===== Supertonic 기본 화자 설정 (M1~F5) =====
        self.openai_frame = ctk.CTkFrame(tts_scroll, fg_color="transparent")
        
        cat_title_frame = ctk.CTkFrame(self.openai_frame, fg_color="transparent")
        cat_title_frame.pack(fill="x", pady=8)
        
        ctk.CTkLabel(
            cat_title_frame, text="🎙️ Supertonic 기본 화자",
            font=self.font_manager.get_font('heading', 'bold'),
            text_color=COLOR_THEME["success"]
        ).pack(side="left")
        
        ctk.CTkLabel(
            cat_title_frame, text="(M1~F5 실제 화자 + 화자별 속도)",
            font=self.font_manager.get_font('small'),
            text_color=COLOR_THEME["text_secondary"]
        ).pack(side="left", padx=5)
        
        for cat_name in CONFIG.CAST_MEMBERS:
            cat_box = ctk.CTkFrame(self.openai_frame, fg_color=COLOR_THEME["surface"])
            cat_box.pack(fill="x", pady=3)

            cat_row = ctk.CTkFrame(cat_box, fg_color="transparent")
            cat_row.pack(fill="x", padx=8, pady=(5, 2))
            cat_emoji = "🎙️" if cat_name.startswith("M") else "🎧"
            
            ctk.CTkLabel(
                cat_row, text=f"{cat_emoji} {CONFIG.get_voice_display_name(cat_name)}",
                font=self.font_manager.get_font('body', 'bold'), width=110 if self.compact_mode else 140,
                text_color=COLOR_THEME["text_secondary"]
            ).pack(side="left")
            
            voice_combo = ctk.CTkComboBox(
                cat_row, values=SUPERTONIC_ALL_VOICES,
                variable=self.cat_voice_vars[cat_name],
                width=82 if self.compact_mode else 92,
                height=28 if self.compact_mode else 30, font=self.font_manager.get_font('small'),
                text_color=COLOR_THEME["text_primary"],
                fg_color=COLOR_THEME["surface_light"],
                button_color=COLOR_THEME["primary"],
                button_hover_color=COLOR_THEME["primary_hover"],
                dropdown_fg_color=COLOR_THEME["surface_light"],
                dropdown_text_color=COLOR_THEME["text_primary"]
            )
            voice_combo.pack(side="left", padx=10)

            speed_frame = ctk.CTkFrame(cat_row, fg_color="transparent")
            speed_frame.pack(side="left", padx=(0, 6), fill="x", expand=True)

            ctk.CTkLabel(
                speed_frame, text="속도",
                font=self.font_manager.get_font('small'),
                text_color=COLOR_THEME["text_secondary"], width=30
            ).pack(side="left")

            speed_value_label = ctk.CTkLabel(
                speed_frame, text=f"{self.cat_speed_vars[cat_name].get():.2f}x",
                font=self.font_manager.get_font('small'),
                text_color=COLOR_THEME["text_accent"], width=44
            )
            speed_value_label.pack(side="right", padx=(8, 0))

            speed_slider = ctk.CTkSlider(
                speed_frame, from_=0.85, to=1.10, variable=self.cat_speed_vars[cat_name],
                number_of_steps=25, button_color=COLOR_THEME["progress"],
                button_hover_color=COLOR_THEME["primary_hover"], progress_color=COLOR_THEME["progress"]
            )
            speed_slider.pack(side="left", fill="x", expand=True)

            desc = CONFIG.CAT_DESCRIPTIONS.get(cat_name, SUPERTONIC_VOICE_DESC.get(cat_name, ""))
            style = CONFIG.get_cat_edge_style(cat_name)
            edge_hint = f"Supertonic ID: {self.cat_voice_vars[cat_name].get()} / 기본속도 {CONFIG.CAT_SPEED_MAPPING.get(cat_name,1.0):.2f}x"
            desc_label = ctk.CTkLabel(
                cat_box, text=f"{desc} | {edge_hint}", font=self.font_manager.get_font('small'),
                text_color=COLOR_THEME["text_secondary"], anchor="w", justify="left"
            )
            desc_label.pack(fill="x", padx=10, pady=(0, 5))
            
            def make_callback(lbl, cat):
                def _update(choice=None):
                    desc = CONFIG.CAT_DESCRIPTIONS.get(cat, SUPERTONIC_VOICE_DESC.get(cat, ""))
                    lbl.configure(text=f"{desc} | Supertonic ID: {self.cat_voice_vars[cat].get()} / 속도 {self.cat_speed_vars[cat].get():.2f}x")
                return _update

            def make_speed_callback(lbl, cat):
                def _update(value):
                    lbl.configure(text=f"{float(value):.2f}x")
                return _update
            
            voice_combo.configure(command=make_callback(desc_label, cat_name))
            speed_slider.configure(command=make_speed_callback(speed_value_label, cat_name))
        
        self.on_tts_engine_change()
        
        # ===== 하단 생성 버튼 =====
        bottom = ctk.CTkFrame(main, fg_color="transparent", height=72)
        bottom.pack(fill="x", pady=(6, 0))
        
        button_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        button_frame.pack(pady=6 if self.compact_mode else 4)
        
        self.generate_btn = ctk.CTkButton(
            button_frame, text="🎙️ 팟캐스트 생성", command=self.generate_podcast,
            width=160 if self.compact_mode else 190, height=36 if self.compact_mode else 42, fg_color="#10B981", hover_color="#059669",
            font=self.font_manager.get_font('button_large', 'bold'), corner_radius=35,
            text_color=COLOR_THEME["text_primary"]
        )
        self.generate_btn.pack(side="left", padx=5)
        
        self.cancel_btn = ctk.CTkButton(
            button_frame, text="⏹ 생성 취소", command=self.cancel_generation,
            width=110 if self.compact_mode else 130, height=36 if self.compact_mode else 42, fg_color="#EF4444", hover_color="#DC2626",
            font=self.font_manager.get_font('button_large', 'bold'), corner_radius=35,
            text_color=COLOR_THEME["text_primary"], state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=5)
        
        progress_frame = ctk.CTkFrame(bottom, fg_color="transparent", height=24 if self.compact_mode else 30)
        progress_frame.pack(fill="x", pady=4 if self.compact_mode else 2)
        
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame, height=15, fg_color="#334155",
            progress_color=COLOR_THEME["progress"], corner_radius=8
        )
        self.progress_bar.pack(fill="x", padx=18 if self.compact_mode else 30)
        self.progress_bar.set(0)
        
        status_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        status_frame.pack(fill="x", pady=2 if self.compact_mode else 5)
        
        self.status_label = ctk.CTkLabel(
            status_frame, text="✅ 준비 완료", text_color=COLOR_THEME["success"],
            font=self.font_manager.get_font('body', 'bold')
        )
        self.status_label.pack(side="left", padx=18 if self.compact_mode else 30)
        
        self.time_label = ctk.CTkLabel(
            status_frame, text="⏱️ 00:00", font=self.font_manager.get_font('body'),
            text_color=COLOR_THEME["text_secondary"]
        )
        self.time_label.pack(side="right", padx=18 if self.compact_mode else 30)
        
        self.cache_label = ctk.CTkLabel(
            bottom, text="💾 캐시: 준비", text_color=COLOR_THEME["text_accent"],
            font=self.font_manager.get_font('small')
        )
        self.cache_label.pack(side="bottom", pady=2)
    
    def on_tts_engine_change(self, choice=None):
        engine = self.tts_engine.get()

        if hasattr(self, 'edge_frame'):
            self.edge_frame.pack_forget()
        if hasattr(self, 'supertonic_frame'):
            self.supertonic_frame.pack_forget()
        if hasattr(self, 'openai_frame'):
            self.openai_frame.pack_forget()
        if hasattr(self, 'api_frame'):
            self.api_frame.pack_forget()

        if "edge" in engine:
            if hasattr(self, 'edge_frame'):
                self.edge_frame.pack(fill="x", pady=5)
        elif "supertonic" in engine:
            if hasattr(self, 'supertonic_frame'):
                self.supertonic_frame.pack(fill="x", pady=5)
            if hasattr(self, 'openai_frame'):
                self.openai_frame.pack(fill="x", pady=5)
        else:
            if hasattr(self, 'openai_frame'):
                self.openai_frame.pack(fill="x", pady=5)
            if hasattr(self, 'api_frame'):
                self.api_frame.pack(fill="x", pady=8)
        self.save_settings()
    
    def insert_emotion_tag(self, tag: str):
        """대본 입력창의 현재 커서 위치에 Supertonic3 감정 태그 또는 대체 감정 문구를 삽입합니다."""
        token = EMOTION_INSERT_TEXT.get(tag, f"<{tag}>")
        try:
            self.text_input.insert("insert", token)
            self.text_input.focus_set()
            if tag in EMOTION_INSERT_TEXT:
                self.update_status(f"✅ 감정 문구 삽입: {token.strip()}", "success")
            else:
                self.update_status(f"✅ 감정 태그 삽입: {token}", "success")
        except Exception:
            try:
                self.text_input.insert("end", token)
                self.text_input.focus_set()
            except Exception:
                pass

    @staticmethod
    def clean_text_for_srt(text: str) -> str:
        """SRT 자막에는 <laugh> 같은 TTS 제어 태그가 보이지 않도록 제거합니다."""
        text = TTS_CONTROL_TAG_RE.sub("", text or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def show_help(self):
        HelpPopup(self.window)
    
    def load_example(self):
        self.text_input.delete("1.0", "end")
        self.text_input.insert("1.0", AI_PROMPT_EXAMPLE)
        self.update_status("✅ AI 프롬프트 예제가 로드되었습니다.", "success")

    def format_time(self, seconds: float) -> str:
        seconds = max(0, int(seconds or 0))
        return f"{seconds//60:02d}:{seconds%60:02d}"

    def on_player_volume_change(self, value=None):
        if hasattr(self, 'player_volume_label'):
            self.player_volume_label.configure(text=f"{int(float(self.player_volume.get())*100)}%")
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.set_volume(min(1.0, max(0.0, float(self.player_volume.get()))))
            except Exception:
                pass
        self.save_settings()

    def update_full_subtitle_view(self):
        if not hasattr(self, 'subtitle_all_text'):
            return
        self.subtitle_all_text.configure(state="normal")
        self.subtitle_all_text.delete("1.0", "end")
        if self.subtitle_subs:
            lines = []
            for idx, sub in enumerate(self.subtitle_subs, start=1):
                clean_text = sub.text.replace("\n", " ")
                start_sec = sub.start.ordinal / 1000.0
                end_sec = sub.end.ordinal / 1000.0
                lines.append(f"{idx:02d}. [{self.format_time(start_sec)} - {self.format_time(end_sec)}] {clean_text}")
            self.subtitle_all_text.insert("1.0", "\n\n".join(lines))
        else:
            self.subtitle_all_text.insert("1.0", "SRT 파일이 없습니다")
        self.subtitle_all_text.configure(state="disabled")

    def find_matching_srt(self, audio_path: str) -> Optional[str]:
        """MP3와 같은 이름의 SRT를 우선 탐색"""
        if not audio_path:
            return None

        audio_path = os.path.abspath(audio_path)
        base_path = os.path.splitext(audio_path)[0]
        exact_srt = base_path + ".srt"
        if os.path.exists(exact_srt):
            return exact_srt

        folder = os.path.dirname(audio_path)
        stem = os.path.splitext(os.path.basename(audio_path))[0].lower()
        if not os.path.isdir(folder):
            return None

        for name in os.listdir(folder):
            file_base, ext = os.path.splitext(name)
            if ext.lower() == ".srt" and file_base.lower() == stem:
                return os.path.join(folder, name)
        return None

    @staticmethod
    def srt_time_to_ms(time_text: str) -> int:
        hhmmss, millis = time_text.split(',')
        hours, minutes, seconds = [int(x) for x in hhmmss.split(':')]
        return ((hours * 3600) + (minutes * 60) + seconds) * 1000 + int(millis)

    def parse_srt_fallback(self, srt_path: str):
        """pysrt가 없거나 실패할 때 사용할 백업 파서"""
        from types import SimpleNamespace

        raw = Path(srt_path).read_text(encoding='utf-8-sig', errors='ignore')
        blocks = re.split(r"\r?\n\r?\n+", raw.strip())
        parsed = []

        for block in blocks:
            lines = [line.strip("\ufeff ") for line in block.splitlines() if line.strip()]
            if len(lines) < 2:
                continue

            if '-->' in lines[0]:
                time_line = lines[0]
                text_lines = lines[1:]
            elif len(lines) >= 3 and '-->' in lines[1]:
                time_line = lines[1]
                text_lines = lines[2:]
            else:
                continue

            try:
                start_text, end_text = [part.strip() for part in time_line.split('-->')]
                start_ms = self.srt_time_to_ms(start_text)
                end_ms = self.srt_time_to_ms(end_text)
            except Exception:
                continue

            parsed.append(
                SimpleNamespace(
                    start=SimpleNamespace(ordinal=start_ms),
                    end=SimpleNamespace(ordinal=end_ms),
                    text="\n".join(text_lines)
                )
            )
        return parsed

    def set_player_total_duration(self, file_path: str):
        self.player_total_duration = FFmpegUtils.get_duration(file_path) if file_path else 0.0
        self.update_player_time_labels(force_zero=not self.player_playing and not self.player_paused)

    def get_current_playback_position(self) -> float:
        if self.player_paused:
            return self.player_pause_started_at
        if not self.player_playing:
            return 0.0
        return max(0.0, time.time() - self.player_started_at - self.player_pause_accumulated)

    def update_player_time_labels(self, force_zero: bool = False):
        current = 0.0 if force_zero else self.get_current_playback_position()
        total = max(0.0, self.player_total_duration)
        if total > 0:
            current = min(current, total)
        remaining = max(0.0, total - current)
        if hasattr(self, 'player_time_label'):
            self.player_time_label.configure(
                text=f"진행 {self.format_time(current)} / 전체 {self.format_time(total)} / 남음 {self.format_time(remaining)}"
            )

    def reset_player_ui(self, stopped_message: str = "🎵 재생이 중지되었습니다"):
        self.player_playing = False
        self.player_paused = False
        self.player_pause_started_at = 0.0
        self.player_pause_accumulated = 0.0
        self.play_btn.configure(text="▶ 재생", fg_color="#3B82F6")
        self.stop_btn.configure(state="normal")
        self.update_player_time_labels(force_zero=True)
        self.last_subtitle_text = ""
        if self.subtitle_subs:
            self.subtitle_text.configure(text=stopped_message)
        else:
            self.subtitle_text.configure(text="🎵 자막 파일이 없습니다")

    
    def open_file_dialog(self):
        """파일 선택 다이얼로그 - MP3 + SRT 함께 재생"""
        file_path = filedialog.askopenfilename(
            title="MP3 파일 선택 (SRT는 자동 로드)",
            initialdir=CONFIG.OUTPUT_DIR,
            filetypes=[("MP3 files", "*.mp3"), ("All files", "*.*")]
        )

        if file_path:
            self.stop_playback(reset_only=True)
            self.current_audio_file = os.path.abspath(file_path)
            self.current_srt_file = self.find_matching_srt(self.current_audio_file)

            if self.current_srt_file:
                self.load_subtitles(self.current_srt_file)
            else:
                self.subtitle_subs = None
                self.last_subtitle_text = ""
                self.subtitle_text.configure(text="🎵 자막 파일이 없습니다")
                self.update_full_subtitle_view()

            self.current_file_label.configure(
                text=f"📁 {os.path.basename(self.current_audio_file)}",
                text_color=COLOR_THEME["text_accent"]
            )
            self.set_player_total_duration(self.current_audio_file)
            self.play_btn.configure(state="normal", command=self.toggle_playback)
            self.stop_btn.configure(state="normal", command=self.stop_playback)

    def load_subtitles(self, srt_path):
        """SRT 파일 로드 및 파싱"""
        resolved_path = srt_path or self.find_matching_srt(self.current_audio_file)
        self.current_srt_file = resolved_path

        if not resolved_path or not os.path.exists(resolved_path):
            print(f"[WARN] SRT 파일 없음: {resolved_path}")
            self.subtitle_subs = None
            self.last_subtitle_text = ""
            self.subtitle_text.configure(text="🎵 자막 파일이 없습니다")
            self.update_full_subtitle_view()
            return False

        try:
            try:
                import pysrt
                self.subtitle_subs = pysrt.open(resolved_path, encoding='utf-8-sig')
            except Exception as pysrt_error:
                print(f"[WARN] pysrt 로드 실패, 백업 파서로 재시도: {pysrt_error}")
                self.subtitle_subs = self.parse_srt_fallback(resolved_path)

            if not self.subtitle_subs:
                raise ValueError("파싱된 자막이 없습니다")

            self.last_subtitle_text = ""
            self.update_full_subtitle_view()
            self.subtitle_text.configure(text="▶ 재생을 시작하면 자막이 표시됩니다")
            print(f"[INFO] 자막 로드 성공: {resolved_path}")
            return True
        except Exception as e:
            print(f"[ERROR] 자막 로드 실패: {e}")
            self.subtitle_subs = None
            self.last_subtitle_text = ""
            self.subtitle_text.configure(text="🎵 자막 파일이 없습니다")
            self.update_full_subtitle_view()
            return False

    def start_playback(self):
        """MP3 재생 시작 + 자막 싱크"""
        if not self.current_audio_file or not os.path.exists(self.current_audio_file):
            return

        self.stop_playback(reset_only=True)

        try:
            pygame.mixer.music.load(self.current_audio_file)
            pygame.mixer.music.set_volume(min(1.0, max(0.0, float(self.player_volume.get()))))
            pygame.mixer.music.play()
            self.player_playing = True
            self.player_paused = False
            self.player_started_at = time.time()
            self.player_pause_started_at = 0.0
            self.player_pause_accumulated = 0.0
            self.set_player_total_duration(self.current_audio_file)

            self.play_btn.configure(text="⏸ 일시정지", fg_color="#F59E0B")
            self.stop_btn.configure(state="normal")

            if self.subtitle_subs:
                self.subtitle_running = True
                self.subtitle_thread = threading.Thread(target=self.subtitle_display_thread, daemon=True)
                self.subtitle_thread.start()
            else:
                self.subtitle_running = False
                self.subtitle_text.configure(text="🎵 자막 파일이 없습니다")

            threading.Thread(target=self.playback_monitor, daemon=True).start()

        except Exception as e:
            print(f"[ERROR] 재생 실패: {e}")

    def stop_playback(self, reset_only: bool = False):
        self.subtitle_running = False
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        self.reset_player_ui("🎵 재생이 중지되었습니다")
        if not reset_only:
            self.update_status("⏹ 재생을 중지하고 처음 위치로 돌아갔습니다", "info")

    def toggle_playback(self):
        if not self.current_audio_file or not os.path.exists(self.current_audio_file):
            return

        if not self.player_playing and not self.player_paused:
            self.start_playback()
            return

        if self.player_playing:
            try:
                pygame.mixer.music.pause()
            except Exception:
                return
            self.player_playing = False
            self.player_paused = True
            self.player_pause_started_at = self.get_current_playback_position()
            self.play_btn.configure(text="▶ 이어듣기", fg_color="#3B82F6")
            self.update_status("⏸ 일시정지됨", "warning")
            return

        if self.player_paused:
            try:
                pygame.mixer.music.unpause()
            except Exception:
                self.start_playback()
                return
            self.player_playing = True
            self.player_paused = False
            self.player_pause_accumulated += max(0.0, time.time() - self.player_started_at - self.player_pause_accumulated - self.player_pause_started_at)
            self.play_btn.configure(text="⏸ 일시정지", fg_color="#F59E0B")
            self.update_status("▶ 재생을 이어갑니다", "info")
            threading.Thread(target=self.playback_monitor, daemon=True).start()

    def playback_monitor(self):
        while self.player_playing or self.player_paused:
            self.window.after(0, self.update_player_time_labels)
            if self.player_paused:
                time.sleep(0.1)
                continue
            if not pygame.mixer.music.get_busy():
                break
            time.sleep(0.1)

        if self.player_paused:
            return

        self.window.after(0, lambda: self.reset_player_ui("🎵 재생이 완료되었습니다"))

    def subtitle_display_thread(self):
        """자막 싱크 맞춰 한 줄씩 표시"""
        if not self.subtitle_subs:
            return

        try:
            while self.subtitle_running and (self.player_playing or self.player_paused):
                current_pos = self.get_current_playback_position()

                current_sub = None
                for sub in self.subtitle_subs:
                    start_sec = sub.start.ordinal / 1000.0
                    end_sec = sub.end.ordinal / 1000.0
                    if start_sec <= current_pos <= end_sec:
                        current_sub = sub.text.replace('\n', ' ')
                        break

                if current_sub != self.last_subtitle_text:
                    self.last_subtitle_text = current_sub or ""
                    if current_sub:
                        self.window.after(0, lambda t=current_sub: self.subtitle_text.configure(text=t))
                    elif self.player_paused:
                        self.window.after(0, lambda: self.subtitle_text.configure(text="⏸ 일시정지 중"))
                    else:
                        self.window.after(0, lambda: self.subtitle_text.configure(text=""))

                time.sleep(0.1)

            if not self.player_paused:
                self.window.after(0, lambda: self.subtitle_text.configure(text="🎵 재생이 완료되었습니다"))

        except Exception as e:
            print(f"[ERROR] 자막 스레드: {e}")


    def toggle_sample_preview(self):
        """샘플 TTS + 선택 음악 동시 재생 (안정판)"""
        if self.preview_playing:
            self.stop_sample_preview()
            return

        self.preview_stop = False

        def preview_thread_func():
            with self.preview_lock:
                try:
                    self.window.after(0, lambda: self.update_status("🔊 TTS 생성 중...", "info"))

                    # 1) 샘플 TTS 1개 생성
                    tts_file = self.temp_manager.create_temp_file(".wav")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            self.create_tts(SAMPLE_TTS_TEXT, "M1", [], tts_file)
                        )
                    finally:
                        loop.close()

                    if not result or not os.path.exists(result) or os.path.getsize(result) <= 1000:
                        self.window.after(0, lambda: self.update_status("❌ TTS 생성 실패", "error"))
                        return

                    # 2) 음악 파일 선택
                    music_file = None
                    if self.music_files and self.random_music.get():
                        selected = random.choice(self.music_files)
                        music_file = os.path.join(self.music_folder.get(), selected)
                    elif self.selected_music_file:
                        music_file = self.selected_music_file

                    voice_vol = float(self.voice_volume.get())
                    music_vol = float(self.music_volume.get())

                    print(f"[PREVIEW] 음성 볼륨: {voice_vol:.2f}")
                    print(f"[PREVIEW] 음악 볼륨: {music_vol:.2f}")

                    mixed_file = self.temp_manager.create_temp_file(".wav")

                    if music_file and os.path.exists(music_file):
                        # 3-A) 음악이 있으면 아주 단순하게 8초 잘라서 믹싱
                        self.window.after(0, lambda: self.update_status("🎵 음악 믹싱 중...", "info"))

                        music_temp = self.temp_manager.create_temp_file(".wav")
                        cmd_vol = [
                            "ffmpeg", "-y",
                            "-i", music_file,
                            "-af", f"volume={music_vol}",
                            "-t", "8",
                            "-ac", "2",
                            music_temp
                        ]
                        result_vol = run_subprocess_hidden(
                            cmd_vol,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="ignore"
                        )
                        if result_vol.returncode != 0 or not os.path.exists(music_temp) or os.path.getsize(music_temp) <= 1000:
                            print(f"[ERROR] 음악 처리 실패: {result_vol.stderr}")
                            self.window.after(0, lambda: self.update_status("❌ 음악 처리 실패", "error"))
                            return

                        cmd_mix = [
                            "ffmpeg", "-y",
                            "-i", result,
                            "-i", music_temp,
                            "-filter_complex",
                            f"[0:a]volume={voice_vol}[v];[1:a][v]amix=inputs=2:duration=first",
                            "-ac", "2",
                            mixed_file
                        ]
                        result_mix = run_subprocess_hidden(
                            cmd_mix,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="ignore"
                        )
                        if result_mix.returncode != 0 or not os.path.exists(mixed_file) or os.path.getsize(mixed_file) <= 1000:
                            print(f"[ERROR] 믹싱 실패: {result_mix.stderr}")
                            self.window.after(0, lambda: self.update_status("❌ 믹싱 실패", "error"))
                            return
                    else:
                        # 3-B) 음악이 없으면 TTS만 볼륨 적용
                        self.window.after(0, lambda: self.update_status("🔊 TTS만 재생...", "info"))
                        cmd_tts = [
                            "ffmpeg", "-y",
                            "-i", result,
                            "-af", f"volume={voice_vol}",
                            "-ac", "2",
                            mixed_file
                        ]
                        result_tts = run_subprocess_hidden(
                            cmd_tts,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="ignore"
                        )
                        if result_tts.returncode != 0 or not os.path.exists(mixed_file) or os.path.getsize(mixed_file) <= 1000:
                            print(f"[ERROR] TTS 처리 실패: {result_tts.stderr}")
                            self.window.after(0, lambda: self.update_status("❌ 오디오 처리 실패", "error"))
                            return

                    # 4) 재생
                    self.window.after(0, lambda: self.update_status("▶ 미리듣기 재생 중...", "success"))

                    if not pygame.mixer.get_init():
                        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

                    try:
                        pygame.mixer.music.stop()
                    except Exception:
                        pass

                    pygame.mixer.music.load(mixed_file)
                    pygame.mixer.music.set_volume(1.0)
                    pygame.mixer.music.play()

                    self.preview_playing = True
                    self.window.after(0, lambda: self.preview_btn.configure(text="⏸ 일시정지", fg_color="#F59E0B"))
                    self.window.after(0, lambda: self.preview_stop_btn.configure(state="normal"))

                    start_time = time.time()
                    while pygame.mixer.music.get_busy() and self.preview_playing and not self.preview_stop:
                        time.sleep(0.1)
                        if time.time() - start_time > 10:
                            pygame.mixer.music.stop()
                            break

                    self.preview_playing = False
                    self.window.after(0, lambda: self.update_status("✅ 미리듣기 완료", "success"))
                    self.window.after(0, lambda: self.preview_btn.configure(text="▶ 샘플 듣기", fg_color="#3B82F6"))
                    self.window.after(0, lambda: self.preview_stop_btn.configure(state="disabled"))

                except Exception as e:
                    print(f"[ERROR] 미리듣기 실패: {e}")
                    traceback.print_exc()
                    self.preview_playing = False
                    self.window.after(0, lambda: self.update_status("❌ 미리듣기 실패", "error"))
                    self.window.after(0, lambda: self.preview_btn.configure(text="▶ 샘플 듣기", fg_color="#3B82F6"))
                    self.window.after(0, lambda: self.preview_stop_btn.configure(state="disabled"))

        self.preview_thread = threading.Thread(target=preview_thread_func, daemon=True)
        self.preview_thread.start()

    def stop_sample_preview(self):
        """샘플 미리듣기 중지"""
        self.preview_playing = False
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
        self.preview_btn.configure(text="▶ 샘플 듣기", fg_color="#3B82F6")
        self.preview_stop_btn.configure(state="disabled")

    def refresh_music_list(self):
        if not hasattr(self, 'music_listbox'):
            return
        self.music_listbox.delete(0, tk.END)
        self.music_files = []
        
        folder = self.music_folder.get()
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    self.music_files.append(file)
                    self.music_listbox.insert(tk.END, file)
            print(f"[MUSIC] {len(self.music_files)}개 파일 발견")
    
    def browse_music_folder(self):
        folder = filedialog.askdirectory(title="음악 폴더 선택")
        if folder:
            self.music_folder.set(folder)
            self.refresh_music_list()
            self.save_settings()
    
    def select_music_file_dialog(self):
        file_path = filedialog.askopenfilename(
            title="음악 파일 선택",
            filetypes=[("오디오 파일", "*.mp3 *.wav *.m4a *.flac"), ("모든 파일", "*.*")]
        )
        
        if file_path:
            self.selected_music_file = file_path
            self.music_file_var.set(os.path.basename(file_path))
            self.random_music.set(False)
            self.music_listbox.selection_clear(0, tk.END)
            self.update_status(f"✅ 음악 선택: {os.path.basename(file_path)}", "success")
            self.save_settings()
    
    def preview_selected_from_list(self):
        if not self.music_listbox.curselection():
            self.update_status("⚠️ 리스트에서 음악 파일을 선택하세요", "warning")
            return
        
        idx = self.music_listbox.curselection()[0]
        filename = self.music_files[idx]
        file_path = os.path.join(self.music_folder.get(), filename)
        
        self.selected_music_file = file_path
        self.music_file_var.set(filename)
        self.toggle_sample_preview()
    
    def on_music_select(self, event):
        if self.music_listbox.curselection():
            self.random_music.set(False)
            self.save_settings()
    
    def toggle_random_music(self):
        """랜덤 선택시 파일명 비우기"""
        if self.random_music.get():
            self.music_file_var.set("")
            self.selected_music_file = None
            self.music_listbox.selection_clear(0, tk.END)
        self.save_settings()
    
    def select_music_file(self) -> Optional[str]:
        """실제 생성시 사용할 음악 파일 선택"""
        if self.cli_mode:
            if not getattr(self, "music_random_value", True):
                return None
            music_dir = Path(CONFIG.MUSIC_DIR)
            files = [p for pattern in ("*.mp3", "*.wav", "*.m4a") for p in music_dir.glob(pattern)]
            return str(random.choice(files)) if files else None
        if self.random_music.get() and self.music_files:
            # 랜덤 선택시 폴더에서 랜덤으로 선택
            selected = random.choice(self.music_files)
            return os.path.join(self.music_folder.get(), selected)
        elif self.selected_music_file and os.path.exists(self.selected_music_file):
            return self.selected_music_file
        return None
    
    # =========================================================================
    # 화자 파싱 함수
    # =========================================================================
    def parse_remark_script(self, text: str) -> List[Dict]:
        lines = text.split('\n')
        segments = []
        current_speaker = 'M1'
        current_text = []
        
        cat_names = CONFIG.CAST_MEMBERS
        openai_voices = OPENAI_ALL_VOICES
        supertonic_voices = SUPERTONIC_ALL_VOICES
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            if line.startswith('#'):
                if current_text:
                    content = '\n'.join(current_text).strip()
                    if content:
                        segments.append({
                            'type': 'speech',
                            'speaker': current_speaker,
                            'content': content,
                            'effects': []
                        })
                    current_text = []
                
                speaker = line[1:].strip()
                
                if speaker in cat_names:
                    current_speaker = speaker
                    print(f"  [화자] #{speaker} → Supertonic 기본 화자")
                elif speaker in supertonic_voices:
                    current_speaker = speaker
                    print(f"  [화자] #{speaker} → Supertonic 직접 음성")
                elif speaker.lower() in openai_voices:
                    current_speaker = speaker
                else:
                    if speaker in ['남자', '남성', 'male']:
                        current_speaker = 'male'
                    elif speaker in ['여자', '여성', 'female']:
                        current_speaker = 'female'
                    else:
                        current_speaker = 'M1'
                
                i += 1
                continue
            
            if line:
                current_text.append(line)
            
            i += 1
        
        if current_text:
            content = '\n'.join(current_text).strip()
            if content:
                segments.append({
                    'type': 'speech',
                    'speaker': current_speaker,
                    'content': content,
                    'effects': []
                })
        
        print(f"\n[PARSE] 리마크 파싱 완료: {len(segments)}개 세그먼트")
        return segments
    
    def parse_xml_script(self, text: str) -> List[Dict]:
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        valid_tags = ['male', 'female', 'pause', 'pause1', 'pause2'] + list(EFFECT_PRESETS.keys())
        valid_tags_pattern = '|'.join(valid_tags)
        
        segments = []
        current_gender = 'male'
        current_effects = []
        pos = 0
        
        tag_pattern = rf'<(/?)({valid_tags_pattern})(?:\s+([^>]+))?\s*/?>'
        full_text = ' '.join(text.split('\n'))
        
        for match in re.finditer(tag_pattern, full_text, re.IGNORECASE):
            start, end = match.span()
            is_closing = match.group(1) == '/'
            tag = match.group(2).lower()
            attrs = match.group(3) if len(match.groups()) > 2 else ''
            
            if start > pos:
                content = full_text[pos:start].strip()
                if content:
                    content = re.sub(r'\s+', ' ', content)
                    speaker = 'M1' if current_gender == 'male' else 'F1'
                    segments.append({
                        'type': 'speech',
                        'speaker': speaker,
                        'effects': current_effects.copy(),
                        'content': content
                    })
            
            if tag in ['male', 'female']:
                if not is_closing:
                    current_gender = tag
            elif tag in ['pause', 'pause1', 'pause2']:
                duration = 1.0 if tag == 'pause' else (2.0 if tag == 'pause2' else 1.0)
                if tag == 'pause' and attrs:
                    time_match = re.search(r'time="?([\d.]+)"?', attrs)
                    if time_match:
                        duration = float(time_match.group(1))
                segments.append({'type': 'pause', 'duration': duration})
            elif tag in EFFECT_PRESETS:
                if not is_closing:
                    if tag not in current_effects:
                        current_effects.append(tag)
                else:
                    if tag in current_effects:
                        current_effects.remove(tag)
            
            pos = end
        
        if pos < len(full_text):
            content = full_text[pos:].strip()
            if content:
                content = re.sub(r'\s+', ' ', content)
                speaker = 'M1' if current_gender == 'male' else 'F1'
                segments.append({
                    'type': 'speech',
                    'speaker': speaker,
                    'effects': current_effects.copy(),
                    'content': content
                })
        
        return segments
    
    def parse_dialogue(self, text: str) -> List[Dict]:
        lines = text.split('\n')
        has_remark = any(line.strip().startswith('#') for line in lines if line.strip())
        
        if has_remark:
            print("[INFO] 리마크 형식 스크립트 감지")
            return self.parse_remark_script(text)
        else:
            print("[INFO] XML 태그 형식 스크립트 감지")
            return self.parse_xml_script(text)
    
    # =========================================================================
    # TTS 생성 함수
    # =========================================================================
    async def create_openai_tts(self, text: str, speaker: str, effects: List[str], output_path: str) -> Optional[str]:
        try:
            import openai
            from openai import OpenAI
            
            if self.cli_mode:
                api_key = CONFIG.OPENAI_API_KEY
            else:
                api_key = self.openai_api_key.get()
            
            if not api_key:
                print(f"  [ERROR] OpenAI API 키 없음")
                return None
            
            cat_names = CONFIG.CAST_MEMBERS
            openai_voices = OPENAI_ALL_VOICES
            speaker = CONFIG.normalize_cat_name(speaker)
            
            if speaker in cat_names:
                gender = CONFIG.get_cat_gender(speaker)
                voice = "onyx" if gender == "male" else "nova"
                print(f"  [화자] {speaker} → OpenAI fallback {voice}")
            elif speaker.lower() in openai_voices:
                voice = speaker.lower()
            elif speaker == 'male':
                voice = self.openai_male_voice.get()
            elif speaker == 'female':
                voice = self.openai_female_voice.get()
            else:
                voice = 'nova'
            
            base_speed = self.speed.get() if not self.cli_mode else getattr(self, "speed_value", 1.0)
            cat_speed = self.cat_speed_vars[speaker].get() if (not self.cli_mode and speaker in cat_names) else CONFIG.CAT_SPEED_MAPPING.get(speaker, 1.0)
            speed = base_speed * cat_speed
            
            effect_params = {}
            for effect in effects:
                if effect in EFFECT_PRESETS:
                    preset = EFFECT_PRESETS[effect]
                    if 'speed' in preset:
                        speed *= preset['speed']
            
            cache_voice = f"cat_{speaker}_{voice}" if speaker in cat_names else f"openai_{voice}"
            cached_file = self.tts_cache.get(text, cache_voice, speed, effects)
            
            if cached_file:
                wav_file = self.temp_manager.create_temp_file(".wav")
                shutil.copy2(cached_file, wav_file)
                return wav_file
            
            print(f"  [OpenAI] 음성:{voice}, 속도:{speed:.2f}, {len(text)}자")
            
            client = OpenAI(api_key=api_key)
            response = client.audio.speech.create(
                model="tts-1", voice=voice, input=text, speed=speed
            )
            
            mp3_file = self.temp_manager.create_temp_file(".mp3")
            response.stream_to_file(mp3_file)
            
            if not os.path.exists(mp3_file) or os.path.getsize(mp3_file) < 1000:
                return None
            
            wav_file = self.temp_manager.create_temp_file(".wav")
            cmd = ["ffmpeg", "-y", "-i", mp3_file, "-c:a", "pcm_s16le", wav_file]
            result = run_subprocess_hidden(cmd, capture_output=True)
            if result.returncode != 0:
                print(f"  [ERROR] WAV 변환 실패: {result.stderr.decode()}")
                return mp3_file
            
            self.tts_cache.save(text, cache_voice, speed, effects, wav_file)
            return wav_file
            
        except Exception as e:
            print(f"  [ERROR] OpenAI TTS: {e}")
            return None
    
    async def create_supertonic_tts(self, text: str, speaker: str, effects: List[str], output_path: str) -> Optional[str]:
        """Supertonic 3 로컬 TTS 생성

        권장 방식은 /home/bourne/StoryMaker_1/Supertonic3/.venv에서 실행 중인 ``supertonic serve``를 HTTP로 호출하는 것입니다.
        서버가 꺼져 있으면 현재 Python 환경에 설치된 supertonic SDK 직접 호출로 자동 fallback합니다.
        """
        # Supertonic3 직전 발음 정규화.
        # 화면/SRT 원문은 건드리지 않고 실제 음성 입력만 교정한다.
        # 1++/1+는 한우 등급 표기에서 각각 '투플러스'/'원플러스'로 읽게 한다.
        # 숫자 내부의 11++ 같은 문자열은 건드리지 않는다.
        text = re.sub(r"(?<!\d)1\s*[+＋]\s*[+＋](?![+＋])", "투플러스", text)
        text = re.sub(r"(?<!\d)1\s*[+＋](?![+＋])", "원플러스", text)

        try:
            if len(text) < CONFIG.MIN_TEXT_LENGTH:
                return None

            speaker = CONFIG.normalize_cat_name(speaker)
            if speaker in CONFIG.CAST_MEMBERS:
                gender = CONFIG.get_cat_gender(speaker)
            elif speaker in SUPERTONIC_VOICE_GENDER:
                gender = SUPERTONIC_VOICE_GENDER.get(speaker, "male")
            else:
                gender = 'female' if str(speaker).lower() == 'female' else 'male'

            cat_style = CONFIG.get_cat_edge_style(speaker)

            if self.cli_mode:
                if speaker in SUPERTONIC_ALL_VOICES:
                    voice = speaker
                else:
                    voice = SUPERTONIC_CAT_VOICE_MAPPING.get(
                        speaker,
                        CONFIG.SUPERTONIC_DEFAULT_MALE if gender == 'male' else CONFIG.SUPERTONIC_DEFAULT_FEMALE
                    )
                speed = CONFIG.CAT_SPEED_MAPPING.get(speaker, 1.0) * getattr(self, "speed_value", 1.0)
            else:
                if speaker in CONFIG.CAST_MEMBERS:
                    selected_voice = self.cat_voice_vars[speaker].get() if speaker in self.cat_voice_vars else speaker
                    selected_voice = CONFIG.normalize_cat_name(selected_voice)
                    voice = selected_voice if selected_voice in SUPERTONIC_ALL_VOICES else SUPERTONIC_CAT_VOICE_MAPPING.get(
                        speaker,
                        CONFIG.SUPERTONIC_DEFAULT_MALE if gender == 'male' else CONFIG.SUPERTONIC_DEFAULT_FEMALE
                    )
                    speed = self.speed.get() * self.cat_speed_vars[speaker].get()
                elif speaker in SUPERTONIC_ALL_VOICES:
                    voice = speaker
                    speed = self.speed.get()
                else:
                    voice = self.supertonic_male_voice.get() if gender == 'male' else self.supertonic_female_voice.get()
                    speed = self.speed.get()

            speed *= float(cat_style.get('speed', 1.0))

            for effect in effects:
                if effect in EFFECT_PRESETS:
                    preset = EFFECT_PRESETS[effect]
                    if 'speed' in preset:
                        speed *= preset['speed']

            # -----------------------------------------------------------------
            # 전체 속도 + 화자별 속도 + 효과 속도를 모두 반영합니다.
            #
            # 기존 문제:
            # - Supertonic3 안정화를 위해 speed를 0.85~1.10으로 강제 제한했습니다.
            # - 그래서 우측 전체 속도 슬라이더를 1.2 / 1.5 / 2.0으로 올려도
            #   실제 TTS 서버에는 계속 1.10만 전달되어 "전체 속도 조절이 안 되는 것처럼" 보였습니다.
            #
            # 수정 방식:
            # - Supertonic3 엔진에는 안정 범위(synthesis_speed)만 전달합니다.
            # - 사용자가 의도한 최종 속도(raw_speed)는 캐시 키와 후처리 기준으로 유지합니다.
            # - raw_speed와 synthesis_speed가 다르면 ffmpeg atempo로 WAV 길이를 다시 보정합니다.
            # -----------------------------------------------------------------
            raw_speed = max(0.50, min(2.00, float(speed)))
            synthesis_speed = max(CONFIG.SUPERTONIC_MIN_SPEED, min(CONFIG.SUPERTONIC_MAX_SPEED, raw_speed))
            tempo_ratio = raw_speed / synthesis_speed if synthesis_speed else 1.0
            speed = raw_speed
            if abs(synthesis_speed - raw_speed) > 0.001:
                print(f"  [TTS DEBUG] supertonic engine speed clipped = {raw_speed:.2f} -> {synthesis_speed:.2f}")
                print(f"  [TTS DEBUG] ffmpeg tempo ratio = {tempo_ratio:.3f}")

            cache_voice = f"supertonic_{speaker}_{voice}" if speaker in CONFIG.CAST_MEMBERS else f"supertonic_{voice}"
            cached_file = self.tts_cache.get(text, cache_voice, speed, effects)
            if cached_file:
                wav_file = self.temp_manager.create_temp_file(".wav")
                shutil.copy2(cached_file, wav_file)
                return wav_file

            print(f"  [TTS DEBUG] speaker = {speaker}")
            print(f"  [TTS DEBUG] gender = {gender}")
            print(f"  [TTS DEBUG] style_id/voice = {voice}")
            print(f"  [TTS DEBUG] text = {text[:50]}")
            print(f"  [Supertonic3] 음성:{voice}, 속도:{speed:.2f}, {len(text)}자")

            wav_file = self.temp_manager.create_temp_file(".wav")

            # 1순위: /home/bourne/StoryMaker_1/Supertonic3에서 띄운 supertonic serve HTTP 서버 호출
            if CONFIG.SUPERTONIC_USE_SERVER_FIRST:
                try:
                    import json
                    import urllib.request
                    import urllib.error

                    server = CONFIG.SUPERTONIC_SERVER_URL.rstrip('/')
                    payload = json.dumps({
                        "model": "supertonic-3",
                        "input": text,
                        "voice": voice,
                        "lang": CONFIG.SUPERTONIC_LANG,
                        "speed": synthesis_speed,
                        "total_steps": CONFIG.SUPERTONIC_TOTAL_STEPS,
                        "response_format": "wav",
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        f"{server}/v1/audio/speech",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=120) as res:
                        audio_bytes = res.read()
                    if audio_bytes and len(audio_bytes) > 1000:
                        with open(wav_file, "wb") as f:
                            f.write(audio_bytes)
                        duration = FFmpegUtils.get_duration(wav_file)
                        print(f"  [TTS DEBUG] chunk_duration = {duration:.3f}s")
                        if duration < CONFIG.TTS_MIN_CHUNK_DURATION:
                            print(f"  [WARNING] TTS 조각이 너무 짧습니다. 재생 끊김 가능성: {duration:.3f}s")
                        wav_file = self._apply_supertonic_tempo_if_needed(wav_file, tempo_ratio)
                        self.tts_cache.save(text, cache_voice, speed, effects, wav_file)
                        return wav_file
                except Exception as http_error:
                    print(f"  [Supertonic3] 로컬 서버 호출 실패 → SDK 직접 호출 fallback: {http_error}")

            # 2순위: 현재 Python 환경의 Supertonic SDK 직접 호출
            from supertonic import TTS
            tts = TTS(auto_download=True)
            try:
                style = tts.get_voice_style(voice_name=voice)
            except Exception:
                fallback = CONFIG.SUPERTONIC_FALLBACK_MALE if gender == 'male' else CONFIG.SUPERTONIC_FALLBACK_FEMALE
                print(f"  [Supertonic3] '{voice}' 음성 로드 실패 → '{fallback}'로 대체")
                style = tts.get_voice_style(voice_name=fallback)

            wav, duration = tts.synthesize(
                text=text,
                lang=CONFIG.SUPERTONIC_LANG,
                voice_style=style,
                total_steps=CONFIG.SUPERTONIC_TOTAL_STEPS,
                speed=synthesis_speed,
            )

            tts.save_audio(wav, wav_file)

            if not os.path.exists(wav_file) or os.path.getsize(wav_file) < 1000:
                return None

            wav_file = self._apply_supertonic_tempo_if_needed(wav_file, tempo_ratio)

            duration = FFmpegUtils.get_duration(wav_file)
            print(f"  [TTS DEBUG] chunk_duration = {duration:.3f}s")
            if duration < CONFIG.TTS_MIN_CHUNK_DURATION:
                print(f"  [WARNING] TTS 조각이 너무 짧습니다. 재생 끊김 가능성: {duration:.3f}s")

            self.tts_cache.save(text, cache_voice, speed, effects, wav_file)
            return wav_file


        except Exception as e:
            print(f"  [ERROR] Supertonic3 TTS: {e}")
            return None


    def _apply_supertonic_tempo_if_needed(self, wav_file: str, tempo_ratio: float) -> str:
        """Supertonic3 안정 속도 제한 이후에도 사용자가 정한 전체 속도를 실제 파일에 반영합니다."""
        try:
            tempo_ratio = float(tempo_ratio)
            if abs(tempo_ratio - 1.0) <= 0.01:
                return wav_file
            if not os.path.exists(wav_file) or os.path.getsize(wav_file) < 1000:
                return wav_file

            adjusted_file = self.temp_manager.create_temp_file(".wav")

            # ffmpeg atempo는 한 번에 0.5~2.0 범위를 권장합니다.
            # 현재 UI 전체 속도 범위가 0.5~2.0이고 엔진 제한 후 ratio도 이 범위 안에 들어오지만,
            # 안전하게 체인 필터를 구성해 둡니다.
            filters = []
            ratio = tempo_ratio
            while ratio > 2.0:
                filters.append("atempo=2.0")
                ratio /= 2.0
            while ratio < 0.5:
                filters.append("atempo=0.5")
                ratio /= 0.5
            filters.append(f"atempo={ratio:.6f}")
            filter_arg = ",".join(filters)

            cmd = [
                "ffmpeg", "-y",
                "-i", wav_file,
                "-filter:a", filter_arg,
                "-c:a", "pcm_s16le",
                adjusted_file,
            ]
            result = run_subprocess_hidden(cmd, capture_output=True)
            if result.returncode == 0 and os.path.exists(adjusted_file) and os.path.getsize(adjusted_file) > 1000:
                print(f"  [TTS DEBUG] final tempo applied = {tempo_ratio:.3f}x")
                return adjusted_file

            print("  [WARNING] ffmpeg tempo 보정 실패 → 원본 Supertonic WAV 사용")
            return wav_file
        except Exception as e:
            print(f"  [WARNING] ffmpeg tempo 보정 예외 → 원본 Supertonic WAV 사용: {e}")
            return wav_file

    async def create_edge_tts(self, text: str, speaker: str, effects: List[str], output_path: str) -> Optional[str]:
        try:
            import edge_tts
            
            if len(text) < CONFIG.MIN_TEXT_LENGTH:
                return None
            
            speaker = CONFIG.normalize_cat_name(speaker)
            gender = CONFIG.get_cat_gender(speaker) if speaker in CONFIG.CAST_MEMBERS else ('female' if speaker == 'female' else 'male')
            cat_style = CONFIG.get_cat_edge_style(speaker)
            
            if self.cli_mode:
                voice = "ko-KR-InJoonNeural" if gender == 'male' else "ko-KR-SunHiNeural"
                speed = CONFIG.CAT_SPEED_MAPPING.get(speaker, 1.0) * getattr(self, "speed_value", 1.0)
                pitch = int(cat_style.get('pitch', 0))
                volume = int(cat_style.get('volume', 0))
            else:
                voice = self.male_voice.get() if gender == 'male' else self.female_voice.get()
                speed = self.speed.get() * self.cat_speed_vars[speaker].get() if speaker in CONFIG.CAST_MEMBERS else self.speed.get()
                pitch = self.pitch.get() + int(cat_style.get('pitch', 0))
                volume = self.volume.get() + int(cat_style.get('volume', 0))
                speed *= float(cat_style.get('speed', 1.0))
            
            voice = voice.split()[0]
            
            effect_params = {}
            for effect in effects:
                if effect in EFFECT_PRESETS:
                    preset = EFFECT_PRESETS[effect]
                    if 'speed' in preset:
                        speed *= preset['speed']
                    if 'pitch' in preset:
                        pitch += preset['pitch']
                    if 'volume' in preset:
                        volume += preset['volume']
            
            cache_voice = f"edge_{speaker}_{voice}" if speaker in CONFIG.CAST_MEMBERS else voice
            cached_file = self.tts_cache.get(text, cache_voice, speed, effects)
            if cached_file:
                wav_file = self.temp_manager.create_temp_file(".wav")
                shutil.copy2(cached_file, wav_file)
                return wav_file
            
            rate = f"{int((speed - 1.0) * 100):+d}%"
            pitch_str = f"{pitch:+d}Hz"
            volume_str = f"{max(-50, min(50, volume)):+d}%"
            
            print(f"  [Edge] 음성:{voice}, 속도:{speed:.2f}, {len(text)}자")
            
            tts_file = self.temp_manager.create_temp_file(".mp3")
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch_str, volume=volume_str)
            await communicate.save(tts_file)
            
            if not os.path.exists(tts_file) or os.path.getsize(tts_file) < 1000:
                return None
            
            wav_file = self.temp_manager.create_temp_file(".wav")
            cmd = ["ffmpeg", "-y", "-i", tts_file, "-c:a", "pcm_s16le", wav_file]
            result = run_subprocess_hidden(cmd, capture_output=True)
            if result.returncode != 0:
                return tts_file
            
            self.tts_cache.save(text, cache_voice, speed, effects, wav_file)
            return wav_file
            
        except Exception as e:
            print(f"  [ERROR] Edge TTS: {e}")
            return None
    
    async def create_tts(self, text: str, speaker: str, effects: List[str], output_path: str) -> Optional[str]:
        if self.cli_mode:
            tts_engine = CONFIG.TTS_ENGINE
        else:
            tts_engine = self.tts_engine.get().split()[0]

        if tts_engine == "openai":
            return await self.create_openai_tts(text, speaker, effects, output_path)
        if tts_engine == "supertonic":
            return await self.create_supertonic_tts(text, speaker, effects, output_path)
        return await self.create_edge_tts(text, speaker, effects, output_path)
    
    # =========================================================================
    # SRT 생성 (화자 이름 제외)
    # =========================================================================
    def generate_srt(self, segments: List[Dict], voice_files: List[str], output_path: str) -> bool:
        try:
            srt_lines = []
            current_time = CONFIG.INTRO_MUSIC
            voice_idx = 0
            subtitle_index = 1
            
            for seg in segments:
                if seg['type'] == 'speech' and voice_idx < len(voice_files):
                    duration = FFmpegUtils.get_duration(voice_files[voice_idx])
                    if duration > 0:
                        text = self.clean_text_for_srt(seg['content'])
                        if not text:
                            current_time += duration
                            voice_idx += 1
                            continue
                        
                        words = text.split()
                        current_subtitle = ""
                        subtitle_parts = []
                        
                        for word in words:
                            if current_subtitle:
                                test_subtitle = current_subtitle + " " + word
                            else:
                                test_subtitle = word
                            
                            if len(test_subtitle) > 48:
                                if current_subtitle:
                                    subtitle_parts.append(current_subtitle)
                                current_subtitle = word
                            else:
                                current_subtitle = test_subtitle
                        
                        if current_subtitle:
                            subtitle_parts.append(current_subtitle)
                        
                        if subtitle_parts:
                            part_duration = duration / len(subtitle_parts)
                            
                            for i, part_text in enumerate(subtitle_parts):
                                start = current_time + (i * part_duration)
                                end = current_time + ((i + 1) * part_duration)
                                
                                srt_lines.append(
                                    f"{subtitle_index}\n"
                                    f"{self.seconds_to_srt(start)} --> {self.seconds_to_srt(end)}\n"
                                    f"{part_text}\n"
                                )
                                subtitle_index += 1
                        
                        current_time += duration
                        voice_idx += 1
                    
                elif seg['type'] == 'pause':
                    current_time += seg.get('duration', 1.0)
            
            if srt_lines:
                with open(output_path, 'w', encoding='utf-8-sig') as f:
                    f.write("\n".join(srt_lines))
                print(f"  [SRT] 생성 완료: {len(srt_lines)}개 자막")
                return True
            return False
            
        except Exception as e:
            print(f"[ERROR] SRT 생성: {e}")
            return False
    
    @staticmethod
    def seconds_to_srt(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    # =========================================================================
    # 오디오 믹싱
    # =========================================================================
    def mix_audio(self, voice_files: List[str], music_path: Optional[str], 
                  output_path: str, voice_duration: float) -> bool:
        print(f"\n[AUDIO] 믹싱 시작: {len(voice_files)}개 파일")
        
        if not voice_files:
            return False
        
        try:
            voice_concat = self.temp_manager.create_temp_file(".wav")
            concat_list = self.temp_manager.create_temp_file(".txt")
            
            with open(concat_list, 'w', encoding='utf-8') as f:
                for vf in voice_files:
                    f.write(f"file '{vf}'\n")
            
            cmd_concat = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-ac", "2", "-ar", str(CONFIG.SAMPLE_RATE),
                "-c:a", "pcm_s16le", voice_concat
            ]
            result = run_subprocess_hidden(cmd_concat, capture_output=True)
            if result.returncode != 0:
                print(f"  [ERROR] 음성 합치기 실패: {result.stderr.decode()}")
                return False
            
            voice_with_intro = self.temp_manager.create_temp_file(".wav")
            silence = self.temp_manager.create_temp_file(".wav")
            
            run_subprocess_hidden([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-t", str(CONFIG.INTRO_MUSIC), silence
            ], capture_output=True)
            
            cmd_join = [
            "ffmpeg", "-y", "-i", voice_concat,
            "-map", "0:a", "-c:a", "pcm_s16le", voice_with_intro
            ]
            result = run_subprocess_hidden(cmd_join, capture_output=True)
            if result.returncode != 0:
                print(f"  [ERROR] 무음 추가 실패: {result.stderr.decode()}")
                return False
            
            voice_boost = self.temp_manager.create_temp_file(".wav")
            voice_vol = self.voice_volume.get() if not self.cli_mode else CONFIG.VOICE_VOLUME
            print(f"  [AUDIO] 음성 볼륨: {voice_vol:.2f} ({voice_vol*100:.0f}%)")
            
            cmd_voice = [
                "ffmpeg", "-y", "-i", voice_with_intro,
                "-af", f"volume={voice_vol}", voice_boost
            ]
            result = run_subprocess_hidden(cmd_voice, capture_output=True)
            if result.returncode != 0:
                print(f"  [ERROR] 음성 볼륨 적용 실패: {result.stderr.decode()}")
                return False
            
            if not music_path or not os.path.exists(music_path):
                print("  [AUDIO] 배경음악 없음, 음성만 저장")
                cmd_final = [
                    "ffmpeg", "-y", "-i", voice_boost,
                    "-c:a", "libmp3lame", "-q:a", "2", output_path
                ]
                result = run_subprocess_hidden(cmd_final, capture_output=True)
                if result.returncode != 0:
                    print(f"  [ERROR] MP3 변환 실패: {result.stderr.decode()}")
                    return False
                
                print(f"  [AUDIO] 음성만 저장 완료: {output_path}")
                return True
            
            result = run_subprocess_hidden(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", music_path],
                capture_output=True, text=True
            )
            music_duration = float(result.stdout.strip())
            total_duration = CONFIG.INTRO_MUSIC + voice_duration + CONFIG.OUTRO_MUSIC
            
            music_loop = self.temp_manager.create_temp_file(".wav")
            cmd_loop = [
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", music_path,
                "-t", str(total_duration), "-vn", "-ac", "2", "-ar", str(CONFIG.SAMPLE_RATE),
                "-c:a", "pcm_s16le", music_loop
            ]
            result = run_subprocess_hidden(cmd_loop, capture_output=True)
            if result.returncode != 0:
                print(f"  [ERROR] 음악 반복 실패: {result.stderr.decode()}")
                return False
            
            music_processed = self.temp_manager.create_temp_file(".wav")
            if self.cli_mode:
                music_vol = CONFIG.MUSIC_VOLUME
                fade_in_val = CONFIG.FADE_IN
                fade_out_val = CONFIG.FADE_OUT
            else:
                music_vol = self.music_volume.get()
                fade_in_val = self.fade_in.get()
                fade_out_val = self.fade_out.get()
            
            print(f"  [AUDIO] 음악 원본 길이: {music_duration:.2f}초")
            print(f"  [AUDIO] 전체 믹싱 길이: {total_duration:.2f}초")
            print(f"  [AUDIO] 음악 볼륨: {music_vol:.2f} ({music_vol*100:.0f}%)")
            
            fade_start = max(0, total_duration - fade_out_val)
            vol_filter = f"volume={music_vol}"
            if fade_in_val > 0:
                vol_filter += f",afade=t=in:d={min(fade_in_val, CONFIG.INTRO_MUSIC)}"
            if fade_out_val > 0:
                vol_filter += f",afade=t=out:st={fade_start}:d={fade_out_val}"
            
            cmd_volume = ["ffmpeg", "-y", "-i", music_loop, "-af", vol_filter, music_processed]
            result = run_subprocess_hidden(cmd_volume, capture_output=True)
            if result.returncode != 0:
                print(f"  [ERROR] 음악 볼륨 적용 실패: {result.stderr.decode()}")
                return False
            
            cmd_mix = [
                "ffmpeg", "-y", "-i", voice_boost, "-i", music_processed,
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95",
                "-c:a", "libmp3lame", "-q:a", "2", output_path
            ]
            
            result = run_subprocess_hidden(cmd_mix, capture_output=True)
            if result.returncode != 0:
                print(f"  [ERROR] 최종 믹싱 실패: {result.stderr.decode()}")
                return False
            
            print(f"  [AUDIO] 믹싱 완료: {output_path}")
            return True
            
        except Exception as e:
            print(f"  [ERROR] 믹싱 오류: {e}")
            traceback.print_exc()
            return False
    
    def add_silence_padding_to_audio(self, input_path: str, silence_ms: Optional[int] = None) -> str:
        """각 TTS 조각 뒤에만 짧은 무음을 붙여 대사 사이의 인위적인 끊김을 줄입니다."""
        silence_ms = CONFIG.TTS_CHUNK_SILENCE_MS if silence_ms is None else int(silence_ms)
        if silence_ms <= 0:
            return input_path

        try:
            padded_path = self.temp_manager.create_temp_file(".wav")
            silence_path = self.temp_manager.create_temp_file(".wav")
            concat_list = self.temp_manager.create_temp_file(".txt")
            silence_sec = max(0.0, silence_ms / 1000.0)

            run_subprocess_hidden([
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r={CONFIG.SAMPLE_RATE}:cl=stereo",
                "-t", f"{silence_sec:.3f}",
                "-ac", "2",
                "-ar", str(CONFIG.SAMPLE_RATE),
                "-c:a", "pcm_s16le",
                silence_path
            ], capture_output=True)

            normalized_input = self.temp_manager.create_temp_file(".wav")
            normalize_result = run_subprocess_hidden([
                "ffmpeg", "-y",
                "-i", input_path,
                "-ac", "2",
                "-ar", str(CONFIG.SAMPLE_RATE),
                "-c:a", "pcm_s16le",
                normalized_input
            ], capture_output=True)

            if normalize_result.returncode != 0:
                print(f"  [WARNING] TTS 조각 정규화 실패, 원본 사용: {normalize_result.stderr.decode(errors='ignore')}")
                normalized_input = input_path

            with open(concat_list, "w", encoding="utf-8") as f:
                f.write(f"file '{normalized_input}'\n")
                f.write(f"file '{silence_path}'\n")

            concat_result = run_subprocess_hidden([
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list,
                "-ac", "2",
                "-ar", str(CONFIG.SAMPLE_RATE),
                "-c:a", "pcm_s16le",
                padded_path
            ], capture_output=True)

            if concat_result.returncode != 0:
                print(f"  [WARNING] TTS 무음 패딩 실패, 원본 사용: {concat_result.stderr.decode(errors='ignore')}")
                return input_path

            print(f"  [TTS DEBUG] silence_before_after = {silence_ms}ms")
            return padded_path

        except Exception as e:
            print(f"  [WARNING] TTS 무음 패딩 오류, 원본 사용: {e}")
            return input_path

    # =========================================================================
    # 팟캐스트 생성 (취소 기능 추가)
    # =========================================================================
    async def generate_podcast_async(self, script_text: str, output_mp3: str, output_srt: str = None):
        self.generation_cancelled = False
        
        try:
            segments = self.parse_dialogue(script_text)
            if not segments:
                print("[ERROR] 파싱된 세그먼트 없음")
                return False
            
            speech_segments = [s for s in segments if s['type'] == 'speech']
            pause_segments = [s for s in segments if s['type'] == 'pause']
            
            if not speech_segments:
                print("[ERROR] 음성 세그먼트 없음")
                return False
            
            total_speech = len(speech_segments)
            voice_files = []
            voice_duration = 0.0
            
            for i, seg in enumerate(speech_segments):
                if self.generation_cancelled:
                    print("[CANCEL] 사용자에 의해 생성 취소됨")
                    return False
                
                print(f"\n[TTS] {i+1}/{total_speech}")
                temp_file = self.temp_manager.create_temp_file(".wav")
                result = await self.create_tts(seg['content'], seg['speaker'], seg.get('effects', []), temp_file)
                
                if result:
                    duration = FFmpegUtils.get_duration(result)
                    print(f"  [TTS DEBUG] chunk_duration_before_padding = {duration:.3f}s")
                    if duration < CONFIG.TTS_MIN_CHUNK_DURATION:
                        print(f"  [WARNING] TTS 조각 길이가 너무 짧습니다. 원문을 확인하세요: {seg['content'][:40]}")

                    padded_result = self.add_silence_padding_to_audio(result)
                    padded_duration = FFmpegUtils.get_duration(padded_result)
                    print(f"  [TTS DEBUG] chunk_duration_after_padding = {padded_duration:.3f}s")

                    voice_files.append(padded_result)
                    voice_duration += padded_duration
                    self.update_progress(int((i+1)/total_speech*50), f"TTS 생성 중... ({i+1}/{total_speech})")
                else:
                    print(f"  [ERROR] TTS 생성 실패")
            
            if not voice_files:
                print("[ERROR] 생성된 음성 파일 없음")
                return False
            
            if self.generation_cancelled:
                return False
            
            for seg in pause_segments:
                pause_file = self.temp_manager.create_temp_file(".wav")
                run_subprocess_hidden([
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-t", str(seg.get('duration', 1.0)), "-c:a", "pcm_s16le", pause_file
                ], capture_output=True)
                if os.path.exists(pause_file):
                    voice_files.append(pause_file)
                    voice_duration += seg.get('duration', 1.0)
            
            if self.generation_cancelled:
                return False
            
            music_file = self.select_music_file()
            if music_file:
                print(f"  [MUSIC] 배경음악: {os.path.basename(music_file)}")
            
            self.update_progress(70, "오디오 믹싱 중...")
            
            if self.generation_cancelled:
                return False
            
            if self.mix_audio(voice_files, music_file, output_mp3, voice_duration):
                self.update_progress(90, "자막 생성 중...")
                
                if output_srt and ((not self.cli_mode and self.generate_subtitles.get()) or 
                                 (self.cli_mode and self.generate_subtitles_value)):
                    self.generate_srt(segments, voice_files, output_srt)
                
                self.update_progress(100, "✅ 생성 완료!")
                return True
            else:
                print("[ERROR] 오디오 믹싱 실패")
                return False
            
        except Exception as e:
            print(f"[ERROR] 생성 중 오류: {e}")
            traceback.print_exc()
            return False
    
    def generate_podcast_cli(self, script_path: str, output_mp3: str, output_srt: str = None):
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                script_text = f.read()
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.generate_podcast_async(script_text, output_mp3, output_srt)
                )
            finally:
                loop.close()
        except Exception as e:
            print(f"[ERROR] {e}")
            return False
    
    def generate_podcast(self):
        """GUI 모드 생성 (취소 기능 포함)"""
        def run():
            with self.temp_manager:
                self.start_time = time.time()
                self.progress_bar.set(0)
                self.generate_btn.configure(state="disabled", text="⏳ 생성중...")
                self.cancel_btn.configure(state="normal", text="⏹ 생성 취소", command=self.cancel_generation)
                self.generation_cancelled = False
                self.update_status("팟캐스트 생성 시작...", "info")

                try:
                    text = self.text_input.get("1.0", "end-1c").strip()
                    if not text:
                        self.update_status("⚠️ 스크립트를 입력하세요", "warning")
                        self.window.after(0, self.reset_buttons)
                        return

                    entered_title = ""
                    if hasattr(self, "output_filename_entry"):
                        try:
                            entered_title = self.output_filename_entry.get().strip()
                        except Exception:
                            entered_title = ""
                    if not entered_title and hasattr(self, "output_filename_var"):
                        entered_title = self.output_filename_var.get().strip()

                    entered_title = sanitize_output_filename(entered_title)

                    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                    if not entered_title:
                        entered_title = timestamp
                        self.update_status("파일명을 날짜/시간으로 자동 생성합니다", "info")
                        print(f"[INFO] 타이틀 없음 → 자동 파일명: {entered_title}")

                    self.output_filename_var.set(entered_title)
                    if entered_title == timestamp:
                        base_name = entered_title
                    else:
                        base_name = f"{entered_title}_{timestamp}"

                    # 같은 초에 여러 번 생성해도 덮어쓰지 않도록 중복 파일명을 피합니다.
                    candidate = base_name
                    suffix_idx = 1
                    while os.path.exists(os.path.join(CONFIG.OUTPUT_DIR, f"{candidate}.mp3")):
                        suffix_idx += 1
                        candidate = f"{base_name}_{suffix_idx:02d}"
                    base_name = candidate

                    output_mp3 = os.path.join(CONFIG.OUTPUT_DIR, f"{base_name}.mp3")
                    output_srt = os.path.join(CONFIG.OUTPUT_DIR, f"{base_name}.srt")

                    print(f"\n[INFO] 출력 파일: {output_mp3}")
                    print(f"[INFO] 제목: {entered_title}")

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        success = loop.run_until_complete(
                            self.generate_podcast_async(text, output_mp3, output_srt)
                        )
                    finally:
                        try:
                            loop.run_until_complete(loop.shutdown_asyncgens())
                        except Exception:
                            pass
                        loop.close()

                    if success and not self.generation_cancelled:
                        elapsed = time.time() - self.start_time
                        cache_stats = self.tts_cache.get_stats()

                        try:
                            self.save_project_snapshot(base_name, text)
                        except Exception as save_err:
                            print(f"[WARN] 프로젝트 자동 저장 실패: {save_err}")

                        self.current_audio_file = os.path.abspath(output_mp3)
                        self.current_srt_file = self.find_matching_srt(self.current_audio_file)
                        if output_srt and os.path.exists(output_srt):
                            self.current_srt_file = output_srt

                        if self.current_srt_file:
                            self.load_subtitles(self.current_srt_file)
                        else:
                            self.subtitle_subs = None
                            self.last_subtitle_text = ""
                            self.subtitle_text.configure(text="🎵 자막 파일이 없습니다")
                            self.update_full_subtitle_view()

                        self.window.after(0, lambda: self.update_player_after_generation(
                            self.current_audio_file, self.current_srt_file, elapsed, cache_stats
                        ))
                        self.window.after(0, lambda: self.output_filename_var.set(""))
                        if hasattr(self, "output_filename_entry"):
                            self.window.after(0, lambda: self.output_filename_entry.delete(0, "end"))
                        self.window.after(500, self.start_playback)

                    elif self.generation_cancelled:
                        self.update_status("⏹ 생성 취소됨", "warning")
                    else:
                        self.update_status("❌ 생성 실패", "error")

                    self.window.after(0, self.reset_buttons)

                except Exception as e:
                    print(f"[ERROR] 생성 중 오류: {e}")
                    traceback.print_exc()
                    self.update_status(f"❌ 오류: {str(e)[:50]}", "error")
                    self.window.after(0, self.reset_buttons)

        threading.Thread(target=run, daemon=True).start()

    def reset_buttons(self):
        """버튼 상태 초기화"""
        self.generate_btn.configure(state="normal", text="🎙️ 팟캐스트 생성")
        self.cancel_btn.configure(state="disabled", text="⏹ 생성 취소")
        self.progress_bar.set(0)

    def cancel_generation(self):
        self.generation_cancelled = True
        self.update_status("⏹ 생성 취소 중...", "warning")
        self.cancel_btn.configure(state="disabled")
    
    def update_player_after_generation(self, mp3_path, srt_path, elapsed, cache_stats):
        minutes, seconds = divmod(int(elapsed), 60)
        self.current_srt_file = srt_path or self.find_matching_srt(mp3_path)

        self.current_file_label.configure(
            text=f"📁 {os.path.basename(mp3_path)} ({minutes}분 {seconds}초)",
            text_color=COLOR_THEME["success"]
        )

        self.play_btn.configure(state="normal", command=self.toggle_playback)
        self.stop_btn.configure(state="normal", command=self.stop_playback)
        self.generate_btn.configure(state="normal", text="🎙️ 팟캐스트 생성")

        if self.current_srt_file:
            self.load_subtitles(self.current_srt_file)
        else:
            self.subtitle_subs = None
            self.last_subtitle_text = ""
            self.subtitle_text.configure(text="🎵 자막 파일이 없습니다")
            self.update_full_subtitle_view()

        self.update_status(f"✅ 생성 완료! ({minutes}분 {seconds}초)", "success")
        self.cache_label.configure(text=f"💾 {cache_stats}")

    def auto_play_generated(self):
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            self.start_playback()
    
    # =========================================================================
    # 설정 저장/로드
    # =========================================================================
    def save_settings(self):
        try:
            settings = {
                "tts_engine": self.tts_engine.get(),
                "openai_api_key": self.openai_api_key.get(),
                "speed": self.speed.get(),
                "pitch": self.pitch.get(),
                "volume": self.volume.get(),
                "voice_volume": self.voice_volume.get(),
                "music_volume": self.music_volume.get(),
                "fade_in": self.fade_in.get(),
                "fade_out": self.fade_out.get(),
                "music_folder": self.music_folder.get(),
                "random_music": self.random_music.get(),
                "generate_subtitles": self.generate_subtitles.get(),
                "male_voice": self.male_voice.get(),
                "female_voice": self.female_voice.get(),
                "supertonic_male_voice": self.supertonic_male_voice.get(),
                "supertonic_female_voice": self.supertonic_female_voice.get(),
                "openai_male_voice": self.openai_male_voice.get(),
                "openai_female_voice": self.openai_female_voice.get(),
                "selected_music_file": self.selected_music_file if hasattr(self, 'selected_music_file') else "",
                "output_filename": self.output_filename_var.get() if hasattr(self, "output_filename_var") else "",
                "player_volume": self.player_volume.get(),
                "cat_voices": {cat: var.get() for cat, var in self.cat_voice_vars.items()},
                "cat_speeds": {cat: var.get() for cat, var in self.cat_speed_vars.items()}
            }
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"[ERROR] 설정 저장 실패: {e}")
    
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8-sig') as f:
                    settings = json.load(f)
                
                if "tts_engine" in settings:
                    self.tts_engine.set(settings["tts_engine"])
                if "openai_api_key" in settings:
                    self.openai_api_key.set(settings["openai_api_key"])
                if "speed" in settings:
                    self.speed.set(settings["speed"])
                if "pitch" in settings:
                    self.pitch.set(settings["pitch"])
                if "volume" in settings:
                    self.volume.set(settings["volume"])
                if "voice_volume" in settings:
                    self.voice_volume.set(settings["voice_volume"])
                if "music_volume" in settings:
                    self.music_volume.set(settings["music_volume"])
                if "fade_in" in settings:
                    self.fade_in.set(settings["fade_in"])
                if "fade_out" in settings:
                    self.fade_out.set(settings["fade_out"])
                if "music_folder" in settings:
                    self.music_folder.set(settings["music_folder"])
                if "random_music" in settings:
                    self.random_music.set(settings["random_music"])
                if "generate_subtitles" in settings:
                    self.generate_subtitles.set(settings["generate_subtitles"])
                if "male_voice" in settings:
                    self.male_voice.set(settings["male_voice"])
                if "female_voice" in settings:
                    self.female_voice.set(settings["female_voice"])
                if "supertonic_male_voice" in settings:
                    self.supertonic_male_voice.set(settings["supertonic_male_voice"])
                if "supertonic_female_voice" in settings:
                    self.supertonic_female_voice.set(settings["supertonic_female_voice"])
                if "openai_male_voice" in settings:
                    self.openai_male_voice.set(settings["openai_male_voice"])
                if "openai_female_voice" in settings:
                    self.openai_female_voice.set(settings["openai_female_voice"])
                
                if "selected_music_file" in settings and settings["selected_music_file"]:
                    if os.path.exists(settings["selected_music_file"]):
                        self.selected_music_file = settings["selected_music_file"]
                        self.music_file_var.set(os.path.basename(settings["selected_music_file"]))
                if "output_filename" in settings and hasattr(self, "output_filename_var"):
                    self.output_filename_var.set(settings["output_filename"])
                if "player_volume" in settings:
                    self.player_volume.set(settings["player_volume"])
                
                if "cat_voices" in settings:
                    for cat, voice in settings["cat_voices"].items():
                        normalized_cat = CONFIG.normalize_cat_name(cat)
                        if normalized_cat in self.cat_voice_vars:
                            self.cat_voice_vars[normalized_cat].set(voice)
                if "cat_speeds" in settings:
                    for cat, speed in settings["cat_speeds"].items():
                        normalized_cat = CONFIG.normalize_cat_name(cat)
                        if normalized_cat in self.cat_speed_vars:
                            try:
                                self.cat_speed_vars[normalized_cat].set(float(speed))
                            except:
                                pass
                
                self.on_tts_engine_change()
                
        except Exception as e:
            print(f"[ERROR] 설정 로드 실패: {e}")
    
    def save_openai_key(self):
        key = self.openai_api_key.get().strip()
        if key:
            try:
                key_file = os.path.join(CONFIG.SCRIPT_DIR, "openai_key.txt")
                with open(key_file, 'w', encoding='utf-8') as f:
                    f.write(key)
                CONFIG.OPENAI_API_KEY = key
                self.update_status("✅ API 키 저장됨", "success")
                self.save_settings()
            except Exception as e:
                self.update_status(f"❌ {e}", "error")
        else:
            self.update_status("⚠️ API 키를 입력하세요", "warning")
    
    def update_progress(self, value: int, status: str):
        if not hasattr(self, 'window'):
            return
        self.window.after(0, lambda: self.progress_bar.set(value / 100))
        self.window.after(0, lambda: self.status_label.configure(text=status))
        
        if self.start_time and value > 0 and not self.generation_cancelled:
            elapsed = time.time() - self.start_time
            if value < 100:
                estimated = (elapsed / value) * 100
                remaining = estimated - elapsed
                time_text = f"⏱️ 경과: {time.strftime('%M:%S', time.gmtime(elapsed))} (남음: {int(remaining//60)}분 {int(remaining%60)}초)"
            else:
                time_text = f"⏱️ 총 시간: {time.strftime('%M:%S', time.gmtime(elapsed))}"
            self.window.after(0, lambda: self.time_label.configure(text=time_text))
        
        cache_stats = self.tts_cache.get_stats()
        self.window.after(0, lambda: self.cache_label.configure(text=f"💾 {cache_stats}"))
    
    def update_status(self, message: str, status_type: str = "info"):
        if not hasattr(self, 'window'):
            print(f"{status_type.upper()}: {message}")
            return
        colors = {
            "success": COLOR_THEME["success"],
            "warning": COLOR_THEME["warning"],
            "error": COLOR_THEME["error"],
            "info": COLOR_THEME["text_accent"]
        }
        self.window.after(0, lambda: self.status_label.configure(
            text=message, text_color=colors.get(status_type, COLOR_THEME["text_secondary"])
        ))
    

    def clear_project_fields(self):
        """신규작성 시 스크립트/파일명 초기화"""
        try:
            self.text_input.delete("1.0", "end")
        except Exception:
            pass

        if hasattr(self, "output_filename_var"):
            self.output_filename_var.set("")
        if hasattr(self, "output_filename_entry"):
            try:
                self.output_filename_entry.delete(0, "end")
            except Exception:
                pass

        self.update_status("✅ 새 프로젝트 준비 완료", "success")

    def new_project(self):
        """신규작성 버튼"""
        script_text = ""
        title_text = ""
        try:
            script_text = self.text_input.get("1.0", "end-1c").strip()
        except Exception:
            pass
        try:
            if hasattr(self, "output_filename_entry"):
                title_text = self.output_filename_entry.get().strip()
            elif hasattr(self, "output_filename_var"):
                title_text = self.output_filename_var.get().strip()
        except Exception:
            pass

        if script_text or title_text:
            ok = messagebox.askyesno("신규작성", "현재 작성 중인 내용이 지워집니다. 신규작성 하시겠습니까?")
            if not ok:
                return

        self.clear_project_fields()

    def save_project_snapshot(self, base_name: str, script_text: str) -> str:
        """스크립트 내용만 PROJECT 폴더에 저장"""
        project_folder = self.get_project_folder()
        project_path = os.path.join(project_folder, f"{base_name}.json")
        payload = {
            "script": script_text
        }
        with open(project_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return project_path

    def choose_recent_project_file(self) -> str:
        """최근 수정 순으로 프로젝트 선택"""
        project_folder = self.get_project_folder()
        files = []
        if os.path.isdir(project_folder):
            for name in os.listdir(project_folder):
                if name.lower().endswith(".json"):
                    path = os.path.join(project_folder, name)
                    try:
                        mtime = os.path.getmtime(path)
                    except Exception:
                        mtime = 0
                    files.append((mtime, path))

        if not files:
            messagebox.showinfo("프로젝트 없음", "불러올 프로젝트가 없습니다.")
            return ""

        files.sort(key=lambda x: x[0], reverse=True)
        ordered_paths = [p for _, p in files]

        popup = tk.Toplevel(self.window)
        popup.title("프로젝트 불러오기")
        popup.geometry("760x520")
        popup.transient(self.window)
        popup.grab_set()

        selected = {"path": ""}

        frame = ctk.CTkFrame(popup)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            frame,
            text="최근 작업한 프로젝트 순서",
            font=self.font_manager.get_font('heading', 'bold'),
            text_color=COLOR_THEME["text_accent"]
        ).pack(anchor="w", pady=(0, 10))

        listbox = tk.Listbox(
            frame,
            font=(CONFIG.FONT_FAMILY, 12),
            bg="#2a2a2a",
            fg="white",
            selectbackground=COLOR_THEME["primary"]
        )
        listbox.pack(fill="both", expand=True, pady=(0, 12))

        for path in ordered_paths:
            listbox.insert(tk.END, os.path.basename(path))

        def confirm():
            if not listbox.curselection():
                return
            idx = listbox.curselection()[0]
            selected["path"] = ordered_paths[idx]
            popup.destroy()

        def on_double(_event=None):
            confirm()

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x")

        ctk.CTkButton(btn_row, text="불러오기", command=confirm).pack(side="left")
        ctk.CTkButton(btn_row, text="취소", command=popup.destroy, fg_color="#555555").pack(side="right")

        listbox.bind("<Double-Button-1>", on_double)
        if ordered_paths:
            listbox.selection_set(0)

        popup.wait_window()
        return selected["path"]

    def save_project(self):
        project_folder = self.get_project_folder()
        default_name = ""
        try:
            if hasattr(self, "output_filename_entry"):
                default_name = self.output_filename_entry.get().strip()
            elif hasattr(self, "output_filename_var"):
                default_name = self.output_filename_var.get().strip()
        except Exception:
            default_name = ""

        default_name = sanitize_output_filename(default_name) or "project"

        file_path = filedialog.asksaveasfilename(
            title="프로젝트 저장",
            initialdir=project_folder,
            initialfile=f"{default_name}.json",
            defaultextension=".json",
            filetypes=[("Project files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                project = {
                    "script": self.text_input.get("1.0", "end-1c")
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(project, f, ensure_ascii=False, indent=2)
                self.update_status("✅ 프로젝트 저장됨", "success")
            except Exception as e:
                self.update_status(f"❌ {e}", "error")

    def load_project(self):
        file_path = self.choose_recent_project_file()
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    project = json.load(f)

                self.text_input.delete("1.0", "end")
                self.text_input.insert("1.0", project.get("script", ""))

                title = sanitize_output_filename(Path(file_path).stem)
                if hasattr(self, "output_filename_var"):
                    self.output_filename_var.set(title)
                if hasattr(self, "output_filename_entry"):
                    try:
                        self.output_filename_entry.delete(0, "end")
                        self.output_filename_entry.insert(0, title)
                    except Exception:
                        pass

                self.update_status("✅ 프로젝트 로드됨", "success")

            except Exception as e:
                self.update_status(f"❌ {e}", "error")

    def quit_program(self):

        self.save_settings()
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        self.temp_manager.cleanup()
        if hasattr(self, 'window'):
            self.window.quit()
            self.window.destroy()
        os._exit(0)
    
    def run(self):
        if hasattr(self, 'window'):
            self.window.mainloop()


# =============================================================================
# 메인 실행
# =============================================================================
def main(embed_mode=False, parent=None):
    if embed_mode:
        app = PodcastGenerator(cli_mode=False, embed_mode=True, parent=parent)
        return app
    else:
        app = PodcastGenerator()
        app.run()

if __name__ == "__main__":
    import io
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="ignore")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="ignore")
    except:
        pass

    parser = argparse.ArgumentParser(description='Supertonic3 팟캐스트 생성기 v2.0')
    parser.add_argument('--script', type=str, help='대본 파일 경로')
    parser.add_argument('--output-mp3', type=str, help='출력 MP3 파일 경로')
    parser.add_argument('--output-srt', type=str, help='출력 SRT 파일 경로')
    parser.add_argument('--openai-key', type=str, help='OpenAI API 키')
    parser.add_argument('--male-voice', type=str)
    parser.add_argument('--female-voice', type=str)
    parser.add_argument('--speed', type=float, default=1.0)
    parser.add_argument('--music-folder', type=str, default='')
    parser.add_argument('--music-random', choices=('true', 'false'), default='true')
    parser.add_argument('--music-volume', type=float, default=CONFIG.MUSIC_VOLUME)
    parser.add_argument('--no-gui', action='store_true', help='CLI 모드')
    parser.add_argument('--embed', action='store_true', help='프레임 모드')

    args = parser.parse_args()

    print("\n" + "="*60)
    print("🎙️ Supertonic3 팟캐스트 생성기 v2.0")
    print("="*60)

    try:
        import numpy as np
        print("✅ numpy")
    except:
        print("❌ numpy 없음")
        sys.exit(1)

    try:
        import openai
        print("✅ openai")
    except:
        print("⚠️ openai 없음 (OpenAI TTS 사용 불가)")

    try:
        import edge_tts
        print("✅ edge_tts")
    except:
        print("⚠️ edge_tts 없음 (Edge TTS 사용 불가)")

    try:
        run_subprocess_hidden(["ffmpeg", "-version"], capture_output=True, check=True)
        print("✅ FFmpeg")
    except:
        print("❌ FFmpeg 없음")
        sys.exit(1)

    try:
        import pysrt
        print("✅ pysrt")
    except:
        print("⚠️ pysrt 없음 (자막 시간 표시 제한적)")

    print("="*60 + "\n")

    if args.no_gui:
        if not args.script or not args.output_mp3:
            print("[ERROR] --script, --output-mp3 필요")
            sys.exit(1)

        if args.openai_key:
            CONFIG.OPENAI_API_KEY = args.openai_key
        if args.music_folder:
            CONFIG.MUSIC_DIR = args.music_folder
        CONFIG.MUSIC_VOLUME = max(0.0, min(1.0, args.music_volume))

        app = PodcastGenerator(cli_mode=True)
        cli_tts_engine = os.getenv("PODCAST_TTS_ENGINE", "supertonic").strip().lower() or "supertonic"
        if cli_tts_engine not in {"supertonic", "edge_tts", "edge", "openai"}:
            print(f"[WARNING] 알 수 없는 TTS 엔진: {cli_tts_engine} → supertonic 사용")
            cli_tts_engine = "supertonic"
        if cli_tts_engine == "edge":
            cli_tts_engine = "edge_tts"
        CONFIG.TTS_ENGINE = cli_tts_engine
        app.tts_engine_value = cli_tts_engine
        print(f"[INFO] CLI TTS 엔진: {CONFIG.TTS_ENGINE}")
        app.speed_value = max(0.5, min(2.0, args.speed))
        app.music_random_value = args.music_random == 'true'
        app.generate_subtitles_value = True

        success = app.generate_podcast_cli(args.script, args.output_mp3, args.output_srt)
        sys.exit(0 if success else 1)

    elif args.embed:
        pass
    else:
        print(f"[INFO] 출력 폴더: {CONFIG.OUTPUT_DIR}")
        print(f"[INFO] 음악 폴더: {CONFIG.MUSIC_DIR}")
        print(f"[INFO] 캐시 폴더: {CONFIG.CACHE_DIR}")
        print(f"[INFO] Supertonic 기본 화자: M1, M2, M3, M4, M5, F1, F2, F3, F4, F5")
        print("="*60 + "\n")

        app = PodcastGenerator()
        app.run()
