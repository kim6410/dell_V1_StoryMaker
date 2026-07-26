# Dell V1 딸깍 MP3·MP4 성능 개선 수정 전 기준점

## 작업 일시

- 2026-07-27 02:07 KST

## 작업 목적

- Dell V1 딸깍 제작의 MP3 생성부터 MP4 저장까지 발생하는 중복 실행과 렌더링 병목을 개선하기 전 Git 기준점과 별도 복구본을 준비
- 이번 개선 대상 이외의 V2, Beta, React 활성 번들 및 사용자 작업 파일을 커밋 범위에서 제외

## 수정 전 백업

- `/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260727_020725_딸깍_MP3_MP4_성능개선_수정전`
- 백업 폴더의 `MANIFEST.txt`에 현재 브랜치, Git HEAD, origin/main 및 파일별 SHA-256 기록

## 개선 대상 후보 파일

- `storymaker-web/backend/app/static/v1/v1-podcast-frontend-recovery.js`
- `storymaker-web/backend/app/static/v1/v1-browser-mp4-save-bridge.js`
- `storymaker-web/backend/app/static/v1/index.html`
- `storymaker-web/backend/app/api/mobile_one_shot.py`

## 기준 상태

- 브랜치: `main`
- 수정 전 HEAD: `db48be981b9889012f182e18225df584e4c884ac`
- 수정 전 origin/main: `91b55b04d418ab957a03ab45af5d154789ae9e87`
- 위 네 파일은 모두 Git 추적 상태
- 위 네 파일의 작업 트리 Diff 없음

## 현재 확인된 개선 항목

- 팟캐스트 브리지와 React 자동 실행 간 TTS 중복 실행 제거
- 동일 handoff의 `/browser-podcast` 중복 요청 방지
- MP4 Blob 직접 저장과 DOM 감시 저장의 중복 업로드 방지
- 오래된 `artifact_id` 대기 및 이전 오디오 선택 위험 제거
- 브라우저 숏폼 모드에서 불필요한 서버 slideshow 선행 실행 최소화
- 체험 연구실의 WebCodecs 직접 렌더링 경로 공통화 가능성 검토

## 이 기준점에서 수행하지 않은 작업

- 운영 코드 수정 없음
- 파일 삭제·이동 없음
- DB·Worker·Queue 생성 또는 변경 없음
- React 활성 번들 직접 수정 없음
- Dell V2 및 StoryMaker Beta 수정 없음
- 현재 작업 트리에 남아 있는 다른 Beta/V1 변경 및 미추적 파일은 스테이징하지 않음

## 검증

- 백업 파일 4개 생성 확인
- 원본과 백업 SHA-256 일치 확인
- 개선 대상 네 파일 Git 추적 및 작업 트리 clean 확인

## 롤백

- 향후 변경 전 상태로 복구할 때 백업 폴더의 네 파일을 같은 상대 경로로 복원
- 또는 이 기준점 이후 생성되는 성능 개선 커밋만 역적용
