# 2026-08-12 VoiceBox Studio 관리자 인증 게이트 무한대기 수정 업무일지

작성일: 2026-08-12
작업 루트: `/home/bourne/StoryMaker_1`

## 증상

관리자 로그인 상태에서 VoiceBox Studio에 진입해도 `관리자 권한을 확인하고 있습니다.` 화면에서 계속 멈췄다.

## 원인 분석

- 외부 캐시 문제는 아니었다.
- `app.mystorymaker.net`은 최신 `voicebox-studio.html`과 최신 JS/CSS를 `no-cache, no-store`로 제공하고 있었다.
- `/v1-api/auth/me` 응답 구조도 `CommonResponse.data = UserResponse`로 현재 Studio 파서와 일치했다.
- 문제의 핵심은 정적 Studio UI 전체를 `/v1-api/auth/me` 재확인이 끝날 때까지 인증 게이트가 막고 있는 구조였다.
- V1 관리자 화면의 VoiceBox 버튼은 이미 `/v1-api/auth/me` 관리자 판정을 통과한 뒤 생성되므로, 같은 관리자 진입에서 다시 화면 전체를 블로킹할 필요가 없었다.

## 수정 내용

1. V1 관리자 VoiceBox 버튼 클릭 시 `sessionStorage.storymaker_voicebox_admin_entry`에 현재 시각을 기록한다.
2. 관리자 버튼에서 Studio로 이동할 때 `?from=v1-admin&v=20260812-2242`를 붙인다.
3. Studio는 최근 10분 이내 관리자 진입 grant 또는 `from=v1-admin`을 확인하면 상세 UI를 즉시 연다.
4. `/v1-api/auth/me` 재확인은 백그라운드에서 계속 수행한다.
5. 인증 요청에는 3.5초 AbortController 타임아웃을 추가했다.
6. 관리자 버튼 진입 상태에서 인증 응답이 느려도 UI는 유지하고 상태 문구만 `관리자 세션 확인 지연 · 기능 연결 전 UI 사용 가능`으로 표시한다.
7. 직접 URL 접근에서 관리자 인증이 명확히 실패하면 기존처럼 V1로 이동한다.
8. 실제 향후 Voicebox 생성/저장/합치기 API는 FastAPI `get_admin_user`를 사용해 서버에서 반드시 관리자 권한을 다시 확인한다. 정적 UI 진입 grant를 서버 보안 경계로 사용하지 않는다.

## 수정 파일

- `storymaker-web/backend/app/static/v1/index.html`
- `storymaker-web/backend/app/static/v1/v1-admin-voicebox-entry.js`
- `storymaker-web/backend/app/static/v1/voicebox-studio.js`
- `storymaker-web/backend/app/static/v1/voicebox-studio.html`

## 수정 전 백업

`/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260812_224227_VoiceBox_Studio_인증게이트_수정전`

## 검증

- `node --check v1-admin-voicebox-entry.js`: PASS
- `node --check voicebox-studio.js`: PASS
- `git diff --check`: PASS
- 외부 V1에서 `v1-admin-voicebox-entry.js?v=20260812-auth-gate-3` 제공 확인
- 외부 Studio에서 `voicebox-studio.js/css?v=20260812-auth-gate-3` 제공 확인
- 로컬 Studio HTTP 200
- 외부 Studio HTTP 200
- Headless Chrome 관리자 진입 재현 PASS
  - `<main id="voicebox-app">` 표시
  - `voicebox-auth-gate hidden` 확인
  - `처음 사용해도 4단계면 끝` 표시
  - `30초 기준 자동 분할` 표시

## 현재 범위

이번 작업은 VoiceBox Studio 화면 진입과 UI 인증 게이트 문제만 수정했다.
Voicebox 실제 TTS Backend, 청크 생성 API, 재생성, WAV/MP3 병합, SRT 생성 기능은 다음 단계에서 연결한다.
