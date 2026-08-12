# StoryMaker V1 VoiceBox 실제 기능 연결 · 한국어 Sohee GPU 생성 · systemd 자동기동 · 커밋/배포 최종 업무일지

작성일: 2026-08-12
작업 루트: `/home/bourne/StoryMaker_1`

## 1. 이번 작업 목표

관리자 로그인 후 접근하는 VoiceBox Studio 껍데기 화면을 실제 Voicebox Backend와 연결하고, Dell GTX 1060에서 한국어 TTS를 실제 생성하며, 재부팅 시 Voicebox가 자동 기동되도록 구성한다.

핵심 흐름:

`V1 관리자 → VoiceBox Studio → /v1-api/voicebox/* → V1 Backend Adapter → Dell host 17493 → Voicebox → GTX1060 → WAV`

## 2. 설치 경로

Voicebox는 Supertonic과 같은 레벨로 고정했다.

`/home/bourne/StoryMaker_1/voicebox`

기존 StoryMaker V1 Python, Supertonic, Worker, DB, CUDA 전역 환경은 수정하지 않았다.

Voicebox 전용 Python 3.11 환경:

`/home/bourne/StoryMaker_1/voicebox/runtime/venv`

Python 버전:

`3.11.15`

## 3. GPU / PyTorch 환경

Voicebox 전용 venv에 다음 버전을 설치했다.

- torch `2.7.1+cu126`
- torchaudio `2.7.1+cu126`
- torchvision `0.22.1+cu126`
- CUDA runtime 12.6 계열

실제 Python 확인 결과:

- `torch.cuda.is_available() == True`
- GPU: `NVIDIA GeForce GTX 1060 with Max-Q Design`
- CUDA capability: `(6, 1)`

Voicebox Backend `/health` 응답에서도:

- `gpu_available: true`
- `backend_type: pytorch`
- `backend_variant: cuda`

을 확인했다.

## 4. Voicebox 의존성

Voicebox Backend 의존성 설치 완료.

확인된 주요 패키지:

- FastAPI
- Uvicorn
- PyTorch
- torchaudio
- transformers
- qwen_tts
- soundfile
- SQLAlchemy
- Kokoro
- LuxTTS 관련 zipvoice

`flash-attn`은 설치하지 않았다. GTX1060 Pascal GPU에서는 기본 PyTorch 경로를 우선 사용한다.

SoX 미설치 경고는 있으나 이번 Qwen CustomVoice WAV 생성에는 영향을 주지 않았다.

## 5. 한국어 기본 음성

Voicebox Qwen CustomVoice preset 목록에서 한국어 음성을 확인했다.

- speaker id: `Sohee`
- language: `ko`
- gender: female
- 설명: Warm Korean female voice with rich emotion

StoryMaker 전용 기본 테스트 프로필을 생성했다.

프로필명:

`StoryMaker Sohee KO`

프로필 ID:

`3c4c2c4e-5f7c-49ff-8a56-28a88efbf255`

설정:

- voice_type: preset
- preset_engine: qwen_custom_voice
- preset_voice_id: Sohee
- default_engine: qwen_custom_voice
- language: ko

## 6. 모델 설치 상태

테스트 모델:

`Qwen CustomVoice 0.6B`

Voicebox model name:

`qwen-custom-voice-0.6B`

HuggingFace repo:

`Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`

최종 모델 상태:

- downloaded: true
- downloading: false
- loaded: true
- size_mb: 약 2382.64MB

중복 다운로드 요청 때문에 `/tasks/active`에 오래 남아 있던 stale download task는 Voicebox 정상 cancel API로 정리했다.

최종 task 상태:

```json
{"downloads":[],"generations":[]}
```

## 7. 실제 한국어 WAV 생성 검증

첫 번째 실제 생성 문장:

`안녕하세요. 스토리메이커 보이스박스 한국어 음성 생성 테스트입니다.`

결과:

- HTTP 200
- Content-Type: audio/wav
- 24,000Hz
- 16bit PCM
- mono
- duration: 7.28초
- bytes: 349,484

생성 파일:

`/home/bourne/StoryMaker_1/voicebox/runtime/output/sohee_smoke.wav`

두 번째 검증은 Voicebox systemd 서비스를 재시작한 직후 콜드 스타트 상태에서 실행했다.

문장:

`재부팅 자동 실행 환경에서 보이스박스 한국어 음성을 다시 확인합니다.`

결과:

- HTTP 200
- 첫 모델 재로딩 포함 elapsed 약 65.52초
- duration: 8.0초
- bytes: 384,044

파일:

`/home/bourne/StoryMaker_1/voicebox/runtime/output/sohee_restart_smoke.wav`

SHA-256:

`ba32b24f7b2b984d856c6f7962754f81fd632937c2d667ffa5ae486b2ba808df`

이 검증으로 서비스 재시작 후 모델 캐시 재사용 + GPU 재로딩 + 한국어 TTS 생성까지 통과했다.

## 8. systemd 자동기동

서비스명:

`storymaker-v1-voicebox.service`

원본 파일:

`/home/bourne/StoryMaker_1/voicebox/storymaker-v1-voicebox.service`

systemd link:

`/etc/systemd/system/storymaker-v1-voicebox.service`

부팅 대상:

`multi-user.target`

현재 상태:

- `systemctl is-enabled storymaker-v1-voicebox.service` → enabled
- `systemctl is-active storymaker-v1-voicebox.service` → active

중요 실행 명령:

```ini
ExecStart=/home/bourne/StoryMaker_1/voicebox/runtime/venv/bin/python -m backend.main --host 0.0.0.0 --port 17493 --data-dir /home/bourne/StoryMaker_1/voicebox/runtime/data
```

초기에는 `uvicorn backend.main:app`을 직접 실행했지만 이 방식은 Voicebox의 `--data-dir` 인자가 적용되지 않아 기본 `voicebox/data`를 사용했고 readonly DB 경고가 발생했다.

공식 entry point인 `python -m backend.main ... --data-dir ...` 방식으로 수정한 후 DB 경로가 아래로 정상 고정됐다.

`/home/bourne/StoryMaker_1/voicebox/runtime/data/voicebox.db`

현재 로그:

- Profiles: 정상
- Generations: 정상
- Backend: PYTORCH
- GPU: CUDA GTX1060
- Ready

## 9. Voicebox runtime 소유권

Voicebox systemd 서비스는 `bourne` 사용자로 실행한다.

따라서 쓰기가 필요한 다음 경로의 소유권을 `bourne:bourne`으로 정리했다.

- `runtime/data`
- `runtime/models`
- `runtime/cache`
- `runtime/logs`

Python runtime 자체와 venv는 기존 상태를 유지했다.

## 10. Docker 네트워크 / UFW

V1 Backend는 Docker 컨테이너 안에서 동작한다.

컨테이너 내부의 `127.0.0.1:17493`은 Dell host가 아니라 컨테이너 자체이므로 사용할 수 없다.

V1 Docker network gateway:

`172.27.0.1`

Voicebox Adapter 기본 upstream:

`http://172.27.0.1:17493`

Dell UFW는 기본 INPUT DROP이므로 V1 Docker network에만 최소 허용 규칙을 추가했다.

```text
17493/tcp ALLOW IN 172.27.0.0/16 # StoryMaker V1 VoiceBox from V1 docker network
```

외부 전체 공개는 하지 않았다.

V1 컨테이너 내부에서 실제 테스트:

`http://172.27.0.1:17493/health` → HTTP 200

## 11. V1 Backend Adapter

신규 파일:

`storymaker-web/backend/app/api/voicebox.py`

V1 main.py에 router 연결.

등록 API:

- `/api/voicebox/health`
- `/api/voicebox/profiles`
- `/api/voicebox/generate/chunk`

외부 V1 prefix 기준:

- `/v1-api/voicebox/health`
- `/v1-api/voicebox/profiles`
- `/v1-api/voicebox/generate/chunk`

세 API 모두 `get_admin_user`를 사용해 관리자 전용으로 보호한다.

비로그인 검증:

- health → 401
- profiles → 401
- generate → 401

OpenAPI에 세 route가 등록된 것을 확인했다.

Adapter는 브라우저가 17493을 직접 호출하지 않도록 설계했다.

올바른 구조:

`browser → app.mystorymaker.net/v1-api/voicebox/* → V1 Backend → 172.27.0.1:17493`

## 12. VoiceBox Studio UI

신규 정적 파일:

- `storymaker-web/backend/app/static/v1/voicebox-studio.html`
- `storymaker-web/backend/app/static/v1/voicebox-studio.css`
- `storymaker-web/backend/app/static/v1/voicebox-studio.js`
- `storymaker-web/backend/app/static/v1/v1-admin-voicebox-entry.js`

기존 V1 `index.html`에는 관리자 VoiceBox 진입 브리지 JS만 최소 추가했다.

Studio 주소:

`https://app.mystorymaker.net/static/v1/voicebox-studio.html`

현재 외부 HTTP 200 확인.

## 13. 인증 게이트 문제와 수정

초기 증상:

`관리자 권한을 확인하고 있습니다` 화면에서 계속 멈춤.

원인:

HTML의 `hidden` attribute보다 CSS `.auth-gate { display:grid }`가 우선 표시되어 브라우저에서 인증 카드가 계속 나타났다.

수정:

```css
.auth-gate[hidden]{display:none!important}
```

JS 초기화에서도:

```javascript
if (gate) {
  gate.hidden = true;
  gate.style.display = 'none';
}
if (app) app.hidden = false;
```

을 적용했다.

실제 생성 API는 서버에서 관리자 권한을 다시 검증하므로 Studio UI 자체는 즉시 보여도 보안 경계가 유지된다.

## 14. 현재 Studio 기능

현재 구현된 UI 기능:

- 전체 대본 입력
- 글자 수 표시
- 예시 대본
- 20/30/40초 기준 Smart Chunk
- 한국어 문장 경계 우선 분할
- 청크별 텍스트 수정
- 청크 삭제
- 실제 Voice 프로필 목록 조회
- Qwen CustomVoice 한국어 Sohee 선택
- Qwen CustomVoice 0.6B 선택
- 청크 실제 WAV 생성 Adapter 연결
- 생성 중 상태 표시
- 생성된 WAV를 Object URL로 보관
- 실제 audio duration 읽기
- 청크별 V1/V2/V3 버전 누적
- 버전 선택
- 청크 재생
- 개별 재생성
- 선택된 청크 전체 순차 재생

향후 미구현:

- 서버 영구 프로젝트 저장
- Final WAV/MP3 병합
- 실제 오디오 duration 기반 SRT 생성
- Export ZIP
- VTT / JSON Export
- 청크별 speed/pitch/emotion override
- 프로젝트 히스토리 영구 저장

## 15. 청크 생성 요청 예시

V1 Studio가 호출하는 Adapter 요청 예시:

```json
{
  "profile_id": "3c4c2c4e-5f7c-49ff-8a56-28a88efbf255",
  "text": "안녕하세요. 테스트 음성입니다.",
  "language": "ko",
  "engine": "qwen_custom_voice",
  "model_size": "0.6B",
  "normalize": true,
  "max_chunk_chars": 800,
  "crossfade_ms": 50
}
```

Adapter는 Voicebox `/generate/stream`에 요청하고 `audio/wav`를 그대로 관리자 브라우저에 streaming response로 전달한다.

## 16. 최종 검증

커밋 직전 검증:

- Python `py_compile` PASS
- `node --check v1-admin-voicebox-entry.js` PASS
- `node --check voicebox-studio.js` PASS
- `git diff --check` PASS
- OpenAPI Voicebox 3 route 확인
- Studio HTML 외부 HTTP 200
- Studio JS 외부 HTTP 200
- Studio CSS 외부 HTTP 200
- Voicebox systemd enabled
- Voicebox systemd active
- Voicebox `/health` HTTP 200
- GTX1060 CUDA 인식
- 실제 한국어 WAV 생성 성공
- V1 컨테이너 → Dell Voicebox HTTP 200
- 기존 V1 root HTTP 200

## 17. Git 원칙

이번 커밋은 VoiceBox 관련 파일만 정확히 지정해서 stage 한다.

금지:

- `git add .`
- `git add -A`
- `git clean`
- 기존 미추적 파일 일괄 처리

StoryMaker 상위 Git에서 `/voicebox` 외부 소스/모델/runtime은 의도적으로 추적하지 않는다.

따라서 모델 2.38GB, 생성 WAV, runtime venv, DB 등은 Git에 포함하지 않는다.

## 18. 다음 개발 우선순위

1. 관리자 브라우저에서 실제 청크 생성 버튼 실사용 확인
2. 청크 재생성 V1/V2/V3 UX 보완
3. 전체 연속 재생 간 0.1~0.8초 padding 적용
4. 최종 선택 버전 기반 서버 Export API
5. WAV 병합
6. MP3 변환
7. 실제 WAV duration 기반 SRT 생성
8. WAV + MP3 + SRT 동시 다운로드
9. 프로젝트 JSON 영구 저장
10. 2분 → 5분 → 10분 장문 실전 테스트

## 19. 복구 핵심

Voicebox 서비스 확인:

```bash
systemctl status storymaker-v1-voicebox.service --no-pager
curl http://127.0.0.1:17493/health
```

V1 컨테이너에서 연결 확인:

```bash
docker exec storymaker-v1-backend python -c "import httpx; print(httpx.get('http://172.27.0.1:17493/health',timeout=5).json())"
```

모델 확인:

```bash
curl http://127.0.0.1:17493/models/status
```

현재 운영 기본 모델:

`qwen-custom-voice-0.6B`

현재 운영 기본 한국어 Voice profile:

`StoryMaker Sohee KO`
