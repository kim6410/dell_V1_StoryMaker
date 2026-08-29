# 2026-08-30 StoryMaker V1/Beta 복사출력전문점 · 프롬프트 · 날씨 최종 인수인계

## 1. 목적

2026-08-30 작업의 핵심은 StoryMaker에 `복사출력전문점` 업종을 추가하고, Beta의 복사·출력 전문점 전용 프롬프트(`copy_print_service v1.1`)를 적용하며, Gemini 실제 전송 프롬프트와 관리자용 원본 템플릿을 명확히 구분하고 중복 프롬프트 저장을 방지하는 것이다. 함께 확인된 날씨 스냅샷의 오래된 시간대 문제도 현재 시각 기준 데이터가 들어오는지 재검증했다.

## 2. 작업 전 안전 기준

- 최상위 지침: `/home/bourne/StoryMaker_1/00_READ_FIRST.md`
- 저장소에는 이번 작업 전부터 다른 세션/작업자의 수정·미추적 파일이 다수 존재했다.
- 따라서 전체 `git add .`, `git add -A`, `git commit -am`, `git clean`, `git reset --hard` 금지 원칙을 유지한다.
- 다른 작업자의 변경은 삭제·되돌리기·정리하지 않는다.
- 이번 인수인계 문서 작성 시점에도 저장소는 clean 상태가 아니다.

## 3. 복사출력전문점 업종 추가

### V1 업종

- industry key: `copy_print_shop`
- label: `복사출력전문점`
- category: `복사·인쇄`
- DB `industry_prompt_templates`에 활성 행 추가 완료
- sort_order: 127
- 추가 전/후 SQLite integrity check: `ok`
- DB 백업: `/home/bourne/StoryMaker_1/Backup/storymaker_before_copy_print_shop_20260830_051459.db`

V1 관련 수정 파일:

- `storymaker-web/backend/app/api/personas.py`
  - persona industry 허용 목록에 `copy_print_shop` 추가
- `storymaker-web/backend/app/main.py`
  - 프로필 표시명에 `copy_print_shop: 복사출력전문점` 추가
- `storymaker-web/backend/app/static/v1/assets/index-uploadui-20260719-v1-errorlog-2.js`
  - 업종 선택 UI에 `복사·인쇄 > 복사출력전문점` 추가
- `storymaker-web/backend/app/static/v1/index.html`
  - JS cache bust를 `20260830-copy-print-shop-1` 계열로 갱신했던 작업 포함

주의: 위 V1 bundle/index는 기존부터 다른 변경이 섞여 있던 dirty 파일이므로 파일 전체를 이번 작업분으로 간주하면 안 된다.

## 4. Beta 복사출력전문점 전용 프롬프트

신규 파일:

- `StoryMaker_beta/data/prompt_templates/copy_print_service.md`

템플릿 기준:

- template key: `copy_print_service`
- version: `1.1`
- 업종: 복사출력전문점
- 복사·출력·제본·명함·전단·포스터·배너·대형출력 등은 실제 제공 여부가 확인된 항목만 작성
- 파일 접수, 용지 규격/종류, 수량, 납기, 후가공, 방문/택배/픽업 등 주문 조건을 우선
- 학생·직장인·소상공인·행사 고객 등 이용 목적을 고려
- 확인되지 않은 가격·영업시간·장비 사양·무료 서비스·할인 생성 금지
- `최저가`, `무조건 당일`, `색상 100% 일치`, `오차 없음`, `모든 파일 출력 가능` 같은 보장형 표현 금지

`StoryMaker_beta/app/beta_prompt_store.py`에는 복사출력전문점 업종이 `copy_print_service` 템플릿을 선택하도록 하는 작업이 포함되어 있다.

## 5. Gemini 프롬프트 중복 문제 조사 결과

사용자가 관리자 화면에서 복사한 내용에는 다음 두 종류가 연달아 보여 실제 Gemini 전송도 두 벌이라고 오해할 수 있었다.

1. 관리자 편집용 원본 템플릿: `{{company}}`, `{{region}}` 같은 변수가 포함됨
2. 현재 작업 데이터가 치환된 Gemini 실제 전송 최종본

실제 서버 렌더링을 직접 검사한 결과 Gemini로 보내는 프롬프트는 이미 한 벌이었다.

검증 결과:

- 최종 프롬프트 헤더 수: 1
- `copy_print_service v1.1` 마커 수: 1
- `{{company}}` 등 원본 변수 잔존 수: 0
- 즉 생성부에서 원본+최종본 두 벌을 Gemini에 전송하는 구조는 아니었다.

따라서 정상 생성 로직을 임의로 잘라내지 않고 UI 구분과 서버 저장 검증을 강화했다.

## 6. 프롬프트 UI 및 재발 방지 수정

수정 파일:

- `StoryMaker_beta/app/beta_gemini.py`
- `StoryMaker_beta/static/beta-production.js`
- `StoryMaker_beta/static/production.html`

적용 내용:

- 관리자 원본 템플릿은 `프롬프트 템플릿 편집 (변수 포함)`으로 명확히 표시
- 실제 작업에 치환되어 Gemini에 들어가는 프롬프트는 `Gemini 실제 전송 프롬프트 (최종본)`으로 표시
- 실제 전송본은 최종 전송본 1벌임을 UI에서 알 수 있도록 구분
- 관리자가 실수로 원본 템플릿과 렌더링된 실제 전송본을 한 파일에 붙여 저장하는 경우를 서버 저장 단계에서 거부하도록 방어 로직 추가
- `<!-- StoryMaker prompt: ... -->` 형태의 렌더링 마커가 원본 템플릿에 섞이거나, 콘텐츠 통합 패키지 프롬프트가 중복된 형태를 저장하지 못하게 검증 강화
- Beta production JS cache bust 갱신: `beta-production.js?v=20260830-prompt-final-single-1`

작업 중 MCP 자동 백업 생성 위치:

- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260829_205029/StoryMaker_1__StoryMaker_beta__app__beta_gemini.py`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260829_205036/StoryMaker_1__StoryMaker_beta__static__beta-production.js`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260829_205043/StoryMaker_1__StoryMaker_beta__static__beta-production.js`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260829_205048/StoryMaker_1__StoryMaker_beta__static__beta-production.js`
- `/workspace/AI_Server/backup/mcp_workspace_file_backups/20260829_205137/StoryMaker_1__StoryMaker_beta__static__production.html`

## 7. 날씨 데이터 재검증

이전 생성 작업에 저장된 프롬프트에서는 과거 시간대의 25.7℃ 값이 계속 보일 수 있다. 이는 해당 작업 생성 당시 저장된 스냅샷이므로 기존 job을 다시 열어도 자동으로 바뀌지 않는다.

새 호출 기준으로 서울 동작구 상도동 날씨를 재검증했을 때:

- 관측/스냅샷 시각: 2026-08-30 05:45 기준
- 현재 기온: 약 22℃
- 상태: 흐림
- 최근 시간대 예: 03시 23.0℃ → 04시 22.7℃ → 05시 22.2℃

따라서 새 콘텐츠 생성에서는 최신 날씨 스냅샷이 사용되는 흐름을 확인했다. 기존 job의 과거 스냅샷과 새 job의 최신 스냅샷을 구분해야 한다.

## 8. 최종 검증

확인 완료:

- `copy_print_service` template version 1.1 확인
- 원본 템플릿의 `{{company}}` 등 변수 존재 정상
- 실제 job 렌더링 결과에서는 변수 잔존 0
- 실제 전송 프롬프트 헤더 1회
- 실제 전송 프롬프트 marker 1회
- `copy_print_service` marker 1회
- Python 문법 검사 통과
- JavaScript 문법 검사 통과
- `git diff --check` 통과
- Beta 서비스 active 확인
- Beta health 정상 응답 확인
- 실제 제공 HTML에서 `beta-production.js?v=20260830-prompt-final-single-1` 확인

## 9. 현재 Git 상태 — 매우 중요

인수인계 문서 작성 직전 HEAD:

- `becb206`

현재 저장소는 clean이 아니며 이번 작업과 이전/다른 세션 변경이 함께 존재한다.

추적 수정 파일:

- `StoryMaker_beta/app/beta_gemini.py`
- `StoryMaker_beta/app/beta_jobs.py`
- `StoryMaker_beta/app/beta_prompt_store.py`
- `StoryMaker_beta/data/prompt_templates/food_service.md`
- `StoryMaker_beta/static/beta-production.js`
- `StoryMaker_beta/static/production.html`
- `storymaker-web/backend/app/api/personas.py`
- `storymaker-web/backend/app/api/voicebox.py`
- `storymaker-web/backend/app/main.py`
- `storymaker-web/backend/app/static/v1/assets/index-uploadui-20260719-v1-errorlog-2.js`
- `storymaker-web/backend/app/static/v1/index.html`
- `storymaker-web/backend/app/static/v1/v1-admin-voicebox-entry.js`
- `storymaker-web/backend/app/static/v1/voicebox-studio.css`
- `storymaker-web/backend/app/static/v1/voicebox-studio.html`
- `storymaker-web/backend/app/static/v1/voicebox-studio.js`
- `storymaker-web/docker-compose.yml`
- `supertonic/app.py`
- `supertonic/podcast_generator.pyw`

미추적 파일에는 최소 다음이 포함되어 있다.

- `StoryMaker_beta/data/prompt_templates/copy_print_service.md`
- 과거 VoiceBox WORK_LOGS 3건
- `storymaker-web/backend/storymaker.db`
- `storymaker-web/docker-compose.yml.bak-before-plausible-removal-20260817`
- 본 인수인계 문서

절대로 다음 작업자가 이 목록 전체를 한꺼번에 커밋/삭제/정리하면 안 된다. 각 파일의 diff와 소유 작업을 먼저 분리해야 한다.

## 10. 커밋/Push 상태

본 인수인계 작성 시점에는 이번 복사출력전문점/Beta 프롬프트 작업을 별도 커밋하거나 Push하지 않았다.

이유:

- 저장소가 이미 여러 작업으로 dirty함
- 특히 bundle/index 및 Beta 일부 파일에 다른 세션 변경이 섞여 있을 가능성이 있음
- 사용자는 이번 요청에서 업무일지 저장과 다음 채팅 인수인계를 요청했으며, 전체 dirty 변경을 임의로 Push하라는 요청은 하지 않음

다음 작업에서 Push가 필요하면 반드시 이번 작업에 해당하는 exact diff만 다시 확인한 뒤 선택적으로 stage/commit 해야 한다.

## 11. 다음 채팅에서 가장 먼저 할 일

1. `/home/bourne/StoryMaker_1/00_READ_FIRST.md`를 먼저 읽는다.
2. 이 문서 `WORK_LOGS/2026-08-30_StoryMaker_V1_Beta_복사출력전문점_프롬프트_날씨_최종인수인계.md`를 읽는다.
3. `git status --short`로 dirty 상태가 그대로인지 확인한다.
4. 새 Beta 콘텐츠를 하나 생성해 관리자 화면에서 `Gemini 실제 전송 프롬프트 (최종본)`을 연다.
5. 다음을 확인한다.
   - `copy_print_service v1.1`이 1회만 존재
   - `{{company}}` 같은 원본 변수가 없음
   - 최신 날씨/시간대가 들어감
   - 복사출력전문점 전용 지침이 실제 생성 결과에 반영됨
6. 이상이 없다면 사용자 요청에 따라 이번 작업분만 선택 커밋/Push 여부를 결정한다.

## 12. 다음 작업자에게 전달할 핵심 한 줄

`복사출력전문점(copy_print_shop) + Beta copy_print_service v1.1은 적용되어 있고 실제 Gemini 전송 프롬프트는 1벌이다. 원본 템플릿과 최종 전송본 UI를 구분했고 중복 저장 방어까지 추가했다. 저장소는 여러 작업이 섞인 dirty 상태이므로 절대 전체 stage/commit/clean하지 말고 이 인수인계서를 기준으로 exact diff만 다룰 것.`
