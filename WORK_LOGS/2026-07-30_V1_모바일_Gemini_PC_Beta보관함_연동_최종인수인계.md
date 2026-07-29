# StoryMaker Dell V1 모바일 Gemini·PC Beta 보관함 연동 최종 인수인계

작성일: 2026-07-30
작업 루트: `/home/bourne/StoryMaker_1`
운영 화면: `https://app.mystorymaker.net/v1/?page=betaProduction`

## 1. 작업 목표

모바일에서는 사진과 메모를 받아 Gemini API로 SNS 글 슬롯을 생성하고, 글과 원본 사진만 서버에 저장한다.

팟캐스트, 숏폼 MP4, 썸네일 제작은 모바일에서 실행하지 않는다. PC의 Beta 보관함에서 WebGPU, WASM, WebCodecs, MediaBunny 등 브라우저 자원을 이용해 사용자가 직접 이어서 제작한다.

## 2. 확인된 핵심 문제

### 2.1 모바일 결과 조회 시 서버 미디어 자동 실행

모바일 Gemini 글 생성은 성공했지만 결과 상세, 진행 상태, 보관함 조회 과정에서 기존 서버 파이프라인이 팟캐스트와 썸네일 작업을 자동 시작했다.

이 때문에 모바일 완료 상태인 `pc_continue_waiting`이 `podcast_running`, `podcast_failed`, `thumbnail_requested` 등으로 덮였고 화면에 생성 실패 메시지가 표시됐다.

### 2.2 DB 연결 풀 고갈로 흰 화면 발생

반복 조회와 장시간 요청이 겹치면서 SQLAlchemy QueuePool이 소진됐다.

확인 오류:

`QueuePool limit of size 5 overflow 10 reached`

이 상태에서 `/v1/`, `/api/auth/personas`, 관리자 사용량 API가 500을 반환해 화면이 하얗게 표시됐다.

백엔드 컨테이너 재시작으로 연결 풀을 정리했고 이후 신규 QueuePool 오류가 없는 것을 확인했다.

### 2.3 잘못된 보관함 경로 확인

모바일 작업은 V1 내부 `mobile_one_shot_jobs`, `content_documents`, `content_archive_assets`에는 저장됐지만 사용자가 PC에서 확인하는 보관함은 별도 Beta 보관함이었다.

PC Beta 보관함 기준:

- DB: `/home/bourne/StoryMaker_1/StoryMaker_beta/data/storymaker_beta.db`
- 테이블: `beta_jobs`
- 작업 폴더: `/home/bourne/StoryMaker_1/StoryMaker_beta/data/jobs/beta_...`
- 결과 파일: 작업 폴더의 `result.json`

따라서 V1 내부 DB 저장만으로는 PC Beta 보관함에 표시되지 않았다.

## 3. 최종 수정 내용

### 3.1 모바일 Gemini API 직접 생성

파일:

`storymaker-web/backend/app/api/mobile_one_shot.py`

모바일 생성 요청은 Gemini API를 우선 사용한다.

성공 시:

- 상태 `gemini_completed`
- 진행률 100
- SNS 슬롯 파싱 및 저장
- `pipeline.defer_media_to_pc = true`
- `media.status = pc_continue_waiting`
- 모바일 후속 미디어 자동 실행 금지

Gemini API 실패 시 기존 Firefox Gemini Worker 대기열로 폴백한다.

### 3.2 모바일 완료 작업의 미디어 자동 실행 차단

파일:

- `storymaker-web/backend/app/api/mobile_one_shot.py`
- `storymaker-web/backend/app/api/content_board.py`

`pipeline.defer_media_to_pc`가 참이면 다음을 자동 실행하거나 동기화하지 않는다.

- 팟캐스트 생성
- 썸네일 생성
- 숏폼 MP4 생성
- 기존 실패 미디어 상태 재반영

모바일의 역할은 글과 사진 저장으로 종료한다.

### 3.3 PC Beta 보관함 브리지 추가

파일:

`storymaker-web/backend/app/api/mobile_one_shot.py`

모바일 Gemini 생성이 완료되면 V1 작업을 PC Beta 작업 구조로 변환한다.

생성 항목:

- `beta_YYYYMMDD_HHMMSS_hash` 작업 ID
- `StoryMaker_beta/data/jobs/<beta_job_id>/result.json`
- `storymaker_beta.db`의 `beta_jobs` 행
- `owner_user_id`
- 업체명, 지역, 업종, 전화번호
- 블로그, 네이버 플레이스, 구글 비즈니스, 인스타그램, 당근, 팟캐스트 대본 슬롯
- 원본 이미지 경로

미디어 항목은 비워 둔다.

- MP3 없음
- MP4 없음
- 썸네일 없음
- 음악 없음

PC Beta 보관함에서 사용자가 직접 후속 제작한다.

### 3.4 Beta 데이터 쓰기 마운트

파일:

`storymaker-web/docker-compose.yml`

변경:

`StoryMaker_beta/data:/beta_data:ro`

→

`StoryMaker_beta/data:/beta_data`

V1 백엔드가 Beta 작업 폴더와 `beta_jobs` 행을 생성할 수 있도록 해당 마운트만 쓰기 가능으로 전환했다.

Gemini API 환경변수는 기존 Beta `.env`를 V1 백엔드에서 읽도록 `env_file`을 연결했다. 업무일지와 Git에는 비밀값을 기록하지 않았다.

### 3.5 모바일 화면 정리

파일:

- `storymaker-web/backend/app/static/v1/index.html`
- `storymaker-web/backend/app/static/v1/mobile-beta-footer.js`
- `storymaker-web/backend/app/static/v1/mobile-beta-footer.css`

모바일에서는 팟캐스트, 숏폼 MP4, 썸네일 관련 하단 제작 영역을 숨기고 다음 안내를 표시한다.

- 모바일 작업 완료
- 글과 사진 저장 완료
- PC 스토리메이커 보관함에서 후속 제작
- 모바일에서는 글 결과 확인과 복사까지만 지원

PC 화면에서는 기존 모듈을 그대로 유지한다.

## 4. 실제 복구 및 검증 작업

최신 모바일 작업:

`mob-20260729210141-7485f436`

변환된 PC Beta 작업:

`beta_20260729_210141_7485f436`

검증 결과:

- Beta DB 행 존재
- `owner_user_id = 82`
- 상태 `gemini_completed`
- 진행률 100
- Beta `result.json` 존재
- 채널 7개 연결
- 원본 사진 6장 연결
- MP3, MP4, 썸네일, 음악 없음
- 소스 `mobile-one-shot`
- V1 HTTP 200
- Python `py_compile` PASS
- Node 문법 검사 PASS
- Docker Compose config PASS
- Git diff check PASS

## 5. 유지 원칙

1. 모바일에서는 글과 사진만 생성·저장한다.
2. 모바일 결과 조회만으로 팟캐스트, 썸네일, MP4를 시작하지 않는다.
3. PC Beta 보관함에서 WebGPU·WASM·WebCodecs 기반 제작을 사용자가 직접 시작한다.
4. 모바일 작업은 V1 내부 DB와 PC Beta 보관함 양쪽에 저장한다.
5. Beta 보관함 행에는 실제 로그인 사용자의 `owner_user_id`를 기록한다.
6. `.env`와 API 키는 출력하거나 Git에 포함하지 않는다.
7. `StoryMaker_beta/data` 이외의 Beta 폴더 권한은 변경하지 않는다.

## 6. Git 기록

기능 코드 커밋:

`e3f9597b5bd245040b3b11547807e0a41b2351d3`

커밋 메시지:

`모바일 결과를 PC Beta 보관함에 연동`

`origin/main` 푸시 완료.

## 7. 다음 작업 시작 기준

다음 작업에서는 아래 문서를 순서대로 먼저 확인한다.

1. `/home/bourne/StoryMaker_1/00_READ_FIRST.md`
2. `/home/bourne/StoryMaker_1/WORK_LOGS/2026-07-30_V1_모바일_Gemini_PC_Beta보관함_연동_최종인수인계.md`

첫 확인 항목:

- 새 모바일 작업 1건 생성
- 모바일 종료 상태가 `pc_continue_waiting`인지 확인
- PC Beta 보관함 최상단에 새 작업이 나타나는지 확인
- 보관함을 여는 것만으로 미디어 제작이 시작되지 않는지 확인
- PC에서 사용자가 직접 팟캐스트 및 숏폼 제작을 시작할 수 있는지 확인
