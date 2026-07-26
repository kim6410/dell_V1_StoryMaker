# ===== 콘솔 숨김 =====
import sys
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass
# ====================

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

# 한글 폰트 강제 설정
KOREAN_FONT = "Malgun Gothic"  # 맑은 고딕으로 강제 지정

# 기존 프로그램들을 모듈로 임포트
sys.path.insert(0, os.path.dirname(__file__))

# SLID_Maker의 CineUI 클래스 임포트
try:
    from SLID_Maker import CineUI
except Exception:
    from SLID_Maker_stable_v2 import CineUI
# podcast_generator의 PodcastGenerator 클래스 임포트
from podcast_generator import PodcastGenerator

class IntegratedStudio:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎬 KKBBQ_통합 제작 스튜디오")
        self.root.state('zoomed')  # 전체화면
        
        self.slid_app = None
        self.podcast_app = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # 메인 컨테이너
        main_container = tk.Frame(self.root)
        main_container.pack(fill="both", expand=True)
        
        # 상단 툴바
        toolbar = tk.Frame(main_container, bg="#2c3e50", height=40)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        
        # 한글 폰트 강제 적용
        title_font = (KOREAN_FONT, 14, "bold")
        status_font = (KOREAN_FONT, 10)
        button_font = (KOREAN_FONT, 10, "bold")
        label_font = (KOREAN_FONT, 12, "bold")
        
        tk.Label(toolbar, text="🎬 KKBBQ_통합 제작 스튜디오", 
                font=title_font,
                fg="white", bg="#2c3e50").pack(side="left", padx=10, pady=5)
        
        # 종료 버튼 (우측 상단)
        self.close_btn = tk.Button(toolbar, text="✕ 종료", 
                                   command=self.close_all,
                                   bg="#e74c3c", fg="white",
                                   font=button_font,
                                   relief="flat", cursor="hand2",
                                   width=8)
        self.close_btn.pack(side="right", padx=10, pady=5)
        
        # 상태 표시
        self.status_label = tk.Label(toolbar, text="● 로딩중...", 
                                     fg="#f1c40f", bg="#2c3e50",
                                     font=status_font)
        self.status_label.pack(side="right", padx=10)
        
        # 메인 콘텐츠 영역 (가변 분할)
        content_frame = tk.Frame(main_container, bg="#203040")
        content_frame.pack(fill="both", expand=True)

        self.splitter = tk.PanedWindow(
            content_frame, orient="horizontal", sashwidth=8, sashrelief="flat",
            bg="#203040", bd=0, relief="flat", opaqueresize=True
        )
        self.splitter.pack(fill="both", expand=True)

        # 왼쪽: 팟캐스트 생성기
        left_frame = tk.Frame(self.splitter, bg="#34495e")
        tk.Label(left_frame, text="🎙️ 팟캐스트 생성기", 
                font=label_font,
                fg="white", bg="#34495e").pack(pady=4)

        self.podcast_container = tk.Frame(left_frame, bg="white", relief="sunken", bd=1)
        self.podcast_container.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # 오른쪽: SLID 메이커
        right_frame = tk.Frame(self.splitter, bg="#2c3e50")
        tk.Label(right_frame, text="📱 KKBBQ_숏폼 제작기", 
                font=label_font,
                fg="white", bg="#2c3e50").pack(pady=4)

        self.slid_container = tk.Frame(right_frame, bg="white", relief="sunken", bd=1)
        self.slid_container.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self.splitter.add(left_frame, minsize=860, stretch="always")
        self.splitter.add(right_frame, minsize=760, stretch="always")

        # 기본 비율: 팟캐스트 54% / 숏폼 46%
        self.root.after(200, self.set_initial_split)
        
        # 하단 상태바
        statusbar = tk.Frame(main_container, bg="#34495e", height=25)
        statusbar.pack(fill="x")
        statusbar.pack_propagate(False)
        
        self.file_status = tk.Label(statusbar, text="", 
                                     fg="white", bg="#34495e",
                                     font=(KOREAN_FONT, 9))
        self.file_status.pack(side="left", padx=10)
        
        # 프로그램 로드
        self.root.after(100, self.load_programs)
        
    def set_initial_split(self):
        try:
            total_w = max(self.root.winfo_width(), 1600)
            left_w = int(total_w * 0.54)
            self.splitter.sash_place(0, left_w, 0)
        except Exception:
            pass

    def load_programs(self):
        """각 프로그램을 프레임에 직접 로드"""
        try:
            self.status_label.config(text="● SLID 로딩중...", fg="#f1c40f")
            self.root.update()
            
            # SLID 메이커를 프레임 모드로 실행
            self.slid_app = CineUI(embed_mode=True, parent=self.slid_container)
            
            self.status_label.config(text="● Podcast 로딩중...", fg="#f1c40f")
            self.root.update()
            
            # 팟캐스트 생성기를 프레임 모드로 실행
            self.podcast_app = PodcastGenerator(embed_mode=True, parent=self.podcast_container)
            
            self.status_label.config(text="● 실행중", fg="#2ecc71")
            self.update_file_status()
            
        except Exception as e:
            self.status_label.config(text="● 오류", fg="#e74c3c")
            messagebox.showerror("로딩 오류", f"프로그램 로딩 중 오류 발생:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def update_file_status(self):
        """파일 상태 업데이트"""
        slid_path = os.path.join(os.path.dirname(__file__), "SLID_Maker.pyw")
        podcast_path = os.path.join(os.path.dirname(__file__), "podcast_generator.pyw")
        
        slid_exists = os.path.exists(slid_path)
        podcast_exists = os.path.exists(podcast_path)
        
        status = []
        if slid_exists:
            slid_size = os.path.getsize(slid_path)
            status.append(f"📱 SLID: {slid_size:,} bytes")
        else:
            status.append("📱 SLID: 파일 없음")
        
        if podcast_exists:
            podcast_size = os.path.getsize(podcast_path)
            status.append(f"🎙️ Podcast: {podcast_size:,} bytes")
        else:
            status.append("🎙️ Podcast: 파일 없음")
        
        self.file_status.config(text=" | ".join(status))
        self.root.after(5000, self.update_file_status)
    
    def close_all(self):
        """모든 프로그램 종료"""
        if messagebox.askyesno("종료 확인", "통합 스튜디오를 종료할까요?"):
            try:
                if self.slid_app:
                    self.slid_app.on_closing()
            except:
                pass
            
            try:
                if self.podcast_app:
                    self.podcast_app.quit_program()
            except:
                pass
            
            self.root.quit()
            self.root.destroy()
            sys.exit(0)
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.close_all)
        self.root.mainloop()

# FontManager 클래스 (podcast_generator에서 필요)
class FontManager:
    def __init__(self):
        self.font_family = "Malgun Gothic"  # 맑은 고딕으로 강제
        self.font_cache = {}
        self.font_sizes = {
            'title': 28, 'subtitle': 20, 'heading': 16,
            'body': 14, 'small': 12, 'button_large': 24,
            'button_normal': 16, 'button_small': 14, 'subtitle_large': 18
        }
    
    def get_font(self, size_key='body', weight="normal"):
        import customtkinter as ctk
        size = self.font_sizes.get(size_key, 14)
        return ctk.CTkFont(family=self.font_family, size=size, weight=weight)
    
    def get_custom_font(self, size, weight="normal"):
        import customtkinter as ctk
        return ctk.CTkFont(family=self.font_family, size=size, weight=weight)

if __name__ == "__main__":
    app = IntegratedStudio()
    app.run()