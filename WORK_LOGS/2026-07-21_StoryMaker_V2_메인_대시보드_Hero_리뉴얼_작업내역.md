# StoryMaker V2 메인 대시보드 Hero 리뉴얼 작업내역

작성일: 2026-07-21

## 1. 작업 목표

V2 로그인 후 첫 화면을 기존 관리형 대시보드가 아니라, 사용자가 바로 제작을 시작할 수 있는 런처형 Hero 화면으로 변경하는 작업입니다.

이번 작업은 기존 제작 기능을 새로 만들거나 React 원본을 수정하는 방식이 아닙니다.

운영 중인 V2 화면 위에 브리지 JavaScript와 동적 CSS를 적용하여 Hero 영역만 교체하는 방식으로 진행했습니다.

핵심 목표는 로그인 직후 사용자가 가장 먼저 아래 두 가지 행동을 선택하도록 만드는 것입니다.

- 일괄 제작(딸깍)
- 단계별 제작

기존 날씨, 최근 생성, 업체, 연구실, 통계 카드 등은 삭제하지 않고 Hero 아래에 그대로 유지하는 방향입니다.

## 2. 확정된 디자인 방향

사용자가 가장 만족한 시안을 기준으로 아래 구성을 확정했습니다.

배경 이미지 구성:

- 바다
- 노트북
- 아이스커피
- 여름 분위기의 밝고 시원한 이미지

레이아웃:

- 좌측: 텍스트와 CTA 버튼 2개
- 우측: 바다, 노트북, 아이스커피가 보이는 이미지 영역
- 텍스트는 좌측 정렬
- Hero는 큰 카드 형태
- 기존 좌측 메뉴는 그대로 유지

Hero 문구:

- 3분이면
- SNS 콘텐츠 완성
- 사진 몇 장으로 블로그, 쇼츠, 팟캐스트까지 한 번에!

CTA 버튼:

- 일괄 제작(딸깍)
- 단계별 제작

제거 대상:

- 로켓 아이콘
- 추가 CTA 버튼
- 기존 대시보드 제목
- 대시보드로 돌아가기 문구
- 기존 “오늘 만들 콘텐츠와 업체 상태...” 카드

## 3. 수정한 운영 파일

실제 수정 파일:

`/home/bourne/StoryMaker/storymaker-web/backend/app/static/v2/v2-dashboard-summer-hero.js`

Windows 공유 경로 기준:

`\\192.168.0.32\StoryMaker\storymaker-web\backend\app\static\v2\v2-dashboard-summer-hero.js`

주의:

이번 작업 파일은 `StoryMaker_1`이 아니라 운영 V2 경로인 `StoryMaker` 아래에 있습니다.

작업 인수인계 문서만 사용자가 지정한 아래 경로에 저장합니다.

`/home/bourne/StoryMaker_1/WORK_LOGS`

## 4. 구현 방식

브리지 JS가 기존 V2 대시보드 DOM이 나타날 때까지 대기한 뒤, 기존 대시보드 소개 카드를 찾아 그 앞에 Hero section을 삽입하는 구조입니다.

기존 소개 카드는 삭제하지 않고 다음 방식으로 숨깁니다.

```javascript
dashboardCard.style.display = 'none';
```

따라서 React 원본이나 기존 대시보드 데이터 구조를 건드리지 않습니다.

Hero가 중복 삽입되지 않도록 전역 플래그와 고정 ID를 사용합니다.

주요 식별자:

```javascript
window.__STORYMAKER_V2_SUMMER_HERO__
```

```javascript
const HERO_ID = 'storymaker-v2-summer-hero';
```

DOM 로딩이 늦는 경우를 대비해 다음 두 방식을 함께 사용합니다.

- 250ms 간격 재시도
- MutationObserver

## 5. Hero 이미지

현재 Hero 배경은 외부 Pexels 이미지 URL을 사용합니다.

코드 내 상수:

```javascript
const IMAGE_URL = 'https://images.pexels.com/photos/11352221/pexels-photo-11352221.jpeg?auto=compress&cs=tinysrgb&w=1800';
```

현재 화면에서 바다, 테이블, 아이스커피가 보이며 좌측에는 밝은 흰색 오버레이가 적용됩니다.

오버레이 목적:

- 배경 위 텍스트 가독성 확보
- 좌측 CTA 영역 강조
- 우측 바다 이미지 보존

## 6. 텍스트 배치 수정 과정

초기 상태에서는 제목이 화면 폭에 따라 다음처럼 비정상적으로 줄바꿈됐습니다.

- SNS 콘텐츠 완
- 성

이후 제목을 두 줄로 고정하는 시도를 했으나 사용자가 “SNS 콘텐츠 완성” 전체를 한 줄로 표시해 달라고 요청했습니다.

최종적으로 제목 HTML은 아래 구조로 정리했습니다.

```html
<h1 class="sm-summer-title"><span>SNS</span> 콘텐츠 완성</h1>
```

그리고 제목 전체에 줄바꿈 방지 속성을 적용했습니다.

핵심 CSS:

```css
.sm-summer-title {
    white-space: nowrap;
    word-break: keep-all;
}
```

텍스트 영역 폭도 기존보다 넓혀 한 줄을 유지하도록 조정했습니다.

현재 사용자 확인 결과:

- “SNS 콘텐츠 완성” 한 줄 표시 정상
- 최종 화면에서 줄바꿈 문제 해결 확인

## 7. 현재 Hero 스타일 핵심

Hero 카드:

- 큰 라운드 카드
- 바다 이미지 cover
- 좌측 밝은 그라데이션 오버레이
- 하단 어두운 그라데이션
- 얇은 청록색 테두리
- 그림자 적용

Hero 내부 텍스트 영역:

- 세로 중앙 정렬
- 좌측 정렬
- 제목 한 줄 고정
- 화면 폭에 따라 clamp 기반 폰트 크기 사용

제목 색상:

- `SNS` 부분은 파랑 계열 그라데이션
- `콘텐츠 완성`은 짙은 네이비

설명 문구:

- 블로그, 쇼츠, 팟캐스트 부분을 파란색 강조

버튼:

- 일괄 제작은 파랑·보라 그라데이션
- 단계별 제작은 흰색 반투명 스타일
- hover 시 살짝 위로 이동 및 밝기 증가

## 8. 일괄 제작 버튼 링크 수정

초기 버튼 동작은 fallback 주소만 사용하는 형태였고, 실제 좌측 메뉴 텍스트에 `HOT`가 붙어 있어 정확히 일치하지 않을 가능성이 있었습니다.

기존 좌측 메뉴는 화면상 다음처럼 표시됩니다.

`딸깍 제작 HOT`

따라서 버튼 검색 로직을 다음처럼 보강했습니다.

- Hero 내부 버튼은 검색 대상에서 제외
- 텍스트가 정확히 일치하는 요소 우선
- 정확히 일치하지 않으면 해당 텍스트로 시작하는 요소 검색

핵심 로직:

```javascript
const candidates = [...document.querySelectorAll('button,a,[role="button"]')]
  .filter((el) => !el.closest(`#${HERO_ID}`));

return candidates.find((el) => normalize(el.textContent) === text)
  || candidates.find((el) => normalize(el.textContent).startsWith(text));
```

일괄 제작 버튼 클릭 시:

1. 좌측 기존 `딸깍 제작` 메뉴를 찾아 실제 클릭
2. 메뉴를 찾지 못하면 fallback 주소로 이동

fallback:

```text
/v2?view=one-shot
```

단계별 제작 버튼 클릭 시:

1. 좌측 기존 `단계별 제작` 메뉴를 찾아 실제 클릭
2. 메뉴를 찾지 못하면 fallback 주소로 이동

fallback:

```text
/storymaker?embed=1
```

현재 수정 결과:

- Hero 버튼이 자기 자신을 다시 찾는 문제 방지
- 좌측 메뉴의 `HOT` 문구가 있어도 `딸깍 제작` 시작 문자열로 정상 탐색
- 일괄 제작 버튼 링크 보강 완료

## 9. 이번 작업 중 생성된 자동 백업

MCP의 `workspace_file_patch_replace`를 사용했고, 각 수정 전 자동 백업이 생성됐습니다.

확인된 백업 경로:

```text
/workspace/AI_Server/backup/mcp_workspace_file_backups/20260720_201011/StoryMaker__storymaker-web__backend__app__static__v2__v2-dashboard-summer-hero.js
```

```text
/workspace/AI_Server/backup/mcp_workspace_file_backups/20260720_201027/StoryMaker__storymaker-web__backend__app__static__v2__v2-dashboard-summer-hero.js
```

```text
/workspace/AI_Server/backup/mcp_workspace_file_backups/20260720_201036/StoryMaker__storymaker-web__backend__app__static__v2__v2-dashboard-summer-hero.js
```

```text
/workspace/AI_Server/backup/mcp_workspace_file_backups/20260720_201043/StoryMaker__storymaker-web__backend__app__static__v2__v2-dashboard-summer-hero.js
```

```text
/workspace/AI_Server/backup/mcp_workspace_file_backups/20260720_201153/StoryMaker__storymaker-web__backend__app__static__v2__v2-dashboard-summer-hero.js
```

```text
/workspace/AI_Server/backup/mcp_workspace_file_backups/20260720_201308/StoryMaker__storymaker-web__backend__app__static__v2__v2-dashboard-summer-hero.js
```

```text
/workspace/AI_Server/backup/mcp_workspace_file_backups/20260720_201316/StoryMaker__storymaker-web__backend__app__static__v2__v2-dashboard-summer-hero.js
```

각 백업은 수정 단계별 상태를 포함하므로, 문제가 생기면 가장 최근 정상 단계 또는 필요한 시점으로 되돌릴 수 있습니다.

## 10. 절대 수정 금지 원칙

이번 작업에서 아래 항목은 수정하지 않았습니다.

- 기존 제작 엔진
- 기존 API
- Queue
- Worker
- FFmpeg
- React 원본
- `/home/bourne/storymaker-v2-app`
- 기존 딸깍 제작 로직
- 기존 단계별 제작 로직
- DB 구조
- 로그인 및 인증 흐름

이번 작업은 운영 static V2에 추가된 Hero 브리지 JS 한 파일만 수정했습니다.

## 11. 현재 최종 상태

사용자 화면 확인 기준:

- Hero 카드 정상 표시
- 바다 배경 정상 표시
- 좌측 밝은 오버레이 정상
- “3분이면” 정상 표시
- “SNS 콘텐츠 완성” 한 줄 표시 정상
- 설명 문구 정상 표시
- 일괄 제작 버튼 정상 표시
- 단계별 제작 버튼 정상 표시
- 기존 좌측 메뉴 유지
- 기존 실시간 날씨 영역 유지
- 기존 하단 카드 영역은 Hero 아래 구조로 유지

사용자가 최종적으로 “오케이 되었어”라고 확인했습니다.

## 12. 다음 작업 시 우선 확인할 사항

다음 채팅에서 작업을 이어갈 경우 먼저 아래 순서로 확인합니다.

1. 브라우저 강력 새로고침 후 Hero 유지 여부 확인

```text
Ctrl + F5
```

2. 일괄 제작 버튼 실제 클릭 테스트

- 클릭 후 기존 딸깍 제작 화면이 열리는지 확인
- 좌측 메뉴 선택 상태가 정상 반영되는지 확인

3. 단계별 제작 버튼 실제 클릭 테스트

- 기존 단계별 제작 화면이 정상 열리는지 확인
- iframe 또는 embed 흐름이 기존과 동일한지 확인

4. 화면 폭별 반응형 확인

- 1920px PC
- 1600px PC
- 1366px 노트북
- 모바일 또는 좁은 브라우저

현재 제목은 PC 화면에서 한 줄 고정을 우선 적용했습니다.

좁은 모바일 화면에서는 한 줄 고정으로 인해 화면 밖으로 넘칠 수 있으므로, 모바일 대응 시에는 별도의 작은 폰트 크기 또는 모바일 전용 줄바꿈 규칙을 추가하는 편이 안전합니다.

5. Hero 이미지 외부 URL 안정성 검토

현재 Pexels 외부 이미지를 직접 불러옵니다.

장기 운영 시에는 아래 방식이 더 안전합니다.

- 이미지를 운영 static/v2/assets 아래에 로컬 저장
- 브리지 JS에서 로컬 경로 사용
- 외부 이미지 삭제, URL 변경, 속도 저하에 대비

단, 이미지 로컬 저장 작업은 현재 하지 않았습니다.

## 13. 향후 개선 후보

현재 기능상 필수는 아니며, 다음 단계에서 선택적으로 적용할 수 있습니다.

- Hero 이미지 로컬 자산화
- 텍스트 등장 애니메이션
- 버튼 hover 효과 정교화
- Hero 높이 반응형 보정
- Hero와 하단 카드 사이 간격 조정
- 최근 생성 카드 디자인 톤 통일
- 업체 카드와 연구실 카드의 색상 체계 통일
- 모바일 전용 Hero 레이아웃

주의:

추가 개선을 하더라도 React 원본을 수정하거나 새 빌드를 진행하지 말고, 현재 브리지 방식 안에서 최소 수정하는 것이 이번 작업 원칙에 맞습니다.

## 14. 핵심 인수인계 한 줄

현재 운영 V2 메인 대시보드는 `v2-dashboard-summer-hero.js` 브리지로 여름 바다 Hero 런처가 적용됐고, 제목 한 줄 표시와 일괄 제작 메뉴 연결 보강까지 완료된 정상 상태입니다.
