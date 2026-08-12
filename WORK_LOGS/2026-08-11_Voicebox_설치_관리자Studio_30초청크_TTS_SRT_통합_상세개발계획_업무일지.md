# 2026-08-11 StoryMaker V1 Voicebox 설치·관리자 Studio·30초 청크 TTS·통합 오디오·SRT 상세 개발계획 업무일지

작성 시각: 2026-08-11 05:17 KST
작업 루트: `/home/bourne/StoryMaker_1`
Voicebox 설치 루트: `/home/bourne/StoryMaker_1/voicebox`
대상: StoryMaker V1 관리자 전용 VoiceBox Studio 신규 기능
상태: 개발계획 수립 + Voicebox 설치 진행 중

---

## 1. 이번 업무일지의 목적

StoryMaker V1에 새로운 로컬 AI 음성엔진 Voicebox를 도입하고, 관리자 로그인 후 사용할 수 있는 별도의 `VoiceBox Studio` 테스트 페이지를 만드는 전체 개발계획을 정리한다.

핵심 목표는 긴 원고를 한 번에 TTS로 생성하는 방식이 아니라 약 30초 분량의 청크 단위로 나누어 개별 생성·청취·재생성·버전선택을 할 수 있게 하는 것이다.

모든 청크가 확정되면 관리자가 최종 합치기를 실행하여 다음 결과물을 생성한다.

- 하나의 최종 WAV
- 하나의 최종 MP3
- 하나의 최종 SRT
- 필요 시 VTT
- 필요 시 청크별 WAV ZIP
- 프로젝트 메타데이터 JSON

이번 문서는 실제 구현 전에 설계 기준을 확정하는 문서이며, 아래 예시 코드는 향후 구현 시 기준으로 사용할 설계 예시다.

---

## 2. 현재 실제 상태

### 완료된 항목

- Dell 서버 연결 정상 확인
- `/home/bourne/StoryMaker_1/00_READ_FIRST.md` 확인
- StoryMaker V1/Beta 기존 안전규칙 확인
- Voicebox 공식 소스 확인
- Voicebox `v0.5.0` 소스 다운로드
- 설치 위치를 `/home/bourne/StoryMaker_1/voicebox`로 확정
- 기존 `/home/bourne/StoryMaker_1/supertonic`과 같은 루트 레벨의 음성엔진 구조로 배치
- GTX 1060 6GB 확인
- GPU Compute Capability `sm_61` 확인
- Voicebox 기본 포트 `17493` 미사용 확인
- Voicebox용 Git 로컬 exclude 처리
- Voicebox 런타임/모델/데이터 폴더 분리
- `uv 0.12.3` 설치
- Voicebox 전용 Python `3.11.15` 설치
- Voicebox 전용 venv 생성

Voicebox 전용 venv:

```text
/home/bourne/StoryMaker_1/voicebox/runtime/venv
```

### 아직 완료되지 않은 항목

- Voicebox Python 전체 의존성 설치 완료
- PyTorch CUDA 12.6 런타임 최종 설치 완료
- Voicebox Backend 실제 기동
- `127.0.0.1:17493/health` 정상 응답 확인
- 실제 GPU TTS 생성
- 실제 한국어 엔진 검증
- systemd 자동기동 등록
- 서버 재부팅 후 자동기동 실검증
- StoryMaker V1 관리자 UI 연결
- VoiceBox Studio 페이지 생성
- Voicebox Adapter API 개발
- 청크 데이터 저장 구조 개발
- 최종 오디오 병합 및 SRT 생성 기능 개발

따라서 현재 Voicebox 설치는 `진행 중`이며, 설치 완료로 기록하지 않는다.

---

## 3. 절대 보호 원칙

Voicebox 도입 때문에 현재 정상 운영 중인 다음 대상을 수정하거나 교체하지 않는다.

- 기존 Supertonic
- `/home/bourne/StoryMaker_1/supertonic`
- 기존 Supertonic 서비스
- 기존 StoryMaker TTS 흐름
- 기존 Worker
- 기존 Queue
- 기존 DB 스키마
- 기존 Podcast 기능
- 기존 MP4 생성 흐름
- 기존 Beta 데이터
- 시스템 Python
- 시스템 전역 CUDA
- 다른 Docker 서비스

Voicebox가 실패해도 기존 StoryMaker 제작 기능은 그대로 동작해야 한다.

Voicebox는 기존 TTS를 교체하는 엔진이 아니라 추가 선택형 엔진으로 도입한다.

---

## 4. 최종 목표 아키텍처

```text
StoryMaker V1 관리자
        ↓
VoiceBox Studio
        ↓
StoryMaker Voicebox Adapter API
        ↓
127.0.0.1:17493
        ↓
Voicebox Generation Queue
        ↓
선택한 TTS Engine
        ↓
Dell GTX 1060
        ↓
Chunk WAV
        ↓
관리자 청취 / 재생성 / 버전 선택
        ↓
Final Merge Engine
        ↓
Final WAV + MP3 + SRT + JSON
```

장기적으로는 다음 3단계 Voice Engine 구조를 목표로 한다.

```text
StoryMaker Voice Engine

1. Supertonic
   - 현재 안정 기본음성
   - 빠른 제작

2. Browser TTS
   - 사용자 PC WebGPU / WASM
   - 향후 한국어 지원 경량 모델 연구

3. Voicebox Server
   - Dell GPU
   - 고급 음성
   - 음성복제
   - 감정·표현
   - 장문 청크 제작
```

---

## 5. 왜 30초 청크 방식으로 개발하는가

긴 대본을 통째로 한 번에 TTS 생성하면 다음 문제가 발생할 수 있다.

- 후반부 호흡이 부자연스러워짐
- 특정 발음이 뭉개짐
- 중간 생성 실패 시 전체 재생성 필요
- 감정이나 속도 수정이 전체 원고에 영향을 줌
- 긴 음원의 오류 위치를 찾기 어려움
- 다시 생성할 때 GPU 시간을 불필요하게 많이 사용

따라서 StoryMaker에서는 원고를 약 30초 단위로 자동 분할한다.

단, 정확히 30.000초로 잘라서는 안 된다.

문장 경계를 우선한다.

권장 기준:

- 목표: 약 30초
- 허용 범위: 약 20~40초
- 한국어 평균 발화량을 기준으로 초기값 약 90~150자
- 마침표, 물음표, 느낌표 우선
- 줄바꿈 다음 우선
- 쉼표는 최후 보조 경계
- 문장이 너무 길면 강제 분할 가능

실제 음성 생성 후에는 글자 수가 아니라 생성된 WAV의 실제 duration을 기준으로 시간을 다시 확정한다.

---

## 6. 관리자 VoiceBox 아이콘 위치

StoryMaker V1 관리자 로그인 후 관리자 전용 메뉴에 `VoiceBox` 아이콘을 추가한다.

일반 사용자에게는 노출하지 않는다.

예상 메뉴:

```text
관리자 대시보드

AI 연구실
네모트론 연구실
VoiceBox
회원관리
사용량 관리
업종별 관리
...
```

아이콘 클릭 시 새 관리자 전용 페이지로 이동한다.

예상 URL:

```text
/v1/admin/voicebox
```

또는 현재 V1 라우팅 구조에 맞춰:

```text
/v1/?page=voiceboxStudio
```

실제 URL은 현재 관리자 라우팅 구조를 조사한 뒤 확정한다.

---

## 7. VoiceBox Studio UI 설계

### 전체 구조

PC 관리자 테스트 페이지는 2-Column Split 구조를 기본으로 한다.

```text
+--------------------------------------------------------------------------------+
| VoiceBox Studio | 프로젝트명 | 엔진 | Voice Profile | [전체듣기] [최종합치기] |
+---------------------------------------+----------------------------------------+
| 전체 대본                              | 청크 카드 목록                          |
|                                       |                                        |
| 긴 원고 입력                           | Chunk 01 00:00~00:28                   |
|                                       | 텍스트                                 |
| [자동 30초 분할]                       | 플레이어                               |
|                                       | V1 V2 V3                               |
| 분할 기준 20~40초                      | [생성] [재생성] [버전선택]             |
|                                       |                                        |
| 무음 간격 300ms                        | Chunk 02 00:28~00:57                   |
|                                       | ...                                    |
+---------------------------------------+----------------------------------------+
```

### 상단 Header

- 프로젝트명
- Voicebox 연결상태
- GPU 상태
- 선택 엔진
- Voice Profile
- 기본 Speed
- 기본 Pitch 또는 엔진별 지원 파라미터
- 청크 사이 Silence Padding
- 전체 재생
- 최종 합치기
- WAV 다운로드
- MP3 다운로드
- SRT 다운로드

### 왼쪽 패널

- 전체 원고 입력 textarea
- 총 글자 수
- 예상 청크 수
- 자동 분할 버튼
- 청크 재분할
- 분할 기준 설정
- 전체 원고 버전 저장

### 오른쪽 패널

각 청크가 독립 카드로 표시된다.

카드 정보:

- Chunk 번호
- 상태
- 텍스트
- 예상 시간
- 실제 생성 시간
- 플레이어
- 파형
- 생성 버튼
- 재생성 버튼
- 이전 버전 선택
- 현재 선택 버전
- 속도
- 감정/스타일
- silence_after_ms
- 오류 메시지

---

## 8. 가장 중요한 사용자 흐름

```text
1. 관리자 원고 입력
2. 자동 30초 분할
3. 청크 카드 생성
4. Chunk 01 음성 생성
5. 들어보기
6. 마음에 들면 승인
7. 마음에 안 들면 재생성
8. V1/V2/V3 비교
9. 최종 버전 선택
10. 다음 Chunk 진행
11. 모든 Chunk 승인
12. 전체 연속 재생
13. 최종 합치기
14. WAV 생성
15. MP3 생성
16. SRT 생성
17. 다운로드 또는 StoryMaker 제작으로 전달
```

핵심은 `전체 재생성`이 아니라 `문제가 있는 청크만 재생성`이다.

---

## 9. 초기 버전에서 Redis + Celery를 넣지 않는 이유

초기 제안에는 Redis + Celery 병렬 생성 구조가 있었으나 Dell GTX 1060 6GB에서는 초기 버전에 적용하지 않는다.

이유:

- GPU VRAM 6GB
- 여러 TTS 모델 동시 로드 위험
- Voicebox 자체 Generation Queue 존재
- 병렬 TTS가 반드시 더 빠르지 않음
- OOM 발생 시 전체 안정성 저하
- 관리자 테스트 기능에는 직렬 처리로 충분

초기 구조:

```text
Chunk 요청
  ↓
StoryMaker Adapter
  ↓
Voicebox Queue
  ↓
한 번에 1개 GPU Generation
```

향후 동시 사용자가 늘어나면 Queue Broker를 별도 도입한다.

---

## 10. 데이터 저장 구조 제안

V1 운영 DB를 바로 변경하지 않고 초기 테스트는 별도 Voicebox 프로젝트 저장 구조를 우선 검토한다.

예상 루트:

```text
/home/bourne/StoryMaker_1/voicebox/runtime/projects/
```

프로젝트 예:

```text
projects/
└── vb_20260811_001/
    ├── project.json
    ├── script.txt
    ├── chunks/
    │   ├── chunk_001/
    │   │   ├── chunk.json
    │   │   ├── v001.wav
    │   │   ├── v002.wav
    │   │   └── v003.wav
    │   └── chunk_002/
    └── export/
        ├── final.wav
        ├── final.mp3
        ├── final.srt
        └── final.json
```

초기 독립 테스트 성공 후 StoryMaker V1 DB 연동 여부를 결정한다.

---

## 11. 프로젝트 JSON 데이터 모델 예시

```json
{
  "project_id": "vb_20260811_001",
  "title": "테스트 나레이션",
  "engine": "qwen3_tts_0_6b",
  "voice_profile_id": "profile_001",
  "source_text": "전체 원고",
  "silence_padding_ms": 300,
  "status": "editing",
  "chunks": [
    {
      "chunk_id": "chunk_001",
      "index": 1,
      "text": "첫 번째 청크 원고입니다.",
      "status": "completed",
      "selected_version": 2,
      "duration_sec": 28.42,
      "silence_after_ms": 300,
      "versions": [
        {
          "version": 1,
          "audio_path": "chunks/chunk_001/v001.wav",
          "duration_sec": 28.31,
          "created_at": "2026-08-11T05:30:00+09:00"
        },
        {
          "version": 2,
          "audio_path": "chunks/chunk_001/v002.wav",
          "duration_sec": 28.42,
          "created_at": "2026-08-11T05:31:15+09:00"
        }
      ],
      "settings": {
        "speed": 1.0,
        "pitch": 0.0,
        "style": "warm"
      }
    }
  ]
}
```

---

## 12. Backend Pydantic 모델 예시

```python
from pydantic import BaseModel, Field
from typing import Literal


class ChunkSettings(BaseModel):
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=0.0, ge=-12.0, le=12.0)
    style: str | None = None


class VoiceChunk(BaseModel):
    chunk_id: str
    index: int
    text: str
    status: Literal["idle", "queued", "processing", "completed", "error"] = "idle"
    selected_version: int | None = None
    duration_sec: float = 0.0
    silence_after_ms: int = 300
    settings: ChunkSettings = ChunkSettings()


class VoiceProject(BaseModel):
    project_id: str
    title: str
    engine: str
    voice_profile_id: str | None = None
    source_text: str
    silence_padding_ms: int = 300
    chunks: list[VoiceChunk] = []
```

주의:

실제 개발 시 mutable default list는 `Field(default_factory=list)` 사용으로 보강한다.

---

## 13. 한국어 Smart Chunker 설계

### 기본 로직

1. 문장을 `.`, `?`, `!`, 줄바꿈 기준으로 우선 분리
2. 문장들을 순서대로 누적
3. 목표 글자 수 도달 시 청크 확정
4. 너무 짧으면 다음 문장과 결합
5. 너무 길면 쉼표 또는 공백 기준 보조 분리

### 예시 Python 코드

```python
import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    index: int
    text: str
    char_count: int


def split_korean_script(
    text: str,
    target_chars: int = 120,
    min_chars: int = 80,
    max_chars: int = 170,
) -> list[TextChunk]:
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", cleaned)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current and current_len + 1 + sentence_len > max_chars:
            chunks.append(" ".join(current).strip())
            current = []
            current_len = 0

        current.append(sentence)
        current_len += sentence_len + (1 if current_len else 0)

        if current_len >= target_chars:
            chunks.append(" ".join(current).strip())
            current = []
            current_len = 0

    if current:
        tail = " ".join(current).strip()

        if chunks and len(tail) < min_chars:
            chunks[-1] = f"{chunks[-1]} {tail}".strip()
        else:
            chunks.append(tail)

    return [
        TextChunk(index=i + 1, text=chunk, char_count=len(chunk))
        for i, chunk in enumerate(chunks)
    ]
```

이 코드는 예시이며 실제 30초 기준은 음성엔진별 한국어 발화속도 실측 후 보정한다.

---

## 14. 청크 생성 API 설계

StoryMaker가 Voicebox 내부 모듈을 직접 import하지 않는다.

반드시 localhost REST API로 연결한다.

예상 StoryMaker Adapter API:

```text
POST /v1-api/admin/voicebox/projects
POST /v1-api/admin/voicebox/projects/{project_id}/split
POST /v1-api/admin/voicebox/projects/{project_id}/chunks/{chunk_id}/generate
POST /v1-api/admin/voicebox/projects/{project_id}/chunks/{chunk_id}/regenerate
POST /v1-api/admin/voicebox/projects/{project_id}/chunks/{chunk_id}/select-version
POST /v1-api/admin/voicebox/projects/{project_id}/export
GET  /v1-api/admin/voicebox/projects/{project_id}
GET  /v1-api/admin/voicebox/health
```

모든 API는 관리자 인증을 필수로 한다.

---

## 15. Voicebox REST Adapter 예시 코드

```python
import httpx

VOICEBOX_BASE_URL = "http://127.0.0.1:17493"


class VoiceboxClient:
    def __init__(self, base_url: str = VOICEBOX_BASE_URL):
        self.base_url = base_url.rstrip("/")

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    async def generate(
        self,
        text: str,
        profile_id: str | None,
        engine: str,
        settings: dict,
    ) -> dict:
        payload = {
            "text": text,
            "profile_id": profile_id,
            "engine": engine,
            "settings": settings,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
```

주의:

Voicebox 실제 `/generate` 요청 스키마는 Backend 기동 후 `/openapi.json`을 조회하여 정확히 맞춘다.

추측으로 production payload를 고정하지 않는다.

---

## 16. Chunk 재생성 버전 관리 설계

재생성 시 기존 음원을 덮어쓰지 않는다.

예:

```text
chunk_001/
    v001.wav
    v002.wav
    v003.wav
```

관리자는 V1/V2/V3를 각각 들어보고 하나를 선택한다.

예시 선택 API:

```python
@router.post("/{project_id}/chunks/{chunk_id}/select-version")
async def select_chunk_version(
    project_id: str,
    chunk_id: str,
    version: int,
    admin=Depends(require_admin),
):
    project = load_project(project_id)
    chunk = find_chunk(project, chunk_id)

    available = {item["version"] for item in chunk["versions"]}
    if version not in available:
        raise HTTPException(status_code=404, detail="version_not_found")

    chunk["selected_version"] = version
    save_project(project)

    return {
        "ok": True,
        "chunk_id": chunk_id,
        "selected_version": version,
    }
```

---

## 17. Waveform UI

초기 버전은 HTML `<audio>`만으로도 충분히 기능 검증 가능하다.

2차에서 `wavesurfer.js`를 추가한다.

권장 순서:

1. 기본 audio player
2. 생성·재생성·버전선택 검증
3. 최종 병합 검증
4. 이후 waveform 추가

UI 시각효과보다 음성 생성 신뢰성을 먼저 검증한다.

---

## 18. Frontend Chunk Card 예시

```html
<article class="voicebox-chunk-card" data-chunk-id="chunk_001">
  <header>
    <strong>Chunk 01</strong>
    <span class="chunk-status">완료</span>
  </header>

  <textarea class="chunk-text">첫 번째 청크 원고입니다.</textarea>

  <audio controls preload="metadata" src="/v1-api/admin/voicebox/audio/chunk_001/v002.wav"></audio>

  <div class="chunk-version-row">
    <button type="button" data-version="1">V1</button>
    <button type="button" data-version="2" aria-pressed="true">V2 선택됨</button>
    <button type="button" data-version="3">V3</button>
  </div>

  <div class="chunk-actions">
    <button type="button" class="generate">생성</button>
    <button type="button" class="regenerate">개별 재생성</button>
  </div>
</article>
```

---

## 19. Frontend 재생성 예시 JavaScript

```javascript
async function regenerateChunk(projectId, chunkId) {
  const button = document.querySelector(
    `[data-chunk-id="${chunkId}"] .regenerate`
  );

  button.disabled = true;
  button.textContent = "재생성 중...";

  try {
    const response = await fetch(
      `/v1-api/admin/voicebox/projects/${projectId}/chunks/${chunkId}/regenerate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();
    refreshChunkCard(result.chunk);
  } finally {
    button.disabled = false;
    button.textContent = "개별 재생성";
  }
}
```

실제 CSRF 정책과 관리자 인증 방식은 현재 V1 인증 구조를 그대로 따른다.

---

## 20. 연속 미리듣기 설계

최종 합치기 전에 브라우저에서 선택된 청크를 순차 재생한다.

초기 버전에서는 브라우저에서 여러 오디오를 이어 재생한다.

```javascript
async function playSequence(audioUrls) {
  for (const url of audioUrls) {
    await new Promise((resolve, reject) => {
      const audio = new Audio(url);
      audio.addEventListener("ended", resolve, { once: true });
      audio.addEventListener("error", reject, { once: true });
      audio.play().catch(reject);
    });
  }
}
```

이 기능은 최종 병합 파일을 만들기 전에 전체 흐름을 빠르게 검수하기 위한 기능이다.

---

## 21. 최종 WAV 병합 설계

병합은 청크의 `selected_version`만 사용한다.

청크 사이에는 설정된 무음 구간을 삽입한다.

기본값:

```text
300ms
```

관리자 조절 범위 제안:

```text
100ms ~ 800ms
```

오디오 결합은 초기 구현에서 `ffmpeg` 사용을 우선한다.

이유:

- 서버에 이미 ffmpeg 사용 경험이 있음
- WAV/MP3 처리 안정적
- pydub보다 의존성 단순화 가능
- 샘플레이트 통일 가능

---

## 22. Python WAV 병합 예시

아래는 표준 `wave` 기반 단순 예시다.

```python
import wave
from pathlib import Path


def merge_wav_files(
    input_files: list[Path],
    output_file: Path,
    silence_ms: int = 300,
):
    if not input_files:
        raise ValueError("no_input_files")

    with wave.open(str(input_files[0]), "rb") as first:
        params = first.getparams()

    nchannels = params.nchannels
    sampwidth = params.sampwidth
    framerate = params.framerate

    silence_frames = int(framerate * silence_ms / 1000)
    silence = b"\x00" * silence_frames * nchannels * sampwidth

    with wave.open(str(output_file), "wb") as output:
        output.setnchannels(nchannels)
        output.setsampwidth(sampwidth)
        output.setframerate(framerate)

        for index, input_file in enumerate(input_files):
            with wave.open(str(input_file), "rb") as source:
                if (
                    source.getnchannels() != nchannels
                    or source.getsampwidth() != sampwidth
                    or source.getframerate() != framerate
                ):
                    raise ValueError(f"wav_format_mismatch:{input_file}")

                output.writeframes(source.readframes(source.getnframes()))

            if index < len(input_files) - 1:
                output.writeframes(silence)
```

실제 production에서는 Voicebox 엔진마다 샘플레이트가 다를 가능성이 있으므로 ffmpeg로 표준화 후 병합하는 방식이 더 안전하다.

---

## 23. FFmpeg 표준화 예시

모든 청크를 예를 들어 48kHz mono PCM으로 통일할 수 있다.

예시 개념:

```bash
ffmpeg -i chunk.wav -ar 48000 -ac 1 -c:a pcm_s16le normalized.wav
```

실제 구현에서는 shell 문자열 직접 조합보다 Python `subprocess.run([...])` 배열 인자로 안전하게 호출한다.

예:

```python
import subprocess


def normalize_wav(src: str, dst: str):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", src,
            "-ar", "48000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            dst,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
```

---

## 24. SRT 생성 원칙

SRT 타임코드는 절대 글자 수로 최종 확정하지 않는다.

반드시 선택된 실제 음원의 duration을 사용한다.

계산 방식:

```text
Chunk 1 시작 = 0
Chunk 1 종료 = 실제 duration
Padding 추가
Chunk 2 시작 = Chunk1 종료 + Padding
Chunk 2 종료 = Chunk2 시작 + 실제 duration
...
```

---

## 25. SRT 생성 예시 코드

```python
from datetime import timedelta


def srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def build_srt(chunks: list[dict], silence_ms: int = 300) -> str:
    cursor = 0.0
    blocks: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        duration = float(chunk["duration_sec"])
        start = cursor
        end = start + duration

        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{srt_timestamp(start)} --> {srt_timestamp(end)}",
                    chunk["text"].strip(),
                ]
            )
        )

        cursor = end + (silence_ms / 1000.0)

    return "\n\n".join(blocks) + "\n"
```

---

## 26. SRT 품질 고도화 방향

초기 SRT는 `청크 1개 = 자막 블록 1개`로 시작할 수 있다.

그러나 30초 분량 텍스트 전체를 한 자막 블록으로 넣으면 실제 영상 자막으로는 길다.

따라서 2차 개발에서는 청크 내부 문장별 타임코드를 생성한다.

방법 후보:

### 방법 A

청크 내부 문장의 글자 비율로 duration을 배분

장점:

- 단순
- 빠름

단점:

- 실제 발음속도와 차이

### 방법 B

Whisper로 최종 청크 음성을 다시 STT alignment

장점:

- 실제 음성 기준
- 자막 싱크 정확도 향상

단점:

- 추가 연산

StoryMaker 최종 영상용 SRT는 장기적으로 방법 B가 더 적합하다.

---

## 27. 최종 Export API 예시

```python
@router.post("/{project_id}/export")
async def export_voice_project(
    project_id: str,
    admin=Depends(require_admin),
):
    project = load_project(project_id)

    selected_chunks = []

    for chunk in project["chunks"]:
        selected_version = chunk.get("selected_version")
        if selected_version is None:
            raise HTTPException(
                status_code=409,
                detail=f"chunk_not_approved:{chunk['chunk_id']}",
            )

        version = find_version(chunk, selected_version)
        selected_chunks.append(
            {
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "audio_path": version["audio_path"],
                "duration_sec": version["duration_sec"],
            }
        )

    final_wav = build_final_wav(project_id, selected_chunks)
    final_mp3 = convert_to_mp3(final_wav)
    final_srt = create_final_srt(project_id, selected_chunks)

    return {
        "ok": True,
        "wav": final_wav,
        "mp3": final_mp3,
        "srt": final_srt,
    }
```

---

## 28. 키보드 단축키 계획

관리자 편집 속도를 높이기 위해 다음 단축키를 검토한다.

```text
Ctrl + Enter
현재 청크 재생성

Space
현재 선택 청크 재생 / 일시정지

Tab
다음 청크 이동

Shift + Tab
이전 청크 이동

Ctrl + S
현재 프로젝트 저장
```

브라우저 기본 단축키와 충돌하는지 확인 후 적용한다.

---

## 29. 청크별 파라미터

모든 Voicebox 엔진이 동일한 파라미터를 지원한다고 가정하지 않는다.

공통 UI는 추상화한다.

예:

```text
속도
톤
스타일
표현강도
```

내부에서는 엔진별 Adapter가 실제 파라미터로 변환한다.

예:

```python
class EngineSettingsAdapter:
    def for_qwen(self, settings: dict) -> dict:
        return {
            "speed": settings.get("speed", 1.0),
            "instruction": settings.get("style_instruction"),
        }

    def for_chatterbox(self, settings: dict) -> dict:
        return {
            "exaggeration": settings.get("expression", 0.5),
        }
```

실제 파라미터명은 Voicebox OpenAPI를 확인하여 확정한다.

---

## 30. Voice Director 확장

장기적으로 StoryMaker 원고와 TTS 사이에 `AI Voice Director`를 둘 수 있다.

예:

```text
원문
"배관을 열어보니 기름때가 상당히 심했습니다."

Voice Director
"발견 사실을 강조하고 약간 놀란 느낌으로 전달"

Engine Adapter
Qwen → 자연어 style instruction
Chatterbox → 지원 expression 태그 변환
```

이 기능은 1차 VoiceBox Studio 안정화 후 별도 개발한다.

---

## 31. Voicebox 엔진 선택 전략

GTX 1060 6GB에서는 모든 모델을 동시에 다루지 않는다.

검증 우선순위:

1. 실제 한국어가 가능한 경량 엔진 확인
2. Qwen3-TTS 0.6B 실측
3. Chatterbox Multilingual 실측
4. LuxTTS 실측
5. 다른 모델 확대

Kokoro는 경량성 때문에 Browser TTS 연구 후보로 가치가 있지만 한국어 지원 여부가 핵심이므로 StoryMaker 한국어 기본엔진으로 바로 가정하지 않는다.

---

## 32. Browser TTS 장기 연구

Voicebox 전체를 WebGPU/WASM으로 포팅하지 않는다.

대신 브라우저에서 실행 가능한 경량 TTS 엔진을 별도 연구한다.

장기 구조:

```text
사용자 브라우저
    ↓
navigator.gpu 확인
    ↓
WebGPU 가능 → Browser GPU TTS
    ↓ 실패
WASM CPU
    ↓ 성능 부족
Dell Voicebox
```

장점:

- 사용자 수가 늘수록 각 사용자 PC가 연산 담당
- Dell GPU 병목 감소
- StoryMaker 서버는 로그인/DB/원고/파일 관리 중심

하지만 한국어 모델 선정이 선행돼야 한다.

---

## 33. Voicebox 자동기동 최종 계획

Voicebox 단독 실행이 정상 검증된 후 systemd 서비스로 등록한다.

예상 서비스명:

```text
storymaker-v1-voicebox.service
```

예시 unit 파일:

```ini
[Unit]
Description=StoryMaker V1 Voicebox Local TTS Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=bourne
Group=bourne
WorkingDirectory=/home/bourne/StoryMaker_1/voicebox
Environment=VOICEBOX_DATA_DIR=/home/bourne/StoryMaker_1/voicebox/runtime/data
Environment=VOICEBOX_MODELS_DIR=/home/bourne/StoryMaker_1/voicebox/runtime/models
Environment=HF_HOME=/home/bourne/StoryMaker_1/voicebox/runtime/models/huggingface
Environment=NUMBA_CACHE_DIR=/home/bourne/StoryMaker_1/voicebox/runtime/cache/numba
ExecStart=/home/bourne/StoryMaker_1/voicebox/runtime/venv/bin/python -m backend.main --host 127.0.0.1 --port 17493
Restart=on-failure
RestartSec=5
TimeoutStartSec=180

[Install]
WantedBy=multi-user.target
```

주의:

실제 `backend.main` CLI 옵션은 v0.5.0 환경에서 직접 실행 검증한 후 unit에 반영한다.

---

## 34. 자동기동 완료 판정 기준

단순히 `systemctl enable`만 했다고 완료로 보지 않는다.

반드시 다음을 검증한다.

```text
systemctl is-enabled storymaker-v1-voicebox.service
→ enabled

systemctl is-active storymaker-v1-voicebox.service
→ active

curl http://127.0.0.1:17493/health
→ HTTP 200
```

그리고 실제 서버 재부팅 후 다시 확인한다.

```text
재부팅
↓
Docker / systemd 정상 기동
↓
Voicebox 자동기동
↓
17493 LISTEN
↓
/health 200
↓
GPU 인식
↓
기존 Supertonic 정상
↓
StoryMaker V1 정상
```

이 검증까지 끝나야 `재부팅 자동로딩 완료`로 기록한다.

---

## 35. Health Adapter UI

VoiceBox Studio 상단에 다음 상태를 표시한다.

```text
Voicebox: ONLINE
GPU: GTX 1060 6GB
Backend: 17493
Engine: Qwen3-TTS 0.6B
Queue: Idle
```

오프라인이면 생성 버튼을 비활성화한다.

예:

```javascript
async function refreshVoiceboxHealth() {
  const response = await fetch("/v1-api/admin/voicebox/health", {
    credentials: "same-origin",
  });

  const status = document.querySelector("#voicebox-health");

  if (!response.ok) {
    status.textContent = "Voicebox OFFLINE";
    document.body.dataset.voiceboxReady = "false";
    return;
  }

  const data = await response.json();
  status.textContent = `Voicebox ONLINE · ${data.gpu_name || "GPU 확인 중"}`;
  document.body.dataset.voiceboxReady = "true";
}
```

---

## 36. 관리자 권한 보호

VoiceBox Studio는 관리자 전용이다.

보호 원칙:

- 메뉴 자체를 일반 사용자에게 숨김
- URL 직접 접근도 서버에서 관리자 권한 검사
- API도 관리자 권한 검사
- 음성 프로젝트 파일 URL도 직접 공개하지 않음
- 다운로드는 인증된 API 경유

프런트에서 버튼만 숨기는 방식으로 보안을 처리하지 않는다.

---

## 37. 파일명 안전 규칙

사용자 입력 프로젝트명을 실제 파일 경로로 사용하지 않는다.

서버가 안전한 ID를 생성한다.

예:

```python
from datetime import datetime
from secrets import token_hex


def new_voice_project_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"vb_{stamp}_{token_hex(3)}"
```

실제 파일 구조는 project_id만 사용한다.

---

## 38. 원자적 project.json 저장

재생성 도중 서버가 중단되어 project.json이 깨지지 않도록 atomic write를 사용한다.

예시:

```python
import json
import os
from pathlib import Path


def save_json_atomic(path: Path, payload: dict):
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
        fp.flush()
        os.fsync(fp.fileno())

    os.replace(temp_path, path)
```

초기 테스트에서도 결과 파일 손상 방지를 우선한다.

---

## 39. 청크 상태 머신

청크 상태를 단순하게 유지한다.

```text
IDLE
  ↓
QUEUED
  ↓
PROCESSING
  ↓
COMPLETED

실패 시
ERROR
```

재생성은 기존 completed 파일을 보존하고 새로운 version을 추가한다.

---

## 40. 프로젝트 상태 머신

```text
DRAFT
  ↓
SPLIT
  ↓
GENERATING
  ↓
REVIEWING
  ↓
READY_TO_EXPORT
  ↓
EXPORTING
  ↓
COMPLETED

오류 시
ERROR
```

모든 청크에 selected_version이 있어야 `READY_TO_EXPORT`로 전환한다.

---

## 41. 최종 합치기 버튼 활성 조건

다음 조건이 모두 맞을 때만 활성화한다.

- 청크 1개 이상
- 모든 청크 status=completed
- 모든 청크 selected_version 존재
- 모든 selected audio 파일 존재
- duration_sec > 0
- Voicebox 생성 작업이 현재 processing 상태가 아님

Voicebox 서버 자체는 최종 병합 시 없어도 된다.

이미 생성된 WAV 파일만 있으면 병합과 SRT 생성은 가능해야 한다.

---

## 42. Export 결과 구조

```text
export/
├── final.wav
├── final.mp3
├── final.srt
├── final.vtt
├── final.json
└── chunks.zip
```

`final.json`에는 다음 정보를 포함한다.

- project_id
- export 시각
- engine
- voice profile
- 각 chunk 선택 버전
- duration
- silence padding
- 최종 총 길이
- 파일 SHA-256

---

## 43. 최종 JSON 예시

```json
{
  "project_id": "vb_20260811_001",
  "engine": "qwen3_tts_0_6b",
  "exported_at": "2026-08-11T06:10:00+09:00",
  "total_duration_sec": 181.44,
  "silence_padding_ms": 300,
  "files": {
    "wav": "final.wav",
    "mp3": "final.mp3",
    "srt": "final.srt"
  },
  "chunks": [
    {
      "chunk_id": "chunk_001",
      "selected_version": 2,
      "duration_sec": 28.42
    }
  ]
}
```

---

## 44. MP3 변환 예시

```python
import subprocess
from pathlib import Path


def wav_to_mp3(wav_path: Path, mp3_path: Path):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(wav_path),
            "-codec:a", "libmp3lame",
            "-b:a", "192k",
            str(mp3_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
```

MP3는 배포/다운로드 편의용이며 최종 제작 원본은 WAV를 기준으로 보관한다.

---

## 45. 오류 처리 정책

### Voicebox Offline

- 기존 프로젝트 열람 가능
- 기존 생성음성 재생 가능
- 최종 병합 가능
- 신규 생성/재생성만 차단

### GPU OOM

- 현재 청크 ERROR
- 기존 청크 보존
- 자동으로 모든 프로젝트 실패 처리 금지
- 관리자에게 VRAM 오류 표시
- 모델 unload/retry 옵션 검토

### Generation Timeout

- 해당 version 생성 실패 기록
- 이전 정상 version 유지

### FFmpeg 실패

- 원본 청크 WAV 보존
- export만 실패 처리

---

## 46. 기존 Supertonic과의 관계

VoiceBox Studio 개발이 완료돼도 Supertonic은 삭제하지 않는다.

초기에는 서로 완전히 별도 메뉴로 유지한다.

장기적으로 StoryMaker 제작화면에서 선택형 TTS UI로 합칠 수 있다.

예:

```text
음성 엔진

○ 빠른 기본 음성 - Supertonic
○ 고급 음성 - Voicebox
○ 브라우저 음성 - Browser TTS
```

이 통합은 VoiceBox Studio의 안정화 이후 별도 작업으로 진행한다.

---

## 47. StoryMaker 기존 제작 흐름 연결 시점

VoiceBox Studio 단독 검증이 끝나기 전에 기존 제작 화면에 연결하지 않는다.

연결 조건:

1. Voicebox Backend 안정 기동
2. 재부팅 자동기동 PASS
3. 한국어 30초 청크 생성 PASS
4. 개별 재생성 PASS
5. 버전 선택 PASS
6. 5분 이상 원고 전체 청크 제작 PASS
7. 최종 WAV 병합 PASS
8. SRT 생성 PASS
9. 관리자 페이지 새로고침 상태유지 PASS
10. 기존 Supertonic 회귀 PASS

---

## 48. 1차 개발 범위

1차에서는 기능 신뢰성만 본다.

포함:

- 관리자 VoiceBox 아이콘
- 관리자 전용 Studio 페이지
- Voicebox health
- 전체 원고 입력
- 자동 청크 분할
- 청크 수정
- 개별 생성
- 개별 재생성
- 버전 목록
- 버전 선택
- 청크 오디오 재생
- 전체 순차 재생
- 최종 WAV
- 최종 MP3
- 최종 SRT

제외:

- 화려한 Waveform 편집
- 드래그 분할선
- Redis/Celery
- 다중 GPU
- 일반 사용자 공개
- 요금제 연결
- Browser TTS
- Voice Director 자동 감정 연출

---

## 49. 2차 개발 범위

- WaveSurfer 파형
- 드래그 청크 경계
- VTT
- ZIP 다운로드
- 청크별 silence override
- 엔진별 고급 파라미터
- Voice profile 관리
- 음성복제 UI
- Whisper 기반 문장별 SRT alignment
- StoryMaker 제작화면 연동

---

## 50. 3차 개발 범위

- 일반 사용자 제공 검토
- 사용량/과금
- Browser TTS WebGPU/WASM
- 로컬 사용자 GPU 분산
- 자동 엔진 선택
- Voice Director
- 업종별 음성 preset
- 사용자별 Voice profile
- Queue 확장

---

## 51. 설치 완료 후 첫 TTS 실측 테스트

예상 테스트 문장:

```text
안녕하세요. 스토리메이커 보이스박스 테스트입니다.
이 음성은 델 서버의 로컬 GPU에서 생성되고 있습니다.
긴 원고는 약 삼십 초 단위로 나누어 만들고,
마음에 들지 않는 부분만 다시 생성할 수 있도록 개발할 예정입니다.
```

측정 항목:

- 모델 다운로드 시간
- 최초 로딩 시간
- VRAM 사용량
- TTS 생성 시간
- 실제 WAV 길이
- RTF
- 한국어 발음
- 숫자 읽기
- 영어 혼합 문장
- 주소/전화번호 발음
- 30초 청크 안정성

---

## 52. GTX 1060 성능 기록 항목

테스트마다 아래를 기록한다.

```text
engine
model
VRAM before
VRAM peak
VRAM after
generation seconds
audio duration
RTF
result
error
```

RTF 예:

```text
30초 음성을 15초에 생성
RTF = 0.5
```

StoryMaker 실제 운영 후보는 품질뿐 아니라 VRAM과 생성속도를 함께 판단한다.

---

## 53. 자동 모델 다운로드 정책

모든 Voicebox 모델을 한 번에 다운로드하지 않는다.

한 모델씩 검증한다.

초기 순서:

```text
1. Backend 기동
2. GPU 확인
3. 한국어 후보 한 모델
4. 짧은 TTS
5. 30초 TTS
6. 5개 청크 연속
7. 재생성
8. 모델 추가
```

대형 모델은 사용성 검증 후 추가한다.

---

## 54. 모델 저장 위치

모델은 가능한 한 Voicebox 내부로 고정한다.

```text
/home/bourne/StoryMaker_1/voicebox/runtime/models
```

HuggingFace:

```text
/home/bourne/StoryMaker_1/voicebox/runtime/models/huggingface
```

이를 통해 다른 AI 서비스의 모델 캐시와 혼동하지 않는다.

---

## 55. Voicebox 로그 위치

```text
/home/bourne/StoryMaker_1/voicebox/runtime/logs
```

systemd journal도 사용하되 Voicebox 프로젝트 자체 로그는 위 경로로 모으는 방안을 검토한다.

로그에 개인정보·원고 전체·음성 샘플 경로를 불필요하게 과다 출력하지 않는다.

---

## 56. 백업 정책

Voicebox 소스는 upstream Git 태그로 복구 가능하지만 다음 데이터는 별도 보호해야 한다.

- runtime/data
- runtime/projects
- voice profiles
- 사용자 음성 샘플
- 최종 exports
- 모델 목록/버전 정보
- StoryMaker Adapter 코드

대형 모델 파일은 전체 백업 정책에서 선택적으로 제외할 수 있으나 재다운로드 가능한 버전 정보를 반드시 기록한다.

---

## 57. Git 정책

`/home/bourne/StoryMaker_1/voicebox`는 upstream Voicebox 저장소다.

StoryMaker 상위 Git에서는 `/voicebox/`를 로컬 exclude 처리했다.

따라서 Voicebox 대용량 모델과 upstream 소스가 StoryMaker V1 Git에 미추적으로 쏟아지지 않게 유지한다.

StoryMaker V1 Adapter와 관리자 UI 코드는 상위 StoryMaker Git에서 관리한다.

향후 관리파일을 Voicebox 내부에 둘 경우 upstream Git 오염을 피하기 위해 현재처럼 `.git/info/exclude`를 사용하거나 StoryMaker 전용 별도 관리 경로를 검토한다.

---

## 58. 보안 원칙

Voicebox 포트 `17493`은 외부에 직접 공개하지 않는다.

바인딩:

```text
127.0.0.1:17493
```

외부 브라우저가 Voicebox에 직접 요청하지 않는다.

반드시 StoryMaker V1 관리자 API를 경유한다.

```text
Browser
  ↓ 인증
StoryMaker V1
  ↓ localhost
Voicebox
```

---

## 59. 관리자 API에서 허용할 기능만 노출

Voicebox가 많은 REST API를 제공하더라도 StoryMaker V1에서 전체 API를 프록시하지 않는다.

초기 허용:

- health
- profile 목록
- generation
- generation status
- 필요한 audio 결과

관리자 Studio에서 필요하지 않은 Voicebox 내부 관리 API는 노출하지 않는다.

---

## 60. 향후 StoryMaker MP4 연결

VoiceBox Studio에서 최종 WAV가 생성되면 기존 MP4 제작 흐름에 전달할 수 있다.

```text
VoiceBox Studio
  ↓
final.wav
final.srt
  ↓
StoryMaker MP4 input adapter
  ↓
기존 이미지/영상
  ↓
기존 렌더러
  ↓
MP4
```

기존 MP4 엔진을 Voicebox 때문에 수정하지 않고 별도 입력 연결로 개발한다.

---

## 61. 개발 파일 예상안

실제 V1 구조 조사 후 확정하지만 예상 파일은 다음과 같다.

```text
storymaker-web/backend/app/api/admin_voicebox.py
storymaker-web/backend/app/services/voicebox_client.py
storymaker-web/backend/app/services/voicebox_projects.py
storymaker-web/backend/app/services/voicebox_export.py
storymaker-web/backend/app/static/v1/admin-voicebox.html
storymaker-web/backend/app/static/v1/admin-voicebox.js
storymaker-web/backend/app/static/v1/admin-voicebox.css
```

기존 보호 번들은 직접 수정하지 않는다.

관리자 메뉴 연결도 가능한 한 기존 인라인 브리지 패턴을 따른다.

---

## 62. API 파일 책임 분리

### `admin_voicebox.py`

- 관리자 인증
- HTTP route
- request validation

### `voicebox_client.py`

- localhost 17493 통신
- health
- generate
- status

### `voicebox_projects.py`

- 프로젝트 생성
- chunk 저장
- version 관리
- selected version 관리

### `voicebox_export.py`

- WAV 표준화
- merge
- MP3
- SRT
- VTT
- export manifest

프런트 로직과 파일 처리 로직을 한 파일에 몰아넣지 않는다.

---

## 63. 테스트 계획

### 설치 테스트

- Python 3.11 venv
- torch import
- torch.cuda.is_available
- GPU 이름
- Backend import
- 17493 LISTEN
- health 200

### TTS 테스트

- 1문장
- 30초
- 5개 청크
- 10개 청크
- 같은 청크 3회 재생성

### Export 테스트

- WAV 병합
- MP3 변환
- SRT 타임코드
- 300ms padding
- 중간 chunk 교체 후 재export

### UI 테스트

- 관리자만 메뉴 노출
- 일반 사용자 직접 URL 403 또는 redirect
- 새로고침 후 프로젝트 복원
- 플레이어
- 재생성
- 버전 선택
- 전체 재생

### 회귀 테스트

- Supertonic 정상
- 기존 V1 제작 정상
- 기존 관리자 메뉴 정상
- 기존 DB 무변경
- 기존 Worker 정상

---

## 64. 롤백 원칙

VoiceBox Studio는 기존 기능에 종속되지 않도록 개발한다.

문제가 발생하면:

```text
1. StoryMaker Voicebox 메뉴 연결 비활성
2. Voicebox Adapter route 비활성
3. Voicebox systemd 서비스 중지
4. 기존 Supertonic 유지
5. 기존 StoryMaker 정상 여부 확인
```

Voicebox 실패 때문에 Supertonic을 복원해야 하는 구조 자체를 만들지 않는다.

---

## 65. 다음 실제 작업 순서

### Phase A. Voicebox 설치 완료

1. Voicebox venv 활성
2. PyTorch CUDA 12.6 설치 검증
3. Voicebox 의존성 설치
4. Backend import
5. 17493 기동
6. `/health` 확인
7. GPU 확인
8. 짧은 한국어 생성
9. 30초 생성

### Phase B. 자동기동

1. 서비스 unit 작성
2. Voicebox 전용 경로만 참조
3. daemon-reload
4. enable
5. start
6. health
7. 기존 서비스 회귀
8. 실제 재부팅
9. 자동기동 재검증

### Phase C. V1 관리자 UI 조사

1. 관리자 메뉴 실제 파일 확인
2. 관리자 권한 분기 확인
3. 기존 연구실 아이콘 연결 방식 확인
4. 별도 VoiceBox 메뉴 연결 설계
5. 수정 전 백업

### Phase D. VoiceBox Studio 기본판

1. 관리자 페이지
2. health 표시
3. 원고 입력
4. auto chunk
5. chunk card
6. generate
7. audio playback
8. regenerate
9. versions
10. select

### Phase E. Final Export

1. selected audio 검사
2. normalize
3. merge
4. padding
5. WAV
6. MP3
7. SRT
8. download

### Phase F. 장문 실전 테스트

1. 5분 원고
2. 10분 원고
3. 중간 2개 청크 재생성
4. 전체 재생
5. 최종 병합
6. SRT 싱크

---

## 66. 완료 기준

Voicebox 도입은 다음을 모두 만족해야 완료다.

```text
[ ] Voicebox Backend 17493 정상
[ ] GTX1060 CUDA 정상
[ ] 한국어 TTS 정상
[ ] 30초 청크 정상
[ ] 재부팅 자동기동 정상
[ ] 기존 Supertonic 정상
[ ] 관리자 VoiceBox 메뉴 정상
[ ] 일반 사용자 미노출
[ ] 청크 자동 분할 정상
[ ] 개별 생성 정상
[ ] 개별 재생성 정상
[ ] 버전 선택 정상
[ ] 전체 연속 재생 정상
[ ] Final WAV 정상
[ ] Final MP3 정상
[ ] Final SRT 정상
[ ] 새로고침 상태 유지
[ ] 기존 V1 회귀 없음
```

---

## 67. 이번 작업에서 실제 수정한 StoryMaker 기능

없음.

이번 단계에서는 개발계획 업무일지만 신규 생성한다.

V1 관리자 UI와 Voicebox Adapter는 아직 수정하지 않는다.

---

## 68. 이번 작업에서 실제 생성한 파일

```text
/home/bourne/StoryMaker_1/WORK_LOGS/2026-08-11_Voicebox_설치_관리자Studio_30초청크_TTS_SRT_통합_상세개발계획_업무일지.md
```

---

## 69. 이번 작업의 최종 판단

Voicebox는 StoryMaker에서 단순히 새로운 TTS 버튼 하나를 추가하는 방식으로 개발하면 안 된다.

가장 가치 있는 기능은 긴 원고를 관리 가능한 20~40초 청크로 나누고, 각 청크를 독립적으로 생성·검수·재생성·버전 선택할 수 있게 하는 것이다.

이 구조를 만들면 5분, 10분 이상의 긴 나레이션에서도 특정 한 문장의 발음 오류 때문에 전체 음성을 다시 만들 필요가 없다.

또한 최종 확정된 실제 WAV duration을 이용해 SRT를 생성하면 기존 단순 글자수 추정보다 훨씬 안정적인 영상 자막 파이프라인으로 발전시킬 수 있다.

StoryMaker는 장기적으로 다음 역할 분담을 목표로 한다.

```text
Supertonic
→ 빠른 기본 음성

Voicebox
→ 고급 음성 / 음성복제 / 표현형 장문 제작

Browser TTS
→ 사용자 PC 분산 연산
```

초기 VoiceBox Studio는 관리자 테스트 도구로 완성도를 확보한 뒤 기존 제작 흐름과 연결한다.

기존 Supertonic과 현재 정상 V1 제작 흐름은 끝까지 보호한다.

---

## 70. 다음 채팅 시작 지시문

다음 작업자는 먼저 아래 문서를 순서대로 읽는다.

```text
/home/bourne/StoryMaker_1/00_READ_FIRST.md
/home/bourne/StoryMaker_1/WORK_LOGS/2026-08-11_Voicebox_설치_관리자Studio_30초청크_TTS_SRT_통합_상세개발계획_업무일지.md
```

그 다음 반드시 현재 Git 상태와 Voicebox 실제 설치 상태를 확인한다.

Voicebox 설치 루트:

```text
/home/bourne/StoryMaker_1/voicebox
```

Voicebox venv:

```text
/home/bourne/StoryMaker_1/voicebox/runtime/venv
```

목표 포트:

```text
127.0.0.1:17493
```

다음 우선 작업은 Voicebox 전용 Python 3.11 환경에서 Backend 실제 기동과 한국어 TTS 생성까지 완료한 뒤 `storymaker-v1-voicebox.service` 자동기동을 구축하는 것이다.

그 검증이 끝난 이후에만 StoryMaker V1 관리자 VoiceBox 아이콘과 Studio 페이지 개발을 시작한다.
