from __future__ import annotations
from .core import *
from .core import _ts

def build_reflection_canvas(src: Image.Image, settings: AppSettings) -> Image.Image:
    """강한 블러 배경 위에 선명한 원본을 살짝 작게 올려 반사배경 느낌을 만듭니다."""
    src = ImageOps.exif_transpose(src).convert("RGBA")
    cw, ch = src.size
    refl = getattr(settings, "reflection", None)
    strength = float(getattr(refl, "strength", 1.6) or 1.6)
    blur_radius = int(getattr(refl, "blur_radius", 55) or 55)
    dim = float(getattr(refl, "dim", 0.72) or 0.72)

    bg = src.copy().resize((max(1, int(cw * strength)), max(1, int(ch * strength))), Image.BICUBIC)
    bg = ImageOps.fit(bg, (cw, ch), method=Image.BICUBIC)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=max(0, blur_radius)))
    bg = ImageEnhance.Brightness(bg).enhance(max(0.25, min(1.5, dim)))
    bg = ImageEnhance.Contrast(bg).enhance(1.06)
    bg = ImageEnhance.Color(bg).enhance(1.03)

    fg_ratio = max(0.72, 0.96 - ((strength - 1.0) * 0.10))
    fg_w = max(1, int(cw * fg_ratio))
    fg_h = max(1, int(ch * fg_ratio))
    fg = src.resize((fg_w, fg_h), Image.BICUBIC)
    canvas = bg.copy()
    canvas.alpha_composite(fg, ((cw - fg_w) // 2, (ch - fg_h) // 2))
    return canvas



def _effective_top_text(obj, *fallback_objs):
    if obj is None:
        return False, '', False, ''
    title_enabled = bool(getattr(obj, 'title_enabled', False))
    subtitle_enabled = bool(getattr(obj, 'subtitle_enabled', False))
    title = str(getattr(obj, 'title_text', '') or '').strip()
    subtitle = str(getattr(obj, 'subtitle_text', '') or '').strip()
    if (title_enabled and title) or (subtitle_enabled and subtitle):
        return title_enabled, title, subtitle_enabled, subtitle
    for fb in fallback_objs:
        if fb is None:
            continue
        fb_title_enabled = bool(getattr(fb, 'title_enabled', False))
        fb_subtitle_enabled = bool(getattr(fb, 'subtitle_enabled', False))
        fb_title = str(getattr(fb, 'title_text', '') or '').strip()
        fb_subtitle = str(getattr(fb, 'subtitle_text', '') or '').strip()
        if (fb_title_enabled and fb_title) or (fb_subtitle_enabled and fb_subtitle):
            return fb_title_enabled, fb_title, fb_subtitle_enabled, fb_subtitle
    return title_enabled, title, subtitle_enabled, subtitle
def draw_watermark(canvas: Image.Image, settings: AppSettings) -> Image.Image:
    """워터마크 그리기 (배경박스를 하단 그라데이션으로 재활용)"""
    wm = getattr(settings, "image_watermark", getattr(settings, "watermark", None))

    canvas = canvas.convert("RGBA")
    cw, ch = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    short_side = max(1, min(cw, ch))
    scale = short_side / 1080.0

    brand_font = load_font(max(12, int(wm.brand_font_size * scale)), is_brand=True, font_name=getattr(wm, "font_name", None))
    phone_font = load_font(max(12, int(wm.phone_font_size * scale)), is_brand=False, font_name=getattr(wm, "font_name", None))

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

def _draw_text_block(draw, text, font, y, canvas_w, fill_hex, wm, scale=1.0):
    if not str(text or '').strip():
        return y
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    tx = (canvas_w - tw) / 2 + int(getattr(wm, 'x_offset', 0) * scale)
    fill_rgba = hex_to_rgba(fill_hex)
    stroke_rgba = hex_to_rgba(getattr(wm, 'stroke_color', '#000000'))
    shadow_rgba = hex_to_rgba(getattr(wm, 'shadow_color', '#000000'))
    if getattr(wm, 'shadow_enabled', True):
        draw.text((tx + int(getattr(wm, 'shadow_offset_x', 2) * scale), y + int(getattr(wm, 'shadow_offset_y', 2) * scale)), text, font=font, fill=shadow_rgba)
    if getattr(wm, 'stroke_enabled', True):
        draw.text((tx, y), text, font=font, fill=fill_rgba, stroke_width=max(1, int(getattr(wm, 'stroke_width', 4) * scale)), stroke_fill=stroke_rgba)
    else:
        draw.text((tx, y), text, font=font, fill=fill_rgba)
    return y + th

def draw_top_text(canvas: Image.Image, wm) -> Image.Image:
    canvas = canvas.convert('RGBA')
    overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cw, ch = canvas.size
    short_side = max(1, min(cw, ch))
    scale = short_side / 1080.0
    title_enabled, title, subtitle_enabled, subtitle = _effective_top_text(wm)
    y = int(getattr(wm, 'title_margin_top', 80) * scale) + int(getattr(wm, 'y_offset', 0) * scale)
    if title_enabled and title:
        title_font = load_font(max(16, int(getattr(wm, 'title_font_size', 54) * scale)), True, getattr(wm, 'font_name', None))
        y = _draw_text_block(draw, title, title_font, y, cw, getattr(wm, 'title_color', '#FFFFFF'), wm, scale=scale)
    if subtitle_enabled and subtitle:
        y += int(getattr(wm, 'subtitle_gap_px', 14) * scale)
        subtitle_font = load_font(max(14, int(getattr(wm, 'subtitle_font_size', 34) * scale)), False, getattr(wm, 'font_name', None))
        _draw_text_block(draw, subtitle, subtitle_font, y, cw, getattr(wm, 'subtitle_color', '#DDE7FF'), wm, scale=scale)
    return Image.alpha_composite(canvas, overlay)

def generate_thumbnail_image(settings: AppSettings, out_path: Path | None = None) -> Path:
    thumb = getattr(settings, 'thumbnail', None)
    if thumb is None or not str(getattr(thumb, 'image_path', '') or '').strip():
        raise ValueError('썸네일용 이미지를 먼저 선택하세요.')
    src_path = Path(str(thumb.image_path))
    if not src_path.exists():
        raise FileNotFoundError(f'썸네일 이미지가 없습니다: {src_path}')
    src = ImageOps.exif_transpose(Image.open(src_path)).convert('RGBA')
    width, height = int(getattr(thumb, 'width', 1080)), int(getattr(thumb, 'height', 1920))

    bg = src.copy().resize((max(1, int(width * 1.25)), max(1, int(height * 1.25))), Image.LANCZOS)
    bg = ImageOps.fit(bg, (width, height), method=Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=max(20, int(getattr(settings.reflection, 'blur_radius', 55) or 55))))
    bg = ImageEnhance.Brightness(bg).enhance(0.62)
    bg = ImageEnhance.Contrast(bg).enhance(1.08)
    bg = ImageEnhance.Color(bg).enhance(1.04)

    fg = ImageOps.contain(src, (int(width * 0.92), int(height * 0.56)), method=Image.LANCZOS)
    canvas = bg.copy()
    canvas.alpha_composite(fg, ((width - fg.width) // 2, int(height * 0.26)))

    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    style = type('Style', (), {})()
    style.font_name = getattr(thumb, 'font_name', 'Pretendard Bold')

    # 썸네일 전용 값이 비어 있으면 사진/영상 워터마크의 상단 문구를 부드럽게 이어받는다.
    # 새 기능 추가 직후 사용자가 기존 입력값만 넣어도 바로 결과가 보이도록 하기 위한 안전장치다.
    fallback_sources = [
        getattr(settings, 'thumbnail', None),
        getattr(settings, 'image_watermark', None),
        getattr(settings, 'video_watermark', None),
        getattr(settings, 'watermark', None),
    ]
    def _pick_attr(name: str, default=''):
        for obj in fallback_sources:
            if obj is None:
                continue
            value = getattr(obj, name, None)
            if isinstance(value, str):
                if value.strip():
                    return value
            elif value not in (None, ''):
                return value
        return default
    style.stroke_enabled = True; style.stroke_width = 5; style.stroke_color = '#000000'
    style.shadow_enabled = True; style.shadow_color = '#000000'; style.shadow_offset_x = 2; style.shadow_offset_y = 2
    style.x_offset = 0; style.y_offset = 0

    title_text = str(_pick_attr('title_text', '') or '').strip()
    subtitle_text = str(_pick_attr('subtitle_text', '') or '').strip()
    brand = str(_pick_attr('brand_text', '') or '').strip()
    phone = str(_pick_attr('phone_text', '') or '').strip()

    y = int(getattr(thumb, 'title_margin_top', 90))
    if getattr(thumb, 'title_enabled', True) and title_text:
        f1 = load_font(int(getattr(thumb, 'title_font_size', 88)), True, getattr(thumb, 'font_name', None))
        y = _draw_text_block(draw, title_text, f1, y, width, getattr(thumb, 'title_color', '#FFFFFF'), style)
    if getattr(thumb, 'subtitle_enabled', True) and subtitle_text:
        y += int(getattr(thumb, 'subtitle_gap_px', 18))
        f2 = load_font(int(getattr(thumb, 'subtitle_font_size', 46)), False, getattr(thumb, 'font_name', None))
        _draw_text_block(draw, subtitle_text, f2, y, width, getattr(thumb, 'subtitle_color', '#DDE7FF'), style)
    if brand or phone:
        grad_h = int((getattr(thumb, 'brand_font_size', 58) + getattr(thumb, 'phone_font_size', 50) + 50) * 2.8)
        grad_y = height - grad_h - int(getattr(thumb, 'margin_bottom', 90) * 0.3)
        for i in range(max(1, grad_h)):
            alpha = int(180 * (1 - i / max(1, grad_h)))
            yy = grad_y + i
            if 0 <= yy < height:
                draw.rectangle([0, yy, width, yy + 1], fill=(0, 0, 0, alpha))
        f3 = load_font(int(getattr(thumb, 'brand_font_size', 58)), True, getattr(thumb, 'font_name', None))
        f4 = load_font(int(getattr(thumb, 'phone_font_size', 50)), False, getattr(thumb, 'font_name', None))
        bb1 = draw.textbbox((0, 0), brand or ' ', font=f3)
        bb2 = draw.textbbox((0, 0), phone or ' ', font=f4)
        bh = bb1[3] - bb1[1]; ph = bb2[3] - bb2[1]
        gap = int(getattr(thumb, 'phone_gap_px', 10))
        total_h = (bh if brand else 0) + (ph if phone else 0) + (gap if brand and phone else 0)
        by = height - total_h - int(getattr(thumb, 'margin_bottom', 90))
        if brand:
            by = _draw_text_block(draw, brand, f3, by, width, getattr(thumb, 'brand_color', '#FFD300'), style)
        if phone:
            if brand:
                by += gap
            _draw_text_block(draw, phone, f4, by, width, getattr(thumb, 'phone_color', '#FFFFFF'), style)

    result = Image.alpha_composite(canvas, overlay).convert('RGB')
    if out_path is None:
        out_dir = BASE_DIR / 'output'
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"thumbnail_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    result.save(out_path, quality=95)
    return out_path

def resize_image_max_bounds(img: Image.Image, max_w: int = 1080, max_h: int = 1920) -> Image.Image:
    w, h = img.size
    ratio = min(max_w / w, max_h / h)
    if ratio < 1.0:
        new_w = max(1, int(w * ratio))
        new_h = max(1, int(h * ratio))
        try:
            resampling = Image.Resampling.BICUBIC
        except AttributeError:
            resampling = Image.BICUBIC
        return img.resize((new_w, new_h), resampling)
    return img

def preprocess_images(src_folder: Path, settings: AppSettings, qevt: queue.Queue, preview_only: bool = False):
    out_folder = src_folder / "output"
    temp_base_folder = out_folder / "temp_base_images"
    if not preview_only:
        out_folder.mkdir(exist_ok=True)
        temp_base_folder.mkdir(exist_ok=True)
    
    imgs = find_images(src_folder)
    if settings.transition.shuffle_images and not preview_only:
        random.shuffle(imgs)
    
    if preview_only:
        if not imgs: return None, None
        try:
            src = ImageOps.exif_transpose(Image.open(imgs[0])).convert("RGB")
            src = resize_image_max_bounds(src, 1080, 1920)
            canvas = build_reflection_canvas(src, settings)
            canvas = draw_top_text(canvas, settings.image_watermark)
            canvas = draw_watermark(canvas, settings)
            return canvas.convert("RGB"), imgs[0].name
        except Exception as e:
            safe_print(f"프리뷰 실패: {e}")
            return None, None
    
    qevt.put(("log", f"[{_ts()}] 원본 이미지 {len(imgs)}장"))
    qevt.put(("log", f"[{_ts()}] ✅ 슬라이드용 이미지 저장 위치: {temp_base_folder}"))
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import os
    
    max_workers = min(16, os.cpu_count() or 4)
    qevt.put(("log", f"[{_ts()}] ⚡ 이미지 병렬 전처리 시작 (스레드 수: {max_workers})"))
    
    ok, skip = 0, 0
    total = len(imgs)
    start_time = time.time()
    
    def process_single_image(p: Path) -> tuple[bool, str | None]:
        new_stem = normalize_output_stem(p.stem)
        out_path = temp_base_folder / f"{new_stem}.jpg"
        
        if out_path.exists() and not settings.encoding.preprocess_overwrite:
            try:
                if out_path.stat().st_mtime >= p.stat().st_mtime:
                    return True, None
            except Exception:
                pass
        
        src_img = None
        try:
            src_img = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            src_img = resize_image_max_bounds(src_img, 1080, 1920)
            canvas = build_reflection_canvas(src_img, settings)
            canvas_rgb = canvas.convert("RGB")
            canvas_rgb.save(out_path, quality=int(settings.encoding.pre_jpg_quality), optimize=True)
            return True, None
        except Exception as e:
            return False, f"⚠ 전처리 실패(스킵): {p.name} / {e}"
        finally:
            try:
                if src_img is not None:
                    src_img.close()
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_img = {executor.submit(process_single_image, p): p for p in imgs}
        
        for i, future in enumerate(as_completed(future_to_img), start=1):
            p = future_to_img[future]
            try:
                success, err_msg = future.result()
                if success:
                    ok += 1
                else:
                    skip += 1
                    if qevt is not None and err_msg:
                        qevt.put(("log", f"[{_ts()}] {err_msg}"))
            except Exception as e:
                skip += 1
                if qevt is not None:
                    qevt.put(("log", f"[{_ts()}] ⚠ 스레드 오류: {p.name} / {e}"))
            
            elapsed = time.time() - start_time
            progress = i / total if total else 1.0
            eta = (elapsed / progress) * (1 - progress) if progress > 0 else 0
            speed = format_speed(i, elapsed)
            
            if qevt is not None:
                qevt.put(("progress_pre", f"{i}/{total} 처리 중", progress * 100, eta, speed))
                
    out_imgs = sorted(temp_base_folder.glob("*.jpg"))
    if qevt is not None:
        qevt.put(("log", f"[{_ts()}] 전처리 완료: 성공 {ok} / 스킵 {skip} / 결과 {len(out_imgs)}장"))
    return temp_base_folder, out_imgs

# =============================================================================
# SRT 정리 + 스타일
# =============================================================================

