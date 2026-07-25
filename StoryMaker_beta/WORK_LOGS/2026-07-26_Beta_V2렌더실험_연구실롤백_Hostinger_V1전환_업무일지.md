# StoryMaker 업무일지

작성일: 2026-07-26

## 1. 작업 범위

오늘 작업은 다음 세 영역으로 나뉘어 진행했습니다.

1. StoryMaker Beta의 브라우저 렌더링 속도 개선 실험
2. V1 AI 연구실의 V2 전체 렌더러 독립 이식 실험 및 원복
3. Hostinger 운영 홈페이지의 V2 연결을 V1 대시보드로 전환

Dell Beta 작업 루트:

```text
/home/bourne/StoryMaker_1/StoryMaker_beta
```

V1 외부 접속 주소:

```text
https://app.mystorymaker.net/v1
```

Hostinger 운영 홈페이지:

```text
https://mystorymaker.net/
```

---

## 2. Beta 정상 기준점

오늘 작업 전 기준으로 확인한 정상 상태는 다음과 같습니다.

```text
WebGPU 브라우저 TTS
→ 서버 음악 믹싱
→ WebCodecs MP4 제작
→ 브라우저 렌더 완료 즉시 서버 업로드
→ 보관함 자동 저장
```

정상 기준 백업:

```text
/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260726_061123_BETA_속도_정상화_완주본
```

정상 기준 Git 커밋:

```text
1c3854af9b341e007e3e33f20c6a16e115be8c13
```

커밋 메시지:

```text
fix(beta): normalize WebGPU render speed and archive flow
```

확인된 정상 작업:

```text
beta_20260726_060252_6c6403
```

---

## 3. V2 브라우저 오디오 파이프라인 이식 실험

### 목적

V2에서 사용 중인 브라우저 오디오 혼합 방식을 Beta에 이식하여 Dell 서버 CPU 사용량과 서버 왕복 시간을 줄이려 했습니다.

### 적용했던 내용

다음 파일에 V2 방식의 브라우저 오디오 혼합과 실시간 Canvas 미리보기를 적용했습니다.

```text
static/beta-browser-render.js
static/beta-shortform-inline.js
static/production.html
app/beta_shortform.py
```

수정 전 백업:

```text
/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260726_063649_V2_고속_브라우저_파이프라인_이식전
```

주요 실험 내용:

```text
브라우저 WebGPU TTS 결과 유지
브라우저에서 BGM 다운로드
브라우저 AudioBuffer 기반 음성+BGM 혼합
혼합 WAV Blob 생성
MP3 인코딩과 MP4 렌더 병렬 실행
실제 WebCodecs Canvas 프레임 미리보기
서버 prepare-audio 자동 폴백 유지
```

### 실험 결과

Dell 서버 CPU 사용량은 거의 증가하지 않았습니다.

따라서 오디오 작업이 서버에서 브라우저로 이동한 것은 확인됐습니다.

그러나 전체 제작 속도는 크게 빨라지지 않았고, 최종적으로 렌더 흐름이 멈추는 실패가 발생했습니다.

판단된 원인:

```text
V2는 일체형 파이프라인
Beta는 단계형·manifest 기반 파이프라인
브라우저 메모리 AudioBuffer와 서버 manifest 상태가 혼재
MP3 저장과 MP4 렌더 병렬 실행이 기존 순차 상태 관리와 충돌
보관함 저장 및 완료 이벤트가 일부 단계 완료를 기다리며 정지
```

### 조치

V2 이식 실험 전체를 수정 전 백업으로 롤백했습니다.

복원 후 네 파일의 SHA-256이 백업본과 일치함을 확인했습니다.

복원 상태:

```text
storymaker-beta.service active
Beta 제작 화면 HTTP 200
렌더 JavaScript HTTP 200
Git 대상 파일 clean
```

최종 결론:

```text
오디오 브라우저 이식만으로는 큰 속도 향상이 없음
실제 병목은 Canvas 프레임 생성과 H.264/AAC 인코딩 구간
V2 전체 파이프라인을 별도 실험 환경에서 검증한 뒤 합쳐야 함
현재 Beta 정상본은 유지
```

---

## 4. V1 AI 연구실 V2 전체 렌더러 이식 실험

### 목적

V2 전체 브라우저 렌더러를 V1의 AI 연구실 1에서 다른 기능과 연관되지 않도록 독립 실행하려 했습니다.

실제 확인된 고정 자산:

```text
BrowserMp4TestPage-CmPBgwv3.js
index-_LPoLVC5.js
browserPodcast.worker-nPEw1MVN.js
```

전체 렌더러 직접 실행 주소:

```text
/v1/?browser_mp4_test=1
```

### 첫 번째 독립화 시도

연구실 전용 페이지를 만들고 그 안에 전체 렌더러를 iframe으로 넣었습니다.

생성했던 파일:

```text
storymaker-web/backend/app/static/v1/ai-lab/index.html
```

수정했던 파일:

```text
storymaker-web/backend/app/static/v1/v1-dashboard-inline-labs.js
storymaker-web/backend/app/static/v1/experience-lab-route-bridge.js
storymaker-web/backend/app/static/v1/index.html
```

수정 전 백업:

```text
/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260726_065218_AI연구실_독립실행_수정전
```

### 발생한 문제

1차 구조가 다음처럼 iframe 두 겹이 되었습니다.

```text
V1 대시보드
→ 연구실 iframe
→ ai-lab/index.html
→ V1 전체 앱 iframe
```

렌더 번들과 Worker는 HTTP 200으로 정상 로드됐지만 화면이 빈 상태가 됐습니다.

중간 iframe을 제거하고 직접 연결하자 화면이 잠깐 나타났다가 부모 React 화면에 다시 덮였습니다.

최상단 fixed 레이어로 올리는 실험도 했지만 연구실이 전체 화면을 덮어 사용자 요구와 맞지 않았습니다.

### 최종 조치

사용자 요청에 따라 연구실 관련 작업을 전부 최초 상태로 롤백했습니다.

복원 기준:

```text
/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260726_065218_AI연구실_독립실행_수정전
```

복원한 파일:

```text
static/v1/v1-dashboard-inline-labs.js
static/v1/experience-lab-route-bridge.js
static/v1/index.html
```

삭제한 실험 파일:

```text
static/v1/ai-lab/index.html
```

복원 후 해시:

```text
v1-dashboard-inline-labs.js
3fc04f93fa4b3295daf7fa6d527514ecddb52a229323e477556392bbd774e4be

experience-lab-route-bridge.js
c8b6f07d0ca66d959253964a87fe43b1076f29c155ad31dbf37f1ce101d0a158

index.html
a090da1291eddb450aa7010a72784ed9f866f9e9a59c72bdf4e51d525bc0ff44
```

현재 연구실 기준 주소:

```text
/v1/?page=experienceLab&inline_lab_frame=1
```

복원 검증:

```text
연구실 화면 HTTP 200
연구실 연결 스크립트 HTTP 200
라우트 브리지 HTTP 200
백업본과 SHA-256 일치
```

최종 결론:

```text
연구실은 기존의 단순하고 잘 보이는 상태로 복원
V2 전체 렌더러 이식은 별도 독립 페이지 또는 별도 앱으로 다시 설계 필요
기존 V1 연구실 UI는 현재 상태를 유지
```

---

## 5. Hostinger 홈페이지 V2 → V1 연결 전환

### 목적

Hostinger의 `mystorymaker.net` 주요 버튼과 메뉴가 V2가 아닌 V1 대시보드 첫 화면으로 이동하도록 변경했습니다.

최종 목적지:

```text
https://app.mystorymaker.net/v1
```

기존에는 다음과 같은 다양한 V2 링크가 존재했습니다.

```text
https://app.mystorymaker.net/v2
https://app.mystorymaker.net/v2?page=workpanel
https://app.mystorymaker.net/v2?page=write
https://app.mystorymaker.net/v2?page=podcast
https://app.mystorymaker.net/v2?page=shortform
```

모든 링크를 쿼리 없이 V1 대시보드 첫 화면으로 통일했습니다.

### 수정 대상

Hostinger 테마 경로:

```text
~/domains/mystorymaker.net/public_html/wp-content/themes/storymaker-theme
```

수정 파일:

```text
page-about.php
page-slideshow.php
page-podcast.php
front-page.php
header.php
page-inquiry.php
page-services.php
page-guide.php
page-faq.php
```

수정 전 백업:

```text
/home/u161311303/domains/mystorymaker.net/public_html/_manual_backups/all_v2_links_to_v1_dashboard_20260725_223658
```

### 최종 링크 상태

다음 메뉴 및 버튼이 모두 V1 첫 화면으로 연결됩니다.

```text
SNS AI Studio 로고
앱바로가기
스토리 메이커 바로가기
스토리 메이커 지금 체험하기
SlideShow 가이드 활용하기
Podcast 대본 및 오디오 생성하기
사진으로 숏폼 생성하기
공짜 SNS 작성
StoryMaker 시작하기
AI 제작 도구 확인하기
스토리 메이커 웹앱 바로 시작하기
StoryMaker 바로 기동하기
무료로 시작하기
궁금증 해결 무료 체험 시작하기
```

### 검증 결과

```text
활성 파일의 V2 링크 없음
V1 링크 뒤의 ?page= 쿼리 없음
9개 PHP 파일 문법 검사 전부 통과
WordPress 캐시 flush 성공
LiteSpeed 전체 캐시 삭제 성공
실제 홈페이지 버튼 V1 연결 성공
```

확인 메시지:

```text
Success: The cache was flushed.
Success: 모두 삭제되었습니다!
```

최종 사용자 검증:

```text
연결 성공
```

---

## 6. 현재 최종 상태

### Beta

```text
V2 오디오 파이프라인 실험은 실패 후 완전 롤백
기존 WebGPU TTS + 서버 음악 믹싱 + WebCodecs MP4 정상본 유지
```

### V1 AI 연구실

```text
V2 전체 렌더러 독립 이식 실험은 완전 롤백
기존 단순하고 잘 보이는 연구실 상태 유지
```

### Hostinger 운영 홈페이지

```text
mystorymaker.net 주요 앱 링크
→ https://app.mystorymaker.net/v1
→ V1 대시보드 첫 화면
```

### Git

오늘의 실험 및 롤백과 Hostinger 변경에 대해 추가 Git 커밋이나 push는 수행하지 않았습니다.

---

## 7. 다음 작업 권장 순서

1. 현재 Beta 정상 상태를 유지합니다.
2. V2 렌더러 이식은 기존 연구실 안이 아닌 완전히 별도 정적 페이지 또는 별도 앱 엔트리로 구현합니다.
3. V2 전체 렌더러의 React 공용 번들 의존성을 제거하거나 독립 빌드를 생성합니다.
4. 전체 제작 속도 최적화는 오디오보다 프레임 수, FPS, 이미지 디코딩, Canvas 합성 비용을 우선 측정합니다.
5. Hostinger V1 연결은 현재 상태를 유지하고, 필요할 때 백업 폴더로 즉시 복원합니다.

---

## 8. 다음 채팅 시작 기준

다음 채팅에서는 먼저 아래 업무일지를 확인합니다.

```text
/home/bourne/StoryMaker_1/StoryMaker_beta/WORK_LOGS/2026-07-26_Beta_V2렌더실험_연구실롤백_Hostinger_V1전환_업무일지.md
```

절대 유지 기준:

```text
현재 Beta 정상본 보호
V1 AI 연구실 기존 표시 상태 보호
Hostinger 주요 링크는 V1 대시보드 첫 화면 유지
수정 전 백업 필수
전체 파일 덮어쓰기 금지
Git commit/push는 사용자 승인 후 진행
```
