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

---

# mp4속도개선 방법

## 전달 대상

맥미니 StoryMaker 작업자.

이 항목은 Dell Beta에서 실제 제작 시간을 비교하며 확인한 속도 개선 방법을 정리한 것이다. 이름은 `mp4속도개선 방법`이지만, 실제로 가장 큰 체감 향상은 MP4 프레임 인코더 자체가 아니라 MP4 제작 직전에 실행되는 브라우저 WebGPU 음성 Worker의 조기 예열과 재사용에서 발생했다.

## 가장 중요한 결론

속도를 살리는 핵심은 다음 세 가지다.

1. 실제 제작에 사용하는 Beta Worker를 작업 ID가 생성되는 즉시 준비한다.
2. 준비된 WebGPU·ONNX Worker와 세션을 영상 한 건마다 종료하지 않고 같은 탭에서 재사용한다.
3. 정상 완료 시 Worker를 유지하고 오류, GPU 장치 손실, 실제 추론 지연, 장시간 미사용, 탭 종료 때만 폐기한다.

V1 화면에서 별도의 Worker를 하나 더 띄우는 중복 예열 방식은 사용하지 않는다. 245MB ONNX 모델을 중복으로 올리면 브라우저 메모리와 GPU 자원을 이중으로 사용하며, 모델 로딩 97% 부근 실패 또는 흰 화면이 재발할 수 있다.

## Dell에서 효과가 확인된 현재 구현

핵심 파일:

- `/home/bourne/StoryMaker_1/StoryMaker_beta/static/beta-browser-render.js`
- `/home/bourne/StoryMaker_1/StoryMaker_beta/static/beta-shortform-inline.js`
- `/home/bourne/StoryMaker_1/StoryMaker_beta/static/production.html`

현재 기준 커밋:

- `e77ad7604d308d95d7c22cfe782f37c8b3298bc4`
- 커밋 메시지: `Beta Worker 조기예열과 재사용으로 제작 속도 개선`

참고용 과거 빠른 체크포인트:

- `ef03c6611b275f8d8f3be2d75c4e00ddc584bcdf`
- 커밋 메시지: `Beta 동영상 클립 길이 15퍼센트 확대`

과거 체크포인트는 가장 빠른 상태를 비교하기 위한 참고 기준이며, 그대로 전체 복원하는 것보다 현재 커밋의 Worker 재사용 구조를 적용하는 편이 안전하다.

## 구현 순서

### 1. 작업 ID 생성 즉시 실제 Beta Worker 예열

작업 ID를 받은 직후 `renderer.prime(jobId)`를 비동기로 즉시 호출한다. 원고와 이미지 문맥을 불러오는 동안 WebGPU 어댑터, ONNX 세션, 음성 스타일을 동시에 준비한다.

제작 버튼을 누른 뒤에 준비를 시작하면 사용자 화면에서는 GPU가 일하지 않는 10~30초 대기 구간이 생길 수 있다.

### 2. 준비 완료 전 제작 버튼 잠금

Worker 준비가 끝나기 전에는 `영상 만들기` 버튼을 비활성화한다.

표시 예:

- 준비 중: `브라우저 엔진 준비 중...`
- 준비 완료: `영상 만들기`
- 준비 실패: `브라우저 엔진 다시 준비`

준비 완료 전에 사용자가 제작을 시작하지 못하게 해야, 제작 단계 안에서 준비 대기 시간이 섞이지 않는다.

### 3. 정상 완료 후 Worker를 종료하지 않음

영상 한 건이 정상 완료된 뒤 `releaseBrowserPodcastWorker()`를 실행하지 않는다.

정상 완료 시에는 마지막 사용 시각만 갱신하고 유휴 정리 타이머를 다시 설정한다. 같은 탭에서 다음 작업을 만들 때 기존 Worker와 ONNX 세션을 그대로 재사용한다.

### 4. 다음 조건에서만 Worker 폐기

- 엔진 준비 실패
- 음성 생성 Worker 오류
- 실제 음성 추론 제한시간 초과
- WebGPU `device.lost`
- 15분 미사용
- `pagehide`
- `beforeunload`

오류 뒤에는 기존 Worker를 폐기하고 다음 시도에서 새 Worker를 만든다.

### 5. 준비 제한시간과 실제 추론 제한시간 분리

대형 ONNX 모델을 처음 준비하는 시간과, 이미 준비된 모델로 실제 음성을 추론하는 시간을 동일한 제한으로 처리하면 안 된다.

권장 방향:

- 백그라운드 모델 준비: 충분한 시간 허용
- 준비 완료 후 실제 음성 추론: 짧은 제한시간 적용

현재 Dell 구현에서는 실제 추론이 15초를 넘으면 Worker를 폐기하고 오류 처리한다. 맥미니에서는 첫 모델 준비시간을 별도로 측정한 뒤 적절한 제한값을 정한다.

## 실제 속도 비교 기준

Dell에서 빠른 팟캐스트 50 작업의 브라우저 기록은 다음 범위였다.

- WebGPU 활성: `true`
- 엔진 예열: `engine_was_warm: true`
- WebGPU 어댑터 준비: `0ms`
- ONNX 세션 생성: `0ms`
- TTS 추론: 약 `1.7~2.5초`
- MP3 포함 음성 전체: 약 `2.5~3.4초`

현재 개선판 실측 예:

- `podcast_provider: webgpu`
- `podcast_generation_seconds: 3.3874`
- `tts_inference_ms: 2463.1`
- `podcast_total_ms: 3384.8`
- `engine_was_warm: true`

이 범위가 나오면 Worker 예열·재사용은 정상이다.

## 진단 시 반드시 확인할 항목

결과의 `diagnostics.json` 또는 `browser_render.diagnostics`에서 다음을 확인한다.

- `webgpuActive`
- `podcast_provider`
- `podcast_generation_seconds`
- `podcast_perf.engine_was_warm`
- `podcast_perf.webgpu_adapter_ms`
- `podcast_perf.onnx_session_create_ms`
- `podcast_perf.tts_inference_ms`
- `podcast_perf.mp3_encode_ms`
- `podcast_perf.podcast_total_ms`

빠른 상태라면 `podcast_provider`는 `webgpu`, `engine_was_warm`은 `true`, 어댑터와 ONNX 세션 생성시간은 거의 0이어야 한다.

## MP4 프레임 구간에 대한 판단

음성 구간이 3초 안팎으로 복구된 뒤 남는 시간은 720×1280, 24fps, 자막, 전환 효과, 영상 클립을 실제로 그리는 MP4 프레임 렌더 구간이다.

35초 영상은 약 840개 이상의 프레임을 처리하므로 일정 시간이 필요한 것이 정상이다. 사용자가 지루하지 않다고 느끼는 현재 Dell 상태에서는 MP4 프레임 인코더를 무리하게 변경하지 않는다.

## 실패한 MP4 최적화와 금지사항

다음 변경은 Dell Chrome 환경에서 오히려 현저히 느려져 즉시 원복했다.

- WebCodecs H.264 설정을 `hardwareAcceleration: "prefer-hardware"`로 강제
- 실시간 미리보기 Canvas 복사 횟수 축소
- 진행상황 DOM 갱신 횟수 축소

Dell에서는 브라우저 자동 선택인 `hardwareAcceleration: "no-preference"`가 훨씬 빨랐다. 따라서 맥미니에서도 `prefer-hardware`가 반드시 빠를 것이라고 가정하지 말고 A/B 실측 후 결정한다.

현재 안정판에서 다음을 함부로 변경하지 않는다.

- 최종 720×1280 해상도
- 24fps
- 자막 및 상호·전화번호 렌더
- 전환 효과
- WebCodecs 자동 인코더 선택
- Worker 정상 완료 후 재사용 구조

## 맥미니 적용 절차

1. 현재 맥미니 코드를 별도 타임머신 백업한다.
2. 실제 제작용 Worker가 어디에서 생성되는지 찾는다.
3. 작업 ID 생성 직후 해당 Worker 하나만 `prime`한다.
4. 준비 완료 전 제작 버튼을 잠근다.
5. 정상 제작 완료 후 Worker를 종료하는 코드를 제거한다.
6. 오류, GPU 손실, 제한시간 초과, 15분 미사용, 탭 종료 때만 Worker를 정리한다.
7. V1 부모 화면이나 다른 iframe에서 동일 모델을 중복 예열하지 않는다.
8. 같은 탭에서 팟캐스트 50을 3회 연속 제작한다.
9. 첫 작업과 두 번째·세 번째 작업의 진단시간을 비교한다.
10. TTS 전체가 2.5~3.5초 범위로 안정되면 성공으로 판정한다.

## 복원 기준

Dell 현재 개선판 백업:

- `/home/bourne/StoryMaker_1/Backup/7월31일mp4속도증가_개선판`

Worker 수정 전 백업:

- `/home/bourne/StoryMaker_1/Backup/TIME_MACHINE_20260731_034700_BetaWorker속도복원전`

현재 안정 커밋:

- `e77ad7604d308d95d7c22cfe782f37c8b3298bc4`

문제가 생기면 MP4 인코더 일부만 임의로 섞어 복원하지 말고, 위 개선판 백업의 세 파일을 한 세트로 복원한다.

## 최종 전달 요약

맥미니에서 먼저 고칠 곳은 MP4 H.264 인코더가 아니라 MP4 제작 전에 실행되는 브라우저 음성 Worker 수명주기다.

`작업 ID 즉시 예열 → 준비 완료 후 버튼 활성화 → 정상 Worker 계속 재사용 → 오류·유휴·탭 종료 때만 폐기`

이 구조가 Dell에서 가장 큰 체감 속도 향상을 만들었다. MP4 프레임 인코더 강제 최적화는 장비와 브라우저에 따라 역효과가 날 수 있으므로 별도 백업과 A/B 실측 없이 적용하지 않는다.
