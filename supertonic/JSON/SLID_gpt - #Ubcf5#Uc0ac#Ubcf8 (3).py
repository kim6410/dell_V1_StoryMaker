"""
SLID_gpt_STABLE_v3_14_CINEMATIC_PRO_MOBILE.py
------------------------------------------------------------
목표(확정)
- 1080x1920(9:16) 고정: 쇼츠/릴스/숏폼 전용
- "잘림 없이 전체 노출" + 여백은 '물에 비친 듯한 강한 반사(블러) 배경'으로 처리
- 이미지 순서/전환 효과/색보정은 매 실행마다 랜덤(자연스럽고 고급스럽게)
- 전환 비율 기반 계산 모드: 전환시간 = (이미지 표시시간) * TRANSITION_RATIO
- 워터마크: 전처리 이미지에 내장(상호/전화 하단)
- 자막(SRT): 폰트 크기/위치/효과(외곽선/그림자/박스) 컨트롤 센터에서 조절
- UI: 깔끔한 다크톤, 진행상태 자세히, 완료 팝업은 10초 무조작이면 자동 닫힘
- TEMP 폴더는 작업 끝나면 자동 삭제

주의
- 이 스크립트는 Windows 환경(한글 경로)에서도 FFmpeg 출력 파싱이 깨지지 않도록
  subprocess 출력 디코딩을 utf-8 / errors=ignore로 고정합니다.
"""

import os
import re
import random
import time
import shutil
import subprocess
import threading
import queue
from pathlib import Path
from dataclasses import dataclass

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# =============================================================================
# 🎛 컨트롤 센터(관리자 설정) - 여기만 바꾸면 됩니다
# =============================================================================

# -----------------------------------------------------------------------------
# [1] 영상 기본 설정 (쇼츠/릴스 고정)
# -----------------------------------------------------------------------------
VIDEO_W = 1080
VIDEO_H = 1920
FPS = 30  # 25도 가능하지만 숏폼은 30이 무난

BACKGROUND_FALLBACK_COLOR = "black"  # 반사 배경 생성 실패 시 패드 색

# -----------------------------------------------------------------------------
# [2] 슬라이드 속도 / 전환(전환 비율 기반 계산 모드)
# -----------------------------------------------------------------------------
# BASE_IMAGE_SEC
# - 1장당 '전체 시간' 입니다. (정지 구간 + 전환 구간 포함)
# - 기본값 2.0초 => 숏폼 템포에 잘 맞습니다.
BASE_IMAGE_SEC = 2.0

# TRANSITION_RATIO
# - 전환시간 = BASE_IMAGE_SEC * TRANSITION_RATIO
# - 예: 2.0 * 0.4 = 0.8초 전환(부드럽고 자연스러움)
TRANSITION_RATIO = 0.40  # ✅ 오빠 요청: 0.4 기본값

# 전환시간 상한/하한 안전장치 (너무 크면 영상이 늘어지거나 xfade가 꼬입니다)
TRANSITION_MIN_SEC = 0.35
TRANSITION_MAX_SEC = 1.50


# ▣ 줌 강도(초당 확대 비율)
# - 0.008~0.020 권장(값이 클수록 더 많이 확대)
# - 너무 크면 어지럽고 촌스러워집니다(숏폼은 0.010~0.014 추천)
ZOOM_INTENSITY = 0.012
# -----------------------------------------------------------------------------
# [3] "잘림 없는 전체 노출" + 강한 물반사 배경
# -----------------------------------------------------------------------------
# 반사 배경 강도(1.0~2.0 권장)
REFLECT_STRENGTH = 1.60

# 반사 배경 블러 (크면 더 몽환적 / 성능은 조금 더 사용)
REFLECT_BLUR_RADIUS = 55

# 반사 배경 어둡기(0.6~0.9 권장) - 값이 작을수록 더 어둡게
REFLECT_DIM = 0.72

# 반사 느낌(하단) 더 강하게 만드는 그라데이션 강도 (0~1)
REFLECT_GRADIENT = 0.75

# -----------------------------------------------------------------------------
# [4] 워터마크(전처리 이미지에 내장) - 상호/전화/카드 위치
# -----------------------------------------------------------------------------
WM_BRAND_TEXT = "강경 숯불바베큐"
WM_PHONE_TEXT = "0507-1393-5889"

# 텍스트 크기(기본 폰트 기준)
WM_FONT_BASE = 38          # 기본 폰트 크기
WM_BRAND_PLUS_PX = 8       # 상호 +4px
WM_PHONE_PLUS_PX = 5       # 전화 +2px

# 색상
WM_BRAND_COLOR = (255, 211, 0, 255)   # 노랑(상호)
WM_PHONE_COLOR = (255, 255, 255, 255) # 흰색(전화)

# 위치(하단에서 띄우는 값)
WM_MARGIN_BOTTOM_PX = 80
WM_X_OFFSET_PX = 0
WM_Y_OFFSET_PX = 0

# 음영 카드(박스)
WM_BOX_ENABLE = True
WM_BOX_ALPHA = 125
WM_BOX_PAD_X = 20
WM_BOX_PAD_Y = int(20 * 1.20)  # ✅ 20% 크게(오빠 요구 유지)

# 글자 진한 음영(외곽선 + 그림자)
WM_STROKE_ENABLE = True
WM_STROKE_WIDTH = 4
WM_STROKE_COLOR = (0, 0, 0, 255)

WM_SHADOW_ENABLE = True
WM_SHADOW_COLOR = (0, 0, 0, 235)
WM_SHADOW_OFFSET = (2, 2)

# 전처리 저장 품질(용량 절감)
PRE_JPG_QUALITY = 86
PREPROCESS_OVERWRITE = False

# -----------------------------------------------------------------------------
# [5] 자막(SRT) - 폰트 크기/위치/효과 선택 (컨트롤 센터에서 조절)
# -----------------------------------------------------------------------------
SUB_ENABLE_DEFAULT = True

# 폰트
SUB_FONT_NAME = "Malgun Gothic"  # Windows 기본: 맑은 고딕
SUB_FONT_SIZE = 11               # 모바일에서 읽히는 기본 크기
SUB_BOLD = 1                     # 1=굵게, 0=보통

# 위치: MarginV (아래쪽 여백 픽셀)
# - 값이 클수록 자막이 위로 올라옵니다.
SUB_MARGIN_V = 40

# 외곽선/그림자(가독성 핵심)
SUB_OUTLINE = 4
SUB_SHADOW = 2

# 자막 박스(반투명) 효과(선택)
# 0=없음, 1=약하게, 2=강하게
SUB_BOX_MODE = 2

# 박스 색/투명도(ASS 스타일 기준: BackColour + BorderStyle=3)
# - BackColour는 &HAABBGGRR& (AA=투명도, 00 불투명 / FF 완전 투명)
# - 아래는 "반투명 검정" (대략 65%)
SUB_BOX_BACK_COLOUR = "&H99000000&"

# 자막 글자 색(흰색 추천)
SUB_PRIMARY_COLOUR = "&H00FFFFFF&"

# -----------------------------------------------------------------------------
# [6] 랜덤 연출 옵션
# -----------------------------------------------------------------------------
# 이미지 순서 랜덤 섞기
RANDOM_SHUFFLE_IMAGES = True

# 미세 색보정 랜덤(너무 과하면 촌스러우니 미세 범위)
COLOR_RANDOM_ENABLE = True
SAT_RANGE = (0.98, 1.06)
CONTRAST_RANGE = (0.98, 1.06)
BRIGHT_RANGE = (0.96, 1.04)

# 전환 효과(자연스럽고 고급스러운 것 위주)
# ⚠ xfade transition 이름이 설치된 FFmpeg에 따라 다를 수 있어서, "안전 리스트"로 구성
XFADE_TRANSITIONS_NATURAL = [
    "fade",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    "circleopen", "circleclose",
    "horzopen", "horzclose", "vertopen", "vertclose",
]

# 전환 효과 선택 방식: "natural" 또는 "fade_only"
TRANSITION_STYLE = "natural"

# -----------------------------------------------------------------------------
# [7] FFmpeg / 인코딩 / 파일명
# -----------------------------------------------------------------------------
FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"

# NVENC 우선, 실패 시 x264로 폴백
ENC_PRIMARY = "h264_nvenc"
NVENC_PRESET = "p4"
ENC_FALLBACK = "libx264"
X264_PRESET = "medium"
X264_CRF = 20

AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"

OUTPUT_FILENAME = "slideshow_mobile_cinematic.mp4"

# 진행 신호가 일정 시간 없으면 강제 종료(FFmpeg 멈춤 방지)
NO_PROGRESS_KILL_SEC = 90

# 작업 종료 시 TEMP 폴더 삭제
DELETE_TEMP_AFTER_DONE = True

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
    """요구사항:
    - '스크린샷' 제거
    - 'KakaoTalk_' 제거
    """
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


def load_font(size: int):
    """Windows에서 한글 폰트가 없으면 기본 폰트로 폴백"""
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


def escape_subtitles_path_for_windows(p: Path) -> str:
    """FFmpeg subtitles 필터에서 Windows 경로 안전 처리"""
    s = str(p).replace("\\", "/")
    # D:/ -> D\:/ 형태로
    s = re.sub(r"^([A-Za-z]):/", r"\1\\:/", s)
    # 작은따옴표 escape
    s = s.replace("'", r"\\'")
    return s


def probe_audio_duration(audio_path: Path) -> float:
    try:
        cmd = [
            FFPROBE_BIN, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="ignore")
        return float((p.stdout or "").strip())
    except Exception:
        return 0.0


# =============================================================================
# 반사 배경 생성 + 워터마크 내장(전처리)
# =============================================================================

def build_reflection_canvas(src: Image.Image) -> Image.Image:
    """
    핵심:
    - 잘림 없는 전체 노출: 중앙(원본)을 "decrease" 방식으로 맞춤
    - 여백 배경은 원본을 크게 확대한 뒤 강한 블러 + 디밍 + 그라데이션으로 '물반사' 느낌
    """
    # 1) 배경: 확대 + 강블러
    bg = src.convert("RGB").copy()
    # 강하게 확대(REFLECT_STRENGTH)
    bw = int(VIDEO_W * REFLECT_STRENGTH)
    bh = int(VIDEO_H * REFLECT_STRENGTH)
    bg = bg.resize((bw, bh), Image.LANCZOS)
    # 중앙 크롭(1080x1920)
    left = (bw - VIDEO_W) // 2
    top = (bh - VIDEO_H) // 2
    bg = bg.crop((left, top, left + VIDEO_W, top + VIDEO_H))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=int(REFLECT_BLUR_RADIUS)))

    # 2) 디밍(어둡게) + 약간의 콘트라스트
    bg = ImageEnhance.Brightness(bg).enhance(float(REFLECT_DIM))
    bg = ImageEnhance.Contrast(bg).enhance(1.03)

    # 3) 하단 반사 느낌 그라데이션(위->아래 더 어둡게 + 살짝 번짐)
    if REFLECT_GRADIENT > 0:
        grad = Image.new("L", (VIDEO_W, VIDEO_H), 0)
        gpix = grad.load()
        for y in range(VIDEO_H):
            # 아래쪽으로 갈수록 더 진하게(0~255)
            v = int(255 * (y / (VIDEO_H - 1)) * float(REFLECT_GRADIENT))
            for x in range(VIDEO_W):
                gpix[x, y] = v
        overlay = Image.new("RGB", (VIDEO_W, VIDEO_H), (0, 0, 0))
        bg = Image.composite(overlay, bg, grad)

    # 4) 전경(원본)을 잘림 없이 전체 노출로 리사이즈
    fg = src.convert("RGB").copy()
    fg.thumbnail((VIDEO_W, VIDEO_H), Image.LANCZOS)

    canvas = bg.convert("RGBA")
    fg_rgba = fg.convert("RGBA")

    x = (VIDEO_W - fg_rgba.width) // 2
    y = (VIDEO_H - fg_rgba.height) // 2
    canvas.paste(fg_rgba, (x, y), fg_rgba)

    return canvas


def draw_watermark(canvas: Image.Image) -> Image.Image:
    """요구사항: 하단에 상호/전화. 상호 노랑 +4px, 전화 흰 +2px, 진한 음영"""
    canvas = canvas.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    brand_font = load_font(int(WM_FONT_BASE + WM_BRAND_PLUS_PX))
    phone_font = load_font(int(WM_FONT_BASE + WM_PHONE_PLUS_PX))

    bb1 = draw.textbbox((0, 0), WM_BRAND_TEXT, font=brand_font)
    bb2 = draw.textbbox((0, 0), WM_PHONE_TEXT, font=phone_font)
    bw, bh = bb1[2] - bb1[0], bb1[3] - bb1[1]
    pw, ph = bb2[2] - bb2[0], bb2[3] - bb2[1]

    gap = int(ph * 0.25)
    tw = max(bw, pw)
    th = bh + gap + ph

    x = (VIDEO_W - tw) / 2 + WM_X_OFFSET_PX
    y = VIDEO_H - th - WM_MARGIN_BOTTOM_PX + WM_Y_OFFSET_PX

    if WM_BOX_ENABLE:
        pad_x, pad_y = int(WM_BOX_PAD_X), int(WM_BOX_PAD_Y)
        box = (int(x - pad_x), int(y - pad_y), int(x + tw + pad_x), int(y + th + pad_y))
        box = (max(0, box[0]), max(0, box[1]), min(VIDEO_W, box[2]), min(VIDEO_H, box[3]))
        draw.rectangle(box, fill=(0, 0, 0, int(WM_BOX_ALPHA)))

    def _text(xy, text, font, fill):
        tx, ty = xy
        if WM_SHADOW_ENABLE:
            sx, sy = WM_SHADOW_OFFSET
            draw.text((tx + sx, ty + sy), text, font=font, fill=WM_SHADOW_COLOR)
        if WM_STROKE_ENABLE:
            draw.text((tx, ty), text, font=font, fill=fill,
                      stroke_width=int(WM_STROKE_WIDTH), stroke_fill=WM_STROKE_COLOR)
        else:
            draw.text((tx, ty), text, font=font, fill=fill)

    _text(((VIDEO_W - bw) / 2 + WM_X_OFFSET_PX, y), WM_BRAND_TEXT, brand_font, WM_BRAND_COLOR)
    _text(((VIDEO_W - pw) / 2 + WM_X_OFFSET_PX, y + bh + gap), WM_PHONE_TEXT, phone_font, WM_PHONE_COLOR)

    out = Image.alpha_composite(canvas, overlay)
    return out


def preprocess_images(src_folder: Path, qevt: queue.Queue):
    """
    - src_folder/output 에 워터마크+반사 배경 적용된 jpg 저장
    - 파일명 규칙 적용
    - 이미지 순서는 랜덤 shuffle (옵션)
    """
    out_folder = src_folder / "output"
    out_folder.mkdir(exist_ok=True)

    imgs = find_images(src_folder)
    if RANDOM_SHUFFLE_IMAGES:
        random.shuffle(imgs)

    qevt.put(("log", f"[{_ts()}] 원본 이미지 {len(imgs)}장"))
    qevt.put(("log", f"[{_ts()}] ✅ 전처리 이미지 저장 위치: {out_folder}"))
    qevt.put(("log", f"[{_ts()}] 워터마크: 이미지에 내장 + 반사 배경(강함)"))

    ok, skip = 0, 0
    for i, p in enumerate(imgs, start=1):
        qevt.put(("progress", "전처리", f"{i}/{len(imgs)} 처리 중", (i / max(1, len(imgs))) * 20.0))

        new_stem = normalize_output_stem(p.stem)
        out_path = out_folder / f"{new_stem}.jpg"

        if out_path.exists() and not PREPROCESS_OVERWRITE:
            try:
                if out_path.stat().st_mtime >= p.stat().st_mtime:
                    ok += 1
                    continue
            except Exception:
                pass

        try:
            src = Image.open(p).convert("RGB")
            canvas = build_reflection_canvas(src)
            canvas = draw_watermark(canvas)
            canvas.convert("RGB").save(out_path, quality=int(PRE_JPG_QUALITY), optimize=True)
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
# SRT 정리 + 스타일(force_style)
# =============================================================================

def clean_srt(original_srt: Path, out_srt: Path) -> Path:
    """SRT에 태그/주석이 섞여 들어오면 subtitles 필터가 깨질 수 있어 정리"""
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
    raw = re.sub(r"<[^>]+>", "", raw)  # 혹시 모를 태그 제거
    raw = re.sub(r"\n{3,}", "\n\n", raw).strip() + "\n"

    out_srt.write_text(raw, encoding="utf-8")
    return out_srt


def build_ass_force_style() -> str:
    """
    subtitles 필터의 force_style은 ASS 스타일 문자열입니다.
    - 핵심: 모바일 가독성: Fontsize, Outline, Shadow, MarginV
    - 박스: BorderStyle=3 + BackColour
    """
    # 박스 모드
    if SUB_BOX_MODE == 0:
        border_style = 1
        back = "&H00000000&"  # 의미 없음
        outline = SUB_OUTLINE
        shadow = SUB_SHADOW
    else:
        border_style = 3
        back = SUB_BOX_BACK_COLOUR
        # 박스가 있으면 outline/shadow는 약간만 주는게 보기 좋습니다(원하면 컨트롤 가능)
        outline = max(2, int(SUB_OUTLINE))
        shadow = max(1, int(SUB_SHADOW))

    style = (
        f"FontName={SUB_FONT_NAME},"
        f"FontSize={int(SUB_FONT_SIZE)},"
        f"Bold={int(SUB_BOLD)},"
        f"PrimaryColour={SUB_PRIMARY_COLOUR},"
        f"Outline={int(outline)},"
        f"Shadow={int(shadow)},"
        f"MarginV={int(SUB_MARGIN_V)},"
        f"BorderStyle={int(border_style)},"
        f"BackColour={back}"
    )
    return style


# =============================================================================
# FFmpeg filter script (xfade 체인 + 전환 비율)
# =============================================================================

def clamp(v, a, b):
    return max(a, min(b, v))


def pick_transition_name() -> str:
    if TRANSITION_STYLE == "fade_only":
        return "fade"
    # natural
    return random.choice(XFADE_TRANSITIONS_NATURAL)


def build_filter_script_xfade(pre_imgs: list[Path], seg: float, fade: float, srt_path: Path | None) -> tuple[str, str]:
    """
    xfade 기반 체인
    - 각 입력은 seg 길이(반복 루프 + trim)
    - 각 전환은 fade 길이
    - offset_i = (i+1)*(seg - fade)
    - 최종 라벨: [vout]
    """
    lines = []

    # 각 입력 정리(혹시라도 메타가 꼬일 수 있어 fps/format/sar 고정)
    for i in range(len(pre_imgs)):
        eq = ""
        if COLOR_RANDOM_ENABLE:
            sat = random.uniform(*SAT_RANGE)
            con = random.uniform(*CONTRAST_RANGE)
            bri = random.uniform(*BRIGHT_RANGE)
            # eq는 밝기/채도/대비를 미세하게만
            eq = f"eq=saturation={sat:.3f}:contrast={con:.3f}:brightness={(bri-1.0):.4f},"

        # 줌: t 기반 scale -> 다시 1080x1920에 맞춤(혹시 분해능이 변해도 안전)
        zoom = (
            f"scale=iw*(1+{ZOOM_INTENSITY:.6f}*t):"
            f"ih*(1+{ZOOM_INTENSITY:.6f}*t):eval=frame,"
        )

        chain = (
            f"[{i}:v]"
            f"{zoom}"
            f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color={BACKGROUND_FALLBACK_COLOR},"
            f"setsar=1,setdar={VIDEO_W}/{VIDEO_H},"
            f"{eq}"
            f"format=yuv420p,fps={FPS},"
            f"trim=duration={seg:.3f},setpts=PTS-STARTPTS"
            f"[v{i}];"
        )
        lines.append(chain)

    # xfade 체인
    # 첫 페어: [v0][v1] -> [x1]
    if len(pre_imgs) == 1:
        cur = "[v0]"
    else:
        offset_step = (seg - fade)  # 다음 전환이 시작되는 간격
        offset = offset_step  # 첫 전환은 seg-fade 시점
        tname = pick_transition_name()
        lines.append(f"[v0][v1]xfade=transition={tname}:duration={fade:.3f}:offset={offset:.3f}[x1];")
        cur = "[x1]"

        for k in range(2, len(pre_imgs)):
            offset = offset_step * k  # (i+1)*(seg-fade)에서 i=k-1 -> k*(seg-fade)
            tname = pick_transition_name()
            lines.append(f"{cur}[v{k}]xfade=transition={tname}:duration={fade:.3f}:offset={offset:.3f}[x{k}];")
            cur = f"[x{k}]"

    # 자막
    if srt_path:
        srt_esc = escape_subtitles_path_for_windows(srt_path)
        style = build_ass_force_style().replace("'", r"\\'")
        lines.append(f"{cur}subtitles='{srt_esc}':charenc=UTF-8:force_style='{style}'[vout];")
    else:
        lines.append(f"{cur}copy[vout];")

    return "\n".join(lines), "[vout]"


# =============================================================================
# FFmpeg 실행(진행률/멈춤 감지)
# =============================================================================

def run_ffmpeg_with_progress(cmd: list[str], qevt: queue.Queue, stage: str, base_pct: float, span_pct: float) -> tuple[int, str]:
    """
    - FFmpeg -progress pipe:1 출력 기반으로 진행 신호 감지
    - 일정 시간 신호 없으면 kill
    """
    # -progress pipe:1 를 stdout으로 받기
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
                    last_sig = time.time()
                    # 0~1 신호(정확한 %는 모르지만 진행 중임을 UI에 확실히 보여줌)
                    tick = (out_ms % 10_000_000) / 10_000_000
                    qevt.put(("progress", stage, "인코딩 진행 중...", base_pct + tick * span_pct))
                except Exception:
                    pass

            if time.time() - last_sig > NO_PROGRESS_KILL_SEC:
                tail_add(f"[KILL] no progress > {NO_PROGRESS_KILL_SEC}s")
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
# 메인 빌드(원패스)
# =============================================================================

@dataclass
class BuildReport:
    output_mp4: Path
    preprocess_folder: Path
    output_folder: Path
    temp_folder: Path
    audio_len: float
    seg: float
    fade: float
    elapsed: float
    img_count: int


def build_video_onepass(pre_imgs: list[Path], audio_path: Path, srt_path: Path | None, base_dir: Path, qevt: queue.Queue) -> BuildReport:
    if not pre_imgs:
        raise RuntimeError("전처리 이미지가 없습니다.")

    # 폴더 구조
    output_folder = base_dir / "OUTPUT"
    temp_folder = output_folder / "temp"
    output_folder.mkdir(exist_ok=True)
    temp_folder.mkdir(exist_ok=True)

    # 오디오 길이(참고용)
    audio_len = probe_audio_duration(audio_path)
    if audio_len <= 0:
        audio_len = 0.0

    # seg/fade 계산(전환 비율 기반)
    seg = float(BASE_IMAGE_SEC)
    fade = clamp(seg * float(TRANSITION_RATIO), TRANSITION_MIN_SEC, TRANSITION_MAX_SEC)
    # seg보다 크면 안 됨(겹침이 과해져서 꼬임)
    fade = min(fade, seg * 0.85)

    qevt.put(("log", f"[{_ts()}] MP3 길이: {audio_len:.2f}초" if audio_len else f"[{_ts()}] 오디오 길이: 측정 불가(진행)"))
    qevt.put(("log", f"[{_ts()}] 이미지당 표시(전체): {seg:.2f}초"))
    qevt.put(("log", f"[{_ts()}] 전환시간: {fade:.2f}초 (비율 {TRANSITION_RATIO:.2f})"))
    qevt.put(("log", f"[{_ts()}] 출력: {VIDEO_W}x{VIDEO_H} / FPS={FPS} / 전환 스타일={TRANSITION_STYLE}"))

    # SRT 정리
    if srt_path:
        clean_path = temp_folder / (srt_path.stem + "__clean.srt")
        try:
            srt_path = clean_srt(srt_path, clean_path)
            qevt.put(("log", f"[{_ts()}] ✅ SRT 정리 완료: {clean_path.name}"))
        except Exception as e:
            qevt.put(("log", f"[{_ts()}] ⚠ SRT 정리 실패(원본 사용): {e}"))

    # filter script 생성
    script_text, vout_label = build_filter_script_xfade(pre_imgs, seg, fade, srt_path)
    script_path = temp_folder / "filter_complex.txt"
    script_path.write_text(script_text, encoding="utf-8")

    out_mp4 = output_folder / OUTPUT_FILENAME

    def make_cmd(encoder: str) -> list[str]:
        cmd = [FFMPEG_BIN, "-hide_banner", "-y"]

        # 이미지 입력: 각 이미지를 seg 길이로 루프
        for img in pre_imgs:
            cmd += ["-loop", "1", "-t", f"{seg:.3f}", "-i", str(img)]

        # 오디오 입력
        cmd += ["-i", str(audio_path)]

        # 필터
        cmd += ["-filter_complex_script", str(script_path)]
        cmd += ["-map", vout_label, "-map", f"{len(pre_imgs)}:a"]
        cmd += ["-r", str(FPS)]

        # 비디오 인코더
        if encoder == "h264_nvenc":
            cmd += ["-c:v", "h264_nvenc", "-preset", NVENC_PRESET, "-pix_fmt", "yuv420p"]
        else:
            cmd += ["-c:v", "libx264", "-preset", X264_PRESET, "-crf", str(X264_CRF), "-pix_fmt", "yuv420p"]

        # 오디오
        cmd += ["-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE]

        # ✅ 영상 길이 문제 방지: -shortest
        cmd += ["-shortest", str(out_mp4)]
        return cmd

    qevt.put(("progress", "최종 생성", "FFmpeg 원패스 인코딩 시작", 20.0))

    # NVENC -> x264 폴백
    tail = ""
    for label, enc in (("NVENC", ENC_PRIMARY), ("x264", ENC_FALLBACK)):
        qevt.put(("log", f"[{_ts()}] 실행: {label}"))
        rc, tail = run_ffmpeg_with_progress(make_cmd(enc), qevt, "최종 생성", 20.0, 79.0)
        if rc == 0:
            qevt.put(("progress", "완료", f"완료: {out_mp4.name}", 100.0))
            return BuildReport(
                output_mp4=out_mp4,
                preprocess_folder=base_dir / "output",
                output_folder=output_folder,
                temp_folder=temp_folder,
                audio_len=audio_len,
                seg=seg,
                fade=fade,
                elapsed=0.0,
                img_count=len(pre_imgs),
            )
        else:
            qevt.put(("log", f"[{_ts()}] ⚠ 실패: {label} (rc={rc})"))

    raise RuntimeError(f"최종 영상 생성 실패\n\n--- tail ---\n{tail}")


# =============================================================================
# UI (다크톤, 큐 기반 스레드 안전, 완료 자동 닫힘)
# =============================================================================

class CineUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CINEMATIC SHORTS ENGINE (1080x1920)")
        self.root.geometry("900x620")
        self.root.configure(bg="#0f1115")

        # 스타일
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TProgressbar", thickness=18)
        style.configure("TButton", padding=6)

        self.stage_var = tk.StringVar(value="대기")
        self.detail_var = tk.StringVar(value="")
        self.pct_var = tk.StringVar(value="0.0%")

        header = tk.Frame(self.root, bg="#0f1115")
        header.pack(fill="x", padx=16, pady=(14, 10))

        tk.Label(header, text="CINEMATIC SHORTS ENGINE", fg="#ffffff", bg="#0f1115",
                 font=("Malgun Gothic", 16, "bold")).pack(anchor="w")
        tk.Label(header, text="1080x1920 / 전환 비율 기반 / 반사 배경(강함) / 랜덤 연출",
                 fg="#9aa4b2", bg="#0f1115", font=("Malgun Gothic", 10)).pack(anchor="w", pady=(6, 0))

        status = tk.Frame(self.root, bg="#0f1115")
        status.pack(fill="x", padx=16, pady=(0, 10))

        tk.Label(status, textvariable=self.stage_var, fg="#ffffff", bg="#0f1115",
                 font=("Malgun Gothic", 12, "bold")).pack(anchor="w")
        tk.Label(status, textvariable=self.detail_var, fg="#c7d0db", bg="#0f1115",
                 font=("Malgun Gothic", 10)).pack(anchor="w", pady=(4, 0))

        self.pb = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", maximum=100)
        self.pb.pack(fill="x", padx=16, pady=(6, 0))
        tk.Label(self.root, textvariable=self.pct_var, fg="#c7d0db", bg="#0f1115",
                 font=("Malgun Gothic", 10, "bold")).pack(anchor="e", padx=18, pady=(4, 10))

        # 로그
        log_box = tk.Frame(self.root, bg="#0f1115")
        log_box.pack(fill="both", expand=True, padx=16, pady=10)

        tk.Label(log_box, text="진행 로그", fg="#ffffff", bg="#0f1115",
                 font=("Malgun Gothic", 11, "bold")).pack(anchor="w")

        self.txt = tk.Text(log_box, wrap="word", height=18, bg="#121622", fg="#dbe5f0",
                           insertbackground="#dbe5f0", relief="flat")
        self.txt.pack(fill="both", expand=True, pady=(8, 0))
        self.txt.insert("1.0", "준비 완료.\n")
        self.txt.config(state="disabled")

        # 버튼
        btns = tk.Frame(self.root, bg="#0f1115")
        btns.pack(fill="x", padx=16, pady=(0, 14))

        self.btn_start = tk.Button(btns, text="작업 시작", command=self.start, bg="#2d6cdf", fg="white",
                                   activebackground="#3b7af0", activeforeground="white", relief="flat",
                                   font=("Malgun Gothic", 11, "bold"), padx=14, pady=10)
        self.btn_start.pack(side="left")

        self.btn_quit = tk.Button(btns, text="닫기", command=self.root.destroy, bg="#1f2433", fg="#c7d0db",
                                  activebackground="#2a3145", activeforeground="#ffffff", relief="flat",
                                  font=("Malgun Gothic", 10), padx=12, pady=10)
        self.btn_quit.pack(side="right")

        self.qevt = queue.Queue()
        self.worker = None
        self.root.after(120, self.poll)

    def log(self, s: str):
        safe_print(s)
        self.txt.config(state="normal")
        self.txt.insert("end", s + "\n")
        self.txt.see("end")
        self.txt.config(state="disabled")

    def set_progress(self, stage: str, detail: str, pct: float):
        pct = max(0.0, min(100.0, float(pct)))
        self.stage_var.set(stage)
        self.detail_var.set(detail)
        self.pb["value"] = pct
        self.pct_var.set(f"{pct:.1f}%")

    def pick_inputs(self):
        messagebox.showinfo("선택", "이미지 폴더를 선택해 주세요.")
        img_dir = filedialog.askdirectory(title="이미지 폴더 선택")
        if not img_dir:
            return None, None, None

        messagebox.showinfo("선택", "오디오 파일(MP3/WAV 등)을 선택해 주세요.")
        audio = filedialog.askopenfilename(
            title="오디오 파일 선택",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac"), ("All files", "*.*")]
        )
        if not audio:
            return None, None, None

        srt = None
        if messagebox.askyesno("자막", "자막(SRT)을 영상에 넣을까요?"):
            picked = filedialog.askopenfilename(
                title="자막 SRT 선택",
                filetypes=[("SubRip", "*.srt"), ("All files", "*.*")]
            )
            if picked:
                srt = Path(picked)
        return Path(img_dir), Path(audio), srt

    def open_folder(self, folder: Path):
        try:
            if os.name == "nt":
                os.startfile(str(folder.resolve()))
        except Exception:
            pass

    def cleanup_temp(self, temp_dir: Path):
        if not DELETE_TEMP_AFTER_DONE:
            return
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    def worker_run(self, img_dir: Path, audio: Path, srt: Path | None):
        t0 = time.time()
        try:
            self.qevt.put(("progress", "시작", "전처리(반사 배경 + 워터마크) 시작", 0.0))
            out_folder, pre_imgs = preprocess_images(img_dir, self.qevt)

            self.qevt.put(("progress", "최종 생성", "원패스 인코딩 시작", 20.0))
            report = build_video_onepass(pre_imgs, audio, srt, base_dir=img_dir, qevt=self.qevt)
            report.elapsed = time.time() - t0

            # TEMP 삭제
            self.cleanup_temp(report.temp_folder)

            self.qevt.put(("done", report))
        except Exception as e:
            self.qevt.put(("error", str(e)))

    def start(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("진행중", "이미 작업이 진행 중입니다.")
            return

        img_dir, audio, srt = self.pick_inputs()
        if not img_dir or not audio:
            return

        self.btn_start.config(state="disabled")
        self.set_progress("준비", "작업 스레드 시작", 0.0)
        self.log("작업 시작.")
        self.worker = threading.Thread(target=self.worker_run, args=(img_dir, audio, srt), daemon=True)
        self.worker.start()

    def _report_popup(self, report: BuildReport):
        pop = tk.Toplevel(self.root)
        pop.title("작업 리포트")
        pop.geometry("720x420")
        pop.configure(bg="#0f1115")
        pop.attributes("-topmost", True)

        tk.Label(pop, text="완료", fg="#ffffff", bg="#0f1115",
                 font=("Malgun Gothic", 13, "bold")).pack(anchor="w", padx=14, pady=(12, 0))

        text = tk.Text(pop, wrap="word", height=14, bg="#121622", fg="#dbe5f0",
                       relief="flat", insertbackground="#dbe5f0")
        text.pack(fill="both", expand=True, padx=14, pady=12)

        msg = (
            f"최종 파일: {report.output_mp4}\n\n"
            f"전처리 폴더: {report.preprocess_folder}\n"
            f"OUTPUT 폴더: {report.output_folder}\n\n"
            f"이미지 수: {report.img_count}장\n"
            f"이미지당 표시(전체): {report.seg:.2f}초\n"
            f"전환시간: {report.fade:.2f}초 (비율 {TRANSITION_RATIO:.2f})\n"
            f"오디오 길이: {report.audio_len:.2f}초\n"
            f"총 소요 시간: {report.elapsed:.2f}초\n\n"
            f"TEMP 정리: {'삭제 완료' if DELETE_TEMP_AFTER_DONE else '유지'}\n"
        )
        text.insert("1.0", msg)
        text.config(state="disabled")

        btn = tk.Button(pop, text="확인", command=pop.destroy, bg="#2d6cdf", fg="white",
                        activebackground="#3b7af0", activeforeground="white", relief="flat",
                        font=("Malgun Gothic", 10, "bold"), padx=12, pady=8)
        btn.pack(anchor="e", padx=14, pady=(0, 14))

        # ✅ 10초 무조작이면 자동 닫힘(조작 감지 시 타이머 리셋)
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
                    _, stage, detail, pct = evt
                    self.set_progress(stage, detail, pct)
                elif kind == "done":
                    _, report = evt
                    self.log("완료.")
                    self.set_progress("완료", "작업 완료", 100.0)
                    self.btn_start.config(state="normal")

                    # 폴더 열기
                    self.open_folder(report.preprocess_folder)
                    self.open_folder(report.output_folder)

                    # 리포트 팝업(10초 무조작 자동 닫힘)
                    self._report_popup(report)

                elif kind == "error":
                    _, err = evt
                    self.btn_start.config(state="normal")
                    self.set_progress("오류", "작업 중단", 0.0)
                    self.log("오류 발생.")
                    messagebox.showerror("오류", err)

        except queue.Empty:
            pass

        self.root.after(120, self.poll)

    def run(self):
        self.root.mainloop()


def main():
    CineUI().run()


if __name__ == "__main__":
    main()
