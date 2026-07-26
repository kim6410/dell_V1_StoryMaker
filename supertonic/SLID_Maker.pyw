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
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Tuple
from math import ceil

import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageFile, ImageOps
import tkinter.font as tkfont

# VLC 바인딩 (pip install python-vlc 필요)
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    print("⚠️ python-vlc가 설치되지 않았습니다. 영상 프리뷰 기능이 제한됩니다.")
    print("   설치: pip install python-vlc")

# 콘솔 없이 GUI만 실행되도록 설정 (탐색기 더블클릭용)
if sys.platform == "win32":
    import ctypes
    try:
        # 콘솔 숨기기 (Windows)
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass

ImageFile.LOAD_TRUNCATED_IMAGES = True
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

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
    zoom_center_only: bool = True
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
    """워터마크 설정 (그라데이션 박스 포함)"""
    brand_text: str = "오박사 만능인테리어"
    phone_text: str = "010-8284-5584"
    phone_gap_px: int = 0  # 상호-전화번호 간격(px). 0이면 자동
    brand_font_size: int = 46
    phone_font_size: int = 43
    brand_color: str = "#FFD300"
    phone_color: str = "#FFFFFF"
    margin_bottom: int = 80
    x_offset: int = 0
    y_offset: int = 0
    
    # 🔥 배경박스 설정 (하단 그라데이션으로 재활용)
    box_enabled: bool = True  # 그라데이션 사용 여부 (기본 True)
    box_alpha: int = 70  # 최대 투명도 (0-255)
    box_height_multiplier: float = 3.0  # 텍스트 높이 대비 배수
    
    # 기존 박스 설정 (호환성 유지)
    box_pad_x: int = 20
    box_pad_y: int = 24
    
    # 텍스트 스타일
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
    box_mode: int = 0  # 0=없음, 1=약, 2=강
    box_back_colour: str = "&H99000000&"
    primary_colour: str = "&H00FFFFFF&"

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
class AppSettings:
    """전체 애플리케이션 설정"""
    video: VideoSettings = None
    reflection: ReflectionSettings = None
    color_random: ColorRandomSettings = None
    watermark: WatermarkSettings = None
    subtitle: SubtitleSettings = None
    transition: TransitionSettings = None
    encoding: EncodingSettings = None
    
    def __post_init__(self):
        if self.video is None: self.video = VideoSettings()
        if self.reflection is None: self.reflection = ReflectionSettings()
        if self.color_random is None: self.color_random = ColorRandomSettings()
        if self.watermark is None: self.watermark = WatermarkSettings()
        if self.subtitle is None: self.subtitle = SubtitleSettings()
        if self.transition is None: self.transition = TransitionSettings()
        if self.encoding is None: self.encoding = EncodingSettings()
    
    def save_to_file(self, path: Path):
        data = {
            "video": asdict(self.video),
            "reflection": asdict(self.reflection),
            "color_random": asdict(self.color_random),
            "watermark": asdict(self.watermark),
            "subtitle": asdict(self.subtitle),
            "transition": asdict(self.transition),
            "encoding": asdict(self.encoding)
        }
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
        settings.watermark = WatermarkSettings(**data.get('watermark', {}))
        settings.subtitle = SubtitleSettings(**data.get('subtitle', {}))
        settings.transition = TransitionSettings(**data.get('transition', {}))
        settings.encoding = EncodingSettings(**data.get('encoding', {}))
        return settings

# =============================================================================
# 내부 유틸
# =============================================================================

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

def load_font(size: int):
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for fp in candidates:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
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
    
    if settings.watermark.box_enabled and settings.watermark.box_alpha < 30:
        warnings.append("ℹ️ 박스 투명도가 너무 낮아 글씨가 잘 안 보일 수 있습니다")
    
    if settings.watermark.margin_bottom < 30:
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

def build_reflection_canvas(src: Image.Image, settings: AppSettings) -> Image.Image:
    """워터마크 단계에서는 원본 방향/원본 비율/원본 해상도를 유지합니다."""
    src = ImageOps.exif_transpose(src).convert("RGBA")
    fg = src.copy()
    # 아주 약한 보정만 적용
    fg = ImageEnhance.Contrast(fg).enhance(1.01)
    fg = ImageEnhance.Color(fg).enhance(1.01)
    fg = ImageEnhance.Sharpness(fg).enhance(1.01)
    return fg

def draw_watermark(canvas: Image.Image, settings: AppSettings) -> Image.Image:
    """워터마크 그리기 (배경박스를 하단 그라데이션으로 재활용)"""
    wm = settings.watermark

    canvas = canvas.convert("RGBA")
    cw, ch = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    short_side = max(1, min(cw, ch))
    scale = short_side / 1080.0

    brand_font = load_font(max(12, int(wm.brand_font_size * scale)))
    phone_font = load_font(max(12, int(wm.phone_font_size * scale)))

    bb1 = draw.textbbox((0, 0), wm.brand_text, font=brand_font)
    bb2 = draw.textbbox((0, 0), wm.phone_text, font=phone_font)
    bw, bh = bb1[2] - bb1[0], bb1[3] - bb1[1]
    pw, ph = bb2[2] - bb2[0], bb2[3] - bb2[1]

    gap = int(ph * 0.25)
    try:
        if int(getattr(wm, 'phone_gap_px', 0) or 0) > 0:
            gap = max(0, int(wm.phone_gap_px * scale))
    except Exception:
        pass

    tw = max(bw, pw)
    th = bh + gap + ph

    x = (cw - tw) / 2 + int(wm.x_offset * scale)
    y = ch - th - int(wm.margin_bottom * scale) + int(wm.y_offset * scale)

    # 🔥 하단 그라데이션 박스 (배경박스 설정 재활용)
    if wm.box_enabled:
        gradient_height = int(th * wm.box_height_multiplier)  # 텍스트 높이의 배수
        gradient_y = ch - gradient_height - int(wm.margin_bottom * 0.3 * scale) + int(wm.y_offset * scale)
        
        # 부드러운 그라데이션 그리기 (위로 갈수록 투명)
        for i in range(gradient_height):
            # 위로 갈수록 투명도 감소
            alpha = int(wm.box_alpha * (1 - i/gradient_height))
            y_pos = gradient_y + i
            if 0 <= y_pos < ch:
                draw.rectangle(
                    [0, y_pos, cw, y_pos+1],
                    fill=(0, 0, 0, alpha)  # 검정색 그라데이션
                )

    def _text(xy, text, font, fill_hex):
        tx, ty = xy
        fill_rgba = hex_to_rgba(fill_hex)
        stroke_rgba = hex_to_rgba(wm.stroke_color)
        shadow_rgba = hex_to_rgba(wm.shadow_color)

        if wm.shadow_enabled:
            draw.text((tx + int(wm.shadow_offset_x * scale), ty + int(wm.shadow_offset_y * scale)),
                     text, font=font, fill=shadow_rgba)
        if wm.stroke_enabled:
            draw.text((tx, ty), text, font=font, fill=fill_rgba,
                     stroke_width=max(1, int(wm.stroke_width * scale)), stroke_fill=stroke_rgba)
        else:
            draw.text((tx, ty), text, font=font, fill=fill_rgba)

    _text(((cw - bw) / 2 + int(wm.x_offset * scale), y), wm.brand_text, brand_font, wm.brand_color)
    _text(((cw - pw) / 2 + int(wm.x_offset * scale), y + bh + gap), wm.phone_text, phone_font, wm.phone_color)

    return Image.alpha_composite(canvas, overlay)

def preprocess_images(src_folder: Path, settings: AppSettings, qevt: queue.Queue, preview_only: bool = False):
    out_folder = src_folder / "output"
    if not preview_only:
        out_folder.mkdir(exist_ok=True)
    
    imgs = find_images(src_folder)
    if settings.transition.shuffle_images and not preview_only:
        random.shuffle(imgs)
    
    if preview_only:
        if not imgs: return None, None
        try:
            src = ImageOps.exif_transpose(Image.open(imgs[0])).convert("RGB")
            canvas = build_reflection_canvas(src, settings)
            canvas = draw_watermark(canvas, settings)
            return canvas.convert("RGB"), imgs[0].name
        except Exception as e:
            safe_print(f"프리뷰 실패: {e}")
            return None, None
    
    qevt.put(("log", f"[{_ts()}] 원본 이미지 {len(imgs)}장"))
    qevt.put(("log", f"[{_ts()}] ✅ 전처리 이미지 저장 위치: {out_folder}"))
    
    ok, skip = 0, 0
    total = len(imgs)
    start_time = time.time()
    
    for i, p in enumerate(imgs, start=1):
        elapsed = time.time() - start_time
        progress = i / total
        eta = (elapsed / progress) * (1 - progress) if progress > 0 else 0
        speed = format_speed(i, elapsed)
        
        qevt.put(("progress_pre", f"{i}/{total} 처리 중", progress * 100, eta, speed))
        
        new_stem = normalize_output_stem(p.stem)
        out_path = out_folder / f"{new_stem}.jpg"
        
        if out_path.exists() and not settings.encoding.preprocess_overwrite:
            try:
                if out_path.stat().st_mtime >= p.stat().st_mtime:
                    ok += 1
                    continue
            except Exception:
                pass
        
        try:
            src = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            canvas = build_reflection_canvas(src, settings)
            canvas = draw_watermark(canvas, settings)
            canvas.convert("RGB").save(out_path, 
                                      quality=int(settings.encoding.pre_jpg_quality), 
                                      optimize=True)
            ok += 1
        except Exception as e:
            skip += 1
            qevt.put(("log", f"[{_ts()}] ⚠ 전처리 실패(스킵): {p.name} / {e}"))
        finally:
            try:
                src.close()
            except Exception:
                pass
    
    out_imgs = sorted(out_folder.glob("*.jpg"))
    qevt.put(("log", f"[{_ts()}] 전처리 완료: 성공 {ok} / 스킵 {skip} / 결과 {len(out_imgs)}장"))
    return out_folder, out_imgs

# =============================================================================
# SRT 정리 + 스타일
# =============================================================================

def clean_srt(original_srt: Path, out_srt: Path) -> Path:
    raw = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            raw = original_srt.read_text(encoding=enc, errors="ignore")
            break
        except Exception:
            continue
    if raw is None:
        raw = original_srt.read_text(errors="ignore")
    
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw).strip() + "\n"
    
    blocks = re.split(r"\n\s*\n", raw.strip())
    fixed_blocks = []
    for block in blocks:
        lines2 = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if len(lines2) <= 2:
            fixed_blocks.append("\n".join(lines2))
            continue
        head = lines2[:2]
        body = " ".join(lines2[2:])
        body = re.sub(r"\s+", " ", body).strip()
        fixed_blocks.append("\n".join(head + ([body] if body else [])))
    raw = "\n\n".join(fixed_blocks).strip() + "\n"

    out_srt.write_text(raw, encoding="utf-8")
    return out_srt

def build_ass_force_style(settings: SubtitleSettings) -> str:
    if settings.box_mode == 0:
        border_style = 1
        back = "&H00000000&"
        outline = settings.outline
        shadow = settings.shadow
    else:
        border_style = 3
        back = settings.box_back_colour
        outline = max(2, int(settings.outline))
        shadow = max(1, int(settings.shadow))
    
    style = (
        f"FontName={settings.font_name},"
        f"FontSize={int(settings.font_size)},"
        f"Bold={1 if settings.bold else 0},"
        f"PrimaryColour={settings.primary_colour},"
        f"Outline={int(outline)},"
        f"Shadow={int(shadow)},"
        f"MarginV={int(settings.margin_v)},MarginL=20,MarginR=20,"
        f"BorderStyle={int(border_style)},"
        f"BackColour={back}"
    )
    return style

# =============================================================================
# FFmpeg filter script
# =============================================================================

def clamp(v, a, b):
    return max(a, min(b, v))

def pick_transition_name(settings: TransitionSettings) -> str:
    if settings.style == "fade_only":
        return "fade"
    return random.choice(settings.transitions_natural)

def build_cycle_shuffled_images(pre_imgs: list[Path], repeat_count: int, settings: TransitionSettings) -> list[Path]:
    if repeat_count <= 1:
        return pre_imgs
    
    expanded = []
    for cycle in range(repeat_count):
        if cycle == 0:
            if settings.shuffle_images:
                cycle_imgs = random.sample(pre_imgs, len(pre_imgs))
            else:
                cycle_imgs = pre_imgs
        else:
            if settings.cycle_shuffle:
                cycle_imgs = random.sample(pre_imgs, len(pre_imgs))
            elif settings.reverse_cycle:
                cycle_imgs = list(reversed(pre_imgs))
            else:
                cycle_imgs = pre_imgs
        expanded.extend(cycle_imgs)
    
    return expanded

def build_filter_script_xfade(pre_imgs: list[Path], seg: float, fade: float, 
                              srt_path: Path | None, settings: AppSettings) -> tuple[str, str]:
    """이미지 비율별 4단계 전략으로 최종 1080x1920 프레임 생성 후 xfade 적용"""
    lines = []
    vw, vh = int(settings.video.width), int(settings.video.height)

    for i, img_path in enumerate(pre_imgs):
        eq = ""
        if settings.color_random.enabled:
            sat = random.uniform(settings.color_random.sat_min, settings.color_random.sat_max)
            con = random.uniform(settings.color_random.contrast_min, settings.color_random.contrast_max)
            bri = random.uniform(settings.color_random.bright_min, settings.color_random.bright_max)
            eq = f"eq=saturation={sat:.3f}:contrast={con:.3f}:brightness={(bri-1.0):.4f},"

        try:
            with Image.open(img_path) as im:
                im = ImageOps.exif_transpose(im)
                iw0, ih0 = im.size
        except Exception:
            iw0, ih0 = vw, vh

        ratio = (iw0 / ih0) if ih0 else 1.0
        bg_color = getattr(settings.video, "background_fallback_color", "black") or "black"

        d = max(int(seg * settings.video.fps), 2)
        d1 = d - 1
        cap = float(getattr(settings.video, "zoom_cap", 1.005) or 1.005)
        cap = max(1.0, min(cap, 1.20))
        delta = cap - 1.0
        direction = getattr(settings.video, "zoom_direction", "random") or "random"
        if direction == "random":
            direction = random.choice(["in", "out"])
        if direction == "in":
            z_expr = f"1+({delta:.6f})*on/{d1}"
        elif direction == "out":
            z_expr = f"{cap:.6f}-({delta:.6f})*on/{d1}"
        elif direction == "inout":
            half = d1 / 2.0
            z_expr = (
                f"if(lte(on,{half:.3f}),"
                f"1+({delta:.6f})*on/{half:.3f},"
                f"{cap:.6f}-({delta:.6f})*(on-{half:.3f})/{half:.3f})"
            )
        elif direction == "outin":
            half = d1 / 2.0
            z_expr = (
                f"if(lte(on,{half:.3f}),"
                f"{cap:.6f}-({delta:.6f})*on/{half:.3f},"
                f"1+({delta:.6f})*(on-{half:.3f})/{half:.3f})"
            )
        else:
            z_expr = f"1+({delta:.6f})*on/{d1}"

        # 입력 1장 -> 배경/전경 분리용 split
        lines.append(f"[{i}:v]split=2[base{i}][fgsrc{i}];")

        if ratio >= 1.9:
            # 극단적 가로: 높이를 맞춘 뒤 중앙 크롭
            lines.append(
                f"[base{i}]scale=-2:{vh},crop={vw}:{vh},boxblur=20:1,setsar=1[bg{i}];"
            )
            lines.append(
                f"[fgsrc{i}]scale=-2:{vh},crop={vw}:{vh},setsar=1[fg{i}];"
            )
        elif ratio >= 1.15:
            # 일반 가로: 릴스 풀화면 우선, 전경도 9:16으로 꽉 채운 뒤 중앙 크롭
            lines.append(
                f"[base{i}]scale={vw}:{vh}:force_original_aspect_ratio=increase,crop={vw}:{vh},"
                f"boxblur=26:2,eq=brightness=-0.08:saturation=0.95,setsar=1[bg{i}];"
            )
            lines.append(
                f"[fgsrc{i}]scale={vw}:{vh}:force_original_aspect_ratio=increase,"
                f"crop={vw}:{vh},setsar=1[fg{i}];"
            )
        elif ratio >= 0.85:
            # 정사각형/근접: 가운데 작아 보이지 않도록 전경도 풀블리드 처리
            lines.append(
                f"[base{i}]scale={vw}:{vh}:force_original_aspect_ratio=increase,crop={vw}:{vh},"
                f"boxblur=22:2,eq=brightness=-0.10:saturation=0.94,setsar=1[bg{i}];"
            )
            lines.append(
                f"[fgsrc{i}]scale={vw}:{vh}:force_original_aspect_ratio=increase,"
                f"crop={vw}:{vh},setsar=1[fg{i}];"
            )
        else:
            # 세로 이미지: 기존처럼 작게 두지 않고 9:16 화면을 끝까지 채움
            lines.append(
                f"[base{i}]scale={vw}:{vh}:force_original_aspect_ratio=increase,crop={vw}:{vh},"
                f"boxblur=18:2,eq=brightness=-0.12:saturation=0.93,setsar=1[bg{i}];"
            )
            lines.append(
                f"[fgsrc{i}]scale={vw}:{vh}:force_original_aspect_ratio=increase,"
                f"crop={vw}:{vh},setsar=1[fg{i}];"
            )

        lines.append(
            f"[bg{i}]drawbox=x=0:y=0:w={vw}:h={vh}:color={bg_color}@0.18:t=fill[bgbox{i}];"
        )
        lines.append(
            f"[bgbox{i}][fg{i}]overlay=(W-w)/2:(H-h)/2:format=auto,format=rgba[comp{i}];"
        )

        if settings.video.zoom_center_only or settings.video.enable_zoompam:
            if settings.video.enable_zoompam:
                pan_x = random.uniform(-0.004, 0.004)
                pan_y = random.uniform(-0.004, 0.004)
                x_expr = f"trunc((iw/2-(iw/zoom/2)+{pan_x:.5f}*on)/2)*2"
                y_expr = f"trunc((ih/2-(ih/zoom/2)+{pan_y:.5f}*on)/2)*2"
            else:
                x_expr = "trunc((iw/2-(iw/zoom/2))/2)*2"
                y_expr = "trunc((ih/2-(ih/zoom/2))/2)*2"

            chain = (
                f"[comp{i}]"
                f"{eq}"
                f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={d}:s={vw}x{vh}:fps={settings.video.fps},"
                f"setsar=1,setdar={vw}/{vh},format=yuv420p,trim=duration={seg:.3f},setpts=PTS-STARTPTS[v{i}];"
            )
        else:
            if direction == "out":
                zoom = (
                    f"scale=iw*({cap:.6f}-({delta:.6f})*t/{seg:.6f}):ih*({cap:.6f}-({delta:.6f})*t/{seg:.6f}):eval=frame,"
                )
            elif direction in ("inout", "outin"):
                half_t = seg / 2.0
                if direction == "inout":
                    zoom = (
                        f"scale=iw*(if(lte(t,{half_t:.6f}),1+({delta:.6f})*t/{half_t:.6f},{cap:.6f}-({delta:.6f})*(t-{half_t:.6f})/{half_t:.6f})):"
                        f"ih*(if(lte(t,{half_t:.6f}),1+({delta:.6f})*t/{half_t:.6f},{cap:.6f}-({delta:.6f})*(t-{half_t:.6f})/{half_t:.6f})):eval=frame,"
                    )
                else:
                    zoom = (
                        f"scale=iw*(if(lte(t,{half_t:.6f}),{cap:.6f}-({delta:.6f})*t/{half_t:.6f},1+({delta:.6f})*(t-{half_t:.6f})/{half_t:.6f})):"
                        f"ih*(if(lte(t,{half_t:.6f}),{cap:.6f}-({delta:.6f})*t/{half_t:.6f},1+({delta:.6f})*(t-{half_t:.6f})/{half_t:.6f})):eval=frame,"
                    )
            else:
                zoom = (
                    f"scale=iw*(1+({delta:.6f})*t/{seg:.6f}):ih*(1+({delta:.6f})*t/{seg:.6f}):eval=frame,"
                )

            chain = (
                f"[comp{i}]"
                f"{eq}"
                f"{zoom}"
                f"crop={vw}:{vh}:(iw-{vw})/2:(ih-{vh})/2,setsar=1,setdar={vw}/{vh},format=yuv420p,"
                f"fps={settings.video.fps},trim=duration={seg:.3f},setpts=PTS-STARTPTS[v{i}];"
            )
        lines.append(chain)

    if len(pre_imgs) == 1:
        cur = "[v0]"
    else:
        offset_step = (seg - fade)
        offset = offset_step
        tname = pick_transition_name(settings.transition)
        lines.append(f"[v0][v1]xfade=transition={tname}:duration={fade:.3f}:offset={offset:.3f}[x1];")
        cur = "[x1]"
        for k in range(2, len(pre_imgs)):
            offset = offset_step * k
            tname = pick_transition_name(settings.transition)
            lines.append(f"{cur}[v{k}]xfade=transition={tname}:duration={fade:.3f}:offset={offset:.3f}[x{k}];")
            cur = f"[x{k}]"

    if srt_path and settings.subtitle.enabled:
        srt_esc = escape_subtitles_path_for_windows(srt_path)
        style = build_ass_force_style(settings.subtitle).replace("'", r"\'")
        lines.append(f"{cur}subtitles='{srt_esc}':charenc=UTF-8:force_style='{style}'[vout];")
    else:
        lines.append(f"{cur}copy[vout];")

    return "\n".join(lines), "[vout]"

# =============================================================================
# FFmpeg 실행
# =============================================================================

def run_ffmpeg_with_progress(cmd: list[str], qevt: queue.Queue, stage: str, 
                            total_duration: float, no_progress_kill_sec: int) -> tuple[int, str]:
    cmd2 = cmd[:]
    cmd2.insert(1, "-loglevel"); cmd2.insert(2, "warning")
    cmd2.insert(1, "-progress"); cmd2.insert(2, "pipe:1")
    cmd2.insert(3, "-nostats")
    
    p = subprocess.Popen(
        cmd2,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,
        universal_newlines=True,
        **get_hidden_startup_kwargs()
    )
    
    last_sig = time.time()
    start_time = time.time()
    tail = []
    
    def tail_add(s: str):
        tail.append(s)
        if len(tail) > 260:
            del tail[:60]
    
    try:
        for line in p.stdout:
            line = (line or "").strip()
            if not line:
                continue
            tail_add(line)
            
            if line.startswith("out_time_ms="):
                try:
                    out_ms = int(line.split("=", 1)[1])
                    out_sec = out_ms / 1_000_000
                    last_sig = time.time()
                    
                    progress = (out_sec / total_duration) * 100 if total_duration > 0 else 0
                    progress = min(100, max(0, progress))
                    
                    elapsed = time.time() - start_time
                    if out_sec > 0:
                        eta = (elapsed / out_sec) * (total_duration - out_sec)
                    else:
                        eta = 0
                    
                    speed = format_speed(out_sec, elapsed)
                    
                    qevt.put(("progress_enc", f"인코딩 중... {out_sec:.1f}/{total_duration:.1f}초", 
                             progress, eta, speed))
                    
                except Exception:
                    pass
            
            if time.time() - last_sig > no_progress_kill_sec:
                tail_add(f"[KILL] no progress > {no_progress_kill_sec}s")
                try:
                    p.kill()
                except Exception:
                    pass
                break
        
        rc = p.wait()
        return rc, "\n".join(tail[-200:])
    finally:
        try:
            if p.stdout:
                p.stdout.close()
        except Exception:
            pass

# =============================================================================
# 메인 빌드
# =============================================================================

@dataclass
class BuildReport:
    output_mp4: Path
    version_label: str
    encoder_used: str
    video_quality: str
    audio_bitrate: str
    preprocess_folder: Path
    output_folder: Path
    temp_folder: Path
    audio_len: float
    video_len: float
    seg: float
    fade: float
    elapsed: float
    img_count: int
    repeat_count: int
    file_size_mb: float
    audio_used: str

def get_random_audio_from_folder(folder: Path) -> Optional[Path]:
    if not folder or not folder.exists(): return None
    audio_files = find_audio_files(folder)
    if not audio_files: return None
    return random.choice(audio_files)

def build_video_onepass(pre_imgs: list[Path], audio_path: Path, srt_path: Path | None, 
                       base_dir: Path, settings: AppSettings, qevt: queue.Queue) -> list[BuildReport]:
    if not pre_imgs:
        raise RuntimeError("전처리 이미지가 없습니다.")
    
    output_folder = base_dir / "OUTPUT"
    temp_folder = output_folder / "temp"
    output_folder.mkdir(exist_ok=True)
    temp_folder.mkdir(exist_ok=True)
    
    # 오디오 랜덤 선택
    audio_used = str(audio_path)
    if settings.encoding.audio_random_enabled and settings.encoding.audio_folder:
        audio_folder = Path(settings.encoding.audio_folder)
        random_audio = get_random_audio_from_folder(audio_folder)
        if random_audio:
            audio_path = random_audio
            audio_used = str(random_audio)
            qevt.put(("log", f"[{_ts()}] 🎵 랜덤 선택된 오디오: {random_audio.name}"))
    
    audio_len = probe_audio_duration(audio_path, settings.encoding.ffprobe_bin)
    if audio_len <= 0:
        audio_len = 0.0
        qevt.put(("log", f"[{_ts()}] ⚠ 오디오 길이 측정 실패, 타임라인 기반으로 처리합니다."))
    
    seg = float(settings.video.base_image_sec)
    fade = clamp(seg * float(settings.video.transition_ratio), 
                settings.video.transition_min_sec, 
                settings.video.transition_max_sec)
    fade = min(fade, seg * 0.85)
    
    original_img_count = len(pre_imgs)
    base_video_len = max(0.0, (original_img_count * seg) - (max(0, original_img_count-1) * fade))
    
    # 🔥 중요: 이미지 반복 계산 로직 강화
    repeat_count = 1
    if audio_len > 0 and base_video_len < audio_len:
        repeat_count = ceil(audio_len / base_video_len)
        pre_imgs = build_cycle_shuffled_images(pre_imgs, repeat_count, settings.transition)
        
        qevt.put(("log", f"[{_ts()}] 🔄 이미지 반복 상세:"))
        qevt.put(("log", f"  - 원본 이미지: {original_img_count}장"))
        qevt.put(("log", f"  - 반복 횟수: {repeat_count}회"))
        qevt.put(("log", f"  - 총 이미지: {len(pre_imgs)}장"))
        calc_len = max(0.0, (len(pre_imgs) * seg) - (max(0, len(pre_imgs)-1) * fade))
        qevt.put(("log", f"  - 계산된 영상 길이: {calc_len:.2f}초"))
        qevt.put(("log", f"  - 오디오 길이: {audio_len:.2f}초"))
        
        if settings.transition.cycle_shuffle:
            qevt.put(("log", f"[{_ts()}] 🔀 회전마다 이미지 순서 랜덤 셔플 적용"))
    
    final_video_len = max(0.0, (len(pre_imgs) * seg) - (max(0, len(pre_imgs)-1) * fade))
    
    # 🔥 추가 안전장치: 영상 길이가 오디오보다 짧으면 추가 반복
    if audio_len > 0 and final_video_len < audio_len - 0.5:  # 0.5초 오차 허용
        qevt.put(("log", f"[{_ts()}] ⚠️ 경고: 영상 길이({final_video_len:.2f}초)가 오디오({audio_len:.2f}초)보다 짧습니다!"))
        
        # 원본 이미지 기준으로 추가 반복 횟수 계산
        needed_extra = ceil((audio_len - final_video_len) / (original_img_count * seg))
        extra_repeat = needed_extra + 1  # 여유 있게 +1
        
        qevt.put(("log", f"[{_ts()}] 🔄 추가 반복 {extra_repeat}회 적용"))
        
        # 새 이미지 리스트 생성 (원본 이미지로 다시 반복)
        fresh_imgs = find_images(base_dir / "output")  # output 폴더에서 다시 로드
        if fresh_imgs:
            pre_imgs = build_cycle_shuffled_images(fresh_imgs, repeat_count + extra_repeat, settings.transition)
        else:
            # 실패하면 원본 리스트 확장
            extra_cycle = []
            for _ in range(extra_repeat):
                if settings.cycle_shuffle:
                    extra_cycle.extend(random.sample(pre_imgs[:original_img_count], original_img_count))
                else:
                    extra_cycle.extend(pre_imgs[:original_img_count])
            pre_imgs.extend(extra_cycle)
        
        final_video_len = max(0.0, (len(pre_imgs) * seg) - (max(0, len(pre_imgs)-1) * fade))
        repeat_count += extra_repeat
        qevt.put(("log", f"[{_ts()}]   - 수정 후 영상 길이: {final_video_len:.2f}초 (이미지 {len(pre_imgs)}장)"))
    
    qevt.put(("log", f"[{_ts()}] MP3 길이: {audio_len:.2f}초"))
    qevt.put(("log", f"[{_ts()}] 최종 영상 길이: {final_video_len:.2f}초 (이미지 {len(pre_imgs)}장)"))

    # 🔥 최종 안전장치: xfade 겹침까지 반영했는데도 오디오보다 짧으면 마지막 프레임을 붙여 길이를 맞춥니다.
    if audio_len > 0:
        # 실제 길이(겹침 반영)
        eff_len = max(0.0, (len(pre_imgs) * seg) - (max(0, len(pre_imgs)-1) * fade))
        while eff_len < audio_len + 0.20 and len(pre_imgs) > 0:
            pre_imgs.append(pre_imgs[-1])  # 마지막 이미지 1장 추가
            eff_len = max(0.0, (len(pre_imgs) * seg) - (max(0, len(pre_imgs)-1) * fade))
        final_video_len = eff_len
        qevt.put(("log", f"[{_ts()}] ⏱️ (겹침 반영) 최종 길이 보정: {final_video_len:.2f}초 / 오디오: {audio_len:.2f}초 (이미지 {len(pre_imgs)}장)"))

    qevt.put(("log", f"[{_ts()}] 이미지당 표시: {seg:.2f}초"))
    qevt.put(("log", f"[{_ts()}] 전환시간: {fade:.2f}초 (비율 {settings.video.transition_ratio:.2f})"))
    
    if settings.video.zoom_center_only:
        qevt.put(("log", f"[{_ts()}] 🎯 느린 중앙 줌 적용 (강도: {settings.video.zoom_intensity})"))
    elif settings.video.enable_zoompam:
        qevt.put(("log", f"[{_ts()}] ⚠️ 미세 줌팬 효과 적용 (강도: {settings.video.zoompam_intensity})"))
    
    if srt_path and settings.subtitle.enabled:
        clean_path = temp_folder / (srt_path.stem + "__clean.srt")
        try:
            srt_path = clean_srt(srt_path, clean_path)
            qevt.put(("log", f"[{_ts()}] ✅ SRT 정리 완료: {clean_path.name}"))
        except Exception as e:
            qevt.put(("log", f"[{_ts()}] ⚠ SRT 정리 실패(원본 사용): {e}"))
    
    # ✅ 필터 스크립트는 출력 버전(SNS/HQ)별로 해상도/옵션이 다를 수 있어, 아래 인코딩 루프에서 버전별로 생성합니다.
    
    # MP4 파일명 = 이미지 폴더명
    folder_name = base_dir.name
    safe_name = re.sub(r'[\\/*?:"<>|]', "_", folder_name)
    timestamp = time.strftime('%Y%m%d_%H%M%S')

    # =============================================================================
    # ✅ 2버전 동시 생성 (SNS/HQ) - 체크박스 기반
    # =============================================================================
    versions = []
    enc = settings.encoding

    if enc.out_sns_enabled:
        versions.append({
            "label": "SNS",
            "nvenc_cq": int(enc.sns_nvenc_cq),
            "x264_crf": int(enc.sns_x264_crf),
            "audio_bitrate": str(enc.sns_audio_bitrate),
            "x264_preset": str(enc.sns_x264_preset),
            "nvenc_preset": str(enc.sns_nvenc_preset),
        })

    if enc.out_hq_enabled:
        versions.append({
            "label": "HQ",
            "nvenc_cq": int(enc.hq_nvenc_cq),
            "x264_crf": int(enc.hq_x264_crf),
            "audio_bitrate": str(enc.hq_audio_bitrate),
            "x264_preset": str(enc.hq_x264_preset),
            "nvenc_preset": str(enc.hq_nvenc_preset),
        })

    # 혹시 둘 다 꺼져 있으면, 안전하게 SNS만 생성
    if not versions:
        versions.append({
            "label": "SNS",
            "nvenc_cq": int(enc.sns_nvenc_cq),
            "x264_crf": int(enc.sns_x264_crf),
            "audio_bitrate": str(enc.sns_audio_bitrate),
            "x264_preset": str(enc.sns_x264_preset),
            "nvenc_preset": str(enc.sns_nvenc_preset),
        })

    def make_cmd(settings_local: AppSettings, script_path_local: Path, vout_label_local: str, encoder: str, out_mp4: Path, cfg: dict) -> list[str]:
        cmd = [settings_local.encoding.ffmpeg_bin, "-hide_banner", "-y"]

        # 🔥 모든 이미지를 입력으로 추가 (순서 보장)
        for i, img in enumerate(pre_imgs):
            cmd += ["-loop", "1", "-t", f"{seg:.3f}", "-i", str(img)]
            if i < 3:  # 처음 3개만 로그 표시 (너무 많으면 로그가 길어짐)
                qevt.put(("log", f"[{_ts()}] 📸 이미지 입력 {i+1}: {img.name}"))

        if len(pre_imgs) > 3:
            qevt.put(("log", f"[{_ts()}] ... 외 {len(pre_imgs)-3}개 이미지"))

        cmd += ["-i", str(audio_path)]

        cmd += ["-filter_complex_script", str(script_path_local)]
        cmd += ["-map", vout_label_local, "-map", f"{len(pre_imgs)}:a"]
        cmd += ["-r", str(settings_local.video.fps)]
        cmd += ["-fps_mode", "cfr"]
        cmd += ["-shortest"]  # 🔥 오디오 길이에 맞춰 영상 자르기

        if encoder == "h264_nvenc":
            cmd += [
                "-c:v", "h264_nvenc",
                "-preset", str(cfg.get("nvenc_preset", settings_local.encoding.nvenc_preset)),
                "-pix_fmt", "yuv420p",
                "-cq", str(int(cfg.get("nvenc_cq", 28))),
            ]
        else:
            cmd += [
                "-c:v", "libx264",
                "-preset", str(cfg.get("x264_preset", settings_local.encoding.x264_preset)),
                "-crf", str(int(cfg.get("x264_crf", settings_local.encoding.x264_crf_optimized))),
                "-pix_fmt", "yuv420p",
            ]

        cmd += ["-c:a", settings_local.encoding.audio_codec, "-b:a", str(cfg.get("audio_bitrate", settings_local.encoding.audio_bitrate))]

        # 오디오 길이만큼만 인코딩
        if audio_len > 0:
            cmd += ["-t", f"{audio_len:.3f}", str(out_mp4)]
        else:
            cmd += [str(out_mp4)]

        return cmd

    reports: list[BuildReport] = []

    # =============================================================================
    # 인코딩 실행 (SNS/HQ 순차 생성)
    # =============================================================================
    for cfg in versions:
        vlabel = str(cfg["label"])
        out_mp4 = output_folder / f"{safe_name}_{vlabel}_{timestamp}.mp4"

        # ✅ 버전별 설정 복제(SNS는 720 자동 / HQ는 1080 유지)
        import copy as _copy
        settings_local = _copy.deepcopy(settings)
        if vlabel.upper() == "SNS" and settings.encoding.sns_scale_down:
            settings_local.video.width = int(settings.encoding.sns_width)
            settings_local.video.height = int(settings.encoding.sns_height)

        # ✅ 버전별 filter_complex 생성
        script_text, vout_label = build_filter_script_xfade(pre_imgs, seg, fade, srt_path, settings_local)
        script_path = temp_folder / f"filter_complex_{vlabel}.txt"
        script_path.write_text(script_text, encoding="utf-8")
        qevt.put(("log", f"[{_ts()}] 📁 출력({vlabel}): {out_mp4.name}"))

        qevt.put(("progress_enc", f"인코딩 준비 중... ({vlabel})", 0, audio_len, "0x"))

        tail = ""
        ok = False
        for enc_label, enc_name in (("NVENC", settings.encoding.enc_primary), ("x264", settings.encoding.enc_fallback)):
            qevt.put(("log", f"[{_ts()}] 실행: {enc_label} / {vlabel} (품질: NVENC cq {cfg.get('nvenc_cq')} | x264 crf {cfg.get('x264_crf')} / 오디오 {cfg.get('audio_bitrate')})"))
            rc, tail = run_ffmpeg_with_progress(
                make_cmd(settings_local, script_path, vout_label, enc_name, out_mp4, cfg),
                qevt,
                f"최종 생성({vlabel})",
                audio_len,
                settings.encoding.no_progress_kill_sec
            )
            if rc == 0:
                file_size_mb = out_mp4.stat().st_size / (1024 * 1024) if out_mp4.exists() else 0.0
                qevt.put(("log", f"[{_ts()}] ✅ 완료({vlabel}) / 파일 크기: {file_size_mb:.2f} MB"))
                qevt.put(("progress_enc", f"인코딩 완료 ({vlabel})", 100, 0, "0x"))

                reports.append(BuildReport(
                    output_mp4=out_mp4,
                    version_label=vlabel,
                    encoder_used=enc_label,
                    video_quality=f"NVENC cq {cfg.get('nvenc_cq')} / x264 crf {cfg.get('x264_crf')}",
                    audio_bitrate=str(cfg.get("audio_bitrate")),
                    preprocess_folder=base_dir / "output",
                    output_folder=output_folder,
                    temp_folder=temp_folder,
                    audio_len=audio_len,
                    video_len=final_video_len,
                    seg=seg,
                    fade=fade,
                    elapsed=0.0,
                    img_count=original_img_count,
                    repeat_count=repeat_count,
                    file_size_mb=file_size_mb,
                    audio_used=audio_used
                ))
                ok = True
                break
            else:
                qevt.put(("log", f"[{_ts()}] ⚠ 실패: {enc_label} / {vlabel} (rc={rc})"))

        if not ok:
            raise RuntimeError(f"최종 영상 생성 실패 ({vlabel})\n\n--- tail ---\n{tail}")

    return reports

# =============================================================================
# 🎬 영상 프리뷰 플레이어 클래스 (자동 경로 탐색 + 자동 재생)
# =============================================================================

class VideoPreviewPlayer(tk.Frame):
    """VLC 기반 영상 프리뷰 플레이어 (자동 경로 탐색)"""
    
    def __init__(self, parent, on_folder_open_callback=None, auto_play=False):
        super().__init__(parent, bg="#1a1e2a", relief="flat", bd=1)
        self.parent = parent
        self.on_folder_open = on_folder_open_callback
        self.auto_play = auto_play
        
        # VLC 경로 자동 탐색
        self.vlc_path = self.find_vlc()
        
        # VLC 경로를 PATH에 추가
        if self.vlc_path and os.path.exists(self.vlc_path):
            os.environ['PATH'] = self.vlc_path + ';' + os.environ.get('PATH', '')
            print(f"✅ VLC 경로 추가됨: {self.vlc_path}")
        
        # VLC 인스턴스 생성
        self.vlc_available = VLC_AVAILABLE
        self.instance = None
        self.player = None
        
        if self.vlc_available:
            self.init_vlc()
        
        # 현재 재생 중인 파일
        self.current_video = None
        self.is_playing = False
        self.video_files = []  # 사용 가능한 비디오 파일 목록
        self.seek_pressed = False
        
        # UI 생성
        self.create_widgets()
        
        # 타이머 설정 (재생 상태 업데이트)
        if self.vlc_available:
            self.update_timer()
    
    def find_vlc(self):
        """VLC 설치 경로 찾기"""
        candidates = [
            "/usr/bin",
            "/usr/lib/x86_64-linux-gnu",
            "/usr/lib",
        ]
        
        for path in candidates:
            dll_path = os.path.join(path, "libvlc.dll")
            if os.path.exists(dll_path):
                print(f"✅ VLC 발견: {path}")
                return path
        return None
    
    def init_vlc(self):
        """VLC 초기화"""
        try:
            if self.vlc_path:
                dll_path = os.path.join(self.vlc_path, "libvlc.dll")
                if os.path.exists(dll_path):
                    import ctypes
                    ctypes.CDLL(dll_path)
                    print(f"✅ libvlc.dll 로드 성공")
            
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            self.vlc_available = True
            print("✅ VLC 인스턴스 생성 성공!")
        except Exception as e:
            self.vlc_available = False
            print(f"⚠️ VLC 초기화 실패: {e}")
    
    def create_widgets(self):
        # 상단: 파일 선택 프레임
        top_frame = tk.Frame(self, bg="#1a1e2a")
        top_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        tk.Label(top_frame, text="🎬 출력 영상:", fg="#c7d0db", bg="#1a1e2a", 
                font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=(0, 10))
        
        self.video_combo = ttk.Combobox(top_frame, values=[], width=40)
        self.video_combo.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.video_combo.bind('<<ComboboxSelected>>', self.on_video_selected)
        
        # 폴더 열기 버튼
        if self.on_folder_open:
            folder_btn = tk.Button(top_frame, text="📂 출력 폴더 열기", 
                                 command=self.on_folder_open,
                                 bg="#4a5568", fg="white", relief="flat",
                                 font=("Malgun Gothic", 9))
            folder_btn.pack(side="right")
        
        # 프리뷰 캔버스 (영상 표시)
        self.video_canvas = tk.Canvas(self, bg="#121622", width=480, height=854, 
                                     highlightthickness=0)  # 9:16 비율
        self.video_canvas.pack(pady=10, padx=10)
        
        # VLC 비디오 출력을 캔버스에 연결 (사용 가능한 경우)
        if self.vlc_available and self.player:
            try:
                self.player.set_xwindow(self.video_canvas.winfo_id())
            except:
                pass
        
        # VLC 미사용 시 안내 메시지
        if not self.vlc_available:
            self.video_canvas.create_text(240, 427, 
                                         text="⚠️ VLC 플레이어가 필요합니다\n\n설치: python-vlc 패키지 설치 후\nVLC 미디어 플레이어 설치",
                                         fill="#9aa4b2", font=("Malgun Gothic", 12), width=400, justify="center")
        
        # 컨트롤 프레임
        control_frame = tk.Frame(self, bg="#1a1e2a")
        control_frame.pack(fill="x", padx=10, pady=5)
        
        # 재생 컨트롤 버튼들
        btn_frame = tk.Frame(control_frame, bg="#1a1e2a")
        btn_frame.pack(side="left")
        
        self.play_btn = tk.Button(btn_frame, text="▶", command=self.toggle_play,
                                  bg="#2d6cdf", fg="white", relief="flat",
                                  font=("Malgun Gothic", 10, "bold"), width=3)
        self.play_btn.pack(side="left", padx=2)
        
        self.stop_btn = tk.Button(btn_frame, text="■", command=self.stop,
                                  bg="#4a5568", fg="white", relief="flat",
                                  font=("Malgun Gothic", 10, "bold"), width=3)
        self.stop_btn.pack(side="left", padx=2)
        
        # 시간 표시
        time_frame = tk.Frame(control_frame, bg="#1a1e2a")
        time_frame.pack(side="left", padx=10)
        
        self.time_label = tk.Label(time_frame, text="00:00 / 00:00", 
                                   fg="#c7d0db", bg="#1a1e2a",
                                   font=("Malgun Gothic", 9))
        self.time_label.pack(side="left")
        
        # 볼륨 컨트롤
        volume_frame = tk.Frame(control_frame, bg="#1a1e2a")
        volume_frame.pack(side="right")
        
        tk.Label(volume_frame, text="🔊", fg="#c7d0db", bg="#1a1e2a",
                font=("Malgun Gothic", 10)).pack(side="left", padx=(0, 5))
        
        self.volume_var = tk.IntVar(value=50)
        self.volume_scale = ttk.Scale(volume_frame, from_=0, to=100, 
                                       variable=self.volume_var, orient="horizontal",
                                       length=80, command=self.on_volume_change)
        self.volume_scale.pack(side="left")
        
        # 재생 진행바
        seek_frame = tk.Frame(self, bg="#1a1e2a")
        seek_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.seek_var = tk.DoubleVar(value=0)
        self.seek_scale = ttk.Scale(seek_frame, from_=0, to=1000, 
                                     variable=self.seek_var, orient="horizontal",
                                     command=self.on_seek)
        self.seek_scale.pack(fill="x")
        
        # 마우스 이벤트 바인딩
        self.seek_scale.bind("<ButtonPress-1>", self.on_seek_press)
        self.seek_scale.bind("<ButtonRelease-1>", self.on_seek_release)
    
    def update_video_list(self, folder_path=None, auto_play=False):
        """출력 폴더에서 비디오 파일 목록 업데이트"""
        if folder_path and Path(folder_path).exists():
            # MP4 파일 찾기
            mp4_files = list(Path(folder_path).glob("*.mp4"))
            self.video_files = sorted(mp4_files, key=lambda p: p.stat().st_mtime, reverse=True)
            
            # 콤보박스 업데이트
            names = [f.name for f in self.video_files]
            self.video_combo['values'] = names
            
            if names:
                self.video_combo.set(names[0])
                self.load_video(self.video_files[0])
                
                # 자동 재생
                if auto_play and self.vlc_available:
                    self.after(500, self.auto_play_video)  # 0.5초 후 재생
    
    def auto_play_video(self):
        """자동 재생"""
        if self.current_video and self.vlc_available:
            self.player.play()
            self.play_btn.config(text="⏸")
            self.is_playing = True
    
    def load_video(self, video_path):
        """비디오 로드"""
        if not video_path or not video_path.exists() or not self.vlc_available:
            return
        
        self.current_video = video_path
        media = self.instance.media_new(str(video_path))
        self.player.set_media(media)
        total = self.player.get_length()
        self.time_label.config(text=f"00:00 / {self.format_time(total)}")
    
    def on_video_selected(self, event=None):
        """콤보박스에서 비디오 선택 시"""
        selection = self.video_combo.get()
        for video in self.video_files:
            if video.name == selection:
                self.load_video(video)
                break
    
    def toggle_play(self):
        """재생/일시정지 토글"""
        if not self.current_video or not self.vlc_available:
            return
        
        if self.player.is_playing():
            self.player.pause()
            self.play_btn.config(text="▶")
            self.is_playing = False
        else:
            self.player.play()
            self.play_btn.config(text="⏸")
            self.is_playing = True
    
    def stop(self):
        """정지"""
        if not self.vlc_available:
            return
        self.player.stop()
        self.play_btn.config(text="▶")
        self.is_playing = False
        total = self.player.get_length()
        self.time_label.config(text=f"00:00 / {self.format_time(total)}")
        self.seek_var.set(0)
    
    def on_volume_change(self, value):
        """볼륨 변경"""
        if not self.vlc_available:
            return
        self.player.audio_set_volume(int(float(value)))
    
    def on_seek_press(self, event):
        """시크바 누를 때"""
        self.seek_pressed = True
    
    def on_seek_release(self, event):
        """시크바 놓을 때"""
        if not self.vlc_available:
            return
        self.seek_pressed = False
        self.player.set_position(self.seek_var.get() / 1000)
    
    def on_seek(self, value):
        """시크바 이동"""
        if self.seek_pressed and self.current_video and self.vlc_available:
            # 드래그 중에는 시간만 업데이트
            total = self.player.get_length()
            pos = float(value) / 1000
            self.time_label.config(text=f"{self.format_time(total * pos)} / {self.format_time(total)}")
    
    def format_time(self, ms):
        """밀리초를 MM:SS로 변환"""
        if ms <= 0:
            return "00:00"
        total_seconds = int(ms / 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def update_timer(self):
        """재생 상태 업데이트 타이머"""
        if self.vlc_available and self.player and self.player.is_playing() and not self.seek_pressed:
            # 현재 재생 위치 업데이트
            pos = self.player.get_position()
            if pos >= 0:
                self.seek_var.set(pos * 1000)
                
                total = self.player.get_length()
                current = total * pos
                self.time_label.config(text=f"{self.format_time(current)} / {self.format_time(total)}")
        
        self.after(100, self.update_timer)

# =============================================================================
# 설정 UI 프레임 (워터마크 탭에 그라데이션 컨트롤 추가)
# =============================================================================

class SettingsFrame(ttk.Frame):
    def __init__(self, parent, settings: AppSettings, on_change_callback=None, auto_save_callback=None):
        super().__init__(parent)
        self.settings = settings
        self.on_change = on_change_callback
        self.auto_save = auto_save_callback
        self.vars = {}
        self._debounce_id = None
        self.create_widgets()
    
    def create_widgets(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        self.create_video_tab(notebook)
        self.create_reflection_tab(notebook)
        self.create_watermark_tab(notebook)
        self.create_subtitle_tab(notebook)
        self.create_transition_tab(notebook)
        self.create_advanced_tab(notebook)
    
    def on_setting_changed(self, *args):
        """설정값이 변경될 때 호출 - 실시간 반영 및 자동 저장"""
        self.apply_settings_to_object()
        
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        
        if self.on_change:
            self._debounce_id = self.after(500, self._debounced_update)
        
        if self.auto_save:
            self.auto_save()
    
    def _debounced_update(self):
        self._debounce_id = None
        if self.on_change:
            self.on_change()
    
    def apply_settings_to_object(self):
        for key, var in self.vars.items():
            parts = key.split('.')
            obj = self.settings
            for part in parts[:-1]:
                obj = getattr(obj, part)
            try:
                value = var.get()
                setattr(obj, parts[-1], value)
            except Exception:
                pass
    
    def create_video_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="영상")
        row = 0
        
        ttk.Label(frame, text="이미지당 시간 (초):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=self.settings.video.base_image_sec)
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.base_image_sec"] = var
        ttk.Spinbox(frame, from_=0.5, to=10.0, increment=0.1, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="전환 비율 (0.2~0.8):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=self.settings.video.transition_ratio)
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.transition_ratio"] = var
        ttk.Spinbox(frame, from_=0.1, to=0.9, increment=0.05, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="줌 강도 (0.001~0.01):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=self.settings.video.zoom_intensity)
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.zoom_intensity"] = var
        ttk.Spinbox(frame, from_=0.001, to=0.02, increment=0.001, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1

        ttk.Label(frame, text="줌 방향:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.StringVar(value=getattr(self.settings.video, "zoom_direction", "in") or "in")
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.zoom_direction"] = var

        dir_box = tk.Frame(frame, bg="#1a1e2a")
        dir_box.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        tk.Radiobutton(dir_box, text="줌인",   value="in",     variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left")
        tk.Radiobutton(dir_box, text="줌아웃", value="out",    variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left", padx=(6,0))
        tk.Radiobutton(dir_box, text="랜덤",   value="random", variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left", padx=(6,0))
        row += 1

        ttk.Label(frame, text="줌 상한 (예: 1.02~1.08):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=float(getattr(self.settings.video, "zoom_cap", 1.04) or 1.04))
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.zoom_cap"] = var
        ttk.Spinbox(frame, from_=1.00, to=1.20, increment=0.005, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1

        ttk.Label(frame, text="중앙 줌 전용:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.video.zoom_center_only)
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.zoom_center_only"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1

        ttk.Label(frame, text="⚠️ 줌팬 사용:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.video.enable_zoompam)
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.enable_zoompam"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1

        ttk.Label(frame, text="줌팬 강도:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=self.settings.video.zoompam_intensity)
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.zoompam_intensity"] = var
        ttk.Spinbox(frame, from_=0.0005, to=0.005, increment=0.0005, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1

        ttk.Label(frame, text="FPS:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.video.fps)
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.fps"] = var
        ttk.Combobox(frame, textvariable=var, values=[24, 25, 30, 60], width=8).grid(row=row, column=1, padx=5, pady=2)
        row += 1
    
    def create_reflection_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="반사배경")
        row = 0
        
        ttk.Label(frame, text="반사 강도 (1.0~2.5):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=self.settings.reflection.strength)
        var.trace_add("write", self.on_setting_changed)
        self.vars["reflection.strength"] = var
        ttk.Scale(frame, from_=1.0, to=2.5, variable=var, orient="horizontal", length=150).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="블러 강도 (20~100):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.reflection.blur_radius)
        var.trace_add("write", self.on_setting_changed)
        self.vars["reflection.blur_radius"] = var
        ttk.Scale(frame, from_=20, to=100, variable=var, orient="horizontal", length=150).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="배경 어둡기 (0.5~1.0):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=self.settings.reflection.dim)
        var.trace_add("write", self.on_setting_changed)
        self.vars["reflection.dim"] = var
        ttk.Scale(frame, from_=0.5, to=1.0, variable=var, orient="horizontal", length=150).grid(row=row, column=1, padx=5, pady=2)
        row += 1
    
    def create_watermark_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="워터마크")
        
        canvas = tk.Canvas(frame, highlightthickness=0, bg="#1a1e2a")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        row = 0
        ttk.Label(scrollable_frame, text="상호명:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.StringVar(value=self.settings.watermark.brand_text)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.brand_text"] = var
        ttk.Entry(scrollable_frame, textvariable=var, width=20).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(scrollable_frame, text="전화번호:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.StringVar(value=self.settings.watermark.phone_text)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.phone_text"] = var
        ttk.Entry(scrollable_frame, textvariable=var, width=20).grid(row=row, column=1, padx=5, pady=2)
        row += 1

        ttk.Label(scrollable_frame, text="상호-전화 간격(px):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=getattr(self.settings.watermark, "phone_gap_px", 0))
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.phone_gap_px"] = var
        ttk.Spinbox(scrollable_frame, from_=0, to=200, increment=2, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        ttk.Label(scrollable_frame, text="0=자동, 숫자=고정 간격").grid(row=row, column=2, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(scrollable_frame, text="상호 폰트 크기:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.watermark.brand_font_size)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.brand_font_size"] = var
        ttk.Spinbox(scrollable_frame, from_=20, to=100, increment=2, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(scrollable_frame, text="전화번호 폰트 크기:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.watermark.phone_font_size)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.phone_font_size"] = var
        ttk.Spinbox(scrollable_frame, from_=20, to=100, increment=2, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(scrollable_frame, text="상호 색상:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.StringVar(value=self.settings.watermark.brand_color)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.brand_color"] = var
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.grid(row=row, column=1, padx=5, pady=2)
        color_preview = tk.Label(btn_frame, bg=var.get(), width=2, height=1)
        color_preview.pack(side="left", padx=(0, 5))
        btn = ttk.Button(btn_frame, text="선택", command=lambda: self.choose_color(var, color_preview))
        btn.pack(side="left")
        row += 1
        
        ttk.Label(scrollable_frame, text="전화 색상:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.StringVar(value=self.settings.watermark.phone_color)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.phone_color"] = var
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.grid(row=row, column=1, padx=5, pady=2)
        color_preview = tk.Label(btn_frame, bg=var.get(), width=2, height=1)
        color_preview.pack(side="left", padx=(0, 5))
        btn = ttk.Button(btn_frame, text="선택", command=lambda: self.choose_color(var, color_preview))
        btn.pack(side="left")
        row += 1
        
        ttk.Label(scrollable_frame, text="하단 여백:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.watermark.margin_bottom)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.margin_bottom"] = var
        ttk.Spinbox(scrollable_frame, from_=20, to=300, increment=5, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        # 🔥 새 옵션: 하단 그라데이션 박스 설정
        row += 1
        ttk.Label(scrollable_frame, text="━━━━━━━━━━━━━━━━━━━━━━").grid(row=row, column=0, columnspan=3, sticky="w", padx=5, pady=5)
        row += 1
        
        ttk.Label(scrollable_frame, text="🎨 하단 그라데이션", font=("Malgun Gothic", 10, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(scrollable_frame, text="그라데이션 사용:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.watermark.box_enabled)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.box_enabled"] = var
        tk.Checkbutton(scrollable_frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(scrollable_frame, text="그라데이션 투명도:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.watermark.box_alpha)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.box_alpha"] = var
        ttk.Scale(scrollable_frame, from_=0, to=255, variable=var, orient="horizontal", length=150).grid(row=row, column=1, padx=5, pady=2)
        ttk.Label(scrollable_frame, text=f"{var.get()}").grid(row=row, column=2, padx=5)
        row += 1
        
        ttk.Label(scrollable_frame, text="그라데이션 높이:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=self.settings.watermark.box_height_multiplier)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.box_height_multiplier"] = var
        ttk.Scale(scrollable_frame, from_=1.0, to=6.0, variable=var, orient="horizontal", length=150).grid(row=row, column=1, padx=5, pady=2)
        ttk.Label(scrollable_frame, text=f"{var.get():.1f}배").grid(row=row, column=2, padx=5)
        row += 1
        
        ttk.Label(scrollable_frame, text="(텍스트 높이 기준)").grid(row=row, column=1, sticky="w", padx=5, pady=0)
    
    def choose_color(self, var, preview_label):
        color = colorchooser.askcolor(var.get())[1]
        if color:
            var.set(color)
            preview_label.config(bg=color)
    
    def create_subtitle_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="자막")
        row = 0
        
        ttk.Label(frame, text="자막 사용:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.subtitle.enabled)
        var.trace_add("write", self.on_setting_changed)
        self.vars["subtitle.enabled"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="폰트 크기:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.subtitle.font_size)
        var.trace_add("write", self.on_setting_changed)
        self.vars["subtitle.font_size"] = var
        ttk.Spinbox(frame, from_=8, to=30, increment=1, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="하단 여백:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.subtitle.margin_v)
        var.trace_add("write", self.on_setting_changed)
        self.vars["subtitle.margin_v"] = var
        ttk.Spinbox(frame, from_=10, to=200, increment=5, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="외곽선 두께:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.subtitle.outline)
        var.trace_add("write", self.on_setting_changed)
        self.vars["subtitle.outline"] = var
        ttk.Spinbox(frame, from_=0, to=10, increment=1, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="그림자 두께:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.subtitle.shadow)
        var.trace_add("write", self.on_setting_changed)
        self.vars["subtitle.shadow"] = var
        ttk.Spinbox(frame, from_=0, to=10, increment=1, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="박스 모드:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.subtitle.box_mode)
        var.trace_add("write", self.on_setting_changed)
        self.vars["subtitle.box_mode"] = var
        ttk.Combobox(frame, textvariable=var, values=[0, 1, 2], width=5).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="굵게:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.subtitle.bold)
        var.trace_add("write", self.on_setting_changed)
        self.vars["subtitle.bold"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
    
    def create_transition_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="전환효과")
        row = 0
        
        ttk.Label(frame, text="첫 회전 랜덤:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.transition.shuffle_images)
        var.trace_add("write", self.on_setting_changed)
        self.vars["transition.shuffle_images"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="회전마다 랜덤:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.transition.cycle_shuffle)
        var.trace_add("write", self.on_setting_changed)
        self.vars["transition.cycle_shuffle"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="역순 재생:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.transition.reverse_cycle)
        var.trace_add("write", self.on_setting_changed)
        self.vars["transition.reverse_cycle"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="전환 스타일:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.StringVar(value=self.settings.transition.style)
        var.trace_add("write", self.on_setting_changed)
        self.vars["transition.style"] = var
        ttk.Combobox(frame, textvariable=var, values=["natural", "fade_only"], width=12).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="랜덤 색보정:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.color_random.enabled)
        var.trace_add("write", self.on_setting_changed)
        self.vars["color_random.enabled"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
    
    def create_advanced_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="고급")
        row = 0
        
        ttk.Label(frame, text="설정 JSON:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Button(frame, text="JSON 편집", command=self.edit_json).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="프리셋:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=1, padx=5, pady=2)
        ttk.Button(btn_frame, text="저장", command=self.save_preset).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="불러오기", command=self.load_preset).pack(side="left", padx=2)
        row += 1
        
        ttk.Label(frame, text="오디오 랜덤:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.encoding.audio_random_enabled)
        var.trace_add("write", self.on_setting_changed)
        self.vars["encoding.audio_random_enabled"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="오디오 폴더:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        audio_folder_var = tk.StringVar(value=self.settings.encoding.audio_folder)
        audio_folder_var.trace_add("write", self.on_setting_changed)
        self.vars["encoding.audio_folder"] = audio_folder_var
        ttk.Entry(frame, textvariable=audio_folder_var, width=20).grid(row=row, column=1, padx=5, pady=2)
        ttk.Button(frame, text="찾기", command=self.select_audio_folder).grid(row=row, column=2, padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="TEMP 삭제:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.encoding.delete_temp_after_done)
        var.trace_add("write", self.on_setting_changed)
        self.vars["encoding.delete_temp_after_done"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        

        # =============================================================================
        # ✅ 출력 버전 선택 (SNS/HQ)
        # - 기본값: SNS만 생성
        # =============================================================================
        ttk.Label(frame, text="출력 버전:").grid(row=row, column=0, sticky="w", padx=5, pady=2)

        ver_frame = ttk.Frame(frame)
        ver_frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=2)

        sns_var = tk.BooleanVar(value=self.settings.encoding.out_sns_enabled)
        sns_var.trace_add("write", self.on_setting_changed)
        self.vars["encoding.out_sns_enabled"] = sns_var
        tk.Checkbutton(ver_frame, text="SNS(경량)", variable=sns_var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left", padx=(0, 10))

        hq_var = tk.BooleanVar(value=self.settings.encoding.out_hq_enabled)
        hq_var.trace_add("write", self.on_setting_changed)
        self.vars["encoding.out_hq_enabled"] = hq_var
        tk.Checkbutton(ver_frame, text="HQ(고화질)", variable=hq_var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left")

        row += 1

        ttk.Label(frame, text="SNS/HQ 품질(기본):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(frame, text="SNS: (체크 시 720 자동) cq/crf 32 · 96k / HQ: 1080 유지 cq/crf 20 · 192k", foreground="#9aa4b2").grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=2)
        row += 1
        ttk.Label(frame, text="용량 최적화:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(frame, text="CRF 28 / 오디오 128k (모바일 숏폼용)", foreground="#4caf50").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
    
    def select_audio_folder(self):
        folder = filedialog.askdirectory(title="오디오 폴더 선택")
        if folder:
            self.vars["encoding.audio_folder"].set(folder)
    
    def edit_json(self):
        temp_json = Path("temp_settings.json")
        self.settings.save_to_file(temp_json)
        try:
            os.startfile(str(temp_json))
            messagebox.showinfo("JSON 편집", "설정 파일이 열렸습니다.\n수정 후 저장하고 닫아주세요.\n\n적용하려면 '프리셋 불러오기'를 클릭하세요.")
        except Exception as e:
            messagebox.showerror("오류", f"파일을 열 수 없습니다: {e}")
    
    def save_preset(self):
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="프리셋 저장")
        if filename:
            self.settings.save_to_file(Path(filename))
            messagebox.showinfo("완료", "프리셋이 저장되었습니다.")
    
    def load_preset(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="프리셋 불러오기")
        if filename:
            try:
                new_settings = AppSettings.load_from_file(Path(filename))
                self.settings = new_settings
                self.update_vars_from_settings()
                messagebox.showinfo("완료", "프리셋이 적용되었습니다.")
                if self.on_change:
                    self.on_change()
                if self.auto_save:
                    self.auto_save()
            except Exception as e:
                messagebox.showerror("오류", f"프리셋 불러오기 실패: {e}")
    
    def update_vars_from_settings(self):
        for key, var in self.vars.items():
            parts = key.split('.')
            obj = self.settings
            for part in parts[:-1]:
                obj = getattr(obj, part)
            value = getattr(obj, parts[-1])
            try:
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(value))
                elif isinstance(var, tk.IntVar):
                    var.set(int(value))
                elif isinstance(var, tk.DoubleVar):
                    var.set(float(value))
                else:
                    var.set(str(value))
            except Exception:
                pass
    
    def apply_settings(self):
        """호환성을 위해 유지"""
        self.apply_settings_to_object()
        return self.settings

# =============================================================================
# 멀티 진행바 컴포넌트
# =============================================================================

class MultiProgressBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#0f1115")
        
        pre_frame = tk.Frame(self, bg="#0f1115")
        pre_frame.pack(fill="x", pady=(0, 5))
        
        tk.Label(pre_frame, text="📸 전처리:", fg="#c7d0db", bg="#0f1115", font=("Malgun Gothic", 9)).pack(side="left", padx=(0, 10))
        self.pre_bar = ttk.Progressbar(pre_frame, orient="horizontal", mode="determinate", length=200)
        self.pre_bar.pack(side="left", fill="x", expand=True)
        self.pre_label = tk.Label(pre_frame, text="0/0 (0%)", fg="#9aa4b2", bg="#0f1115", font=("Malgun Gothic", 9), width=15)
        self.pre_label.pack(side="right", padx=(5, 0))
        
        enc_frame = tk.Frame(self, bg="#0f1115")
        enc_frame.pack(fill="x", pady=(0, 5))
        
        tk.Label(enc_frame, text="🎬 인코딩:", fg="#c7d0db", bg="#0f1115", font=("Malgun Gothic", 9)).pack(side="left", padx=(0, 10))
        self.enc_bar = ttk.Progressbar(enc_frame, orient="horizontal", mode="determinate", length=200)
        self.enc_bar.pack(side="left", fill="x", expand=True)
        self.enc_label = tk.Label(enc_frame, text="0%", fg="#9aa4b2", bg="#0f1115", font=("Malgun Gothic", 9), width=15)
        self.enc_label.pack(side="right", padx=(5, 0))
        
        info_frame = tk.Frame(self, bg="#0f1115")
        info_frame.pack(fill="x", pady=(5, 0))
        
        self.eta_label = tk.Label(info_frame, text="⏱️ 예상: --:--", fg="#c7d0db", bg="#0f1115", font=("Malgun Gothic", 9))
        self.eta_label.pack(side="left", padx=(0, 15))
        self.speed_label = tk.Label(info_frame, text="⚡ 속도: --x", fg="#c7d0db", bg="#0f1115", font=("Malgun Gothic", 9))
        self.speed_label.pack(side="left", padx=(0, 15))
        self.remain_label = tk.Label(info_frame, text="📊 남음: --", fg="#c7d0db", bg="#0f1115", font=("Malgun Gothic", 9))
        self.remain_label.pack(side="left")
    
    def update_preprocess(self, current: int, total: int, percent: float, eta: float, speed: str):
        self.pre_bar["value"] = percent
        self.pre_label.config(text=f"{current}/{total} ({percent:.1f}%)")
        if eta > 0:
            self.eta_label.config(text=f"⏱️ 예상: {format_time(eta)}")
            self.speed_label.config(text=f"⚡ 속도: {speed}")
            self.remain_label.config(text=f"📊 남음: {total-current}장")
    
    def update_encode(self, percent: float, eta: float, speed: str, current_sec: float = None, total_sec: float = None):
        self.enc_bar["value"] = percent
        if current_sec is not None and total_sec is not None:
            self.enc_label.config(text=f"{current_sec:.1f}/{total_sec:.1f}초 ({percent:.1f}%)")
            remain_sec = total_sec - current_sec
            self.remain_label.config(text=f"📊 남음: {format_time(remain_sec)}")
        else:
            self.enc_label.config(text=f"{percent:.1f}%")
        if eta > 0:
            self.eta_label.config(text=f"⏱️ 예상: {format_time(eta)}")
            self.speed_label.config(text=f"⚡ 속도: {speed}")
    
    def reset(self):
        self.pre_bar["value"] = 0
        self.enc_bar["value"] = 0
        self.pre_label.config(text="0/0 (0%)")
        self.enc_label.config(text="0%")
        self.eta_label.config(text="⏱️ 예상: --:--")
        self.speed_label.config(text="⚡ 속도: --x")
        self.remain_label.config(text="📊 남음: --")

# =============================================================================
# 메인 UI (프리뷰 모드 전환 + 자동 재생)
# =============================================================================

class CineUI:
    def __init__(self, embed_mode=False, parent=None):
        self.embed_mode = embed_mode
        
        if embed_mode and parent:
            # 프레임 모드: 부모 프레임에 삽입
            self.root = parent
            self.root.configure(bg="#0f1115")
        else:
            # 독립 실행 모드
            self.root = tk.Tk()
            self.root.title("KKBBQ 숏폼 제작기 v5.2")
            self.root.geometry("1400x1290")
            self.root.configure(bg="#0f1115")
        
        self.config_file = Path("settings.json")
        self.settings = AppSettings()
        self.load_last_settings()
        
        # 자동 저장 타이머
        self._auto_save_timer = None
        
        # 프리뷰 모드
        self.preview_mode = tk.StringVar(value="image")  # "image" 또는 "video"
        
        # 출력 폴더
        self.output_folder = None

        # ===== 환경변수 설정 적용 =====
        if os.environ.get('SLID_BRAND_NAME'):
            self.settings.watermark.brand_text = os.environ.get('SLID_BRAND_NAME')
            print(f"[환경변수] 상호명: {self.settings.watermark.brand_text}")

        if os.environ.get('SLID_PHONE_NUMBER'):
            self.settings.watermark.phone_text = os.environ.get('SLID_PHONE_NUMBER')
            print(f"[환경변수] 전화번호: {self.settings.watermark.phone_text}")

        if os.environ.get('SLID_BRAND_SIZE'):
            self.settings.watermark.brand_font_size = int(os.environ.get('SLID_BRAND_SIZE'))

        if os.environ.get('SLID_PHONE_SIZE'):
            self.settings.watermark.phone_font_size = int(os.environ.get('SLID_PHONE_SIZE'))

        if os.environ.get('SLID_MARGIN_BOTTOM'):
            self.settings.watermark.margin_bottom = int(os.environ.get('SLID_MARGIN_BOTTOM'))

        if os.environ.get('SLID_BOX_ENABLED'):
            self.settings.watermark.box_enabled = os.environ.get('SLID_BOX_ENABLED').lower() == 'true'

        if os.environ.get('SLID_STROKE_ENABLED'):
            self.settings.watermark.stroke_enabled = os.environ.get('SLID_STROKE_ENABLED').lower() == 'true'

        if os.environ.get('SLID_SHADOW_ENABLED'):
            self.settings.watermark.shadow_enabled = os.environ.get('SLID_SHADOW_ENABLED').lower() == 'true'

        if os.environ.get('SLID_IMAGE_SEC'):
            self.settings.video.base_image_sec = float(os.environ.get('SLID_IMAGE_SEC'))

        if os.environ.get('SLID_TRANSITION_SEC'):
            base_sec = self.settings.video.base_image_sec
            trans_sec = float(os.environ.get('SLID_TRANSITION_SEC'))
            if base_sec > 0:
                self.settings.video.transition_ratio = trans_sec / base_sec
            print(f"[환경변수] 전환시간: {trans_sec}초 → 비율: {self.settings.video.transition_ratio:.2f}")

        if os.environ.get('SLID_ZOOM_INTENSITY'):
            self.settings.video.zoom_intensity = float(os.environ.get('SLID_ZOOM_INTENSITY'))

        if os.environ.get('SLID_SUBTITLE_ENABLED'):
            self.settings.subtitle.enabled = os.environ.get('SLID_SUBTITLE_ENABLED').lower() == 'true'

        if os.environ.get('SLID_SUBTITLE_SIZE'):
            self.settings.subtitle.font_size = int(os.environ.get('SLID_SUBTITLE_SIZE'))

        if os.environ.get('SLID_SUBTITLE_MARGIN'):
            self.settings.subtitle.margin_v = int(os.environ.get('SLID_SUBTITLE_MARGIN'))

        print('[설정] 환경변수 적용 완료')


        self.setup_styles()
        self.create_widgets()
        
        self.qevt = queue.Queue()
        self.worker = None
        self.preview_image = None
        self.preview_photo = None
        self.img_dir = None
        self.audio_path = None
        self.srt_path = None
        
        if hasattr(self.root, "protocol"):
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        if hasattr(self.root, "after"):
            self.root.after(120, self.poll)
    
    def load_last_settings(self):
        if self.config_file.exists():
            try:
                self.settings = AppSettings.load_from_file(self.config_file)
                safe_print(f"✅ 마지막 설정을 불러왔습니다: {self.config_file}")
            except Exception as e:
                safe_print(f"⚠️ 설정 불러오기 실패: {e}")
    
    def save_last_settings(self):
        """설정을 파일에 저장 (자동 저장)"""
        try:
            self.settings.save_to_file(self.config_file)
            safe_print(f"✅ 설정이 저장되었습니다: {self.config_file}")
        except Exception as e:
            safe_print(f"⚠️ 설정 저장 실패: {e}")
    
    def schedule_auto_save(self):
        """자동 저장 예약 (디바운싱)"""
        if self._auto_save_timer:
            self.root.after_cancel(self._auto_save_timer)
        self._auto_save_timer = self.root.after(1000, self.save_last_settings)  # 1초 후 저장
    
    def on_closing(self):
        """프로그램 종료 시 설정 저장"""
        self.save_last_settings()
        self.root.destroy()

    def apply_image_based_defaults(self):
        """이미지 폴더를 고른 직후 기본값을 현재 프로젝트 성격에 맞춰 자동 보정"""
        if not self.img_dir:
            return
        try:
            imgs = find_images(self.img_dir)
            if not imgs:
                return
            sample = imgs[: min(8, len(imgs))]
            portrait = 0
            landscape = 0
            for p in sample:
                try:
                    with Image.open(p) as im:
                        im = ImageOps.exif_transpose(im)
                        w, h = im.size
                        if h >= w:
                            portrait += 1
                        else:
                            landscape += 1
                except Exception:
                    pass
            # 출력은 SNS 세로형으로 고정
            self.settings.video.width = 1080
            self.settings.video.height = 1920
            self.settings.video.fps = 30
            self.settings.video.base_image_sec = 5.0
            self.settings.video.transition_ratio = 1.0
            self.settings.video.zoom_direction = "random"
            self.settings.video.zoom_cap = 1.005
            self.settings.video.zoom_center_only = True
            self.settings.video.enable_zoompam = False
            self.settings.video.zoompam_intensity = 0.001

            # 가로 이미지가 많으면 배경 반사를 조금 더 강하게
            if landscape > portrait:
                self.settings.reflection.strength = 1.75
                self.settings.reflection.blur_radius = 58
                self.settings.reflection.dim = 0.68
            else:
                self.settings.reflection.strength = 1.60
                self.settings.reflection.blur_radius = 42
                self.settings.reflection.dim = 0.74

            self.settings.subtitle.enabled = True
            self.settings.subtitle.font_size = 8
            self.settings.subtitle.margin_v = 40
            self.settings.subtitle.outline = 1
            self.settings.subtitle.shadow = 1
            self.settings.subtitle.box_mode = 0
            self.settings.subtitle.bold = True

            self.settings.watermark.brand_text = self.settings.watermark.brand_text or "오박사 만능인테리어"
            self.settings.watermark.phone_text = self.settings.watermark.phone_text or "010-8284-5584"
            self.settings.watermark.phone_gap_px = 47
            self.settings.watermark.brand_font_size = 46
            self.settings.watermark.phone_font_size = 43
            self.settings.watermark.margin_bottom = 80
            self.settings.watermark.box_enabled = True
            self.settings.watermark.box_alpha = 70
            self.settings.watermark.box_height_multiplier = 3.0

            if hasattr(self, "settings_frame"):
                self.settings_frame.settings = self.settings
                self.settings_frame.update_vars_from_settings()
            
            # 자동 저장 예약
            self.schedule_auto_save()
            
        except Exception as e:
            safe_print(f"⚠️ 이미지 기본값 자동 적용 실패: {e}")
    
    def setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        
        style.configure("TNotebook", background="#1a1e2a")
        style.configure("TNotebook.Tab", background="#2a3145", foreground="#ffffff", padding=[10, 2])
        style.map("TNotebook.Tab", background=[("selected", "#3b4a6b")])
        style.configure("TFrame", background="#1a1e2a")
        style.configure("TLabel", background="#1a1e2a", foreground="#ffffff")
        style.configure("TButton", background="#2d6cdf", foreground="#ffffff", borderwidth=0, focuscolor="none")
        style.map("TButton", background=[("active", "#3b7af0")])
        style.configure("TProgressbar", thickness=18, background="#2d6cdf")
    
    def create_widgets(self):
        header = tk.Frame(self.root, bg="#0f1115")
        header.pack(fill="x", padx=16, pady=(14, 10))
        
        tk.Label(header, text="KKBBQ 숏폼 제작기 v5.2", fg="#ffffff", bg="#0f1115", font=("Malgun Gothic", 18, "bold")).pack(anchor="w")
        tk.Label(header, text="1080x1920 / 반사배경 / 워터마크 / 자막 / 느린 중앙 줌 / 랜덤 오디오", fg="#9aa4b2", bg="#0f1115", font=("Malgun Gothic", 10)).pack(anchor="w", pady=(6, 0))
        
        main_container = tk.Frame(self.root, bg="#0f1115")
        main_container.pack(fill="both", expand=True, padx=16, pady=10)
        
        left_panel = tk.Frame(main_container, bg="#0f1115", width=450)
        left_panel.pack(side="left", fill="both", expand=False, padx=(0, 8))
        left_panel.pack_propagate(False)
        
        right_panel = tk.Frame(main_container, bg="#0f1115")
        right_panel.pack(side="right", fill="both", expand=True, padx=(8, 0))
        
        # 파일 선택 프레임
        file_frame = tk.Frame(left_panel, bg="#1a1e2a", relief="flat", bd=1)
        file_frame.pack(fill="x", pady=(0, 10))
        
        tk.Label(file_frame, text="📁 파일 선택", fg="#ffffff", bg="#1a1e2a", font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        img_frame = tk.Frame(file_frame, bg="#1a1e2a")
        img_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(img_frame, text="이미지 폴더:", fg="#c7d0db", bg="#1a1e2a", width=12).pack(side="left")
        self.img_dir_label = tk.Label(img_frame, text="선택 안됨", fg="#9aa4b2", bg="#1a1e2a", anchor="w", width=25)
        self.img_dir_label.pack(side="left", fill="x", expand=True)
        ttk.Button(img_frame, text="찾아보기", command=self.select_img_dir, width=10).pack(side="right")
        
        audio_frame = tk.Frame(file_frame, bg="#1a1e2a")
        audio_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(audio_frame, text="오디오 파일:", fg="#c7d0db", bg="#1a1e2a", width=12).pack(side="left")
        self.audio_label = tk.Label(audio_frame, text="선택 안됨", fg="#9aa4b2", bg="#1a1e2a", anchor="w", width=25)
        self.audio_label.pack(side="left", fill="x", expand=True)
        ttk.Button(audio_frame, text="찾아보기", command=self.select_audio, width=10).pack(side="right")
        
        srt_frame = tk.Frame(file_frame, bg="#1a1e2a")
        srt_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(srt_frame, text="자막 파일:", fg="#c7d0db", bg="#1a1e2a", width=12).pack(side="left")
        self.srt_label = tk.Label(srt_frame, text="선택 안됨", fg="#9aa4b2", bg="#1a1e2a", anchor="w", width=25)
        self.srt_label.pack(side="left", fill="x", expand=True)
        btn_frame = tk.Frame(srt_frame, bg="#1a1e2a")
        btn_frame.pack(side="right")
        
        ttk.Button(btn_frame, text="오디오+자막", command=self.select_audio_srt_pair, width=10).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="찾아보기", command=self.select_srt, width=8).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="초기화", command=self.clear_srt, width=6).pack(side="left")
        
        self.settings_frame = SettingsFrame(left_panel, self.settings, 
                                           on_change_callback=self.update_preview,
                                           auto_save_callback=self.schedule_auto_save)
        self.settings_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.warning_label = tk.Label(left_panel, text="", fg="#ffaa00", bg="#0f1115", font=("Malgun Gothic", 9), wraplength=400, justify="left")
        self.warning_label.pack(fill="x", pady=(0, 5))
        
        btn_frame = tk.Frame(left_panel, bg="#0f1115")
        btn_frame.pack(fill="x", pady=(0, 5))
        
        self.btn_start = tk.Button(btn_frame, text="🎬 작업 시작", command=self.start,
                                   bg="#2d6cdf", fg="white", activebackground="#3b7af0",
                                   activeforeground="white", relief="flat",
                                   font=("Malgun Gothic", 12, "bold"), padx=20, pady=12)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_preview = tk.Button(btn_frame, text="👁 프리뷰", command=self.update_preview,
                                     bg="#4a5568", fg="white", activebackground="#5f6b80",
                                     activeforeground="white", relief="flat",
                                     font=("Malgun Gothic", 11), padx=10, pady=12)
        self.btn_preview.pack(side="right", padx=(5, 0))
        
        # 우측 패널 - 프리뷰 영역
        preview_tab_frame = tk.Frame(right_panel, bg="#1a1e2a")
        preview_tab_frame.pack(fill="x", pady=(0, 5))
        
        tk.Radiobutton(preview_tab_frame, text="🖼️ 이미지 프리뷰", 
                      variable=self.preview_mode, value="image",
                      command=self.switch_preview_mode,
                      bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left", padx=5)
        
        tk.Radiobutton(preview_tab_frame, text="🎬 영상 프리뷰", 
                      variable=self.preview_mode, value="video",
                      command=self.switch_preview_mode,
                      bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left", padx=5)
        
        # 이미지 프리뷰 프레임
        self.image_preview_frame = tk.Frame(right_panel, bg="#1a1e2a", relief="flat", bd=1)
        self.create_image_preview(self.image_preview_frame)
        
        # 영상 프리뷰 프레임
        self.video_preview_frame = tk.Frame(right_panel, bg="#1a1e2a", relief="flat", bd=1)
        self.create_video_preview(self.video_preview_frame)
        
        # 초기에는 이미지 프리뷰만 표시
        self.image_preview_frame.pack(fill="both", expand=True, pady=(0, 10))
        self.video_preview_frame.pack_forget()
        
        self.progress_bars = MultiProgressBar(right_panel)
        self.progress_bars.pack(fill="x", pady=(0, 10))
        
        info_frame = tk.Frame(right_panel, bg="#1a1e2a", relief="flat", bd=1)
        info_frame.pack(fill="x", pady=(0, 10))
        
        tk.Label(info_frame, text="📊 파일 정보", fg="#ffffff", bg="#1a1e2a", font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.info_text = tk.Label(info_frame, text="이미지: 0장\n오디오: -\n예상 영상 길이: -",
                                  fg="#c7d0db", bg="#1a1e2a", font=("Malgun Gothic", 10), justify="left")
        self.info_text.pack(anchor="w", padx=10, pady=(0, 10))
        
        log_frame = tk.Frame(right_panel, bg="#1a1e2a", relief="flat", bd=1)
        log_frame.pack(fill="both", expand=True)
        
        tk.Label(log_frame, text="📋 진행 로그", fg="#ffffff", bg="#1a1e2a", font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.txt = ScrolledText(log_frame, wrap="word", height=8, bg="#121622", fg="#dbe5f0",
                                insertbackground="#dbe5f0", relief="flat", font=("Consolas", 9))
        self.txt.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt.insert("1.0", "준비 완료.\n")
        self.txt.config(state="disabled")
        
        progress_frame = tk.Frame(right_panel, bg="#0f1115")
        progress_frame.pack(fill="x", pady=(5, 0))
        
        self.stage_var = tk.StringVar(value="대기")
        self.detail_var = tk.StringVar(value="")
        
        tk.Label(progress_frame, textvariable=self.stage_var, fg="#ffffff", bg="#0f1115", font=("Malgun Gothic", 11, "bold")).pack(anchor="w")
        tk.Label(progress_frame, textvariable=self.detail_var, fg="#c7d0db", bg="#0f1115", font=("Malgun Gothic", 9)).pack(anchor="w", pady=(2, 0))
    
    def create_image_preview(self, parent):
        """이미지 프리뷰 프레임 생성"""
        tk.Label(parent, text="🖼️ 이미지 프리뷰 (첫 번째 이미지)", 
                fg="#ffffff", bg="#1a1e2a", 
                font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.preview_canvas = tk.Canvas(parent, bg="#121622", width=360, height=640, 
                                       highlightthickness=0)
        self.preview_canvas.pack(pady=10, padx=10)
        
        self.preview_info = tk.Label(parent, text="이미지 폴더를 선택하세요", 
                                     fg="#9aa4b2", bg="#1a1e2a", 
                                     font=("Malgun Gothic", 9))
        self.preview_info.pack(pady=(0, 10))
    
    def create_video_preview(self, parent):
        """영상 프리뷰 프레임 생성"""
        tk.Label(parent, text="🎬 영상 프리뷰", 
                fg="#ffffff", bg="#1a1e2a", 
                font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        # 영상 플레이어 (자동 경로 탐색)
        self.video_player = VideoPreviewPlayer(
            parent, 
            on_folder_open_callback=lambda: self.open_folder(self.output_folder)
        )
        self.video_player.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def switch_preview_mode(self):
        """프리뷰 모드 전환"""
        if self.preview_mode.get() == "image":
            self.video_preview_frame.pack_forget()
            self.image_preview_frame.pack(fill="both", expand=True, pady=(0, 10))
            self.update_preview()
        else:
            self.image_preview_frame.pack_forget()
            self.video_preview_frame.pack(fill="both", expand=True, pady=(0, 10))
            self.update_video_preview(auto_play=False)  # 수동 전환 시 자동 재생 안 함
    
    def update_video_preview(self, auto_play=False):
        """영상 프리뷰 업데이트"""
        if self.output_folder and self.output_folder.exists():
            self.video_player.update_video_list(self.output_folder, auto_play)
    
    def select_img_dir(self):
        folder = filedialog.askdirectory(title="이미지 폴더 선택")
        if folder:
            self.img_dir = Path(folder)
            self.img_dir_label.config(text=str(self.img_dir)[:30] + "...")
            self.apply_image_based_defaults()
            self.update_file_info()
            self.update_preview()
            self.schedule_auto_save()
    
    def select_audio(self):
        file = filedialog.askopenfilename(title="오디오 파일 선택", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac"), ("All files", "*.*")])
        if file:
            self.audio_path = Path(file)
            self.audio_label.config(text=self.audio_path.name)
            self.update_file_info()
            self.schedule_auto_save()
    
    def select_srt(self):
        file = filedialog.askopenfilename(title="자막 SRT 선택", filetypes=[("SubRip", "*.srt"), ("All files", "*.*")])
        if file:
            self.srt_path = Path(file)
            self.srt_label.config(text=self.srt_path.name)
            self.schedule_auto_save()
    
    def select_audio_srt_pair(self):
        audio_file = filedialog.askopenfilename(title="오디오 파일 선택 (자막은 자동 찾기)", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac"), ("All files", "*.*")])
        if not audio_file: return
        
        audio_path = Path(audio_file)
        self.audio_path = audio_path
        self.audio_label.config(text=audio_path.name)
        
        srt_candidates = [audio_path.with_suffix(".srt"), audio_path.parent / f"{audio_path.stem}.srt"]
        
        for srt_path in srt_candidates:
            if srt_path.exists():
                self.srt_path = srt_path
                self.srt_label.config(text=srt_path.name)
                messagebox.showinfo("자막 발견", f"자막 파일이 자동으로 선택되었습니다:\n{srt_path.name}")
                break
        else:
            if messagebox.askyesno("자막 없음", "같은 이름의 SRT 파일이 없습니다. 직접 선택하시겠습니까?"):
                self.select_srt()
        
        self.update_file_info()
        self.schedule_auto_save()
    
    def clear_srt(self):
        self.srt_path = None
        self.srt_label.config(text="선택 안됨")
        self.schedule_auto_save()
    
    def update_file_info(self):
        img_count = 0
        audio_len = 0
        if self.img_dir:
            imgs = find_images(self.img_dir)
            img_count = len(imgs)
        
        if self.audio_path:
            audio_len = probe_audio_duration(self.audio_path, self.settings.encoding.ffprobe_bin)
        
        video_len = img_count * self.settings.video.base_image_sec
        if audio_len > 0 and video_len < audio_len:
            repeat = ceil(audio_len / video_len) if video_len > 0 else 1
            video_len = img_count * self.settings.video.base_image_sec * repeat
            info = f"이미지: {img_count}장 (반복 {repeat}회)\n오디오: {audio_len:.1f}초\n예상 영상: {video_len:.1f}초"
        else:
            info = f"이미지: {img_count}장\n오디오: {audio_len:.1f}초\n예상 영상: {video_len:.1f}초"
        
        self.info_text.config(text=info)
    
    def update_preview(self):
        if not self.img_dir:
            self.preview_info.config(text="이미지 폴더를 선택하세요")
            return
        
        self.settings = self.settings_frame.apply_settings()
        
        warnings = validate_settings(self.settings)
        if warnings:
            self.warning_label.config(text="\n".join(warnings))
        else:
            self.warning_label.config(text="")
        
        try:
            preview_img, name = preprocess_images(self.img_dir, self.settings, None, preview_only=True)
            if preview_img:
                preview_img.thumbnail((360, 640), Image.LANCZOS)
                self.preview_photo = self.pil_to_photo(preview_img)
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(180, 320, image=self.preview_photo)
                self.preview_info.config(text=f"프리뷰: {name}")
            else:
                self.preview_info.config(text="프리뷰 생성 실패")
        except Exception as e:
            self.preview_info.config(text=f"프리뷰 오류: {str(e)[:30]}")
    
    def pil_to_photo(self, pil_image):
        from PIL import ImageTk
        return ImageTk.PhotoImage(pil_image)
    
    def log(self, s: str):
        safe_print(s)
        self.txt.config(state="normal")
        self.txt.insert("end", s + "\n")
        self.txt.see("end")
        self.txt.config(state="disabled")
    
    def set_progress(self, stage: str, detail: str):
        self.stage_var.set(stage)
        self.detail_var.set(detail)
    
    def start(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("진행중", "이미 작업이 진행 중입니다.")
            return
        
        if not self.img_dir or not self.audio_path:
            messagebox.showwarning("파일 부족", "이미지 폴더와 오디오 파일을 모두 선택해주세요.")
            return
        
        self.settings = self.settings_frame.apply_settings()
        
        warnings = validate_settings(self.settings)
        if warnings:
            for w in warnings:
                self.log(f"⚠️ {w}")
        
        self.btn_start.config(state="disabled")
        self.progress_bars.reset()
        self.set_progress("준비", "작업 스레드 시작")
        self.log("작업 시작.")
        self.worker = threading.Thread(target=self.worker_run, 
                                       args=(self.img_dir, self.audio_path, self.srt_path), 
                                       daemon=True)
        self.worker.start()
    
    def worker_run(self, img_dir: Path, audio: Path, srt: Path | None):
        t0 = time.time()
        try:
            self.qevt.put(("progress", "시작", "전처리(반사 배경 + 워터마크) 시작"))
            out_folder, pre_imgs = preprocess_images(img_dir, self.settings, self.qevt, preview_only=False)
            
            self.qevt.put(("progress", "최종 생성", "원패스 인코딩 시작"))
            reports = build_video_onepass(pre_imgs, audio, srt, base_dir=img_dir, 
                                        settings=self.settings, qevt=self.qevt)
            for r in reports:
                r.elapsed = time.time() - t0
            
            if reports:
                self.output_folder = reports[0].output_folder
            
            if self.settings.encoding.delete_temp_after_done:
                try:
                    if reports and reports[0].temp_folder.exists():
                        shutil.rmtree(reports[0].temp_folder, ignore_errors=True)
                except Exception:
                    pass
            
            self.qevt.put(("done", reports))
        except Exception as e:
            self.qevt.put(("error", str(e)))
    
    def open_folder(self, folder: Path):
        try:
            if folder and folder.exists():
                if os.name == "nt":
                    os.startfile(str(folder.resolve()))
        except Exception:
            pass
    
    def _report_popup(self, reports: list[BuildReport]):
        # 작업 완료 후 자동으로 영상 프리뷰 탭으로 전환 및 재생
        if reports and self.preview_mode.get() != "video":
            self.preview_mode.set("video")
            self.switch_preview_mode()
        
        if self.preview_mode.get() == "video" and self.output_folder:
            self.video_player.update_video_list(self.output_folder, auto_play=True)
        
        pop = tk.Toplevel(self.root)
        pop.title("작업 리포트")
        pop.geometry("760x480")
        pop.configure(bg="#0f1115")
        pop.attributes("-topmost", True)

        tk.Label(pop, text="✅ 작업 완료", fg="#ffffff", bg="#0f1115",
                 font=("Malgun Gothic", 14, "bold")).pack(anchor="w", padx=14, pady=(12, 0))

        text = tk.Text(pop, wrap="word", height=18, bg="#121622", fg="#dbe5f0",
                       relief="flat", insertbackground="#dbe5f0", font=("Consolas", 10))
        text.pack(fill="both", expand=True, padx=14, pady=12)

        if not reports:
            msg = "리포트를 표시할 데이터가 없습니다."
            out_folder = None
        else:
            base = reports[0]
            out_folder = base.output_folder

            lines = []
            lines.append("📦 생성된 파일")
            for r in reports:
                lines.append(f"  - [{r.version_label}] {r.output_mp4.name}")
                lines.append(f"      · 크기: {r.file_size_mb:.2f} MB")
                lines.append(f"      · 인코더: {r.encoder_used}")
                lines.append(f"      · 품질: {r.video_quality}")
                lines.append(f"      · 오디오: {r.audio_bitrate}")
            lines.append("")
            lines.append("📊 공통 정보")
            lines.append(f"  - 이미지 수: {base.img_count}장")
            lines.append(f"  - 반복 횟수: {base.repeat_count}회")
            lines.append(f"  - 오디오 길이: {base.audio_len:.2f}초")
            lines.append(f"  - 영상 길이: {base.video_len:.2f}초")
            lines.append(f"  - 이미지당 표시: {base.seg:.2f}초")
            lines.append(f"  - 전환시간: {base.fade:.2f}초")
            lines.append("")
            lines.append(f"🎵 사용 오디오: {Path(base.audio_used).name}")
            lines.append(f"⏱️ 총 소요 시간: {base.elapsed:.2f}초")
            lines.append(f"🗑️ TEMP 정리: {'삭제 완료' if self.settings.encoding.delete_temp_after_done else '유지'}")
            lines.append(f"📂 출력 폴더: {base.output_folder}")

            msg = "\n".join(lines)

        text.insert("1.0", msg)
        text.config(state="disabled")

        btn_frame = tk.Frame(pop, bg="#0f1115")
        btn_frame.pack(fill="x", padx=14, pady=(0, 14))

        tk.Button(
            btn_frame,
            text="폴더 열기",
            command=(lambda: self.open_folder(out_folder)) if out_folder else (lambda: None),
            bg="#2d6cdf",
            fg="white",
            activebackground="#3b7af0",
            relief="flat",
            padx=12,
            pady=6
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="확인",
            command=pop.destroy,
            bg="#4a5568",
            fg="white",
            activebackground="#5f6b80",
            relief="flat",
            padx=12,
            pady=6
        ).pack(side="right")

        timer = {"id": None, "last": time.time()}

        def reset_timer(_evt=None):
            timer["last"] = time.time()

        def tick():
            if time.time() - timer["last"] >= 10.0:
                try:
                    pop.destroy()
                except Exception:
                    pass
                return
            timer["id"] = pop.after(250, tick)

        for ev in ("<Key>", "<Button>", "<Motion>", "<MouseWheel>"):
            pop.bind(ev, reset_timer)

        tick()
    
    def poll(self):
        try:
            while True:
                evt = self.qevt.get_nowait()
                kind = evt[0]
                
                if kind == "log":
                    self.log(evt[1])
                elif kind == "progress":
                    _, stage, detail = evt
                    self.set_progress(stage, detail)
                elif kind == "progress_pre":
                    _, detail, percent, eta, speed = evt
                    match = re.search(r"(\d+)/(\d+)", detail)
                    if match:
                        current = int(match.group(1))
                        total = int(match.group(2))
                        self.progress_bars.update_preprocess(current, total, percent, eta, speed)
                    self.set_progress("전처리", detail)
                elif kind == "progress_enc":
                    _, detail, percent, eta, speed = evt
                    match = re.search(r"(\d+\.?\d*)/(\d+\.?\d*)초", detail)
                    if match:
                        current = float(match.group(1))
                        total = float(match.group(2))
                        self.progress_bars.update_encode(percent, eta, speed, current, total)
                    else:
                        self.progress_bars.update_encode(percent, eta, speed)
                    self.set_progress("인코딩", detail)
                elif kind == "done":
                    _, reports = evt
                    self.log("✅ 작업 완료.")
                    self.progress_bars.update_encode(100, 0, "0x")
                    self.set_progress("완료", "작업 완료")
                    self.btn_start.config(state="normal")
                    
                    if reports:
                        self.open_folder(reports[0].preprocess_folder)
                        self.open_folder(reports[0].output_folder)
                    
                    self._report_popup(reports)
                    self.update_file_info()
                
                elif kind == "error":
                    _, err = evt
                    self.btn_start.config(state="normal")
                    self.set_progress("오류", "작업 중단")
                    self.log(f"❌ 오류 발생: {err}")
                    messagebox.showerror("오류", err)
        
        except queue.Empty:
            pass
        
        self.root.after(120, self.poll)
    
    def run(self):
        self.root.mainloop()

# =============================================================================
# 실행
# =============================================================================

def main(embed_mode=False, parent=None):
    """통합 모드 지원"""
    if embed_mode:
        # 프레임 모드: parent 프레임에 삽입
        app = CineUI(embed_mode=True, parent=parent)
        return app
    else:
        # 독립 실행 모드
        app = CineUI()
        app.run()

def _headless_cli():
    import argparse
    from pathlib import Path
    import queue as _queue
    import shutil as _shutil

    parser = argparse.ArgumentParser()
    parser.add_argument("--image-folder", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--srt", default="")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--project-key", required=True)
    args = parser.parse_args()

    image_folder = Path(args.image_folder)
    audio_path = Path(args.audio)
    srt_path = Path(args.srt) if args.srt else None
    project_dir = Path(args.project_dir)
    project_key = args.project_key

    project_dir.mkdir(parents=True, exist_ok=True)

    qevt = _queue.Queue()
    settings = AppSettings()

    out_folder, pre_imgs = preprocess_images(image_folder, settings, qevt, preview_only=False)
    _ = build_video_onepass(pre_imgs, audio_path, srt_path, base_dir=project_dir, settings=settings, qevt=qevt)

    cand_root = project_dir / "OUTPUT"
    built_mp4s = sorted(cand_root.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True) if cand_root.exists() else []
    if not built_mp4s:
        built_mp4s = sorted(project_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not built_mp4s:
        raise RuntimeError("MP4 생성 실패: 결과 mp4를 찾지 못했습니다.")

    final_mp4 = project_dir / f"{project_key}.mp4"
    try:
        if final_mp4.exists():
            final_mp4.unlink()
    except Exception:
        pass
    built_mp4s[0].replace(final_mp4)

    try:
        _shutil.rmtree(project_dir / "OUTPUT", ignore_errors=True)
    except Exception:
        pass

    print(f"[DONE] {final_mp4}")

if __name__ == "__main__":
    import sys as _sys

    # 명령줄 인자로 프레임 모드 확인
    if "--embed" in _sys.argv:
        # 프레임 모드로 실행 (외부에서 호출)
        pass  # 외부에서 직접 호출할 때 사용
    elif any(k in _sys.argv for k in ["--image-folder", "--project-dir", "--project-key", "--audio"]):
        _headless_cli()
    else:
        main(embed_mode=False)  # 일반 모드
