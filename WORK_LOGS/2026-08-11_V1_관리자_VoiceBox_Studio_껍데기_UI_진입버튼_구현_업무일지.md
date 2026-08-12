# 2026-08-11 V1 관리자 VoiceBox Studio 껍데기 UI 및 진입 버튼 구현 업무일지

작성일: 2026-08-11 KST
작업 루트: `/home/bourne/StoryMaker_1`
대상: StoryMaker V1 관리자 전용 VoiceBox Studio 1차 껍데기

## 1. 작업 목적

Voicebox 실제 Backend 연결이 완료되기 전에 StoryMaker V1 관리자 화면에서 향후 음성 제작 기능의 UI/UX를 먼저 확인할 수 있도록 관리자 전용 VoiceBox 진입 버튼과 별도 Studio 껍데기 화면을 구현했다.

이번 단계는 실제 TTS 생성 API, WAV/MP3 병합, SRT 생성 API를 연결하는 단계가 아니다.

현재 구현 범위는 다음과 같다.

- 관리자 로그인 여부 확인
- 관리자에게만 VoiceBox 진입 버튼 노출
- 독립 VoiceBox Studio 화면 생성
- 전체 대본 입력
- 약 20/30/40초 목표 청크 선택
- 한국어 문장 경계를 우선하는 프런트 Smart Chunker
- 청크별 편집 카드 생성
- 청크별 예상 재생시간 및 글자 수 표시
- 생성, 재생성, 재생 버튼의 자리 구성
- 청크 삭제
- 전체 연속 재생 버튼 자리 구성
- 최종 음성 + SRT 합치기 버튼 자리 구성
- Voicebox Backend 미연결 상태를 명확하게 표시

## 2. 작업 전 안전 점검

1. 기존 V1 `index.html`만 수정 대상으로 특정했다.
2. 기존 Supertonic, Worker, DB, 인증 Backend, 보호 번들, Beta 파일은 수정하지 않았다.
3. 신규 VoiceBox 파일은 독립 파일로 생성했다.
4. 기존 `index.html`은 부분 치환으로 스크립트 참조 1줄만 추가했다.
5. 삭제, 이동, `git add .`, `git clean`, `git reset`, 전체 덮어쓰기를 사용하지 않았다.

## 3. 수정 전 백업

백업 경로:

`/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260811_052342_VoiceBox_Studio_껍데기_수정전`

백업 파일:

`index.html`

백업 검증:

- 61줄
- 5,123 bytes
- SHA-256 `49ce2a243eddd1908a5d0b65268647dbb84bff38f4cf5878dab63ee6366495c7`

## 4. 변경 파일

기존 파일 수정:

`storymaker-web/backend/app/static/v1/index.html`

신규 파일:

`storymaker-web/backend/app/static/v1/v1-admin-voicebox-entry.js`

`storymaker-web/backend/app/static/v1/voicebox-studio.html`

`storymaker-web/backend/app/static/v1/voicebox-studio.css`

`storymaker-web/backend/app/static/v1/voicebox-studio.js`

## 5. 관리자 VoiceBox 진입 버튼

신규 브리지:

`v1-admin-voicebox-entry.js`

V1 기존 관리자 판정 기준과 동일하게 `/v1-api/auth/me`를 사용한다.

응답의 다음 형태를 지원한다.

- `payload.data.user`
- `payload.user`
- `payload.data`

다음 관리자 속성을 인정한다.

- `is_admin=true/1`
- `admin=true/1`
- `role=admin`
- `role=administrator`

관리자가 아니면 VoiceBox 버튼 DOM 자체를 제거한다.

관리자인 경우 화면 우측 하단에 `VoiceBox / 관리자 음성 스튜디오` 버튼을 생성한다.

버튼 클릭 경로:

`/static/v1/voicebox-studio.html`

로그인 상태 변경 이벤트 `storymaker-auth-changed`, `pageshow`, 탭 재활성화 시 인증 상태를 다시 확인한다.

## 6. V1 index 연결

`index.html`에 아래 한 줄만 추가했다.

```html
<script src="/static/v1/v1-admin-voicebox-entry.js?v=20260811-voicebox-shell-1"></script>
```

기존 React 번들, 메뉴 컴포넌트, 관리자 인증 코드는 수정하지 않았다.

## 7. VoiceBox Studio 관리자 이중 확인

Studio URL을 직접 입력하는 경우도 있으므로 페이지 내부 `voicebox-studio.js`에서 `/v1-api/auth/me`를 다시 조회한다.

관리자가 아니면 Studio 본문을 표시하지 않고 V1 대시보드 `/v1/`로 되돌린다.

이번 단계는 프런트 UI 보호이며, 향후 실제 Voicebox 생성 API는 서버에서도 관리자 권한을 다시 검사해야 한다.

## 8. Studio UI 구성

상단:

- V1 대시보드 돌아가기
- VoiceBox Studio 제목
- Voicebox 엔진 상태
- 음성 엔진 선택 자리
- 목표 청크 20/30/40초
- 청크 간 무음 0.1/0.3/0.5/0.8초
- 전체 연속 재생
- 최종 음성 + SRT 합치기

좌측 패널:

- 전체 대본 편집기
- 글자 수
- 예시 대본
- 비우기
- 자동 분할
- Smart Chunker 설명

우측 패널:

- Chunk 번호
- 예상 길이
- 글자 수
- 독립 텍스트 편집
- 파형 Placeholder
- 음성 생성
- 개별 재생성
- 재생
- 삭제

## 9. Smart Chunker 1차 구현

현재 프런트 껍데기에서도 자동 분할을 실제로 테스트할 수 있게 구현했다.

문장 경계 우선순위:

- 마침표
- 물음표
- 느낌표
- 한국어/중국어 계열 종결기호
- 문단 줄바꿈

시간 추정은 임시로 한국어 약 `4.4자/초`를 사용한다.

30초 기준 목표 글자 수 예:

`30 × 4.4 ≒ 132자`

최소 범위는 목표의 약 58%, 최대 범위는 약 138%로 둔다.

이 값은 최종 기준이 아니다.

실제 Voicebox 음성이 생성되면 추정 시간이 아니라 WAV/MP3의 실제 duration을 사용한다.

## 10. 청크 수정 정책

청크 텍스트를 수정하면 해당 청크 상태를 다시 `DRAFT`로 돌리고, 향후 연결될 기존 음성 버전과 선택 버전을 무효화하도록 데이터 흐름을 준비했다.

청크 삭제는 현재 브라우저 메모리의 해당 카드만 제거한다.

아직 프로젝트 DB나 파일에는 저장하지 않는다.

## 11. Voicebox Health 연결 구조 수정

초기 구현 중 브라우저에서 `http://127.0.0.1:17493/health`를 직접 호출하면 관리자 PC 자신의 localhost를 호출하게 되는 구조적 문제가 확인됐다.

즉 브라우저 → Dell Voicebox 직접 호출 구조로 만들면 안 된다.

즉시 다음 구조로 수정했다.

```text
Browser
  ↓
/v1-api/voicebox/health
  ↓
StoryMaker V1 Backend
  ↓
127.0.0.1:17493
  ↓
Dell Voicebox
```

현재 `/v1-api/voicebox/health` Backend 프록시는 아직 만들지 않았으므로 UI에서는 `Voicebox 엔진 연결 대기`로 표시된다.

다음 Backend 단계에서 이 API를 생성한다.

## 12. 현재 버튼별 상태

현재 실제 동작:

- 관리자 권한 확인
- VoiceBox 진입
- 예시 대본 넣기
- 전체 대본 작성
- 글자 수 계산
- 20/30/40초 자동 분할
- 청크 독립 편집
- 청크 삭제

Backend 연결 후 활성화할 기능:

- 음성 생성
- 개별 재생성
- V1/V2/V3 히스토리
- 재생
- 전체 연속 재생
- WAV 합치기
- MP3 합치기
- SRT 생성
- 최종 다운로드

## 13. UI 파일 검증값

### v1-admin-voicebox-entry.js

- 99줄
- 3,836 bytes
- SHA-256 `cb013cba9a693a59ab301fd2d31e6d1d5b73c8ff7bbffb56d4f7f6bf1546523f`

### voicebox-studio.html

- 113줄
- 5,011 bytes
- SHA-256 `275e12e396da648b30dd2739ae28aad50e05c67de818537d975aa970c3c3c1a9`

### voicebox-studio.css

- 7,800 bytes
- SHA-256 `59579e0682035fd18b089f8c5d1341848255c10cfd2d0b7138394f38f9d4ced3`

### voicebox-studio.js

- 272줄
- 11,628 bytes
- SHA-256 `f1918c4729361c79b8ca0bdfd924c384f2095fec629cc78e863ad470efca0593`

## 14. 문법 및 HTTP 검증

JavaScript:

`node --check v1-admin-voicebox-entry.js` PASS

`node --check voicebox-studio.js` PASS

Git whitespace:

`git diff --check` PASS

Dell V1 HTTP:

- `http://127.0.0.1:8011/v1/` → 200
- `/static/v1/v1-admin-voicebox-entry.js` → 200
- `/static/v1/voicebox-studio.html` → 200
- `/static/v1/voicebox-studio.css` → 200
- `/static/v1/voicebox-studio.js` → 200

외부 제공 확인:

- `https://app.mystorymaker.net/v1/` → 200
- `https://app.mystorymaker.net/static/v1/voicebox-studio.html` → 200

## 15. 아직 미확인인 항목

실제 브라우저에서 관리자 계정으로 로그인한 뒤 다음 UI는 사용자가 직접 확인할 필요가 있다.

- 우측 하단 VoiceBox 버튼의 실제 위치와 크기
- 기존 V1 모바일/PC 카드와 겹침 여부
- Studio 화면의 실제 모니터 해상도별 가독성
- 자동 분할 결과가 실제 한국어 원고에서 원하는 호흡과 맞는지

HTTP와 JS 문법은 검증됐지만 실제 관리자 브라우저 E2E를 아직 수행하지 않았으므로 UI 최종 성공으로 단정하지 않는다.

## 16. 다음 작업

1. `/home/bourne/StoryMaker_1/voicebox/runtime/venv` Voicebox 설치 완료
2. Dell GTX1060에서 Voicebox 실제 기동
3. `127.0.0.1:17493/health` 확인
4. `storymaker-v1-voicebox.service` 자동기동
5. V1 Backend에 관리자 전용 `/v1-api/voicebox/health` 추가
6. StoryMaker Voicebox Adapter 생성
7. 청크 생성 API 연결
8. 청크별 WAV 저장
9. 재생성 버전 V1/V2/V3 저장 및 선택
10. 실제 audio duration 계산
11. 전체 연속 재생
12. 선택 음원 WAV/MP3 병합
13. 실제 duration 기반 SRT 생성
14. 5분 이상 장문 원고 E2E

## 17. 롤백

V1 진입 버튼 연결을 원복할 경우 수정 전 백업의 `index.html`을 기준으로 현재 Diff를 확인한다.

신규 VoiceBox UI 파일은 기존 기능에서 직접 참조하는 파일이 아니므로 문제가 있어도 기존 StoryMaker 제작·Supertonic·Worker에는 영향이 없어야 한다.

삭제나 복원은 사용자 승인 없이 수행하지 않는다.

## 18. Git 상태

현재 이번 작업 파일은 아직 커밋 및 Push하지 않았다.

이번 작업 관련 대상:

- `storymaker-web/backend/app/static/v1/index.html`
- `storymaker-web/backend/app/static/v1/v1-admin-voicebox-entry.js`
- `storymaker-web/backend/app/static/v1/voicebox-studio.html`
- `storymaker-web/backend/app/static/v1/voicebox-studio.css`
- `storymaker-web/backend/app/static/v1/voicebox-studio.js`
- 이 업무일지

기존 저장소의 다른 미추적·미커밋 파일은 이번 작업에서 수정, 삭제, 스테이징하지 않았다.
