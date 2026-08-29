# -*- coding: utf-8 -*-
"""
로컬 웹앱 FastAPI 서버 - 통합 숏폼 제작 시스템
확정 조건 완전 반영:
- 3열 레이아웃 + 우측 외부도구 토글
- 프로젝트명: 업체명_날짜_제목 (자동 정규화)
- podcast/, SlidShow/, music/ 폴더 규칙
- 이미지 다중 업로드 + 폴더 업로드 지원
- iframe 외부도구 + 차단시 새탭 전환
- 최신 mp4 50개 히스토리
- 워터마크 설정 전달 기능 추가
- 유튜브 링크 자동 실행 기능 개선
"""

import os
import sys
import re
import shutil
import subprocess
import asyncio
import json
import time
import glob
import secrets
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import uuid
import urllib.request
import urllib.error

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
import uvicorn

# =============================================================================
# 설정
# =============================================================================
BASE_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = BASE_DIR / "OUTPUT"
MUSIC_DIR = BASE_DIR / "music"
PODCAST_DIR = BASE_DIR / "podcast"
SLIDESHOW_DIR = BASE_DIR / "SlidShow"
TEMP_DIR = BASE_DIR / "temp"
UPLOAD_DIR = BASE_DIR / "uploads"
USER_JOBS_DIR = BASE_DIR / "user_jobs"
STATIC_DIR = BASE_DIR / "static"

# 폴더 생성
for dir_path in [MUSIC_DIR, PODCAST_DIR, SLIDESHOW_DIR, TEMP_DIR, UPLOAD_DIR, USER_JOBS_DIR, STATIC_DIR, OUTPUT_DIR]:
    dir_path.mkdir(exist_ok=True)

# 임시 이미지 폴더 정리 함수 (24시간 경과 폴더 삭제)
def cleanup_old_slideshow_uploads():
    """Delete slideshow upload folders older than 24 hours."""
    try:
        slideshow_uploads = UPLOAD_DIR / "slideshow"
        if not slideshow_uploads.exists():
            return
        now = time.time()
        cutoff = now - 24 * 3600 # 24 hours ago
        for user_dir in slideshow_uploads.iterdir():
            if user_dir.is_dir():
                for job_dir in user_dir.iterdir():
                    if job_dir.is_dir():
                        mtime = job_dir.stat().st_mtime
                        if mtime < cutoff:
                            print(f"[cleanup] Deleting old slideshow temp dir: {job_dir}")
                            shutil.rmtree(job_dir, ignore_errors=True)
                if not any(user_dir.iterdir()):
                    try:
                        user_dir.rmdir()
                    except Exception:
                        pass
    except Exception as e:
        print(f"[cleanup] Error during old uploads cleanup: {e}")



# =============================================================================
# 유틸: project_key 안전화 + 프로젝트 폴더 생성
# =============================================================================
def safe_name(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

def ensure_project_dirs(project_key: str):
    project_key = safe_name(project_key)
    if not project_key:
        raise ValueError("project_key가 비었습니다.")
    project_dir = OUTPUT_DIR / project_key
    images_dir = project_dir / "images"
    project_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    return project_key, project_dir, images_dir

def preview_mp4_path(mp4_path: Path) -> Path:
    return mp4_path.with_name(f"{mp4_path.stem}.preview.mp4")

def create_slideshow_preview_mp4(mp4_path: Path, log: list[str] | None = None) -> Path | None:
    if not mp4_path.exists():
        return None

    preview_path = preview_mp4_path(mp4_path)
    if preview_path.exists():
        if log is not None:
            log.append(f"미리보기 MP4 재사용: {preview_path.name}")
        return preview_path

    cmd = [
        "ffmpeg", "-hide_banner", "-y",
        "-i", str(mp4_path),
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
        "-r", "24",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", "3M",
        "-maxrate", "4M",
        "-bufsize", "6M",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(preview_path),
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300, check=True)
        if log is not None:
            log.append(f"미리보기 MP4 생성: {preview_path.name}")
        return preview_path
    except Exception as exc:
        if log is not None:
            log.append(f"미리보기 MP4 생성 실패: {exc}")
        try:
            preview_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None

def file_mtime(path: Path | None) -> float | None:
    return path.stat().st_mtime if path and path.exists() else None

# 음악 파일 목록 캐시
MUSIC_FILES = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav")) + list(MUSIC_DIR.glob("*.m4a"))

app = FastAPI(title="숏폼 스튜디오 로컬 서버")

@app.on_event("startup")
async def startup_event():
    cleanup_old_slideshow_uploads()
    cleanup_expired_user_data()
    await ensure_podcast_worker_started()
    asyncio.create_task(periodic_cleanup_worker())

# CORS 설정 (로컬 개발용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    api_key = os.environ.get("SUPERTONIC_API_KEY", "")
    authorization = request.headers.get("Authorization", "")
    if not api_key or not secrets.compare_digest(authorization, f"Bearer {api_key}"):
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await call_next(request)

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# =============================================================================
# 작업 상태 관리 (메모리 저장 - 간단 버전)
# =============================================================================
def _voice_readable_text(text: str):
    """TTS용 전화번호 발음 변환.

    중요:
    기존 구현은 split() 후 " ".join()을 사용해서 줄바꿈을 모두 없앴습니다.
    그 결과 [여성]/[남성] 또는 #F1/#M1 화자 태그가 대사와 한 줄에 붙어
    podcast_generator.pyw 세그먼트 파싱이 실패했습니다.

    이 함수는 원본 줄바꿈을 보존하면서 전화번호만 발음형으로 바꿉니다.
    """
    ko = "공일이삼사오육칠팔구"

    def rd(value: str) -> str:
        return "".join(ko[int(ch)] if ch.isdigit() else ch for ch in value)

    back = {}
    source = text or ""
    phone_pattern = re.compile(r"(?<!\d)(01[016789])[-.\s]?(\d{3,4})[-.\s]?(\d{4})(?!\d)")

    def repl(match: re.Match) -> str:
        original = match.group(0)
        first, middle, last = match.groups()
        spoken = f"{rd(first)}, {rd(middle)}, {rd(last)}"
        back[spoken] = original
        return spoken

    return phone_pattern.sub(repl, source), back

jobs = {}  # job_id -> {status, percent, stage, eta, log, result}


def _set_job_terminal_status(job_id: str, status: str) -> None:
    """종료 상태와 실제 종료 시각을 함께 기록합니다."""
    job = jobs.get(job_id)
    if not job:
        return
    job["status"] = status
    job["finished_ts"] = time.time()


slideshow_render_lock = threading.Lock()
slideshow_queue_lock = threading.Lock()
slideshow_waiting_jobs = deque()
slideshow_running_processes = {}  # job_id -> subprocess.Popen
podcast_job_queue: asyncio.Queue | None = None
podcast_worker_started = False

RETENTION_SECONDS = 7 * 24 * 60 * 60
MEMORY_JOB_RETENTION_SECONDS = 6 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 60 * 60
GENERATED_DATA_DIRS = (
    OUTPUT_DIR,
    PODCAST_DIR,
    SLIDESHOW_DIR,
    TEMP_DIR,
    UPLOAD_DIR,
    USER_JOBS_DIR,
    BASE_DIR / "tts_cache",
)


def cleanup_expired_user_data() -> dict:
    """V1 사용자 생성 데이터 중 7일이 지난 파일과 폴더만 정리합니다."""
    cutoff = time.time() - RETENTION_SECONDS
    deleted_files = 0
    deleted_dirs = 0
    freed_bytes = 0

    for base_dir in GENERATED_DATA_DIRS:
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted(base_dir.rglob("*"), key=lambda item: len(item.parts), reverse=True):
                try:
                    if path.is_file() or path.is_symlink():
                        stat = path.stat()
                        if stat.st_mtime < cutoff:
                            freed_bytes += stat.st_size
                            path.unlink(missing_ok=True)
                            deleted_files += 1
                    elif path.is_dir():
                        # 오래된 파일 삭제 시 상위 폴더 mtime이 현재 시각으로 갱신되므로,
                        # 정리 대상 루트 아래의 빈 하위 폴더는 mtime과 관계없이 즉시 제거합니다.
                        if not any(path.iterdir()):
                            path.rmdir()
                            deleted_dirs += 1
                except FileNotFoundError:
                    continue
                except Exception as exc:
                    print(f"[cleanup] skip {path}: {exc}")
        except Exception as exc:
            print(f"[cleanup] scan failed {base_dir}: {exc}")

    return {
        "deleted_files": deleted_files,
        "deleted_dirs": deleted_dirs,
        "freed_bytes": freed_bytes,
    }


def cleanup_memory_jobs() -> dict:
    """완료·실패·취소된 오래된 작업만 메모리에서 제거합니다."""
    now = time.time()
    terminal_states = {"completed", "failed", "canceled", "cancelled"}
    removed = []

    for job_id, job in list(jobs.items()):
        status = str(job.get("status") or "").lower()
        if status not in terminal_states:
            continue
        created_ts = float(job.get("created_ts") or now)
        finished_ts = float(job.get("finished_ts") or created_ts)
        if now - finished_ts >= MEMORY_JOB_RETENTION_SECONDS:
            jobs.pop(job_id, None)
            slideshow_running_processes.pop(job_id, None)
            removed.append(job_id)

    if len(jobs) > 500:
        terminal = sorted(
            (
                (float(job.get("finished_ts") or job.get("created_ts") or 0), job_id)
                for job_id, job in jobs.items()
                if str(job.get("status") or "").lower() in terminal_states
            )
        )
        for _, job_id in terminal[: max(0, len(jobs) - 500)]:
            jobs.pop(job_id, None)
            slideshow_running_processes.pop(job_id, None)
            removed.append(job_id)

    return {"removed": removed, "remaining": len(jobs)}


async def periodic_cleanup_worker() -> None:
    while True:
        try:
            disk_result = cleanup_expired_user_data()
            memory_result = cleanup_memory_jobs()
            if disk_result["deleted_files"] or disk_result["deleted_dirs"] or memory_result["removed"]:
                print(f"[cleanup] disk={disk_result} memory={memory_result}")
        except Exception as exc:
            print(f"[cleanup] periodic error: {exc}")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


async def ensure_podcast_worker_started() -> None:
    global podcast_job_queue, podcast_worker_started
    if podcast_job_queue is None:
        podcast_job_queue = asyncio.Queue()
    if not podcast_worker_started:
        asyncio.create_task(podcast_queue_worker())
        podcast_worker_started = True


async def podcast_queue_worker() -> None:
    """Run podcast generation jobs one at a time."""
    assert podcast_job_queue is not None
    while True:
        item = await podcast_job_queue.get()
        job_id = None
        try:
            (
                job_id,
                project_key,
                script,
                male_voice,
                female_voice,
                speed,
                music_random,
                music_file,
                music_volume,
                voice_volume,
                tts_engine,
            ) = item

            if job_id not in jobs:
                continue

            jobs[job_id]["status"] = "running"
            jobs[job_id]["stage"] = "podcast_generator.pyw 실행 중"
            jobs[job_id]["log"].append("podcast job started")

            await asyncio.to_thread(
                run_podcast_subprocess,
                job_id,
                project_key,
                script,
                male_voice,
                female_voice,
                speed,
                music_random,
                music_file,
                music_volume,
                voice_volume,
                tts_engine,
            )
        except Exception as exc:
            if job_id and job_id in jobs:
                _set_job_terminal_status(job_id, "failed")
                jobs[job_id]["stage"] = f"queue error: {exc}"
                jobs[job_id]["log"].append(f"QUEUE_ERROR: {exc}")
        finally:
            podcast_job_queue.task_done()


def refresh_slideshow_queue_positions():
    with slideshow_queue_lock:
        waiting = list(slideshow_waiting_jobs)
    for pos, queued_job_id in enumerate(waiting, start=1):
        job = jobs.get(queued_job_id)
        if job and job.get("status") == "queued":
            job["queue_position"] = pos
            job["stage"] = f"대기 중... 앞에 {pos - 1}개 작업이 있습니다."

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# =============================================================================
# 유틸리티 함수
# =============================================================================
def normalize_filename(text: str, max_length: int = 100) -> str:
    """파일명 정규화: 금지문자 제거, 공백 언더바, 길이 제한"""
    # 금지문자: \ / : * ? " < > |
    text = re.sub(r'[\\/:*?"<>|]', '_', text)
    # 공백을 언더바로
    text = re.sub(r'\s+', '_', text)
    # 연속 언더바 제거
    text = re.sub(r'_+', '_', text)
    # 앞뒤 언더바 제거
    text = text.strip('_')
    # 길이 제한
    if len(text) > max_length:
        text = text[:max_length]
    return text

def generate_project_key(client: str, date: str, title: str) -> str:
    """프로젝트 키 생성: 업체명_날짜_제목"""
    safe_client = normalize_filename(client, 30)
    safe_title = normalize_filename(title, 50)
    # 날짜 검증 (YYYY-MM-DD)
    if not re.match(r'\d{4}-\d{2}-\d{2}', date):
        date = datetime.now().strftime("%Y-%m-%d")
    return f"{safe_client}_{date}_{safe_title}"

def get_latest_media_list(limit: int = 50) -> List[dict]:
    """최신 미디어 파일 목록 반환 (MP3 + MP4)

    - MP4: SLIDESHOW_DIR/*.mp4
    - MP3: PODCAST_DIR/*.mp3
    - MP3: OUTPUT_DIR/<project_key>/*.mp3 (프로젝트별 결과)
    """
    files: List[dict] = []

    # MP4 파일 (슬라이드쇼)
    try:
        for mp4 in SLIDESHOW_DIR.glob("*.mp4"):
            if not mp4.is_file():
                continue
            stat = mp4.stat()
            files.append({
                "name": mp4.name,
                "project_key": mp4.stem,
                "mtime": stat.st_mtime,
                "mtime_str": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "url": f"/media/slideshow/{mp4.name}",
                "type": "mp4",
            })
    except Exception as e:
        print(f"[get_latest_media_list] mp4 scan error: {e}")

    # MP3 파일 (팟캐스트 폴더)
    try:
        for mp3 in PODCAST_DIR.glob("*.mp3"):
            if not mp3.is_file():
                continue
            stat = mp3.stat()
            stem = mp3.stem
            srt = mp3.with_suffix(".srt")
            files.append({
                "name": mp3.name,
                "project_key": stem,
                "mtime": stat.st_mtime,
                "mtime_str": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "path": str(mp3),
                "srt_path": str(srt) if srt.exists() else "",
                "url": f"/media/podcast/{mp3.name}",
                "srt_url": f"/media/podcast/{srt.name}" if srt.exists() else "",
                "type": "mp3",
            })
    except Exception as e:
        print(f"[get_latest_media_list] podcast mp3 scan error: {e}")

    # MP3 파일 (OUTPUT/<project_key>/ 폴더)
    try:
        for mp3 in OUTPUT_DIR.glob("*/*.mp3"):
            if not mp3.is_file():
                continue
            stat = mp3.stat()
            project_key = mp3.parent.name  # ✅ NameError 방지: 여기서 정의
            srt = mp3.with_suffix(".srt")
            files.append({
                "name": mp3.name,
                "project_key": project_key,
                "mtime": stat.st_mtime,
                "mtime_str": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "path": str(mp3),
                "srt_path": str(srt) if srt.exists() else "",
                # 프로젝트 폴더 기반 라우트(있으면 이걸 쓰고, 없으면 파일명 기반으로도 열 수 있게 백업)
                "url": f"/media/podcast/{project_key}/mp3",
                "srt_url": f"/media/podcast/{project_key}/srt" if srt.exists() else "",
                "type": "mp3",
            })
    except Exception as e:
        print(f"[get_latest_media_list] output mp3 scan error: {e}")

    # 최신순 정렬
    files.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return files[:limit]



@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/tts/persona")
async def proxy_persona_tts(request: Request):
    """StoryMaker 백엔드용 Supertonic3 WAV 프록시."""
    try:
        payload = await request.body()
        upstream = urllib.request.Request(
            "http://127.0.0.1:7789/v1/audio/speech",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "audio/wav"},
            method="POST",
        )
        with urllib.request.urlopen(upstream, timeout=180) as response:
            audio_data = response.read()
        if len(audio_data) < 44 or not audio_data.startswith(b"RIFF"):
            raise HTTPException(status_code=502, detail="Supertonic3가 올바른 WAV를 반환하지 않았습니다.")
        return Response(content=audio_data, media_type="audio/wav")
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", "replace")
        raise HTTPException(status_code=502, detail=f"Supertonic3 응답 오류: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail="Supertonic3에 연결할 수 없습니다.") from exc


@app.get("/", response_class=HTMLResponse)
async def root():
    """메인 페이지 - static/index.html 서빙"""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>index.html 파일이 없습니다. static/index.html을 생성해주세요.</h1>")
    return FileResponse(str(index_path))

# =============================================================================
# 프로젝트 API
# =============================================================================
@app.post("/api/project/normalize")
async def normalize_project(
    client: str = Form(...),
    date: str = Form(...),
    title: str = Form(...)
):
    """프로젝트명 정규화"""
    project_key = generate_project_key(client, date, title)
    return {
        "project_key": project_key,
        "safe_name": project_key,
        "podcast_mp3": f"/media/podcast/{project_key}.mp3",
        "podcast_srt": f"/media/podcast/{project_key}.srt",
        "slideshow_mp4": f"/media/slideshow/{project_key}.mp4"
    }

# =============================================================================
# 팟캐스트 API
# =============================================================================
@app.post("/api/podcast/run")
async def run_podcast(
    background_tasks: BackgroundTasks,
    project_key: str = Form(...),
    script: str = Form(...),
    male_voice: str = Form("ko-KR-InJoonNeural"),
    female_voice: str = Form("ko-KR-SunHiNeural"),
    speed: float = Form(1.0),
    music_random: bool = Form(True),
    music_file: str = Form(""),
    music_volume: float = Form(0.3),
    voice_volume: float = Form(1.0),
    tts_engine: str = Form("supertonic")
):
    """팟캐스트 생성 실행 (subprocess)"""
    await ensure_podcast_worker_started()
    job_id = f"podcast_{uuid.uuid4().hex[:8]}"
    
    # 작업 상태 초기화
    jobs[job_id] = {
        "status": "pending",
        "percent": 0,
        "stage": "대기 중...",
        "eta": 0,
        "log": [],
        "result": None,
        "type": "podcast",
        "project_key": project_key,
        "created_ts": time.time()
    }
    
    # 호출자가 즉시 job_id를 받고 상태를 폴링할 수 있게 독립 실행
    queue_payload = (
        job_id,
        project_key,
        script,
        male_voice,
        female_voice,
        speed,
        music_random,
        music_file,
        music_volume,
        voice_volume,
        tts_engine,
    )
    assert podcast_job_queue is not None
    await podcast_job_queue.put(queue_payload)

    try:
        queue_size = podcast_job_queue.qsize()
    except Exception:
        queue_size = 0
    jobs[job_id]["queue_size"] = queue_size
    jobs[job_id]["stage"] = "대기열 등록 완료"
    jobs[job_id]["log"].append("podcast job queued")

    return {"job_id": job_id, "queue_size": queue_size}

def run_podcast_subprocess(job_id, project_key, script, male_voice, female_voice, speed, music_random, music_file, music_volume, voice_volume, tts_engine):
    """실제 podcast_generator.pyw 실행 (CLI 모드)"""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["stage"] = "임시 파일 준비 중..."
        jobs[job_id]["log"].append(f"프로젝트: {project_key}")
        
        # 임시 스크립트 파일 생성
        script_file = TEMP_DIR / f"{project_key}_script.txt"
        tts_script, display_restore_map = _voice_readable_text(script)
        script_file.write_text(tts_script, encoding="utf-8")
        jobs[job_id]["log"].append(f"스크립트 파일 생성: {script_file.name}")
        
        # 출력 파일 경로
        # 프로젝트 폴더 생성 (OUTPUT/<project_key>/)
        project_key, project_dir, images_dir = ensure_project_dirs(project_key)

        # 출력 파일 경로 (OUTPUT로 고정)
        mp3_path = project_dir / f"{project_key}.mp3"
        srt_path = project_dir / f"{project_key}.srt"

        jobs[job_id]["stage"] = "팟캐스트 생성기 실행 중..."
        jobs[job_id]["percent"] = 20
        jobs[job_id]["log"].append(f"음성 설정: 엔진={tts_engine}, 남성={male_voice}, 여성={female_voice}, 속도={speed}, 대사볼륨={voice_volume}")
        jobs[job_id]["log"].append(f"음악 설정: 랜덤={music_random}, 선택={music_file or '랜덤'}, 믹싱볼륨={music_volume}")
        
        # ===== podcast_generator.pyw 실행 명령어 구성 =====
        # --no-gui 옵션으로 GUI 팝업 없이 백그라운드 실행
        # UTF-8 환경 변수 설정
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        env['PODCAST_TTS_ENGINE'] = str(tts_engine or 'supertonic')
        jobs[job_id]["log"].append(f"CLI 환경변수 PODCAST_TTS_ENGINE={env['PODCAST_TTS_ENGINE']}")
        env['PODCAST_MUSIC_FILE'] = str(music_file or '')

        cmd = [
            sys.executable, "podcast_generator.pyw",  # python 대신 sys.executable 사용
            "--no-gui",
            "--script", str(script_file),
            "--output-mp3", str(mp3_path),
            "--output-srt", str(srt_path),
            "--male-voice", male_voice,
            "--female-voice", female_voice,
            "--speed", str(speed),
            "--music-folder", str(MUSIC_DIR),
            "--music-random", str(music_random).lower(),
            "--music-volume", str(music_volume),
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=1,
            env=env  # 환경 변수 추가
        )
        # 실시간 로그 수집
        # 실시간 로그 수집 및 진행률 업데이트
        line_count = 0
        for line in process.stdout:
            line = (line or "").strip()
            if not line:
                continue

            # 로그 저장
            jobs[job_id]["log"].append(line)
            print(f"[slideshow] {line}")

            # 진행률 파싱 (다양한 패턴)

            # 1. 이미지 전처리 진행률
            if "전처리" in line and "/" in line:
                match = re.search(r'(\d+)/(\d+)', line)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    progress = 30 + (current / total * 10)  # 30~40%
                    jobs[job_id]["percent"] = min(progress, 40)
                    jobs[job_id]["stage"] = f"전처리: {current}/{total}"

            # 2. 인코딩 진행률
            elif "인코딩 중" in line:
                match = re.search(r'(\d+\.?\d*)/(\d+\.?\d*)초', line)
                if match:
                    current = float(match.group(1))
                    total = float(match.group(2))
                    progress = 40 + (current / total * 55)  # 40~95%
                    jobs[job_id]["percent"] = min(progress, 95)
                    jobs[job_id]["stage"] = f"인코딩: {current:.1f}/{total:.1f}초"

            # 3. 이미지 처리 중
            elif "처리 중" in line and "/" in line:
                match = re.search(r'(\d+)/(\d+)', line)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    jobs[job_id]["stage"] = f"이미지 처리: {current}/{total}"

            # 4. 완료 메시지
            elif "완료" in line and ("MP4" in line or "파일 크기" in line):
                jobs[job_id]["percent"] = 98
                jobs[job_id]["stage"] = "마무리"

            # 5. 일반 로그는 stage에 표시 (너무 길면 자름)
            elif len(line) < 50 and ":" in line:
                jobs[job_id]["stage"] = line[:50]

            # 진행률 표시 (10% 단위로 로그에도 기록)
            if line_count % 10 == 0:
                jobs[job_id]["log"].append(f"진행률: {jobs[job_id]['percent']:.1f}% - {jobs[job_id]['stage']}")

            line_count += 1

        return_code = process.wait()
        
        if return_code == 0:
            # 성공
            jobs[job_id]["percent"] = 100
            jobs[job_id]["stage"] = "완료"
            _set_job_terminal_status(job_id, "completed")
            jobs[job_id]["log"].append(f"팟캐스트 생성 완료!")
            
            # 파일 크기 확인
            if mp3_path.exists():
                size_mb = mp3_path.stat().st_size / (1024 * 1024)
                jobs[job_id]["log"].append(f"MP3 파일 크기: {size_mb:.2f} MB")
                jobs[job_id]["log"].append(f"저장 위치: {mp3_path}")
            
            if srt_path.exists():
                try:
                    srt_text = srt_path.read_text(encoding="utf-8")
                    for spoken_text, original_text in display_restore_map.items():
                        srt_text = srt_text.replace(spoken_text, original_text)
                    srt_path.write_text(srt_text, encoding="utf-8")
                except Exception as restore_error:
                    jobs[job_id]["log"].append(f"SRT 원문 복원 실패: {restore_error}")
                jobs[job_id]["log"].append(f"SRT 파일 생성됨")
            
            jobs[job_id]["result"] = {
                "mp3_url": f"/media/podcast/{project_key}/mp3", 
                "srt_url": f"/media/podcast/{project_key}/srt", 
                "project_key": project_key
            }
        else:
            # 실패
            _set_job_terminal_status(job_id, "failed")
            jobs[job_id]["stage"] = f"오류 (코드: {return_code})"
            jobs[job_id]["log"].append(f"팟캐스트 생성 실패 (코드: {return_code})")
            jobs[job_id]["log"].append(f"podcast_generator.pyw 로그를 확인하세요")
        
    except FileNotFoundError:
        _set_job_terminal_status(job_id, "failed")
        jobs[job_id]["stage"] = "파일 없음"
        jobs[job_id]["log"].append(f"podcast_generator.pyw 파일을 찾을 수 없습니다")
        jobs[job_id]["log"].append(f"현재 디렉토리: {BASE_DIR}")
        
    except Exception as e:
        _set_job_terminal_status(job_id, "failed")
        jobs[job_id]["stage"] = f"오류: {str(e)}"
        jobs[job_id]["log"].append(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

# =============================================================================
# 슬라이드쇼 API
# =============================================================================
@app.post("/api/slideshow/run")
async def run_slideshow(
    background_tasks: BackgroundTasks,
    project_key: str = Form(...),
    mp3_path: str = Form(...),
    srt_path: str = Form(None),
    brand_name: str = Form("강경숯불바베큐"),
    phone_number: str = Form("0507-1393-5889"),
    brand_size: int = Form(60),
    phone_size: int = Form(43),
    margin_bottom: int = Form(91),
    box_enabled: bool = Form(True),
    stroke_enabled: bool = Form(True),
    shadow_enabled: bool = Form(True),
    image_sec: float = Form(2.0),
    transition_sec: float = Form(0.8),
    zoom_intensity: float = Form(0.004),
    zoom_center_only: bool = Form(False),
    subtitle_enabled: bool = Form(True),
    subtitle_font_size: int = Form(10),
    subtitle_margin: int = Form(30),
    # mac mini subtitle tuning
    mm_sub_boost: int = Form(20),
    mm_sub_lift: int = Form(95),
    mm_sub_width: int = Form(72),
    mm_sub_spacing: int = Form(8),
    mm_wm_lift: int = Form(0),
    mm_wm_gap: int = Form(18),
    narration_audio: Optional[UploadFile] = File(None),
    narration_srt: Optional[UploadFile] = File(None),
    images: List[UploadFile] = File(...),
    user_id: str = Form("default"),
    resolution: str = Form("1080x1920"),
    fps: int = Form(24),
    nvenc_preset: str = Form("p3"),
    render_target: str = Form("macmini")
):
    """슬라이드쇼 생성 실행 - 워터마크 설정 및 해상도/프레임/프리셋 추가"""
    # 24시간 지난 임시 폴더 정리 수행
    cleanup_old_slideshow_uploads()

    job_id = f"slideshow_{uuid.uuid4().hex[:8]}"
    input_logs = []
    
    # 외부 나레이션은 TTS + SRT 한 쌍으로만 적용합니다.
    has_external_audio = bool(narration_audio and narration_audio.filename)
    has_external_srt = bool(narration_srt and narration_srt.filename)
    if has_external_audio != has_external_srt:
        raise HTTPException(status_code=400, detail="외부 나레이션은 TTS 음성과 SRT를 함께 업로드해야 합니다.")

    external_mp3_path = None
    external_srt_path = None
    if has_external_audio and has_external_srt:
        audio_ext = Path(narration_audio.filename or "").suffix.lower()
        srt_ext = Path(narration_srt.filename or "").suffix.lower()
        if audio_ext not in {".mp3", ".wav", ".m4a"}:
            raise HTTPException(status_code=400, detail="TTS 음성은 MP3, WAV, M4A 파일만 사용할 수 있습니다.")
        if srt_ext != ".srt":
            raise HTTPException(status_code=400, detail="자막은 SRT 파일만 사용할 수 있습니다.")

        user_id_safe = safe_name(user_id) or "default"
        narration_dir = USER_JOBS_DIR / user_id_safe / job_id / "input_narration"
        narration_dir.mkdir(parents=True, exist_ok=True)
        audio_name = f"narration{audio_ext}"
        srt_name = "narration.srt"
        external_audio_file = narration_dir / audio_name
        external_srt_file = narration_dir / srt_name
        external_audio_file.write_bytes(await narration_audio.read())
        external_srt_file.write_bytes(await narration_srt.read())
        external_mp3_path = str(external_audio_file)
        external_srt_path = str(external_srt_file)
        input_logs.append(f"외부 TTS 업로드 사용: {narration_audio.filename}")
        input_logs.append(f"외부 SRT 업로드 사용: {narration_srt.filename}")

    # mp3_path 처리: 외부 업로드가 있으면 기존 StoryMaker 음성보다 우선합니다.
    if external_mp3_path:
        mp3_full_path = external_mp3_path
        input_logs.append(f"외부 나레이션 음성 선택: {mp3_full_path}")
    elif mp3_path and os.path.exists(mp3_path):
        mp3_full_path = mp3_path
        input_logs.append(f"MP3 선택값 사용: {mp3_full_path}")
    else:
        if mp3_path:
            input_logs.append(f"MP3 선택값을 찾을 수 없어 fallback 검사: {mp3_path}")
        else:
            input_logs.append("MP3 선택값이 비어 있어 fallback 검사")
        pk = safe_name(project_key)
        cand = OUTPUT_DIR / pk / f"{pk}.mp3"
        if cand.exists():
            mp3_full_path = str(cand)
            input_logs.append(f"MP3 fallback 사용: {mp3_full_path}")
        else:
            mp3_filename = Path(mp3_path).name if mp3_path else f"{pk}.mp3"
            mp3_full_path = str(PODCAST_DIR / mp3_filename)
            input_logs.append(f"MP3 fallback 후보 사용: {mp3_full_path}")

    # srt_path 처리: 외부 업로드가 있으면 기존 StoryMaker SRT보다 우선합니다.
    srt_full_path = None
    if external_srt_path:
        srt_full_path = external_srt_path
        input_logs.append(f"외부 나레이션 SRT 선택: {srt_full_path}")
    elif srt_path and os.path.exists(srt_path):
        srt_full_path = srt_path
        input_logs.append(f"SRT 선택값 사용: {srt_full_path}")
    else:
        if srt_path:
            input_logs.append(f"SRT 선택값을 찾을 수 없어 fallback 검사: {srt_path}")
        else:
            input_logs.append("SRT 선택값이 비어 있어 fallback 검사")
        pk = safe_name(project_key)
        cand = OUTPUT_DIR / pk / f"{pk}.srt"
        if cand.exists():
            srt_full_path = str(cand)
            input_logs.append(f"SRT fallback 사용: {srt_full_path}")
        else:
            srt_filename = Path(srt_path).name if srt_path else f"{pk}.srt"
            cand2 = PODCAST_DIR / srt_filename
            if cand2.exists():
                srt_full_path = str(cand2)
                input_logs.append(f"SRT fallback 사용: {srt_full_path}")
            else:
                input_logs.append("SRT fallback 파일 없음")

    # 작업 상태 초기화
    jobs[job_id] = {
        "status": "queued",
        "percent": 0,
        "stage": "대기열에 등록됨...",
        "eta": 0,
        "log": ["렌더링 대기열에 등록되었습니다."],
        "result": None,
        "type": "slideshow",
        "queue_position": 0,
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        "project_key": project_key,
        "created_ts": time.time()
    }
    jobs[job_id]["log"].extend(input_logs)

    with slideshow_queue_lock:
        slideshow_waiting_jobs.append(job_id)
    refresh_slideshow_queue_positions()
    
    # 백그라운드 큐 실행
    background_tasks.add_task(
        queued_slideshow_subprocess,
        job_id,
        project_key,
        mp3_full_path,
        srt_full_path,
        {
            "user_id": user_id,
            "brand_name": brand_name,
            "phone_number": phone_number,
            "brand_size": brand_size,
            "phone_size": phone_size,
            "margin_bottom": margin_bottom,
            "box_enabled": box_enabled,
            "stroke_enabled": stroke_enabled,
            "shadow_enabled": shadow_enabled,
            "image_sec": image_sec,
            "transition_sec": transition_sec,
            "zoom_intensity": zoom_intensity,
            "zoom_center_only": zoom_center_only,
            "subtitle_enabled": subtitle_enabled,
            "subtitle_font_size": subtitle_font_size,
            "subtitle_margin": subtitle_margin,
            "mm_sub_boost": mm_sub_boost,
            "mm_sub_lift": mm_sub_lift,
            "mm_wm_lift": mm_wm_lift,
            "mm_wm_gap": mm_wm_gap,
            "resolution": resolution,
            "fps": fps,
            "nvenc_preset": nvenc_preset,
            "render_target": render_target if render_target in ["macmini", "dell"] else "macmini",
        },
        images,
    )
    
    return {"job_id": job_id}

def queued_slideshow_subprocess(job_id, project_key, mp3_path, srt_path, slideshow_opts, images):
    with slideshow_render_lock:
        with slideshow_queue_lock:
            try:
                slideshow_waiting_jobs.remove(job_id)
            except ValueError:
                pass
        refresh_slideshow_queue_positions()
        if job_id in jobs:
            jobs[job_id]["status"] = "running"
            jobs[job_id]["queue_position"] = 0
            jobs[job_id]["stage"] = "rendering started"
            jobs[job_id]["log"].append("queue job started")
        return run_slideshow_subprocess(job_id, project_key, mp3_path, srt_path, slideshow_opts, images)

def run_slideshow_subprocess(job_id, project_key, mp3_path, srt_path, slideshow_opts, images):
    """슬라이드쇼 subprocess 실행 - SLID_Maker.py 연결 (Headless CLI)"""
    # 임시 이미지 폴더 경로를 나중에 finally/exception 블록에서도 참조할 수 있도록 미리 None으로 선언
    temp_image_dir = None
    try:

        opts = slideshow_opts or {}
        brand_name = opts.get("brand_name", "") or ""
        phone_number = opts.get("phone_number", "") or ""
        brand_size = int(opts.get("brand_size", 46) or 46)
        phone_size = int(opts.get("phone_size", 43) or 43)
        margin_bottom = int(opts.get("margin_bottom", 80) or 80)
        box_enabled = bool(opts.get("box_enabled", True))
        stroke_enabled = bool(opts.get("stroke_enabled", True))
        shadow_enabled = bool(opts.get("shadow_enabled", True))
        image_sec = float(opts.get("image_sec", 2.0) or 2.0)
        transition_sec = float(opts.get("transition_sec", 0.8) or 0.8)
        zoom_intensity = float(opts.get("zoom_intensity", 0.004) or 0.004)
        zoom_center_only = str(opts.get("zoom_center_only", False)).strip().lower() in {"1", "true", "yes", "on"}
        subtitle_enabled = bool(opts.get("subtitle_enabled", True))
        subtitle_font_size = int(opts.get("subtitle_font_size", 10) or 10)
        subtitle_margin = int(opts.get("subtitle_margin", 30) or 30)
        resolution = opts.get("resolution", "1080x1920") or "1080x1920"
        fps = int(opts.get("fps", 24) or 24)
        nvenc_preset = opts.get("nvenc_preset", "p3") or "p3"
        render_target = opts.get("render_target", "dell") or "dell"

        jobs[job_id]["status"] = "running"
        jobs[job_id]["stage"] = "프로젝트 폴더 준비 중..."
        jobs[job_id]["log"].append(f"프로젝트: {project_key}")
        jobs[job_id]["log"].append(f"워터마크: {brand_name} / {phone_number}")

        # 프로젝트 폴더 생성 (OUTPUT/<project_key>/images)
        project_key, project_dir, images_dir = ensure_project_dirs(project_key)

        # 사용자별 작업 폴더 생성: user_jobs/user_id/job_id/images|audio|srt|result.mp4
        user_id_safe = safe_name(opts.get("user_id", "default")) or "default"
        user_job_dir = USER_JOBS_DIR / user_id_safe / job_id
        temp_image_dir = user_job_dir / "images"
        user_audio_dir = user_job_dir / "audio"
        user_srt_dir = user_job_dir / "srt"
        for p in [user_job_dir, temp_image_dir, user_audio_dir, user_srt_dir]:
            p.mkdir(parents=True, exist_ok=True)
        jobs[job_id]["user_id"] = user_id_safe
        jobs[job_id]["job_dir"] = str(user_job_dir)

        # 입력 파일 검증: /api/slideshow/run에서 확정한 경로만 사용합니다.
        mp3_in = Path(mp3_path) if mp3_path else None
        if not (mp3_in and mp3_in.exists()):
            jobs[job_id]["log"].append(f"selected mp3 missing before render: {mp3_path}")
            raise FileNotFoundError(f"selected mp3 missing before render: {mp3_path}")

        srt_in = Path(srt_path) if srt_path else None
        if srt_path:
            if not (srt_in and srt_in.exists()):
                jobs[job_id]["log"].append(f"selected srt missing before render: {srt_path}")
                raise FileNotFoundError(f"selected srt missing before render: {srt_path}")

        # 이미지 저장: 계정별 임시 폴더에 저장
        jobs[job_id]["stage"] = "이미지 저장 중..."

        # 기존 임시 이미지 정리
        try:
            for p in temp_image_dir.glob("*"):
                if p.is_file():
                    p.unlink()
        except Exception:
            pass

        saved_count = 0
        for i, img in enumerate(images or []):
            ext = Path(img.filename).suffix.lower() if img.filename else ""
            if ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
                ext = ".jpg"
            file_path = temp_image_dir / f"image_{i:03d}{ext}"

            content = img.file.read()
            file_path.write_bytes(content)

            saved_count += 1
            jobs[job_id]["log"].append(f"이미지 저장: {file_path.name} ({len(content)/1024:.1f}KB)")

        if saved_count == 0:
            raise ValueError("업로드된 이미지가 없습니다.")

        jobs[job_id]["percent"] = 30
        jobs[job_id]["stage"] = f"슬라이드쇼 생성 준비... ({saved_count}장)"
        jobs[job_id]["log"].append(f"MP3: {mp3_in}")
        try:
            shutil.copy2(mp3_in, user_audio_dir / mp3_in.name)
            if srt_in:
                shutil.copy2(srt_in, user_srt_dir / srt_in.name)
        except Exception as copy_error:
            jobs[job_id]["log"].append(f"사용자 작업폴더 입력 파일 복사 실패: {copy_error}")

        if srt_in:
            jobs[job_id]["log"].append(f"SRT: {srt_in}")

        # 최종 출력은 job별 파일로 저장하고, 사용자 작업폴더에도 result.mp4 복사
        output_stem = f"{project_key}_{job_id}"
        output_mp4 = SLIDESHOW_DIR / f"{output_stem}.mp4"

        if render_target == "macmini":
            jobs[job_id]["stage"] = "Mac mini로 렌더링 오프로드 중..."
            jobs[job_id]["percent"] = 40
            
            # 1. render_job.json 생성
            job_info = {
                "job_id": job_id,
                "project_key": project_key,
                "image_dir": str(temp_image_dir),
                "mp3_path": str(mp3_in),
                "srt_path": str(srt_in) if srt_in else "",
                "output_mp4": str(output_mp4),
                "source_mp3_mtime": file_mtime(mp3_in),
                "source_srt_mtime": file_mtime(srt_in),
                "source_image_count": saved_count,
                "options": opts
            }
            
            json_job_path = user_job_dir / "render_job.json"
            with open(json_job_path, "w", encoding="utf-8") as f:
                json.dump(job_info, f, indent=2, ensure_ascii=False)
            
            jobs[job_id]["log"].append("Mac mini용 render_job.json이 생성되었습니다.")
            
            # 2. run_storymaker_external_slideshow.sh 실행
            external_script = str(BASE_DIR / "run_v1_slideshow.sh")
            jobs[job_id]["log"].append(f"오프로드 스크립트 실행: {external_script} {json_job_path}")
            
            process = subprocess.Popen(
                ["bash", external_script, str(json_job_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1
            )
            slideshow_running_processes[job_id] = process
            
            line_count = 0
            for line in process.stdout:
                line = (line or "").strip()
                if not line:
                    continue
                jobs[job_id]["log"].append(f"[Mac mini] {line}")
                print(f"[slideshow-macmini] {line}")
                
                line_count += 1
                if line_count % 3 == 0:
                    jobs[job_id]["percent"] = min(40 + line_count, 95)
            
            return_code = process.wait()
            slideshow_running_processes.pop(job_id, None)
            
            if jobs.get(job_id, {}).get("status") == "canceled":
                return

            if return_code == 0 and output_mp4.exists():
                jobs[job_id]["percent"] = 100
                jobs[job_id]["stage"] = "완료"
                _set_job_terminal_status(job_id, "completed")
                
                size_mb = output_mp4.stat().st_size / (1024 * 1024)
                jobs[job_id]["log"].append("Mac mini 렌더링 완료 및 파일 회수 성공!")
                jobs[job_id]["log"].append(f"MP4 파일 크기: {size_mb:.2f} MB")
                jobs[job_id]["log"].append(f"저장 위치: {output_mp4}")
                preview_mp4 = create_slideshow_preview_mp4(output_mp4, jobs[job_id]["log"])
                
                try:
                    shutil.copy2(output_mp4, user_job_dir / "result.mp4")
                    jobs[job_id]["result_mp4_path"] = str(user_job_dir / "result.mp4")
                    if preview_mp4:
                        shutil.copy2(preview_mp4, user_job_dir / "preview.mp4")
                        jobs[job_id]["preview_mp4_path"] = str(user_job_dir / "preview.mp4")
                except Exception as copy_error:
                    jobs[job_id]["log"].append(f"사용자 작업폴더 결과 파일 복사 실패: {copy_error}")

                jobs[job_id]["result"] = {
                    "mp4_url": f"/media/slideshow/{output_mp4.name}",
                    "preview_mp4_url": f"/media/slideshow/{output_mp4.name}?preview=true",
                    "project_key": project_key
                }
                
                # 사용자 작업폴더는 7일 자동삭제 정책에 따라 보관합니다.
                jobs[job_id]["log"].append("사용자 작업폴더에 이미지/오디오/자막/결과 파일을 보관했습니다.")
                return
            else:
                jobs[job_id]["status"] = "running"
                jobs[job_id]["stage"] = "Mac mini 실패, Dell 2차 폴백 준비 중..."
                jobs[job_id]["log"].append(f"Mac mini 숏폼 생성 실패 (코드: {return_code})")
                jobs[job_id]["log"].append("V1 Dell SLID_Maker.py로 2차 폴백합니다.")
                try:
                    if output_mp4.exists():
                        output_mp4.unlink()
                except Exception:
                    pass

        # ===== SLID_Maker.py 실행 명령어 구성 (Headless CLI) =====
        cmd = [
            sys.executable, str(BASE_DIR / "SLID_Maker.py"),
            "--image-folder", str(temp_image_dir),
            "--audio", str(mp3_in),
            "--project-dir", str(SLIDESHOW_DIR),
            "--project-key", str(output_stem),
        ]
        if srt_in:
            cmd.extend(["--srt", str(srt_in)])
        jobs[job_id]["log"].append(f"실행 명령어: {' '.join(cmd)}")
        
        # 환경 변수로 워터마크 설정 전달
        env = os.environ.copy()
        env['SLID_BRAND_NAME'] = brand_name
        env['SLID_PHONE_NUMBER'] = phone_number
        env['SLID_BRAND_SIZE'] = str(brand_size)
        env['SLID_PHONE_SIZE'] = str(phone_size)
        env['SLID_MARGIN_BOTTOM'] = str(margin_bottom)
        env['SLID_BOX_ENABLED'] = str(box_enabled).lower()
        env['SLID_STROKE_ENABLED'] = str(stroke_enabled).lower()
        env['SLID_SHADOW_ENABLED'] = str(shadow_enabled).lower()
        env['SLID_IMAGE_SEC'] = str(image_sec)
        env['SLID_TRANSITION_SEC'] = str(transition_sec)
        env['SLID_ZOOM_INTENSITY'] = str(zoom_intensity)
        env['SLID_ZOOM_CENTER_ONLY'] = str(zoom_center_only).lower()
        env['SLID_SUBTITLE_ENABLED'] = str(subtitle_enabled).lower()
        env['SLID_SUBTITLE_SIZE'] = str(subtitle_font_size)
        env['SLID_SUBTITLE_MARGIN'] = str(subtitle_margin)
        env['SLID_RESOLUTION'] = resolution
        env['SLID_FPS'] = str(fps)
        env['SLID_NVENC_PRESET'] = nvenc_preset
        env['PYTHONIOENCODING'] = 'utf-8'
        # =========================================================

        jobs[job_id]["stage"] = "SLID_Maker.py 실행 중..."
        jobs[job_id]["percent"] = 40

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            bufsize=1,
            cwd=str(BASE_DIR),
            env=env  # 환경변수 전달
        )
        slideshow_running_processes[job_id] = process

        line_count = 0
        for line in process.stdout:
            line = (line or "").strip()
            if not line:
                continue
            jobs[job_id]["log"].append(line)
            print(f"[slideshow] {line}")

            # 러프 진행률(로그 줄 수 기반)
            line_count += 1
            if line_count % 5 == 0:
                jobs[job_id]["percent"] = min(40 + line_count, 90)

        return_code = process.wait()
        slideshow_running_processes.pop(job_id, None)

        if jobs.get(job_id, {}).get("status") == "canceled":
            return

        if return_code == 0 and output_mp4.exists():
            jobs[job_id]["percent"] = 100
            jobs[job_id]["stage"] = "완료"
            _set_job_terminal_status(job_id, "completed")

            size_mb = output_mp4.stat().st_size / (1024 * 1024)
            jobs[job_id]["log"].append("슬라이드쇼 생성 완료!")
            jobs[job_id]["log"].append(f"MP4 파일 크기: {size_mb:.2f} MB")
            jobs[job_id]["log"].append(f"저장 위치: {output_mp4}")
            preview_mp4 = create_slideshow_preview_mp4(output_mp4, jobs[job_id]["log"])

            try:
                shutil.copy2(output_mp4, user_job_dir / "result.mp4")
                jobs[job_id]["result_mp4_path"] = str(user_job_dir / "result.mp4")
                if preview_mp4:
                    shutil.copy2(preview_mp4, user_job_dir / "preview.mp4")
                    jobs[job_id]["preview_mp4_path"] = str(user_job_dir / "preview.mp4")
            except Exception as copy_error:
                jobs[job_id]["log"].append(f"사용자 작업폴더 결과 파일 복사 실패: {copy_error}")

            jobs[job_id]["result"] = {
                "mp4_url": f"/media/slideshow/{output_mp4.name}", 
                "preview_mp4_url": f"/media/slideshow/{output_mp4.name}",
                "project_key": project_key
            }

            # 사용자 작업폴더는 7일 자동삭제 정책에 따라 보관합니다.
            jobs[job_id]["log"].append("사용자 작업폴더에 이미지/오디오/자막/결과 파일을 보관했습니다.")
        else:
            _set_job_terminal_status(job_id, "failed")
            jobs[job_id]["stage"] = f"오류 (코드: {return_code})"
            jobs[job_id]["log"].append(f"슬라이드쇼 생성 실패 (코드: {return_code})")

            try:
                if output_mp4.exists():
                    output_mp4.unlink()
            except Exception:
                pass

    except FileNotFoundError as e:
        _set_job_terminal_status(job_id, "failed")
        jobs[job_id]["stage"] = "파일 없음"
        jobs[job_id]["log"].append(f"{str(e)}")
        jobs[job_id]["log"].append(f"현재 디렉토리: {BASE_DIR}")
        jobs[job_id]["log"].append(f"예상 경로: {BASE_DIR / 'SLID_Maker.py'}")

    except Exception as e:
        _set_job_terminal_status(job_id, "failed")
        jobs[job_id]["stage"] = f"오류: {str(e)}"
        jobs[job_id]["log"].append(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

# =============================================================================
# 작업 상태 조회 API
# =============================================================================
@app.get("/api/queue")
async def queue_status():
    refresh_slideshow_queue_positions()
    items = [{"job_id": jid, "type": j.get("type", ""), "status": j.get("status", ""), "stage": j.get("stage", ""), "percent": j.get("percent", 0), "queue_position": j.get("queue_position", 0), "project_key": j.get("project_key", ""), "user_id": j.get("user_id", ""), "submitted_at": j.get("submitted_at", "")} for jid, j in jobs.items()]
    running = [x for x in items if x["type"] == "slideshow" and x["status"] == "running"]
    queued = sorted([x for x in items if x["type"] == "slideshow" and x["status"] == "queued"], key=lambda x: x.get("queue_position", 9999))
    completed = [x for x in items if x["type"] == "slideshow" and x["status"] == "completed"]
    completed_recent = list(reversed(completed[-10:]))
    return {"server_time": datetime.now().isoformat(timespec="seconds"), "running": running, "queued": queued, "queued_count": len(queued), "completed_count": len(completed), "completed_recent": completed_recent, "total_jobs": len(items)}

@app.post("/api/queue/{job_id}/cancel")
async def cancel_queue_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    status = job.get("status")
    if status == "queued":
        with slideshow_queue_lock:
            try:
                slideshow_waiting_jobs.remove(job_id)
            except ValueError:
                pass
        job["status"] = "canceled"
        job["stage"] = "관리자가 대기 작업을 취소했습니다."
        job["queue_position"] = 0
        job.setdefault("log", []).append("admin canceled queued job")
        refresh_slideshow_queue_positions()
        return {"ok": True, "job_id": job_id, "status": "canceled", "mode": "queued"}
    if status == "running":
        process = slideshow_running_processes.get(job_id)
        job["status"] = "canceled"
        job["stage"] = "관리자가 렌더링 작업을 취소했습니다."
        job.setdefault("log", []).append("admin requested running job cancel")
        if process and process.poll() is None:
            try:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
            except Exception as exc:
                job.setdefault("log", []).append(f"cancel process error: {exc}")
        slideshow_running_processes.pop(job_id, None)
        return {"ok": True, "job_id": job_id, "status": "canceled", "mode": "running"}
    return {"ok": False, "job_id": job_id, "status": status, "message": "이미 완료되었거나 취소할 수 없는 상태입니다."}

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """작업 상태 조회"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.post("/api/jobs/{job_id}/cleanup")
@app.post("/api/slideshow/jobs/{job_id}/cleanup")
async def cleanup_slideshow_job(job_id: str, request: Request):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    job = jobs[job_id]
    result = job.get("result") or {}
    candidates: list[tuple[str, Path]] = []

    def add_media_url(label: str, url: str | None):
        if not url:
            return
        filename = safe_name(url.rsplit("?", 1)[0].rstrip("/").split("/")[-1])
        if filename.lower().endswith(".mp4"):
            candidates.append((label, SLIDESHOW_DIR / filename))

    add_media_url("original", result.get("mp4_url"))
    add_media_url("preview", result.get("preview_mp4_url"))
    if result.get("mp4_url"):
        candidates.append(("preview", preview_mp4_path(SLIDESHOW_DIR / safe_name(result["mp4_url"].rsplit("?", 1)[0].rstrip("/").split("/")[-1]))))

    for label, key in (("original_copy", "result_mp4_path"), ("preview_copy", "preview_mp4_path")):
        path = job.get(key)
        if path:
            candidates.append((label, Path(path)))

    deleted: list[str] = []
    missing: list[str] = []
    seen: set[Path] = set()
    for label, path in candidates:
        try:
            path = path.resolve()
        except Exception:
            continue
        if path in seen:
            continue
        seen.add(path)
        if path.exists() and path.is_file():
            path.unlink()
            deleted.append(label)
        else:
            missing.append(label)

    job_dir = Path(job.get("job_dir") or "")
    if job_dir:
        try:
            resolved_job_dir = job_dir.resolve()
            resolved_user_jobs = USER_JOBS_DIR.resolve()
            if resolved_user_jobs in resolved_job_dir.parents and resolved_job_dir.exists():
                shutil.rmtree(resolved_job_dir)
                deleted.append("user_job_dir")
        except Exception as exc:
            missing.append(f"user_job_dir:{exc}")

    reason = payload.get("reason") or "manual"
    jobs.pop(job_id, None)
    slideshow_running_processes.pop(job_id, None)
    return {"ok": True, "deleted": deleted, "missing": missing, "reason": reason, "memory_job_removed": True}

# =============================================================================
# WebSocket 진행률 (실시간 로그)
# =============================================================================
@app.websocket("/ws/jobs/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(websocket)
    try:
        # 초기 상태 전송
        if job_id in jobs:
            await websocket.send_json(jobs[job_id])
        
        # TODO: 실제 진행률 업데이트 로직
        while True:
            await websocket.receive_text()  # 클라이언트 ping 대기
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# =============================================================================
# 히스토리 API
# =============================================================================
@app.get("/api/history/mp4")
async def get_mp4_history(limit: int = 50):
    """최신 미디어 파일 50개 목록 (MP3 + MP4)"""
    return get_latest_media_list(limit)

# =============================================================================
# 미디어 서빙 API
# =============================================================================

@app.get("/api/audio/list")
async def list_audio_files():
    """MP3 목록 반환 (슬라이드쇼 오디오 선택용)"""
    try:
        candidates = []
        # OUTPUT_DIR 우선, PODCAST_DIR 보조
        search_dirs = []
        if 'OUTPUT_DIR' in globals():
            search_dirs.append(OUTPUT_DIR)
        if 'PODCAST_DIR' in globals():
            search_dirs.append(PODCAST_DIR)

        seen = set()
        for base in search_dirs:
            try:
                base = Path(base)
                if not base.exists():
                    continue
                mp3_iter = base.rglob("*.mp3") if base == OUTPUT_DIR else base.glob("*.mp3")
                for p in mp3_iter:
                    if not p.is_file():
                        continue
                    rp = str(p.resolve())
                    if rp in seen:
                        continue
                    seen.add(rp)
                    st = p.stat()
                    project_key = p.parent.name if p.parent != base else p.stem
                    srt = p.with_suffix(".srt")
                    candidates.append({
                        "name": p.name,
                        "filename": p.name,
                        "project_key": project_key,
                        "path": rp,
                        "url": f"/media/podcast/{project_key}/mp3" if base == OUTPUT_DIR else f"/media/podcast/{p.name}",
                        "srt_url": f"/media/podcast/{project_key}/srt" if srt.exists() and base == OUTPUT_DIR else (f"/media/podcast/{srt.name}" if srt.exists() else ""),
                        "type": "mp3",
                        "size_mb": round(st.st_size / (1024 * 1024), 2),
                        "mtime": st.st_mtime,
                        "mtime_str": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    })
            except Exception:
                continue

        # 최신순 정렬
        candidates.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        return candidates[:200]
    except Exception as e:
        print(f"/api/audio/list 오류: {e}")
        return []

@app.get("/media/podcast/{filename}")
def media_podcast_file(filename: str):
    """
    호환용:
    - 기존: /podcast/<filename>
    - 신규: /OUTPUT/<project_key>/<project_key>.mp3 또는 .srt
    """
    filename = safe_name(filename)
    stem = Path(filename).stem

    cand1 = OUTPUT_DIR / stem / filename
    if cand1.exists():
        return FileResponse(str(cand1))

    p = PODCAST_DIR / filename
    if p.exists():
        return FileResponse(str(p))

    raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")


@app.api_route("/media/slideshow/{filename}", methods=["GET", "HEAD"])
async def get_slideshow_media(filename: str, request: Request, preview: bool = False):
    """슬라이드쇼 미디어 파일 서빙"""
    from urllib.parse import unquote
    import re
    
    decoded_filename = unquote(filename)
    
    # 1. 경로 이탈(traversal) 방지 보안 검증
    if "/" in decoded_filename or "\\" in decoded_filename or ".." in decoded_filename:
        raise HTTPException(status_code=400, detail="Invalid filename path")
        
    # 2. 확장자 검증
    if not decoded_filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only MP4 files are allowed")
        
    file_path = SLIDESHOW_DIR / decoded_filename
    if preview and file_path.suffix.lower() == ".mp4" and not file_path.stem.endswith(".preview"):
        preview_path = preview_mp4_path(file_path)
        if preview_path.exists():
            file_path = preview_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    # 3. ASCII 안전 파일명 생성
    safe_name_str = decoded_filename.replace("팟캐스트", "podcast").replace("슬라이드쇼", "slideshow")
    safe_name_str = re.sub(r'[^a-zA-Z0-9\-_.]', '_', safe_name_str)
    safe_name_str = re.sub(r'_{2,}', '_', safe_name_str).strip('_')
    if not safe_name_str.lower().endswith(".mp4"):
        safe_name_str += ".mp4"
        
    # 4. 안정화된 다운로드 응답 헤더 제공
    disposition = "inline" if preview else f'attachment; filename="{safe_name_str}"'
    headers = {
        "Content-Disposition": disposition,
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
    }
    return FileResponse(str(file_path), media_type="video/mp4", headers=headers)

@app.get("/media/podcast/{project_key}/mp3")
async def get_podcast_mp3(project_key: str):
    """프로젝트 키로 mp3 찾기 (OUTPUT/<project_key>/ 우선, 없으면 podcast/ 폴더)"""
    project_key = safe_name(project_key)
    filename = f"{project_key}.mp3"

    cand1 = OUTPUT_DIR / project_key / filename
    if cand1.exists():
        return FileResponse(str(cand1))

    cand2 = PODCAST_DIR / filename
    if cand2.exists():
        return FileResponse(str(cand2))

    raise HTTPException(status_code=404, detail="MP3 not found")


@app.get("/media/podcast/{project_key}/srt")
async def get_podcast_srt(project_key: str):
    """프로젝트 키로 srt 찾기 (OUTPUT/<project_key>/ 우선, 없으면 podcast/ 폴더)"""
    project_key = safe_name(project_key)
    filename = f"{project_key}.srt"

    cand1 = OUTPUT_DIR / project_key / filename
    if cand1.exists():
        return FileResponse(str(cand1))

    cand2 = PODCAST_DIR / filename
    if cand2.exists():
        return FileResponse(str(cand2))

    raise HTTPException(status_code=404, detail="SRT not found")


@app.api_route("/media/slideshow/{project_key}", methods=["GET", "HEAD"])
async def get_slideshow_mp4(project_key: str, request: Request, preview: bool = False):
    """프로젝트 키로 mp4 찾기"""
    from urllib.parse import unquote
    import re
    
    decoded_key = unquote(project_key)
    
    # 1. 경로 이탈(traversal) 방지 보안 검증
    if "/" in decoded_key or "\\" in decoded_key or ".." in decoded_key:
        raise HTTPException(status_code=400, detail="Invalid project key")
        
    filename = f"{decoded_key}.mp4"
    mp4_path = SLIDESHOW_DIR / filename
    if not mp4_path.exists():
        raise HTTPException(status_code=404, detail="MP4 not found")
        
    # 2. ASCII 안전 파일명 생성
    safe_name_str = filename.replace("팟캐스트", "podcast").replace("슬라이드쇼", "slideshow")
    safe_name_str = re.sub(r'[^a-zA-Z0-9\-_.]', '_', safe_name_str)
    safe_name_str = re.sub(r'_{2,}', '_', safe_name_str).strip('_')
    if not safe_name_str.lower().endswith(".mp4"):
        safe_name_str += ".mp4"
        
    # 3. 안정화된 다운로드 응답 헤더 제공
    disposition = "inline" if preview else f'attachment; filename="{safe_name_str}"'
    headers = {
        "Content-Disposition": disposition,
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
    }
    return FileResponse(str(mp4_path), media_type="video/mp4", headers=headers)

# =============================================================================
# 외부 사이트 관리 API (localStorage와 연동)
# =============================================================================
@app.get("/api/external-sites/default")
async def get_default_sites():
    """기본 외부 사이트 목록"""
    return [
        {"id": 1, "name": "ChatGPT", "url": "https://chatgpt.com", "enabled": True},
        {"id": 2, "name": "Claude", "url": "https://claude.ai", "enabled": False},
        {"id": 3, "name": "Perplexity", "url": "https://perplexity.ai", "enabled": False}
    ]

# =============================================================================
# 파일 관리 API (수정된 버전)
# =============================================================================
@app.post("/api/open-folder")
async def open_folder(request: Request):
    """폴더 열기 (Windows 탐색기) - OUTPUT 포함, 디버깅 강화"""
    try:
        data = await request.json()
        raw_path = data.get('path', '')
        print(f"[open_folder] 요청 받음: {raw_path}")

        if not raw_path:
            return {"status": "error", "message": "경로가 비어있습니다"}

        # 1) 입력 정리
        path = str(raw_path).strip().replace('\\\\', '\\').replace('\n', '').replace('\r', '').replace('"', '')
        print(f"[open_folder] 정리된 입력: {path}")

        # 2) 실제 경로가 전달된 경우 (절대/상대)
        if os.path.exists(path):
            print(f"[open_folder] 직접 경로 존재: True")
            target = Path(path)
            # 파일이면 부모 폴더 열기
            open_target = target.parent if target.is_file() else target
            print(f"[open_folder] 열 대상: {open_target}")
            if os.name == 'nt':
                os.startfile(str(open_target))
                return {"status": "ok", "message": "폴더 열기 성공"}
            return {"status": "error", "message": "Windows에서만 지원됩니다"}

        # 3) 파일명만 온 경우: 확장자 기반으로 후보 경로 탐색
        filename = os.path.basename(path)
        filename = filename.strip().replace('\n', '').replace('\r', '').replace('"', '')
        print(f"[open_folder] 파일명 추출: {filename}")

        if not filename:
            return {"status": "error", "message": "파일명이 비어있습니다"}

        # 경로 탐색 우선순위:
        # - mp3/srt: OUTPUT/**/filename -> PODCAST_DIR/filename
        # - mp4: SLIDESHOW_DIR/filename -> OUTPUT/**/filename(혹시)
        candidates = []

        ext = Path(filename).suffix.lower()
        if ext in (".mp3", ".srt"):
            candidates.append(OUTPUT_DIR / filename)  # 혹시 OUTPUT 루트에 바로 있는 경우
            candidates.append(PODCAST_DIR / filename)
            # OUTPUT 하위 폴더 전체 탐색
            for p in OUTPUT_DIR.glob(f"**/{filename}"):
                candidates.append(p)
        elif ext == ".mp4":
            candidates.append(SLIDESHOW_DIR / filename)
            for p in OUTPUT_DIR.glob(f"**/{filename}"):
                candidates.append(p)
        else:
            # 확장자 불명: OUTPUT에서라도 찾아본다
            for p in OUTPUT_DIR.glob(f"**/{filename}"):
                candidates.append(p)

        found = None
        for c in candidates:
            try:
                if c and Path(c).exists():
                    found = Path(c)
                    break
            except Exception:
                continue

        print(f"[open_folder] 후보 수: {len(candidates)} / 찾음: {found}")

        if not found:
            return {"status": "error", "message": f"파일을 찾을 수 없습니다: {filename}"}

        open_target = found.parent if found.is_file() else found
        print(f"[open_folder] 최종 열 대상: {open_target}")

        if os.name == 'nt':
            os.startfile(str(open_target))
            return {"status": "ok", "message": "폴더 열기 성공"}

        return {"status": "error", "message": "Windows에서만 지원됩니다"}

    except Exception as e:
        print(f"[open_folder] 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.post("/api/delete-file")
async def delete_file(request: Request):
    """파일 삭제 - OUTPUT 포함, 디버깅 강화"""
    try:
        data = await request.json()
        raw_filename = data.get('filename', '')
        filetype = data.get('type', '')

        print(f"[delete_file] 요청 받음: filename={raw_filename}, type={filetype}")

        if not raw_filename:
            return {"status": "error", "message": "파일명이 없습니다"}

        # 파일명 정리 (경로가 섞여 오면 basename만 취함)
        filename = str(raw_filename).strip().replace('\n', '').replace('\r', '').replace('"', '')
        filename = os.path.basename(filename)
        print(f"[delete_file] 정리된 파일명: {filename}")

        # 후보 경로 만들기
        candidates = []
        ext = Path(filename).suffix.lower()

        # 타입 우선 + 확장자 보조
        if filetype == 'mp3' or ext in (".mp3", ".srt"):
            candidates.append(PODCAST_DIR / filename)
            candidates.append(OUTPUT_DIR / filename)
            for p in OUTPUT_DIR.glob(f"**/{filename}"):
                candidates.append(p)
        else:
            # mp4 등
            candidates.append(SLIDESHOW_DIR / filename)
            candidates.append(OUTPUT_DIR / filename)
            for p in OUTPUT_DIR.glob(f"**/{filename}"):
                candidates.append(p)

        found = None
        for c in candidates:
            c = Path(c)
            if c.exists() and c.is_file():
                found = c
                break

        print(f"[delete_file] 후보 수: {len(candidates)} / 찾음: {found}")

        if not found:
            # 디렉토리 목록을 일부 출력 (너무 길어지면 상위 30개만)
            try:
                if filetype == 'mp3':
                    mp3s = list(PODCAST_DIR.glob("*.mp3"))[:30]
                    print("[delete_file] PODCAST_DIR 샘플 목록:")
                    for f in mp3s:
                        print("  -", f.name)
                mp4s = list(SLIDESHOW_DIR.glob("*.mp4"))[:30]
                print("[delete_file] SLIDESHOW_DIR 샘플 목록:")
                for f in mp4s:
                    print("  -", f.name)
            except Exception:
                pass
            return {"status": "error", "message": f"파일을 찾을 수 없습니다: {filename}"}

        # 삭제
        size = found.stat().st_size
        print(f"[delete_file] 삭제 대상: {found} ({size} bytes)")
        found.unlink()

        # 삭제 확인
        if not found.exists():
            return {"status": "ok", "message": "삭제 성공"}
        return {"status": "error", "message": "파일이 삭제되지 않았습니다"}

    except Exception as e:
        print(f"[delete_file] 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.post("/api/run-slid-maker")
async def run_slid_maker(request: Request):
    """SLID_Maker.py 실행 (별도 창)"""
    data = await request.json()
    exe_path = str((BASE_DIR / 'SLID_Maker.py').resolve())
    brand_name = data.get('brandName', '')
    phone_number = data.get('phoneNumber', '')
    
    try:
        # 실제 실행할 파일 경로
        if not os.path.exists(exe_path):
            # 대체 경로 시도
            alt_path = BASE_DIR / "SLID_Maker.py"
            if alt_path.exists():
                exe_path = str(alt_path)
            else:
                return {"success": False, "message": f"SLID_Maker.py를 찾을 수 없습니다: {exe_path}"}
        
        # Python 스크립트 실행
        cmd = [sys.executable, exe_path]
        
        # 환경 변수로 상호/전화번호 전달
        env = os.environ.copy()
        env['SLID_BRAND_NAME'] = brand_name
        env['SLID_PHONE_NUMBER'] = phone_number
        
        # 별도 창으로 실행 (CREATE_NEW_CONSOLE)
        if os.name == 'nt':
            # Windows에서 새 콘솔 창으로 실행
            subprocess.Popen(
                cmd,
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=str(BASE_DIR)
            )
        else:
            # Linux/Mac
            subprocess.Popen(
                cmd,
                env=env,
                cwd=str(BASE_DIR)
            )
        
        print(f"SLID_Maker.py 실행됨 (상호: {brand_name}, 전화: {phone_number})")
        return {"success": True, "message": "실행됨"}
        
    except Exception as e:
        print(f"SLID_Maker 실행 오류: {e}")
        return {"success": False, "message": str(e)}

# =============================================================================
# 예외 처리
# =============================================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation error: {exc.errors()}")
    print(f"Request body: {await request.form()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(await request.form())},
    )

# =============================================================================
# 서버 실행
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Shortform Studio Local Server")
    print("=" * 60)
    print(f"음악 폴더: {MUSIC_DIR}")
    print(f"팟캐스트 저장: {PODCAST_DIR}")
    print(f"슬라이드쇼 저장: {SLIDESHOW_DIR}")
    print(f"업로드 임시: {UPLOAD_DIR}")
    print(f"정적 파일: {STATIC_DIR}")
    print("=" * 60)
    print("Server: http://0.0.0.0:8003")
    print("Auto-reload: OFF (stable mode)")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8003, reload=False)
