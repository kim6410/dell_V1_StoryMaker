
# -*- coding: utf-8 -*-
"""
AI Shortform Studio FINAL
이미지 + 영상 + TTS → 숏폼 MP4 자동 생성
"""

import os
import asyncio
import random
import tkinter as tk
from tkinter import filedialog, messagebox

IMAGE_DURATION = 3
VIDEO_INSERT_INTERVAL = 4
WIDTH = 1080
HEIGHT = 1920
FPS = 30
OUTPUT_NAME = "shortform_output.mp4"
SUBTITLE_SIZE = 48
MUSIC_VOLUME = 0.3
VOICE = "ko-KR-SunHiNeural"

IMAGE_EXT = (".jpg",".jpeg",".png",".webp")
VIDEO_EXT = (".mp4",".mov",".mkv")

from moviepy import (
    ImageClip,
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    TextClip
)

import edge_tts

async def generate_tts(text, output):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output)

def create_tts(text, path):
    asyncio.run(generate_tts(text, path))

def scan(folder):

    images=[]
    videos=[]
    music=None

    for f in os.listdir(folder):

        p=os.path.join(folder,f)

        if f.lower().endswith(IMAGE_EXT):
            images.append(p)

        elif f.lower().endswith(VIDEO_EXT):
            videos.append(p)

        elif f.lower().endswith(".mp3"):
            music=p

    return images,videos,music

def build_timeline(images,videos):

    timeline=[]
    c=0

    for img in images:

        timeline.append(("image",img))
        c+=1

        if videos and c%VIDEO_INSERT_INTERVAL==0:
            timeline.append(("video",random.choice(videos)))

    return timeline

def render(folder,script):

    images,videos,music=scan(folder)

    if not images:
        raise Exception("이미지가 없습니다")

    timeline=build_timeline(images,videos)

    clips=[]

    for t,p in timeline:

        if t=="image":

            clip=(
                ImageClip(p)
                .with_duration(IMAGE_DURATION)
                .resized(height=HEIGHT)
            )

        else:

            v=VideoFileClip(p)
            clip=v.subclipped(0,min(5,v.duration)).resized(height=HEIGHT)

        clips.append(clip)

    base=concatenate_videoclips(clips,method="compose")

    tts_path=os.path.join(folder,"tts_voice.mp3")
    create_tts(script,tts_path)

    tts_audio=AudioFileClip(tts_path)

    video=base.with_audio(tts_audio)

    subtitle=(
        TextClip(
            text=script,
            font_size=SUBTITLE_SIZE,
            color="white",
            size=(WIDTH,None),
            method="caption"
        )
        .with_position(("center","bottom"))
        .with_duration(video.duration)
    )

    video=CompositeVideoClip([video,subtitle],size=(WIDTH,HEIGHT))

    if music:

        bg=AudioFileClip(music).with_volume_scaled(MUSIC_VOLUME)
        video=video.with_audio(bg)

    out=os.path.join(folder,OUTPUT_NAME)

    video.write_videofile(
        out,
        fps=FPS,
        codec="libx264",
        audio_codec="aac"
    )

    return out

class App:

    def __init__(self,root):

        self.root=root
        root.title("AI Shortform Studio FINAL")
        root.geometry("420x420")

        tk.Button(root,text="미디어 폴더 선택",command=self.select).pack(pady=10)

        self.script_box=tk.Text(root,height=6,width=40)
        self.script_box.pack(pady=10)
        self.script_box.insert("1.0","여기에 영상 TTS 스크립트를 입력하세요")

        tk.Button(root,text="MP4 생성",command=self.render).pack(pady=10)

        self.label=tk.Label(root,text="대기중")
        self.label.pack(pady=10)

        self.folder=None

    def select(self):

        self.folder=filedialog.askdirectory()

        if self.folder:
            self.label.config(text=self.folder)

    def render(self):

        if not self.folder:
            messagebox.showerror("오류","폴더 먼저 선택")
            return

        script=self.script_box.get("1.0","end").strip()

        if not script:
            messagebox.showerror("오류","스크립트 입력 필요")
            return

        try:

            self.label.config(text="렌더링 중...")
            self.root.update()

            out=render(self.folder,script)

            self.label.config(text="완료")

            messagebox.showinfo("완료",f"영상 생성 완료\n{out}")

            os.startfile(out)

        except Exception as e:

            messagebox.showerror("오류",str(e))

if __name__=="__main__":

    root=tk.Tk()
    App(root)
    root.mainloop()
