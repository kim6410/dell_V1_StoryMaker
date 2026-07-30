# 2026-07-31 Beta Worker 조기예열·재사용 MP4 속도증가 개선판 업무일지

## 작업 목적

어제저녁 이후 추가된 Beta 기능은 유지하면서, 브라우저 WebGPU 음성 엔진의 불필요한 준비 대기와 작업별 Worker 폐기로 발생하던 속도 편차를 줄인다.

## 적용 내용

- 작업 ID가 연결되는 즉시 실제 Beta 음성 Worker를 준비한다.
- 준비 Promise가 완료되기 전에는 영상 만들기 버튼을 비활성화한다.
- 정상 제작 완료 후 Worker와 ONNX 세션을 종료하지 않고 같은 탭에서 재사용한다.
- 준비 실패, 음성 추론 시간 초과, Worker 오류, GPU device lost 때만 Worker를 폐기한다.
- 15분 동안 사용하지 않거나 탭을 닫을 때 Worker를 정리한다.
- V1 본체에 별도 음성 Worker를 추가하지 않아 245MB 모델 중복 적재를 방지한다.
- 랜덤 음성, 설정값 적용, 전화번호 읽기 변환, 음악 믹싱, MP4 생성, 보관함 자동 저장 기능은 유지한다.

## 수정 파일

- `StoryMaker_beta/static/beta-browser-render.js`
- `StoryMaker_beta/static/beta-shortform-inline.js`
- `StoryMaker_beta/static/production.html`

## 캐시 버전

- `beta-browser-render.js?v=20260731-worker-reuse-prewarm-1`
- `beta-shortform-inline.js?v=20260731-worker-ready-gate-1`

## 성능 확인

적용 후 확인 작업 `beta_20260731_035020_9662e0169454`:

- provider: WebGPU
- engine_was_warm: true
- TTS inference: 약 2.46초
- 브라우저 음성 전체 생성: 약 3.39초
- 서버 폴백 없음

어제 빠른 기록의 일반 구간인 약 2.7~3.4초와 유사한 수준으로 복구됐다.

## 백업

현재 정상·고속 기준 백업:

`/home/bourne/StoryMaker_1/Backup/7월31일mp4속도증가_개선판`

MP4 인코더 하드웨어 강제 우선 및 프리뷰 축소 실험은 체감 속도가 악화되어 위 백업 상태로 즉시 복원했다. 최종 커밋에는 해당 실패 실험이 포함되지 않는다.

## 검증 항목

- JavaScript 문법 검사
- Beta 서비스 active 확인
- 실제 HTTP 제공 파일과 로컬 파일 SHA-256 일치
- Worker 15분 유휴 정리
- 정상 완료 후 Worker 유지
- 오류·추론 제한·GPU device lost 시 Worker 정리
- 작업 ID 연결 즉시 예열
- 엔진 준비 완료 전 제작 버튼 잠금
- 다른 작업 트리 변경사항 미포함
