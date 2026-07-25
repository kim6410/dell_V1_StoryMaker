# Dell StoryMaker V1 독립성 및 Windows 잔재 전수점검 보고서

작성일: 2026-07-25

점검 대상:

`/home/bourne/StoryMaker_1`

외부 접속:

`https://app.mystorymaker.net/v1/`

점검 목적:

Windows 5800X에서 이전한 StoryMaker V1이 Dell Ubuntu 서버에서 독립적으로 작동하는지 확인하고, Windows 절대경로·Windows 전용 파일·이전용 임시 파일·외부 장비 의존성을 분류한다.

이번 점검에서는 파일 수정, 삭제, 이동, 서비스 재시작을 하지 않았다.

---

## 1. 최종 판정

현재 Dell V1은 대시보드, 정적 파일, 주요 API, DB, 보관함 데이터, V1 전용 Podcast API와 V1 전용 Supertonic3까지 기본 실행은 정상이다.

그러나 **완전 독립·완전 고립 상태로 판정할 수는 없다.**

주요 이유는 두 가지다.

1. 서버형 슬라이드쇼 제작 경로가 Mac mini `192.168.0.34`에 SSH·SCP로 작업을 넘기는 구조를 아직 사용한다.
2. V1 Podcast API 서비스가 실행 파일은 V1 전용 `app.py`를 사용하지만 Python 인터프리터는 공용 `/home/bourne/Supertonic3/.venv/bin/python`을 사용한다.

따라서 Windows PC가 꺼져도 Dell V1의 대시보드·DB·콘텐츠 조회·Podcast API·TTS 기본 서비스는 동작할 가능성이 높지만, Mac mini가 꺼지거나 접근 불가하면 서버형 슬라이드쇼 경로는 실패할 수 있다.

V1 Podcast API의 공용 Python 가상환경이 변경되거나 깨지면 V1 Podcast API도 함께 영향을 받을 수 있다.

현재 독립성 판정:

- Windows 5800X 의존성: 대부분 제거됨
- Dell 내부 독립 실행: 기본 기능 정상
- Mac mini 의존성: 남아 있음
- 공용 Python 가상환경 의존성: 남아 있음
- 완전 고립 판정: 미달

---

## 2. 현재 정상 확인 항목

### V1 Backend 컨테이너

컨테이너:

`storymaker-v1-backend`

상태:

- running
- 재시작 횟수 0
- 호스트 포트 `8011` → 컨테이너 `8090`

마운트는 모두 Dell 로컬 경로를 사용한다.

- `/home/bourne/StoryMaker_1/storymaker-v1-app` → `/v1_frontend`
- `/home/bourne/StoryMaker_1/database` → `/data`
- `/home/bourne/StoryMaker_1/personas` → `/data/personas`
- `/home/bourne/StoryMaker_1/output_results` → `/data/output_results`
- `/home/bourne/StoryMaker_1/exports` → `/data/exports`
- `/home/bourne/StoryMaker_1/backups` → `/data/backups`
- `/home/bourne/StoryMaker_1/supertonic/music` → `/data/music`
- `/home/bourne/StoryMaker_1/storymaker-web/backend` → `/app`

Windows 드라이브를 직접 마운트하거나 Windows 공유폴더를 참조하는 컨테이너 마운트는 확인되지 않았다.

### HTTP 확인

아래 주소는 모두 HTTP 200을 반환했다.

- `http://127.0.0.1:8011/v1`
- `http://127.0.0.1:8011/v1/`
- `http://127.0.0.1:8011/docs`
- `http://127.0.0.1:8011/openapi.json`
- `https://app.mystorymaker.net/v1/`

공개 V1 HTML의 주요 JavaScript와 CSS 자산 10개를 표본 검사했고 모두 HTTP 200이었다.

공개 HTML에서 `127.0.0.1`, `localhost`, `192.168.x.x`를 직접 참조하는 초기 로더 URL은 확인되지 않았다.

`https://mystorymaker.net/v1`은 현재 HTTP 404다.

현재 운영 V1 주소는 `https://app.mystorymaker.net/v1/`이다.

### DB 무결성

다음 SQLite DB의 `PRAGMA quick_check` 결과는 모두 `ok`였다.

- `content_intelligence.db`
- `storymaker.db`
- `content_performance.db`

이전 및 점검용 DB 사본도 quick_check 결과 `ok`였다.

### 이전 데이터 존재

- `output_results`: 약 2.0GB
- 결과 파일 수: 2,042개
- `personas`: 7개 파일
- `database`: 약 29MB
- `supertonic`: 약 705MB

최근 보관함 API와 작업 진행 API 요청이 반복적으로 HTTP 200을 반환하고 있다.

인증이 필요한 API를 비로그인 상태로 호출했을 때 HTTP 401과 정상적인 로그인 필요 메시지가 반환돼 인증 가드도 작동한다.

### Dell V1 전용 서비스

V1 Podcast API:

- 서비스: `storymaker-v1-podcast-api.service`
- 포트: `8003`
- `/health`: HTTP 200

V1 Supertonic3:

- 서비스: `storymaker-v1-supertonic3.service`
- 포트: `7789`
- 작업 경로: `/home/bourne/StoryMaker_1/Supertonic3`
- 실행 파일: `/home/bourne/StoryMaker_1/Supertonic3/.venv/bin/supertonic`

Backend 컨테이너의 Podcast 연결:

`PODCAST_API_URL=http://host.docker.internal:8003`

이는 Windows 호스트가 아니라 동일한 Dell 호스트의 8003 포트에 접근하기 위한 Docker 연결이다.

---

## 3. 완전 고립을 막는 핵심 의존성

### A. Mac mini 슬라이드쇼 의존성

활성 파일:

`/home/bourne/StoryMaker_1/supertonic/run_v1_slideshow.sh`

설정:

`MAC_HOST="192.168.0.34"`

실제 동작:

- SSH로 Mac mini 접속
- 이미지·MP3·SRT·JSON을 SCP 전송
- Mac mini에서 `slideshow_worker.py` 실행
- 완성 MP4를 Dell로 다시 SCP 복사

활성 호출 위치:

`/home/bourne/StoryMaker_1/supertonic/app.py`

`app.py`에서 `run_v1_slideshow.sh`를 실제 외부 렌더 스크립트로 지정한다.

영향:

Mac mini가 꺼져 있거나 SSH 접속이 실패하면 이 서버형 슬라이드쇼 경로는 Dell 단독으로 완주하지 못한다.

판정:

**완전 독립을 막는 1순위 항목이다.**

브라우저 WebCodecs MP4 경로가 별도로 정상 작동하더라도 서버형 API 경로에 Mac mini 의존성이 남아 있으므로 전체 시스템은 완전 고립으로 볼 수 없다.

### B. V1 Podcast API의 공용 Python 가상환경 의존성

서비스:

`/etc/systemd/system/storymaker-v1-podcast-api.service`

현재 실행:

`ExecStart=/home/bourne/Supertonic3/.venv/bin/python app.py`

작업 경로와 앱 소스는 V1 전용이다.

`WorkingDirectory=/home/bourne/StoryMaker_1/supertonic`

하지만 Python 인터프리터와 설치 패키지는 공용 Supertonic3 가상환경을 사용한다.

영향:

공용 `/home/bourne/Supertonic3/.venv`의 패키지 변경, Python 손상, 재설치가 V1 Podcast API에 영향을 줄 수 있다.

판정:

**논리적 격리는 됐지만 실행환경 격리는 미완료다.**

V1 전용 가상환경을 사용하도록 바꿔야 완전 고립에 가까워진다.

### C. Dell 공용 날씨 서비스 의존성

파일:

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/core/prompt_builder.py`

기본 연결:

`http://host.docker.internal:8030/tool/weather`

이는 Windows PC나 다른 장비가 아니라 동일한 Dell 서버의 공용 Weather 서비스다.

판정:

Dell 한 대 안에서 작동하므로 Windows 독립성에는 문제가 없다.

다만 V1 디렉터리만 떼어 별도 서버로 이전하는 수준의 완전 자급 구조는 아니다.

---

## 4. Windows 절대경로가 남은 활성·준활성 파일

### 직접 점검이 필요한 파일

`/home/bourne/StoryMaker_1/supertonic/podcast_generator.pyw`

남은 값:

- `F:\Supertonic3`
- Windows 설치 구조 설명

현재 systemd 서비스는 `app.py`를 실행하므로 이 `.pyw`가 운영 핵심 경로로 직접 실행되는 정황은 확인되지 않았다.

분류:

Windows GUI 실행본 또는 이전 원본일 가능성이 높다.

`/home/bourne/StoryMaker_1/supertonic/vlc_check.py`

남은 값:

- `F:\Program Files\VideoLAN\VLC`
- `F:\Program Files (x86)\VideoLAN\VLC`
- `F:\VLC`
- `F:\VideoLAN\VLC`
- `os.walk("F:\\")`

Linux 운영에서 실행되면 의미가 없거나 불필요한 전체 드라이브 탐색 로직이다.

`/home/bourne/StoryMaker_1/supertonic/fm_paths.py`

남은 값:

- `C:\Program Files\VideoLAN\VLC\vlc.exe`
- `C:\Program Files (x86)\VideoLAN\VLC\vlc.exe`

운영 호출 여부를 추가 확인한 뒤 Linux 분기 또는 비활성 후보로 분류해야 한다.

### Windows 경로가 남은 설정·상태 데이터

`/home/bourne/StoryMaker_1/supertonic/user_jobs/default/*/render_job.json`

여러 과거 작업에 다음 경로가 저장돼 있다.

- `F:\StoryMaker_V1\supertonic\user_jobs\...`
- `F:\StoryMaker_V1\output_results\...`
- `F:\StoryMaker_V1\supertonic\SlidShow\...`

이 파일들은 과거 작업 메타데이터로 보인다.

단순 보관만 하면 즉시 장애를 만들지는 않지만, 재시도·재렌더·복구 기능이 이 JSON을 다시 사용하면 Dell에서 경로 오류가 발생할 수 있다.

판정:

삭제보다 먼저 현재 API가 과거 `render_job.json`을 재사용하는지 확인해야 한다.

`/home/bourne/StoryMaker_1/supertonic/slid_refactored/SETTING.json`

`/home/bourne/StoryMaker_1/supertonic/slid_refactored/slid_ui_state.json`

남은 값:

- `G:/ONEDRIVE_BACKUP/...`
- `F:\O_SLIDE\OUTPUT\...`
- `F:\FM연구소\slid_refactored`

Windows 로컬 작업 상태와 개인 미디어 경로가 그대로 남아 있다.

현재 Linux V1 핵심 서비스에서 사용되는지 확인 후 격리 또는 보관 후보로 분류해야 한다.

### Windows 전용 참고·실험 코드

`/home/bourne/StoryMaker_1/supertonic/JSON/` 아래 여러 Python 파일에 다음 값이 남아 있다.

- `C:\Windows\Fonts\malgun.ttf`
- `C:\Windows\Fonts\malgunbd.ttf`
- `C:\Windows\Fonts\arial.ttf`

파일명과 위치상 실험·참고 코드일 가능성이 높지만, 실제 호출 여부를 확인하기 전에는 삭제하지 않는다.

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/ai_auto_generate_console.js`

화면 연출용 문자열 `c:\_`가 있다.

이는 실제 파일 경로가 아니라 콘솔 애니메이션 표현이므로 운영 장애 요소가 아니다.

---

## 5. Windows 전용 실행 파일

다음 Windows 배치 파일이 남아 있다.

- `/home/bourne/StoryMaker_1/supertonic/00_FIND_PODCAST_GENERATOR_PATH.bat`
- `/home/bourne/StoryMaker_1/supertonic/01_START_SUPERTONIC_SERVER.bat`
- `/home/bourne/StoryMaker_1/supertonic/02_OPEN_SUPERTONIC_DOCS.bat`
- `/home/bourne/StoryMaker_1/supertonic/02_START_SLIDESHOW.bat`
- `/home/bourne/StoryMaker_1/supertonic/02_START_SLIDESHOW_ALT.bat`
- `/home/bourne/StoryMaker_1/supertonic/03_TEST_SUPERTONIC_TTS.bat`
- `/home/bourne/StoryMaker_1/supertonic/PODCAST_GENERATOR.bat`

Linux systemd 또는 Docker가 이 파일을 실행하는 정황은 확인되지 않았다.

분류:

운영 불필요 가능성이 높은 Windows 잔재다.

즉시 삭제하지 않고 별도 보관 폴더로 이동 가능한지 참조 검색과 백업 후 판단한다.

V1 Supertonic3 가상환경 안의 `.exe`, `Activate.ps1`, Windows 호환 라이브러리 파일은 pip·setuptools 패키지가 기본 포함하는 플랫폼 호환 자산이다.

이 파일들은 용량이 작고 Python 패키지 내부 구성 요소이므로 개별 삭제 대상이 아니다.

---

## 6. 이전용 대용량 파일과 임시 폴더

현재 StoryMaker_1 루트에 Windows 이전 과정의 대용량 파일이 남아 있다.

- `WINDOWS_V1_ALL_DATA_20260725_031500.tar`: 약 2.1GB
- `WINDOWS_V1_SLIDESHOW_20260725.tar`: 약 136MB
- `WINDOWS_V1_SUPERTONIC_USER_JOBS_20260725.tar`: 약 170MB
- `STORYMAKER_BETA_DELL_IMPORT_20260725.tar`: 약 1.72GB
- `.windows_import_20260725_025300`: 약 618MB
- `.windows_data_stage_20260725_031500`: 약 4KB

이전 관련 백업 폴더도 존재한다.

- `/home/bourne/StoryMaker_1/backups/windows_v1_import_20260725_025300`
- `/home/bourne/StoryMaker_1/backups/dell_data_before_windows_full_20260725_035200`
- `/home/bourne/StoryMaker_1/backups/supertonic_data_before_windows_20260725_040000`

판정:

루트의 TAR와 스테이징 폴더는 실행에 필요한 운영 파일이라기보다 이전 원본·임시 자료일 가능성이 높다.

하지만 현재는 이전 직후이고 복구 기준점 역할을 할 수 있으므로 삭제하지 않는다.

먼저 해시, 포함 목록, 공식 백업 중복 여부, 마지막 정상 완주를 확인한 뒤 보관 위치 이동 여부를 결정해야 한다.

---

## 7. 백업·사본 파일

활성 소스 폴더 안에 Windows 이전 전후 사본이 남아 있다.

예:

- `podcast.py.before_windows_podcast_api`
- `main.py.before_windows_v1api_bridge`
- `index.html.before_windows_auth`
- `v1-browser-mp4-save-bridge.js.before_windows_auto_mp4`
- `storymaker-gemini-worker-v1.user.js.before_windows_worker`
- `app.py.before_v1_8003_20260720`
- `app - 07201030.py`

이 파일들은 현재 import 또는 정적 로딩 대상이 아니라면 운영에는 필요하지 않다.

다만 장애 복구 근거가 될 수 있으므로 즉시 삭제하지 않고, 참조 여부 확인 후 `backups` 또는 별도 아카이브로 이동하는 방식이 적합하다.

---

## 8. 현재 로그에서 확인된 주의사항

최근 V1 Backend 로그에서 과거 한 시점에 다음 응답이 확인됐다.

- `/api/slideshow/audio-list` → 502
- `/api/slideshow/health` → 502

재검사 결과:

- `/api/slideshow/health` → HTTP 200
- `/api/slideshow/audio-list` → 비로그인 상태 HTTP 401

현재 즉시 장애는 재현되지 않았다.

FastAPI OpenAPI 생성 시 중복 Operation ID 경고가 두 건 있다.

- slideshow media HEAD 라우트
- weather snapshots 라우트

이는 현재 HTTP 200 응답을 막지는 않지만 API 문서와 클라이언트 자동 생성 시 충돌 가능성이 있다.

---

## 9. 완전 독립화를 위한 작업 우선순위

### 1순위: Mac mini 렌더 경로 제거 또는 Dell 로컬 렌더로 전환

대상:

- `supertonic/app.py`
- `supertonic/run_v1_slideshow.sh`

목표:

슬라이드쇼 서버형 제작도 Dell 내부에서만 완주하도록 한다.

브라우저 MP4 제작이 최종 표준이라면 서버형 Mac 경로를 비활성화하고 브라우저 경로만 사용하도록 정리할 수 있다.

서버 렌더가 필요하다면 Dell 로컬 FFmpeg 또는 Dell 전용 Worker로 교체해야 한다.

### 2순위: V1 Podcast API 전용 Python 가상환경 적용

현재:

`/home/bourne/Supertonic3/.venv/bin/python`

목표 예시:

`/home/bourne/StoryMaker_1/supertonic/.venv/bin/python`

또는 검증된 V1 전용 가상환경을 별도로 만든다.

패키지 버전과 실행 검증을 끝낸 뒤 systemd ExecStart만 전환해야 한다.

### 3순위: Windows 경로가 남은 과거 render_job 메타 처리

과거 작업 재시도 기능이 필요한지 확인한다.

필요하면 Windows 경로를 Dell 경로로 변환하는 안전한 마이그레이션 도구를 만든다.

필요하지 않으면 활성 작업 경로에서 분리 보관한다.

### 4순위: Windows 전용 배치·GUI·VLC 탐색 파일 정리

참조 검색 후 실행 대상이 아닌 파일만 별도 아카이브로 이동한다.

삭제보다 보관 이동을 우선한다.

### 5순위: 이전용 TAR·스테이징 폴더 정리

현재 정상 완주와 복구 백업을 확인한 뒤 루트에서 공식 백업 위치로 이동할 수 있다.

사용자 승인 전에는 삭제하지 않는다.

---

## 10. 완전 독립 성공 판정 기준

아래 조건을 모두 만족해야 Dell V1을 완전 독립으로 판정한다.

1. Windows 5800X 전원을 끈 상태에서 로그인·대시보드·업체정보·제작·보관함이 정상이다.
2. Mac mini 전원을 끈 상태에서도 Podcast·SRT·썸네일·MP4 제작이 완주된다.
3. 공용 `/home/bourne/Supertonic3/.venv`를 사용하지 않고 V1 전용 Python 환경으로 Podcast API가 실행된다.
4. V1 TTS는 V1 전용 포트 7789와 V1 전용 모델 환경만 사용한다.
5. V1 DB와 결과물은 `/home/bourne/StoryMaker_1` 아래에서만 읽고 쓴다.
6. 새 작업의 모든 `result.json`, `render_job.json`, 로그에 `C:\`, `F:\`, `G:\` 경로가 기록되지 않는다.
7. 서버형 또는 브라우저형 MP4 제작 중 선택한 표준 경로가 Dell 단독으로 완주된다.
8. 새로고침 후 보관함에서 이미지·MP3·SRT·썸네일·MP4가 열린다.
9. Docker, V1 Podcast API, V1 Supertonic3를 재부팅 후 자동 복구할 수 있다.
10. 최근 로그에 500·502·Traceback이 없고 실제 사용자 완주 테스트를 통과한다.

---

## 11. 다음 작업 권고

코드를 바로 수정하기보다 먼저 아래 두 가지를 실제로 시험하는 것이 안전하다.

첫 번째 시험:

Windows 5800X와 Mac mini를 모두 끈 상태에서 Dell V1의 콘텐츠 제작을 실행한다.

두 번째 시험:

새 작업에서 이미지 업로드 → AI 콘텐츠 → MP3 → SRT → 썸네일 → MP4 → 보관함 저장까지 완주하고, 생성된 JSON과 로그에 Windows 경로가 새로 생기는지 확인한다.

이 시험에서 MP4만 실패하면 Mac mini 의존성이 실제 장애 원인으로 확정된다.

Podcast API가 공용 가상환경을 사용하고 있다는 사실은 시험 결과와 관계없이 구조적 격리 미완료 항목이다.

---

## 12. 이번 점검에서 변경한 항목

생성한 보고서:

`/home/bourne/StoryMaker_1/WORK_LOGS/2026-07-25_Dell_V1_독립성_Windows잔재_전수점검_보고서.md`

기존 코드·DB·설정·서비스는 변경하지 않았다.

삭제·이동·재시작도 수행하지 않았다.
