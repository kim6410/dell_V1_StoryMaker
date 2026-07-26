from __future__ import annotations
"""
SLID_gpt_STABLE_v5_2_ADVANCED.py
------------------------------------------------------------
✅ 최종 수정사항 (2024)
- 1080x1920(9:16) 고정: 쇼츠/릴스/숏폼 전용
- "잘림 없이 전체 노출" + 여백은 '물에 비친 듯한 강한 반사(블러) 배경'
- 이미지 순서/전환 효과/색보정은 매 실행마다 랜덤
- ✅ 오디오 길이에 맞춰 이미지 자동 반복 (회전마다 랜덤 셔플)
- ✅ UI에서 모든 설정값 실시간 편집 가능
- ✅ 첫 프레임 미리보기
- ✅ 설정 프리셋 저장/불러오기 + 자동 저장/복원
- ✅ JSON 고급 편집 모드
- ✅ 멀티 상태바 (전처리/인코딩 분리 + 예상시간 + 상세 정보)
- ✅ 설정값 검증 시스템 (경고 표시)
- ✅ 파일 크기 최적화 (모바일 숏폼용 15-20MB 목표, CRF 28 적용)
- ✅ 오디오/자막 파일 동시 선택 (파일명 동일, 확장자만 다른 경우)
- ✅ 느린 중앙 줌 (zoom_intensity=0.003, 매우 미세하게)
- ✅ 줌팬 효과 (매우 약하게, 위험도 분석 옵션)
- ✅ 오디오 랜덤 선택 (폴더 내 MP3 랜덤)
- ✅ MP4 파일명 = 이미지 폴더명
- ✅ 상호/전화번호 개별 폰트 크기 조절
- ✅ 🔥 수정: 30초에서 멈추는 문제 해결 (이미지 반복 로직 강화)
- ✅ 🔥 수정: get_hidden_startup_kwargs 함수 추가
- ✅ 🔥 수정: 설정값 실시간 반영 메커니즘 강화
- ✅ 🔥 수정: 파일 선택 후 자동 저장 기능 추가
- ✅ 🔥 수정: 프리뷰 디바운싱 적용
- ✅ 🔥 추가: 하단 그라데이션 박스 (워터마크 배경박스 재활용)
- ✅ 🔥 추가: 투명도/높이 조절 슬라이더
- ✅ 🔥 추가: VLC 기반 영상 프리뷰 플레이어 (자동 경로 탐색)
- ✅ 🔥 추가: 출력 폴더 바로가기 버튼
- ✅ 🔥 추가: 작업 완료 후 자동 영상 재생
"""

import os
import re
import random
import time
import shutil
import subprocess
import threading
import queue
import json
import sys
import copy
from pathlib import Path

from fm_paths import BASE_DIR, SLID_RUNTIME_DIR, ensure_dirs, find_vlc_executable, hide_console
from dataclasses import dataclass, asdict
from typing import Optional, List, Tuple
from math import ceil

import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageFile, ImageOps
import tkinter.font as tkfont

# =============================================================================
# 앱 기본 경로 및 설정 파일 상수
# =============================================================================
APP_BASE_DIR = BASE_DIR / "slid_refactored"
APP_FONT_DIR = APP_BASE_DIR / "fonts"
APP_RUNTIME_DIR = SLID_RUNTIME_DIR
APP_PRESET_DIR = APP_RUNTIME_DIR / "presets"
APP_LOG_DIR = APP_RUNTIME_DIR / "logs"
APP_TEMP_DIR = APP_RUNTIME_DIR / "temp"
APP_SETTING_FILE = APP_RUNTIME_DIR / "SETTING.json"
APP_UI_STATE_FILE = APP_RUNTIME_DIR / "slid_ui_state.json"

def ensure_runtime_dirs():
    ensure_dirs(APP_RUNTIME_DIR, APP_PRESET_DIR, APP_LOG_DIR, APP_TEMP_DIR)

# VLC 바인딩 (pip install python-vlc 필요)
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    print("⚠️ python-vlc가 설치되지 않았습니다. 영상 프리뷰 기능이 제한됩니다.")
    print("   설치: pip install python-vlc")

hide_console()

ImageFile.LOAD_TRUNCATED_IMAGES = True
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
ensure_runtime_dirs()

# =============================================================================
# 🛠️ 누락된 함수 추가 (get_hidden_startup_kwargs)
# =============================================================================

def get_hidden_startup_kwargs():
    """Windows에서 서브프로세스 실행 시 콘솔 창을 숨기기 위한 설정 반환"""
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
    return {"startupinfo": startupinfo} if startupinfo else {}

# =============================================================================
# 🎛 설정 데이터 클래스 (설정값 구조화) - WatermarkSettings 확장
# =============================================================================

@dataclass
class VideoSettings:
    """영상 기본 설정"""
    width: int = 1080
    height: int = 1920
    fps: int = 30
    base_image_sec: float = 5.0
    transition_ratio: float = 1.0
    transition_min_sec: float = 0.35
    transition_max_sec: float = 1.50
    zoom_intensity: float = 0.004  # 기본 줌 강도(안정 구간)
    # 줌 방향: in | out | inout | outin | random
    zoom_direction: str = "random"
    # 최대 확대 상한(클수록 떨림/어지러움 증가)
    zoom_cap: float = 1.005
    zoom_center_only: bool = False
    enable_zoompam: bool = False
    zoompam_intensity: float = 0.001  # 매우 미세한 줌팬
    background_fallback_color: str = "black"
    
@dataclass
class ReflectionSettings:
    """반사 배경 설정"""
    strength: float = 1.60
    blur_radius: int = 55
    dim: float = 0.72
    gradient: float = 0.75

@dataclass
class ColorRandomSettings:
    """랜덤 색보정 설정"""
    enabled: bool = True
    sat_min: float = 0.98
    sat_max: float = 1.06
    contrast_min: float = 0.98
    contrast_max: float = 1.06
    bright_min: float = 0.96
    bright_max: float = 1.04

@dataclass
class WatermarkSettings:
    """워터마크 설정 (하단 워터마크 + 상단 설명 공용)"""
    font_name: str = "Pretendard Bold"
    brand_text: str = "오박사 만능인테리어"
    phone_text: str = "010-8284-5584"
    phone_gap_px: int = 0
    brand_font_size: int = 46
    phone_font_size: int = 43
    brand_color: str = "#FFD300"
    phone_color: str = "#FFFFFF"
    margin_bottom: int = 80
    x_offset: int = 0
    y_offset: int = 0
    title_enabled: bool = False
    subtitle_enabled: bool = False
    title_text: str = ""
    subtitle_text: str = ""
    title_font_size: int = 54
    subtitle_font_size: int = 34
    title_color: str = "#FFFFFF"
    subtitle_color: str = "#DDE7FF"
    title_margin_top: int = 80
    subtitle_gap_px: int = 14
    box_enabled: bool = True
    box_alpha: int = 70
    box_height_multiplier: float = 3.0
    box_pad_x: int = 20
    box_pad_y: int = 24
    stroke_enabled: bool = True
    stroke_width: int = 4
    stroke_color: str = "#000000"
    shadow_enabled: bool = True
    shadow_color: str = "#000000"
    shadow_offset_x: int = 2
    shadow_offset_y: int = 2

@dataclass
class SubtitleSettings:
    """자막 설정"""
    enabled: bool = True
    font_name: str = "Malgun Gothic"
    font_size: int = 8
    bold: bool = True
    margin_v: int = 40
    outline: int = 1
    shadow: int = 1
    box_mode: int = 0
    box_alpha: int = 0
    box_back_colour: str = "&H99000000&"
    primary_colour: str = "&H00FFFFFF&"


@dataclass
class ThumbnailSettings:
    width: int = 1080
    height: int = 1920
    image_path: str = ""
    font_name: str = "Pretendard Bold"
    title_enabled: bool = True
    subtitle_enabled: bool = True
    title_text: str = ""
    subtitle_text: str = ""
    brand_text: str = "오박사 만능인테리어"
    phone_text: str = "010-8284-5584"
    title_font_size: int = 88
    subtitle_font_size: int = 46
    brand_font_size: int = 58
    phone_font_size: int = 50
    title_color: str = "#FFFFFF"
    subtitle_color: str = "#DDE7FF"
    brand_color: str = "#FFD300"
    phone_color: str = "#FFFFFF"
    title_margin_top: int = 90
    subtitle_gap_px: int = 18
    margin_bottom: int = 90
    phone_gap_px: int = 10

@dataclass
class TransitionSettings:
    """전환 효과 설정"""
    style: str = "natural"
    shuffle_images: bool = True
    cycle_shuffle: bool = True
    reverse_cycle: bool = False
    transitions_natural: List[str] = None
    
    def __post_init__(self):
        if self.transitions_natural is None:
            self.transitions_natural = [
                "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
                "slideleft", "slideright", "slideup", "slidedown",
                "smoothleft", "smoothright", "smoothup", "smoothdown",
                "circleopen", "circleclose", "horzopen", "horzclose", "vertopen", "vertclose"
            ]

@dataclass
class EncodingSettings:
    """인코딩 설정 (모바일 숏폼용 최적화 - CRF 28 적용)"""
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    enc_primary: str = "h264_nvenc"
    nvenc_preset: str = "p4"
    enc_fallback: str = "libx264"
    x264_preset: str = "medium"
    x264_crf: int = 20
    x264_crf_optimized: int = 28  # 🔥 22 → 28 (모바일 숏폼용)
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"   # 🔥 160k → 128k
    pre_jpg_quality: int = 86
    preprocess_overwrite: bool = False
    no_progress_kill_sec: int = 90
    delete_temp_after_done: bool = True
    audio_random_enabled: bool = False
    audio_folder: str = ""

    # =============================================================================
    # ✅ 2버전 동시 생성 (SNS/HQ) 옵션
    # - 기본: SNS만 생성
    # - 체크박스로 SNS/HQ 선택 가능
    # =============================================================================
    out_sns_enabled: bool = True
    out_hq_enabled: bool = False


    # SNS 체크 시 자동 다운스케일(1080→720). HQ는 1080 유지
    sns_scale_down: bool = True
    sns_width: int = 720
    sns_height: int = 1280
    # SNS(경량) 권장값: 10MB 초반 목표
    sns_nvenc_cq: int = 32
    sns_x264_crf: int = 32
    sns_audio_bitrate: str = "96k"
    sns_x264_preset: str = "faster"
    sns_nvenc_preset: str = "p4"   # NVENC는 기존 p4 유지(속도/품질 밸런스)

    # HQ(고화질) 권장값: 40MB 이상(보관/광고용)
    hq_nvenc_cq: int = 20
    hq_x264_crf: int = 20
    hq_audio_bitrate: str = "192k"
    hq_x264_preset: str = "slow"
    hq_nvenc_preset: str = "p4"


@dataclass
class MediaSettings:
    """외부 동영상 믹스 설정"""
    enabled: bool = False
    placement: str = "interleave"   # interleave | append_end | prepend_start
    playback_speed: float = 1.00
    target_ratio: float = 0.25
    selected_files: List[str] = None
    interleave_balance: float = 0.50  # 0.0이면 앞쪽 치우침, 1.0이면 뒤쪽 치우침

    def __post_init__(self):
        if self.selected_files is None:
            self.selected_files = []


@dataclass
class AppSettings:
    """전체 애플리케이션 설정"""
    video: VideoSettings = None
    reflection: ReflectionSettings = None
    color_random: ColorRandomSettings = None
    watermark: WatermarkSettings = None  # 구버전 호환용(이미지 워터마크 별칭)
    image_watermark: ImageWatermarkSettings = None
    video_watermark: VideoWatermarkSettings = None
    subtitle: SubtitleSettings = None
    thumbnail: ThumbnailSettings = None
    transition: TransitionSettings = None
    encoding: EncodingSettings = None
    media: MediaSettings = None
    
    def __post_init__(self):
        if self.video is None: self.video = VideoSettings()
        if self.reflection is None: self.reflection = ReflectionSettings()
        if self.color_random is None: self.color_random = ColorRandomSettings()
        if self.image_watermark is None:
            self.image_watermark = ImageWatermarkSettings(**(asdict(self.watermark) if isinstance(self.watermark, WatermarkSettings) else {})) if self.watermark is not None else ImageWatermarkSettings()
        if self.video_watermark is None:
            self.video_watermark = VideoWatermarkSettings(**asdict(self.image_watermark))
        self.watermark = self.image_watermark
        if self.subtitle is None: self.subtitle = SubtitleSettings()
        if self.thumbnail is None:
            self.thumbnail = ThumbnailSettings(
                brand_text=self.image_watermark.brand_text,
                phone_text=self.image_watermark.phone_text,
                brand_color=self.image_watermark.brand_color,
                phone_color=self.image_watermark.phone_color,
                font_name=getattr(self.image_watermark, 'font_name', 'Pretendard Bold'),
            )
        if self.transition is None: self.transition = TransitionSettings()
        if self.encoding is None: self.encoding = EncodingSettings()
        if self.media is None: self.media = MediaSettings()
    
    def save_to_file(self, path: Path):
        data = {
            "video": asdict(self.video),
            "reflection": asdict(self.reflection),
            "color_random": asdict(self.color_random),
            "watermark": asdict(self.image_watermark),
            "image_watermark": asdict(self.image_watermark),
            "video_watermark": asdict(self.video_watermark),
            "subtitle": asdict(self.subtitle),
            "thumbnail": asdict(self.thumbnail),
            "transition": asdict(self.transition),
            "encoding": asdict(self.encoding),
            "media": asdict(self.media)
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, path: Path) -> 'AppSettings':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        settings = cls()
        settings.video = VideoSettings(**data.get('video', {}))
        settings.reflection = ReflectionSettings(**data.get('reflection', {}))
        settings.color_random = ColorRandomSettings(**data.get('color_random', {}))
        image_wm_data = data.get('image_watermark', data.get('watermark', {}))
        video_wm_data = data.get('video_watermark', image_wm_data)
        settings.image_watermark = ImageWatermarkSettings(**image_wm_data)
        settings.video_watermark = VideoWatermarkSettings(**video_wm_data)
        settings.watermark = settings.image_watermark
        settings.subtitle = SubtitleSettings(**data.get('subtitle', {}))
        settings.thumbnail = ThumbnailSettings(**data.get('thumbnail', {}))
        settings.transition = TransitionSettings(**data.get('transition', {}))
        settings.encoding = EncodingSettings(**data.get('encoding', {}))
        settings.media = MediaSettings(**data.get('media', {}))
        return normalize_settings_types(settings)

# =============================================================================
# 내부 유틸
# =============================================================================


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s=v.strip().lower()
        if s in {"1","true","yes","y","on","예","사용"}:
            return True
        if s in {"0","false","no","n","off","아니오","미사용",""}:
            return False
    return bool(v)

def _coerce_dataclass_fields(obj, type_map: dict[str, type]):
    for field_name, caster in type_map.items():
        if not hasattr(obj, field_name):
            continue
        try:
            raw = getattr(obj, field_name)
            if caster is bool:
                value = _to_bool(raw)
            elif caster is int:
                value = int(float(raw))
            elif caster is float:
                value = float(raw)
            elif caster is str:
                value = '' if raw is None else str(raw)
            else:
                value = raw
            setattr(obj, field_name, value)
        except Exception:
            pass

def normalize_settings_types(settings: AppSettings) -> AppSettings:
    """JSON/UI에서 문자열로 들어온 값을 안전하게 숫자/불리언으로 정규화"""
    _coerce_dataclass_fields(settings.video, {
        'width': int, 'height': int, 'fps': int, 'base_image_sec': float, 'transition_ratio': float,
        'transition_min_sec': float, 'transition_max_sec': float, 'zoom_intensity': float,
        'zoom_direction': str, 'zoom_cap': float, 'zoom_center_only': bool,
        'enable_zoompam': bool, 'zoompam_intensity': float, 'background_fallback_color': str,
    })
    _coerce_dataclass_fields(settings.reflection, {
        'strength': float, 'blur_radius': int, 'dim': float, 'gradient': float,
    })
    _coerce_dataclass_fields(settings.color_random, {
        'enabled': bool, 'sat_min': float, 'sat_max': float, 'contrast_min': float, 'contrast_max': float,
        'bright_min': float, 'bright_max': float,
    })
    for _wm in [getattr(settings, 'image_watermark', None), getattr(settings, 'video_watermark', None), getattr(settings, 'watermark', None)]:
        if _wm is None:
            continue
        _coerce_dataclass_fields(_wm, {
            'font_name': str, 'brand_text': str, 'phone_text': str, 'phone_gap_px': int, 'brand_font_size': int, 'phone_font_size': int,
            'brand_color': str, 'phone_color': str, 'margin_bottom': int, 'x_offset': int, 'y_offset': int,
            'title_enabled': bool, 'subtitle_enabled': bool, 'title_text': str, 'subtitle_text': str,
            'title_font_size': int, 'subtitle_font_size': int, 'title_color': str, 'subtitle_color': str,
            'title_margin_top': int, 'subtitle_gap_px': int,
            'box_enabled': bool, 'box_alpha': int, 'box_height_multiplier': float, 'box_pad_x': int,
        })
    settings.watermark = settings.image_watermark if getattr(settings, 'image_watermark', None) is not None else settings.watermark
    _coerce_dataclass_fields(settings.subtitle, {
        'enabled': bool, 'font_name': str, 'font_size': int, 'margin_v': int, 'outline': int, 'shadow': int,
        'bold': bool, 'box_mode': int, 'box_alpha': int, 'primary_colour': str, 'box_back_colour': str,
    })
    _coerce_dataclass_fields(settings.thumbnail, {
        'width': int, 'height': int, 'image_path': str, 'font_name': str,
        'title_enabled': bool, 'subtitle_enabled': bool, 'title_text': str, 'subtitle_text': str,
        'brand_text': str, 'phone_text': str, 'title_font_size': int, 'subtitle_font_size': int,
        'brand_font_size': int, 'phone_font_size': int, 'title_color': str, 'subtitle_color': str,
        'brand_color': str, 'phone_color': str, 'title_margin_top': int, 'subtitle_gap_px': int,
        'margin_bottom': int, 'phone_gap_px': int,
    })
    _coerce_dataclass_fields(settings.transition, {
        'shuffle_images': bool, 'cycle_shuffle': bool, 'reverse_cycle': bool, 'style': str,
    })
    if getattr(settings.transition, 'transitions_natural', None) is None:
        settings.transition.transitions_natural = []
    settings.transition.transitions_natural = [str(x) for x in list(getattr(settings.transition, 'transitions_natural', []) or [])]
    _coerce_dataclass_fields(settings.encoding, {
        'ffmpeg_bin': str, 'ffprobe_bin': str, 'enc_primary': str, 'enc_fallback': str, 'audio_codec': str,
        'audio_bitrate': str, 'nvenc_cq': int, 'x264_crf_optimized': int, 'x264_preset': str, 'nvenc_preset': str,
        'delete_temp_after_done': bool, 'audio_random_enabled': bool, 'audio_folder': str,
        'out_sns_enabled': bool, 'out_hq_enabled': bool, 'sns_scale_down': bool, 'sns_width': int, 'sns_height': int,
        'sns_nvenc_cq': int, 'sns_x264_crf': int, 'sns_audio_bitrate': str, 'sns_x264_preset': str, 'sns_nvenc_preset': str,
        'hq_nvenc_cq': int, 'hq_x264_crf': int, 'hq_audio_bitrate': str, 'hq_x264_preset': str, 'hq_nvenc_preset': str,
        'no_progress_kill_sec': int,
    })
    _coerce_dataclass_fields(settings.media, {
        'enabled': bool, 'placement': str, 'playback_speed': float, 'target_ratio': float, 'interleave_balance': float,
    })
    if getattr(settings.media, 'selected_files', None) is None:
        settings.media.selected_files = []
    settings.media.selected_files = [str(x) for x in list(getattr(settings.media, 'selected_files', []) or [])]
    return settings

def _ts():
    return time.strftime("%H:%M:%S")

def safe_print(s: str):
    try:
        print(s, flush=True)
    except Exception:
        pass

def normalize_output_stem(stem: str) -> str:
    stem = re.sub(r"^스크린샷\s*", "", stem)
    stem = re.sub(r"^KakaoTalk_", "", stem)
    stem = stem.strip()
    return stem if stem else "image"

def find_images(folder: Path):
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    out = []
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            out.append(p)
    return out

def find_audio_files(folder: Path):
    exts = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
    out = []
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            out.append(p)
    return out

FONT_PRESET_MAP = {
    "Pretendard ExtraBold": [APP_FONT_DIR / "Pretendard-ExtraBold.ttf", APP_FONT_DIR / "Pretendard-ExtraBold.otf", APP_FONT_DIR / "public/static/alternative/Pretendard-ExtraBold.ttf"],
    "Pretendard Bold": [APP_FONT_DIR / "Pretendard-Bold.ttf", APP_FONT_DIR / "Pretendard-Bold.otf", APP_FONT_DIR / "public/static/alternative/Pretendard-Bold.ttf"],
    "Pretendard Regular": [APP_FONT_DIR / "Pretendard-Regular.ttf", APP_FONT_DIR / "Pretendard-Regular.otf", APP_FONT_DIR / "public/static/alternative/Pretendard-Regular.ttf"],
}


def _font_search_roots() -> list[Path]:
    """프로그램 내부 fonts 폴더만 검색한다."""
    roots = []
    for candidate in [BASE_DIR / "fonts", APP_FONT_DIR, APP_FONT_DIR / "public/static", APP_FONT_DIR / "public/static/alternative"]:
        try:
            p = Path(candidate)
            if p.exists() and p not in roots:
                roots.append(p)
        except Exception:
            continue
    return roots


def _normalize_font_key(name: str | None) -> str:
    s = str(name or '').strip().lower()
    s = s.replace('_', ' ').replace('-', ' ')
    s = re.sub(r'\s+', ' ', s)
    return s


def _display_font_name(path: Path) -> str:
    stem = path.stem.replace('_', ' ').strip()
    stem = re.sub(r'\s+', ' ', stem)
    return stem


def _discover_font_map() -> dict[str, list[Path | str]]:
    merged: dict[str, list[Path | str]] = {}

    # 1) 프로그램 내부 preset 폰트 중 실제 존재하는 파일만 등록
    for display, candidates in FONT_PRESET_MAP.items():
        existing = []
        for fp in candidates:
            try:
                p = Path(fp)
                if p.exists():
                    existing.append(p)
            except Exception:
                continue
        if existing:
            merged[display] = existing

    # 2) 프로그램 내부 fonts 폴더만 재귀 검색
    seen_files = set()
    for roots in _font_search_roots():
        for pattern in ('*.ttf', '*.otf', '*.ttc'):
            for fp in roots.rglob(pattern):
                try:
                    rp = fp.resolve()
                except Exception:
                    rp = fp
                key = str(rp).lower()
                if key in seen_files:
                    continue
                seen_files.add(key)
                display = _display_font_name(fp)
                merged.setdefault(display, []).append(fp)
    return merged


def get_available_font_names():
    font_map = _discover_font_map()
    names = list(font_map.keys())
    pinned = [n for n in ["Pretendard ExtraBold", "Pretendard Bold", "Pretendard Regular"] if n in names]
    dynamic = sorted([n for n in names if n not in pinned], key=lambda x: x.lower())
    return pinned + dynamic


def find_font_file_by_name(font_name: str | None, is_brand: bool = True):
    font_map = _discover_font_map()
    name = (font_name or '').strip()
    preferred: list[Path | str] = []

    if name:
        # 1) 드롭다운 표시명과 정확히 일치
        if name in font_map:
            preferred.extend(font_map[name])

        # 2) 파일명/줄기명과 정확히 일치 (확장자 포함/미포함 모두 허용)
        lower_name = name.lower()
        exact_candidates = {lower_name}
        if not lower_name.endswith(('.ttf', '.otf', '.ttc')):
            exact_candidates.update({lower_name + '.ttf', lower_name + '.otf', lower_name + '.ttc'})
        for roots in _font_search_roots():
            for pattern in ('*.ttf', '*.otf', '*.ttc'):
                for fp in roots.rglob(pattern):
                    try:
                        stem_lower = fp.stem.lower()
                        file_lower = fp.name.lower()
                        if stem_lower == lower_name or file_lower in exact_candidates:
                            preferred.append(fp)
                    except Exception:
                        continue

        # 3) 유사 이름 매칭
        target = _normalize_font_key(name)
        for display, files in font_map.items():
            disp_norm = _normalize_font_key(display)
            stem_norms = {_normalize_font_key(Path(f).stem) for f in files}
            if target == disp_norm or target in stem_norms or target in disp_norm or disp_norm in target:
                preferred.extend(files)

    fallback_names = ["Pretendard ExtraBold", "Pretendard Bold"] if is_brand else ["Pretendard Bold", "Pretendard Regular"]
    for fb in fallback_names:
        preferred.extend(font_map.get(fb, []))

    seen = set()
    for fp in preferred:
        try:
            p = Path(fp)
            key = str(p).lower()
            if key in seen:
                continue
            seen.add(key)
            if p.exists():
                return p
        except Exception:
            continue
    return None


def find_preferred_font_file(is_brand: bool = True, font_name: str | None = None):
    return find_font_file_by_name(font_name, is_brand=is_brand)

def load_font(size: int, is_brand: bool = True, font_name: str | None = None):
    fp = find_font_file_by_name(font_name, is_brand=is_brand)
    if fp:
        try:
            return ImageFont.truetype(str(fp), size)
        except Exception:
            pass
    return ImageFont.load_default()

def hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b, alpha)

def escape_subtitles_path_for_windows(p: Path) -> str:
    s = str(p).replace("\\", "/")
    s = re.sub(r"^([A-Za-z]):/", r"\1\\:/", s)
    s = s.replace("'", r"\\'")
    return s



def find_video_files(folder: Path):
    exts = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}
    out = []
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            out.append(p)
    return out


def probe_media_duration(path: Path, ffprobe_bin: str) -> float:
    try:
        cmd = [
            ffprobe_bin, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", **get_hidden_startup_kwargs())
        val = (res.stdout or "").strip()
        return float(val) if val else 0.0
    except Exception:
        return 0.0
def probe_audio_duration(audio_path: Path, ffprobe_bin: str = "ffprobe") -> float:
    try:
        cmd = [
            ffprobe_bin, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="ignore", **get_hidden_startup_kwargs())
        return float((p.stdout or "").strip())
    except Exception:
        return 0.0

def format_time(seconds: float) -> str:
    if seconds < 0: return "--:--"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def format_speed(processed_sec: float, elapsed_sec: float) -> str:
    if elapsed_sec <= 0 or processed_sec <= 0: return "--x"
    speed = processed_sec / elapsed_sec
    return f"{speed:.1f}x"

# =============================================================================
# 설정값 검증 시스템
# =============================================================================

def validate_settings(settings: AppSettings) -> List[str]:
    warnings = []
    if settings.video.transition_ratio > 0.8:
        warnings.append("⚠️ 전환비율이 0.8 이상이면 영상이 어지러울 수 있습니다 (권장: 0.3~0.6)")
    elif settings.video.transition_ratio < 0.1:
        warnings.append("⚠️ 전환비율이 너무 낮아 전환 효과가 거의 보이지 않습니다")
    
    if settings.video.zoom_intensity > 0.015:
        warnings.append("⚠️ 줌 강도가 너무 높으면 멀미를 유발할 수 있습니다 (권장: 0.001~0.008)")
    elif settings.video.zoom_intensity < 0.001:
        warnings.append("ℹ️ 줌 효과가 거의 없어 정적인 영상이 됩니다")
    
    if settings.video.base_image_sec < 1.0:
        warnings.append("⚠️ 이미지당 시간이 1초 미만이면 너무 빠릅니다")
    elif settings.video.base_image_sec > 5.0:
        warnings.append("ℹ️ 이미지당 시간이 길어 슬로우한 영상이 됩니다")
    
    if settings.video.enable_zoompam:
        warnings.append("⚠️ [주의] 줌팬 효과는 멀미를 유발할 수 있습니다. 가급적 중앙 줌만 사용하세요.")
        if settings.video.zoompam_intensity > 0.003:
            warnings.append("⚠️ 줌팬 강도가 너무 높습니다. 0.002 이하로 낮추세요.")
    
    if settings.image_watermark.box_enabled and settings.image_watermark.box_alpha < 30:
        warnings.append("ℹ️ 박스 투명도가 너무 낮아 글씨가 잘 안 보일 수 있습니다")
    
    if settings.image_watermark.margin_bottom < 30:
        warnings.append("⚠️ 워터마크가 화면 하단에 너무 붙어 잘릴 수 있습니다")
    
    if settings.subtitle.enabled:
        if settings.subtitle.font_size < 8:
            warnings.append("⚠️ 자막 폰트 크기가 너무 작아 읽기 어렵습니다")
        if settings.subtitle.margin_v < 20:
            warnings.append("⚠️ 자막이 화면 하단에 너무 붙어 있습니다")
    
    return warnings

# =============================================================================
# 반사 배경 생성 + 워터마크 내장 (수정: 하단 그라데이션 박스)
# =============================================================================

@dataclass
class ImageWatermarkSettings(WatermarkSettings):
    """이미지 워터마크 설정"""
    pass


@dataclass
class VideoWatermarkSettings(WatermarkSettings):
    """동영상 워터마크 설정"""
    pass


