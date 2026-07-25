# StoryMaker Beta AI Provider 다중 폴백 구현 업무일지

작성일: 2026-07-25

## 작업 대상

- Dell Beta 루트: `/home/bourne/StoryMaker_1/StoryMaker_beta`
- 운영 서비스: `storymaker-beta.service`
- 운영 포트: `8021`
- Supertonic 포트: `7790`
- 수정 파일: `app/beta_gemini.py`

## 작업 전 확인

- `/home/bourne/StoryMaker_1/StoryMaker_beta/00_READ_FIRST.md` 확인 완료
- V1과 운영 V2는 수정하지 않음
- 기존 MCP 자동 백업 보존
- 서비스 재시작 전 Python 문법 검사 수행

## 발견한 문제

기존 `beta_gemini.py`에는 `beta_call_gemini_only()` 함수가 존재했지만 라우터와 작업 생성 함수에서는 정의되지 않은 `beta_call_gemini()`를 호출하고 있었다.

이 상태는 이전 Gemini 호출 함수 분리 작업이 중간에 멈추면서 남은 불완전한 변경으로 판단했다.

## 신규 자동 백업

수정 과정에서 MCP가 아래 백업을 생성했다.

- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260725_010017/StoryMaker_1__StoryMaker_beta__app__beta_gemini.py`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260725_010033/StoryMaker_1__StoryMaker_beta__app__beta_gemini.py`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260725_010119/StoryMaker_1__StoryMaker_beta__app__beta_gemini.py`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260725_010135/StoryMaker_1__StoryMaker_beta__app__beta_gemini.py`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260725_010156/StoryMaker_1__StoryMaker_beta__app__beta_gemini.py`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260725_010216/StoryMaker_1__StoryMaker_beta__app__beta_gemini.py`

기존 사전 조사 자동 백업:

- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260725_004740/`

## 구현 내용

AI Provider 호출 순서를 아래와 같이 구현했다.

```text
Gemini
  ↓ 실패
DeepSeek
  ↓ 실패
Nemotron 3 Ultra
```

추가한 주요 함수:

- `beta_deepseek_key()`
- `beta_nvidia_key()`
- `beta_deepseek_model()`
- `beta_nemotron_model()`
- `beta_fallback_enabled()`
- `beta_extract_openai_text()`
- `beta_call_openai_provider()`
- `beta_call_deepseek()`
- `beta_call_nemotron()`
- `beta_call_ai()`

적용 환경변수:

- `GEMINI_API_KEY`
- `DEEPSEEK_API_KEY`
- `NVIDIA_API_KEY`
- `AI_FALLBACK_ENABLED`
- `DEEPSEEK_MODEL`
- `NEMOTRON_MODEL`
- 선택 항목: `NVIDIA_API_BASE`

기본 모델:

- Gemini: 기존 `gemini-3.5-flash-lite` 유지
- DeepSeek: `deepseek-v4-flash`
- Nemotron: `nvidia/nemotron-3-ultra-550b-a55b`

## 로그 정책

API 키와 전체 프롬프트는 기록하지 않는다.

기록 항목:

- Provider 이름
- 성공 또는 실패
- 응답 시간
- 실패 사유 일부
- 최종 성공 Provider

## 검증 결과

### Python 문법 검사

```text
python3 -m py_compile app/beta_gemini.py
STATUS=PASS
```

### 강제 폴백 모의 테스트

```text
ORDER=gemini>deepseek>nemotron
PROVIDER=nemotron
ATTEMPTS=2
STATUS=PASS
```

### 서비스 재시작

```text
storymaker-beta.service
active (running)
Uvicorn 0.0.0.0:8021
STATUS=PASS
```

재시작 직후 첫 HTTP 확인은 서버 기동 완료 전 접근하여 ConnectionRefused가 한 번 발생했다.

이후 systemd와 Uvicorn 로그에서 정상 기동을 확인했다.

### Provider 상태 API

`GET /beta-api/gemini/status`

확인 결과:

- fallback_enabled: true
- Gemini configured: true
- DeepSeek configured: true
- Nemotron configured: true
- API 키 노출 없음

### 실제 API 폴백 테스트

`POST /beta-api/gemini/generate`로 실제 콘텐츠 생성 요청을 실행했다.

실제 흐름:

1. Gemini 호출
   - API 응답은 왔으나 SNS 8채널 BLOCK 형식 검증 실패
2. DeepSeek 호출
   - HTTP 402 `Insufficient Balance`
3. Nemotron 3 Ultra 호출
   - 성공

최종 결과:

- Provider: `nemotron`
- Model: `nvidia/nemotron-3-ultra-550b-a55b`
- 생성 채널 8개 모두 확인
  - BLOG
  - NAVER_PLACE
  - GOOGLE_BUSINESS
  - INSTAGRAM
  - CARROT
  - CAROUSEL_7
  - PODCAST_50
  - PODCAST_80
- `STATUS=PASS`

## 현재 판단

다중 폴백 엔진은 실제 API 기준으로 작동한다.

Gemini는 키 오류가 아니라 현재 응답 형식이 StoryMaker Beta의 8채널 BLOCK 규격을 만족하지 않아 폴백되었다.

DeepSeek는 키 인증 단계를 통과했으나 계정 잔액 부족으로 402가 발생했다.

Nemotron 3 Ultra는 실제 응답과 8채널 파싱까지 정상 완주했다.

## 미완료 및 후속 확인

- 실제 Beta 화면의 `콘텐츠 자동생성` 버튼을 눌러 브라우저 Worker 흐름과 이번 서버 Provider 폴백 경로가 어느 조건에서 연결되는지 확인 필요
- DeepSeek 잔액 충전 후 Provider 단독 성공 테스트 필요
- Gemini 출력 형식을 8채널 BLOCK으로 더 강제할지 별도 검토 필요
- 현재 Dell 배포 폴더와 상위 폴더에서 `.git` 저장소를 찾지 못해 Git diff와 커밋은 수행하지 못함

## 롤백 기준

문제 발생 시 가장 마지막 수정 전 원본은 아래 백업부터 역순으로 확인한다.

`/workspace/AI_Server/backup/mcp_workspace_file_backups/20260725_010017/StoryMaker_1__StoryMaker_beta__app__beta_gemini.py`

파일 전체 덮어쓰기나 임의 삭제는 하지 않고, 백업과 현재 파일의 차이를 확인한 뒤 필요한 블록만 복구한다.
