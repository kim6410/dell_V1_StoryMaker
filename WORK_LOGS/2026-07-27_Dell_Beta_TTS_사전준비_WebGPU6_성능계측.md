# Dell Beta TTS 사전 준비 및 WebGPU 최적화

## 작업 목적

- 딸깍 Beta의 TTS·MP3 생성 구간 약 30초를 줄인다.
- 작업 생성 직후 Gemini 원고 생성 시간과 TTS 엔진 준비 시간을 겹쳐 실행한다.
- 실제 병목을 다음 작업 결과에서 세부 시간으로 확인할 수 있게 한다.

## 수정 전 백업

- `/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260727_023105_Beta_TTS_사전준비_WebGPU6_수정전`
- 대상 파일 3개, 작업 전 Git Diff, Git 상태, SHA256 manifest 포함
- 백업 파일과 작업 전 원본의 SHA256 일치 확인 완료

## 수정 파일

- `StoryMaker_beta/static/beta-browser-render.js`
- `StoryMaker_beta/static/beta-production.js`
- `StoryMaker_beta/static/production.html`

## 변경 내용

- Beta 작업 ID 생성 직후 브라우저 Podcast Worker에 `prepare` 요청을 보낸다.
- 준비 Promise를 재사용해 실제 TTS 시작 시 Worker와 ONNX 세션을 다시 만들지 않는다.
- WebGPU 준비 성공 시 `inferenceSteps`를 8에서 6으로 조정한다.
- WebGPU를 사용할 수 없는 WASM 경로는 기존 8단계를 유지한다.
- MP4와 최종 보관함 업로드가 끝날 때까지 Worker를 유지한 뒤 종료한다.
- 최종 진단에 provider, 전체 생성 시간, 엔진 warm 여부, adapter/session/voice/TTS/후처리/WAV/MP3/SRT 시간을 저장한다.
- 기존 썸네일 UI 변경과 `beta-shortform-inline.js` 캐시 버전은 그대로 보존했다.

## 검사

- `node --check` 2개 JavaScript 통과
- `git diff --check` 통과
- 세 파일 UTF-8 판정 확인
- 공개 Beta 화면, `beta-browser-render.js`, `beta-production.js` HTTP 200
- 브라우저에서 신규 캐시 버전 로드 확인
- 브라우저 초기 콘솔 오류 없음

## 실제 측정 기준

다음 Beta 작업의 결과 진단에서 아래 값을 이전 작업과 비교한다.

- `podcast_generation_seconds`
- `podcast_perf.engine_was_warm`
- `podcast_perf.webgpu_adapter_ms`
- `podcast_perf.onnx_session_create_ms`
- `podcast_perf.voice_style_load_ms`
- `podcast_perf.tts_inference_ms`
- `podcast_perf.audio_postprocess_ms`
- `podcast_perf.mp3_encode_ms`
- `podcast_perf.podcast_total_ms`

## 롤백

아래 스크립트로 복원한다.

```bash
bash "/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260727_023105_Beta_TTS_사전준비_WebGPU6_수정전/rollback_beta_tts_prewarm.sh"
```

두 JavaScript는 백업 원본으로 복원하고 `production.html`은 이번 캐시 키 2개만 되돌려 백업 이후의 썸네일 변경을 보존한다. 스크립트가 `node --check`와 `git diff --check`까지 실행한다.
