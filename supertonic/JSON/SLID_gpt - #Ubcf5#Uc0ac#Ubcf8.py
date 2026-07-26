# slideshow_maker_v4_6_1_soft_transitions_loop_marquee_fixcomma.py
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
import re
import random
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import time
from PIL import Image, ImageDraw, ImageFont


VERSION = "4.6.1-STABLE-WM"

# =============================================================================
# 전환 효과 풀(요청: fade / dissolve / wipe / slide 계열 위주)
# =============================================================================
TRANSITIONS = [
    "fade",
    "dissolve",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown"
]

# =============================================================================
# 컨트롤 센터(관리자 설정)
# =============================================================================
VIDEO_W = 1080
VIDEO_H = 1920
FPS = 30

RANDOMIZE_IMAGES = True

COVER_FILL = True

VIGNETTE_ENABLE = True
VIGNETTE_TOP_H = 240
VIGNETTE_BOTTOM_H = 300
VIGNETTE_ALPHA = 0.22

KENBURNS_ENABLE = True
KENBURNS_MAX_ZOOM = 1.055
KENBURNS_ZOOM_STEP = 0.00055
KENBURNS_PAN_STRENGTH = 0.10
KENBURNS_RANDOM_DIRECTION = True

SUB_LINE_LEN = 28
SUB_MAX_LINES = 2

# ✅ 자막 스크롤(마퀴) - 전체 적용 + 속도 조절 (요청값)
SUB_SCROLL_ENABLE = True
SUB_SCROLL_ALL = True
SUB_SCROLL_PX_PER_SEC = 280    # 값 낮을수록 더 느리게 흐름(추천 55~85)
SUB_SCROLL_GAP_PX = 50       # 한 바퀴 돌 때 텍스트 간격
SUB_SCROLL_GUARD_SEC = 0.05   # 자막 구간 앞뒤 약간 여유(깜빡임 방지)

USE_GPU_NVENC = True
NVENC_PRESET = "p5"
NVENC_CQ = 23

X264_PRESET = "medium"
X264_CRF = "23"

WM_BOTTOM_MARGIN = 50
WM_LINE_GAP = 12
WM_FONT_SIZE = 48

# =============================================================================
# 워터마크 전처리(원본 보존 + output 폴더에 용량절감/워터마크 이미지 생성)
# =============================================================================
PREPROCESS_ENABLE = True              # True: 슬라이드쇼는 전처리 이미지 사용
PREPROCESS_SUBFOLDER = "output"       # 이미지 저장 폴더(원본 폴더 바로 아래)
PREPROCESS_FORMAT = "jpg"             # "jpg" 권장(용량 절감). "png"도 가능
PREPROCESS_JPEG_QUALITY = 85          # 70~90 권장
PREPROCESS_MAX_SIDE = 2200            # 긴 변 최대(픽셀). 너무 크면 용량 증가
PREPROCESS_OVERWRITE = False          # True면 매번 재생성

WM_TEXT_GAP_PX = 14                   # 상호/전화번호 두 줄 간격
WM_BOTTOM_PAD_PX = 60                # 하단에서 60px 띄우기(요청)
WM_STROKE_W = 3
WM_FILL = (255, 255, 255)            # 텍스트 색(흰색)
WM_STROKE = (0, 0, 0)                # 외곽선(검정)
WM_BG_ENABLE = False                 # True면 텍스트 뒤 반투명 박스
WM_BG_ALPHA = 110                    # 0~255
WM_BG_PAD_X = 28
WM_BG_PAD_Y = 16


SUB_ABOVE_BRAND_PX = 30

FONT_FILE = "C\\:/Windows/Fonts/malgun.ttf"

XFADER_FALLBACK_TO_X264 = True

FFMPEG_ERR_TAIL_LINES = 80
# =============================================================================

def clean_srt_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def split_to_lines(text: str, max_len: int) -> list:
    text = text.strip()
    if not text:
        return []

    if " " not in text or len(text.split()) <= 1:
        lines = []
        buf = ""
        for ch in text:
            buf += ch
            if len(buf) >= max_len:
                lines.append(buf)
                buf = ""
        if buf:
            lines.append(buf)
        return lines

    words = text.split()
    lines = []
    cur = ""

    for w in words:
        if len(w) > max_len:
            if cur.strip():
                lines.append(cur.rstrip())
                cur = ""
            chunk = ""
            for ch in w:
                chunk += ch
                if len(chunk) >= max_len:
                    lines.append(chunk)
                    chunk = ""
            if chunk:
                cur = chunk + " "
            continue

        if len(cur) + len(w) + 1 <= max_len:
            cur += w + " "
        else:
            lines.append(cur.rstrip())
            cur = w + " "

    if cur.strip():
        lines.append(cur.rstrip())

    return lines

def paginate_lines(lines: list, max_lines: int) -> list:
    pages = []
    i = 0
    while i < len(lines):
        pages.append("\n".join(lines[i:i+max_lines]))
        i += max_lines
    return pages

def parse_srt_with_pages(srt_path: str):
    subtitles = []
    try:
        with open(srt_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        blocks = re.split(r"\n\s*\n", content.strip())

        def time_to_seconds(t: str) -> float:
            h, m, s = t.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue

            time_line = lines[1]
            m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
            if not m:
                continue

            start_str, end_str = m.groups()
            start = start_str.replace(",", ".")
            end = end_str.replace(",", ".")

            raw_text = " ".join(lines[2:]).strip()
            clean = clean_srt_text(raw_text)

            sub_lines = split_to_lines(clean, SUB_LINE_LEN)
            pages = paginate_lines(sub_lines, SUB_MAX_LINES)
            if not pages:
                continue

            subtitles.append({
                "start": time_to_seconds(start),
                "end": time_to_seconds(end),
                "pages": pages
            })

    except Exception as e:
        print("SRT 파싱 오류:", e)

    return subtitles

def escape_for_drawtext(text: str) -> str:
    if text is None:
        return ""
    text = text.replace("\\", "\\\\")
    # ✅ 줄바꿈이 'n'으로 보이는 문제 방지
    text = text.replace("\n", r"\\n")
    text = text.replace("'", r"\'")
    text = text.replace(":", r"\:")
    text = text.replace(",", r"\,")
    return text

def escape_commas_in_expr(expr: str) -> str:
    # ✅ FFmpeg 필터 문자열에서 "표현식 내부 콤마"는 필터 구분자로 오해될 수 있어 \, 처리 필요
    return expr.replace(",", r"\,")

def even_int(x: float) -> int:
    v = int(round(x))
    return v if v % 2 == 0 else v + 1

def smoothstep_expr(p: str) -> str:
    return f"({p})*({p})*(3-2*({p}))"

def has_nvenc() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        return "h264_nvenc" in out
    except:
        return False

def encoder_settings(prefer_gpu: bool = True):
    if prefer_gpu and USE_GPU_NVENC and has_nvenc():
        return "h264_nvenc", ["-preset", NVENC_PRESET, "-rc", "vbr", "-cq", str(NVENC_CQ)]
    return "libx264", ["-preset", X264_PRESET, "-crf", str(X264_CRF)]

def build_base_visual_filter(clip_seconds: float) -> str:
    if not KENBURNS_ENABLE:
        if COVER_FILL:
            base = (
                f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_W}:{VIDEO_H}"
            )
        else:
            base = (
                f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
                f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color=white"
            )
    else:
        pre_w = even_int(VIDEO_W * KENBURNS_MAX_ZOOM)
        pre_h = even_int(VIDEO_H * KENBURNS_MAX_ZOOM)

        total_frames = max(2, int(round(clip_seconds * FPS)))
        denom = max(1, total_frames - 1)

        p = f"(on/{denom})"
        e = smoothstep_expr(p)

        pan = float(KENBURNS_PAN_STRENGTH)

        if KENBURNS_RANDOM_DIRECTION:
            patterns = [
                (0.15, 0.15, 0.85, 0.85),
                (0.85, 0.15, 0.15, 0.85),
                (0.15, 0.85, 0.85, 0.15),
                (0.85, 0.85, 0.15, 0.15),
                (0.50, 0.20, 0.50, 0.80),
                (0.20, 0.50, 0.80, 0.50),
            ]
            sx, sy, ex, ey = random.choice(patterns)
        else:
            sx, sy, ex, ey = (0.15, 0.15, 0.85, 0.85)

        x0 = f"(iw-ow)*({sx})*{pan} + (iw-ow)*(1-{pan})/2"
        x1 = f"(iw-ow)*({ex})*{pan} + (iw-ow)*(1-{pan})/2"
        y0 = f"(ih-oh)*({sy})*{pan} + (ih-oh)*(1-{pan})/2"
        y1 = f"(ih-oh)*({ey})*{pan} + (ih-oh)*(1-{pan})/2"

        x_expr = f"max(0,min(iw-ow, ({x0}) + (({x1})-({x0}))*({e})))"
        y_expr = f"max(0,min(ih-oh, ({y0}) + (({y1})-({y0}))*({e})))"
        z_expr = f"min(zoom+{KENBURNS_ZOOM_STEP},{KENBURNS_MAX_ZOOM})"

        if COVER_FILL:
            base0 = (
                f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
                f"crop={pre_w}:{pre_h}"
            )
        else:
            base0 = (
                f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=decrease,"
                f"pad={pre_w}:{pre_h}:(ow-iw)/2:(oh-ih)/2:color=white"
            )

        base = (
            base0 + ","
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
            f"d={total_frames}:s={VIDEO_W}x{VIDEO_H}:fps={FPS}"
        )

    if VIGNETTE_ENABLE:
        base += (
            f",drawbox=x=0:y=0:w=iw:h={VIGNETTE_TOP_H}:color=black@{VIGNETTE_ALPHA}:t=fill"
            f",drawbox=x=0:y=ih-{VIGNETTE_BOTTOM_H}:w=iw:h={VIGNETTE_BOTTOM_H}:color=black@{VIGNETTE_ALPHA}:t=fill"
        )

    base += ",setsar=1,setdar=9/16"
    return base

def make_subtitle_filters(subs, clip_start, still_dur, subtitle_y, font_size, bg_on):
    filters = []
    clip_end = clip_start + still_dur

    for sub in subs:
        s0 = sub["start"]
        s1 = sub["end"]
        if s0 >= clip_end or s1 <= clip_start:
            continue

        seg_start = max(s0, clip_start)
        seg_end = min(s1, clip_end)

        rel_start = seg_start - clip_start
        rel_end = seg_end - clip_start
        seg_len = max(0.001, rel_end - rel_start)

        pages = sub.get("pages", [])
        if not pages:
            continue

        page_len = seg_len / len(pages)

        for pi, page_text in enumerate(pages):
            p_start = rel_start + (pi * page_len)
            p_end = rel_start + ((pi + 1) * page_len)

            p_start2 = p_start + SUB_SCROLL_GUARD_SEC
            p_end2 = p_end - SUB_SCROLL_GUARD_SEC
            if p_end2 <= p_start2:
                p_start2 = p_start
                p_end2 = p_end

            txt = escape_for_drawtext(page_text)

            # ✅ 요청: 모든 자막 스크롤 강제
            do_scroll = bool(SUB_SCROLL_ENABLE and SUB_SCROLL_ALL)

            box_opt = "box=1:boxcolor=black@0.60:boxborderw=15:" if bg_on else ""

            if do_scroll:
                # ✅ 루프 스크롤(멈추지 않음)
                # loop_len = tw + w + gap
                loop_len = f"(tw+w+{SUB_SCROLL_GAP_PX})"
                # ✅ 핵심: mod(a,b) 안의 콤마는 \, 로 이스케이프해야 함
                x_expr = f"w-mod((t-{p_start2:.3f})*{SUB_SCROLL_PX_PER_SEC},{loop_len})"
                x_expr = escape_commas_in_expr(x_expr)

                filters.append(
                    "drawtext="
                    f"text='{txt}':fontfile='{FONT_FILE}':"
                    f"fontsize={int(font_size)}:"
                    "fontcolor=white:bordercolor=black:borderw=3:"
                    f"{box_opt}"
                    f"x={x_expr}:y={int(subtitle_y)}:"
                    f"enable='between(t,{p_start2:.3f},{p_end2:.3f})'"
                )
            else:
                filters.append(
                    "drawtext="
                    f"text='{txt}':fontfile='{FONT_FILE}':"
                    f"fontsize={int(font_size)}:"
                    "fontcolor=white:bordercolor=black:borderw=3:"
                    f"{box_opt}"
                    "x=(w-text_w)/2:"
                    f"y={int(subtitle_y)}:"
                    f"enable='between(t,{p_start2:.3f},{p_end2:.3f})'"
                )

    return filters


def _pil_font(size: int):
    # Windows 기본 폰트 우선 사용, 실패 시 PIL 기본 폰트
    try:
        # FONT_FILE 은 FFmpeg용 경로(escaped)라 PIL에는 직접 쓰기 어려워 별도 지정
        # 말굽(맑은고딕) 경로를 직접 사용
        return ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", size=size)
    except:
        try:
            return ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", size=size)
        except:
            return ImageFont.load_default()

def _ensure_rgb(im: Image.Image) -> Image.Image:
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        return bg
    if im.mode != "RGB":
        return im.convert("RGB")
    return im

def _resize_max_side(im: Image.Image, max_side: int) -> Image.Image:
    w, h = im.size
    m = max(w, h)
    if m <= max_side:
        return im
    scale = max_side / float(m)
    nw = max(2, int(round(w * scale)))
    nh = max(2, int(round(h * scale)))
    return im.resize((nw, nh), Image.LANCZOS)

def _draw_centered_multiline(draw: ImageDraw.ImageDraw, lines, font, y_bottom, gap):
    # lines: [line1, line2]  (공백은 스킵)
    lines = [ln for ln in lines if ln and ln.strip()]
    if not lines:
        return None  # nothing
    metrics = []
    max_w = 0
    total_h = 0
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font, stroke_width=WM_STROKE_W)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        metrics.append((ln, w, h))
        max_w = max(max_w, w)
        total_h += h
    total_h += gap * (len(metrics) - 1)

    # 블록의 bottom을 y_bottom에 맞춤
    y0 = int(round(y_bottom - total_h))
    return {"metrics": metrics, "max_w": max_w, "total_h": total_h, "y0": y0}

def watermark_and_save(src_path: str, dst_path: str, brand: str, phone: str):
    im = Image.open(src_path)
    im = _ensure_rgb(im)
    im = _resize_max_side(im, int(PREPROCESS_MAX_SIDE))

    draw = ImageDraw.Draw(im)
    font = _pil_font(int(WM_FONT_SIZE))

    lines = [brand.strip(), phone.strip()]
    y_bottom = im.size[1] - int(WM_BOTTOM_PAD_PX)

    layout = _draw_centered_multiline(draw, lines, font, y_bottom, int(WM_TEXT_GAP_PX))
    if layout:
        x0 = int(round((im.size[0] - layout["max_w"]) / 2))
        y = layout["y0"]

        # 배경 박스(옵션)
        if WM_BG_ENABLE:
            # 대략적 bbox 계산
            bx0 = x0 - WM_BG_PAD_X
            by0 = y - WM_BG_PAD_Y
            bx1 = x0 + layout["max_w"] + WM_BG_PAD_X
            by1 = y + layout["total_h"] + WM_BG_PAD_Y
            overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.rounded_rectangle([bx0, by0, bx1, by1], radius=18, fill=(0, 0, 0, int(WM_BG_ALPHA)))
            im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(im)

        for (ln, w, h) in layout["metrics"]:
            lx = int(round((im.size[0] - w) / 2))
            draw.text((lx, y), ln, font=font, fill=WM_FILL,
                      stroke_width=int(WM_STROKE_W), stroke_fill=WM_STROKE)
            y += h + int(WM_TEXT_GAP_PX)

    # 저장
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    ext = (PREPROCESS_FORMAT or "jpg").lower().strip(".")
    if ext == "png":
        im.save(dst_path, format="PNG", optimize=True)
    else:
        im.save(dst_path, format="JPEG", quality=int(PREPROCESS_JPEG_QUALITY), optimize=True, progressive=True)

def preprocess_images(image_folder: str, image_paths: list, brand: str, phone: str) -> tuple:
    """
    return: (preprocessed_folder, processed_paths)
    """
    out_img_dir = os.path.join(image_folder, PREPROCESS_SUBFOLDER)
    os.makedirs(out_img_dir, exist_ok=True)

    processed = []
    for p in image_paths:
        base = os.path.splitext(os.path.basename(p))[0]
        dst = os.path.join(out_img_dir, f"{base}.{PREPROCESS_FORMAT}")
        try:
            if not PREPROCESS_OVERWRITE and os.path.exists(dst):
                # 원본이 더 새로우면 재생성
                if os.path.getmtime(dst) >= os.path.getmtime(p):
                    processed.append(dst)
                    continue
            watermark_and_save(p, dst, brand, phone)
            processed.append(dst)
        except Exception as e:
            # 전처리 실패 시 원본 사용(안전장치)
            processed.append(p)

    return out_img_dir, processed

def show_auto_close_report(title: str, msg: str, auto_ms: int = 7000):
    # messagebox는 자동닫기 어려워, Toplevel로 구현
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("520x360")
    win.attributes("-topmost", True)

    frm = tk.Frame(win, padx=14, pady=14)
    frm.pack(fill="both", expand=True)

    lbl = tk.Label(frm, text=msg, justify="left", anchor="nw", wraplength=480)
    lbl.pack(fill="both", expand=True)

    btn = tk.Button(frm, text="확인", command=lambda: win.destroy())
    btn.pack(pady=(12, 0))

    def _close():
        try:
            win.destroy()
        except:
            pass

    win.after(int(auto_ms), _close)

    def _on_close():
        try:
            root.destroy()
        except:
            pass

    win.protocol("WM_DELETE_WINDOW", _on_close)

    # win이 닫히면 root도 종료
    def _poll():
        if not win.winfo_exists():
            _on_close()
            return
        win.after(200, _poll)
    _poll()

    root.mainloop()

class SlideshowMaker:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        self.window = ctk.CTk()
        self.window.title(f"슬라이드쇼 메이커 v{VERSION}")
        self.window.geometry("900x850")

        self.image_folder = tk.StringVar()
        self.mp3_file = tk.StringVar()
        self.srt_file = tk.StringVar()

        self.brand_text = tk.StringVar(value="강경 숯불바베큐")
        self.phone_text = tk.StringVar(value="0507-7393-5889")
        self.show_watermark = tk.BooleanVar(value=False)

        self.use_transitions = tk.BooleanVar(value=True)
        # ✅ 기본 전환 속도: 조금 느리게
        self.transition_duration = tk.DoubleVar(value=1.1)
        self.random_transitions = tk.BooleanVar(value=True)

        self.font_size = tk.IntVar(value=48)
        self.subtitle_bg = tk.BooleanVar(value=True)

        self.setup_ui()
        self.check_files()

    def setup_ui(self):
        main = ctk.CTkFrame(self.window)
        main.pack(fill="both", expand=True, padx=15, pady=15)

        title = ctk.CTkLabel(main, text=f"슬라이드쇼 메이커 v{VERSION}", font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(pady=10)

        tabview = ctk.CTkTabview(main, height=500)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        tab_files = tabview.add("파일")
        tab_watermark = tabview.add("워터마크")
        tab_transition = tabview.add("전환")
        tab_subtitle = tabview.add("자막")

        file_frame = ctk.CTkFrame(tab_files)
        file_frame.pack(fill="both", expand=True, padx=20, pady=20)

        row1 = ctk.CTkFrame(file_frame)
        row1.pack(fill="x", pady=10)
        ctk.CTkLabel(row1, text="이미지 폴더:", width=100, font=ctk.CTkFont(size=14)).pack(side="left")
        ctk.CTkEntry(row1, textvariable=self.image_folder, width=450).pack(side="left", padx=5)
        ctk.CTkButton(row1, text="찾기", command=self.browse_image_folder, width=80).pack(side="left")

        row2 = ctk.CTkFrame(file_frame)
        row2.pack(fill="x", pady=10)
        ctk.CTkLabel(row2, text="MP3 파일:", width=100, font=ctk.CTkFont(size=14)).pack(side="left")
        ctk.CTkEntry(row2, textvariable=self.mp3_file, width=450).pack(side="left", padx=5)
        ctk.CTkButton(row2, text="찾기", command=self.browse_mp3_file, width=80).pack(side="left")

        row3 = ctk.CTkFrame(file_frame)
        row3.pack(fill="x", pady=10)
        ctk.CTkLabel(row3, text="SRT 파일:", width=100, font=ctk.CTkFont(size=14)).pack(side="left")
        ctk.CTkEntry(row3, textvariable=self.srt_file, width=450).pack(side="left", padx=5)
        ctk.CTkButton(row3, text="찾기", command=self.browse_srt_file, width=80).pack(side="left")

        wm_frame = ctk.CTkFrame(tab_watermark)
        wm_frame.pack(fill="both", expand=True, padx=20, pady=20)

        wm_switch = ctk.CTkFrame(wm_frame)
        wm_switch.pack(fill="x", pady=10)
        ctk.CTkLabel(wm_switch, text="워터마크 사용", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkSwitch(wm_switch, text="", variable=self.show_watermark).pack(side="right")

        wm_row1 = ctk.CTkFrame(wm_frame)
        wm_row1.pack(fill="x", pady=10)
        ctk.CTkLabel(wm_row1, text="상호:", width=100).pack(side="left")
        ctk.CTkEntry(wm_row1, textvariable=self.brand_text, width=400).pack(side="left", padx=5)

        wm_row2 = ctk.CTkFrame(wm_frame)
        wm_row2.pack(fill="x", pady=10)
        ctk.CTkLabel(wm_row2, text="전화:", width=100).pack(side="left")
        ctk.CTkEntry(wm_row2, textvariable=self.phone_text, width=400).pack(side="left", padx=5)

        trans_frame = ctk.CTkFrame(tab_transition)
        trans_frame.pack(fill="both", expand=True, padx=20, pady=20)

        trans_switch = ctk.CTkFrame(trans_frame)
        trans_switch.pack(fill="x", pady=10)
        ctk.CTkLabel(trans_switch, text="전환 효과 사용", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkSwitch(trans_switch, text="", variable=self.use_transitions).pack(side="right")

        trans_row1 = ctk.CTkFrame(trans_frame)
        trans_row1.pack(fill="x", pady=10)
        ctk.CTkLabel(trans_row1, text="랜덤 효과:", width=100).pack(side="left")
        ctk.CTkSwitch(trans_row1, text="사용", variable=self.random_transitions).pack(side="left")

        trans_row2 = ctk.CTkFrame(trans_frame)
        trans_row2.pack(fill="x", pady=10)
        ctk.CTkLabel(trans_row2, text="전환 시간:", width=100).pack(side="left")

        trans_slider = ctk.CTkSlider(trans_row2, from_=0.3, to=1.5, variable=self.transition_duration, width=300)
        trans_slider.pack(side="left", padx=5)
        self.trans_label = ctk.CTkLabel(trans_row2, text=f"{self.transition_duration.get():.1f}초", width=70)
        self.trans_label.pack(side="left")
        trans_slider.configure(command=lambda v: self.trans_label.configure(text=f"{float(v):.1f}초"))

        sub_frame = ctk.CTkFrame(tab_subtitle)
        sub_frame.pack(fill="both", expand=True, padx=20, pady=20)

        sub_row1 = ctk.CTkFrame(sub_frame)
        sub_row1.pack(fill="x", pady=10)
        ctk.CTkLabel(sub_row1, text="자막 폰트:", width=100).pack(side="left")
        font_slider = ctk.CTkSlider(sub_row1, from_=20, to=80, variable=self.font_size, width=300)
        font_slider.pack(side="left", padx=5)
        self.font_label = ctk.CTkLabel(sub_row1, text=f"{self.font_size.get()}px", width=70)
        self.font_label.pack(side="left")
        font_slider.configure(command=lambda v: self.font_label.configure(text=f"{int(v)}px"))

        sub_row2 = ctk.CTkFrame(sub_frame)
        sub_row2.pack(fill="x", pady=10)
        ctk.CTkLabel(sub_row2, text="자막 배경:", width=100).pack(side="left")
        ctk.CTkSwitch(sub_row2, text="사용", variable=self.subtitle_bg).pack(side="left")

        log_label = ctk.CTkLabel(main, text="실행 로그:", anchor="w")
        log_label.pack(fill="x", padx=10, pady=(5, 0))

        self.log_text = ctk.CTkTextbox(main, height=150)
        self.log_text.pack(fill="x", padx=10, pady=5)

        bottom = ctk.CTkFrame(main)
        bottom.pack(fill="x", padx=10, pady=10)

        self.generate_btn = ctk.CTkButton(
            bottom, text="슬라이드쇼 생성",
            command=self.generate_slideshow,
            width=300, height=60,
            font=ctk.CTkFont(size=20, weight="bold"),
            state="disabled"
        )
        self.generate_btn.pack(side="left", padx=10)

        self.status_label = ctk.CTkLabel(bottom, text="파일을 선택해주세요", text_color="gray", font=ctk.CTkFont(size=14))
        self.status_label.pack(side="left", padx=20)

    def log(self, msg):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.window.update()

    def browse_image_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.image_folder.set(folder)
            self.check_files()

    def browse_mp3_file(self):
        f = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
        if f:
            self.mp3_file.set(f)
            self.check_files()

    def browse_srt_file(self):
        f = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt")])
        if f:
            self.srt_file.set(f)
            self.check_files()

    def check_files(self):
        if self.image_folder.get() and self.mp3_file.get() and self.srt_file.get():
            self.generate_btn.configure(state="normal")
            self.status_label.configure(text="모든 파일이 선택되었습니다")
        else:
            self.generate_btn.configure(state="disabled")

    def get_audio_duration(self, mp3_path):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", mp3_path],
                capture_output=True
            )
            return float((r.stdout or b"").decode("utf-8", errors="ignore").strip())
        except:
            return 0.0

    def run_ffmpeg(self, cmd, desc):
        self.log(f"{desc} 실행 중")
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
            if proc.returncode != 0:
                self.log(f"{desc} 실패")
                if proc.stderr:
                    err = proc.stderr.decode("utf-8", errors="ignore")
                    tail = err.split("\n")[-FFMPEG_ERR_TAIL_LINES:]
                    for line in tail:
                        if line.strip():
                            self.log("  " + line.strip())
                return False
            self.log(f"{desc} 완료")
            return True
        except Exception as e:
            self.log(f"실행 오류: {e}")
            return False

    def generate_slideshow(self):
        start_time = time.time()
        self.log_text.delete("1.0", "end")
        self.log("슬라이드쇼 생성 시작")
        self.status_label.configure(text="생성 중")
        self.window.update()

        try:
            folder = self.image_folder.get()

            images = []
            for fn in sorted(os.listdir(folder)):
                if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                    images.append(os.path.join(folder, fn))

            if RANDOMIZE_IMAGES:
                random.shuffle(images)

            self.log(f"이미지 {len(images)}장")

            # ✅ 요청: 원본 폴더 이미지를 직접 쓰지 않고, 폴더 바로 아래 output에
            #         용량 절감 + 워터마크 내장 이미지를 만들어 사용
            brand_txt = (self.brand_text.get() or "").strip()
            phone_txt = (self.phone_text.get() or "").strip()

            pre_dir = os.path.join(folder, PREPROCESS_SUBFOLDER)
            if PREPROCESS_ENABLE:
                pre_dir, images = preprocess_images(folder, images, brand_txt, phone_txt)
                self.log(f"✅ 전처리 이미지 저장 위치: {pre_dir}")
                self.log("워터마크: 이미지에 내장(FFmpeg 워터마크는 비활성)")
                self.log(f"전처리 이미지 {len(images)}장")

            if len(images) < 2:
                messagebox.showerror("오류", "이미지가 2장 이상 필요합니다")
                return

            audio_duration = self.get_audio_duration(self.mp3_file.get())
            if audio_duration <= 0:
                messagebox.showerror("오류", "MP3 길이를 확인할 수 없습니다")
                return

            self.log(f"MP3 길이 {audio_duration:.2f}초")

            subs = parse_srt_with_pages(self.srt_file.get())
            self.log(f"자막 블록 {len(subs)}개")

            out_dir = os.path.join(folder, "OUTPUT")
            os.makedirs(out_dir, exist_ok=True)

            temp_dir = os.path.join(out_dir, "temp")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)

            n = len(images)

            if self.use_transitions.get():
                trans = float(self.transition_duration.get())
                still = (audio_duration - trans * (n - 1)) / n
                if still < 1.0:
                    still = 1.0
                    trans = (audio_duration - still * n) / max(1, (n - 1))
                    trans = max(0.3, min(trans, 1.5))
                clip_len = still + trans
            else:
                trans = 0.0
                still = audio_duration / n
                clip_len = still

            self.log(f"이미지 유지 {still:.2f}초")
            self.log(f"전환 {trans:.2f}초")
            self.log(f"클립 길이 {clip_len:.2f}초")

            clip_vcodec, clip_vextra = encoder_settings(prefer_gpu=True)
            self.log(f"비디오 인코더: {clip_vcodec}")

            phone_y_expr = f"h-text_h-{WM_BOTTOM_MARGIN}"
            brand_y_expr = f"h-text_h-{WM_BOTTOM_MARGIN + WM_FONT_SIZE + WM_LINE_GAP}"

            subtitle_y = int(
                VIDEO_H
                - (WM_BOTTOM_MARGIN + WM_FONT_SIZE + WM_LINE_GAP + SUB_ABOVE_BRAND_PX + int(self.font_size.get()) * 2)
            )

            clip_files = []
            for i, img in enumerate(images):
                clip = os.path.join(temp_dir, f"clip_{i:03d}.mp4")
                clip_files.append(clip)

                clip_start = i * still

                base = build_base_visual_filter(clip_len)
                filters = [base]

                if (self.show_watermark.get() and (not PREPROCESS_ENABLE)):
                    phone = escape_for_drawtext(self.phone_text.get().strip())
                    brand = escape_for_drawtext(self.brand_text.get().strip())

                    if phone:
                        filters.append(
                            "drawtext="
                            f"text='{phone}':fontfile='{FONT_FILE}':"
                            f"fontsize={WM_FONT_SIZE}:fontcolor=white:"
                            "bordercolor=black:borderw=3:"
                            "x=(w-text_w)/2:"
                            f"y={phone_y_expr}"
                        )

                    if brand:
                        filters.append(
                            "drawtext="
                            f"text='{brand}':fontfile='{FONT_FILE}':"
                            f"fontsize={WM_FONT_SIZE}:fontcolor=yellow:"
                            "bordercolor=black:borderw=3:"
                            "x=(w-text_w)/2:"
                            f"y={brand_y_expr}"
                        )

                filters.extend(make_subtitle_filters(
                    subs=subs,
                    clip_start=clip_start,
                    still_dur=still,
                    subtitle_y=subtitle_y,
                    font_size=int(self.font_size.get()),
                    bg_on=self.subtitle_bg.get()
                ))

                filters.append("setsar=1,setdar=9/16,format=yuv420p")
                vf = ",".join(filters)

                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-i", img,
                    "-vf", vf,
                    "-t", f"{clip_len:.3f}",
                    "-r", str(FPS),
                    "-c:v", clip_vcodec,
                ] + clip_vextra + [
                    "-pix_fmt", "yuv420p",
                    clip
                ]

                if not self.run_ffmpeg(cmd, f"클립 {i+1}"):
                    raise Exception(f"클립 {i+1} 생성 실패")

            temp_video = os.path.join(temp_dir, "temp_video.mp4")
            if os.path.exists(temp_video):
                try:
                    os.remove(temp_video)
                except:
                    pass

            if self.use_transitions.get() and len(clip_files) > 1:
                effects = []
                for _ in range(len(clip_files) - 1):
                    effects.append(random.choice(TRANSITIONS) if self.random_transitions.get() else "fade")

                self.log("전환 효과: " + ", ".join(effects))

                input_files = []
                for c in clip_files:
                    input_files.extend(["-i", c])

                filter_lines = []
                for i in range(len(clip_files)):
                    filter_lines.append(f"[{i}:v]setpts=PTS-STARTPTS,setsar=1,setdar=9/16,format=yuv420p[v{i}]")

                prev = "v0"
                for i in range(1, len(clip_files)):
                    offset = i * still
                    filter_lines.append(
                        f"[{prev}][v{i}]xfade="
                        f"transition={effects[i-1]}:"
                        f"duration={trans:.3f}:"
                        f"offset={offset:.3f}[x{i}]"
                    )
                    prev = f"x{i}"

                fc = ";".join(filter_lines)

                xf_vcodec, xf_vextra = encoder_settings(prefer_gpu=True)

                cmd = ["ffmpeg", "-y"] + input_files + [
                    "-filter_complex", fc,
                    "-map", f"[{prev}]",
                    "-r", str(FPS),
                    "-c:v", xf_vcodec,
                ] + xf_vextra + [
                    "-pix_fmt", "yuv420p",
                    "-t", f"{audio_duration:.3f}",
                    temp_video
                ]

                ok = self.run_ffmpeg(cmd, "전환 합성")

                if (not ok) and XFADER_FALLBACK_TO_X264:
                    self.log("전환 합성 NVENC 실패, x264로 재시도")
                    xf_vcodec2, xf_vextra2 = encoder_settings(prefer_gpu=False)

                    cmd2 = ["ffmpeg", "-y"] + input_files + [
                        "-filter_complex", fc,
                        "-map", f"[{prev}]",
                        "-r", str(FPS),
                        "-c:v", xf_vcodec2,
                    ] + xf_vextra2 + [
                        "-pix_fmt", "yuv420p",
                        "-t", f"{audio_duration:.3f}",
                        temp_video
                    ]

                    ok = self.run_ffmpeg(cmd2, "전환 합성(x264 폴백)")

                if not ok:
                    raise Exception("전환 합성 실패")

            else:
                concat_file = os.path.join(temp_dir, "concat.txt")
                with open(concat_file, "w", encoding="utf-8") as f:
                    for c in clip_files:
                        f.write(f"file '{c.replace('\\', '/')}'\n")

                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", concat_file,
                    "-c:v", "copy",
                    temp_video
                ]

                if not self.run_ffmpeg(cmd, "클립 합치기"):
                    raise Exception("클립 합치기 실패")

            folder_name = os.path.basename(folder.rstrip("/\\"))
            output = os.path.join(out_dir, f"{folder_name}.mp4")

            cmd = [
                "ffmpeg", "-y",
                "-i", temp_video,
                "-i", self.mp3_file.get(),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", f"{audio_duration:.3f}",
                output
            ]

            if self.run_ffmpeg(cmd, "오디오 결합"):
                size = os.path.getsize(output) / (1024 * 1024)
                self.log(f"완료. 파일 크기 {size:.1f}MB")
                                # ✅ 완료 후: output(전처리 이미지) 폴더를 탐색기에서 열기 + 리포트 팝업(7초 후 자동 닫힘)
                try:
                    if os.name == "nt":
                        # 전처리 output 폴더 먼저
                        if PREPROCESS_ENABLE:
                            os.startfile(os.path.join(folder, PREPROCESS_SUBFOLDER))
                        os.startfile(out_dir)
                except:
                    pass

                elapsed = time.time() - start_time
                lines = []
                lines.append("작업 완료")
                lines.append("")
                lines.append(f"- 원본 이미지: {n}장")
                if PREPROCESS_ENABLE:
                    lines.append(f"- 전처리 이미지: {len(images)}장 (output 폴더)")
                    lines.append(f"- 전처리 폴더: {os.path.join(folder, PREPROCESS_SUBFOLDER)}")
                lines.append(f"- MP3 길이: {audio_duration:.2f}초")
                lines.append(f"- 자막 블록: {len(subs)}개")
                lines.append(f"- 전환: {trans:.2f}초")
                lines.append(f"- 이미지 유지: {still:.2f}초")
                lines.append("")
                lines.append(f"- 출력 파일: {output}")
                lines.append("")
                lines.append(f"총 작업시간: {elapsed:.1f}초")

                report = "\n".join(lines)
                show_auto_close_report("완료", report, auto_ms=7000)


                self.status_label.configure(text="완료")
            else:
                self.status_label.configure(text="실패")

            try:
                shutil.rmtree(temp_dir)
                self.log("임시 파일 정리 완료")
            except:
                pass

        except Exception as e:
            self.log(f"오류: {e}")
            messagebox.showerror("오류", str(e))
            self.status_label.configure(text="오류")

    def run(self):
        self.window.mainloop()

if __name__ == "__main__":
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except:
        messagebox.showerror("FFmpeg 필요", "FFmpeg가 설치되어 있지 않습니다.")
        sys.exit(1)

    app = SlideshowMaker()
    app.run()
