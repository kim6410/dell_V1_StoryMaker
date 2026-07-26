
"""
SLID_gpt_STABLE_v3_13_MOBILE_PORTRAIT_WM_STYLE (2026-03-03)
- 모바일 SNS 세로(1080x1920)
- 가로사진 잘림 방지: scale(decrease)+pad
- 워터마크: 상호(노랑,+4px) / 전화(흰,+2px) + 강한 음영/외곽선
- 컨트롤 센터 상단에 슬라이드 속도(초/장) 고정 옵션
- SRT 태그 제거 + SAR/DAR 통일 + 원패스 인코딩 + 진행률 UI
"""

import os, re, random, subprocess, time, threading, queue
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFile
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

ImageFile.LOAD_TRUNCATED_IMAGES = True
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# =============================================================================
# ✅ 컨트롤 센터(관리자 설정) - 여기만 수정하면 됩니다
# =============================================================================

# [A] 슬라이드 속도(초/장)
# 0  : 오디오 길이/이미지수 자동 계산
# >0 : 이미지당 표시 시간을 이 값으로 고정(초)
SLIDE_SEC_PER_IMAGE = 2.0   # 예: 2.8

# [B] 모바일 SNS 세로 출력
TARGET_W = 1080
TARGET_H = 1920
FPS = 25
BACKGROUND_COLOR = "black"  # pad 배경색

# [C] 워터마크 텍스트/스타일
WM_BRAND_TEXT = "강경 숯불바베큐"
WM_PHONE_TEXT = "0507-1393-5889"

WM_MARGIN_BOTTOM_PX = 60
WM_X_OFFSET_PX = 0
WM_Y_OFFSET_PX = 0

WM_FONT_BASE = 34
WM_BRAND_PLUS_PX = 4
WM_PHONE_PLUS_PX = 2

WM_BRAND_COLOR = (255, 211, 0, 255)   # 노란
WM_PHONE_COLOR = (255, 255, 255, 255) # 흰

WM_SHADOW_ENABLE = True
WM_SHADOW_COLOR = (0, 0, 0, 230)
WM_SHADOW_OFFSET = (2, 2)

WM_STROKE_ENABLE = True
WM_STROKE_WIDTH = 4
WM_STROKE_COLOR = (0, 0, 0, 255)

WM_BOX_ENABLE = True
WM_BOX_ALPHA = 120
WM_BOX_PAD_X = 22
WM_BOX_PAD_Y = int(14 * 1.20)  # ✅ 20% 크게

# 전처리 저장 품질(용량 절감)
JPG_QUALITY = 85
PREPROCESS_OVERWRITE = False

# [D] 전환/줌(가벼움+안정)
ZOOM_RATE_PER_SEC = 0.008
TRANS_MIN_SEC = 0.30
TRANS_MAX_SEC = 1.20
MIN_VISIBLE_HOLD_SEC = 0.90
FADEIN_SEC = 0.12
FADE_COLOR = "black"

COLOR_VARIATION = True
SAT_MIN, SAT_MAX = 0.97, 1.05
CON_MIN, CON_MAX = 0.98, 1.05

# 오디오
AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"

# 인코더
FINAL_ENCODER_PRIMARY = "h264_nvenc"
FINAL_NVENC_PRESET = "p4"
FINAL_ENCODER_FALLBACK = "libx264"
FINAL_X264_PRESET = "medium"
FINAL_X264_CRF = 20

FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"

OUTPUT_MP4_NAME = "slideshow_mobile.mp4"
NO_PROGRESS_KILL_SEC = 90

# =============================================================================


def _now():
    return time.strftime("%H:%M:%S")


def ui_log(qevt: queue.Queue, msg: str):
    print(msg)
    qevt.put(("log", f"[{_now()}] {msg}"))


def ui_progress(qevt: queue.Queue, stage: str, detail: str, percent: float):
    qevt.put(("progress", stage, detail, float(percent)))


def probe_audio_duration_seconds(audio_path: Path) -> float:
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


def escape_for_subtitles_filter_windows(p: Path) -> str:
    s = str(p).replace("\\", "/")
    s = re.sub(r"^([A-Za-z]):/", r"\1\\:/", s)  # D:/ -> D\:/
    s = s.replace("'", r"\\'")
    return s


def normalize_output_name(stem: str) -> str:
    stem = re.sub(r"^스크린샷\s*", "", stem)
    stem = re.sub(r"^KakaoTalk_", "", stem)
    stem = stem.strip()
    return stem if stem else "image"


def find_images(src_folder: Path):
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"]
    images = []
    for ptn in patterns:
        images += list(src_folder.glob(ptn))
        images += list(src_folder.glob(ptn.upper()))
    return sorted(set(images))


def _load_font(size: int):
    for fp in (r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\malgunsl.ttf", r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_text(draw: ImageDraw.ImageDraw, xy, text, font, fill, align="center"):
    x, y = xy
    if WM_SHADOW_ENABLE:
        sx, sy = WM_SHADOW_OFFSET
        draw.text((x + sx, y + sy), text, font=font, fill=WM_SHADOW_COLOR)
    if WM_STROKE_ENABLE and hasattr(draw, "text"):
        draw.text((x, y), text, font=font, fill=fill,
                  stroke_width=int(WM_STROKE_WIDTH), stroke_fill=WM_STROKE_COLOR)
    else:
        draw.text((x, y), text, font=font, fill=fill)


def preprocess_images(src_folder: Path, qevt: queue.Queue):
    src_folder = Path(src_folder)
    out_folder = src_folder / "output"
    out_folder.mkdir(exist_ok=True)

    images = find_images(src_folder)
    ui_log(qevt, f"원본 이미지 {len(images)}장")
    ui_log(qevt, f"✅ 전처리 이미지 저장 위치: {out_folder}")
    ui_log(qevt, "워터마크: 이미지에 내장(FFmpeg 워터마크는 비활성)")

    ok = 0
    skipped = 0

    brand_font = _load_font(int(WM_FONT_BASE + WM_BRAND_PLUS_PX))
    phone_font = _load_font(int(WM_FONT_BASE + WM_PHONE_PLUS_PX))

    for idx, img_path in enumerate(images, start=1):
        ui_progress(qevt, "전처리(워터마크)", f"{idx}/{len(images)} 처리 중", (idx / max(1, len(images))) * 20.0)

        new_stem = normalize_output_name(img_path.stem)
        out_path = out_folder / f"{new_stem}.jpg"

        if out_path.exists() and not PREPROCESS_OVERWRITE:
            try:
                if out_path.stat().st_mtime >= img_path.stat().st_mtime:
                    ok += 1
                    continue
            except Exception:
                pass

        try:
            img = Image.open(img_path).convert("RGBA")
        except Exception as e:
            skipped += 1
            ui_log(qevt, f"⚠ 이미지 읽기 실패(스킵): {img_path.name} / {e}")
            continue

        try:
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            w, h = img.size

            bb1 = draw.textbbox((0, 0), WM_BRAND_TEXT, font=brand_font)
            bb2 = draw.textbbox((0, 0), WM_PHONE_TEXT, font=phone_font)
            brand_w, brand_h = bb1[2] - bb1[0], bb1[3] - bb1[1]
            phone_w, phone_h = bb2[2] - bb2[0], bb2[3] - bb2[1]

            tw = max(brand_w, phone_w)
            gap = int(phone_h * 0.25)
            th = brand_h + gap + phone_h

            x = (w - tw) / 2 + WM_X_OFFSET_PX
            y = h - th - WM_MARGIN_BOTTOM_PX + WM_Y_OFFSET_PX

            if WM_BOX_ENABLE:
                pad_x, pad_y = int(WM_BOX_PAD_X), int(WM_BOX_PAD_Y)
                box = (int(x - pad_x), int(y - pad_y), int(x + tw + pad_x), int(y + th + pad_y))
                box = (max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3]))
                draw.rectangle(box, fill=(0, 0, 0, int(WM_BOX_ALPHA)))

            _draw_text(draw, ((w - brand_w) / 2 + WM_X_OFFSET_PX, y), WM_BRAND_TEXT, brand_font, WM_BRAND_COLOR)
            _draw_text(draw, ((w - phone_w) / 2 + WM_X_OFFSET_PX, y + brand_h + gap), WM_PHONE_TEXT, phone_font, WM_PHONE_COLOR)

            out_img = Image.alpha_composite(img, overlay).convert("RGB")
            out_img.save(out_path, quality=int(JPG_QUALITY), optimize=True)
            ok += 1
        except Exception as e:
            skipped += 1
            ui_log(qevt, f"⚠ 워터마크 처리 실패(스킵): {img_path.name} / {e}")
        finally:
            try:
                img.close()
            except Exception:
                pass

    processed = sorted(out_folder.glob("*.jpg"))
    ui_log(qevt, f"전처리 완료: 성공 {ok} / 스킵 {skipped} / 결과 {len(processed)}장")
    return out_folder, processed


def clean_srt_file(original_srt: Path, out_srt: Path, qevt: queue.Queue):
    if not original_srt:
        return None
    try:
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
        ui_log(qevt, f"✅ SRT 정리 완료: {out_srt.name}")
        return out_srt
    except Exception as e:
        ui_log(qevt, f"⚠ SRT 정리 실패(원본 사용): {e}")
        return original_srt


def build_filter_script(pre_imgs, seg_dur: float, fade_out_list, srt_path: Path | None):
    lines = []
    bg = BACKGROUND_COLOR

    for i in range(len(pre_imgs)):
        fade_out = float(fade_out_list[i])
        fo_start = max(0.0, seg_dur - fade_out)

        eq = ""
        if COLOR_VARIATION:
            sat = random.uniform(SAT_MIN, SAT_MAX)
            con = random.uniform(CON_MIN, CON_MAX)
            eq = f"eq=saturation={sat:.3f}:contrast={con:.3f},"

        # ✅ 잘림 방지: decrease+pad
        # ✅ 줌: 시간 기반 scale(가벼움) 후 다시 decrease+pad로 안전 정렬
        zoom = f"scale=iw*(1+{ZOOM_RATE_PER_SEC:.6f}*t):ih*(1+{ZOOM_RATE_PER_SEC:.6f}*t):eval=frame,"

        chain = (
            f"[{i}:v]"
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
            f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color={bg},"
            f"{zoom}"
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
            f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color={bg},"
            f"setsar=1,setdar={TARGET_W}/{TARGET_H},"
            f"{eq}"
            f"format=yuv420p,fps={FPS},"
            f"trim=duration={seg_dur:.3f},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d={FADEIN_SEC:.3f}:c={FADE_COLOR},"
            f"fade=t=out:st={fo_start:.3f}:d={fade_out:.3f}:c={FADE_COLOR}"
            f"[v{i}];"
        )
        lines.append(chain)

    inputs = "".join([f"[v{i}]" for i in range(len(pre_imgs))])
    lines.append(f"{inputs}concat=n={len(pre_imgs)}:v=1:a=0,setsar=1,setdar={TARGET_W}/{TARGET_H}[vcat];")

    if srt_path:
        srt_esc = escape_for_subtitles_filter_windows(srt_path)
        lines.append(f"[vcat]subtitles='{srt_esc}':charenc=UTF-8[vout];")
        vout = "[vout]"
    else:
        vout = "[vcat]"

    return "\n".join(lines), vout


def run_ffmpeg(cmd, qevt: queue.Queue, stage: str, base_pct: float, span_pct: float):
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
                    tick = (out_ms % 10_000_000) / 10_000_000
                    ui_progress(qevt, stage, "FFmpeg 인코딩 중(진행 신호)", base_pct + tick * span_pct)
                except Exception:
                    pass

            if time.time() - last_sig > NO_PROGRESS_KILL_SEC:
                tail_add(f"[KILL] no progress > {NO_PROGRESS_KILL_SEC}s")
                p.kill()
                break

        rc = p.wait()
        return rc, "\n".join(tail[-190:])
    finally:
        try:
            if p.stdout:
                p.stdout.close()
        except Exception:
            pass


def build_slideshow_onepass(pre_imgs, audio_path: Path, srt_path: Path | None, base_dir: Path, qevt: queue.Queue):
    total = len(pre_imgs)
    if total == 0:
        raise RuntimeError("전처리 이미지가 없습니다.")

    output_dir = base_dir / "OUTPUT"
    temp_dir = output_dir / "temp"
    output_dir.mkdir(exist_ok=True)
    temp_dir.mkdir(exist_ok=True)

    audio_len = probe_audio_duration_seconds(audio_path)
    if audio_len <= 0.0:
        audio_len = max(30.0, total * 2.0)

    if SLIDE_SEC_PER_IMAGE and SLIDE_SEC_PER_IMAGE > 0:
        seg_dur = float(SLIDE_SEC_PER_IMAGE)
        ui_log(qevt, f"슬라이드 속도: 고정 {seg_dur:.2f}초/장 (관리자 설정)")
    else:
        seg_dur = max(1.2, audio_len / max(1, total))
        ui_log(qevt, f"슬라이드 속도: 자동 {seg_dur:.2f}초/장")

    fade_out_list = []
    for _ in range(total):
        t = random.uniform(TRANS_MIN_SEC, TRANS_MAX_SEC)
        t = min(t, max(0.15, seg_dur - MIN_VISIBLE_HOLD_SEC))
        fade_out_list.append(t)

    ui_log(qevt, f"MP3 길이: {audio_len:.2f}초")
    ui_log(qevt, f"출력: {TARGET_W}x{TARGET_H} (모바일 세로) / FPS={FPS}")
    ui_log(qevt, f"전환(랜덤): {min(fade_out_list):.2f}~{max(fade_out_list):.2f}초 / 배경={BACKGROUND_COLOR}")
    ui_log(qevt, f"줌: 초당 {ZOOM_RATE_PER_SEC*100:.2f}% (scale 기반)")

    if srt_path:
        clean_path = temp_dir / (srt_path.stem + "__clean.srt")
        srt_path = clean_srt_file(srt_path, clean_path, qevt)

    script_text, vout_label = build_filter_script(pre_imgs, seg_dur, fade_out_list, srt_path)
    script_path = temp_dir / "filter_complex.txt"
    script_path.write_text(script_text, encoding="utf-8")

    out_final = output_dir / OUTPUT_MP4_NAME

    def make_cmd(encoder: str):
        cmd = [FFMPEG_BIN, "-hide_banner", "-y"]
        for img in pre_imgs:
            cmd += ["-loop", "1", "-t", f"{seg_dur:.3f}", "-i", str(img)]
        cmd += ["-i", str(audio_path)]
        cmd += ["-filter_complex_script", str(script_path)]
        cmd += ["-map", vout_label, "-map", f"{len(pre_imgs)}:a"]
        cmd += ["-r", str(FPS)]

        if encoder == "h264_nvenc":
            cmd += ["-c:v", "h264_nvenc", "-preset", FINAL_NVENC_PRESET, "-pix_fmt", "yuv420p"]
        else:
            cmd += ["-c:v", "libx264", "-preset", FINAL_X264_PRESET, "-crf", str(FINAL_X264_CRF), "-pix_fmt", "yuv420p"]

        cmd += ["-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE, "-shortest", str(out_final)]
        return cmd

    ui_progress(qevt, "최종 생성", "FFmpeg 원패스 인코딩 시작", 20.0)

    for name, enc in (("NVENC", FINAL_ENCODER_PRIMARY), ("x264", FINAL_ENCODER_FALLBACK)):
        ui_log(qevt, f"실행: {name}")
        rc, tail = run_ffmpeg(make_cmd(enc), qevt, stage="최종 생성", base_pct=20.0, span_pct=79.0)
        if rc == 0:
            ui_progress(qevt, "완료", f"완료: {out_final}", 100.0)
            ui_log(qevt, f"최종 결과: {out_final}")
            return out_final, output_dir, audio_len, seg_dur
        ui_log(qevt, f"⚠ 실패: {name} (rc={rc})")

    raise RuntimeError(f"최종 영상 생성 실패\n\n--- tail ---\n{tail[-4000:]}")


class AppUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("슬라이드쇼 생성기 (모바일 세로 v3_13)")
        self.root.geometry("860x560")
        self.root.attributes("-topmost", True)

        self.stage_var = tk.StringVar(value="대기")
        self.detail_var = tk.StringVar(value="")
        self.pct_var = tk.StringVar(value="0%")

        top = tk.Frame(self.root)
        top.pack(fill="x", padx=12, pady=10)
        tk.Label(top, textvariable=self.stage_var, font=("Malgun Gothic", 12, "bold")).pack(anchor="w")
        tk.Label(top, textvariable=self.detail_var, font=("Malgun Gothic", 10)).pack(anchor="w", pady=(4, 0))

        self.pb = ttk.Progressbar(self.root, orient="horizontal", length=820, mode="determinate", maximum=100)
        self.pb.pack(padx=12, pady=(8, 0))
        tk.Label(self.root, textvariable=self.pct_var, font=("Malgun Gothic", 10, "bold")).pack(anchor="e", padx=16, pady=(2, 8))

        box = tk.Frame(self.root)
        box.pack(fill="both", expand=True, padx=12, pady=8)
        tk.Label(box, text="진행 로그", font=("Malgun Gothic", 10, "bold")).pack(anchor="w")
        self.txt = tk.Text(box, wrap="word", height=19)
        self.txt.pack(fill="both", expand=True, pady=(6, 0))
        self.txt.insert("1.0", "준비 완료.\n")
        self.txt.config(state="disabled")

        self.btn = tk.Button(self.root, text="시작", command=self.start)
        self.btn.pack(pady=(0, 10))

        self.qevt = queue.Queue()
        self.worker = None
        self.root.after(120, self.poll_queue)

    def append_log(self, s: str):
        self.txt.config(state="normal")
        self.txt.insert("end", s + "\n")
        self.txt.see("end")
        self.txt.config(state="disabled")

    def set_progress(self, stage: str, detail: str, pct: float):
        pct = max(0.0, min(100.0, pct))
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
        audio_path = filedialog.askopenfilename(
            title="오디오 파일 선택",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac"), ("All files", "*.*")]
        )
        if not audio_path:
            return None, None, None

        srt_path = None
        if messagebox.askyesno("자막", "자막(SRT)을 영상에 넣을까요?"):
            picked = filedialog.askopenfilename(
                title="자막 SRT 선택",
                filetypes=[("SubRip", "*.srt"), ("All files", "*.*")]
            )
            if picked:
                srt_path = Path(picked)

        return Path(img_dir), Path(audio_path), srt_path

    def open_folder(self, folder: Path):
        try:
            folder = folder.resolve()
            if os.name == "nt":
                os.startfile(str(folder))
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception:
            pass

    def worker_run(self, img_dir: Path, audio_path: Path, srt_path: Path | None):
        t0 = time.time()
        try:
            ui_progress(self.qevt, "시작", "전처리 시작", 0.0)
            out_folder, pre_imgs = preprocess_images(img_dir, self.qevt)

            ui_progress(self.qevt, "시작", "최종 영상 생성(원패스)", 20.0)
            out_final, output_dir, audio_len, seg_dur = build_slideshow_onepass(
                pre_imgs, audio_path, srt_path, base_dir=img_dir, qevt=self.qevt
            )

            elapsed = time.time() - t0
            self.qevt.put(("done", str(out_final), str(out_folder), str(output_dir), audio_len, seg_dur, elapsed))
        except Exception as e:
            self.qevt.put(("error", str(e)))

    def start(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("진행중", "이미 작업이 진행 중입니다.")
            return

        img_dir, audio_path, srt_path = self.pick_inputs()
        if not img_dir or not audio_path:
            return

        self.btn.config(state="disabled")
        self.set_progress("준비", "작업 스레드 시작", 0.0)
        self.append_log("작업 시작.")
        self.worker = threading.Thread(target=self.worker_run, args=(img_dir, audio_path, srt_path), daemon=True)
        self.worker.start()

    def poll_queue(self):
        try:
            while True:
                evt = self.qevt.get_nowait()
                kind = evt[0]

                if kind == "log":
                    self.append_log(evt[1])
                elif kind == "progress":
                    _, stage, detail, pct = evt
                    self.set_progress(stage, detail, pct)
                elif kind == "done":
                    _, out_final, out_folder, output_dir, audio_len, seg_dur, elapsed = evt
                    self.append_log("완료.")
                    self.btn.config(state="normal")
                    self.set_progress("완료", "작업 완료", 100.0)

                    self.open_folder(Path(out_folder))
                    self.open_folder(Path(output_dir))

                    report = (
                        f"최종 파일: {out_final}\n\n"
                        f"전처리 폴더: {out_folder}\n"
                        f"OUTPUT 폴더: {output_dir}\n\n"
                        f"오디오 길이: {audio_len:.2f}초\n"
                        f"이미지당 표시시간: {seg_dur:.2f}초\n"
                        f"총 소요 시간: {elapsed:.2f}초\n"
                    )
                    pop = tk.Toplevel(self.root)
                    pop.title("작업 리포트")
                    pop.geometry("640x360")
                    pop.attributes("-topmost", True)
                    tk.Label(pop, text="완료", font=("Malgun Gothic", 12, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
                    t = tk.Text(pop, wrap="word", height=12)
                    t.pack(fill="both", expand=True, padx=12, pady=10)
                    t.insert("1.0", report)
                    t.config(state="disabled")
                    tk.Button(pop, text="확인", command=pop.destroy).pack(anchor="e", padx=12, pady=(0, 10))
                    pop.after(7000, pop.destroy)
                elif kind == "error":
                    _, err = evt
                    self.btn.config(state="normal")
                    self.set_progress("오류", "작업 중단", 0.0)
                    self.append_log("오류 발생.")
                    messagebox.showerror("오류", err)

        except queue.Empty:
            pass

        self.root.after(120, self.poll_queue)

    def run(self):
        self.root.mainloop()


def main():
    AppUI().run()


if __name__ == "__main__":
    main()
