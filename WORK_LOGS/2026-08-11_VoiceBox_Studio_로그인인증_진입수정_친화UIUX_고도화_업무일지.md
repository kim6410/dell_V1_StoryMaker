# 2026-08-11 VoiceBox Studio 로그인 인증 진입 수정 및 친화 UI/UX 고도화 업무일지

작성시각: 2026-08-11 05:31 KST
작업 루트: `/home/bourne/StoryMaker_1`

## 1. 작업 목적

관리자 로그인 상태에서 VoiceBox Studio 진입 후 `관리자 권한을 확인하고 있습니다.` 화면에 머무는 문제를 수정하고, 실제 개발계획에 맞춘 친화적인 관리자 작업실 화면으로 UI/UX를 고도화한다.

이번 단계는 Voicebox 실제 TTS Backend 연결 전 단계이며, 기존 로그인 API·세션·DB·Supertonic·Worker는 수정하지 않는다.

## 2. 사용자 확인 증상

관리자 로그인 상태에서 VoiceBox Studio 페이지로 이동했으나 다음 화면에서 진행되지 않았다.

- VB 로고
- VoiceBox Studio
- `관리자 권한을 확인하고 있습니다.`

V1 메인에서는 로그인 상태였으므로 Studio 독립 페이지의 인증 전달 방식을 우선 조사했다.

## 3. 원인 조사

기존 VoiceBox Studio는 `/v1-api/auth/me` 호출 시 `credentials: include`만 사용하고 있었다.

V1 실제 프런트 코드를 조사한 결과 인증 토큰은 아래 저장 위치 중 하나를 사용할 수 있다.

- `localStorage.storymaker_token`
- `sessionStorage.storymaker_token`
- `localStorage.access_token`
- `sessionStorage.access_token`

V1 기존 브리지들 역시 위 토큰을 Bearer Authorization 헤더에 넣는 방식을 사용한다.

따라서 메인 화면에서는 로그인으로 인식하지만 독립 Studio 페이지의 인증 요청에서는 Bearer 토큰이 빠질 가능성이 있었다.

## 4. 수정 전 백업

백업 경로:

`/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260811_053000_VoiceBox_Studio_인증UI_수정전`

백업 파일:

- `voicebox-studio.js`
- `voicebox-studio.html`
- `voicebox-studio.css`

수정 전 SHA-256:

- JS: `f1918c4729361c79b8ca0bdfd924c384f2095fec629cc78e863ad470efca0593`
- HTML: `275e12e396da648b30dd2739ae28aad50e05c67de818537d975aa970c3c3c1a9`
- CSS: `59579e0682035fd18b089f8c5d1341848255c10cfd2d0b7138394f38f9d4ced3`

## 5. 인증 수정

수정 파일:

`storymaker-web/backend/app/static/v1/voicebox-studio.js`

기존 방식은 `storymaker_token`의 localStorage만 확인하도록 보완되어 있었으나, V1 실사용 브리지와 동일하게 다음 4개 경로를 순서대로 확인하도록 확장했다.

```javascript
function getAuthHeaders() {
  const headers = { Accept: 'application/json' };
  try {
    const token = String(
      window.localStorage.getItem('storymaker_token')
      || window.sessionStorage.getItem('storymaker_token')
      || window.localStorage.getItem('access_token')
      || window.sessionStorage.getItem('access_token')
      || ''
    ).trim();
    if (token) headers.Authorization = `Bearer ${token}`;
  } catch (_) {}
  return headers;
}
```

`/v1-api/auth/me` 호출은 기존 서버 인증 API를 그대로 사용하며 DB·로그인 구현은 수정하지 않았다.

## 6. 친화형 UI/UX 고도화

Studio 진입 직후 사용자가 무엇을 해야 하는지 바로 이해하도록 상단에 4단계 작업 흐름을 추가했다.

1. 대본 입력
2. 자동 분할
3. 듣고 선택
4. 최종 합치기

안내 문구:

`대본을 넣고 → 30초로 나누고 → 마음에 드는 목소리만 고르고 → 한 번에 합치세요.`

특정 청크만 재생성할 수 있다는 장점을 처음 화면에서 바로 설명한다.

## 7. 프로젝트 영역 추가

신규 UI 항목:

- 프로젝트명 입력
- 기본값 `새 VoiceBox 프로젝트`
- 추천 설정 안내
- 30초 청크
- 청크 간 0.3초 무음

향후 프로젝트 저장 API가 연결되면 이 프로젝트명을 DB 또는 VoiceBox 프로젝트 메타데이터에 연결할 예정이다.

## 8. 유지된 핵심 작업실 UI

왼쪽 패널:

- 전체 대본 입력
- 글자 수
- 예시 대본
- 비우기
- 20초 / 30초 / 40초 목표 청크
- 30초 기준 자동 분할
- Smart Chunker 안내

오른쪽 패널:

- 청크 번호
- 예상 시간
- 글자 수
- 청크 텍스트 개별 편집
- 음성 파형 영역
- 음성 생성
- 개별 재생성
- 재생
- 청크 삭제

상단 최종 기능 자리:

- 전체 연속 재생
- 최종 음성 + SRT 합치기

실제 Voicebox Backend 연결 전에는 TTS 버튼이 활성 기능으로 오인되지 않도록 Backend 연결 대기 안내를 유지한다.

## 9. 캐시 갱신

브라우저가 이전 인증 JS/CSS를 계속 사용하는 문제를 피하기 위해 Studio 정적 파일 버전을 변경했다.

```text
voicebox-studio.css?v=20260811-friendly-auth-2
voicebox-studio.js?v=20260811-friendly-auth-2
```

## 10. 검증 결과

JavaScript 문법:

`node --check voicebox-studio.js` → PASS

Git whitespace 검사:

`git diff --check` → PASS

로컬 HTTP:

- `/static/v1/voicebox-studio.html` → 200
- `/static/v1/voicebox-studio.js?v=20260811-friendly-auth-2` → 200
- `/static/v1/voicebox-studio.css?v=20260811-friendly-auth-2` → 200

신규 UI 문자열 및 DOM 존재 확인:

- `처음 사용해도 4단계면 끝`
- `step-flow`
- `프로젝트명`
- `30초 기준 자동 분할`
- `최종 음성 + SRT 합치기`

인증 토큰 경로 확인:

- storymaker_token localStorage
- storymaker_token sessionStorage
- access_token localStorage
- access_token sessionStorage

## 11. 아직 미확인

실제 사용자의 현재 브라우저 관리자 로그인 세션으로 Studio 인증 게이트가 해제되는지는 사용자의 Ctrl+F5 또는 새 진입으로 최종 확인이 필요하다.

Voicebox Backend 17493은 아직 실제 TTS 서비스 기동 완료 전이므로 음성 생성 기능은 미연결 상태다.

## 12. 다음 작업

1. 관리자 V1 화면 Ctrl+F5
2. VoiceBox 버튼 클릭
3. 인증 게이트 즉시 해제 확인
4. 친화형 4단계 Studio 화면 표시 확인
5. 예시 대본 → 30초 자동분할 실제 UI 확인
6. Voicebox Backend 설치 완료
7. `/v1-api/voicebox/health` 서버 프록시 구현
8. 청크별 TTS 생성 API 연결
9. 재생성 V1/V2/V3 히스토리
10. 최종 WAV/MP3/SRT 병합

## 13. 절대 수정 금지 유지

이번 작업에서는 다음을 수정하지 않았다.

- 기존 로그인 API 구현
- 세션 DB
- 회원 DB
- Supertonic
- 기존 Worker
- 기존 Queue
- CUDA 전역 환경
- 보호 브라우저 MP4 번들

## 14. 롤백

문제가 발생하면 수정 전 백업 경로의 `voicebox-studio.js`, `voicebox-studio.html`, `voicebox-studio.css`를 기준으로 사용자 승인 후 파일별 복원한다.

`git reset`, `git clean`, 전체 저장소 롤백은 사용하지 않는다.
