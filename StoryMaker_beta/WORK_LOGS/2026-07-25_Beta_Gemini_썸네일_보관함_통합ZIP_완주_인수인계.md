# StoryMaker Beta Gemini 썸네일·보관함 통합 ZIP 완주 업무일지

작성일: 2026-07-25

작업 루트:

`F:\StoryMaker_beta`

V1 접속 주소:

`http://127.0.0.1:8011/v1`

Beta 서버:

`http://127.0.0.1:8021`

Beta 보관함:

`http://127.0.0.1:8021/beta/archive`

---

## 1. 절대 보호 범위

이번 작업에서 아래 대상은 제작 기능 관점에서 수정하지 않았습니다.

- `F:\StoryMaker_V1`의 제작엔진
- V1 DB
- 공용 V2
- 공용 Worker
- 공용 Queue
- 기존 운영 환경
- 기존 브라우저 MP4 엔진
- 기존 TTS·SRT·MP3 생성 흐름

단, V1 대시보드에서 Beta 화면을 여는 연결용 브리지 두 파일은 Beta iframe 캐시 문제 해결을 위해 최소 수정했습니다.

- `F:\StoryMaker_V1\storymaker-web\backend\app\static\v1\v1-beta-menu-bridge.js`
- `F:\StoryMaker_V1\storymaker-web\backend\app\static\v1\index.html`

V1 제작 로직이나 DB에는 영향이 없습니다.

---

## 2. 수정 전 백업

이번 작업 중 확인된 주요 백업은 다음과 같습니다.

### Beta 전체 스냅샷

`F:\v1_backup\V1_BETA0724\SNAPSHOT_20260725_002344`

포함 범위:

- `app`
- `static`
- `data`
- `.venv`
- `Supertonic3`
- `.git`
- SQLite 백업
- SHA-256 manifest

확인 결과:

- Beta 런타임 import 정상
- SQLite 무결성 `ok`
- 주요 폴더 복사 완료

### 보관함 UI·이미지 다운로드 수정 전

`F:\v1_backup\BETA_WORKING_20260725_010000_보관함_UI_이미지다운로드_수정전`

백업 파일:

- `app\beta_browser.py`
- `static\beta-archive-detail-fix-20260724.js`
- `static\archive.html`

### V1 Beta iframe 브리지 수정 전

`F:\v1_backup\V1_BETA_BRIDGE_20260725_012000_보관함캐시수정전`

백업 파일:

- `v1-beta-menu-bridge.js`
- `index.html`

### 보관함 전체 폭·ZIP 파일명 수정 전

`F:\v1_backup\BETA_WORKING_20260725_012400_보관함_전체폭레이아웃_수정전`

백업 파일:

- `static\archive.html`
- `app\beta_image_download.py`

Windows MCP 자체 백업도 각 `edit_file` 작업마다 별도로 생성됐습니다.

---

## 3. Gemini 썸네일 연결 완료

### 기존 상태

첫 Gemini 원고 생성과 SNS 8채널 저장은 정상으로 완료돼 있었습니다.

완료된 항목:

- 첫 Gemini 원고 생성
- 8개 채널 저장
- `thumbnail_prompt.md` 생성
- 썸네일 Queue 등록
- Gemini 썸네일 프롬프트 전달

막힌 항목:

- Gemini가 생성한 이미지 수집
- `output\thumbnail.jpg` 저장
- `result.json` 반영
- 보관함 카드·상세 썸네일 표시

### 발견한 원인

기존 Worker는 Gemini 결과를 아래 기준으로만 찾았습니다.

- 새로 등장한 일반 `img`
- 가로·세로 512px 이상
- 새로운 `src` URL

Gemini 최신 UI에서는 다음 경우를 놓칠 수 있었습니다.

- 기존 이미지 요소의 `src`만 변경
- `srcset` 사용
- Shadow DOM
- `canvas`
- CSS background-image
- `blob:` URL
- 화면상 생성 이미지는 보이지만 URL 재다운로드가 차단되는 경우

### 적용한 Worker 개선

대상 파일:

`F:\StoryMaker_beta\static\storymaker-beta-gemini-worker.user.js`

최종 Worker 버전:

`2.1.10`

설치 주소:

`http://192.168.0.62:8021/beta-static/storymaker-beta-gemini-worker.user.js`

주요 개선:

- Shadow DOM 내부 이미지 탐색
- `img`, `canvas`, `srcset`, CSS 배경 이미지 탐색
- 기존 요소의 URL 변경 감지
- 실제 이미지 크기 평가
- 9:16 세로 비율 우선 점수화
- 같은 후보가 연속 탐지된 후 확정
- 화면에 표시된 이미지 요소를 canvas에 직접 복사
- canvas → JPEG Base64 변환
- URL 방식은 직접 추출 실패 시에만 보조 사용
- `data:image/...;base64` 형식 검증
- 최소 데이터 길이 검증
- 백엔드 저장 성공 응답 확인
- 저장 완료 후 Gemini 새 대화창 자동 전환

새 대화 전환 주소 형식:

`https://gemini.google.com/app?storymaker_beta_thumbnail_done=<timestamp>`

### 백엔드 Worker 버전 통일

대상 파일:

`F:\StoryMaker_beta\app\beta_gemini_worker.py`

적용 내용:

- `REQUIRED_WORKER_ID = "tampermonkey-beta-v2-2.1.10"`
- 허용 Worker 목록에 `2.1.10` 추가

### 최종 성공 확인

사용자 화면에서 아래 흐름을 실제 확인했습니다.

- Gemini 썸네일 생성
- Worker 이미지 수집
- Base64 변환
- Beta 서버 저장
- `thumbnail.jpg` 생성
- `result.json` 반영
- 보관함 카드·상세 표시
- Gemini 새 대화창 전환

---

## 4. 보관함 썸네일 표시 구조

보관함은 별도 DB 썸네일 컬럼보다 `result.json`의 아래 값을 기준으로 표시합니다.

`assets.thumbnail`

썸네일 조회 URL:

`/beta-api/jobs/<job_id>/file/thumbnail`

따라서 `thumbnail/result` API가 다음을 완료하면 보관함에 자동 반영됩니다.

- 이미지 디코딩
- `output\thumbnail.jpg` 저장
- `result.json`의 `assets.thumbnail` 갱신

별도 SQLite 스키마 추가는 하지 않았습니다.

---

## 5. 보관함 하단 UI 개편

수정 파일:

- `F:\StoryMaker_beta\static\archive.html`
- `F:\StoryMaker_beta\static\beta-archive-package-20260725.js`

기존 파일:

`beta-archive-detail-fix-20260724.js`

새 파일을 만든 이유:

V1 인라인 iframe과 브라우저가 기존 정적 JS를 계속 캐시해 새 UI가 보이지 않는 문제가 있었습니다.

캐시를 완전히 분리하기 위해 새 파일명을 사용했습니다.

현재 로드 경로:

`/beta-static/beta-archive-package-20260725.js?v=20260725-package-download-2`

### 최종 하단 구성

보관함 상세 하단에 아래 네 카드가 전체 폭 4열로 표시됩니다.

1. 업로드 이미지
2. 팟캐스트 MP3
3. 썸네일
4. 최종 MP4

각 카드 하단 버튼:

- 가공 이미지 포함 ZIP 다운로드
- MP3 다운로드
- 썸네일 다운로드
- MP4 크게 보기
- MP4 다운로드

네 카드 아래 전체 폭 버튼:

`이미지 · MP3 · SRT · 썸네일 · MP4 전체 ZIP 다운로드`

### 레이아웃 문제와 해결

초기에는 `archive-media-all`은 4열이었지만 부모 `archive-sections`가 2열 그리드여서 하단 영역이 화면 절반만 차지했습니다.

그 결과 전체 ZIP 버튼이 오른쪽 열에 끼어드는 문제가 있었습니다.

해결:

- 부모 영역을 단일 전체 폭으로 강제
- 미디어 카드 영역을 4열로 강제
- 전체 ZIP 버튼을 카드 아래 한 줄 전체 폭으로 고정
- 모바일 폭에서만 2열 또는 1열 전환

사용자 화면에서 최종 성공을 확인했습니다.

---

## 6. V1 인라인 화면 캐시 문제 해결

V1 대시보드의 `보관함 Beta` 메뉴는 iframe으로 아래 주소를 열고 있었습니다.

`http://127.0.0.1:8021/beta/archive`

문제:

- 이미 열린 인라인 패널이 기존 iframe 문서를 유지
- V1 브리지 JS도 이전 캐시 사용
- Beta 서버에서 새 파일을 제공해도 8011 화면에는 이전 UI가 남음

수정 파일:

`F:\StoryMaker_V1\storymaker-web\backend\app\static\v1\v1-beta-menu-bridge.js`

적용 내용:

- Singleton guard V4로 갱신
- iframe을 열 때마다 캐시 키 추가

예:

`http://127.0.0.1:8021/beta/archive?v1_inline_refresh=<timestamp>`

V1 로더 파일:

`F:\StoryMaker_V1\storymaker-web\backend\app\static\v1\index.html`

로더 버전:

`v=20260725-beta-inline-panel-5`

검증:

- 8011에서 새 로더 제공 확인
- V4 브리지 제공 확인
- iframe 캐시 우회 파라미터 확인
- 8021 보관함 HTTP 200

---

## 7. Beta 통합 ZIP 다운로드 기능 신규 개발

V1에는 동일한 보관함 통합 ZIP 기능이 없으므로 Beta에서 새로 구현했습니다.

신규 파일:

`F:\StoryMaker_beta\app\beta_image_download.py`

수정 파일:

`F:\StoryMaker_beta\app\beta_browser.py`

신규 API:

`GET /beta-api/browser/jobs/{beta_job_id}/download-package`

### ZIP 포함 대상

- 업로드 이미지 전체
- 이미지 워터마크·테두리·효과 적용본
- 썸네일
- MP3
- SRT
- MP4

브라우저 생성 MP3·MP4가 있으면 우선 사용합니다.

없을 때만 기존 생성 파일을 사용합니다.

초기 테스트에서 브라우저 MP3와 기존 MP3가 같은 이름으로 중복 포함되는 문제가 있었으며 수정했습니다.

### 이미지 가공 방식

원본 이미지는 절대 수정하지 않습니다.

다운로드 시 별도 캐시 사본에만 아래 효과를 적용합니다.

- EXIF 방향 자동 보정
- 최대 2560px 리사이즈
- 청록색 외곽 테두리
- 노란색 내부 테두리
- 청록색 glow 효과
- 하단 반투명 패널
- 업체명 노란색 워터마크
- 전화번호 흰색 워터마크
- Windows 맑은 고딕 Bold 폰트 사용

폰트 경로:

`C:\Windows\Fonts\malgunbd.ttf`

Pillow 확인 버전:

`12.2.0`

### 캐시 방식

같은 작업의 파일과 메타가 변경되지 않으면 기존 ZIP을 재사용합니다.

캐시 키에 포함되는 항목:

- 패키지 버전
- 콘텐츠 제목
- 업체 정보
- 이미지 경로·크기·수정 시각
- 썸네일
- MP3
- SRT
- MP4

첫 다운로드는 이미지 가공과 압축 때문에 시간이 걸릴 수 있습니다.

두 번째 다운로드부터는 캐시 ZIP을 사용해 빨라집니다.

---

## 8. 최종 ZIP 내부 구조와 파일명 규칙

사용자 최종 요청에 따라 ZIP 내부에는 폴더를 만들지 않습니다.

모든 파일은 ZIP 최상단에 평면으로 저장합니다.

### 이미지 파일명

규칙:

`상호_콘텐츠짧은제목_날짜_일련번호.jpg`

예:

- `오박사만능인테리어_호계동타일융기보수_20260725_001.jpg`
- `오박사만능인테리어_호계동타일융기보수_20260725_002.jpg`

일련번호는 3자리입니다.

### 기타 미디어 파일명

- `상호_콘텐츠짧은제목_날짜_썸네일.jpg`
- `상호_콘텐츠짧은제목_날짜_팟캐스트.mp3`
- `상호_콘텐츠짧은제목_날짜_자막.srt`
- `상호_콘텐츠짧은제목_날짜_최종영상.mp4`

### ZIP 파일명

기본 규칙:

`상호_콘텐츠짧은제목_YYYYMMDD_HHMM_StoryMaker_Beta.zip`

파일명에는 Windows 금지 문자를 제거하고 공백을 `_`로 바꿉니다.

짧은 제목은 과도하게 긴 원문 제목을 줄여 사용하도록 구현했습니다.

### 패키지 버전

최종 ZIP 구조 변경으로 캐시를 분리하기 위해 패키지 버전을 올렸습니다.

`beta-download-package-v3-flat-names`

---

## 9. 다운로드 진행 팝업

보관함에서 전체 ZIP 다운로드 버튼을 누르면 컬러 원 5개가 웨이브처럼 움직이는 팝업이 표시됩니다.

단계:

1. 업로드 이미지 확인
2. 워터마크·테두리·효과 적용
3. MP3·SRT·썸네일·MP4 수집
4. ZIP 압축
5. 브라우저 다운로드 전송

ZIP 응답의 `Content-Length`를 읽을 수 있을 때는 실제 수신량 기준 진행률과 퍼센트를 표시합니다.

완료 시 다운로드 준비 완료 상태로 전환됩니다.

---

## 10. 실제 ZIP 테스트 결과

테스트 작업:

`beta_20260725_005010_50c536`

초기 패키지 테스트:

- 약 11.9MB
- 워터마크 이미지 12장
- 썸네일 1개
- MP3 1개
- SRT 1개
- MP4 1개

중복 MP3 제거 후:

- 약 11.59MB
- 총 16개 파일

구성:

- 워터마크 이미지 12장
- 썸네일 1개
- MP3 1개
- SRT 1개
- MP4 1개

HTTP 응답:

- 상태 200
- `Content-Disposition` UTF-8 파일명 정상

---

## 11. 검증 결과

### Python

- `beta_image_download.py` 문법 검사 통과
- `beta_browser.py` 문법 검사 통과
- Python import 검사 통과

### JavaScript

- `storymaker-beta-gemini-worker.user.js` 문법 검사 통과
- `beta-archive-package-20260725.js` 문법 검사 통과

### Git

- `git diff --check` 통과

### 서비스

- Beta 포트 8021 LISTEN
- Supertonic 포트 7790 LISTEN
- `/beta-api/health` 정상
- `/beta` HTTP 200
- `/beta/archive` HTTP 200
- `/beta/browser-render` HTTP 200

### DB

- `storymaker_beta.db` 존재
- SQLite quick_check `ok`

### 화면

사용자가 최종 화면에서 아래를 직접 확인했습니다.

- 4개 미디어 카드 전체 폭 정렬
- 이미지 12장 표시
- MP3 재생·다운로드
- 썸네일 표시·다운로드
- MP4 표시·크게 보기·다운로드
- 전체 ZIP 다운로드 버튼 하단 전체 폭 배치

---

## 12. 현재 주요 수정 파일

### Beta

- `F:\StoryMaker_beta\app\beta_gemini_worker.py`
- `F:\StoryMaker_beta\app\beta_browser.py`
- `F:\StoryMaker_beta\app\beta_image_download.py`
- `F:\StoryMaker_beta\static\storymaker-beta-gemini-worker.user.js`
- `F:\StoryMaker_beta\static\archive.html`
- `F:\StoryMaker_beta\static\beta-archive-detail-fix-20260724.js`
- `F:\StoryMaker_beta\static\beta-archive-package-20260725.js`

기존 작업에서 함께 변경된 파일이 있을 수 있으므로 다음 채팅에서 Git diff를 반드시 먼저 확인해야 합니다.

### V1 Beta 연결부

- `F:\StoryMaker_V1\storymaker-web\backend\app\static\v1\v1-beta-menu-bridge.js`
- `F:\StoryMaker_V1\storymaker-web\backend\app\static\v1\index.html`

---

## 13. 현재 상태

완료:

- 첫 Gemini 원고 생성
- SNS 8채널 저장
- 썸네일 프롬프트 생성
- 썸네일 Queue 등록
- Gemini 썸네일 생성
- Worker 썸네일 이미지 수집
- `thumbnail.jpg` 저장
- `result.json` 반영
- 보관함 썸네일 표시
- Gemini 새 대화 전환
- 보관함 4열 미디어 UI
- 개별 미디어 다운로드
- 전체 ZIP 다운로드
- 워터마크·테두리·효과 이미지 생성
- ZIP 평면 구조
- 파일명 규칙 적용
- 컬러 웨이브 진행 팝업
- V1 인라인 캐시 우회

남은 핵심 과제:

- 첫 Gemini 프롬프트가 늦게 출발하는 원인 추적
- Queue 등록 → claimed → sent 시각 로그 보강
- 첫 프롬프트 입력창 탐색 시간 단축
- 새 작업 반복 성공 테스트
- 최종 Git diff 검토
- 커밋

---

## 14. 다음 채팅 첫 작업

다음 채팅에서는 이 업무일지를 먼저 읽습니다.

`F:\StoryMaker_beta\WORK_LOGS\2026-07-25_Beta_Gemini_썸네일_보관함_통합ZIP_완주_인수인계.md`

그다음 아래 순서로 진행합니다.

1. `00_READ_FIRST.md` 확인
2. 현재 Git 상태 확인
3. 새 시간 기준 전체 백업
4. 첫 Gemini 프롬프트 지연 재현
5. 작업 생성 시각 확인
6. Queue 등록 시각 확인
7. Worker claimed 시각 확인
8. Worker sent 시각 확인
9. Gemini 입력창 탐색 소요시간 확인
10. 지연 구간만 최소 수정
11. 새 작업 완주 테스트
12. 썸네일·보관함·ZIP 회귀 테스트
13. `check_after_work.ps1` 실행
14. Git diff 검토 후 커밋

---

## 15. 다음 채팅에 전달할 한 줄 요약

StoryMaker Beta는 Gemini 원고·썸네일 생성부터 보관함 저장, 4열 미디어 확인, 워터마크 이미지·MP3·SRT·썸네일·MP4 통합 ZIP 다운로드까지 완주했으며, 다음 작업은 첫 Gemini 프롬프트 출발 지연 원인 추적과 최종 Git 정리입니다.
