# 2026-07-31 Beta Worker 재사용·MP4 속도개선 최종 인수인계

작성 시각: 2026-07-31 04:08 KST
작업 루트: `/home/bourne/StoryMaker_1`

## 다음 채팅에서 가장 먼저 확인할 문서

1. `/home/bourne/StoryMaker_1/00_READ_FIRST.md`
2. `/home/bourne/StoryMaker_1/WORK_LOGS/2026-07-31_Beta_Worker_재사용_MP4속도개선_최종인수인계.md`
3. `/home/bourne/StoryMaker_1/WORK_LOGS/2026-07-31_Beta_Worker_조기예열_재사용_MP4속도증가_개선판_업무일지.md`

## 현재 정상 기준

현재 정상 커밋:

`e77ad7604d308d95d7c22cfe782f37c8b3298bc4`

커밋 메시지:

`Beta Worker 조기예열과 재사용으로 제작 속도 개선`

로컬 HEAD, 추적 브랜치, GitHub 원격 `main`이 모두 동일하며 `PUSH_VERIFY=PASS` 상태다.

Beta 서비스는 `storymaker-beta.service`이며 현재 정상 동작 기준은 다음과 같다.

- 작업 ID 생성 즉시 실제 Beta 음성 Worker 예열
- WebGPU·ONNX 준비 완료 전 영상 만들기 버튼 잠금
- 정상 제작 완료 후 Worker와 세션 유지
- 같은 탭의 다음 작업에서 재사용
- 오류, GPU device lost, 실제 추론 15초 초과 때만 Worker 폐기
- 15분 미사용 또는 탭 종료 때 정리
- V1 별도 Worker 중복 예열 금지

## 현재 핵심 파일

- `/home/bourne/StoryMaker_1/StoryMaker_beta/static/beta-browser-render.js`
- `/home/bourne/StoryMaker_1/StoryMaker_beta/static/beta-shortform-inline.js`
- `/home/bourne/StoryMaker_1/StoryMaker_beta/static/production.html`

실제 제공 캐시 기준:

- `beta-browser-render.js?v=20260731-worker-reuse-prewarm-1`
- `beta-shortform-inline.js?v=20260731-worker-ready-gate-1`

## 속도 실측 기준

현재 정상 개선판 실측 예:

- `podcast_provider=webgpu`
- `engine_was_warm=true`
- TTS 추론 약 2.46초
- 브라우저 음성 전체 약 3.39초
- 서버 폴백 없음

어제 가장 빠른 기록 예:

- 브라우저 음성 전체 약 2.46초
- 일반적인 빠른 구간 약 2.7~3.4초

따라서 현재 음성 생성 속도는 어제의 일반적인 최고속 범위에 거의 도달한 상태다.

## mp4속도개선 방법

실제로 효과가 확인된 핵심은 MP4 인코더 옵션 변경이 아니라 제작 전 음성 엔진 준비와 Worker 재사용이다.

적용 순서:

1. 작업 ID가 생기면 실제 제작에 사용할 Beta Worker를 즉시 준비한다.
2. 준비 Promise가 끝나기 전에는 제작 버튼을 비활성화한다.
3. 정상 완료 후 Worker를 종료하지 않는다.
4. 같은 탭의 다음 제작에서도 동일 Worker와 준비된 WebGPU·ONNX 상태를 재사용한다.
5. 오류, GPU 장치 손실, 실제 추론 지연 때만 Worker를 폐기하고 새로 만든다.
6. 10~15분 미사용 또는 탭 종료 때만 정리한다.
7. V1 본체에서 별도 음성 Worker를 중복으로 띄우지 않는다.

맥미니 적용 시에는 파일 이름을 그대로 복사하기보다 위 구조를 해당 프로젝트 코드에 맞게 이식해야 한다.

확인해야 할 진단값:

- `podcast_provider`
- `engine_was_warm`
- `webgpu_adapter_ms`
- `onnx_session_create_ms`
- `tts_inference_ms`
- `podcast_total_ms`
- 서버 폴백 발생 여부

## 실패한 MP4 실험과 금지사항

다음 실험은 Dell Chrome 환경에서 오히려 현저히 느려져 즉시 롤백했다.

- H.264 인코더 `hardwareAcceleration: "prefer-hardware"` 강제
- 미리보기 Canvas 갱신 초당 약 12회에서 3회로 축소
- 진행상황 갱신 초당 약 2회에서 1회로 축소

결론:

- 현재 Chrome에서는 `prefer-hardware` 강제가 반드시 빠르지 않다.
- 자동 선택인 `no-preference` 상태가 더 빨랐다.
- 미리보기·진행 콜백은 주 병목이 아니었다.
- 영상 프레임 렌더 구간이 약간 느린 것은 정상 범위이며 현재 체감은 지루하지 않은 수준이다.
- MP4 인코더 설정은 추가 근거 없이 변경하지 않는다.

## 복원 백업

현재 정상·고속 기준 백업:

`/home/bourne/StoryMaker_1/Backup/7월31일mp4속도증가_개선판`

Worker 속도복원 전 백업:

`/home/bourne/StoryMaker_1/Backup/TIME_MACHINE_20260731_034700_BetaWorker속도복원전`

업무일지 수정 전 백업:

`/home/bourne/StoryMaker_1/Backup/WORKLOG_BACKUP_20260731_040400_mp4속도개선방법추가전`

## 현재 미커밋 상태

`mp4속도개선 방법` 항목을 추가한 아래 업무일지는 현재 커밋 `e77ad76` 이후 수정된 상태다.

`/home/bourne/StoryMaker_1/WORK_LOGS/2026-07-31_Beta_Worker_조기예열_재사용_MP4속도증가_개선판_업무일지.md`

이번 최종 인수인계 문서 역시 새로 작성되었으며 아직 별도 커밋·Push하지 않았다.

다른 다수의 미커밋·미추적 파일은 기존 작업물이다. 절대 광범위하게 `git add .`, `git reset --hard`, `git clean`을 실행하지 않는다.

## 다음 작업 시작 순서

1. 위 3개 문서를 순서대로 읽는다.
2. `git status --short`에서 현재 문서 2개 외 다른 변경사항을 구분한다.
3. Beta 화면을 Ctrl+F5 후 작업 ID 연결 시 `브라우저 엔진 준비 중...`에서 `영상 만들기`로 바뀌는지 확인한다.
4. 비슷한 길이의 팟캐스트 50 작업을 2~3회 같은 탭에서 제작한다.
5. `podcast_provider=webgpu`, `engine_was_warm=true`, `podcast_total_ms` 약 2.5~4초 범위인지 확인한다.
6. 영상 프레임 처리 속도는 현재 기준을 유지하고 MP4 인코더 옵션을 임의 변경하지 않는다.
7. 문서까지 커밋할 경우 대상 문서만 명시적으로 스테이징한다.

## 절대 주의

- V1과 Beta Worker를 동시에 중복 예열하지 않는다.
- 정상 Worker를 작업마다 종료하지 않는다.
- `prefer-hardware`를 속도 향상 목적으로 강제하지 않는다.
- 현재 정상 백업과 커밋을 덮어쓰지 않는다.
- unrelated dirty files를 포함해 커밋하지 않는다.
