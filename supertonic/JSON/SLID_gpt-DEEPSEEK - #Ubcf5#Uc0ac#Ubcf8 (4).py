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
- ✅ 파일 크기 최적화 (화질 손실 없이 10% 감소)
- ✅ 오디오/자막 파일 동시 선택 (파일명 동일, 확장자만 다른 경우)
- ✅ 느린 중앙 줌 (zoom_intensity=0.003, 매우 미세하게)
- ✅ 줌팬 효과 (매우 약하게, 위험도 분석 옵션)
- ✅ 오디오 랜덤 선택 (폴더 내 MP3 랜덤)
- ✅ MP4 파일명 = 이미지 폴더명
- ✅ 상호/전화번호 개별 폰트 크기 조절
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
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Tuple
from math import ceil

import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageFile
import tkinter.font as tkfont

ImageFile.LOAD_TRUNCATED_IMAGES = True
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# =============================================================================
# 🎛 설정 데이터 클래스 (설정값 구조화)
# =============================================================================

@dataclass
class VideoSettings:
    """영상 기본 설정"""
    width: int = 1080
    height: int = 1920
    fps: int = 30
    base_image_sec: float = 2.0
    transition_ratio: float = 0.40
    transition_min_sec: float = 0.35
    transition_max_sec: float = 1.50
    zoom_intensity: float = 0.003  # 매우 미세한 줌 (0.012 → 0.003)
    zoom_center_only: bool = True
    enable_zoompam: bool = False
    zoompam_intensity: float = 0.001  # 매우 미세한 줌팬 (0.005 → 0.001)
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
    """워터마크 설정"""
    brand_text: str = "강경 숯불바베큐"
    phone_text: str = "0507-1393-5889"
    brand_font_size: int = 46      # 상호 폰트 크기 (개별 조절)
    phone_font_size: int = 43      # 전화번호 폰트 크기 (개별 조절)
    brand_color: str = "#FFD300"
    phone_color: str = "#FFFFFF"
    margin_bottom: int = 80
    x_offset: int = 0
    y_offset: int = 0
    box_enabled: bool = True
    box_alpha: int = 125
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
    font_size: int = 11
    bold: bool = True
    margin_v: int = 40
    outline: int = 4
    shadow: int = 2
    box_mode: int = 2  # 0=없음, 1=약, 2=강
    box_back_colour: str = "&H99000000&"
    primary_colour: str = "&H00FFFFFF&"

@dataclass
class TransitionSettings:
    """전환 효과 설정"""
    style: str = "natural"  # "natural" or "fade_only"
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
    """인코딩 설정"""
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    enc_primary: str = "h264_nvenc"
    nvenc_preset: str = "p4"
    enc_fallback: str = "libx264"
    x264_preset: str = "medium"
    x264_crf: int = 20
    x264_crf_optimized: int = 22
    audio_codec: str = "aac"
    audio_bitrate: str = "160k"
    pre_jpg_quality: int = 86
    preprocess_overwrite: bool = False
    no_progress_kill_sec: int = 90
    delete_temp_after_done: bool = True
    audio_random_enabled: bool = False  # 오디오 랜덤 선택 사용
    audio_folder: str = ""  # 오디오 폴더 경로

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
        if self.video is None:
            self.video = VideoSettings()
        if self.reflection is None:
            self.reflection = ReflectionSettings()
        if self.color_random is None:
            self.color_random = ColorRandomSettings()
        if self.watermark is None:
            self.watermark = WatermarkSettings()
        if self.subtitle is None:
            self.subtitle = SubtitleSettings()
        if self.transition is None:
            self.transition = TransitionSettings()
        if self.encoding is None:
            self.encoding = EncodingSettings()
    
    def save_to_file(self, path: Path):
        """설정을 JSON 파일로 저장"""
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
        """JSON 파일에서 설정 로드"""
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
    """폴더에서 모든 오디오 파일 찾기"""
    exts = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
    out = []
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            out.append(p)
    return out

def load_font(size: int):
    candidates = [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\malgunsl.ttf",
        r"C:\Windows\Fonts\malgunbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
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
                           text=True, encoding="utf-8", errors="ignore")
        return float((p.stdout or "").strip())
    except Exception:
        return 0.0

def format_time(seconds: float) -> str:
    if seconds < 0:
        return "--:--"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def format_speed(processed_sec: float, elapsed_sec: float) -> str:
    if elapsed_sec <= 0 or processed_sec <= 0:
        return "--x"
    speed = processed_sec / elapsed_sec
    return f"{speed:.1f}x"

# =============================================================================
# 설정값 검증 시스템
# =============================================================================

def validate_settings(settings: AppSettings) -> List[str]:
    """설정값 검증 및 경고 메시지 반환"""
    warnings = []
    
    # 영상 설정 검증
    if settings.video.transition_ratio > 0.8:
        warnings.append("⚠️ 전환비율이 0.8 이상이면 영상이 어지러울 수 있습니다 (권장: 0.3~0.6)")
    elif settings.video.transition_ratio < 0.1:
        warnings.append("⚠️ 전환비율이 너무 낮아 전환 효과가 거의 보이지 않습니다")
    
    # 줌 강도 검증 (더 낮은 범위)
    if settings.video.zoom_intensity > 0.015:
        warnings.append("⚠️ 줌 강도가 너무 높으면 멀미를 유발할 수 있습니다 (권장: 0.001~0.008)")
    elif settings.video.zoom_intensity < 0.001:
        warnings.append("ℹ️ 줌 효과가 거의 없어 정적인 영상이 됩니다")
    
    if settings.video.base_image_sec < 1.0:
        warnings.append("⚠️ 이미지당 시간이 1초 미만이면 너무 빠릅니다")
    elif settings.video.base_image_sec > 5.0:
        warnings.append("ℹ️ 이미지당 시간이 길어 슬로우한 영상이 됩니다")
    
    # 줌팬 경고
    if settings.video.enable_zoompam:
        warnings.append("⚠️ [주의] 줌팬 효과는 멀미를 유발할 수 있습니다. 가급적 중앙 줌만 사용하세요.")
        if settings.video.zoompam_intensity > 0.003:
            warnings.append("⚠️ 줌팬 강도가 너무 높습니다. 0.002 이하로 낮추세요.")
    
    # 워터마크 검증
    if settings.watermark.box_enabled and settings.watermark.box_alpha < 30:
        warnings.append("ℹ️ 박스 투명도가 너무 낮아 글씨가 잘 안 보일 수 있습니다")
    
    if settings.watermark.margin_bottom < 30:
        warnings.append("⚠️ 워터마크가 화면 하단에 너무 붙어 잘릴 수 있습니다")
    
    # 자막 검증
    if settings.subtitle.enabled:
        if settings.subtitle.font_size < 8:
            warnings.append("⚠️ 자막 폰트 크기가 너무 작아 읽기 어렵습니다")
        if settings.subtitle.margin_v < 20:
            warnings.append("⚠️ 자막이 화면 하단에 너무 붙어 있습니다")
    
    return warnings

# =============================================================================
# 반사 배경 생성 + 워터마크 내장
# =============================================================================

def build_reflection_canvas(src: Image.Image, settings: AppSettings) -> Image.Image:
    """설정을 기반으로 반사 배경 생성"""
    video = settings.video
    ref = settings.reflection
    
    # 배경: 확대 + 강블러
    bg = src.convert("RGB").copy()
    bw = int(video.width * ref.strength)
    bh = int(video.height * ref.strength)
    bg = bg.resize((bw, bh), Image.LANCZOS)
    
    # 중앙 크롭
    left = (bw - video.width) // 2
    top = (bh - video.height) // 2
    bg = bg.crop((left, top, left + video.width, top + video.height))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=int(ref.blur_radius)))
    
    # 디밍
    bg = ImageEnhance.Brightness(bg).enhance(float(ref.dim))
    bg = ImageEnhance.Contrast(bg).enhance(1.03)
    
    # 그라데이션
    if ref.gradient > 0:
        grad = Image.new("L", (video.width, video.height), 0)
        gpix = grad.load()
        for y in range(video.height):
            v = int(255 * (y / (video.height - 1)) * float(ref.gradient))
            for x in range(video.width):
                gpix[x, y] = v
        overlay = Image.new("RGB", (video.width, video.height), (0, 0, 0))
        bg = Image.composite(overlay, bg, grad)
    
    # 전경
    fg = src.convert("RGB").copy()
    fg.thumbnail((video.width, video.height), Image.LANCZOS)
    
    canvas = bg.convert("RGBA")
    fg_rgba = fg.convert("RGBA")
    
    x = (video.width - fg_rgba.width) // 2
    y = (video.height - fg_rgba.height) // 2
    canvas.paste(fg_rgba, (x, y), fg_rgba)
    
    return canvas

def draw_watermark(canvas: Image.Image, settings: AppSettings) -> Image.Image:
    """설정 기반 워터마크 그리기 (개별 폰트 크기 사용)"""
    wm = settings.watermark
    video = settings.video
    
    canvas = canvas.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # 개별 폰트 크기로 로드
    brand_font = load_font(int(wm.brand_font_size))
    phone_font = load_font(int(wm.phone_font_size))
    
    # 텍스트 영역 계산
    bb1 = draw.textbbox((0, 0), wm.brand_text, font=brand_font)
    bb2 = draw.textbbox((0, 0), wm.phone_text, font=phone_font)
    bw, bh = bb1[2] - bb1[0], bb1[3] - bb1[1]
    pw, ph = bb2[2] - bb2[0], bb2[3] - bb2[1]
    
    gap = int(ph * 0.25)
    tw = max(bw, pw)
    th = bh + gap + ph
    
    # 위치 계산
    x = (video.width - tw) / 2 + wm.x_offset
    y = video.height - th - wm.margin_bottom + wm.y_offset
    
    # 박스
    if wm.box_enabled:
        pad_x, pad_y = int(wm.box_pad_x), int(wm.box_pad_y)
        box = (int(x - pad_x), int(y - pad_y), 
               int(x + tw + pad_x), int(y + th + pad_y))
        box = (max(0, box[0]), max(0, box[1]), 
               min(video.width, box[2]), min(video.height, box[3]))
        draw.rectangle(box, fill=(0, 0, 0, int(wm.box_alpha)))
    
    # 그림자/외곽선/텍스트
    def _text(xy, text, font, fill_hex):
        tx, ty = xy
        fill_rgba = hex_to_rgba(fill_hex)
        stroke_rgba = hex_to_rgba(wm.stroke_color)
        shadow_rgba = hex_to_rgba(wm.shadow_color)
        
        if wm.shadow_enabled:
            draw.text((tx + wm.shadow_offset_x, ty + wm.shadow_offset_y), 
                     text, font=font, fill=shadow_rgba)
        if wm.stroke_enabled:
            draw.text((tx, ty), text, font=font, fill=fill_rgba,
                     stroke_width=int(wm.stroke_width), stroke_fill=stroke_rgba)
        else:
            draw.text((tx, ty), text, font=font, fill=fill_rgba)
    
    _text(((video.width - bw) / 2 + wm.x_offset, y), 
          wm.brand_text, brand_font, wm.brand_color)
    _text(((video.width - pw) / 2 + wm.x_offset, y + bh + gap), 
          wm.phone_text, phone_font, wm.phone_color)
    
    out = Image.alpha_composite(canvas, overlay)
    return out

def preprocess_images(src_folder: Path, settings: AppSettings, qevt: queue.Queue, preview_only: bool = False):
    """이미지 전처리 (프리뷰 모드 지원)"""
    out_folder = src_folder / "output"
    if not preview_only:
        out_folder.mkdir(exist_ok=True)
    
    imgs = find_images(src_folder)
    if settings.transition.shuffle_images and not preview_only:
        random.shuffle(imgs)
    
    if preview_only:
        if not imgs:
            return None, None
        try:
            src = Image.open(imgs[0]).convert("RGB")
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
            src = Image.open(p).convert("RGB")
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
        f"MarginV={int(settings.margin_v)},"
        f"BorderStyle={int(border_style)},"
        f"BackColour={back}"
    )
    return style

# =============================================================================
# FFmpeg filter script (느린 중앙 줌 + 미세 줌팬)
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
    """xfade 기반 체인 (느린 중앙 줌/미세 줌팬 지원)"""
    lines = []
    
    for i in range(len(pre_imgs)):
        eq = ""
        if settings.color_random.enabled:
            sat = random.uniform(settings.color_random.sat_min, 
                                settings.color_random.sat_max)
            con = random.uniform(settings.color_random.contrast_min, 
                                settings.color_random.contrast_max)
            bri = random.uniform(settings.color_random.bright_min, 
                                settings.color_random.bright_max)
            eq = f"eq=saturation={sat:.3f}:contrast={con:.3f}:brightness={(bri-1.0):.4f},"
        
        zoom_factor = settings.video.zoom_intensity
        total_frames = int(seg * settings.video.fps)
        
        if settings.video.zoom_center_only:
            # 느린 중앙 줌 (프레임 기반, 미세하게)
            zoom = (
                f"zoompan=z='1+{zoom_factor:.6f}*on':"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:"
                f"s={settings.video.width}x{settings.video.height},"
                f"fps={settings.video.fps},"
            )
        elif settings.video.enable_zoompam:
            # 미세 줌팬 (매우 느린 움직임)
            pan_x = random.uniform(-0.03, 0.03)
            pan_y = random.uniform(-0.03, 0.03)
            
            zoom = (
                f"zoompan=z='min(1+{settings.video.zoompam_intensity:.6f}*on,1.03)':"
                f"x='iw/2-(iw/zoom/2)+{pan_x:.4f}*on':"
                f"y='ih/2-(ih/zoom/2)+{pan_y:.4f}*on':"
                f"d={total_frames}:"
                f"s={settings.video.width}x{settings.video.height},"
                f"fps={settings.video.fps},"
            )
        else:
            # 기본 줌 (기존 방식)
            zoom = (
                f"scale=iw*(1+{zoom_factor:.6f}*t):"
                f"ih*(1+{zoom_factor:.6f}*t):eval=frame,"
            )
        
        chain = (
            f"[{i}:v]"
            f"{zoom}"
            f"pad={settings.video.width}:{settings.video.height}:(ow-iw)/2:(oh-ih)/2:color={settings.video.background_fallback_color},"
            f"setsar=1,setdar={settings.video.width}/{settings.video.height},"
            f"{eq}"
            f"format=yuv420p,fps={settings.video.fps},"
            f"trim=duration={seg:.3f},setpts=PTS-STARTPTS"
            f"[v{i}];"
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
        style = build_ass_force_style(settings.subtitle).replace("'", r"\\'")
        lines.append(f"{cur}subtitles='{srt_esc}':charenc=UTF-8:force_style='{style}'[vout];")
    else:
        lines.append(f"{cur}copy[vout];")
    
    return "\n".join(lines), "[vout]"

# =============================================================================
# FFmpeg 실행 (멀티 상태바 지원)
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
        universal_newlines=True
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
# 메인 빌드 (회전마다 랜덤 셔플 + 용량 최적화 + MP4 파일명 = 폴더명)
# =============================================================================

@dataclass
class BuildReport:
    output_mp4: Path
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
    audio_used: str  # 사용된 오디오 파일명

def get_random_audio_from_folder(folder: Path) -> Optional[Path]:
    """폴더에서 랜덤하게 오디오 파일 선택"""
    if not folder or not folder.exists():
        return None
    audio_files = find_audio_files(folder)
    if not audio_files:
        return None
    return random.choice(audio_files)

def build_video_onepass(pre_imgs: list[Path], audio_path: Path, srt_path: Path | None, 
                       base_dir: Path, settings: AppSettings, qevt: queue.Queue) -> BuildReport:
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
        qevt.put(("log", f"[{_ts()}] ⚠ 오디오 길이 측정 실패"))
    
    seg = float(settings.video.base_image_sec)
    fade = clamp(seg * float(settings.video.transition_ratio), 
                settings.video.transition_min_sec, 
                settings.video.transition_max_sec)
    fade = min(fade, seg * 0.85)
    
    base_video_len = len(pre_imgs) * seg
    
    repeat_count = 1
    if audio_len > 0 and base_video_len < audio_len:
        repeat_count = ceil(audio_len / base_video_len)
        pre_imgs = build_cycle_shuffled_images(pre_imgs, repeat_count, settings.transition)
        qevt.put(("log", f"[{_ts()}] ✅ 오디오({audio_len:.2f}초)에 맞춰 이미지 {repeat_count}배 반복"))
        if settings.transition.cycle_shuffle:
            qevt.put(("log", f"[{_ts()}] 🔀 회전마다 이미지 순서 랜덤 셔플 적용"))
    
    final_video_len = len(pre_imgs) * seg
    
    qevt.put(("log", f"[{_ts()}] MP3 길이: {audio_len:.2f}초"))
    qevt.put(("log", f"[{_ts()}] 영상 길이: {final_video_len:.2f}초 (이미지 {len(pre_imgs)}장)"))
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
    
    script_text, vout_label = build_filter_script_xfade(pre_imgs, seg, fade, srt_path, settings)
    script_path = temp_folder / "filter_complex.txt"
    script_path.write_text(script_text, encoding="utf-8")
    
    # MP4 파일명 = 이미지 폴더명
    folder_name = base_dir.name
    safe_name = re.sub(r'[\\/*?:"<>|]', "_", folder_name)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    out_mp4 = output_folder / f"{safe_name}_{timestamp}.mp4"
    
    qevt.put(("log", f"[{_ts()}] 📁 출력 파일명: {out_mp4.name}"))
    
    def make_cmd(encoder: str) -> list[str]:
        cmd = [settings.encoding.ffmpeg_bin, "-hide_banner", "-y"]
        
        for img in pre_imgs:
            cmd += ["-loop", "1", "-t", f"{seg:.3f}", "-i", str(img)]
        
        cmd += ["-stream_loop", "-1", "-i", str(audio_path)]
        
        cmd += ["-filter_complex_script", str(script_path)]
        cmd += ["-map", vout_label, "-map", f"{len(pre_imgs)}:a"]
        cmd += ["-r", str(settings.video.fps)]
        
        if encoder == "h264_nvenc":
            cmd += ["-c:v", "h264_nvenc", "-preset", settings.encoding.nvenc_preset, 
                   "-pix_fmt", "yuv420p", "-cq", "22"]
        else:
            cmd += ["-c:v", "libx264", "-preset", settings.encoding.x264_preset, 
                   "-crf", str(settings.encoding.x264_crf_optimized),
                   "-pix_fmt", "yuv420p"]
        
        cmd += ["-c:a", settings.encoding.audio_codec, "-b:a", settings.encoding.audio_bitrate]
        cmd += ["-t", f"{audio_len:.3f}", str(out_mp4)]
        return cmd
    
    qevt.put(("progress_enc", "인코딩 준비 중...", 0, audio_len, "0x"))
    
    tail = ""
    for label, enc in (("NVENC", settings.encoding.enc_primary), 
                       ("x264", settings.encoding.enc_fallback)):
        qevt.put(("log", f"[{_ts()}] 실행: {label} (용량 최적화 모드)"))
        rc, tail = run_ffmpeg_with_progress(make_cmd(enc), qevt, "최종 생성", 
                                           audio_len, settings.encoding.no_progress_kill_sec)
        if rc == 0:
            file_size_mb = out_mp4.stat().st_size / (1024 * 1024) if out_mp4.exists() else 0
            qevt.put(("progress_enc", "인코딩 완료", 100, 0, "0x"))
            
            return BuildReport(
                output_mp4=out_mp4,
                preprocess_folder=base_dir / "output",
                output_folder=output_folder,
                temp_folder=temp_folder,
                audio_len=audio_len,
                video_len=final_video_len,
                seg=seg,
                fade=fade,
                elapsed=0.0,
                img_count=len(pre_imgs) // repeat_count,
                repeat_count=repeat_count,
                file_size_mb=file_size_mb,
                audio_used=audio_used
            )
        else:
            qevt.put(("log", f"[{_ts()}] ⚠ 실패: {label} (rc={rc})"))
    
    raise RuntimeError(f"최종 영상 생성 실패\n\n--- tail ---\n{tail}")

# =============================================================================
# 설정 UI 프레임 (tk.Checkbutton 사용 - 오류 수정)
# =============================================================================

class SettingsFrame(ttk.Frame):
    """설정값을 실시간으로 편집할 수 있는 UI 패널"""
    
    def __init__(self, parent, settings: AppSettings, on_change_callback=None):
        super().__init__(parent)
        self.settings = settings
        self.on_change = on_change_callback
        self.vars = {}
        
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
        if self.on_change:
            self.on_change()
    
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
        
        # tk.Checkbutton 사용 (ttk.Checkbutton -> tk.Checkbutton)
        ttk.Label(frame, text="중앙 줌 전용:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.video.zoom_center_only)
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.zoom_center_only"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", 
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        # tk.Checkbutton 사용
        ttk.Label(frame, text="⚠️ 줌팬 사용:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.video.enable_zoompam)
        var.trace_add("write", self.on_setting_changed)
        self.vars["video.enable_zoompam"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
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
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
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
        btn = ttk.Button(btn_frame, text="선택", 
                        command=lambda: self.choose_color(var, color_preview))
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
        btn = ttk.Button(btn_frame, text="선택", 
                        command=lambda: self.choose_color(var, color_preview))
        btn.pack(side="left")
        row += 1
        
        ttk.Label(scrollable_frame, text="하단 여백:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.watermark.margin_bottom)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.margin_bottom"] = var
        ttk.Spinbox(scrollable_frame, from_=20, to=300, increment=5, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        # tk.Checkbutton 사용
        ttk.Label(scrollable_frame, text="배경 박스 사용:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.watermark.box_enabled)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.box_enabled"] = var
        tk.Checkbutton(scrollable_frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(scrollable_frame, text="박스 투명도:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.IntVar(value=self.settings.watermark.box_alpha)
        var.trace_add("write", self.on_setting_changed)
        self.vars["watermark.box_alpha"] = var
        ttk.Scale(scrollable_frame, from_=0, to=255, variable=var, orient="horizontal", length=150).grid(row=row, column=1, padx=5, pady=2)
        row += 1
    
    def choose_color(self, var, preview_label):
        color = colorchooser.askcolor(var.get())[1]
        if color:
            var.set(color)
            preview_label.config(bg=color)
    
    def create_subtitle_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="자막")
        
        row = 0
        # tk.Checkbutton 사용
        ttk.Label(frame, text="자막 사용:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.subtitle.enabled)
        var.trace_add("write", self.on_setting_changed)
        self.vars["subtitle.enabled"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
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
        
        # tk.Checkbutton 사용
        ttk.Label(frame, text="굵게:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.subtitle.bold)
        var.trace_add("write", self.on_setting_changed)
        self.vars["subtitle.bold"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
    
    def create_transition_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="전환효과")
        
        row = 0
        # tk.Checkbutton 사용
        ttk.Label(frame, text="첫 회전 랜덤:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.transition.shuffle_images)
        var.trace_add("write", self.on_setting_changed)
        self.vars["transition.shuffle_images"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        # tk.Checkbutton 사용
        ttk.Label(frame, text="회전마다 랜덤:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.transition.cycle_shuffle)
        var.trace_add("write", self.on_setting_changed)
        self.vars["transition.cycle_shuffle"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        # tk.Checkbutton 사용
        ttk.Label(frame, text="역순 재생:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.transition.reverse_cycle)
        var.trace_add("write", self.on_setting_changed)
        self.vars["transition.reverse_cycle"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="전환 스타일:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.StringVar(value=self.settings.transition.style)
        var.trace_add("write", self.on_setting_changed)
        self.vars["transition.style"] = var
        ttk.Combobox(frame, textvariable=var, values=["natural", "fade_only"], width=12).grid(row=row, column=1, padx=5, pady=2)
        row += 1
        
        # tk.Checkbutton 사용
        ttk.Label(frame, text="랜덤 색보정:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.color_random.enabled)
        var.trace_add("write", self.on_setting_changed)
        self.vars["color_random.enabled"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
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
        
        # tk.Checkbutton 사용
        ttk.Label(frame, text="오디오 랜덤:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.encoding.audio_random_enabled)
        var.trace_add("write", self.on_setting_changed)
        self.vars["encoding.audio_random_enabled"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="오디오 폴더:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        audio_folder_var = tk.StringVar(value=self.settings.encoding.audio_folder)
        audio_folder_var.trace_add("write", self.on_setting_changed)
        self.vars["encoding.audio_folder"] = audio_folder_var
        ttk.Entry(frame, textvariable=audio_folder_var, width=20).grid(row=row, column=1, padx=5, pady=2)
        ttk.Button(frame, text="찾기", command=self.select_audio_folder).grid(row=row, column=2, padx=5, pady=2)
        row += 1
        
        # tk.Checkbutton 사용
        ttk.Label(frame, text="TEMP 삭제:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.BooleanVar(value=self.settings.encoding.delete_temp_after_done)
        var.trace_add("write", self.on_setting_changed)
        self.vars["encoding.delete_temp_after_done"] = var
        tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white",
                      selectcolor="#2d6cdf", activebackground="#1a1e2a",
                      activeforeground="white").grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        ttk.Label(frame, text="용량 최적화:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(frame, text="CRF 22 / 오디오 160k (약 10%↓)", 
                 foreground="#4caf50").grid(row=row, column=1, sticky="w", padx=5, pady=2)
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
            messagebox.showinfo("JSON 편집", 
                              "설정 파일이 열렸습니다.\n수정 후 저장하고 닫아주세요.\n\n"
                              "적용하려면 '프리셋 불러오기'를 클릭하세요.")
        except Exception as e:
            messagebox.showerror("오류", f"파일을 열 수 없습니다: {e}")
    
    def save_preset(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="프리셋 저장"
        )
        if filename:
            self.settings.save_to_file(Path(filename))
            messagebox.showinfo("완료", "프리셋이 저장되었습니다.")
    
    def load_preset(self):
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="프리셋 불러오기"
        )
        if filename:
            try:
                new_settings = AppSettings.load_from_file(Path(filename))
                self.settings = new_settings
                self.update_vars_from_settings()
                messagebox.showinfo("완료", "프리셋이 적용되었습니다.")
                if self.on_change:
                    self.on_change()
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
        return self.settings

# =============================================================================
# 멀티 진행바 컴포넌트
# =============================================================================

class MultiProgressBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#0f1115")
        
        pre_frame = tk.Frame(self, bg="#0f1115")
        pre_frame.pack(fill="x", pady=(0, 5))
        
        tk.Label(pre_frame, text="📸 전처리:", fg="#c7d0db", bg="#0f1115",
                 font=("Malgun Gothic", 9)).pack(side="left", padx=(0, 10))
        
        self.pre_bar = ttk.Progressbar(pre_frame, orient="horizontal", 
                                       mode="determinate", length=200)
        self.pre_bar.pack(side="left", fill="x", expand=True)
        
        self.pre_label = tk.Label(pre_frame, text="0/0 (0%)", fg="#9aa4b2", 
                                  bg="#0f1115", font=("Malgun Gothic", 9), width=15)
        self.pre_label.pack(side="right", padx=(5, 0))
        
        enc_frame = tk.Frame(self, bg="#0f1115")
        enc_frame.pack(fill="x", pady=(0, 5))
        
        tk.Label(enc_frame, text="🎬 인코딩:", fg="#c7d0db", bg="#0f1115",
                 font=("Malgun Gothic", 9)).pack(side="left", padx=(0, 10))
        
        self.enc_bar = ttk.Progressbar(enc_frame, orient="horizontal",
                                       mode="determinate", length=200)
        self.enc_bar.pack(side="left", fill="x", expand=True)
        
        self.enc_label = tk.Label(enc_frame, text="0%", fg="#9aa4b2",
                                  bg="#0f1115", font=("Malgun Gothic", 9), width=15)
        self.enc_label.pack(side="right", padx=(5, 0))
        
        info_frame = tk.Frame(self, bg="#0f1115")
        info_frame.pack(fill="x", pady=(5, 0))
        
        self.eta_label = tk.Label(info_frame, text="⏱️ 예상: --:--", 
                                   fg="#c7d0db", bg="#0f1115", font=("Malgun Gothic", 9))
        self.eta_label.pack(side="left", padx=(0, 15))
        
        self.speed_label = tk.Label(info_frame, text="⚡ 속도: --x", 
                                     fg="#c7d0db", bg="#0f1115", font=("Malgun Gothic", 9))
        self.speed_label.pack(side="left", padx=(0, 15))
        
        self.remain_label = tk.Label(info_frame, text="📊 남음: --", 
                                      fg="#c7d0db", bg="#0f1115", font=("Malgun Gothic", 9))
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
# 메인 UI (자동 설정 저장/불러오기 포함)
# =============================================================================

class CineUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("시네마틱 숏폼 제작기 v5.2")
        self.root.geometry("1400x1290")
        self.root.configure(bg="#0f1115")
        
        # 설정 파일 경로
        self.config_file = Path("settings.json")
        
        # 설정 객체
        self.settings = AppSettings()
        
        # 자동 설정 불러오기
        self.load_last_settings()
        
        self.setup_styles()
        self.create_widgets()
        
        self.qevt = queue.Queue()
        self.worker = None
        self.preview_image = None
        self.preview_photo = None
        
        self.img_dir = None
        self.audio_path = None
        self.srt_path = None
        
        # 종료 이벤트 바인딩
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.root.after(120, self.poll)
    
    def load_last_settings(self):
        """프로그램 시작 시 마지막 설정 자동 불러오기"""
        if self.config_file.exists():
            try:
                self.settings = AppSettings.load_from_file(self.config_file)
                safe_print(f"✅ 마지막 설정을 불러왔습니다: {self.config_file}")
            except Exception as e:
                safe_print(f"⚠️ 설정 불러오기 실패: {e}")
    
    def save_last_settings(self):
        """프로그램 종료 시 자동 저장"""
        try:
            self.settings.save_to_file(self.config_file)
            safe_print(f"✅ 설정이 저장되었습니다: {self.config_file}")
        except Exception as e:
            safe_print(f"⚠️ 설정 저장 실패: {e}")
    
    def on_closing(self):
        """종료 이벤트 처리"""
        self.save_last_settings()
        self.root.destroy()
    
    def setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        
        style.configure("TNotebook", background="#1a1e2a")
        style.configure("TNotebook.Tab", background="#2a3145", foreground="#ffffff", 
                       padding=[10, 2])
        style.map("TNotebook.Tab", background=[("selected", "#3b4a6b")])
        
        style.configure("TFrame", background="#1a1e2a")
        style.configure("TLabel", background="#1a1e2a", foreground="#ffffff")
        style.configure("TButton", background="#2d6cdf", foreground="#ffffff",
                       borderwidth=0, focuscolor="none")
        style.map("TButton", background=[("active", "#3b7af0")])
        
        style.configure("TProgressbar", thickness=18, background="#2d6cdf")
    
    def create_widgets(self):
        header = tk.Frame(self.root, bg="#0f1115")
        header.pack(fill="x", padx=16, pady=(14, 10))
        
        tk.Label(header, text="시네마틱 숏폼 제작기 v5.2", fg="#ffffff", bg="#0f1115",
                 font=("Malgun Gothic", 18, "bold")).pack(anchor="w")
        tk.Label(header, text="1080x1920 / 반사배경 / 워터마크 / 자막 / 느린 중앙 줌 / 랜덤 오디오",
                 fg="#9aa4b2", bg="#0f1115", font=("Malgun Gothic", 10)).pack(anchor="w", pady=(6, 0))
        
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
        
        tk.Label(file_frame, text="📁 파일 선택", fg="#ffffff", bg="#1a1e2a",
                 font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        img_frame = tk.Frame(file_frame, bg="#1a1e2a")
        img_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(img_frame, text="이미지 폴더:", fg="#c7d0db", bg="#1a1e2a", width=12).pack(side="left")
        self.img_dir_label = tk.Label(img_frame, text="선택 안됨", fg="#9aa4b2", bg="#1a1e2a",
                                      anchor="w", width=25)
        self.img_dir_label.pack(side="left", fill="x", expand=True)
        ttk.Button(img_frame, text="찾아보기", command=self.select_img_dir, width=10).pack(side="right")
        
        audio_frame = tk.Frame(file_frame, bg="#1a1e2a")
        audio_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(audio_frame, text="오디오 파일:", fg="#c7d0db", bg="#1a1e2a", width=12).pack(side="left")
        self.audio_label = tk.Label(audio_frame, text="선택 안됨", fg="#9aa4b2", bg="#1a1e2a",
                                    anchor="w", width=25)
        self.audio_label.pack(side="left", fill="x", expand=True)
        ttk.Button(audio_frame, text="찾아보기", command=self.select_audio, width=10).pack(side="right")
        
        srt_frame = tk.Frame(file_frame, bg="#1a1e2a")
        srt_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(srt_frame, text="자막 파일:", fg="#c7d0db", bg="#1a1e2a", width=12).pack(side="left")
        self.srt_label = tk.Label(srt_frame, text="선택 안됨", fg="#9aa4b2", bg="#1a1e2a",
                                  anchor="w", width=25)
        self.srt_label.pack(side="left", fill="x", expand=True)
        btn_frame = tk.Frame(srt_frame, bg="#1a1e2a")
        btn_frame.pack(side="right")
        
        ttk.Button(btn_frame, text="오디오+자막", command=self.select_audio_srt_pair, 
                  width=10).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="찾아보기", command=self.select_srt, width=8).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="초기화", command=self.clear_srt, width=6).pack(side="left")
        
        self.settings_frame = SettingsFrame(left_panel, self.settings, on_change_callback=self.update_preview)
        self.settings_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.warning_label = tk.Label(left_panel, text="", fg="#ffaa00", bg="#0f1115",
                                      font=("Malgun Gothic", 9), wraplength=400, justify="left")
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
        
        # 우측 패널
        preview_frame = tk.Frame(right_panel, bg="#1a1e2a", relief="flat", bd=1)
        preview_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        tk.Label(preview_frame, text="🖼️ 프리뷰 (첫 번째 이미지)", fg="#ffffff", bg="#1a1e2a",
                 font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.preview_canvas = tk.Canvas(preview_frame, bg="#121622", width=360, height=640,
                                        highlightthickness=0)
        self.preview_canvas.pack(pady=10, padx=10)
        
        self.preview_info = tk.Label(preview_frame, text="이미지 폴더를 선택하세요", 
                                     fg="#9aa4b2", bg="#1a1e2a", font=("Malgun Gothic", 9))
        self.preview_info.pack(pady=(0, 10))
        
        self.progress_bars = MultiProgressBar(right_panel)
        self.progress_bars.pack(fill="x", pady=(0, 10))
        
        info_frame = tk.Frame(right_panel, bg="#1a1e2a", relief="flat", bd=1)
        info_frame.pack(fill="x", pady=(0, 10))
        
        tk.Label(info_frame, text="📊 파일 정보", fg="#ffffff", bg="#1a1e2a",
                 font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.info_text = tk.Label(info_frame, text="이미지: 0장\n오디오: -\n예상 영상 길이: -",
                                  fg="#c7d0db", bg="#1a1e2a", font=("Malgun Gothic", 10),
                                  justify="left")
        self.info_text.pack(anchor="w", padx=10, pady=(0, 10))
        
        log_frame = tk.Frame(right_panel, bg="#1a1e2a", relief="flat", bd=1)
        log_frame.pack(fill="both", expand=True)
        
        tk.Label(log_frame, text="📋 진행 로그", fg="#ffffff", bg="#1a1e2a",
                 font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.txt = ScrolledText(log_frame, wrap="word", height=8, bg="#121622", fg="#dbe5f0",
                                insertbackground="#dbe5f0", relief="flat", font=("Consolas", 9))
        self.txt.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt.insert("1.0", "준비 완료.\n")
        self.txt.config(state="disabled")
        
        progress_frame = tk.Frame(right_panel, bg="#0f1115")
        progress_frame.pack(fill="x", pady=(5, 0))
        
        self.stage_var = tk.StringVar(value="대기")
        self.detail_var = tk.StringVar(value="")
        
        tk.Label(progress_frame, textvariable=self.stage_var, fg="#ffffff", bg="#0f1115",
                 font=("Malgun Gothic", 11, "bold")).pack(anchor="w")
        tk.Label(progress_frame, textvariable=self.detail_var, fg="#c7d0db", bg="#0f1115",
                 font=("Malgun Gothic", 9)).pack(anchor="w", pady=(2, 0))
    
    def select_img_dir(self):
        folder = filedialog.askdirectory(title="이미지 폴더 선택")
        if folder:
            self.img_dir = Path(folder)
            self.img_dir_label.config(text=str(self.img_dir)[:30] + "...")
            self.update_file_info()
            self.update_preview()
    
    def select_audio(self):
        file = filedialog.askopenfilename(
            title="오디오 파일 선택",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac"), ("All files", "*.*")]
        )
        if file:
            self.audio_path = Path(file)
            self.audio_label.config(text=self.audio_path.name)
            self.update_file_info()
    
    def select_srt(self):
        file = filedialog.askopenfilename(
            title="자막 SRT 선택",
            filetypes=[("SubRip", "*.srt"), ("All files", "*.*")]
        )
        if file:
            self.srt_path = Path(file)
            self.srt_label.config(text=self.srt_path.name)
    
    def select_audio_srt_pair(self):
        audio_file = filedialog.askopenfilename(
            title="오디오 파일 선택 (자막은 자동 찾기)",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac"), ("All files", "*.*")]
        )
        if not audio_file:
            return
        
        audio_path = Path(audio_file)
        self.audio_path = audio_path
        self.audio_label.config(text=audio_path.name)
        
        srt_candidates = [
            audio_path.with_suffix(".srt"),
            audio_path.parent / f"{audio_path.stem}.srt"
        ]
        
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
    
    def clear_srt(self):
        self.srt_path = None
        self.srt_label.config(text="선택 안됨")
    
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
            if not messagebox.askyesno("설정 경고", 
                                      "\n".join(warnings) + "\n\n계속 진행하시겠습니까?"):
                return
        
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
            report = build_video_onepass(pre_imgs, audio, srt, base_dir=img_dir, 
                                        settings=self.settings, qevt=self.qevt)
            report.elapsed = time.time() - t0
            
            if self.settings.encoding.delete_temp_after_done:
                try:
                    if report.temp_folder.exists():
                        shutil.rmtree(report.temp_folder, ignore_errors=True)
                except Exception:
                    pass
            
            self.qevt.put(("done", report))
        except Exception as e:
            self.qevt.put(("error", str(e)))
    
    def open_folder(self, folder: Path):
        try:
            if os.name == "nt":
                os.startfile(str(folder.resolve()))
        except Exception:
            pass
    
    def _report_popup(self, report: BuildReport):
        pop = tk.Toplevel(self.root)
        pop.title("작업 리포트")
        pop.geometry("720x420")
        pop.configure(bg="#0f1115")
        pop.attributes("-topmost", True)
        
        tk.Label(pop, text="✅ 작업 완료", fg="#ffffff", bg="#0f1115",
                 font=("Malgun Gothic", 14, "bold")).pack(anchor="w", padx=14, pady=(12, 0))
        
        text = tk.Text(pop, wrap="word", height=14, bg="#121622", fg="#dbe5f0",
                       relief="flat", insertbackground="#dbe5f0", font=("Consolas", 10))
        text.pack(fill="both", expand=True, padx=14, pady=12)
        
        msg = (
            f"📁 최종 파일: {report.output_mp4}\n"
            f"📦 파일 크기: {report.file_size_mb:.2f} MB\n"
            f"🎵 사용 오디오: {Path(report.audio_used).name}\n\n"
            f"📊 통계:\n"
            f"  - 이미지 수: {report.img_count}장\n"
            f"  - 반복 횟수: {report.repeat_count}회\n"
            f"  - 오디오 길이: {report.audio_len:.2f}초\n"
            f"  - 영상 길이: {report.video_len:.2f}초\n"
            f"  - 이미지당 표시: {report.seg:.2f}초\n"
            f"  - 전환시간: {report.fade:.2f}초\n\n"
            f"⏱️ 총 소요 시간: {report.elapsed:.2f}초\n"
            f"🗑️ TEMP 정리: {'삭제 완료' if self.settings.encoding.delete_temp_after_done else '유지'}\n\n"
            f"📂 출력 폴더: {report.output_folder}"
        )
        text.insert("1.0", msg)
        text.config(state="disabled")
        
        btn_frame = tk.Frame(pop, bg="#0f1115")
        btn_frame.pack(fill="x", padx=14, pady=(0, 14))
        
        tk.Button(btn_frame, text="폴더 열기", command=lambda: self.open_folder(report.output_folder),
                 bg="#2d6cdf", fg="white", activebackground="#3b7af0", 
                 relief="flat", padx=12, pady=6).pack(side="left", padx=5)
        
        tk.Button(btn_frame, text="확인", command=pop.destroy,
                 bg="#4a5568", fg="white", activebackground="#5f6b80",
                 relief="flat", padx=12, pady=6).pack(side="right")
        
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
                    _, report = evt
                    self.log("✅ 작업 완료.")
                    self.progress_bars.update_encode(100, 0, "0x")
                    self.set_progress("완료", "작업 완료")
                    self.btn_start.config(state="normal")
                    
                    self.open_folder(report.preprocess_folder)
                    self.open_folder(report.output_folder)
                    
                    self._report_popup(report)
                    
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

def main():
    app = CineUI()
    app.run()

if __name__ == "__main__":
    main()