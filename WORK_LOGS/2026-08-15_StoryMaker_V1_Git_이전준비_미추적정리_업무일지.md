# StoryMaker V1 Git 이전 준비 · 미추적 정리 업무일지

작업일: 2026-08-15
작업 저장소: `/home/bourne/StoryMaker_1`
브랜치: `main`
원격: `git@github.com:kim6410/dell_V1_StoryMaker.git`

## 목적

사무실 Windows 11 신규 서버로 StoryMaker V1을 이전하기 전에 Dell의 실제 운영 소스와 GitHub 상태를 일치시키고, 런타임 데이터와 생성 산출물을 Git 코드에서 분리한다.

## 작업 전 상태

- 기존 HEAD: `c4e0df93093b676c97e4dd6822ce8553952180e0`
- 기존 HEAD와 GitHub `main`은 일치했다.
- Git 기준 미추적 파일은 481개였다.
- 주요 미추적 분포:
  - `storymaker-web`: 222개
  - `StoryMaker_beta`: 187개
  - `supertonic`: 40개
  - `WORK_LOGS`: 23개
  - 기타 루트/배포 자료

## Git에 넣지 않도록 분리한 항목

`.gitignore`를 보완하여 아래 성격의 파일을 GitHub 코드 저장소에서 제외했다.

- V1 프론트엔드의 해시형 빌드 번들
- Browser MP4 테스트 번들
- browserPodcast worker 빌드 산출물
- ONNX Runtime WASM 런타임 패키지
- `browser-tts` 모델/음성 런타임 데이터
- Beta 생성 미디어
- Beta 사용자 content reference history
- 검사·scan JSON, excerpt, 임시 patch/inspect 파일
- Supertonic의 외부 Pretendard 폰트 런타임 payload
- 임시 `patch_*.py`

이 자료들은 사무실 서버 이전 시 Git clone 대상이 아니라 별도 런타임/백업 데이터로 취급한다.

## Git에 포함하도록 선별한 항목

- `AI_START_HERE.md`
- 기존 미추적 `WORK_LOGS` 문서
- V1/Beta 실제 정적 기능 JS/CSS/HTML
- Nemotron Lab 정적 기능 파일
- V1 관리자/아카이브/진행률/인라인 패널 브리지
- Beta 페이지 배경 및 Tori 기능 스크립트
- systemd 참고 파일과 SHA256SUMS
- 서버 복구/격리/프록시 관련 운영 스크립트

## 보안 및 문법 점검

- Git에 스테이징한 파일에서 GitHub/OpenAI형 토큰, private key, 일반 API key/secret/token/password 패턴 검사 수행
- 스테이징 대상에서 비밀정보 패턴 0개 확인
- 제외된 과거 생성 번들 `assets/staged-renderer-v1-20260723.js`에서는 `sk-` 형태 문자열 1건이 감지되어 Git 제외 규칙에 포함
- 스테이징된 JavaScript 문법 검사: 오류 0개
- Python 소스는 바이트코드 생성 없이 `compile()` 방식으로 별도 재검증할 것

## 운영 영향

이번 작업은 Git 인덱스와 `.gitignore` 정리만 수행했다.

다음 운영 서비스는 중지하거나 재시작하지 않았다.

- `storymaker-v1-backend`
- `storymaker-v1-podcast-api.service`
- `storymaker-v1-supertonic3.service`
- `storymaker-v1-voicebox.service`

DB, output, 모델, 미디어, 환경설정 및 Docker 런타임 데이터는 수정하지 않았다.

## 사무실 서버 이전 시 원칙

1. GitHub에서 StoryMaker V1 소스/문서를 clone한다.
2. DB, output, browser TTS 모델, 미디어, 모델 캐시 등 Git 제외 데이터는 Dell에서 별도로 복제한다.
3. Docker와 systemd 설정을 Windows/Docker 환경에 맞게 재구성한다.
4. 신규 사무실 서버에서 검증이 끝날 때까지 Dell 운영본을 종료하지 않는다.
