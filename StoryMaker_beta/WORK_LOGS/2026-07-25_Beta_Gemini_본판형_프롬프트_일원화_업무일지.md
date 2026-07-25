# StoryMaker Beta Gemini 프롬프트 일원화 업무일지

작성일: 2026-07-25

## 작업 목적

Beta의 API Gemini 접근과 브라우저 worker 접근이 같은 프롬프트 템플릿을 사용하도록 `app/beta_gemini.py`의 공통 프롬프트 생성 함수를 본판형 BLOCK 프롬프트로 변경했다.

## 수정 파일

- `/home/bourne/StoryMaker_1/StoryMaker_beta/app/beta_gemini.py`
- `/home/bourne/StoryMaker_1/StoryMaker_beta/app/beta_gemini_worker.py`

## 수정 전 백업

- `/home/bourne/StoryMaker_1/StoryMaker_beta/backups/beta_prompt_unify_20260725_174749/beta_gemini.py`
- `/home/bourne/StoryMaker_1/StoryMaker_beta/backups/beta_prompt_unify_20260725_174749/beta_gemini_worker.py`

## 변경 내용

- `beta_build_prompt()`를 기존 Beta JSON 프롬프트에서 본판형 `# 콘텐츠 통합 패키지 생성 프롬프트 v3.6-stable` BLOCK 프롬프트로 변경했다.
- 본판형 13개 블록을 생성 대상으로 추가했다.
  - `BLOG_TITLES`
  - `BLOG_POST`
  - `NAVER_PLACE_NEWS`
  - `GOOGLE_BUSINESS_POST`
  - `BLOG_HASHTAGS`
  - `CARROT_TITLES`
  - `CARROT_POST`
  - `CARROT_HASHTAGS`
  - `INSTAGRAM_POST`
  - `INSTAGRAM_HASHTAGS`
  - `CAROUSEL_7`
  - `PODCAST_50`
  - `PODCAST_80`
- `beta_extract_blocks()`가 기존 Beta 8채널 응답과 본판형 13블록 응답을 모두 파싱하도록 확장했다.
- 본판형 13블록 응답은 Beta 기존 `channels` 구조로 매핑하고, 원본 블록은 `source_blocks`에 보존하도록 했다.
- 팟캐스트 렌더 포맷에서 `[여성]`, `[남성]` 화자 태그도 인식하도록 했다.
- API 직접 호출과 worker 호출 모두 JSON response schema 강제를 해제하고 동일한 BLOCK 프롬프트를 사용하도록 했다.
- worker의 non-json Gemini 출력 한도를 `16000` 토큰으로 올렸다.

## 검사 결과

- `python3 -m py_compile app/beta_gemini.py app/beta_gemini_worker.py`: PASS
- 본판형 프롬프트 생성 샘플 확인: `v3.6-stable`, `BLOG_TITLES`, `PODCAST_50` 포함 확인
- 본판형 13블록 샘플 파싱 확인: 8개 Beta 채널 매핑 및 `source_blocks` 13개 보존 확인
- `git diff --no-index --check` 백업 대비 공백 오류: 출력 없음
- 원격 localhost HTTP:
  - `GET /beta-api/health`: 200
  - `GET /beta`: 200
  - `GET /beta-api/gemini-worker/status`: 200

## 미확인 항목

- 현재 `storymaker-beta.service`는 `--reload` 없이 실행 중이라 서비스 재시작 전까지 실행 중 프로세스에는 새 Python 코드가 반영되지 않는다.
- `sudo systemctl restart storymaker-beta.service`는 대화 환경에서 비밀번호 없는 sudo가 되지 않아 실행하지 못했다.
- 실제 브라우저 Gemini 생성, 결과 파일 생성, 보관함 반영은 사용자가 서비스 재시작 후 화면에서 확인해야 한다.

## V1 무변경 확인

- 이번 수정은 `/home/bourne/StoryMaker_1/StoryMaker_beta` 내부 파일 2개에만 적용했다.
- `/home/bourne/StoryMaker_1/storymaker-web` 및 V1 운영 파일은 수정하지 않았다.

## 롤백 방법

문제가 있으면 사용자 승인 후 아래 백업 파일 2개를 원래 위치로 복원한다.

- `/home/bourne/StoryMaker_1/StoryMaker_beta/backups/beta_prompt_unify_20260725_174749/beta_gemini.py`
- `/home/bourne/StoryMaker_1/StoryMaker_beta/backups/beta_prompt_unify_20260725_174749/beta_gemini_worker.py`
