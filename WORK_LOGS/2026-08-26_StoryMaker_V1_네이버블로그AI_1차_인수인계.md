# 2026-08-26 StoryMaker V1 네이버 블로그 AI 1차 작업 및 인수인계

## 작업 목적

StoryMaker V1 관리자 화면에 네이버 블로그 자동화 기능을 단계적으로 접목한다.
외부 참고 프로젝트는 `boksajang/blogauto-naver`이며, 통째로 이식하지 않고 StoryMaker 기존 자산을 우선 재활용한다.

관리자 메뉴 명칭은 사용자 요청에 따라 정확히 `네이버 블로그 AI`로 정했다.
메뉴 위치는 V1 좌측 사이드바의 `보관함` 바로 아래이며 관리자에게만 노출한다.

AI 처리부는 사무실 Hermes의 구조를 참고하되 StoryMaker 쪽 모델은 `ChatGPT Luna`를 사용하는 방향으로 설계한다.

## 2026-08-26 1차 구현 완료 내용

### 1. 관리자 전용 메뉴 브리지 추가

신규 파일:

- `storymaker-web/backend/app/static/v1/v1-admin-naver-blog-ai-entry.js`

주요 동작:

- `/v1-api/auth/me`를 통해 관리자 여부 확인
- 관리자일 때만 `네이버 블로그 AI` 메뉴 생성
- `보관함` 메뉴 바로 아래 삽입
- 기존 `StoryMakerV1InlinePanels`를 재활용하여 새 창이 아니라 V1 대시보드 내부에서 화면 표시
- 관리자 권한이 아니면 메뉴 제거

### 2. 네이버 블로그 AI 껍데기 화면 추가

신규 파일:

- `storymaker-web/backend/app/static/v1/naver-blog-ai.html`

1차 화면의 목적은 실제 자동발행을 바로 실행하는 것이 아니라 향후 기능을 안전하게 붙일 작업 공간을 만드는 것이다.

화면의 기본 파이프라인:

1. StoryMaker 기존 원고/프로젝트 자산
2. ChatGPT Luna 검수·보정
3. 이미지·태그 정리
4. 발행 미리보기
5. 네이버 발행
6. 발행 결과 및 작업 로그

기존 네이버 블로그 관련 기능은 새로 만들지 않고 기존 `naver-blog-copy.html` 및 관련 JS/CSS를 우선 재활용하는 방향으로 구성했다.

### 3. V1 진입부 연결

수정 파일:

- `storymaker-web/backend/app/static/v1/index.html`

신규 관리자 메뉴 브리지 JS를 로드하도록 최소 변경했다.

## GitHub 반영 상태

관련 구현은 `kim6410/dell_V1_StoryMaker` main 브랜치에 반영했다.

1차 구현 과정에서 확인된 마지막 기능 커밋:

- `70764b62f011028a32ab000bd6034f8e15763f73`

이번 업무일지 추가 커밋은 별도로 생성된다.

## 기존 StoryMaker에서 재활용할 자산

확인된 기존 자산:

- `storymaker-web/backend/app/static/naver-blog-copy.html`
- `naver_blog_copy.js`
- `naver_blog_copy.css`
- 기존 프로젝트/보관함 데이터
- 프로젝트 이미지·MP4·썸네일 자산
- 기존 네이버 크롤러/스크래퍼/블로그 포매터 계열 백엔드 기능
- `v1-inline-panel-host.js`
- 기존 관리자 권한 판별 패턴

`naver-blog-copy.html`에는 이미 다음 기능이 존재하므로 우선 재활용한다.

- StoryMaker 프로젝트 선택/불러오기
- 업체명/전화번호/핵심 키워드
- 글 목적 및 추가 상황
- 프로젝트 이미지·MP4·썸네일
- 추천 제목
- 대표 제목
- 블로그 본문
- 이미지 앵커/ALT
- 해시태그
- 네이버 블로그 미리보기
- 워드프레스 변환
- 인스타 릴스 패키지

## boksajang/blogauto-naver 1차 분석

저장소는 Electron + JavaScript + Playwright 기반 로컬 Windows 프로그램이다.

주요 파일:

- `src/lib/accountStore.js` — 네이버 계정/프로필 관리
- `src/lib/codexRunner.js` — 멀티 에이전트 실행
- `src/lib/search.js` — 검색 및 근거 수집/판정
- `src/lib/imageAssets.js` — 이미지 자산 처리
- `src/lib/naverPublisher.js` — 네이버 블로그 브라우저 자동발행
- `src/lib/tistoryPublisher.js` — 티스토리 발행
- `src/main.js` — Electron 메인 프로세스

### naverPublisher.js에서 참고 가치가 높은 부분

- Chrome 실제 프로필 기반 로그인 세션 유지
- 네이버 ID와 블로그 ID 분리 대응
- 블로그 ID 기반 `/postwrite` 진입
- 세션 만료를 `SESSION_EXPIRED`로 별도 처리
- 페이지 이동 중 `ERR_ABORTED`, frame detach 등 복구 처리
- iframe을 포함한 실제 네이버 에디터 입력 영역 탐색
- `keyboard.type()` 지연을 이용한 사람에 가까운 입력
- 기존 임시글/팝업 간섭 처리
- Chrome 비정상 종료 프로필 복구 처리

이 부분은 StoryMaker의 실제 자동발행 Agent를 만들 때 적극 참고한다.

### 그대로 가져오지 않을 부분

`codexRunner.js` 전체를 StoryMaker에 이식하는 것은 우선순위가 낮다.
StoryMaker에는 이미 콘텐츠 생성 엔진이 존재하며 AI 처리부는 Hermes 구조를 참고한 `ChatGPT Luna` 기반으로 구성한다.

Electron UI 전체도 StoryMaker V1에 이식하지 않는다.
StoryMaker는 웹 대시보드를 유지하고 실제 브라우저 발행 실행기만 Windows Publishing Agent로 분리하는 방향이 적합하다.

## 목표 아키텍처

```text
StoryMaker 기존 원고/이미지
        ↓
네이버 블로그 AI
        ↓
ChatGPT Luna
사실·과장·SEO·문체 검수
        ↓
최종 미리보기
        ↓
발행 대기 Queue
        ↓
Windows Publishing Agent
        ↓
Chrome + Playwright
        ↓
네이버 블로그
        ↓
발행 결과/로그 → StoryMaker
```

콘텐츠 생성과 관리 UI는 Dell StoryMaker 서버가 담당하고, 네이버 로그인 세션과 실제 Chrome 자동화는 Windows 환경에서 담당하는 구조를 우선 검토한다.

## 현재 미완료 — 다음 작업 최우선

### 1. Dell 운영 서버 배포

현재 GitHub 반영까지 완료했지만 이 채팅 세션에는 기존 `dell-direct / SSH MCP` 실행 연결이 노출되지 않아 운영 서버 배포는 수행하지 못했다.

따라서 다음 작업 시작 시 가장 먼저 Dell 서버 연결 상태를 확인한다.

배포 대상은 정확히 다음 3개 변경으로 제한한다.

- `storymaker-web/backend/app/static/v1/naver-blog-ai.html`
- `storymaker-web/backend/app/static/v1/v1-admin-naver-blog-ai-entry.js`
- `storymaker-web/backend/app/static/v1/index.html`

배포 전 반드시:

1. 서버 작업 경로의 `00_READ_FIRST.md` 확인
2. `git status` 확인
3. 다른 세션의 미커밋 작업 존재 여부 확인
4. 최신 GitHub main과 서버 HEAD 비교
5. 기존 운영 파일 보호/백업 규칙 확인

삭제, `git reset --hard`, `git clean`, 일괄 덮어쓰기는 금지한다.

배포 후 확인:

- `https://app.mystorymaker.net/v1/` 정상 응답
- 관리자 로그인 시 `보관함` 바로 아래 `네이버 블로그 AI` 표시
- 일반 사용자에게 메뉴가 보이지 않는지 확인
- 메뉴 클릭 시 V1 내부 패널에서 `naver-blog-ai.html` 정상 표시
- 기존 대시보드/새 콘텐츠 제작/보관함 회귀 테스트

### 2. blogauto-naver 상세 분석 계속

다음 순서 권장:

1. `accountStore.js`
2. `search.js`
3. `codexRunner.js`에서 프롬프트/검수 루프만 선별 분석
4. `naverPublisher.js` 전체 발행 단계 분석
5. `imageAssets.js`
6. `tistoryPublisher.js`

분석 결과는 반드시 다음 세 분류로 기록한다.

- StoryMaker 기존 기능 재활용
- 구조/아이디어만 참고하여 재구현
- 불필요하여 제외

### 3. 2차 UI 기능

운영 껍데기 확인 후 다음 기능을 순차 추가한다.

- 네이버 계정 관리
- 계정별 블로그 ID/카테고리/Chrome 프로필
- StoryMaker 보관함 원고 선택
- Luna 검수 버튼
- 사실/과장/SEO/문체 검수 결과 표시
- 발행 대기 Queue
- 공개/비공개/예약 발행 옵션
- 발행 로그

실제 네이버 자동발행 버튼은 Publishing Agent와 세션 안전장치가 준비되기 전까지 활성화하지 않는다.

## 라이선스 주의

`boksajang/blogauto-naver`는 공개 저장소이지만 1차 확인 당시 명시적인 라이선스가 확인되지 않았다.
따라서 상업 서비스인 StoryMaker에 원본 코드를 대량 복사하여 포함하지 않는다.

우선 원칙:

- StoryMaker 기존 코드를 최대한 재활용
- 공개 프로젝트의 구조와 동작 아이디어를 분석
- 필요한 부분은 StoryMaker 코드로 재구현
- 라이선스/사용 허가가 명확해지기 전 원본 코드 직접 이식 최소화

## 다음 작업자에게

내일 작업 시작 시 새로운 기능부터 만들지 말고 Dell 운영 배포와 실제 관리자 화면 검증을 가장 먼저 끝낸다.

운영 화면이 정상임을 확인한 뒤 `accountStore.js`와 `naverPublisher.js`를 중심으로 Publishing Agent 설계를 계속한다.

이번 단계의 핵심 목표는 '완전 자동발행을 빨리 만드는 것'이 아니라 StoryMaker의 기존 생성/보관함 자산을 살리면서 네이버 발행 기능을 안전하게 붙이는 것이다.
