
# -*- coding: utf-8 -*-
"""
AI Shortform Studio – Render Edition
이미지 + 영상 + 자막 + 배경음악 → MP4 생성
moviepy 2.x 호환
"""

import os
import random
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

# ===============================
# 관리자 설정 (컨트롤 센터)
# ===============================

IMAGE_DURATION = 3
VIDEO_INTERVAL = 4
OUTPUT_FILE = "render_output.mp4"
SUBTITLE_FONT_SIZE = 40
MUSIC_VOLUME = 0.35

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXT = (".mp4", ".mov", ".mkv")

# ===============================
# moviepy import
# ===============================

try:
    from moviepy import (
        ImageClip,
        VideoFileClip,
        AudioFileClip,
        CompositeVideoClip,
        concatenate_videoclips,
        TextClip
    )
except Exception as e:
    print("moviepy import 실패")
    print(e)
    sys.exit(1)


# ===============================
# 미디어 스캔
# ===============================

def scan_media(folder):

    images = []
    videos = []

    for f in os.listdir(folder):

        p = os.path.join(folder, f)

        if f.lower().endswith(IMAGE_EXT):
            images.append(p)

        elif f.lower().endswith(VIDEO_EXT):
            videos.append(p)

    return images, videos


# ===============================
# 타임라인 생성
# ===============================

def build_timeline(images, videos):

    timeline = []
    count = 0

    for img in images:

        timeline.append(("image", img))

        count += 1

        if videos and count % VIDEO_INTERVAL == 0:
            timeline.append(("video", random.choice(videos)))

    return timeline


# ===============================
# 영상 생성
# ===============================

def render_video(folder):

    images, videos = scan_media(folder)

    if not images:
        raise Exception("이미지가 없습니다")

    timeline = build_timeline(images, videos)

    clips = []

    for t, path in timeline:

        if t == "image":

            clip = (
                ImageClip(path)
                .with_duration(IMAGE_DURATION)
                .resized(height=1080)
            )

        else:

            clip = VideoFileClip(path).subclipped(0, min(5, VideoFileClip(path).duration))

        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")

    subtitle = (
        TextClip(
            text="AI Shortform Studio",
            font_size=SUBTITLE_FONT_SIZE,
            color="white"
        )
        .with_position(("center", "bottom"))
        .with_duration(video.duration)
    )

    final = CompositeVideoClip([video, subtitle])

    music_path = None

    for f in os.listdir(folder):
        if f.endswith(".mp3"):
            music_path = os.path.join(folder, f)
            break

    if music_path:

        audio = AudioFileClip(music_path).with_volume_scaled(MUSIC_VOLUME)

        final = final.with_audio(audio)

    out = os.path.join(folder, OUTPUT_FILE)

    final.write_videofile(
        out,
        codec="libx264",
        audio_codec="aac",
        fps=30
    )

    return out


# ===============================
# UI
# ===============================

class App:

    def __init__(self, root):

        self.root = root
        root.title("AI Shortform Studio – Render")
        root.geometry("420x260")

        tk.Button(root, text="미디어 폴더 선택", command=self.select).pack(pady=10)
        tk.Button(root, text="MP4 생성", command=self.render).pack(pady=10)

        self.label = tk.Label(root, text="대기중")
        self.label.pack(pady=10)

        self.folder = None

    def select(self):

        self.folder = filedialog.askdirectory()

        if not self.folder:
            return

        self.label.config(text=f"선택됨\n{self.folder}")

    def render(self):

        if not self.folder:
            messagebox.showerror("오류", "폴더 먼저 선택")
            return

        try:

            self.label.config(text="렌더링 시작...")
            self.root.update()

            out = render_video(self.folder)

            self.label.config(text="완료")
            messagebox.showinfo("완료", f"MP4 생성 완료\n{out}")

            os.startfile(out)

        except Exception as e:

            messagebox.showerror("렌더 오류", str(e))


# ===============================

if __name__ == "__main__":

    root = tk.Tk()
    App(root)
    root.mainloop()
