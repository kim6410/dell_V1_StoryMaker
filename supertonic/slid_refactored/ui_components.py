from __future__ import annotations
from .core import *
from fm_paths import find_vlc_executable
import time

class VideoPreviewPlayer(tk.Frame):
    """VLC 기반 영상 프리뷰 플레이어 (자동 경로 탐색)"""
    
    def __init__(self, parent, on_folder_open_callback=None, auto_play=False, get_initial_dir_callback=None, remember_path_callback=None):
        super().__init__(parent, bg="#1a1e2a", relief="flat", bd=1)
        self.parent = parent
        self.on_folder_open = on_folder_open_callback
        self.auto_play = auto_play
        self.get_initial_dir_cb = get_initial_dir_callback
        self.remember_path_cb = remember_path_callback
        
        # 외부 VLC 실행 전용
        self.vlc_path = self.find_vlc()
        self.vlc_available = bool(self.vlc_path and os.path.exists(self.vlc_path))
        self.instance = None
        self.player = None
        
        # 현재 재생 중인 파일
        self.current_video = None
        self.is_playing = False
        self.video_files = []  # 호환용(실제 목록은 아래 2개로 분리)
        self.output_video_files = []   # 생성된 출력 영상만
        self.external_video_files = [] # 사용자가 추가한 외부 영상
        self.preview_items = []        # 콤보박스 실제 표시 순서
        self.seek_pressed = False
        self.vlc_process = None
        self._last_opened_video = None
        self._last_open_ts = 0.0
        
        # UI 생성
        self.create_widgets()
        
        # 상태 갱신 타이머
        self.update_timer()
    
    def find_vlc(self):
        """외부 VLC 실행 파일 경로 찾기"""
        exe_path = find_vlc_executable()
        if exe_path:
            print(f"✅ VLC 발견: {exe_path}")
        return exe_path

    def init_vlc(self):
        """외부 VLC 전용 모드에서는 사용하지 않음"""
        self.instance = None
        self.player = None
        self.vlc_available = bool(self.vlc_path and os.path.exists(self.vlc_path))

    def create_widgets(self):
        # 상단: 파일 선택 프레임
        top_frame = tk.Frame(self, bg="#1a1e2a")
        top_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        tk.Label(top_frame, text="🎬 출력 영상:", fg="#c7d0db", bg="#1a1e2a", 
                font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=(0, 10))
        
        self.video_combo = ttk.Combobox(top_frame, values=[], width=40)
        self.video_combo.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.video_combo.bind('<<ComboboxSelected>>', self.on_video_selected)

        self.add_video_btn = tk.Button(top_frame, text="➕ 외부 영상",
                                 command=self.add_external_videos,
                                 bg="#3b4a6b", fg="white", relief="flat",
                                 font=("Malgun Gothic", 9))
        self.add_video_btn.pack(side="right", padx=(5, 0))

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
            self.after(200, self.bind_player_to_canvas)
        
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
                                   fg="#c7d0db", bg="#0f1115",
                                   font=("Malgun Gothic", 9))
        self.time_label.pack(side="left")
        
        # 볼륨 컨트롤
        volume_frame = tk.Frame(control_frame, bg="#0f1115")
        volume_frame.pack(side="right")
        
        tk.Label(volume_frame, text="🔊", fg="#c7d0db", bg="#0f1115",
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
    
    def play_with_vlc_external(self, video_path=None):
        target = Path(video_path) if video_path else self.current_video
        if not target or not Path(target).exists():
            messagebox.showwarning("재생", "재생할 영상을 먼저 선택하세요.")
            return
        if not self.vlc_path or not os.path.exists(self.vlc_path):
            messagebox.showerror("VLC", "VLC 실행 파일을 찾지 못했습니다.\n프로그램 폴더 안의 VLC 폴더 또는 시스템 설치 경로를 확인하세요.")
            return
        try:
            subprocess.Popen([self.vlc_path, str(target)])
            self.is_playing = True
            self.play_btn.config(text="▶ VLC")
            self.time_label.config(text=f"외부 VLC 재생: {Path(target).name}")
        except Exception as e:
            messagebox.showerror("VLC 실행 실패", str(e))

    def bind_player_to_canvas(self):
        return

    def add_external_videos(self):
        files = filedialog.askopenfilenames(title="외부 동영상 선택", initialdir=self.get_initial_dir_cb("video") if self.get_initial_dir_cb else None, filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.m4v *.webm"), ("All files", "*.*")])
        if files:
            self.external_video_files = [Path(x) for x in files]
            if self.remember_path_cb:
                self.remember_path_cb("video", files[0])
            self.refresh_video_combo(auto_play=False)

    def refresh_video_combo(self, auto_play=False):
        combined = []
        seen = set()
        for p in list(self.external_video_files) + list(self.video_files):
            pp = Path(p)
            key = str(pp.resolve()) if pp.exists() else str(pp)
            if key not in seen and pp.exists():
                combined.append(pp)
                seen.add(key)
        self.video_files = combined
        names = [f.name for f in self.video_files]
        self.video_combo['values'] = names
        if names:
            self.video_combo.set(names[0])
            self.load_video(self.video_files[0], auto_play=auto_play)

    def update_video_list(self, folder_path=None, auto_play=False, preferred_video=None, external_videos=None):
        """출력 폴더에서 비디오 파일 목록 업데이트"""
        if external_videos is not None:
            self.external_video_files = [Path(x) for x in external_videos if Path(x).exists()]
        ordered = []
        if folder_path and Path(folder_path).exists():
            ordered = sorted(list(Path(folder_path).glob("*.mp4")), key=lambda p: p.stat().st_mtime, reverse=True)
        if preferred_video:
            pref = Path(preferred_video)
            if pref.exists():
                ordered = [pref] + [p for p in ordered if p.resolve() != pref.resolve()]
        self.video_files = ordered
        self.refresh_video_combo(auto_play=auto_play)
    
    def auto_play_video(self):
        if self.current_video:
            self.play_with_vlc_external(self.current_video)

    def load_video(self, video_path, auto_play=False):
        """선택만 하고 재생은 외부 VLC로 처리"""
        if not video_path or not Path(video_path).exists():
            return
        self.current_video = Path(video_path)
        self.time_label.config(text=f"선택됨: {self.current_video.name}")
        self.seek_var.set(0)
        if auto_play:
            self.after(100, self.auto_play_video)
    
    def on_video_selected(self, event=None):
        idx = self.video_combo.current()
        if idx is None or idx < 0:
            return
        if idx < len(self.preview_items):
            self.load_video(self.preview_items[idx], auto_play=False)

    def toggle_play(self):
        if not self.current_video:
            self.on_video_selected()
        if self.current_video:
            self.play_with_vlc_external(self.current_video)

    def stop(self):
        self.is_playing = False
        self.play_btn.config(text="▶")
        try:
            if self.vlc_process and self.vlc_process.poll() is None:
                self.vlc_process.terminate()
        except Exception:
            pass
        if self.current_video:
            self.time_label.config(text=f"선택됨: {self.current_video.name}")
        else:
            self.time_label.config(text="00:00 / 00:00")
        self.seek_var.set(0)

    def on_volume_change(self, value):
        return

    def on_seek_press(self, event):
        """시크바 누를 때"""
        self.seek_pressed = True
    
    def on_seek_release(self, event):
        self.seek_pressed = False

    def on_seek(self, value):
        return
    
    def format_time(self, ms):
        """밀리초를 MM:SS로 변환"""
        if ms <= 0:
            return "00:00"
        total_seconds = int(ms / 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def update_timer(self):
        self.after(300, self.update_timer)


# =============================================================================
# 설정 UI 프레임 (워터마크 탭에 그라데이션 컨트롤 추가)
# =============================================================================

class SettingsFrame(ttk.Frame):
    def __init__(self, parent, settings: AppSettings, on_change_callback=None, auto_save_callback=None, get_initial_dir_callback=None, remember_path_callback=None):
        super().__init__(parent)
        self.settings = settings
        self.on_change = on_change_callback
        self.auto_save = auto_save_callback
        self.get_initial_dir_cb = get_initial_dir_callback
        self.remember_path_cb = remember_path_callback
        self.vars = {}
        self._debounce_id = None
        self.create_widgets()
    
    def create_widgets(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        self.create_video_tab(notebook)
        self.create_watermark_tab(notebook)
        self.create_subtitle_tab(notebook)
        self.create_media_tab(notebook)
        self.create_advanced_tab(notebook)
        self.create_reflection_tab(notebook)
    
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
        normalize_settings_types(self.settings)

    def _bind_var(self, key, var):
        var.trace_add("write", self.on_setting_changed)
        self.vars[key] = var
        return var

    def _grid_labeled_widget(self, frame, row, label, widget, note=None):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
        widget.grid(row=row, column=1, padx=5, pady=2, sticky="w")
        if note:
            ttk.Label(frame, text=note).grid(row=row, column=2, sticky="w", padx=5, pady=2)
        return row + 1

    def _make_var(self, var_cls, key, value):
        return self._bind_var(key, var_cls(value=value))

    def _add_spinbox_row(self, frame, row, label, key, value, var_cls, spinbox_kwargs, note=None):
        var = self._make_var(var_cls, key, value)
        widget = ttk.Spinbox(frame, textvariable=var, width=10, **spinbox_kwargs)
        return self._grid_labeled_widget(frame, row, label, widget, note=note)

    def _add_scale_row(self, frame, row, label, key, value, var_cls, scale_kwargs):
        var = self._make_var(var_cls, key, value)
        widget = ttk.Scale(frame, variable=var, orient="horizontal", length=150, **scale_kwargs)
        return self._grid_labeled_widget(frame, row, label, widget)

    def _add_check_row(self, frame, row, label, key, value):
        var = self._make_var(tk.BooleanVar, key, value)
        widget = tk.Checkbutton(frame, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf")
        return self._grid_labeled_widget(frame, row, label, widget)

    def _add_combo_row(self, frame, row, label, key, value, values, width=12, note=None):
        var = self._make_var(tk.StringVar, key, value)
        widget = ttk.Combobox(frame, textvariable=var, values=values, width=width, state='readonly')
        return self._grid_labeled_widget(frame, row, label, widget, note=note)

    def _add_font_row(self, frame, row, label, key, value):
        note = "프로그램 내부 fonts 폴더의 폰트만 표시합니다. 새 폰트를 넣은 뒤 프로그램을 다시 열면 목록에 나타납니다."
        return self._add_combo_row(frame, row, label, key, value, get_available_font_names(), width=28, note=note)


    def _add_radiobutton_row(self, frame, row, label, key, value, options):
        var = self._make_var(tk.StringVar, key, value)
        box = tk.Frame(frame, bg="#1a1e2a")
        for idx, (caption, opt_value) in enumerate(options):
            tk.Radiobutton(box, text=caption, value=opt_value, variable=var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left", padx=((6 if idx else 0), 0))
        return self._grid_labeled_widget(frame, row, label, box)

    def _add_path_picker_row(self, frame, row, label, key, value, button_text, browse_command, width=20):
        var = self._make_var(tk.StringVar, key, value)
        holder = ttk.Frame(frame)
        ttk.Entry(holder, textvariable=var, width=width).pack(side="left")
        ttk.Button(holder, text=button_text, command=browse_command).pack(side="left", padx=(5, 0))
        return self._grid_labeled_widget(frame, row, label, holder)

    def _add_button_group_row(self, frame, row, label, buttons):
        holder = ttk.Frame(frame)
        for caption, command in buttons:
            ttk.Button(holder, text=caption, command=command).pack(side="left", padx=2)
        return self._grid_labeled_widget(frame, row, label, holder)

    def _add_entry_row(self, frame, row, label, key, value, width=20, note=None):
        var = self._make_var(tk.StringVar, key, value)
        widget = ttk.Entry(frame, textvariable=var, width=width)
        return self._grid_labeled_widget(frame, row, label, widget, note=note)

    def _add_color_picker_row(self, frame, row, label, key, value):
        var = self._make_var(tk.StringVar, key, value)
        btn_frame = ttk.Frame(frame)
        color_preview = tk.Label(btn_frame, bg=var.get(), width=2, height=1)
        color_preview.pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="선택", command=lambda: self.choose_color(var, color_preview)).pack(side="left")
        return self._grid_labeled_widget(frame, row, label, btn_frame)

    def _add_note_row(self, frame, row, text, columnspan=3, foreground=None):
        kwargs = {"text": text}
        if foreground:
            kwargs["foreground"] = foreground
        ttk.Label(frame, **kwargs).grid(row=row, column=0, columnspan=columnspan, sticky="w", padx=5, pady=2)
        return row + 1

    def _make_scrollable_tab(self, notebook, title):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        canvas = tk.Canvas(frame, highlightthickness=0, bg="#1a1e2a")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return frame, scrollable_frame
    
    def create_video_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="영상/전환")
        row = 0
        row = self._add_spinbox_row(frame, row, "이미지당 시간 (초):", "video.base_image_sec", self.settings.video.base_image_sec, tk.DoubleVar, {"from_":0.5, "to":10.0, "increment":0.1})
        row = self._add_spinbox_row(frame, row, "전환 비율 (0.2~0.8):", "video.transition_ratio", self.settings.video.transition_ratio, tk.DoubleVar, {"from_":0.1, "to":0.9, "increment":0.05})
        row = self._add_note_row(frame, row, "권장 전환 비율은 0.3~0.6 입니다. 0.8 이상은 어지러울 수 있습니다.", foreground="#9aa4b2")
        row = self._add_spinbox_row(frame, row, "줌 강도 (0.001~0.01):", "video.zoom_intensity", self.settings.video.zoom_intensity, tk.DoubleVar, {"from_":0.001, "to":0.02, "increment":0.001})
        row = self._add_radiobutton_row(frame, row, "줌 방향:", "video.zoom_direction", getattr(self.settings.video, "zoom_direction", "in") or "in", [("줌인", "in"), ("줌아웃", "out"), ("랜덤", "random")])
        row = self._add_spinbox_row(frame, row, "줌 상한 (예: 1.02~1.08):", "video.zoom_cap", float(getattr(self.settings.video, "zoom_cap", 1.04) or 1.04), tk.DoubleVar, {"from_":1.00, "to":1.20, "increment":0.005})
        row = self._add_check_row(frame, row, "중앙 줌 전용:", "video.zoom_center_only", self.settings.video.zoom_center_only)
        row = self._add_check_row(frame, row, "⚠️ 줌팬 사용:", "video.enable_zoompam", self.settings.video.enable_zoompam)
        row = self._add_spinbox_row(frame, row, "줌팬 강도:", "video.zoompam_intensity", self.settings.video.zoompam_intensity, tk.DoubleVar, {"from_":0.0005, "to":0.005, "increment":0.0005})
        row = self._add_combo_row(frame, row, "FPS:", "video.fps", str(self.settings.video.fps), [24, 25, 30, 60], width=8)
        row = self._add_note_row(frame, row, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        row = self._add_check_row(frame, row, "첫 회전 랜덤:", "transition.shuffle_images", self.settings.transition.shuffle_images)
        row = self._add_check_row(frame, row, "회전마다 랜덤:", "transition.cycle_shuffle", self.settings.transition.cycle_shuffle)
        row = self._add_check_row(frame, row, "역순 재생:", "transition.reverse_cycle", self.settings.transition.reverse_cycle)
        row = self._add_combo_row(frame, row, "전환 스타일:", "transition.style", self.settings.transition.style, ["natural", "fade_only"], width=12)
        row = self._add_check_row(frame, row, "랜덤 색보정:", "color_random.enabled", self.settings.color_random.enabled)

    def create_reflection_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="반사배경")
        row = 0

        row = self._add_note_row(frame, row, "원본 가장자리에 블러/확대 배경을 깔아 세로 숏폼 느낌을 강하게 만드는 옵션입니다.", foreground="#9aa4b2")
        row = self._add_scale_row(frame, row, "반사 강도 (1.0~3.5):", "reflection.strength", self.settings.reflection.strength, tk.DoubleVar, {"from_":1.0, "to":3.5})
        row = self._add_scale_row(frame, row, "블러 강도 (0~120):", "reflection.blur_radius", self.settings.reflection.blur_radius, tk.IntVar, {"from_":0, "to":120})
        row = self._add_scale_row(frame, row, "배경 어둡기 (0.25~1.40):", "reflection.dim", self.settings.reflection.dim, tk.DoubleVar, {"from_":0.25, "to":1.40})

    def create_watermark_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="워터마크")
        ttk.Label(frame, text="사진 워터마크 / 동영상 워터마크 / 썸네일을 각각 분리해서 관리합니다.", foreground="#9aa4b2").pack(anchor="w", padx=8, pady=(6, 2))
        sub = ttk.Notebook(frame)
        sub.pack(fill="both", expand=True, padx=5, pady=5)

        # 사진 워터마크
        sframe, inner = self._make_scrollable_tab(sub, "사진 워터마크")
        row = 0
        row = self._add_font_row(inner, row, "공통 폰트:", "image_watermark.font_name", getattr(self.settings.image_watermark, 'font_name', 'Pretendard Bold'))
        row = self._add_check_row(inner, row, "상단 타이틀 표시:", "image_watermark.title_enabled", getattr(self.settings.image_watermark, 'title_enabled', False))
        row = self._add_entry_row(inner, row, "상단 타이틀:", "image_watermark.title_text", getattr(self.settings.image_watermark, 'title_text', ''), width=24)
        row = self._add_spinbox_row(inner, row, "타이틀 폰트 크기:", "image_watermark.title_font_size", getattr(self.settings.image_watermark, 'title_font_size', 54), tk.IntVar, {"from_":20, "to":120, "increment":2})
        row = self._add_color_picker_row(inner, row, "타이틀 색상:", "image_watermark.title_color", getattr(self.settings.image_watermark, 'title_color', '#FFFFFF'))
        row = self._add_check_row(inner, row, "상단 서브타이틀 표시:", "image_watermark.subtitle_enabled", getattr(self.settings.image_watermark, 'subtitle_enabled', False))
        row = self._add_entry_row(inner, row, "서브타이틀:", "image_watermark.subtitle_text", getattr(self.settings.image_watermark, 'subtitle_text', ''), width=24)
        row = self._add_spinbox_row(inner, row, "서브타이틀 폰트 크기:", "image_watermark.subtitle_font_size", getattr(self.settings.image_watermark, 'subtitle_font_size', 34), tk.IntVar, {"from_":16, "to":90, "increment":2})
        row = self._add_color_picker_row(inner, row, "서브타이틀 색상:", "image_watermark.subtitle_color", getattr(self.settings.image_watermark, 'subtitle_color', '#DDE7FF'))
        row = self._add_spinbox_row(inner, row, "상단 여백:", "image_watermark.title_margin_top", getattr(self.settings.image_watermark, 'title_margin_top', 80), tk.IntVar, {"from_":0, "to":300, "increment":5})
        row = self._add_spinbox_row(inner, row, "타이틀-서브 간격:", "image_watermark.subtitle_gap_px", getattr(self.settings.image_watermark, 'subtitle_gap_px', 14), tk.IntVar, {"from_":0, "to":80, "increment":2})
        row = self._add_entry_row(inner, row, "상호명:", "image_watermark.brand_text", self.settings.image_watermark.brand_text, width=20)
        row = self._add_entry_row(inner, row, "전화번호:", "image_watermark.phone_text", self.settings.image_watermark.phone_text, width=20)
        row = self._add_spinbox_row(inner, row, "상호-전화 간격(px):", "image_watermark.phone_gap_px", getattr(self.settings.image_watermark, "phone_gap_px", 0), tk.IntVar, {"from_":0, "to":200, "increment":2}, note="0=자동, 숫자=고정 간격")
        row = self._add_spinbox_row(inner, row, "상호 폰트 크기:", "image_watermark.brand_font_size", self.settings.image_watermark.brand_font_size, tk.IntVar, {"from_":20, "to":100, "increment":2})
        row = self._add_spinbox_row(inner, row, "전화번호 폰트 크기:", "image_watermark.phone_font_size", self.settings.image_watermark.phone_font_size, tk.IntVar, {"from_":20, "to":100, "increment":2})
        row = self._add_color_picker_row(inner, row, "상호 색상:", "image_watermark.brand_color", self.settings.image_watermark.brand_color)
        row = self._add_color_picker_row(inner, row, "전화 색상:", "image_watermark.phone_color", self.settings.image_watermark.phone_color)
        row = self._add_spinbox_row(inner, row, "하단 여백:", "image_watermark.margin_bottom", self.settings.image_watermark.margin_bottom, tk.IntVar, {"from_":20, "to":300, "increment":5})
        row = self._add_check_row(inner, row, "그라데이션 사용:", "image_watermark.box_enabled", self.settings.image_watermark.box_enabled)
        row = self._add_scale_row(inner, row, "그라데이션 투명도:", "image_watermark.box_alpha", self.settings.image_watermark.box_alpha, tk.IntVar, {"from_":0, "to":255})
        row = self._add_scale_row(inner, row, "그라데이션 높이:", "image_watermark.box_height_multiplier", self.settings.image_watermark.box_height_multiplier, tk.DoubleVar, {"from_":1.0, "to":6.0})

        # 동영상 워터마크
        sframe2, inner2 = self._make_scrollable_tab(sub, "동영상 워터마크")
        row = 0
        row = self._add_button_group_row(inner2, row, "빠른 복사:", [("사진 설정 → 동영상", self.copy_image_to_video_watermark)])
        row = self._add_font_row(inner2, row, "공통 폰트:", "video_watermark.font_name", getattr(self.settings.video_watermark, 'font_name', 'Pretendard Bold'))
        row = self._add_check_row(inner2, row, "상단 타이틀 표시:", "video_watermark.title_enabled", getattr(self.settings.video_watermark, 'title_enabled', False))
        row = self._add_entry_row(inner2, row, "상단 타이틀:", "video_watermark.title_text", getattr(self.settings.video_watermark, 'title_text', ''), width=24)
        row = self._add_spinbox_row(inner2, row, "타이틀 폰트 크기:", "video_watermark.title_font_size", getattr(self.settings.video_watermark, 'title_font_size', 54), tk.IntVar, {"from_":20, "to":120, "increment":2})
        row = self._add_color_picker_row(inner2, row, "타이틀 색상:", "video_watermark.title_color", getattr(self.settings.video_watermark, 'title_color', '#FFFFFF'))
        row = self._add_check_row(inner2, row, "상단 서브타이틀 표시:", "video_watermark.subtitle_enabled", getattr(self.settings.video_watermark, 'subtitle_enabled', False))
        row = self._add_entry_row(inner2, row, "서브타이틀:", "video_watermark.subtitle_text", getattr(self.settings.video_watermark, 'subtitle_text', ''), width=24)
        row = self._add_spinbox_row(inner2, row, "서브타이틀 폰트 크기:", "video_watermark.subtitle_font_size", getattr(self.settings.video_watermark, 'subtitle_font_size', 34), tk.IntVar, {"from_":16, "to":90, "increment":2})
        row = self._add_color_picker_row(inner2, row, "서브타이틀 색상:", "video_watermark.subtitle_color", getattr(self.settings.video_watermark, 'subtitle_color', '#DDE7FF'))
        row = self._add_spinbox_row(inner2, row, "상단 여백:", "video_watermark.title_margin_top", getattr(self.settings.video_watermark, 'title_margin_top', 80), tk.IntVar, {"from_":0, "to":300, "increment":5})
        row = self._add_spinbox_row(inner2, row, "타이틀-서브 간격:", "video_watermark.subtitle_gap_px", getattr(self.settings.video_watermark, 'subtitle_gap_px', 14), tk.IntVar, {"from_":0, "to":80, "increment":2})
        row = self._add_entry_row(inner2, row, "상호명:", "video_watermark.brand_text", self.settings.video_watermark.brand_text, width=20)
        row = self._add_entry_row(inner2, row, "전화번호:", "video_watermark.phone_text", self.settings.video_watermark.phone_text, width=20)
        row = self._add_spinbox_row(inner2, row, "상호-전화 간격(px):", "video_watermark.phone_gap_px", getattr(self.settings.video_watermark, "phone_gap_px", 0), tk.IntVar, {"from_":0, "to":200, "increment":2}, note="0=자동, 숫자=고정 간격")
        row = self._add_spinbox_row(inner2, row, "상호 폰트 크기:", "video_watermark.brand_font_size", self.settings.video_watermark.brand_font_size, tk.IntVar, {"from_":20, "to":100, "increment":2})
        row = self._add_spinbox_row(inner2, row, "전화번호 폰트 크기:", "video_watermark.phone_font_size", self.settings.video_watermark.phone_font_size, tk.IntVar, {"from_":20, "to":100, "increment":2})
        row = self._add_color_picker_row(inner2, row, "상호 색상:", "video_watermark.brand_color", self.settings.video_watermark.brand_color)
        row = self._add_color_picker_row(inner2, row, "전화 색상:", "video_watermark.phone_color", self.settings.video_watermark.phone_color)
        row = self._add_spinbox_row(inner2, row, "하단 여백:", "video_watermark.margin_bottom", self.settings.video_watermark.margin_bottom, tk.IntVar, {"from_":20, "to":300, "increment":5})
        row = self._add_check_row(inner2, row, "그라데이션 사용:", "video_watermark.box_enabled", self.settings.video_watermark.box_enabled)
        row = self._add_scale_row(inner2, row, "그라데이션 투명도:", "video_watermark.box_alpha", self.settings.video_watermark.box_alpha, tk.IntVar, {"from_":0, "to":255})
        row = self._add_scale_row(inner2, row, "그라데이션 높이:", "video_watermark.box_height_multiplier", self.settings.video_watermark.box_height_multiplier, tk.DoubleVar, {"from_":1.0, "to":6.0})

        # 썸네일
        sframe3, inner3 = self._make_scrollable_tab(sub, "썸네일")
        row = 0
        row = self._add_note_row(inner3, row, "쇼츠 썸네일 기본 크기: 1080 x 1920", foreground="#9aa4b2")
        row = self._add_font_row(inner3, row, "공통 폰트:", "thumbnail.font_name", getattr(self.settings.thumbnail, 'font_name', 'Pretendard Bold'))
        row = self._add_path_picker_row(inner3, row, "중앙 이미지:", "thumbnail.image_path", getattr(self.settings.thumbnail, 'image_path', ''), "선택", self.select_thumbnail_image, width=28)
        row = self._add_check_row(inner3, row, "타이틀 표시:", "thumbnail.title_enabled", getattr(self.settings.thumbnail, 'title_enabled', True))
        row = self._add_entry_row(inner3, row, "타이틀:", "thumbnail.title_text", getattr(self.settings.thumbnail, 'title_text', ''), width=24)
        row = self._add_spinbox_row(inner3, row, "타이틀 폰트 크기:", "thumbnail.title_font_size", getattr(self.settings.thumbnail, 'title_font_size', 88), tk.IntVar, {"from_":24, "to":160, "increment":2})
        row = self._add_color_picker_row(inner3, row, "타이틀 색상:", "thumbnail.title_color", getattr(self.settings.thumbnail, 'title_color', '#FFFFFF'))
        row = self._add_check_row(inner3, row, "서브타이틀 표시:", "thumbnail.subtitle_enabled", getattr(self.settings.thumbnail, 'subtitle_enabled', True))
        row = self._add_entry_row(inner3, row, "서브타이틀:", "thumbnail.subtitle_text", getattr(self.settings.thumbnail, 'subtitle_text', ''), width=24)
        row = self._add_spinbox_row(inner3, row, "서브타이틀 폰트 크기:", "thumbnail.subtitle_font_size", getattr(self.settings.thumbnail, 'subtitle_font_size', 46), tk.IntVar, {"from_":18, "to":100, "increment":2})
        row = self._add_color_picker_row(inner3, row, "서브타이틀 색상:", "thumbnail.subtitle_color", getattr(self.settings.thumbnail, 'subtitle_color', '#DDE7FF'))
        row = self._add_spinbox_row(inner3, row, "상단 여백:", "thumbnail.title_margin_top", getattr(self.settings.thumbnail, 'title_margin_top', 90), tk.IntVar, {"from_":0, "to":320, "increment":5})
        row = self._add_spinbox_row(inner3, row, "타이틀-서브 간격:", "thumbnail.subtitle_gap_px", getattr(self.settings.thumbnail, 'subtitle_gap_px', 18), tk.IntVar, {"from_":0, "to":100, "increment":2})
        row = self._add_entry_row(inner3, row, "하단 상호:", "thumbnail.brand_text", getattr(self.settings.thumbnail, 'brand_text', ''), width=20)
        row = self._add_entry_row(inner3, row, "하단 전화번호:", "thumbnail.phone_text", getattr(self.settings.thumbnail, 'phone_text', ''), width=20)
        row = self._add_spinbox_row(inner3, row, "상호 폰트 크기:", "thumbnail.brand_font_size", getattr(self.settings.thumbnail, 'brand_font_size', 58), tk.IntVar, {"from_":18, "to":120, "increment":2})
        row = self._add_spinbox_row(inner3, row, "전화번호 폰트 크기:", "thumbnail.phone_font_size", getattr(self.settings.thumbnail, 'phone_font_size', 50), tk.IntVar, {"from_":18, "to":120, "increment":2})
        row = self._add_color_picker_row(inner3, row, "상호 색상:", "thumbnail.brand_color", getattr(self.settings.thumbnail, 'brand_color', '#FFD300'))
        row = self._add_color_picker_row(inner3, row, "전화 색상:", "thumbnail.phone_color", getattr(self.settings.thumbnail, 'phone_color', '#FFFFFF'))
        row = self._add_spinbox_row(inner3, row, "하단 여백:", "thumbnail.margin_bottom", getattr(self.settings.thumbnail, 'margin_bottom', 90), tk.IntVar, {"from_":10, "to":300, "increment":5})
        row = self._add_spinbox_row(inner3, row, "상호-전화 간격:", "thumbnail.phone_gap_px", getattr(self.settings.thumbnail, 'phone_gap_px', 10), tk.IntVar, {"from_":0, "to":120, "increment":2})
        row = self._add_button_group_row(inner3, row, "생성:", [("썸네일 만들기", self.generate_thumbnail_now)])

    def copy_image_to_video_watermark(self):
        self.apply_settings_to_object()
        import copy as _copy
        self.settings.video_watermark = _copy.deepcopy(self.settings.image_watermark)
        self.update_vars_from_settings()
        if self.on_change:
            self.on_change()
        if self.auto_save:
            self.auto_save()

    def select_thumbnail_image(self):
        file = filedialog.askopenfilename(title="썸네일 이미지 선택", initialdir=self.get_initial_dir_cb("image") if self.get_initial_dir_cb else None, filetypes=[("Image", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All files", "*.*")])
        if file:
            self.vars["thumbnail.image_path"].set(file)
            if self.remember_path_cb:
                self.remember_path_cb("image", file)

    def generate_thumbnail_now(self):
        try:
            self.apply_settings_to_object()
            out_path = generate_thumbnail_image(self.settings)
            messagebox.showinfo("썸네일 완료", f"저장 완료:\n{out_path}")
        except Exception as e:
            messagebox.showerror("썸네일 오류", str(e))

    def choose_color(self, var, preview_label):
        color = colorchooser.askcolor(var.get())[1]
        if color:
            var.set(color)
            preview_label.config(bg=color)
    
    def create_subtitle_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="자막")
        row = 0

        row = self._add_check_row(frame, row, "자막 사용:", "subtitle.enabled", self.settings.subtitle.enabled)
        row = self._add_font_row(frame, row, "자막 폰트:", "subtitle.font_name", getattr(self.settings.subtitle, 'font_name', 'Malgun Gothic'))
        row = self._add_spinbox_row(frame, row, "폰트 크기:", "subtitle.font_size", self.settings.subtitle.font_size, tk.IntVar, {"from_":8, "to":30, "increment":1}, note="긴 자막은 자동 줄넘김됩니다.")
        row = self._add_spinbox_row(frame, row, "하단 여백:", "subtitle.margin_v", self.settings.subtitle.margin_v, tk.IntVar, {"from_":10, "to":200, "increment":5})
        row = self._add_spinbox_row(frame, row, "외곽선 두께:", "subtitle.outline", self.settings.subtitle.outline, tk.IntVar, {"from_":0, "to":10, "increment":1})
        row = self._add_spinbox_row(frame, row, "그림자 두께:", "subtitle.shadow", self.settings.subtitle.shadow, tk.IntVar, {"from_":0, "to":10, "increment":1})
        row = self._add_scale_row(frame, row, "자막 박스 투명도 (0~100):", "subtitle.box_alpha", getattr(self.settings.subtitle, 'box_alpha', 0), tk.IntVar, {"from_":0, "to":100})
        row = self._add_note_row(frame, row, "범례: 0=박스 없음, 20~35=은은함, 40~60=가독성 강조. 1줄/2줄은 자막 길이에 따라 자동 박스 처리됩니다.", foreground="#9aa4b2")
        row = self._add_check_row(frame, row, "굵게:", "subtitle.bold", self.settings.subtitle.bold)


    def create_transition_tab(self, notebook):
        return

    def create_media_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="외부동영상")
        row = 0
        row = self._add_check_row(frame, row, "외부 동영상 사용:", "media.enabled", self.settings.media.enabled)
        row = self._add_combo_row(frame, row, "배치 위치:", "media.placement", self.settings.media.placement, ["interleave", "append_end", "prepend_start"], width=14)
        row = self._add_spinbox_row(frame, row, "동영상 속도 배수:", "media.playback_speed", self.settings.media.playback_speed, tk.DoubleVar, {"from_":0.25, "to":4.0, "increment":0.05})
        row = self._add_spinbox_row(frame, row, "전체 길이 중 동영상 비율:", "media.target_ratio", self.settings.media.target_ratio, tk.DoubleVar, {"from_":0.05, "to":0.8, "increment":0.05}, note="예: 0.25 = 전체 25%를 영상 구간으로 사용")
        self._add_note_row(frame, row, "선택한 외부 동영상을 9:16으로 맞춰 앞/뒤에 이어붙입니다.\n동영상 비율을 높이면 슬라이드 구간은 자동으로 짧아집니다.")

    def create_advanced_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="고급")
        row = 0

        row = self._add_button_group_row(frame, row, "설정 JSON:", [("JSON 편집", self.edit_json)])
        row = self._add_button_group_row(frame, row, "프리셋:", [("저장", self.save_preset), ("불러오기", self.load_preset)])

        row = self._add_check_row(frame, row, "오디오 랜덤:", "encoding.audio_random_enabled", self.settings.encoding.audio_random_enabled)

        row = self._add_path_picker_row(frame, row, "오디오 폴더:", "encoding.audio_folder", self.settings.encoding.audio_folder, "찾기", self.select_audio_folder)

        row = self._add_check_row(frame, row, "TEMP 삭제:", "encoding.delete_temp_after_done", self.settings.encoding.delete_temp_after_done)

        ttk.Label(frame, text="출력 버전:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ver_frame = ttk.Frame(frame)
        ver_frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=2)
        sns_var = self._make_var(tk.BooleanVar, "encoding.out_sns_enabled", self.settings.encoding.out_sns_enabled)
        tk.Checkbutton(ver_frame, text="SNS(경량)", variable=sns_var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left", padx=(0, 10))
        hq_var = self._make_var(tk.BooleanVar, "encoding.out_hq_enabled", self.settings.encoding.out_hq_enabled)
        tk.Checkbutton(ver_frame, text="HQ(고화질)", variable=hq_var, bg="#1a1e2a", fg="white", selectcolor="#2d6cdf").pack(side="left")
        row += 1

        row = self._add_note_row(frame, row, "SNS/HQ 품질(기본): SNS: (체크 시 720 자동) cq/crf 32 · 96k / HQ: 1080 유지 cq/crf 20 · 192k", foreground="#9aa4b2")
        self._add_note_row(frame, row, "용량 최적화: CRF 28 / 오디오 128k (모바일 숏폼용)", foreground="#4caf50")


    def select_audio_folder(self):
        folder = filedialog.askdirectory(title="오디오 폴더 선택", initialdir=self.get_initial_dir_cb("audio") if self.get_initial_dir_cb else None)
        if folder:
            self.vars["encoding.audio_folder"].set(folder)
            if self.remember_path_cb:
                self.remember_path_cb("audio", folder)
    
    def edit_json(self):
        temp_json = APP_TEMP_DIR / 'temp_settings.json'
        self.settings.save_to_file(temp_json)
        try:
            os.startfile(str(temp_json))
            messagebox.showinfo("JSON 편집", "설정 파일이 열렸습니다.\n수정 후 저장하고 닫아주세요.\n\n적용하려면 '프리셋 불러오기'를 클릭하세요.")
        except Exception as e:
            messagebox.showerror("오류", f"파일을 열 수 없습니다: {e}")
    
    def save_preset(self):
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="프리셋 저장", initialdir=(self.get_initial_dir_cb("preset") if self.get_initial_dir_cb else str(APP_PRESET_DIR)))
        if filename:
            self.settings.save_to_file(Path(filename))
            if self.remember_path_cb:
                self.remember_path_cb("preset", filename)
            messagebox.showinfo("완료", "프리셋이 저장되었습니다.")
    
    def load_preset(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="프리셋 불러오기", initialdir=(self.get_initial_dir_cb("preset") if self.get_initial_dir_cb else str(APP_PRESET_DIR)))
        if filename:
            try:
                if self.remember_path_cb:
                    self.remember_path_cb("preset", filename)
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
        return normalize_settings_types(self.settings)

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

