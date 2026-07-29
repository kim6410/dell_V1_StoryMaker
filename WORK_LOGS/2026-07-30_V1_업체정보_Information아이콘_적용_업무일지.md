# 2026-07-30 V1 업체 정보 Information 아이콘 적용 업무일지

## 작업 목적

V1 좌측 메뉴의 `업체 정보` 앞에 새 콘텐츠 제작·보관함과 어울리는 선형 Information 아이콘을 추가한다.

## 사용자 요청

- 업체 정보 메뉴 앞에 멋진 Information 아이콘 연결
- 기존 정상 메뉴와 Beta 메뉴 구조 유지
- 중복 아이콘 방지

## 작업 전 기준

- 기준 커밋: `f10905422dbaf980662cbc3c71167ad8669db145`
- 이전 타임머신 태그: `v1-menu-before-icon-source-20260730-0006`
- V1 주소: `http://127.0.0.1:8011/v1/`

## 수정 파일

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/v1-beta-independent-menu.js`

## 백업

MCP 자동 백업:

- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260729_151433/StoryMaker_1__storymaker-web__backend__app__static__v1__v1-beta-independent-menu.js`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260729_151448/StoryMaker_1__storymaker-web__backend__app__static__v1__v1-beta-independent-menu.js`

## 구현 내용

- 원형 테두리 안에 소문자 i 형태가 들어간 20×20 선형 SVG 아이콘 추가
- 업체 정보 버튼을 찾았을 때 아이콘을 텍스트 앞에 삽입
- `.storymaker-company-info-menu-icon` 존재 여부로 중복 삽입 차단
- 버튼에 `flex`, `items-center`, `gap-3` 정렬 적용
- 아이콘 색상은 기존 Beta 메뉴와 맞춘 cyan 계열 사용
- `aria-hidden=true`로 장식 아이콘 접근성 처리

## 영향 범위

- V1 좌측 메뉴의 업체 정보 표시만 변경
- 업체 정보 클릭 기능과 라우팅은 유지
- DB, 인증, 구독, 콘텐츠 생성, 음성, SRT, MP4, 썸네일, 보관함 데이터는 변경하지 않음

## 검증 결과

- JavaScript 문법 검사: PASS
- Information 아이콘 정의 수: 1
- 적용 함수 호출 수: 1
- 중복 방지 클래스 확인: PASS
- V1 HTTP 응답: 200
- Git Diff 확인: PASS

## 롤백

이번 커밋만 되돌릴 경우:

```bash
git revert <이번 커밋 해시>
```

전체 메뉴 작업 전으로 복구할 경우 타임머신 태그를 기준으로 비교한다.

```bash
git show v1-menu-before-icon-source-20260730-0006
```

강제 reset과 git clean은 사용하지 않는다.
