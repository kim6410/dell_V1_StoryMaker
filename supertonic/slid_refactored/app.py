from __future__ import annotations
from .core import *
from .image_pipeline import preprocess_images
from .ffmpeg_core import BuildReport, build_video_onepass
from .ui_components import VideoPreviewPlayer, SettingsFrame, MultiProgressBar

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
            self.root.title("SLID_Maker | FM연구소 v5.3")
            self.root.geometry("1400x1290")
            self.root.configure(bg="#0f1115")
        
        self.config_file = APP_SETTING_FILE
        self.ui_state_file = APP_UI_STATE_FILE
        self.settings = AppSettings()
        self.last_dirs = {"image": "", "audio": "", "srt": "", "video": "", "preset": str(APP_PRESET_DIR)}
        self.manual_video_files = []
        self.current_log_file = None

        # 파일/경로 상태는 위젯 생성 전에 먼저 준비
        self.img_dir = None
        self.audio_path = None
        self.srt_path = None

        self.ensure_runtime_files()
        self.load_last_settings()
        self.load_ui_state()
        
        # 자동 저장 타이머
        self._auto_save_timer = None
        
        # 프리뷰 모드
        self.preview_mode = tk.StringVar(value="image")  # "image" 또는 "video"
        
        # 출력 폴더
        self.output_folder = None
        self.last_output_video = None

        # ===== 환경변수 설정 적용 =====
        if os.environ.get('SLID_BRAND_NAME'):
            self.settings.image_watermark.brand_text = os.environ.get('SLID_BRAND_NAME')
            print(f"[환경변수] 상호명: {self.settings.image_watermark.brand_text}")

        if os.environ.get('SLID_PHONE_NUMBER'):
            self.settings.image_watermark.phone_text = os.environ.get('SLID_PHONE_NUMBER')
            print(f"[환경변수] 전화번호: {self.settings.image_watermark.phone_text}")

        if os.environ.get('SLID_BRAND_SIZE'):
            self.settings.image_watermark.brand_font_size = int(os.environ.get('SLID_BRAND_SIZE'))

        if os.environ.get('SLID_PHONE_SIZE'):
            self.settings.image_watermark.phone_font_size = int(os.environ.get('SLID_PHONE_SIZE'))

        if os.environ.get('SLID_MARGIN_BOTTOM'):
            self.settings.image_watermark.margin_bottom = int(os.environ.get('SLID_MARGIN_BOTTOM'))

        if os.environ.get('SLID_BOX_ENABLED'):
            self.settings.image_watermark.box_enabled = os.environ.get('SLID_BOX_ENABLED').lower() == 'true'

        if os.environ.get('SLID_STROKE_ENABLED'):
            self.settings.image_watermark.stroke_enabled = os.environ.get('SLID_STROKE_ENABLED').lower() == 'true'

        if os.environ.get('SLID_SHADOW_ENABLED'):
            self.settings.image_watermark.shadow_enabled = os.environ.get('SLID_SHADOW_ENABLED').lower() == 'true'

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
        if os.environ.get('SLID_ZOOM_CENTER_ONLY') is not None:
            self.settings.video.zoom_center_only = os.environ.get('SLID_ZOOM_CENTER_ONLY', '').strip().lower() in {'1', 'true', 'yes', 'on'}

        if os.environ.get('SLID_SUBTITLE_ENABLED'):
            self.settings.subtitle.enabled = os.environ.get('SLID_SUBTITLE_ENABLED').lower() == 'true'

        if os.environ.get('SLID_SUBTITLE_SIZE'):
            self.settings.subtitle.font_size = int(os.environ.get('SLID_SUBTITLE_SIZE'))

        if os.environ.get('SLID_SUBTITLE_MARGIN'):
            self.settings.subtitle.margin_v = int(os.environ.get('SLID_SUBTITLE_MARGIN'))

        if os.environ.get('SLID_RESOLUTION'):
            res_str = os.environ.get('SLID_RESOLUTION')
            if 'x' in res_str:
                try:
                    w_str, h_str = res_str.split('x')
                    self.settings.video.width = int(w_str)
                    self.settings.video.height = int(h_str)
                    print(f"[환경변수] 해상도 설정: {self.settings.video.width}x{self.settings.video.height}")
                except Exception as e:
                    print(f"[환경변수] 해상도 파싱 실패: {e}")

        if os.environ.get('SLID_FPS'):
            try:
                self.settings.video.fps = int(os.environ.get('SLID_FPS'))
                print(f"[환경변수] FPS 설정: {self.settings.video.fps}")
            except Exception as e:
                print(f"[환경변수] FPS 파싱 실패: {e}")

        if os.environ.get('SLID_NVENC_PRESET'):
            preset_val = os.environ.get('SLID_NVENC_PRESET')
            self.settings.encoding.nvenc_preset = preset_val
            self.settings.encoding.sns_nvenc_preset = preset_val
            self.settings.encoding.hq_nvenc_preset = preset_val
            print(f"[환경변수] NVENC 프리셋 설정: {preset_val}")

        self.settings.video_watermark = copy.deepcopy(self.settings.image_watermark)
        self.settings.watermark = self.settings.image_watermark
        print('[설정] 환경변수 적용 완료')


        self.setup_styles()
        self.create_widgets()
        
        self.qevt = queue.Queue()
        self.worker = None
        self.preview_image = None
        self.preview_photo = None
        
        if hasattr(self.root, "protocol"):
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        if hasattr(self.root, "after"):
            self.root.after(120, self.poll)
    

    def ensure_runtime_files(self):
        """설치형처럼 첫 실행 시 필요한 JSON/폴더를 자동 생성"""
        try:
            ensure_runtime_dirs()
            if not self.config_file.exists():
                AppSettings().save_to_file(self.config_file)
                safe_print(f"✅ 기본 설정 파일 자동 생성: {self.config_file}")
            if not self.ui_state_file.exists():
                payload = {
                    "last_dirs": {"image": "", "audio": "", "srt": "", "video": "", "preset": str(APP_PRESET_DIR)},
                    "img_dir": "",
                    "audio_path": "",
                    "srt_path": "",
                    "manual_video_files": [],
                }
                self.ui_state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                safe_print(f"✅ UI 상태 파일 자동 생성: {self.ui_state_file}")
        except Exception as e:
            safe_print(f"⚠️ 런타임 파일 준비 실패: {e}")

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
            self.save_ui_state()
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
        self.save_ui_state()
        self.root.destroy()

    def load_ui_state(self):
        if self.ui_state_file.exists():
            try:
                data = json.loads(self.ui_state_file.read_text(encoding="utf-8"))
                self.last_dirs.update(data.get("last_dirs", {}))
                if data.get("img_dir"):
                    p = Path(data.get("img_dir"))
                    if p.exists():
                        self.img_dir = p
                if data.get("audio_path"):
                    p = Path(data.get("audio_path"))
                    if p.exists():
                        self.audio_path = p
                if data.get("srt_path"):
                    p = Path(data.get("srt_path"))
                    if p.exists():
                        self.srt_path = p
                self.manual_video_files = [x for x in data.get("manual_video_files", []) if Path(x).exists()]
                if not getattr(self.settings.media, "selected_files", None):
                    self.settings.media.selected_files = list(self.manual_video_files)
            except Exception as e:
                safe_print(f"⚠️ UI 상태 불러오기 실패: {e}")

    def save_ui_state(self):
        try:
            data = {
                "last_dirs": self.last_dirs,
                "img_dir": str(self.img_dir) if self.img_dir else "",
                "audio_path": str(self.audio_path) if self.audio_path else "",
                "srt_path": str(self.srt_path) if self.srt_path else "",
                "manual_video_files": list(self.manual_video_files),
            }
            self.ui_state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            safe_print(f"⚠️ UI 상태 저장 실패: {e}")

    def save_project_bundle(self):
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="전체 프로젝트 저장", initialdir=self.last_dirs.get("preset") or None)
        if not filename:
            return
        self.last_dirs["preset"] = str(Path(filename).parent)
        payload = {
            "settings": {
                "video": asdict(self.settings.video),
                "reflection": asdict(self.settings.reflection),
                "color_random": asdict(self.settings.color_random),
                "watermark": asdict(self.settings.watermark),
                "subtitle": asdict(self.settings.subtitle),
                "transition": asdict(self.settings.transition),
                "encoding": asdict(self.settings.encoding),
                "media": asdict(self.settings.media),
            },
            "ui": {
                "last_dirs": self.last_dirs,
                "img_dir": str(self.img_dir) if self.img_dir else "",
                "audio_path": str(self.audio_path) if self.audio_path else "",
                "srt_path": str(self.srt_path) if self.srt_path else "",
                "manual_video_files": list(self.manual_video_files),
            }
        }
        Path(filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("저장 완료", f"프로젝트 저장 완료\n{filename}")

    def load_project_bundle(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")], title="전체 프로젝트 불러오기", initialdir=self.last_dirs.get("preset") or None)
        if not filename:
            return
        data = json.loads(Path(filename).read_text(encoding="utf-8"))
        self.last_dirs["preset"] = str(Path(filename).parent)
        self.settings = AppSettings.load_from_file(Path(filename)) if "video" in data else AppSettings()
        if "settings" in data:
            tmp = Path(filename).with_suffix('.tmp.json')
            tmp.write_text(json.dumps(data["settings"], ensure_ascii=False, indent=2), encoding="utf-8")
            self.settings = AppSettings.load_from_file(tmp)
            tmp.unlink(missing_ok=True)
        ui = data.get("ui", {})
        self.last_dirs.update(ui.get("last_dirs", {}))
        self.img_dir = Path(ui["img_dir"]) if ui.get("img_dir") and Path(ui["img_dir"]).exists() else None
        self.audio_path = Path(ui["audio_path"]) if ui.get("audio_path") and Path(ui["audio_path"]).exists() else None
        self.srt_path = Path(ui["srt_path"]) if ui.get("srt_path") and Path(ui["srt_path"]).exists() else None
        self.manual_video_files = [x for x in ui.get("manual_video_files", []) if Path(x).exists()]
        self.settings.media.selected_files = list(self.manual_video_files) or list(getattr(self.settings.media, "selected_files", []))
        self.refresh_ui_from_state()
        self.save_last_settings()
        self.save_ui_state()
        messagebox.showinfo("불러오기 완료", f"프로젝트 불러오기 완료\n{filename}")

    def refresh_ui_from_state(self):
        if hasattr(self, "img_dir_label"):
            self.img_dir_label.config(text=(str(self.img_dir)[:30] + "...") if self.img_dir else "선택 안됨")
        if hasattr(self, "audio_label"):
            self.audio_label.config(text=self.audio_path.name if self.audio_path else "선택 안됨")
        if hasattr(self, "srt_label"):
            self.srt_label.config(text=self.srt_path.name if self.srt_path else "선택 안됨")
        if hasattr(self, "video_label"):
            files = [Path(x) for x in getattr(self.settings.media, "selected_files", []) if Path(x).exists()]
            self.video_label.config(text=(f"{len(files)}개 선택" if files else "선택 안됨"))
        if hasattr(self, "video_player"):
            # 저장된 외부 영상 목록은 렌더 입력용으로만 유지하고,
            # 프리뷰 목록에는 자동 주입하지 않습니다.
            self.video_player.external_video_files = []
            self.video_player.refresh_video_combo(auto_play=False)
        if hasattr(self, "settings_frame"):
            self.settings_frame.destroy()
            self.settings_frame = SettingsFrame(self.left_panel, self.settings, on_change_callback=self.update_preview, auto_save_callback=self.schedule_auto_save, get_initial_dir_callback=self.get_initial_dir, remember_path_callback=self.remember_path)
            self.settings_frame.pack(fill="both", expand=True, pady=(0, 10), before=self.warning_label)
        self.update_file_info()
        self.update_preview()

    def remember_path(self, key: str, path_value: Path | str | None):
        if not path_value:
            return
        p = Path(path_value)
        self.last_dirs[key] = str(p if p.is_dir() else p.parent)

    def get_initial_dir(self, key: str):
        v = self.last_dirs.get(key)
        return v if v and Path(v).exists() else None

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
            self.settings.video.zoom_center_only = False
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

            self.settings.image_watermark.brand_text = self.settings.image_watermark.brand_text or "오박사 만능인테리어"
            self.settings.image_watermark.phone_text = self.settings.image_watermark.phone_text or "010-8284-5584"
            self.settings.image_watermark.phone_gap_px = 47
            self.settings.image_watermark.brand_font_size = 46
            self.settings.image_watermark.phone_font_size = 43
            self.settings.image_watermark.margin_bottom = 80
            self.settings.image_watermark.box_enabled = True
            self.settings.image_watermark.box_alpha = 70
            self.settings.image_watermark.box_height_multiplier = 3.0
            self.settings.video_watermark = copy.deepcopy(self.settings.image_watermark)
            self.settings.watermark = self.settings.image_watermark

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
        
        tk.Label(header, text="SLID_Maker | FM연구소 v5.3", fg="#ffffff", bg="#0f1115", font=("Malgun Gothic", 18, "bold")).pack(anchor="w")
        tk.Label(header, text="1080x1920 / 반사배경 / 워터마크 / 자막 / 느린 중앙 줌 / 랜덤 오디오", fg="#9aa4b2", bg="#0f1115", font=("Malgun Gothic", 10)).pack(anchor="w", pady=(6, 0))
        
        main_container = tk.Frame(self.root, bg="#0f1115")
        main_container.pack(fill="both", expand=True, padx=16, pady=10)

        paned = tk.PanedWindow(main_container, orient="horizontal", sashrelief="flat", bg="#0f1115", bd=0, sashwidth=8)
        paned.pack(fill="both", expand=True)

        left_panel = tk.Frame(paned, bg="#0f1115")
        right_panel = tk.Frame(paned, bg="#0f1115")
        paned.add(left_panel, minsize=520)
        paned.add(right_panel, minsize=520)
        self.root.after(250, lambda: paned.sash_place(0, max(520, self.root.winfo_width() // 2), 0))
        self.left_panel = left_panel
        self.right_panel = right_panel
        
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

        video_frame = tk.Frame(file_frame, bg="#1a1e2a")
        video_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(video_frame, text="동영상 파일:", fg="#c7d0db", bg="#1a1e2a", width=12).pack(side="left")
        self.video_label = tk.Label(video_frame, text="선택 안됨", fg="#9aa4b2", bg="#1a1e2a", anchor="w", width=25)
        self.video_label.pack(side="left", fill="x", expand=True)
        video_btn_frame = tk.Frame(video_frame, bg="#1a1e2a")
        video_btn_frame.pack(side="right")
        ttk.Button(video_btn_frame, text="추가", command=self.select_video_files, width=8).pack(side="left", padx=2)
        ttk.Button(video_btn_frame, text="초기화", command=self.clear_video_files, width=8).pack(side="left", padx=2)
        
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
                                           auto_save_callback=self.schedule_auto_save,
                                           get_initial_dir_callback=self.get_initial_dir,
                                           remember_path_callback=self.remember_path)
        self.settings_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.warning_label = tk.Label(left_panel, text="", fg="#ffaa00", bg="#0f1115", font=("Malgun Gothic", 9), wraplength=400, justify="left")
        self.warning_label.pack(fill="x", pady=(0, 5))
        
        project_btn_frame = tk.Frame(left_panel, bg="#0f1115")
        project_btn_frame.pack(fill="x", pady=(0, 5))
        tk.Button(project_btn_frame, text="💾 전체 저장", command=self.save_project_bundle, bg="#3b4a6b", fg="white", relief="flat", font=("Malgun Gothic", 10)).pack(side="left", padx=(0,5))
        tk.Button(project_btn_frame, text="📂 전체 불러오기", command=self.load_project_bundle, bg="#4a5568", fg="white", relief="flat", font=("Malgun Gothic", 10)).pack(side="left")

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

        self.refresh_ui_from_state()
    
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
            on_folder_open_callback=lambda: self.open_folder(self.output_folder) if self.output_folder else None,
            get_initial_dir_callback=self.get_initial_dir,
            remember_path_callback=self.remember_path
        )
        # 프리뷰는 기본적으로 '생성된 출력 영상'만 표시합니다.
        # 외부 영상(selected_files)은 렌더 입력용으로 유지하되, 프리뷰 자동 목록에는 넣지 않습니다.
        self.video_player.external_video_files = []
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
        """영상 프리뷰 업데이트: 생성된 출력 영상만 표시"""
        preferred = self.last_output_video if self.last_output_video and Path(self.last_output_video).exists() else None
        if self.output_folder and self.output_folder.exists():
            self.video_player.update_video_list(self.output_folder, auto_play, preferred_video=preferred, external_videos=[])
        else:
            self.video_player.update_video_list(None, auto_play=False, preferred_video=preferred, external_videos=[])
    
    def select_img_dir(self):
        folder = filedialog.askdirectory(title="이미지 폴더 선택", initialdir=self.get_initial_dir("image"))
        if folder:
            self.img_dir = Path(folder)
            self.remember_path("image", self.img_dir)
            self.img_dir_label.config(text=str(self.img_dir)[:30] + "...")
            self.apply_image_based_defaults()
            self.update_file_info()
            self.update_preview()
            self.schedule_auto_save()
    
    def select_audio(self):
        file = filedialog.askopenfilename(title="오디오 파일 선택", initialdir=self.get_initial_dir("audio"), filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac"), ("All files", "*.*")])
        if file:
            self.audio_path = Path(file)
            self.remember_path("audio", self.audio_path)
            self.audio_label.config(text=self.audio_path.name)
            self.update_file_info()
            self.schedule_auto_save()
    
    def select_srt(self):
        file = filedialog.askopenfilename(title="자막 SRT 선택", initialdir=self.get_initial_dir("srt"), filetypes=[("SubRip", "*.srt"), ("All files", "*.*")])
        if file:
            self.srt_path = Path(file)
            self.remember_path("srt", self.srt_path)
            self.srt_label.config(text=self.srt_path.name)
            self.schedule_auto_save()
    
    def select_audio_srt_pair(self):
        audio_file = filedialog.askopenfilename(title="오디오 파일 선택 (자막은 자동 찾기)", initialdir=self.get_initial_dir("audio"), filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac *.flac"), ("All files", "*.*")])
        if not audio_file: return
        
        audio_path = Path(audio_file)
        self.audio_path = audio_path
        self.remember_path("audio", audio_path)
        self.audio_label.config(text=audio_path.name)
        
        srt_candidates = [audio_path.with_suffix(".srt"), audio_path.parent / f"{audio_path.stem}.srt"]
        
        for srt_path in srt_candidates:
            if srt_path.exists():
                self.srt_path = srt_path
                self.remember_path("srt", srt_path)
                self.srt_label.config(text=srt_path.name)
                messagebox.showinfo("자막 발견", f"자막 파일이 자동으로 선택되었습니다:\n{srt_path.name}")
                break
        else:
            if messagebox.askyesno("자막 없음", "같은 이름의 SRT 파일이 없습니다. 직접 선택하시겠습니까?"):
                self.select_srt()
        
        self.update_file_info()
        self.schedule_auto_save()
    
    def select_video_files(self):
        files = filedialog.askopenfilenames(title="동영상 파일 선택", initialdir=self.get_initial_dir("video"), filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.m4v *.webm"), ("All files", "*.*")])
        if files:
            self.manual_video_files = list(files)
            self.settings.media.selected_files = list(files)
            self.settings.media.enabled = True
            self.remember_path("video", Path(files[0]))
            self.video_label.config(text=f"{len(files)}개 선택")
            if hasattr(self, "video_player"):
                self.video_player.external_video_files = [Path(x) for x in files]
                self.video_player.refresh_video_combo(auto_play=False)
            self.schedule_auto_save()

    def clear_video_files(self):
        self.manual_video_files = []
        self.current_log_file = None
        self.settings.media.selected_files = []
        self.settings.media.enabled = False
        if hasattr(self, "video_label"):
            self.video_label.config(text="선택 안됨")
        if hasattr(self, "video_player"):
            self.video_player.external_video_files = []
            self.video_player.refresh_video_combo(auto_play=False)
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
        
        self.settings = normalize_settings_types(self.settings_frame.apply_settings())
        
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
    
    def _begin_run_log(self):
        self.current_log_files = []
        try:
            ensure_runtime_dirs()
            ts = time.strftime('%Y%m%d_%H%M%S')
            runtime_log = APP_LOG_DIR / f'slid_run_{ts}.log'
            header = [
                f'시작시각: {time.strftime("%Y-%m-%d %H:%M:%S")}',
                f'이미지폴더: {self.img_dir or ""}',
                f'오디오파일: {self.audio_path or ""}',
                f'SRT파일: {self.srt_path or ""}',
                ''
            ]
            runtime_log.parent.mkdir(parents=True, exist_ok=True)
            runtime_log.write_text("\n".join(header), encoding='utf-8')
            self.current_log_files.append(runtime_log)
            if self.img_dir:
                try:
                    project_log_dir = Path(self.img_dir) / 'OUTPUT' / 'logs'
                    project_log_dir.mkdir(parents=True, exist_ok=True)
                    project_log = project_log_dir / f'slid_run_{ts}.log'
                    project_log.write_text("\n".join(header), encoding='utf-8')
                    self.current_log_files.append(project_log)
                except Exception:
                    pass
            self.current_log_file = self.current_log_files[0] if self.current_log_files else None
        except Exception:
            self.current_log_file = None
            self.current_log_files = []

    def _append_run_log(self, s: str):
        for fp in getattr(self, 'current_log_files', []) or ([] if not getattr(self, 'current_log_file', None) else [self.current_log_file]):
            try:
                with fp.open('a', encoding='utf-8') as f:
                    f.write(s + '\n')
            except Exception:
                pass

    def log(self, s: str):
        safe_print(s)
        self._append_run_log(s)
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
        
        self.settings = normalize_settings_types(self.settings_frame.apply_settings())
        
        warnings = validate_settings(self.settings)
        if warnings:
            for w in warnings:
                self.log(f"⚠️ {w}")
        
        self._begin_run_log()
        if getattr(self, "current_log_files", None):
            self.log(f"로그 저장 위치: {self.current_log_files[0]}")
            if len(self.current_log_files) > 1:
                self.log(f"프로젝트 로그 위치: {self.current_log_files[1]}")
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
            self.qevt.put(("progress", "시작", "전처리(반사 배경 / 슬라이드용 원본) 시작"))
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
                    cleanup_project_artifacts(img_dir, self.qevt)
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
        # 작업 완료 후 자동으로 영상 프리뷰 탭으로 전환
        if reports and self.preview_mode.get() != "video":
            self.preview_mode.set("video")
            self.switch_preview_mode()

        if reports:
            try:
                latest = max([r.output_mp4 for r in reports if Path(r.output_mp4).exists()], key=lambda p: Path(p).stat().st_mtime)
                self.last_output_video = str(latest)
            except Exception:
                self.last_output_video = str(reports[0].output_mp4)

        # 프리뷰 목록만 갱신하고 자동 재생은 여기서 한 번만 처리합니다.
        if self.preview_mode.get() == "video":
            self.update_video_preview(auto_play=False)
            if self.last_output_video and hasattr(self, "video_player"):
                try:
                    self.video_player.load_video(Path(self.last_output_video), auto_play=False)
                    self.root.after(400, lambda: self.video_player.play_with_vlc_external(Path(self.last_output_video)))
                except Exception:
                    pass
        
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
                        try:
                            latest = max([r.output_mp4 for r in reports if Path(r.output_mp4).exists()], key=lambda p: Path(p).stat().st_mtime)
                            self.last_output_video = str(latest)
                        except Exception:
                            self.last_output_video = str(reports[0].output_mp4)

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
    parser.add_argument("--brand-name")
    parser.add_argument("--phone-number")
    parser.add_argument("--brand-size", type=int)
    parser.add_argument("--phone-size", type=int)
    parser.add_argument("--margin-bottom", type=int)
    parser.add_argument("--box-enabled")
    parser.add_argument("--stroke-enabled")
    parser.add_argument("--shadow-enabled")
    parser.add_argument("--subtitle-enabled")
    parser.add_argument("--subtitle-font-size", type=int)
    parser.add_argument("--subtitle-margin", type=int)
    parser.add_argument("--resolution")
    parser.add_argument("--fps", type=int)
    parser.add_argument("--nvenc-preset")
    args = parser.parse_args()

    image_folder = Path(args.image_folder)
    audio_path = Path(args.audio)
    srt_path = Path(args.srt) if args.srt else None
    project_dir = Path(args.project_dir)
    project_key = args.project_key

    project_dir.mkdir(parents=True, exist_ok=True)

    qevt = _queue.Queue()
    settings = AppSettings()

    # Apply web/API environment options in headless mode.
    if os.environ.get('SLID_BRAND_NAME'):
        settings.image_watermark.brand_text = os.environ.get('SLID_BRAND_NAME')
    if os.environ.get('SLID_PHONE_NUMBER'):
        settings.image_watermark.phone_text = os.environ.get('SLID_PHONE_NUMBER')
    if os.environ.get('SLID_BRAND_SIZE'):
        settings.image_watermark.brand_font_size = int(os.environ.get('SLID_BRAND_SIZE'))
    if os.environ.get('SLID_PHONE_SIZE'):
        settings.image_watermark.phone_font_size = int(os.environ.get('SLID_PHONE_SIZE'))
    if os.environ.get('SLID_MARGIN_BOTTOM'):
        settings.image_watermark.margin_bottom = int(os.environ.get('SLID_MARGIN_BOTTOM'))
    if os.environ.get('SLID_BOX_ENABLED'):
        settings.image_watermark.box_enabled = os.environ.get('SLID_BOX_ENABLED').lower() == 'true'
    if os.environ.get('SLID_STROKE_ENABLED'):
        settings.image_watermark.stroke_enabled = os.environ.get('SLID_STROKE_ENABLED').lower() == 'true'
    if os.environ.get('SLID_SHADOW_ENABLED'):
        settings.image_watermark.shadow_enabled = os.environ.get('SLID_SHADOW_ENABLED').lower() == 'true'
    if os.environ.get('SLID_IMAGE_SEC'):
        settings.video.base_image_sec = float(os.environ.get('SLID_IMAGE_SEC'))
    if os.environ.get('SLID_TRANSITION_SEC'):
        trans_sec = float(os.environ.get('SLID_TRANSITION_SEC'))
        if settings.video.base_image_sec > 0:
            settings.video.transition_ratio = trans_sec / settings.video.base_image_sec
    if os.environ.get('SLID_ZOOM_INTENSITY'):
        settings.video.zoom_intensity = float(os.environ.get('SLID_ZOOM_INTENSITY'))
    if os.environ.get('SLID_ZOOM_CENTER_ONLY') is not None:
        settings.video.zoom_center_only = os.environ.get('SLID_ZOOM_CENTER_ONLY', '').strip().lower() in {'1', 'true', 'yes', 'on'}
    if os.environ.get('SLID_SUBTITLE_ENABLED'):
        settings.subtitle.enabled = os.environ.get('SLID_SUBTITLE_ENABLED').lower() == 'true'
    if os.environ.get('SLID_SUBTITLE_SIZE'):
        settings.subtitle.font_size = int(os.environ.get('SLID_SUBTITLE_SIZE'))
    if os.environ.get('SLID_SUBTITLE_MARGIN'):
        settings.subtitle.margin_v = int(os.environ.get('SLID_SUBTITLE_MARGIN'))
    if os.environ.get('SLID_RESOLUTION'):
        res_str = os.environ.get('SLID_RESOLUTION')
        if 'x' in res_str:
            try:
                w_str, h_str = res_str.split('x')
                settings.video.width = int(w_str)
                settings.video.height = int(h_str)
                print(f"[환경변수] 해상도 설정: {settings.video.width}x{settings.video.height}")
            except Exception as e:
                print(f"[환경변수] 해상도 파싱 실패: {e}")
    if os.environ.get('SLID_FPS'):
        try:
            settings.video.fps = int(os.environ.get('SLID_FPS'))
            print(f"[환경변수] FPS 설정: {settings.video.fps}")
        except Exception as e:
            print(f"[환경변수] FPS 파싱 실패: {e}")
    if os.environ.get('SLID_NVENC_PRESET'):
        preset_val = os.environ.get('SLID_NVENC_PRESET')
        settings.encoding.nvenc_preset = preset_val
        settings.encoding.sns_nvenc_preset = preset_val
        settings.encoding.hq_nvenc_preset = preset_val
        print(f"[환경변수] NVENC 프리셋 설정: {preset_val}")

    def _cli_bool(value: str) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    if args.brand_name is not None:
        settings.image_watermark.brand_text = args.brand_name
        print(f"[CLI] 상호명: {settings.image_watermark.brand_text}")
    if args.phone_number is not None:
        settings.image_watermark.phone_text = args.phone_number
        print(f"[CLI] 전화번호: {settings.image_watermark.phone_text}")
    if args.brand_size is not None:
        settings.image_watermark.brand_font_size = args.brand_size
    if args.phone_size is not None:
        settings.image_watermark.phone_font_size = args.phone_size
    if args.margin_bottom is not None:
        settings.image_watermark.margin_bottom = args.margin_bottom
    if args.box_enabled is not None:
        settings.image_watermark.box_enabled = _cli_bool(args.box_enabled)
    if args.stroke_enabled is not None:
        settings.image_watermark.stroke_enabled = _cli_bool(args.stroke_enabled)
    if args.shadow_enabled is not None:
        settings.image_watermark.shadow_enabled = _cli_bool(args.shadow_enabled)
    if args.subtitle_enabled is not None:
        settings.subtitle.enabled = _cli_bool(args.subtitle_enabled)
    if args.subtitle_font_size is not None:
        settings.subtitle.font_size = args.subtitle_font_size
    if args.subtitle_margin is not None:
        settings.subtitle.margin_v = args.subtitle_margin
    if args.resolution:
        try:
            w_str, h_str = args.resolution.lower().split("x", 1)
            settings.video.width = int(w_str)
            settings.video.height = int(h_str)
            print(f"[CLI] 해상도 설정: {settings.video.width}x{settings.video.height}")
        except Exception as e:
            print(f"[CLI] 해상도 파싱 실패: {e}")
    if args.fps is not None:
        settings.video.fps = args.fps
        print(f"[CLI] FPS 설정: {settings.video.fps}")
    if args.nvenc_preset:
        settings.encoding.nvenc_preset = args.nvenc_preset
        settings.encoding.sns_nvenc_preset = args.nvenc_preset
        settings.encoding.hq_nvenc_preset = args.nvenc_preset
        print(f"[CLI] NVENC 프리셋 설정: {args.nvenc_preset}")
    settings.video_watermark = copy.deepcopy(settings.image_watermark)
    settings.watermark = settings.image_watermark
    settings = normalize_settings_types(settings)

    out_folder, pre_imgs = preprocess_images(image_folder, settings, qevt, preview_only=False)
    
    # Ensure project_dir / 'output' points to the preprocessed images in image_folder / 'output'
    project_output_dir = project_dir / 'output'
    try:
        # Check both is_symlink() and exists() to handle broken symlinks correctly
        if project_output_dir.is_symlink() or project_output_dir.exists():
            if project_output_dir.is_symlink():
                project_output_dir.unlink()
            else:
                _shutil.rmtree(project_output_dir)
    except Exception:
        pass
    try:
        project_output_dir.symlink_to(image_folder / 'output', target_is_directory=True)
    except Exception:
        try:
            _shutil.copytree(image_folder / 'output', project_output_dir, dirs_exist_ok=True)
        except Exception:
            pass

    try:
        _ = build_video_onepass(pre_imgs, audio_path, srt_path, base_dir=project_dir, settings=settings, qevt=qevt)
    finally:
        while not qevt.empty():
            item = qevt.get()
            if isinstance(item, tuple) and len(item) >= 2:
                print(item[1])

    cand_root = project_dir / "OUTPUT"
    built_mp4s = sorted((p for p in cand_root.glob("*.mp4") if not p.stem.endswith(".preview")), key=lambda p: p.stat().st_mtime, reverse=True) if cand_root.exists() else []
    if not built_mp4s:
        built_mp4s = sorted((p for p in project_dir.rglob("*.mp4") if not p.stem.endswith(".preview")), key=lambda p: p.stat().st_mtime, reverse=True)
    if not built_mp4s:
        raise RuntimeError("MP4 생성 실패: 결과 mp4를 찾지 못했습니다.")

    final_mp4 = project_dir / f"{project_key}.mp4"
    final_preview_mp4 = project_dir / f"{project_key}.preview.mp4"
    source_preview_mp4 = built_mp4s[0].with_name(f"{built_mp4s[0].stem}.preview.mp4")
    try:
        if final_mp4.exists():
            final_mp4.unlink()
        if final_preview_mp4.exists():
            final_preview_mp4.unlink()
    except Exception:
        pass
    built_mp4s[0].replace(final_mp4)
    if source_preview_mp4.exists():
        source_preview_mp4.replace(final_preview_mp4)

    try:
        _shutil.rmtree(project_dir / "OUTPUT", ignore_errors=True)
    except Exception:
        pass

    print(f"[DONE] {final_mp4}")
