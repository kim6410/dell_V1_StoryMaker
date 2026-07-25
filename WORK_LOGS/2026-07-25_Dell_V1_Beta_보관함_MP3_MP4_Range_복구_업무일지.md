# Dell V1 Beta 보관함 MP3·MP4 재생·다운로드 복구 업무일지

작성일: 2026-07-25

## 작업 대상

- Dell V1 루트: `/home/bourne/StoryMaker_1`
- Beta 독립 루트: `/home/bourne/StoryMaker_1/StoryMaker_beta`
- 외부 접속 경로: `https://app.mystorymaker.net/v1/?page=betaProduction`
- 수정 파일: `/home/bourne/StoryMaker_1/storymaker-web/backend/app/main.py`

## 보호 범위

- Beta의 MP3·MP4 생성 엔진은 수정하지 않음
- Beta DB와 기존 작업 결과 파일은 수정하지 않음
- V1 기존 제작 엔진·보관함·Supertonic은 수정하지 않음
- V1의 Beta 전용 프록시 응답 헤더 처리 블록만 최소 수정

## 증상

Beta 제작 화면에서 최종 MP3와 MP4는 정상 생성되고 작업별 `result.json`에도 다음 키로 저장되어 있었다.

- `assets.browser_audio`
- `assets.browser_video`

실제 파일도 다음 위치에 존재했다.

- `output/browser/browser_podcast.mp3`
- `output/browser/browser_final.mp4`

Beta 서버 직접 경로에서는 두 파일 모두 HTTP 200으로 정상 응답했지만, V1 프록시 경로를 거치면 브라우저 미디어 재생과 다운로드가 정상 동작하지 않았다.

## 원인

V1의 `_proxy_beta_request()`가 Beta upstream 응답을 새 `Response`로 다시 만들면서 미디어 구간 요청에 필요한 다음 헤더를 전달하지 않았다.

- `Content-Range`
- `Accept-Ranges`

브라우저의 `<audio>`와 `<video>`는 재생·탐색 과정에서 Range 요청을 사용한다.

기존 외부 응답은 HTTP 206이면서도 `Content-Range`가 없어, 저장된 파일이 있어도 재생·탐색·다운로드가 실패할 수 있는 상태였다.

## 수정 내용

`_proxy_beta_request()`의 정상 upstream 응답 헤더에 다음 항목을 선택적으로 전달하도록 추가했다.

- `Content-Range`
- `Accept-Ranges`
- `Content-Disposition`
- `ETag`
- `Last-Modified`

전체 파일 덮어쓰기는 하지 않았으며 기존 `response_headers` 블록 직후에 헤더 전달 루프만 추가했다.

## 백업

MCP 자동 백업:

`/workspace/AI_Server/backup/mcp_workspace_file_backups/20260725_123649/StoryMaker_1__storymaker-web__backend__app__main.py`

수정 전 SHA-256:

`614ba11a7b747b14a42438242564385bdf500a7265d89b950b750cc38528dfbe`

수정 후 SHA-256:

`17920af2e9859a6101b6b4d4b82be858b4476daed57dd28b992693516095736a`

## 적용

- Python 문법 검사 통과
- `storymaker-v1-backend` 컨테이너 재시작 완료
- V1 backend bind mount 확인: `/home/bourne/StoryMaker_1/storymaker-web/backend -> /app`

## 실제 검증

검증 작업 ID:

`beta_20260725_212711_6a313c`

파일 상태:

- MP3: 574,275 bytes
- MP4: 5,468,189 bytes

외부 V1 프록시 경로에서 시작·중간·마지막 구간을 각각 요청했다.

MP3:

- `bytes 0-99/574275` → HTTP 206
- `bytes 1000-1099/574275` → HTTP 206
- `bytes 574175-574274/574275` → HTTP 206

MP4:

- `bytes 0-99/5468189` → HTTP 206
- `bytes 1000-1099/5468189` → HTTP 206
- `bytes 5468089-5468188/5468189` → HTTP 206

모든 응답에서 다음 헤더가 정상 확인됐다.

- `Content-Range`
- `Accept-Ranges: bytes`

## 현재 상태

서버 측 복구 완료.

브라우저에서는 기존 보관함 탭을 강력 새로고침한 뒤 최신 작업 상세에서 MP3 재생, MP4 재생, MP3 다운로드, MP4 다운로드를 확인하면 된다.
