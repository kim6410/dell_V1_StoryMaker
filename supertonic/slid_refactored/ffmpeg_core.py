from __future__ import annotations
from .core import *
from .core import _ts, _font_search_roots
from .image_pipeline import *
import sys
import shlex
import traceback

AUDIO_START_DELAY_SEC = 0.0

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

def _ass_black_box_colour(level_percent: int) -> str:
    """ASS용 반투명 검정 박스 색상.
    UI 0~100 값을 부드러운 반투명 곡선으로 매핑한다.
    0 = 박스 없음, 100도 완전 먹색이 아니라 약 38% 정도의 반투명 검정으로 제한한다.
    """
    level_percent = int(max(0, min(100, level_percent or 0)))
    if level_percent <= 0:
        return "&HFF000000"
    # 중간 구간이 더 잘 느껴지도록 완만한 감마 곡선 적용
    strength = (level_percent / 100.0) ** 1.35
    opacity = 0.38 * strength
    ass_alpha = int(round(255 * (1.0 - opacity)))  # 00=불투명, FF=투명
    ass_alpha = max(0, min(255, ass_alpha))
    return f"&H{ass_alpha:02X}000000"


def build_ass_force_style(settings: SubtitleSettings) -> str:
    box_alpha = int(max(0, min(100, getattr(settings, 'box_alpha', 0) or 0)))
    border_style = 3 if box_alpha > 0 else 1
    back = _ass_black_box_colour(box_alpha) if box_alpha > 0 else "&HFF000000"
    outline = int(max(0, getattr(settings, 'outline', 0) or 0))
    shadow = int(max(0, getattr(settings, 'shadow', 0) or 0))
    style = (
        f"FontName={settings.font_name},"
        f"FontSize={int(settings.font_size)},"
        f"Bold={1 if settings.bold else 0},"
        f"PrimaryColour={str(getattr(settings, 'primary_colour', '&H00FFFFFF')).rstrip('&')},"
        f"OutlineColour=&H00000000,"
        f"BackColour={back},"
        f"Outline={int(outline)},"
        f"Shadow={int(shadow)},"
        f"MarginV={int(settings.margin_v)},"
        f"BorderStyle={int(border_style)},"
        f"WrapStyle=0"
    )
    return style

# =============================================================================
# FFmpeg filter script
# =============================================================================



def ffmpeg_escape_filter_value(value: str) -> str:
    """filter_complex_script 안에서 fontfile/textfile 경로에 쓸 값을 안전하게 이스케이프한다."""
    s = str(value or '').replace('\\', '/')
    if re.match(r"^[A-Za-z]:/", s):
        s = s[0] + r"\:" + s[2:]
    s = s.replace("'", r"\'")
    s = s.replace('[', r"\[").replace(']', r"\]")
    s = s.replace(',', r"\,")
    s = s.replace(';', r"\;")
    return s


def ffmpeg_escape_drawtext_text(value: str) -> str:
    """drawtext=text=... 에 안전하게 넣기 위한 이스케이프."""
    s = str(value or '')
    s = s.replace('\\', r'\\\\')
    s = s.replace(':', r'\:')
    s = s.replace("'", r"\'")
    s = s.replace('%', r'\%')
    s = s.replace('[', r'\[').replace(']', r'\]')
    s = s.replace(',', r'\,')
    s = s.replace(';', r'\;')
    s = s.replace('\r\n', '\n').replace('\r', '\n').replace('\n', r'\n')
    return s


def _parse_srt_timecode(tc: str) -> float:
    tc = str(tc or '').strip().replace(',', '.')
    try:
        hh, mm, ss = tc.split(':')
        return int(hh) * 3600 + int(mm) * 60 + float(ss)
    except Exception:
        return 0.0


def _read_srt_entries(srt_path: Path) -> list[tuple[float, float, str]]:
    raw = None
    for enc in ('utf-8-sig', 'utf-8', 'cp949', 'euc-kr'):
        try:
            raw = srt_path.read_text(encoding=enc, errors='ignore')
            break
        except Exception:
            continue
    if raw is None:
        raw = srt_path.read_text(errors='ignore')
    raw = raw.replace('\r\n', '\n').replace('\r', '\n').strip()
    blocks = re.split(r'\n\s*\n', raw)
    entries = []
    for block in blocks:
        lines = [ln for ln in block.split('\n') if ln.strip() != '']
        if not lines:
            continue
        if len(lines) >= 2 and '-->' in lines[1]:
            time_line = lines[1]
            text_lines = lines[2:]
        elif '-->' in lines[0]:
            time_line = lines[0]
            text_lines = lines[1:]
        else:
            continue
        try:
            start_tc, end_tc = [x.strip() for x in time_line.split('-->')[:2]]
            start_s = _parse_srt_timecode(start_tc)
            end_s = _parse_srt_timecode(end_tc)
        except Exception:
            continue
        text_value = '\n'.join(t.strip() for t in text_lines).strip()
        if end_s > start_s and text_value:
            entries.append((start_s, end_s, text_value))
    return entries


def _wrap_subtitle_text(text_value: str, video_width: int, font_size: int) -> str:
    """긴 자막을 화면 폭에 맞게 1~2줄 중심으로 줄바꿈합니다."""
    text_value = str(text_value or '').replace('\r', '\n')
    raw_lines = [ln.strip() for ln in text_value.split('\n') if ln.strip()] or ['']

    usable_width = max(360, int(video_width * 0.92))
    approx_char_px = max(12, int(font_size * 0.52))
    max_chars = max(10, usable_width // approx_char_px)

    wrapped_lines: list[str] = []
    for raw in raw_lines:
        if len(raw) <= max_chars:
            wrapped_lines.append(raw)
            continue

        if ' ' in raw:
            import textwrap
            pieces = textwrap.wrap(raw, width=max_chars, break_long_words=False, break_on_hyphens=False)
            wrapped_lines.extend(pieces or [raw])
        else:
            start = 0
            while start < len(raw):
                wrapped_lines.append(raw[start:start + max_chars])
                start += max_chars

    return '\n'.join(wrapped_lines[:3]).strip()


def _rewrite_srt_with_wrapping(srt_in: Path, srt_out: Path, video_width: int, font_size: int) -> Path:
    """긴 SRT 문장을 출력 폭 기준으로 1~3줄로 적당히 나눠 다시 저장한다."""
    raw = None
    for enc in ('utf-8-sig', 'utf-8', 'cp949', 'euc-kr'):
        try:
            raw = srt_in.read_text(encoding=enc, errors='ignore')
            break
        except Exception:
            continue
    if raw is None:
        raw = srt_in.read_text(errors='ignore')
    raw = raw.replace('\r\n', '\n').replace('\r', '\n').strip()
    blocks = re.split(r'\n\s*\n', raw)
    out_blocks = []
    for block in blocks:
        lines = [ln for ln in block.split('\n') if ln.strip() != '']
        if not lines:
            continue
        idx_line = None
        time_line = None
        text_lines = []
        if len(lines) >= 2 and '-->' in lines[1]:
            idx_line = lines[0]
            time_line = lines[1]
            text_lines = lines[2:]
        elif '-->' in lines[0]:
            time_line = lines[0]
            text_lines = lines[1:]
        else:
            out_blocks.append(block)
            continue
        text_value = '\n'.join(text_lines).strip()
        wrapped = _wrap_subtitle_text(text_value, video_width, font_size) or text_value
        parts = []
        if idx_line is not None:
            parts.append(idx_line)
        parts.append(time_line)
        parts.extend(wrapped.split('\n'))
        out_blocks.append('\n'.join(parts))
    srt_out.write_text('\n\n'.join(out_blocks).strip() + '\n', encoding='utf-8')
    return srt_out


def _make_drawtext_subtitle_filter(video_in: Path, srt_path: Path, settings: AppSettings,
                                   input_label: str = '[0:v]', output_label: str = '[vout]') -> tuple[str, list[Path]]:
    sub = settings.subtitle
    font_path = find_preferred_font_file(False, getattr(sub, 'font_name', None))
    if not font_path:
        font_path = find_preferred_font_file(False)
    if not font_path:
        raise RuntimeError('자막용 폰트를 찾지 못했습니다.')

    ui_font_size = int(max(1, getattr(sub, 'font_size', 10) or 10))
    # Dell(libass subtitles)의 FontSize/MarginV 기준과 맞추기 위해 UI 값을 그대로 사용한다.
    # Mac mini는 subtitles 필터가 없어 PNG/drawtext 우회를 쓰지만, 화면상 크기/간격은 Dell 기준으로 통일한다.
    font_size = ui_font_size
    margin_v = int(max(0, getattr(sub, 'margin_v', 40) or 40))
    outline = float(max(0, getattr(sub, 'outline', 0) or 0))
    shadow = float(max(0, getattr(sub, 'shadow', 0) or 0))
    box_alpha = int(max(0, min(100, getattr(sub, 'box_alpha', 0) or 0)))
    box_enabled = box_alpha > 0
    boxcolor = f"black@{box_alpha / 100.0:.3f}"
    boxborderw = int(max(4, round(font_size * 0.34)))
    line_spacing = max(0, int(round(font_size * 0.16)))
    primary_color = 'white'

    entries = _read_srt_entries(srt_path)
    if not entries:
        raise RuntimeError('SRT 자막 항목을 읽지 못했습니다.')

    created_files: list[Path] = []
    filters = []
    last = input_label
    video_width = int(getattr(settings.video, 'width', 1080) or 1080)
    subtitle_dir = APP_TEMP_DIR / 'subtitle_texts'
    subtitle_dir.mkdir(parents=True, exist_ok=True)

    for idx, (start_s, end_s, text_value) in enumerate(entries):
        wrapped_text = _wrap_subtitle_text(text_value, video_width, ui_font_size)
        text_file = subtitle_dir / f'sub_{idx:04d}.txt'
        text_file.write_text(wrapped_text, encoding='utf-8')
        created_files.append(text_file)
        font_file_esc = escape_drawtext_path(font_path)
        text_file_esc = escape_drawtext_path(text_file)
        nxt = output_label if idx == len(entries) - 1 else f'[s{idx}]'
        one = (
            f"{last}drawtext=fontfile='{font_file_esc}':textfile='{text_file_esc}':reload=0:"
            f"fontcolor={primary_color}:fontsize={font_size}:line_spacing={line_spacing}:"
            f"x=(w-text_w)/2:y=h-text_h-{margin_v}:"
            f"borderw={outline:.2f}:bordercolor=black@1.0:"
            f"shadowx={shadow:.2f}:shadowy={shadow:.2f}:shadowcolor=black@1.0:"
            f"box={'1' if box_enabled else '0'}:boxcolor={boxcolor}:boxborderw={boxborderw}:"
            f"fix_bounds=1:text_shaping=1:alpha=1:"
            f"enable='between(t,{start_s:.3f},{end_s:.3f})'"
            f"{nxt}"
        )
        filters.append(one)
        last = nxt
    filter_script = ';\n'.join(filters)
    return filter_script, created_files


def _make_png_subtitle_overlays(srt_path: Path, settings: AppSettings) -> list[tuple[Path, float, float]]:
    sub = settings.subtitle
    entries = _read_srt_entries(srt_path)
    if not entries:
        raise RuntimeError('SRT 자막 항목을 읽지 못했습니다.')

    video_width = int(getattr(settings.video, 'width', 1080) or 1080)
    video_height = int(getattr(settings.video, 'height', 1920) or 1920)
    ui_font_size = int(max(1, getattr(sub, 'font_size', 10) or 10))
    # Mac mini는 subtitles/libass 필터가 없어 PNG 자막을 쓰므로 실제 화면 기준 보정이 필요하다.
    # Dell 공통값은 유지하고, Mac mini 전용 보정값은 환경변수로 따로 조절한다.
    mm_sub_boost = int(os.environ.get('SLID_MM_SUB_BOOST', '0') or 20)
    mm_sub_lift = int(os.environ.get('SLID_MM_SUB_LIFT', '95') or 95)
    mm_sub_width = int(os.environ.get('SLID_MM_SUB_WIDTH', '72') or 72)
    mm_sub_spacing = int(os.environ.get('SLID_MM_SUB_SPACING', '8') or 8)
    soft_shadow_style = str(os.environ.get('SLID_SUBTITLE_SHADOW_STYLE', '') or '').lower() == 'soft-wide'
    mm_sub_width = max(55, min(95, mm_sub_width))
    font_size = max(ui_font_size + mm_sub_boost, 1)
    margin_v = int(max(0, getattr(sub, 'margin_v', 40) or 40))
    outline = max(2, int(max(0, getattr(sub, 'outline', 1) or 1)))
    shadow = max(1, int(max(0, getattr(sub, 'shadow', 1) or 1)))
    wm = getattr(settings, 'video_watermark', getattr(settings, 'watermark', None))
    watermark_lift = mm_sub_lift
    if wm and (str(getattr(wm, 'brand_text', '') or '').strip() or str(getattr(wm, 'phone_text', '') or '').strip()):
        watermark_lift = int(getattr(wm, 'brand_font_size', 46) or 46) + int(getattr(wm, 'phone_font_size', 43) or 43) + int(os.environ.get('SLID_MM_WM_GAP', '25') or 6) + mm_sub_lift
    font_path = find_preferred_font_file(False, getattr(sub, 'font_name', None)) or find_preferred_font_file(False)
    font = ImageFont.truetype(str(font_path), font_size) if font_path else ImageFont.load_default()

    subtitle_dir = APP_TEMP_DIR / 'subtitle_pngs'
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    overlays: list[tuple[Path, float, float]] = []
    for idx, (start_s, end_s, text_value) in enumerate(entries):
        wrapped = _wrap_subtitle_text(text_value, int(video_width * (mm_sub_width / 100.0)), font_size)
        img = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        line_spacing = max(0, int(round(font_size * 0.16)))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=line_spacing, stroke_width=outline)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (video_width - text_w) // 2
        y = video_height - text_h - margin_v - watermark_lift
        if soft_shadow_style:
            shadow_layer = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            spread = max(8, int(round(font_size * 0.34)))
            shadow_draw.multiline_text((x, y), wrapped, font=font, fill=(0, 0, 0, 235), spacing=line_spacing, align='center', stroke_width=outline + spread, stroke_fill=(0, 0, 0, 235))
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=max(5, int(round(font_size * 0.20)))))
            img.alpha_composite(shadow_layer)
            core_shadow = max(2, int(round(font_size * 0.08)))
            draw.multiline_text((x + core_shadow, y + core_shadow), wrapped, font=font, fill=(0, 0, 0, 210), spacing=line_spacing, align='center', stroke_width=outline + 1, stroke_fill=(0, 0, 0, 210))
        elif shadow:
            draw.multiline_text((x + shadow, y + shadow), wrapped, font=font, fill=(0, 0, 0, 220), spacing=line_spacing, align='center')
        draw.multiline_text((x, y), wrapped, font=font, fill=(255, 255, 255, 255), spacing=line_spacing, align='center', stroke_width=outline, stroke_fill=(0, 0, 0, 255))
        out_png = subtitle_dir / f'sub_{idx:04d}.png'
        img.save(out_png)
        overlays.append((out_png, start_s, end_s))
    return overlays


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
    settings = normalize_settings_types(settings)
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

        fps = int(float(settings.video.fps))
        d = max(int(seg * fps), 2)
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
                f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={d}:s={vw}x{vh}:fps={fps},"
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
                f"fps={fps},trim=duration={seg:.3f},setpts=PTS-STARTPTS[v{i}];"
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
    preview_mp4: Path | None = None

def get_random_audio_from_folder(folder: Path) -> Optional[Path]:
    if not folder or not folder.exists(): return None
    audio_files = find_audio_files(folder)
    if not audio_files: return None
    return random.choice(audio_files)

def prepare_external_video_segments(media_files: list[Path], total_target_sec: float, settings: AppSettings, temp_folder: Path, qevt: queue.Queue) -> list[Path]:
    """외부 동영상을 9:16 클립으로 맞춰 temp 폴더에 생성"""
    prepared = []
    if not media_files or total_target_sec <= 0:
        return prepared

    count = len(media_files)
    each_target = max(0.5, total_target_sec / max(count, 1))
    speed = max(0.25, min(4.0, float(getattr(settings.media, "playback_speed", 1.0) or 1.0)))
    vw, vh = int(settings.video.width), int(settings.video.height)

    for idx, src in enumerate(media_files, start=1):
        out = temp_folder / f"ext_video_{idx:02d}.mp4"
        vf = (
            f"scale={vw}:{vh}:force_original_aspect_ratio=increase,"
            f"crop={vw}:{vh},setsar=1,setdar={vw}/{vh},"
            f"setpts=PTS/{speed:.6f},fps={int(settings.video.fps)},format=yuv420p"
        )
        cmd = [
            settings.encoding.ffmpeg_bin, "-hide_banner", "-y",
            "-i", str(src),
            "-an",
            "-t", f"{each_target:.3f}",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            str(out)
        ]
        qevt.put(("log", f"[{_ts()}] 🎞 외부 동영상 준비 {idx}/{count}: {src.name} -> {each_target:.2f}초 / 속도 {speed:.2f}x"))
        rc, tail = run_ffmpeg_with_progress(cmd, qevt, f"외부동영상 준비 {idx}", each_target, settings.encoding.no_progress_kill_sec)
        if rc == 0 and out.exists():
            prepared.append(out)
        else:
            qevt.put(("log", f"[{_ts()}] ⚠ 외부 동영상 준비 실패: {src.name} / {tail[-160:] if tail else '무응답'}"))
    return prepared



def _sum_segment_durations(paths: list[Path], ffprobe_bin: str) -> float:
    total = 0.0
    for pp in paths or []:
        try:
            total += max(0.0, probe_media_duration(pp, ffprobe_bin))
        except Exception:
            pass
    return total


def _delete_tree_with_retry(path: Path, retries: int = 6, delay_sec: float = 0.35) -> bool:
    if not path.exists():
        return True
    for attempt in range(retries):
        try:
            if path.is_dir():
                for sub in sorted(path.rglob('*'), key=lambda x: len(x.parts), reverse=True):
                    try:
                        if sub.is_file() or sub.is_symlink():
                            sub.unlink(missing_ok=True)
                        elif sub.is_dir():
                            sub.rmdir()
                    except Exception:
                        pass
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
            if not path.exists():
                return True
        except Exception:
            pass
        time.sleep(delay_sec)
    try:
        shutil.rmtree(path, ignore_errors=False)
    except Exception:
        pass
    return not path.exists()


def split_video_for_interleave(video_path: Path, split_count: int, total_duration: float, settings: AppSettings, temp_folder: Path, qevt: queue.Queue) -> list[Path]:
    """슬라이드 영상을 여러 구간으로 잘라 외부 동영상 사이에 섞을 수 있게 준비"""
    if split_count <= 1:
        return [video_path]

    actual_duration = probe_media_duration(video_path, settings.encoding.ffprobe_bin)
    work_duration = total_duration if total_duration and total_duration > 0 else actual_duration
    if actual_duration > 0:
        work_duration = min(work_duration, actual_duration) if work_duration > 0 else actual_duration
    if work_duration <= 0:
        return [video_path]

    # 균등 분할이 기본. 향후 유지보수를 위해 간단한 규칙 유지.
    chunk = work_duration / split_count
    segments = []
    for idx in range(split_count):
        start = idx * chunk
        dur = chunk if idx < split_count - 1 else max(0.05, work_duration - start)
        if dur <= 0.05:
            continue
        out = temp_folder / f"slide_part_{idx+1:02d}.mp4"
        cmd = [
            settings.encoding.ffmpeg_bin, "-hide_banner", "-y",
            "-ss", f"{start:.3f}",
            "-i", str(video_path),
            "-t", f"{dur:.3f}",
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(out)
        ]
        qevt.put(("log", f"[{_ts()}] ✂ 슬라이드 분할 {idx+1}/{split_count}: {dur:.2f}초"))
        rc, tail = run_ffmpeg_with_progress(cmd, qevt, f"슬라이드 분할 {idx+1}", max(0.5, dur), settings.encoding.no_progress_kill_sec)
        if rc == 0 and out.exists():
            segments.append(out)
        else:
            qevt.put(("log", f"[{_ts()}] ⚠ 슬라이드 분할 실패: {tail[-160:] if tail else '무응답'}"))
            return [video_path]
    return segments or [video_path]


def build_mixed_segment_order(slide_segments: list[Path], video_segments: list[Path], placement: str) -> list[Path]:
    """슬라이드와 외부 영상을 섞는 순서를 결정"""
    if not video_segments:
        return slide_segments
    if placement == "prepend_start":
        return list(video_segments) + list(slide_segments)
    if placement == "append_end":
        return list(slide_segments) + list(video_segments)

    # 기본: interleave
    ordered = []
    max_len = max(len(slide_segments), len(video_segments))
    for idx in range(max_len):
        if idx < len(slide_segments):
            ordered.append(slide_segments[idx])
        if idx < len(video_segments):
            ordered.append(video_segments[idx])
    return ordered


def concat_video_segments(segment_paths: list[Path], out_path: Path, settings: AppSettings, qevt: queue.Queue) -> bool:
    """구간 연결을 안정적으로 수행한다.

    기존의 -c copy concat은 입력 mp4들의 timebase / edit list / stream metadata가 조금만 달라도
    최종 길이가 짧아지거나 재생 지점이 틀어지는 문제가 있었다.
    지금 증상(49초 mp3인데 39초 mp4로 끊김)은 이 구간 연결 뒤 길이가 줄어드는 경우와도 잘 맞는다.
    그래서 여기서는 약간 느리더라도 concat demuxer 후 재인코딩으로 길이를 안정화한다.
    """
    if not segment_paths:
        return False
    list_path = out_path.with_suffix('.txt')
    def _quote_concat_path(pp: Path) -> str:
        return str(pp).replace("'", r"'\''")
    list_path.write_text("\n".join([f"file '{_quote_concat_path(p)}'" for p in segment_paths]), encoding='utf-8')
    total_dur = 0.0
    try:
        for segp in segment_paths:
            total_dur += max(0.0, probe_media_duration(segp, settings.encoding.ffprobe_bin))
    except Exception:
        total_dur = max(1.0, float(len(segment_paths)))
    cmd = [
        settings.encoding.ffmpeg_bin, "-hide_banner", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_path),
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out_path)
    ]
    rc, tail = run_ffmpeg_with_progress(cmd, qevt, "영상 구간 연결", max(1.0, total_dur), settings.encoding.no_progress_kill_sec)
    if rc == 0 and out_path.exists():
        try:
            dur = probe_media_duration(out_path, settings.encoding.ffprobe_bin)
            _log_q(qevt, f"[{_ts()}] 🔗 연결 영상 길이: {dur:.2f}초")
        except Exception:
            pass
    return rc == 0 and out_path.exists()


def mux_audio_to_video(video_path: Path, audio_path: Path, out_path: Path, settings: AppSettings, qevt: queue.Queue, target_len: float = 0.0) -> bool:
    """영상과 오디오를 합친다.

    핵심 수정:
    1) -shortest 제거: 더 짧은 영상 길이에 끌려 중간 종료되는 현상 방지
    2) 영상이 오디오보다 짧으면 tpad=clone 으로 마지막 프레임을 붙여 길이 연장
    3) 길이 로그를 남겨 문제 추적을 쉽게 함
    """
    delay_ms = int(max(0.0, AUDIO_START_DELAY_SEC) * 1000)
    video_len = probe_media_duration(video_path, settings.encoding.ffprobe_bin)
    audio_len = probe_audio_duration(audio_path, settings.encoding.ffprobe_bin)
    wanted_len = float(target_len or audio_len or video_len or 0.0)
    pad_sec = 0.0
    if wanted_len > 0 and video_len > 0 and video_len < wanted_len - 0.05:
        pad_sec = max(0.0, wanted_len - video_len)
    _log_q(qevt, f"[{_ts()}] 🎚️ 오디오 합치기 길이 확인: video={video_len:.2f}초 / audio={audio_len:.2f}초 / target={wanted_len:.2f}초 / pad={pad_sec:.2f}초")

    cmd = [
        settings.encoding.ffmpeg_bin, "-hide_banner", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
    ]
    if pad_sec > 0:
        cmd += [
            "-vf", f"tpad=stop_mode=clone:stop_duration={pad_sec:.3f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
        ]
    else:
        cmd += ["-c:v", "copy"]
    cmd += [
        "-c:a", settings.encoding.audio_codec,
        "-b:a", settings.encoding.audio_bitrate,
        "-movflags", "+faststart",
    ]
    if delay_ms > 0:
        cmd += ["-af", f"adelay={delay_ms}|{delay_ms}"]
    if wanted_len > 0:
        cmd += ["-t", f"{wanted_len:.3f}"]
    cmd += [str(out_path)]
    rc, tail = run_ffmpeg_with_progress(cmd, qevt, "오디오 합치기", max(1.0, wanted_len or audio_len or video_len or 1.0), settings.encoding.no_progress_kill_sec)
    return rc == 0 and out_path.exists()




def _log_q(qevt: queue.Queue, message: str):
    try:
        qevt.put(("log", message))
    except Exception:
        pass


def _select_audio_source(audio_path: Path, settings: AppSettings, qevt: queue.Queue) -> tuple[Path, str]:
    """오디오 랜덤 선택 옵션을 적용한 실제 오디오 파일 경로를 반환"""
    audio_used = str(audio_path)
    if getattr(settings.encoding, 'audio_random_enabled', False) and getattr(settings.encoding, 'audio_folder', ''):
        audio_folder = Path(settings.encoding.audio_folder)
        random_audio = get_random_audio_from_folder(audio_folder)
        if random_audio:
            audio_path = random_audio
            audio_used = str(random_audio)
            _log_q(qevt, f"[{_ts()}] 🎵 랜덤 선택된 오디오: {random_audio.name}")
    return audio_path, audio_used


def _probe_audio_length(audio_path: Path, settings: AppSettings, qevt: queue.Queue) -> float:
    audio_len = probe_audio_duration(audio_path, settings.encoding.ffprobe_bin)
    if audio_len <= 0:
        audio_len = 0.0
        _log_q(qevt, f"[{_ts()}] ⚠ 오디오 길이 측정 실패, 타임라인 기반으로 처리합니다.")
    return audio_len


def _prepare_media_plan(audio_len: float, settings: AppSettings, qevt: queue.Queue) -> dict:
    media_files = [Path(x) for x in getattr(settings.media, 'selected_files', []) if x and Path(x).exists()]
    media_enabled = bool(getattr(settings.media, 'enabled', False) and media_files and audio_len > 0)
    reserved_video_len = 0.0
    if media_enabled:
        reserved_video_len = clamp(
            audio_len * float(getattr(settings.media, 'target_ratio', 0.25) or 0.25),
            0.5,
            max(0.5, audio_len * 0.8),
        )
        _log_q(
            qevt,
            f"[{_ts()}] 🎞 외부 동영상 모드 활성화: {len(media_files)}개 / 전체의 {float(getattr(settings.media, 'target_ratio', 0.25))*100:.0f}% / 예약 {reserved_video_len:.2f}초",
        )
    effective_audio_len = audio_len - reserved_video_len if media_enabled else audio_len
    if media_enabled and effective_audio_len < 1.0:
        effective_audio_len = max(1.0, audio_len * 0.2)
        reserved_video_len = max(0.5, audio_len - effective_audio_len)
    return {
        'media_files': media_files,
        'media_enabled': media_enabled,
        'reserved_video_len': reserved_video_len,
        'actual_reserved_video_len': 0.0,
        'effective_audio_len': effective_audio_len,
        'prepared_segments': [],
    }


def _compute_timing(settings: AppSettings) -> tuple[float, float]:
    seg = float(settings.video.base_image_sec)
    fade = clamp(
        seg * float(settings.video.transition_ratio),
        settings.video.transition_min_sec,
        settings.video.transition_max_sec,
    )
    fade = min(fade, seg * 0.85)
    return seg, fade


def _video_length_from_count(count: int, seg: float, fade: float) -> float:
    return max(0.0, (count * seg) - (max(0, count - 1) * fade))


def _solve_exact_slide_timing(img_count: int, settings: AppSettings, target_len: float,
                              default_seg: float, default_fade: float, qevt: queue.Queue) -> tuple[float, float, float]:
    """오디오 길이 100% 기준으로 슬라이드 시간을 재분배한다.

    핵심 목표:
    - 남은 오디오 길이를 슬라이드가 정확히 채우게 한다.
    - 마지막 프레임 tpad 얼어붙음을 최소화한다.
    - 사용자가 정한 전환 비율 감각은 최대한 유지한다.
    """
    if img_count <= 0 or target_len <= 0:
        return default_seg, default_fade, _video_length_from_count(img_count, default_seg, default_fade)

    if img_count == 1:
        seg = max(0.20, float(target_len))
        return seg, 0.0, seg

    ratio = float(getattr(settings.video, 'transition_ratio', 0.35) or 0.35)
    tmin = float(getattr(settings.video, 'transition_min_sec', 0.35) or 0.35)
    tmax = float(getattr(settings.video, 'transition_max_sec', 1.50) or 1.50)

    def total_for_seg(seg: float) -> tuple[float, float]:
        fade = clamp(seg * ratio, tmin, tmax)
        fade = min(fade, seg * 0.85)
        total = _video_length_from_count(img_count, seg, fade)
        return total, fade

    lo = max(0.20, tmin / max(0.01, ratio), target_len / max(1, img_count * 6))
    hi = max(default_seg, target_len + tmax + 1.0, 1.0)
    total_hi, fade_hi = total_for_seg(hi)
    grow_guard = 0
    while total_hi < target_len and grow_guard < 24:
        hi *= 1.35
        total_hi, fade_hi = total_for_seg(hi)
        grow_guard += 1

    best_seg = default_seg
    best_fade = default_fade
    best_total = _video_length_from_count(img_count, best_seg, best_fade)

    for _ in range(48):
        mid = (lo + hi) / 2.0
        total_mid, fade_mid = total_for_seg(mid)
        best_seg, best_fade, best_total = mid, fade_mid, total_mid
        if abs(total_mid - target_len) <= 0.02:
            break
        if total_mid < target_len:
            lo = mid
        else:
            hi = mid

    _log_q(qevt, f"[{_ts()}] 🎯 오디오 100% 기준 자동 재분배: 슬라이드 {img_count}장 / 목표 {target_len:.2f}초 / 이미지당 {best_seg:.3f}초 / 전환 {best_fade:.3f}초 / 계산 {best_total:.2f}초")
    return best_seg, best_fade, best_total


def _expand_images_to_target_length(pre_imgs: list[Path], base_dir: Path, settings: AppSettings, qevt: queue.Queue,
                                    seg: float, fade: float, effective_audio_len: float) -> tuple[list[Path], int, int, float]:
    original_img_count = len(pre_imgs)
    base_video_len = _video_length_from_count(original_img_count, seg, fade)

    repeat_count = 1
    if effective_audio_len > 0 and base_video_len < effective_audio_len and base_video_len > 0:
        repeat_count = ceil(effective_audio_len / base_video_len)
        pre_imgs = build_cycle_shuffled_images(pre_imgs, repeat_count, settings.transition)
        _log_q(qevt, f"[{_ts()}] 🔄 이미지 반복 상세:")
        _log_q(qevt, f"  - 원본 이미지: {original_img_count}장")
        _log_q(qevt, f"  - 반복 횟수: {repeat_count}회")
        _log_q(qevt, f"  - 총 이미지: {len(pre_imgs)}장")
        calc_len = _video_length_from_count(len(pre_imgs), seg, fade)
        _log_q(qevt, f"  - 계산된 영상 길이: {calc_len:.2f}초")
        _log_q(qevt, f"  - 슬라이드 목표 길이: {effective_audio_len:.2f}초")
        if settings.transition.cycle_shuffle:
            _log_q(qevt, f"[{_ts()}] 🔀 회전마다 이미지 순서 랜덤 셔플 적용")

    final_video_len = _video_length_from_count(len(pre_imgs), seg, fade)

    if effective_audio_len > 0 and final_video_len < effective_audio_len - 0.5:
        _log_q(qevt, f"[{_ts()}] ⚠️ 경고: 영상 길이({final_video_len:.2f}초)가 목표({effective_audio_len:.2f}초)보다 짧습니다!")
        needed_extra = ceil((effective_audio_len - final_video_len) / max(0.1, (original_img_count * seg)))
        extra_repeat = needed_extra + 1
        _log_q(qevt, f"[{_ts()}] 🔄 추가 반복 {extra_repeat}회 적용")
        fresh_imgs = find_images(base_dir / 'output')
        if fresh_imgs:
            pre_imgs = build_cycle_shuffled_images(fresh_imgs, repeat_count + extra_repeat, settings.transition)
        else:
            extra_cycle = []
            original_slice = pre_imgs[:original_img_count]
            for _ in range(extra_repeat):
                if getattr(settings.transition, 'cycle_shuffle', False):
                    extra_cycle.extend(random.sample(original_slice, len(original_slice)))
                else:
                    extra_cycle.extend(original_slice)
            pre_imgs.extend(extra_cycle)
        final_video_len = _video_length_from_count(len(pre_imgs), seg, fade)
        repeat_count += extra_repeat
        _log_q(qevt, f"[{_ts()}]   - 수정 후 영상 길이: {final_video_len:.2f}초 (이미지 {len(pre_imgs)}장)")

    if effective_audio_len > 0 and pre_imgs:
        eff_len = _video_length_from_count(len(pre_imgs), seg, fade)
        while eff_len < effective_audio_len + 0.20:
            pre_imgs.append(pre_imgs[-1])
            eff_len = _video_length_from_count(len(pre_imgs), seg, fade)
        final_video_len = eff_len
        _log_q(qevt, f"[{_ts()}] ⏱️ (겹침 반영) 슬라이드 길이 보정: {final_video_len:.2f}초 / 목표: {effective_audio_len:.2f}초 (이미지 {len(pre_imgs)}장)")
    else:
        final_video_len = _video_length_from_count(len(pre_imgs), seg, fade)

    return pre_imgs, original_img_count, repeat_count, final_video_len


def _prepare_subtitle_path(srt_path: Path | None, temp_folder: Path, settings: AppSettings, qevt: queue.Queue) -> Path | None:
    if srt_path and settings.subtitle.enabled:
        clean_path = temp_folder / (srt_path.stem + '__clean.srt')
        try:
            cleaned = clean_srt(srt_path, clean_path)
            wrapped_path = temp_folder / (srt_path.stem + '__wrapped.srt')
            video_width = int(getattr(settings.video, 'width', 1080) or 1080)
            font_size = int(max(8, getattr(settings.subtitle, 'font_size', 28) or 28))
            srt_path = _rewrite_srt_with_wrapping(cleaned, wrapped_path, video_width, font_size)
            _log_q(qevt, f"[{_ts()}] ✅ SRT 정리 완료: {clean_path.name}")
            _log_q(qevt, f"[{_ts()}] ✅ SRT 줄넘김 보정 완료: {wrapped_path.name}")
        except Exception as e:
            _log_q(qevt, f"[{_ts()}] ⚠ SRT 정리 실패(원본 사용): {e}")
    return srt_path


def cleanup_project_artifacts(base_dir: Path, qevt: queue.Queue | None = None) -> list[Path]:
    """프로젝트 폴더 아래의 temp* / logs 폴더를 정리한다."""
    removed: list[Path] = []
    candidates: list[Path] = []
    for root_name in ('output', 'OUTPUT'):
        root = base_dir / root_name
        if root.exists():
            for child in root.iterdir():
                name = child.name.lower()
                if child.is_dir() and (name.startswith('temp') or name == 'logs'):
                    candidates.append(child)
            if not any(root.iterdir()):
                candidates.append(root)
    for extra_name in ('logs', 'temp_base_images'):
        extra = base_dir / extra_name
        if extra.exists():
            candidates.append(extra)

    seen: set[str] = set()
    ordered: list[Path] = []
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)

    for path in ordered:
        try:
            ok = _delete_tree_with_retry(path)
            if ok and not path.exists():
                removed.append(path)
                if qevt is not None:
                    _log_q(qevt, f"[{_ts()}] 🧹 작업폴더 정리: {path}")
            elif qevt is not None:
                _log_q(qevt, f"[{_ts()}] ⚠ 작업폴더 정리 미완료: {path}")
        except Exception as e:
            if qevt is not None:
                _log_q(qevt, f"[{_ts()}] ⚠ 작업폴더 정리 실패: {path} / {e}")

    for root_name in ('output', 'OUTPUT'):
        root = base_dir / root_name
        try:
            if root.exists() and not any(root.iterdir()):
                root.rmdir()
                removed.append(root)
                if qevt is not None:
                    _log_q(qevt, f"[{_ts()}] 🧹 빈 폴더 정리: {root}")
        except Exception:
            pass
    return removed


def _build_output_versions(settings: AppSettings) -> list[dict]:
    versions = []
    enc = settings.encoding
    if enc.out_sns_enabled:
        versions.append({
            'label': 'SNS',
            'nvenc_cq': int(enc.sns_nvenc_cq),
            'x264_crf': int(enc.sns_x264_crf),
            'audio_bitrate': str(enc.sns_audio_bitrate),
            'x264_preset': str(enc.sns_x264_preset),
            'nvenc_preset': str(enc.sns_nvenc_preset),
        })
    if enc.out_hq_enabled:
        versions.append({
            'label': 'HQ',
            'nvenc_cq': int(enc.hq_nvenc_cq),
            'x264_crf': int(enc.hq_x264_crf),
            'audio_bitrate': str(enc.hq_audio_bitrate),
            'x264_preset': str(enc.hq_x264_preset),
            'nvenc_preset': str(enc.hq_nvenc_preset),
        })
    if not versions:
        versions.append({
            'label': 'SNS',
            'nvenc_cq': int(enc.sns_nvenc_cq),
            'x264_crf': int(enc.sns_x264_crf),
            'audio_bitrate': str(enc.sns_audio_bitrate),
            'x264_preset': str(enc.sns_x264_preset),
            'nvenc_preset': str(enc.sns_nvenc_preset),
        })
    return versions


def _clone_settings_for_version(settings: AppSettings, label: str) -> AppSettings:
    import copy as _copy
    settings_local = _copy.deepcopy(settings)
    if label.upper() == 'SNS' and settings.encoding.sns_scale_down:
        settings_local.video.width = int(settings.encoding.sns_width)
        settings_local.video.height = int(settings.encoding.sns_height)
    return settings_local


def _make_ffmpeg_cmd(settings_local: AppSettings, pre_imgs: list[Path], seg: float, audio_path: Path, script_path_local: Path,
                     vout_label_local: str, encoder: str, out_mp4: Path, cfg: dict, qevt: queue.Queue,
                     audio_len: float, effective_audio_len: float, mux_audio: bool = True, target_duration: float | None = None) -> list[str]:
    cmd = [settings_local.encoding.ffmpeg_bin, '-hide_banner', '-y']
    for i, img in enumerate(pre_imgs):
        cmd += ['-loop', '1', '-t', f'{seg:.3f}', '-i', str(img)]
        if i < 3:
            _log_q(qevt, f"[{_ts()}] 📸 이미지 입력 {i+1}: {img.name}")
    if len(pre_imgs) > 3:
        _log_q(qevt, f"[{_ts()}] ... 외 {len(pre_imgs)-3}개 이미지")
    if mux_audio:
        cmd += ['-i', str(audio_path)]
    cmd += ['-filter_complex_script', str(script_path_local), '-map', vout_label_local]
    if mux_audio:
        cmd += ['-map', f'{len(pre_imgs)}:a']
    cmd += ['-r', str(settings_local.video.fps), '-fps_mode', 'cfr']
    if mux_audio and AUDIO_START_DELAY_SEC > 0:
        delay_ms = int(AUDIO_START_DELAY_SEC * 1000)
        cmd += ['-af', f'adelay={delay_ms}|{delay_ms}']
    if encoder == 'h264_nvenc':
        cmd += ['-c:v', 'h264_nvenc', '-preset', str(cfg.get('nvenc_preset', settings_local.encoding.nvenc_preset)), '-pix_fmt', 'yuv420p', '-cq', str(int(cfg.get('nvenc_cq', 28)))]
    else:
        cmd += ['-c:v', 'libx264', '-preset', str(cfg.get('x264_preset', settings_local.encoding.x264_preset)), '-crf', str(int(cfg.get('x264_crf', settings_local.encoding.x264_crf_optimized))), '-pix_fmt', 'yuv420p']
    if mux_audio:
        cmd += ['-c:a', settings_local.encoding.audio_codec, '-b:a', str(cfg.get('audio_bitrate', settings_local.encoding.audio_bitrate))]
    cmd += ['-movflags', '+faststart']
    use_len = target_duration if target_duration is not None else (audio_len if mux_audio else effective_audio_len)
    if use_len > 0:
        cmd += ['-t', f'{use_len:.3f}', str(out_mp4)]
    else:
        cmd += [str(out_mp4)]
    return cmd


def _encode_version_file(settings_local: AppSettings, cfg: dict, pre_imgs: list[Path], seg: float, fade: float,
                         audio_path: Path, out_mp4: Path, temp_folder: Path, qevt: queue.Queue,
                         audio_len: float, effective_audio_len: float, media_plan: dict) -> tuple[bool, str, str]:
    vlabel = str(cfg['label'])
    script_text, vout_label = build_filter_script_xfade(pre_imgs, seg, fade, None, settings_local)
    script_path = temp_folder / f'filter_complex_{vlabel}.txt'
    script_path.write_text(script_text, encoding='utf-8')
    _log_q(qevt, f"[{_ts()}] 📁 출력({vlabel}): {out_mp4.name}")
    qevt.put(('progress_enc', f'인코딩 준비 중... ({vlabel})', 0, audio_len, '0x'))
    tail = ''
    enc_used = ''
    for enc_label, enc_name in (('NVENC', settings_local.encoding.enc_primary), ('x264', settings_local.encoding.enc_fallback)):
        enc_used = enc_label
        _log_q(qevt, f"[{_ts()}] 실행: {enc_label} / {vlabel} (품질: NVENC cq {cfg.get('nvenc_cq')} | x264 crf {cfg.get('x264_crf')} / 오디오 {cfg.get('audio_bitrate')})")
        if media_plan['media_enabled']:
            slide_only_mp4 = temp_folder / f'slide_only_{vlabel}.mp4'
            rc, tail = run_ffmpeg_with_progress(
                _make_ffmpeg_cmd(settings_local, pre_imgs, seg, audio_path, script_path, vout_label, enc_name, slide_only_mp4, cfg, qevt, audio_len, effective_audio_len, mux_audio=False, target_duration=effective_audio_len),
                qevt, f'슬라이드 생성({vlabel})', effective_audio_len, settings_local.encoding.no_progress_kill_sec)
            if rc == 0 and slide_only_mp4.exists():
                ext_segments = list(media_plan.get('prepared_segments') or [])
                placement_mode = str(getattr(settings_local.media, 'placement', 'interleave') or 'interleave')
                if placement_mode == 'interleave' and ext_segments:
                    slide_segments = split_video_for_interleave(slide_only_mp4, len(ext_segments) + 1, effective_audio_len, settings_local, temp_folder, qevt)
                else:
                    slide_segments = [slide_only_mp4]
                ordered_segments = build_mixed_segment_order(slide_segments, ext_segments, placement_mode)
                concat_mp4 = temp_folder / f'concat_{vlabel}.mp4'
                if concat_video_segments(ordered_segments, concat_mp4, settings_local, qevt):
                    concat_len = probe_media_duration(concat_mp4, settings_local.encoding.ffprobe_bin)
                    _log_q(qevt, f"[{_ts()}] 🎬 최종 연결 길이 확인: concat={concat_len:.2f}초 / audio={audio_len:.2f}초")
                    rc = 0 if mux_audio_to_video(concat_mp4, audio_path, out_mp4, settings_local, qevt, target_len=audio_len) else 1
                else:
                    rc = 1
            else:
                rc = 1
        else:
            rc, tail = run_ffmpeg_with_progress(
                _make_ffmpeg_cmd(settings_local, pre_imgs, seg, audio_path, script_path, vout_label, enc_name, out_mp4, cfg, qevt, audio_len, effective_audio_len),
                qevt, f'최종 생성({vlabel})', audio_len, settings_local.encoding.no_progress_kill_sec)
        if rc == 0:
            return True, enc_used, tail
        _log_q(qevt, f"[{_ts()}] ⚠ 실패: {enc_label} / {vlabel} (rc={rc})")
    return False, enc_used, tail


def apply_watermark_and_subtitles(video_in: Path, srt_path: Path | None, video_out: Path, settings: AppSettings, qevt: queue.Queue, preview_out: Path | None = None) -> bool:
    """워터마크와 자막을 단 1회의 GPU 가속 인코딩 패스로 결합하여 처리합니다.
    최종 영상 filter_complex 안에서 watermark PNG를 overlay하고 자막 subtitles 필터와 단일 패스로 연결합니다.
    """
    wm = getattr(settings, 'video_watermark', getattr(settings, 'watermark', None))
    
    # 1. 워터마크 사용 여부 확인
    brand = str(getattr(wm, 'brand_text', '') or '').strip() if wm else ''
    phone = str(getattr(wm, 'phone_text', '') or '').strip() if wm else ''
    title = str(getattr(wm, 'title_text', '') or '').strip() if wm else ''
    subtitle = str(getattr(wm, 'subtitle_text', '') or '').strip() if wm else ''
    has_top = wm and ((bool(getattr(wm, 'title_enabled', False)) and bool(title)) or (bool(getattr(wm, 'subtitle_enabled', False)) and bool(subtitle)))
    has_wm = wm and (brand or phone or has_top)
    
    # 2. 자막 사용 여부 확인
    has_sub = srt_path and settings.subtitle.enabled and Path(srt_path).exists()
    
    # 둘 다 안 쓰면 복사 후 리턴
    if not has_wm and not has_sub:
        try:
            if video_in.resolve() != video_out.resolve():
                shutil.copy2(video_in, video_out)
            return video_out.exists()
        except Exception:
            return False

    dur = probe_media_duration(video_in, settings.encoding.ffprobe_bin) or 1.0
    
    # 커맨드 구성 시작
    cmd = [settings.encoding.ffmpeg_bin, '-hide_banner', '-y', '-i', str(video_in)]
    
    filter_graph = ""
    inputs_count = 1
    current_v = "[0:v]"
    subtitle_text_files: list[Path] = []
    subtitle_png_files: list[Path] = []
    
    # 워터마크 PNG 준비
    if has_wm:
        overlay_png = APP_TEMP_DIR / 'wm_overlay_video.png'
        if _build_video_watermark_png(video_in, settings, overlay_png):
            cmd += ['-i', str(overlay_png)]
            current_v = f"[0:v][{inputs_count}:v]overlay=0:0:format=auto"
            inputs_count += 1
        else:
            has_wm = False
            
    # 자막 필터 준비
    if has_sub:
        clean_srt_path = video_out.parent / f"{video_out.stem}__subtitle_clean.srt"
        try:
            clean_srt(Path(srt_path), clean_srt_path)
            
            if sys.platform == "darwin":
                overlays = _make_png_subtitle_overlays(clean_srt_path, settings)
                subtitle_png_files = [path for path, _, _ in overlays]
                start_index = inputs_count
                for png_path in subtitle_png_files:
                    cmd += ['-i', str(png_path)]
                    inputs_count += 1
                last = '[wm]' if has_wm else '[0:v]'
                png_filters = []
                for idx, (_png_path, start_s, end_s) in enumerate(overlays):
                    nxt = '[vout]' if idx == len(overlays) - 1 else f'[sp{idx}]'
                    png_filters.append(f"{last}[{start_index + idx}:v]overlay=0:0:enable='between(t,{start_s:.3f},{end_s:.3f})'{nxt}")
                    last = nxt
                subtitle_filter = ';'.join(png_filters)
                filter_graph = f"{current_v}[wm];{subtitle_filter}" if has_wm else subtitle_filter
            else:
                font_roots = _font_search_roots()
                fonts_dir = None
                for root in font_roots:
                    if root.exists():
                        fonts_dir = root
                        break

                sub = settings.subtitle
                font_name = str(getattr(sub, 'font_name', '') or '').strip() or 'Pretendard Bold'
                box_alpha = int(max(0, min(100, getattr(sub, 'box_alpha', 0) or 0)))
                border_style = 3 if box_alpha > 0 else 1
                outline = int(max(0, getattr(sub, 'outline', 0) or 0))
                shadow = int(max(0, getattr(sub, 'shadow', 0) or 0))
                style_items = {
                    'FontName': font_name,
                    'FontSize': int(max(1, getattr(sub, 'font_size', 10) or 10)),
                    'Bold': 1 if getattr(sub, 'bold', True) else 0,
                    'PrimaryColour': '&H00FFFFFF',
                    'OutlineColour': '&H00000000',
                    'BackColour': _ass_black_box_colour(box_alpha) if box_alpha > 0 else '&HFF000000',
                    'Outline': outline,
                    'Shadow': shadow,
                    'MarginV': int(max(0, getattr(sub, 'margin_v', 40) or 40)),
                    'MarginL': 70,
                    'MarginR': 70,
                    'Alignment': 2,
                    'BorderStyle': border_style,
                    'WrapStyle': 0,
                    'Encoding': 1,
                }
                force_style = ','.join(f"{k}={v}" for k, v in style_items.items())

                srt_esc = escape_subtitles_path_for_windows(clean_srt_path)
                sub_vf = f"subtitles=filename='{srt_esc}':charenc=UTF-8"
                if fonts_dir is not None:
                    sub_vf += f":fontsdir='{escape_subtitles_path_for_windows(Path(fonts_dir))}'"
                safe_force_style = force_style.replace("'", r"\'").replace(",", r"\,")
                sub_vf += f":force_style='{safe_force_style}'"

                if has_wm:
                    filter_graph = f"{current_v}[wm];[wm]{sub_vf}[vout]"
                else:
                    filter_graph = f"{current_v}{sub_vf}[vout]"
        except Exception as e:
            _log_q(qevt, f"[{_ts()}] ⚠ 자막 준비 실패(스킵): {e}")
            has_sub = False
            if has_wm:
                filter_graph = f"{current_v}[vout]"
    else:
        if has_wm:
            filter_graph = f"{current_v}[vout]"

    # 필터 그래프 추가 및 인코더 옵션 추가
    if filter_graph:
        if preview_out:
            filter_graph += ';[vout]split=2[vmain][vprev_base];[vprev_base]scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2[vprev]'
            cmd += ['-filter_complex', filter_graph, '-map', '[vmain]', '-map', '0:a?']
        else:
            cmd += ['-filter_complex', filter_graph, '-map', '[vout]', '-map', '0:a?']
    else:
        try:
            if video_in.resolve() != video_out.resolve():
                shutil.copy2(video_in, video_out)
            return video_out.exists()
        except Exception:
            return False
        
    if sys.platform == "darwin":
        cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28', '-c:a', 'aac', '-movflags', '+faststart', str(video_out)]
    else:
        cmd += ['-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '28', '-c:a', 'aac', '-movflags', '+faststart', str(video_out)]

    if preview_out:
        cmd += [
            '-map', '[vprev]', '-map', '0:a?',
            '-r', '24',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-b:v', '3M',
            '-maxrate', '4M',
            '-bufsize', '6M',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            str(preview_out),
        ]
    
    _log_q(qevt, f"[{_ts()}] 📝 단일 패스 후처리 시작 (워터마크: {has_wm}, 자막: {has_sub})")
    _log_q(qevt, f"[{_ts()}] 후처리 명령: {' '.join(shlex.quote(str(x)) for x in cmd)}")
    rc, tail = run_ffmpeg_with_progress(cmd, qevt, '후처리 인코딩', max(1.0, dur), settings.encoding.no_progress_kill_sec)
    
    # 임시 자막 파일 정리
    if has_sub:
        try:
            if clean_srt_path.exists():
                clean_srt_path.unlink()
            for text_file in subtitle_text_files:
                if text_file.exists():
                    text_file.unlink()
            for png_file in subtitle_png_files:
                if png_file.exists():
                    png_file.unlink()
        except Exception:
            pass
            
    ok = rc == 0 and video_out.exists() and (not preview_out or preview_out.exists())
    if not ok:
        _log_q(qevt, f"[{_ts()}] ⚠ 후처리 인코딩 실패. tail: {tail[-160:] if tail else ''}")
        if has_wm or has_sub:
            return False
        try:
            if video_in.resolve() != video_out.resolve():
                shutil.copy2(video_in, video_out)
            return video_out.exists()
        except Exception:
            return False
    return True

def _postprocess_version_output(out_mp4: Path, temp_folder: Path, vlabel: str, srt_path: Path | None,
                                settings_local: AppSettings, qevt: queue.Queue) -> tuple[Path, Path | None]:
    post_base = temp_folder / f'post_base_{vlabel}.mp4'
    try:
        if post_base.exists():
            post_base.unlink()
        shutil.move(str(out_mp4), str(post_base))
    except Exception:
        if out_mp4.exists() and not post_base.exists():
            shutil.copy2(str(out_mp4), str(post_base))
    final_target = out_mp4
    preview_target = out_mp4.with_name(f"{out_mp4.stem}.preview.mp4")
    post_ok = apply_watermark_and_subtitles(post_base, srt_path, final_target, settings_local, qevt, preview_target)
    if not post_ok:
        raise RuntimeError(f'후처리(워터마크 및 자막) 적용 실패 ({vlabel})')
    return final_target, preview_target if preview_target.exists() else None


def _encode_single_version(*, cfg: dict, pre_imgs: list[Path], seg: float, fade: float, audio_path: Path,
                           srt_path: Path | None, base_dir: Path, output_folder: Path, temp_folder: Path,
                           settings: AppSettings, qevt: queue.Queue, audio_len: float, effective_audio_len: float,
                           media_plan: dict, final_video_len: float, original_img_count: int, repeat_count: int,
                           audio_used: str, safe_name: str, timestamp: str) -> BuildReport:
    vlabel = str(cfg['label'])
    out_mp4 = output_folder / f'{safe_name}_{vlabel}_{timestamp}.mp4'
    settings_local = _clone_settings_for_version(settings, vlabel)
    ok, enc_label, tail = _encode_version_file(settings_local, cfg, pre_imgs, seg, fade, audio_path, out_mp4, temp_folder, qevt, audio_len, effective_audio_len, media_plan)
    if not ok:
        raise RuntimeError(f"최종 영상 생성 실패 ({vlabel})\n\n--- tail ---\n{tail}")
    final_target, preview_target = _postprocess_version_output(out_mp4, temp_folder, vlabel, srt_path, settings_local, qevt)
    file_size_mb = final_target.stat().st_size / (1024 * 1024) if final_target.exists() else 0.0
    final_len_for_report = audio_len if media_plan['media_enabled'] else final_video_len
    _log_q(qevt, f"[{_ts()}] ✅ 완료({vlabel}) / 파일 크기: {file_size_mb:.2f} MB")
    qevt.put(('progress_enc', f'인코딩 완료 ({vlabel})', 100, 0, '0x'))
    return BuildReport(
        output_mp4=final_target,
        version_label=vlabel,
        encoder_used=enc_label,
        video_quality=f"NVENC cq {cfg.get('nvenc_cq')} / x264 crf {cfg.get('x264_crf')}",
        audio_bitrate=str(cfg.get('audio_bitrate')),
        preprocess_folder=base_dir / 'output' / 'temp_base_images',
        output_folder=output_folder,
        temp_folder=temp_folder,
        audio_len=audio_len,
        video_len=final_len_for_report,
        seg=seg,
        fade=fade,
        elapsed=0.0,
        img_count=original_img_count,
        repeat_count=repeat_count,
        file_size_mb=file_size_mb,
        audio_used=audio_used,
        preview_mp4=preview_target,
    )

def build_video_onepass(pre_imgs: list[Path], audio_path: Path, srt_path: Path | None, 
                       base_dir: Path, settings: AppSettings, qevt: queue.Queue) -> list[BuildReport]:
    if not pre_imgs:
        raise RuntimeError("전처리 이미지가 없습니다.")

    settings = normalize_settings_types(settings)
    output_folder = base_dir / "OUTPUT"
    temp_folder = output_folder / "temp"
    output_folder.mkdir(exist_ok=True)
    temp_folder.mkdir(exist_ok=True)

    audio_path, audio_used = _select_audio_source(audio_path, settings, qevt)
    audio_len = _probe_audio_length(audio_path, settings, qevt)
    media_plan = _prepare_media_plan(audio_len, settings, qevt)
    if media_plan["media_enabled"]:
        prepared_segments = prepare_external_video_segments(
            media_plan["media_files"],
            media_plan["reserved_video_len"],
            settings,
            temp_folder,
            qevt,
        )
        actual_reserved = _sum_segment_durations(prepared_segments, settings.encoding.ffprobe_bin)
        media_plan["prepared_segments"] = prepared_segments
        media_plan["actual_reserved_video_len"] = actual_reserved
        if not prepared_segments or actual_reserved <= 0.05:
            media_plan["media_enabled"] = False
            media_plan["effective_audio_len"] = audio_len
            _log_q(qevt, f"[{_ts()}] ⚠ 외부 동영상 실제 길이를 확보하지 못해 슬라이드 전체 길이를 오디오 기준으로 다시 맞춥니다.")
        else:
            media_plan["effective_audio_len"] = max(1.0, audio_len - actual_reserved)
            _log_q(qevt, f"[{_ts()}] 🎞 외부 동영상 실제 길이 합계: {actual_reserved:.2f}초 / 슬라이드 목표 길이 재계산: {media_plan['effective_audio_len']:.2f}초")
    effective_audio_len = media_plan["effective_audio_len"]

    seg, fade = _compute_timing(settings)
    pre_imgs, original_img_count, repeat_count, final_video_len = _expand_images_to_target_length(
        pre_imgs, base_dir, settings, qevt, seg, fade, effective_audio_len
    )
    if effective_audio_len > 0 and pre_imgs:
        seg, fade, final_video_len = _solve_exact_slide_timing(len(pre_imgs), settings, effective_audio_len, seg, fade, qevt)

    _log_q(qevt, f"[{_ts()}] MP3 길이: {audio_len:.2f}초")
    _log_q(qevt, f"[{_ts()}] 최종 영상 길이: {final_video_len:.2f}초 (이미지 {len(pre_imgs)}장)")
    _log_q(qevt, f"[{_ts()}] 이미지당 표시: {seg:.2f}초")
    _log_q(qevt, f"[{_ts()}] 전환시간: {fade:.2f}초 (비율 {settings.video.transition_ratio:.2f})")

    if settings.video.zoom_center_only:
        _log_q(qevt, f"[{_ts()}] 🎯 느린 중앙 줌 적용 (강도: {settings.video.zoom_intensity})")
    elif settings.video.enable_zoompam:
        _log_q(qevt, f"[{_ts()}] ⚠️ 미세 줌팬 효과 적용 (강도: {settings.video.zoompam_intensity})")

    srt_path = _prepare_subtitle_path(srt_path, temp_folder, settings, qevt)

    safe_name = re.sub(r'[\/*?:"<>|]', "_", base_dir.name)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    versions = _build_output_versions(settings)

    reports: list[BuildReport] = []
    try:
        for cfg in versions:
            report = _encode_single_version(
                cfg=cfg,
                pre_imgs=pre_imgs,
                seg=seg,
                fade=fade,
                audio_path=audio_path,
                srt_path=srt_path,
                base_dir=base_dir,
                output_folder=output_folder,
                temp_folder=temp_folder,
                settings=settings,
                qevt=qevt,
                audio_len=audio_len,
                effective_audio_len=effective_audio_len,
                media_plan=media_plan,
                final_video_len=final_video_len,
                original_img_count=original_img_count,
                repeat_count=repeat_count,
                audio_used=audio_used,
                safe_name=safe_name,
                timestamp=timestamp,
            )
            reports.append(report)
        return reports
    finally:
        if getattr(settings.encoding, 'delete_temp_after_done', False):
            cleanup_project_artifacts(base_dir, qevt)


# =============================================================================
# 🎬 영상 프리뷰 플레이어 클래스 (자동 경로 탐색 + 자동 재생)
# =============================================================================

def find_preferred_font_file(is_brand: bool = True, font_name: str | None = None) -> Path | None:
    """공통 폰트 선택 로직을 그대로 재사용한다.
    예전 호출부와의 호환을 위해 font_name 인자를 추가로 받는다."""
    try:
        fp = find_font_file_by_name(font_name, is_brand=is_brand)
        if fp and Path(fp).exists():
            return Path(fp)
    except Exception:
        pass

    base = APP_FONT_DIR if 'APP_FONT_DIR' in globals() else Path(__file__).resolve().parent / "fonts"
    candidates = []
    if is_brand:
        candidates = [
            base / "Pretendard-ExtraBold.ttf",
            base / "Pretendard-ExtraBold.otf",
            base / "Pretendard-Bold.ttf",
            base / "Pretendard-Bold.otf",
            base / "Pretendard-Regular.ttf",
            base / "Pretendard-Regular.otf",
        ]
    else:
        candidates = [
            base / "Pretendard-Bold.ttf",
            base / "Pretendard-Bold.otf",
            base / "Pretendard-Regular.ttf",
            base / "Pretendard-Regular.otf",
            base / "Pretendard-ExtraBold.ttf",
            base / "Pretendard-ExtraBold.otf",
        ]
    for p in candidates:
        if p.exists():
            return p
    return None


def escape_drawtext_path(p: Path | str) -> str:
    """FFmpeg drawtext용 경로 이스케이프.
    윈도우 경로는 슬래시로 바꾸고, 드라이브 콜론만 한 번 이스케이프한다."""
    s = str(p).replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", s):
        s = s[0] + r"\:" + s[2:]
    s = s.replace("'", r"\'")
    s = s.replace("[", r"\[").replace("]", r"\]")
    s = s.replace(",", r"\,")
    return s

def escape_drawtext_text(s: str) -> str:
    """drawtext의 text= 값용 이스케이프."""
    s = str(s)
    s = s.replace("\\", r"\\")
    s = s.replace(":", r"\:")
    s = s.replace("'", r"\'")
    s = s.replace("%", r"\%")
    s = s.replace(",", r"\,")
    s = s.replace("[", r"\[").replace("]", r"\]")
    s = s.replace(";", r"\;")
    return s


def _write_drawtext_textfile(base_dir: Path, name: str, value: str) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    fp = base_dir / name
    fp.write_text(str(value or ""), encoding='utf-8')
    return fp


def _build_drawtext_filter(**kwargs) -> str:
    parts = []
    for key, value in kwargs.items():
        if value is None or value == '':
            continue
        parts.append(f"{key}={value}")
    return 'drawtext=' + ':'.join(parts)

def _build_watermark_drawtext_filters(wm, work_dir: Path, include_fontfile: bool = True) -> list[str]:
    brand_text = str(getattr(wm, 'brand_text', '') or '').strip()
    phone_text = str(getattr(wm, 'phone_text', '') or '').strip()
    if not brand_text and not phone_text:
        return []

    brand_font = find_preferred_font_file(True, getattr(wm, 'font_name', None)) if include_fontfile else None
    phone_font = find_preferred_font_file(False, getattr(wm, 'font_name', None)) if include_fontfile else None
    brand_size = int(max(16, getattr(wm, 'brand_font_size', 64)))
    phone_size = int(max(12, getattr(wm, 'phone_font_size', 42)))
    margin_bottom = int(max(0, getattr(wm, 'margin_bottom', 80)))
    x_offset = int(getattr(wm, 'x_offset', 0))
    y_offset = int(getattr(wm, 'y_offset', 0))
    gap = int(max(6, getattr(wm, 'phone_gap_px', 16)))

    filters = ['format=yuv420p']

    def append_text_filter(filename: str, text: str, fontfile, fontsize: int, y_expr: str, boxcolor: str, boxborderw: int):
        text_file = _write_drawtext_textfile(work_dir, filename, text)
        kwargs = {
            'textfile': f"'{escape_drawtext_path(text_file)}'",
            'fontfile': f"'{escape_drawtext_path(fontfile)}'" if fontfile else None,
            'fontsize': fontsize,
            'fontcolor': 'white',
            'x': f"(w-text_w)/2+({x_offset})",
            'y': y_expr,
        }
        if getattr(wm, 'box_enabled', True):
            kwargs.update({'box': 1, 'boxcolor': boxcolor, 'boxborderw': boxborderw})
        filters.append(_build_drawtext_filter(**kwargs))

    if brand_text:
        append_text_filter('brand_text.txt', brand_text, brand_font, brand_size, f"h-text_h-text_h-{phone_size}-{gap}-{margin_bottom}+({y_offset})", 'black@0.25', 14)
    if phone_text:
        append_text_filter('phone_text.txt', phone_text, phone_font, phone_size, f"h-text_h-{margin_bottom}+({y_offset})", 'black@0.22', 12)
    return filters


def build_video_watermark_filter(settings: AppSettings, work_dir: Path | None = None) -> str | None:
    wm = settings.watermark
    brand_text = str(getattr(wm, 'brand_text', '') or '').strip()
    phone_text = str(getattr(wm, 'phone_text', '') or '').strip()
    if not brand_text and not phone_text:
        return None

    brand_font = find_preferred_font_file(True, getattr(wm, 'font_name', None))
    phone_font = find_preferred_font_file(False, getattr(wm, 'font_name', None))
    brand_size = int(max(16, getattr(wm, 'brand_font_size', 64)))
    phone_size = int(max(12, getattr(wm, 'phone_font_size', 42)))
    margin_bottom = int(max(0, getattr(wm, 'margin_bottom', 80)))
    x_offset = int(getattr(wm, 'x_offset', 0))
    y_offset = int(getattr(wm, 'y_offset', 0))
    gap = int(max(6, getattr(wm, 'phone_gap_px', 16)))

    if work_dir is None:
        work_dir = APP_TEMP_DIR / 'drawtext'
    work_dir.mkdir(parents=True, exist_ok=True)

    filters = ['format=yuv420p']
    if brand_text:
        brand_text_file = _write_drawtext_textfile(work_dir, 'brand_text.txt', brand_text)
        kwargs = {
            'textfile': f"'{escape_drawtext_path(brand_text_file)}'",
            'fontfile': f"'{escape_drawtext_path(brand_font)}'" if brand_font else None,
            'fontsize': brand_size,
            'fontcolor': 'white',
            'x': f"(w-text_w)/2+({x_offset})",
            'y': f"h-text_h-text_h-{phone_size}-{gap}-{margin_bottom}+({y_offset})",
        }
        if getattr(wm, 'box_enabled', True):
            kwargs.update({'box': 1, 'boxcolor': 'black@0.25', 'boxborderw': 14})
        filters.append(_build_drawtext_filter(**kwargs))

    if phone_text:
        phone_text_file = _write_drawtext_textfile(work_dir, 'phone_text.txt', phone_text)
        kwargs = {
            'textfile': f"'{escape_drawtext_path(phone_text_file)}'",
            'fontfile': f"'{escape_drawtext_path(phone_font)}'" if phone_font else None,
            'fontsize': phone_size,
            'fontcolor': 'white',
            'x': f"(w-text_w)/2+({x_offset})",
            'y': f"h-text_h-{margin_bottom}+({y_offset})",
        }
        if getattr(wm, 'box_enabled', True):
            kwargs.update({'box': 1, 'boxcolor': 'black@0.22', 'boxborderw': 12})
        filters.append(_build_drawtext_filter(**kwargs))

    return ','.join(filters) if len(filters) > 1 else None


def _probe_video_size(video_in: Path, ffprobe_bin: str) -> tuple[int, int]:
    try:
        cmd = [ffprobe_bin, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0:s=x', str(video_in)]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8', 'ignore').strip()
        if 'x' in out:
            w, h = out.split('x', 1)
            return max(1, int(w)), max(1, int(h))
    except Exception:
        pass
    return 1080, 1920


def _build_video_watermark_png(video_in: Path, settings: AppSettings, out_png: Path) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    wm = getattr(settings, 'video_watermark', getattr(settings, 'watermark', None))
    if wm is None:
        return False
    brand = str(getattr(wm, 'brand_text', '') or '').strip()
    phone = str(getattr(wm, 'phone_text', '') or '').strip()
    title = str(getattr(wm, 'title_text', '') or '').strip()
    subtitle = str(getattr(wm, 'subtitle_text', '') or '').strip()
    has_top = (bool(getattr(wm, 'title_enabled', False)) and bool(title)) or (bool(getattr(wm, 'subtitle_enabled', False)) and bool(subtitle))
    if not brand and not phone and not has_top:
        return False
    width, height = _probe_video_size(video_in, settings.encoding.ffprobe_bin)
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    brand_font_path = find_preferred_font_file(True, getattr(wm, 'font_name', None))
    phone_font_path = find_preferred_font_file(False, getattr(wm, 'font_name', None))
    brand_size = int(max(16, getattr(wm, 'brand_font_size', 48)))
    phone_size = int(max(12, getattr(wm, 'phone_font_size', 40)))
    try:
        brand_font = ImageFont.truetype(str(brand_font_path), brand_size) if brand_font_path else ImageFont.load_default()
    except Exception:
        brand_font = ImageFont.load_default()
    try:
        phone_font = ImageFont.truetype(str(phone_font_path), phone_size) if phone_font_path else ImageFont.load_default()
    except Exception:
        phone_font = ImageFont.load_default()
    # Mac mini PNG 워터마크는 실제 bbox 기준으로 붙여 그리므로 기본 간격을 좁게 잡는다.
    # Dell/libass 기준 공통값은 유지하되, Mac mini 후처리에서는 환경변수로 별도 보정한다.
    mm_wm_gap = int(os.environ.get('SLID_MM_WM_GAP', str(getattr(wm, 'phone_gap_px', 25) or 25)) or 25)
    mm_wm_lift = int(os.environ.get('SLID_MM_WM_LIFT', '0') or 0)
    gap = int(max(0, mm_wm_gap))
    margin_bottom = int(max(0, getattr(wm, 'margin_bottom', 80) or 80))
    x_offset = int(getattr(wm, 'x_offset', 0) or 0)
    y_offset = int(getattr(wm, 'y_offset', 0) or 0) - mm_wm_lift
    bb_brand = draw.textbbox((0, 0), brand or ' ', font=brand_font)
    bb_phone = draw.textbbox((0, 0), phone or ' ', font=phone_font)
    bw, bh = bb_brand[2] - bb_brand[0], bb_brand[3] - bb_brand[1]
    pw, ph = bb_phone[2] - bb_phone[0], bb_phone[3] - bb_phone[1]
    total_h = (bh if brand else 0) + (ph if phone else 0) + (gap if brand and phone else 0)
    shade_enabled = bool(getattr(wm, 'box_enabled', True))
    shade_alpha = int(max(0, min(255, getattr(wm, 'box_alpha', 70) or 70)))
    shade_mult = float(max(1.0, getattr(wm, 'box_height_multiplier', 3.0) or 3.0))
    if shade_enabled:
        grad_h = int(total_h * shade_mult)
        grad_y = height - grad_h - int(margin_bottom * 0.3) + y_offset
        for i in range(max(1, grad_h)):
            alpha = int(shade_alpha * (1 - i / max(1, grad_h)))
            y = grad_y + i
            if 0 <= y < height:
                draw.rectangle([0, y, width, y + 1], fill=(0, 0, 0, alpha))
    start_y = height - total_h - margin_bottom + y_offset
    def _draw_text_center(text, font, y, fill_hex):
        if not text:
            return
        fill_rgba = hex_to_rgba(fill_hex)
        stroke_rgba = hex_to_rgba(getattr(wm, 'stroke_color', '#000000'))
        shadow_rgba = hex_to_rgba(getattr(wm, 'shadow_color', '#000000'))
        bb = draw.textbbox((0, 0), text, font=font)
        tw = bb[2] - bb[0]
        x = (width - tw) / 2 + x_offset
        if getattr(wm, 'shadow_enabled', True):
            draw.text((x + getattr(wm, 'shadow_offset_x', 2), y + getattr(wm, 'shadow_offset_y', 2)), text, font=font, fill=shadow_rgba)
        if getattr(wm, 'stroke_enabled', True):
            draw.text((x, y), text, font=font, fill=fill_rgba, stroke_width=max(1, int(getattr(wm, 'stroke_width', 4))), stroke_fill=stroke_rgba)
        else:
            draw.text((x, y), text, font=font, fill=fill_rgba)
    def _draw_top_center(text, font, y, fill_hex):
        if not text:
            return y
        fill_rgba = hex_to_rgba(fill_hex)
        stroke_rgba = hex_to_rgba(getattr(wm, 'stroke_color', '#000000'))
        shadow_rgba = hex_to_rgba(getattr(wm, 'shadow_color', '#000000'))
        bb = draw.textbbox((0, 0), text, font=font)
        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]
        x = (width - tw) / 2 + x_offset
        if getattr(wm, 'shadow_enabled', True):
            draw.text((x + getattr(wm, 'shadow_offset_x', 2), y + getattr(wm, 'shadow_offset_y', 2)), text, font=font, fill=shadow_rgba)
        if getattr(wm, 'stroke_enabled', True):
            draw.text((x, y), text, font=font, fill=fill_rgba, stroke_width=max(1, int(getattr(wm, 'stroke_width', 4))), stroke_fill=stroke_rgba)
        else:
            draw.text((x, y), text, font=font, fill=fill_rgba)
        return y + th
    top_y = int(getattr(wm, 'title_margin_top', 80) or 80)
    title = str(getattr(wm, 'title_text', '') or '').strip()
    subtitle = str(getattr(wm, 'subtitle_text', '') or '').strip()
    if getattr(wm, 'title_enabled', False) and title:
        title_font_path = find_preferred_font_file(True, getattr(wm, 'font_name', None))
        try:
            title_font = ImageFont.truetype(str(title_font_path), int(max(16, getattr(wm, 'title_font_size', 54)))) if title_font_path else ImageFont.load_default()
        except Exception:
            title_font = ImageFont.load_default()
        top_y = _draw_top_center(title, title_font, top_y, getattr(wm, 'title_color', '#FFFFFF'))
    if getattr(wm, 'subtitle_enabled', False) and subtitle:
        subtitle_font_path = find_preferred_font_file(False, getattr(wm, 'font_name', None))
        try:
            subtitle_font = ImageFont.truetype(str(subtitle_font_path), int(max(14, getattr(wm, 'subtitle_font_size', 34)))) if subtitle_font_path else ImageFont.load_default()
        except Exception:
            subtitle_font = ImageFont.load_default()
        top_y += int(getattr(wm, 'subtitle_gap_px', 14) or 14)
        _draw_top_center(subtitle, subtitle_font, top_y, getattr(wm, 'subtitle_color', '#DDE7FF'))

    # Mac mini PNG 워터마크는 두 줄 묶음 높이 기준으로 배치해 상호/전화번호 간격이 벌어지지 않게 한다.
    y = start_y
    if brand:
        _draw_text_center(brand, brand_font, y, getattr(wm, 'brand_color', '#FFD300'))
        y += bh + (gap if phone else 0)
    if phone:
        _draw_text_center(phone, phone_font, y, getattr(wm, 'phone_color', '#FFFFFF'))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return out_png.exists()
# Note: Legacy, unused functions apply_watermark_to_video and apply_subtitles_to_video
# have been removed. All watermark and subtitle processing are now performed
# in a single pass in apply_watermark_and_subtitles to avoid multiple re-encodes.
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
