# StoryMaker V1 사무실 서버 복제 목록·용량·이전 지도

작성일: 2026-08-15
대상 원본: `/home/bourne/StoryMaker_1`
목적: 사무실 Windows 11 새 메인 서버로 StoryMaker V1을 안전하게 이전하기 위한 복제 대상, GitHub 수신 대상, Dell 직접 전송 대상, 예상 용량을 분리한다.

## 1. 결론

StoryMaker V1은 GitHub clone만으로 현재 Dell 운영 상태 전체가 재현되지 않는다.

현재 Git 추적 워크트리의 실제 파일 합계는 약 45.8 MB이며, 코드·문서·Docker Compose·운영 설정의 기준본은 GitHub `kim6410/dell_V1_StoryMaker` main에서 받는다.

반면 현재 운영에 필요한 DB, 결과물, Beta 런타임 데이터, Browser TTS ONNX, Supertonic 모델 캐시, VoiceBox 모델·프로필 데이터 등은 Git 제외 대상이므로 Dell에서 별도로 복제해야 한다.

Dell에서 직접 전송할 운영 데이터의 1차 전체 복제 예상량은 약 **9.03 GB (약 8.41 GiB)** 이다. 여기에 StoryMaker 전용 Plausible 분석 DB까지 같이 옮기면 약 **10.4 GB 전후**가 된다.

기존 타임머신 `Backup/` 약 **7.97 GB**는 첫 부팅 필수 항목이 아니므로 1차 이전에서 제외하고, 새 서버가 안정화된 뒤 2차 보관 복제를 권장한다.

Linux 가상환경 `.venv`와 VoiceBox `runtime/venv`는 Windows에서 그대로 재사용할 수 없으므로 복제하지 않고 새 서버에서 재설치한다.

## 2. GitHub에서 받는 항목

원격 저장소:

`git@github.com:kim6410/dell_V1_StoryMaker.git`

기본 브랜치: `main`

2026-08-15 조사 시 Git 추적 파일: 598개
Git 추적 워크트리 파일 합계: 45,777,377 bytes, 약 43.7 MiB

사무실 PC에서는 먼저 GitHub에서 StoryMaker_1 코드를 clone한다.

GitHub 기준으로 받는 범위:

- StoryMaker V1 Python/JavaScript/HTML/CSS 소스
- `storymaker-web/docker-compose.yml`
- StoryMaker Beta 소스 및 정적 리소스
- 운영·복구 문서
- `WORK_LOGS`
- 배포 참고 systemd 파일
- V1/Beta 기능 브리지 및 관리자 UI
- VoiceBox 연동 코드 중 부모 저장소에 포함된 부분

주의: `voicebox/` 자체는 부모 StoryMaker_1 Git 저장소의 추적 대상이 아니다. 별도 Git 저장소이며 현재 원격은 `https://github.com/jamiepine/voicebox.git`, 현재 Dell 체크아웃 HEAD는 `2bcb98d1a8b6fe05e15fbc1559e3085669e4035d`이다. 사무실에서는 이 커밋 기준으로 별도 clone/checkout하거나 Dell의 소스 상태를 별도로 보존해야 한다.

## 3. Dell에서 직접 복제해야 하는 필수 운영 데이터

### 3-1. V1 주 데이터베이스

원본: `/home/bourne/StoryMaker_1/database`

현재 전체 크기: **46,301,551 bytes / 약 44.2 MiB**

주요 파일:

- `storymaker.db` 약 13.3 MB
- `storymaker.db-wal` 약 4.2 MB
- `storymaker.db-shm`
- `weather_cache.db` 약 24.3 MB
- `weather_cache.db-wal` 약 3.2 MB
- `weather_cache.db-shm`
- `content_intelligence.db`
- `content_performance.db`

중요: SQLite WAL 사용 중이므로 월요일 실제 최종 복제 때는 서비스가 쓰는 파일을 단순 복사하지 말고 SQLite 일관성 스냅샷/백업을 만든 뒤 전송한다.

### 3-2. 프롬프트 DB

원본: `/home/bourne/StoryMaker_1/data/prompt_db`

크기: **422,784 bytes / 약 0.4 MiB**

주요 파일:

- `storymaker_prompts.db`
- WAL/SHM 파일

이 데이터는 Git 제외 대상이며 운영 프롬프트 상태 재현에 필요하다.

### 3-3. Persona 데이터

원본: `/home/bourne/StoryMaker_1/personas`

크기: **15,909 bytes**

크기는 작지만 사용자·업체별 동작 재현에 필요하므로 함께 복제한다.

### 3-4. 기존 출력 결과

원본: `/home/bourne/StoryMaker_1/output_results`

크기: **1,371,243,091 bytes / 약 1.28 GiB**

구성 예:

- `storymaker_main_uploads` 약 812 MB
- `mobile_one_shot` 약 387 MB
- `test_thumbnail_jobs` 약 113 MB
- 기타 기존 생성 결과

새 서버에서 과거 보관함·결과물 접근을 그대로 유지하려면 복제 필수다. 과거 결과물이 필요 없다고 사용자가 명시할 경우에만 별도 보관 후 1차 서버 전송에서 제외할 수 있다.

### 3-5. Beta 런타임 데이터

원본: `/home/bourne/StoryMaker_1/StoryMaker_beta/data`

크기: **1,272,319,698 bytes / 약 1.18 GiB**

주요 구성:

- `data/jobs` 약 933 MB
- `data/media` 약 39 MB
- Beta DB (`storymaker.db`, `storymaker_beta.db` 및 WAL/SHM)
- `gemini_queue` 약 2.1 MB
- 콘텐츠 참조 데이터
- 기타 현재 Beta 런타임 상태

동일한 현재 운영상태를 재현하려면 1차 복제 대상이다.

### 3-6. Beta 음악 미디어

원본: `/home/bourne/StoryMaker_1/StoryMaker_beta/media`

크기: **253,826,053 bytes / 약 242 MiB**

현재 대부분 `media/music`에 위치한다. Beta 제작 기능 재현을 위해 복제한다.

### 3-7. Beta Supertonic3 모델 캐시

원본: `/home/bourne/StoryMaker_1/StoryMaker_beta/Supertonic3/.cache`

크기: **403,520,886 bytes / 약 385 MiB**

주요 구성:

- ONNX 모델 약 380 MB
- voice styles 약 2.9 MB
- 이미지 및 기타 캐시

`.venv`는 제외하고 모델 캐시만 복사한다. 새 Windows 환경에서 모델을 다시 다운로드하도록 설계할 수도 있지만, 현장 네트워크 변수 제거를 위해 첫 이전에서는 복제를 권장한다.

### 3-8. Browser TTS

원본: `/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/browser-tts`

크기: **401,279,502 bytes / 약 383 MiB**

구성:

- `onnx/` 약 380 MB
- `voice_styles/` 약 2.9 MB
- model manifest

현재 `.gitignore`로 GitHub에서 제외되어 있으므로 Dell 직접 복제 필수다. 이것이 빠지면 Git clone만 한 새 서버에서 Browser TTS가 현재 Dell과 동일하게 동작하지 않는다.

### 3-9. V1 Supertonic 음악

원본: `/home/bourne/StoryMaker_1/supertonic/music`

크기: **253,831,427 bytes / 약 242 MiB**

Docker V1 backend에서 `/data/music`으로 직접 bind mount 중이다. 따라서 현재 음악 선택·제작 환경을 유지하려면 복제 대상이다.

## 4. VoiceBox 이전

### 4-1. VoiceBox 전체 현황

원본: `/home/bourne/StoryMaker_1/voicebox`

현재 전체 약 **12 GB**이나 이 전체를 Windows로 그대로 복사해서 쓰는 방식은 권장하지 않는다.

가장 큰 원인은 Linux 전용 가상환경이다.

- `voicebox/runtime/venv` 약 6.8 GB: **복제 제외 / Windows에서 재생성**
- `voicebox/runtime/models` 약 4.7 GB: **복제 필수 권장**
- `voicebox/runtime/python` 약 98 MB: Linux 번들 성격 확인 후 Windows 재설치 우선
- `voicebox/runtime/bin` 약 54 MB: Linux 바이너리면 Windows에서 재사용하지 않음
- VoiceBox 소스는 별도 Git 저장소에서 동일 HEAD 기준으로 clone

### 4-2. VoiceBox 모델

원본: `/home/bourne/StoryMaker_1/voicebox/runtime/models`

정확한 크기: **5,014,743,954 bytes / 약 4.67 GiB**

현재 두 모델:

- `Qwen3-TTS-12Hz-0.6B-CustomVoice` 약 2.4 GB
- `Qwen3-TTS-12Hz-0.6B-Base` 약 2.4 GB

이 모델들은 재다운로드 가능할 수 있지만, 월요일 현장 설치를 빠르게 하고 현재 버전 재현성을 높이기 위해 Dell에서 직접 전송한다.

### 4-3. VoiceBox 데이터·프로필·생성 이력

원본: `/home/bourne/StoryMaker_1/voicebox/runtime/data`

크기: **15,850,008 bytes / 약 15.1 MiB**

포함:

- `voicebox.db`
- profiles
- backends 설정
- generations 약 16 MB 범위

현재 등록된 StoryMaker용 음성 프로필과 VoiceBox 상태 재현을 위해 필수 복제한다.

### 4-4. VoiceBox output

원본: `/home/bourne/StoryMaker_1/voicebox/runtime/output`

크기: **733,528 bytes**

용량은 작으므로 함께 복제한다.

### 4-5. VoiceBox 실행 기준

Dell 현재 서비스:

`storymaker-v1-voicebox.service`

Dell 실행 포트: `17493`

Dell 실행 개념:

`python -m backend.main --host 0.0.0.0 --port 17493 --data-dir .../voicebox/runtime/data`

Windows에서는 Linux systemd와 Linux venv를 복사하지 않고 Python 환경을 새로 구성해 같은 포트 또는 사무실용 확정 포트로 Windows 서비스 등록한다.

## 5. Supertonic3 실행환경

Dell 현재 V1 Supertonic3 서비스 포트: `7789`

Dell V1 Podcast API 포트: `8003`

`/home/bourne/StoryMaker_1/Supertonic3` 전체 약 272 MB이나 그 대부분인 약 271 MB가 Linux `.venv`다.

따라서 이 폴더의 Linux `.venv`를 Windows로 가져가는 것은 의미가 없다. 소스·requirements 기준으로 Windows Python 환경을 새로 만들고, 실제 모델 데이터는 Browser TTS/Beta Supertonic 캐시 등 필요한 캐시만 별도 복제한다.

`/home/bourne/StoryMaker_1/supertonic` 전체 약 326 MB 중 `music` 약 243 MB가 실데이터이므로 코드와 음악을 분리해 이전한다.

## 6. Docker 데이터

Dell의 V1 backend 컨테이너:

- `storymaker-v1-backend`
- 호스트 포트 `8011` → 컨테이너 `8090`

현재 bind mount:

- `personas` → `/data/personas`
- `output_results` → `/data/output_results`
- `data/prompt_db` → `/prompt_data`
- `storymaker-web/backend` → `/app`
- `StoryMaker_beta/data` → `/beta_data`
- `storymaker-v1-app` → `/v1_frontend`
- `exports` → `/data/exports`
- `backups` → `/data/backups`
- `supertonic/music` → `/data/music`
- `database` → `/data`

즉 V1 backend 자체의 핵심 운영데이터는 익명 Docker volume 안이 아니라 위 StoryMaker_1 폴더들에 있어, 해당 폴더들을 정확히 복제하는 것이 핵심이다.

### Plausible 분석 데이터

StoryMaker V1 compose 관련 Docker volume:

- `storymaker_v1_plausible-db-data` 약 **51 MB**
- `storymaker_v1_plausible-event-data` 약 **1.3 GB**
- `storymaker_v1_caddy_data` 약 **132 KB**
- `storymaker_v1_caddy_config` 약 **12 KB**

Plausible 분석 이력을 새 서버에서도 그대로 보존하려면 약 1.35 GB를 추가 복제한다.

Caddy 인증서·설정 volume은 사무실 서버의 도메인/HTTPS 구조를 새로 구성할 예정이므로 그대로 이식하기보다 참고/보관 후 새 인증서를 발급하는 방향이 안전하다.

## 7. 첫 이전에서 복사하지 않을 항목

다음 항목은 사무실 Windows 11에서 그대로 재사용할 수 없거나 첫 운영 부팅에 불필요하다.

- 모든 Linux `.venv`
- `voicebox/runtime/venv` 약 6.8 GB
- Linux Python 바이너리/번들 중 Windows 비호환 항목
- `StoryMaker_beta/.venv`
- `StoryMaker_beta/Supertonic3/.venv`
- `/StoryMaker_1/Supertonic3/.venv`
- `__pycache__`, `.pyc`
- Chrome debug/test 캐시 중 기능 재현에 불필요한 임시 브라우저 상태는 최종 이전 시 재분류 가능
- 기존 `Backup/` 약 7.97 GB는 2차 보관 이전
- 오래된 일회성 `backups/`는 Git·업무일지와 별도로 보관 여부 결정

삭제하는 것이 아니라 **Dell에는 그대로 유지하고 1차 사무실 복제에서만 제외**한다.

## 8. 1차 전송 예상 용량

Dell 직접 전송 대상으로 계산한 현재 운영 데이터:

- V1 database: 46.3 MB
- prompt DB: 0.42 MB
- personas: 0.016 MB
- output_results: 1.371 GB
- Beta data: 1.272 GB
- Beta media: 0.254 GB
- Beta Supertonic model cache: 0.404 GB
- Browser TTS: 0.401 GB
- V1 music: 0.254 GB
- VoiceBox models: 5.015 GB
- VoiceBox runtime data: 0.016 GB
- VoiceBox output: 0.0007 GB

합계: **9,034,088,391 bytes ≈ 9.03 GB ≈ 8.41 GiB**

GitHub 추적 코드 약 45.8 MB는 별도 clone이므로 위 합계에 포함하지 않았다.

Plausible 분석 데이터까지 포함 시 약 1.35 GB 추가되어 전체 네트워크 복제량은 대략 **10.4 GB 전후**로 예상한다.

타임머신 `Backup/`까지 모두 옮기면 약 7.97 GB가 추가되어 약 **18 GB 이상**으로 늘어난다. 첫 이전에는 권장하지 않는다.

## 9. 월요일 권장 이전 순서

1. 사무실 Windows 11에 Tailscale 설치 및 Dell과 양방향 연결 확인
2. Git, Python, Docker 환경 준비
3. GitHub에서 `dell_V1_StoryMaker` main clone
4. 별도 VoiceBox 저장소를 Dell과 동일 commit `2bcb98d1a8b6fe05e15fbc1559e3085669e4035d` 기준으로 준비
5. Dell 운영 DB를 일관성 스냅샷으로 생성
6. 위 8.41 GiB 필수 운영 데이터만 Tailscale/SSH 계열로 복제
7. Windows Python 가상환경 새 생성
8. VoiceBox 모델 경로와 runtime data 연결
9. Browser TTS ONNX·voice_styles 경로 연결
10. Supertonic3 Windows 환경 설치 및 모델 캐시 연결
11. Docker V1 backend 재구성 및 bind mount 경로를 Windows 경로로 변경
12. 내부 포트별 테스트: V1 backend 8011, Podcast API 8003, Supertonic3 7789, VoiceBox 17493
13. 기존 기능·보관함·결과물·TTS·VoiceBox 회귀 검증
14. 자동 시작 구성
15. 재부팅 후 자동 복구 검증
16. 외부 도메인/프록시는 모든 내부 검증이 끝난 뒤 마지막에 전환
17. Dell 서버는 즉시 종료하지 않고 병행 운영

## 10. 이전 전 마지막 스냅샷 원칙

오늘 측정한 용량은 2026-08-15 현재값이다. 월요일까지 생성 결과·DB·VoiceBox 데이터가 증가할 수 있으므로 실제 복제 직전에 다시 용량과 DB 상태를 측정한다.

특히 SQLite DB는 WAL 모드 파일이 존재하므로 서비스가 쓰는 라이브 DB 파일을 개별 복사하는 방식으로 이전하지 않는다. 최종 전환 직전에는 SQLite 백업 API 또는 안전한 일관성 백업 절차로 스냅샷을 만든 뒤 SHA-256과 integrity check를 기록한다.

## 11. 현재 Git 상태 기준

이 문서 작성 직전 StoryMaker_1은 `git status --short`가 빈 상태였고, 최신 커밋은 `70e218a 규칙: 로컬 Claude 설정 Git 제외`였다.

이 문서 자체만 선별 커밋·Push하고, 완료 시 로컬 HEAD / origin/main / GitHub 실제 main 일치 및 최종 clean 상태를 다시 확인한다.
