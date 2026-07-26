# StoryMaker AI Project Guide v2.0

작성 기준: 2026-06-27

작업 위치: `/workspace/StoryMaker/storymaker-web`

이 문서는 StoryMaker 프로젝트를 처음 접하는 AI 또는 개발자가 가장 먼저 읽어야 하는 온보딩 문서입니다.

단순 설명서가 아니라, 현재 코드와 문서, 백업 이력, API 구조를 직접 확인해 정리한 개발 인수인계 문서입니다.

---

# 1. 프로젝트 개요

StoryMaker는 지역 소상공인을 위한 AI 기반 통합 콘텐츠 제작 플랫폼입니다.

하나의 기초 내용을 입력하면 여러 플랫폼에서 사용할 수 있는 콘텐츠 패키지를 한 번에 생성합니다.

현재 생성 대상은 다음과 같습니다.

- 네이버 블로그
- 당근마켓
- 인스타그램
- 네이버 플레이스
- Google Business Profile
- Podcast Script
- Carousel
- WordPress SEO 패키지
- ShortForm Slideshow

장기 목표는 다음 흐름입니다.

```text
입력
→ Prompt 생성
→ AI 결과 생성
→ 결과 파싱
→ SNS별 분리
→ Podcast 생성
→ Slideshow 생성
→ WordPress 발행
→ SNS 자동 발행
```

---

# 2. 전체 시스템 구조

현재 StoryMaker 웹앱은 FastAPI 기반입니다.

초기 설명에서 app.py라고 부르던 핵심 진입점은 현재 코드 기준으로 `backend/app/main.py`입니다.

```text
Browser

→ Caddy

→ FastAPI backend/app/main.py

→ API Router

→ Core Logic

→ SQLite Database

→ Podcast / Slideshow Upstream API

→ WordPress REST API
```

운영 도메인은 다음 구조를 사용합니다.

```text
https://mystorymaker.duckdns.org
https://app.mystorymaker.duckdns.org
```

CORS에는 위 두 도메인의 http/https 버전이 등록되어 있습니다.

---

# 3. 주요 폴더 구조

```text
storymaker-web/

backend/
  Dockerfile
  requirements.txt
  app/
    main.py
    settings.py
    migrate_db.py
    api/
    core/
    db/
    schemas/
    services/
    static/
    tests/

services/
  plausible-clickhouse/
  storymaker-user-jobs-cleanup.service
  storymaker-user-jobs-cleanup.timer

scripts/
  backup.sh
  cleanup_storymaker_user_jobs.sh

docs/
  beta_queue_plan.md

reports/
  wordpress_auto_draft_20260626.md
  menu_link_layout_audit.md
  podcast_slideshow_patch_plan.md

docker-compose.yml
Caddyfile
AI_PROJECT_GUIDE.md
GOOGLE_LOGIN_SETUP.md
```

---

# 4. 현재 main.py의 핵심 구조

파일 위치:

```text
backend/app/main.py
```

`main.py`는 StoryMaker 백엔드의 진입점입니다.

핵심 역할은 다음과 같습니다.

## 4.1 데이터베이스 초기화

```text
migrate_user_auth_columns()
Base.metadata.create_all(bind=engine)
seed_admin_user(db)
```

서버 시작 시 기존 users 테이블에 필요한 인증 컬럼을 보강하고, ORM 테이블을 생성하며, 기본 관리자 계정을 자동 시딩합니다.

## 4.2 FastAPI 앱 생성

```text
FastAPI(
  title="StoryMaker Web API",
  version="1.0.0"
)
```

## 4.3 CORS 설정

허용 도메인:

```text
https://mystorymaker.duckdns.org
https://app.mystorymaker.duckdns.org
http://mystorymaker.duckdns.org
http://app.mystorymaker.duckdns.org
```

## 4.4 API Router 등록

모든 API 라우터는 `/api` prefix 아래에 등록됩니다.

등록된 라우터는 다음과 같습니다.

```text
health_router
companies_router
personas_router
projects_router
prompts_router
results_router
keywords_router
scraper_router
auth_router
admin_router
feature_requests_router
wordpress_router
podcast_router
slideshow_router
```

## 4.5 Test Prompt Snapshot API

엔드포인트:

```text
POST /api/test/prompt-snapshot
```

역할:

`/storymaker-test?test_mode=1` 화면에서 생성한 통합 프롬프트를 임시 파일로 저장합니다.

저장 위치 기본값:

```text
/home/bourne/StoryMaker_1/output_results/test_prompt_snapshots
```

생성 파일:

```text
prompt_for_chatgpt.md
snapshot.json
latest.json
```

중요:

이 API는 admin only입니다.

운영 `/storymaker` 화면에서는 호출하지 않는 TEST ONLY 기능입니다.

## 4.6 정적 파일 서빙

정적 파일 위치:

```text
backend/app/static
```

캐시 문제 방지를 위해 `NoCacheStaticFiles`가 적용되어 있습니다.

대표 라우트:

```text
/                 → dashboard.html
/storymaker        → index.html
/storymaker-test   → storymaker-test.html
/podcast           → podcast.html
/slideshow         → slideshow.html
/about             → about.html
/queue-monitor     → queue-monitor.html
/admin/analytics   → index.html
```

---

# 5. API 모듈 구조

파일 위치:

```text
backend/app/api
```

주요 파일과 역할은 다음과 같습니다.

```text
admin.py
  관리자 기능

auth.py
  로그인, 회원가입, Google 로그인, JWT 인증, 사용자 세션

companies.py
  업체 정보 API

personas.py
  업체/사용자 페르소나 API

projects.py
  프로젝트 저장, 조회, 수정

prompts.py
  Prompt Builder API

results.py
  AI 결과 파싱 API

keywords.py
  키워드 빈도 추출 API

scraper.py
  외부 URL/블로그 참고자료 가져오기 API

podcast.py
  Podcast API 프록시 및 TTS 대본 정리

slideshow.py
  Slideshow API 프록시 및 렌더링 요청

wordpress.py
  WordPress 초안/발행 API

feature_requests.py
  수정요청/개선요청 게시판 API

health.py
  상태 확인 API
```

---

# 6. Core 모듈 구조

파일 위치:

```text
backend/app/core
```

중요 파일:

```text
prompt_builder.py
  통합 프롬프트 생성 핵심 로직

result_parser.py
  [BLOCK:...] 결과 파싱 핵심 로직

blog_formatter.py
  BLOG_POST 등 모바일 가독성 후처리
```

StoryMaker에서 가장 중요한 핵심은 `prompt_builder.py`와 `result_parser.py`입니다.

이 두 파일의 규칙이 깨지면 전체 콘텐츠 분리와 WordPress 발행 흐름이 흔들립니다.

---

# 7. Prompt 블록 규격

현재 Prompt Builder는 `콘텐츠 통합 패키지 생성 프롬프트 v3.0`을 생성합니다.

출력 전체는 반드시 하나의 코드블록 안에 있어야 합니다.

코드블록 내부에서는 아래 블록명이 정확히 유지되어야 합니다.

```text
[BLOCK:BLOG_TITLES]
추천 블로그 제목 5개

[BLOCK:BLOG_POST]
네이버 블로그 포스팅 1개

[BLOCK:CARROT_TITLES]
당근마켓 제목 5개

[BLOCK:CARROT_POST]
당근마켓 게시글 1개

[BLOCK:PODCAST_50]
캐릭터 팟캐스트 대본 50초 버전 1개

[BLOCK:PODCAST_80]
캐릭터 팟캐스트 대본 80초 버전 1개

[BLOCK:INSTAGRAM_POST]
인스타그램 캡션 1개

[BLOCK:INSTAGRAM_HASHTAGS]
인스타그램 해시태그 1줄

[BLOCK:CAROUSEL_7]
캐러셀 7장용 마크다운 1개

[BLOCK:NAVER_PLACE_NEWS]
네이버플레이스 소식 1개

[BLOCK:GOOGLE_BUSINESS_POST]
구글마이비즈니스 소식 1개

[BLOCK:BLOG_HASHTAGS]
블로그 해시태그 1줄

[BLOCK:CARROT_HASHTAGS]
당근마켓 해시태그 1줄

[BLOCK:WORDPRESS_SEO]
WordPress SEO 메타 및 본문 HTML 패키지 1개
```

현재 총 14개 블록입니다.

기존 v2 계열은 13개 블록이었고, 현재 v3.0에서는 `WORDPRESS_SEO`가 추가되었습니다.

---

# 8. Result Parser 규칙

파일 위치:

```text
backend/app/core/result_parser.py
```

핵심 함수:

```text
extract_primary_code_block(text)
parse_result_blocks(text)
join_result_blocks(block_names, block_values)
```

## 8.1 코드블록 추출

AI 응답에서 첫 번째 Markdown 코드블록을 우선 추출합니다.

```text
```content
...
```
```

코드블록이 없으면 원문 전체를 대상으로 파싱합니다.

## 8.2 BLOCK 파싱

다음 형식을 기준으로 분리합니다.

```text
[BLOCK:BLOG_POST]
```

공백이 일부 흔들린 형태도 허용합니다.

예:

```text
[ BLOCK : BLOG_POST ]
```

## 8.3 중복 블록 방어

같은 BLOCK이 뒤에서 다시 나와도 첫 번째 정상 콘텐츠가 상태 문구로 덮어씌워지지 않도록 방어합니다.

## 8.4 상태 문구 방어

다음과 같은 값만 들어오면 생성 실패 메시지로 바꿉니다.

```text
확인 완료
완료
작성 완료
생성 완료
출력 완료
ok
okay
done
```

## 8.5 모바일 가독성 보정

파싱 후 `format_blocks_for_mobile()`이 적용됩니다.

적용 대상은 `blog_formatter.py`에서 관리합니다.

---

# 9. Podcast 블록 및 TTS 규칙

Prompt에서는 Podcast 화자 태그를 화면 표시용으로 `[남성]`, `[여성]`만 사용합니다.

실제 Podcast API 호출 시 `podcast.py`에서 TTS 엔진용 태그로 변환합니다.

파일 위치:

```text
backend/app/api/podcast.py
```

핵심 함수:

```text
normalize_podcast_speaker_tags(script, male_voice, female_voice)
normalize_phone_numbers_for_tts(text)
```

지원 입력:

```text
[남성]
[여성]
#M
#F
#M1 ~ #M5
#F1 ~ #F5
```

출력 원칙:

```text
#M1
대사

#F1
대사
```

화자 태그는 반드시 단독 행으로 분리해야 합니다.

전화번호는 TTS에 넘기기 전 한국어 발음으로 변환할 수 있습니다.

예:

```text
010-8284-5584
→ 공일공, 팔이팔사, 오오팔사
```

---

# 10. 데이터베이스 구조

DB는 SQLite를 사용합니다.

DB 경로는 환경변수로 관리됩니다.

```text
STORYMAKER_DB_PATH=/data/storymaker.db
```

호스트 실제 바인딩 경로:

```text
/home/bourne/StoryMaker_1/database
```

## 10.1 database.py

파일 위치:

```text
backend/app/db/database.py
```

핵심 설정:

```text
SQLite WAL 모드 활성화
synchronous=NORMAL
foreign_keys=ON
busy_timeout=5000
check_same_thread=False
```

## 10.2 주요 테이블

파일 위치:

```text
backend/app/db/models.py
```

### companies

업체 정보 테이블입니다.

주요 컬럼:

```text
id
name
created_at
updated_at
```

관계:

```text
Company 1:1 Persona
Company 1:N Project
```

### personas

업체 페르소나 설명 테이블입니다.

주요 컬럼:

```text
id
company_id
content
created_at
updated_at
```

### users

사용자 계정 테이블입니다.

주요 컬럼:

```text
id
username
password_hash
role
tier
wp_enabled
is_active
last_login_at
last_activity_at
google_sub
avatar_url
auth_provider
created_at
updated_at
```

중요:

Google 로그인과 WordPress 권한, paid/free tier가 여기에 포함됩니다.

### user_personas

마이페이지에서 관리하는 사용자별 업체 페르소나입니다.

주요 컬럼:

```text
id
user_id
company_name
phone_number
is_default
keywords_json
content
created_at
updated_at
```

고유 제약:

```text
user_id + company_name
```

### user_sessions

사용자 접속 세션 테이블입니다.

주요 컬럼:

```text
user_id
login_at
logout_at
last_seen_at
duration_seconds
ip_address
user_agent
```

### activity_logs

사용자 활동 로그입니다.

주요 컬럼:

```text
user_id
action
target_type
target_id
metadata_json
ip_address
user_agent
created_at
```

### feature_requests

상단 수정요청 버튼으로 남긴 개선 요청 게시판입니다.

주요 컬럼:

```text
user_id
title
content
status
admin_note
created_at
updated_at
```

### projects

StoryMaker 마케팅 프로젝트 핵심 테이블입니다.

주요 컬럼:

```text
id
company_id
user_id
title
base_content
reference_text
keywords
style
ai_preset
generated_prompt
raw_result
parsed_result_json
created_at
updated_at
```

중요:

`generated_prompt`, `raw_result`, `parsed_result_json`은 StoryMaker 결과 재사용과 자동 발행의 핵심입니다.

---

# 11. Docker 컨테이너 구성

파일 위치:

```text
docker-compose.yml
```

## 11.1 storymaker-backend

컨테이너명:

```text
storymaker-backend
```

역할:

FastAPI 백엔드 실행.

포트:

```text
8090:8090
```

실행 명령:

```text
uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
```

주요 볼륨:

```text
./backend:/app
/home/bourne/StoryMaker_1/database:/data
/home/bourne/StoryMaker_1/personas:/data/personas
/home/bourne/StoryMaker_1/output_results:/data/output_results
/home/bourne/StoryMaker_1/exports:/data/exports
/home/bourne/StoryMaker_1/backups:/data/backups
```

주요 환경변수:

```text
STORYMAKER_ENV=production
STORYMAKER_DB_PATH=/data/storymaker.db
STORYMAKER_PERSONA_DIR=/data/personas
STORYMAKER_OUTPUT_DIR=/data/output_results
STORYMAKER_EXPORT_DIR=/data/exports
STORYMAKER_BACKUP_DIR=/data/backups
STORYMAKER_ADMIN_USER=admin
STORYMAKER_ADMIN_PASSWORD=admin
STORYMAKER_JWT_SECRET=...
STORYMAKER_INVITE_CODE=storymaker2026
STORYMAKER_GOOGLE_CLIENT_ID=${STORYMAKER_GOOGLE_CLIENT_ID:-}
PODCAST_API_URL=http://host.docker.internal:8001
SUPERTONIC_API_KEY=${SUPERTONIC_API_KEY}
WORDPRESS_API_URL=${WORDPRESS_API_URL:-http://storymaker_wp/wp-json/wp/v2}
WORDPRESS_USERNAME=${WORDPRESS_USERNAME:-}
WORDPRESS_APP_PASSWORD=${WORDPRESS_APP_PASSWORD:-}
```

주의:

문서에는 실제 secret을 새로 적지 않습니다.

운영 secret은 `.env`에 보관합니다.

## 11.2 storymaker-caddy

컨테이너명:

```text
storymaker-caddy
```

역할:

Caddy reverse proxy.

포트:

```text
8091:80
8444:443
```

주의:

호스트의 80/443은 Nginx Proxy Manager가 사용 중이므로 Caddy는 우회 포트로 운영됩니다.

## 11.3 Plausible Analytics

구성 컨테이너:

```text
plausible-db
plausible-events-db
plausible
```

역할:

방문 분석 및 애널리틱스.

포트:

```text
8000:8000
```

---

# 12. Podcast / Slideshow Upstream 구조

StoryMaker 본체는 Podcast와 Slideshow를 직접 렌더링하지 않고, 별도 upstream API로 프록시합니다.

환경변수:

```text
PODCAST_API_URL=http://host.docker.internal:8001
```

같은 upstream API가 Podcast와 Slideshow 모두에 사용됩니다.

## 12.1 Podcast 흐름

```text
StoryMaker Frontend
→ /api/podcast/run
→ podcast.py
→ normalize speaker tags
→ upstream /api/podcast/run
→ job_id 반환
→ /api/podcast/jobs/{job_id}
→ mp3/srt media proxy
```

미디어 프록시:

```text
/api/podcast/media/{project_key}/mp3
/api/podcast/media/{project_key}/srt
```

## 12.2 Slideshow 흐름

```text
StoryMaker Frontend
→ /api/slideshow/run
→ slideshow.py
→ image uploads + render options
→ upstream /api/slideshow/run
→ job_id 반환
→ /api/slideshow/jobs/{job_id}
→ mp4 media proxy
```

미디어 프록시:

```text
/api/slideshow/media/{filename}
```

Queue API:

```text
GET  /api/slideshow/queue
POST /api/slideshow/queue/{job_id}/stop
```

---

# 13. Mac mini 렌더링 구조

현재 StoryMaker 웹앱 코드에서 Mac mini/Dell 렌더링 분기는 `backend/app/api/slideshow.py`에 있습니다.

폼 필드:

```text
render_target: macmini | dell
```

기본값:

```text
macmini
```

허용 값:

```text
macmini
dell
```

StoryMaker 백엔드는 이 값을 upstream slideshow API로 전달합니다.

```text
render_target = render_target if render_target in {"macmini", "dell"} else "macmini"
```

프론트 화면에는 `slideshow.html`에 다음 선택지가 있습니다.

```text
Mac mini - 숏폼 렌더링 전용
```

중요:

Mac mini 실제 SSH, ffmpeg, 작업 큐, 실패 시 fallback 여부는 이 웹앱 저장소의 FastAPI 코드가 아니라 upstream 렌더링 API 또는 Dell 서버의 별도 스크립트 쪽에서 담당합니다.

이 웹앱의 역할은 다음입니다.

```text
렌더링 대상 선택
→ 이미지/오디오/옵션 업로드
→ upstream API로 전달
→ job 상태 조회
→ mp4 다운로드 프록시
```

---

# 14. WordPress 자동 발행 흐름

파일 위치:

```text
backend/app/api/wordpress.py
```

보고서:

```text
reports/wordpress_auto_draft_20260626.md
```

## 14.1 환경변수

```text
WORDPRESS_API_URL
WORDPRESS_USERNAME
WORDPRESS_APP_PASSWORD
```

예시 구조:

```text
WORDPRESS_API_URL=http://host.docker.internal:8083/wp-json/wp/v2
WORDPRESS_USERNAME=StoryMaker
WORDPRESS_APP_PASSWORD=********
```

실제 비밀번호는 `.env`에만 저장합니다.

## 14.2 권한 체크

함수:

```text
check_wordpress_access(user)
```

조건:

```text
admin 또는 paid 사용자
wp_enabled = True
```

일반 free 사용자는 WordPress 연동을 사용할 수 없습니다.

## 14.3 주요 엔드포인트

```text
GET  /api/wordpress/health
POST /api/wordpress/draft
POST /api/wordpress/draft-from-blocks
```

## 14.4 StoryMaker Blocks → WordPress 변환

함수:

```text
storymaker_blocks_to_wp_request(req)
```

입력 블록:

```text
BLOG_TITLES
BLOG_POST
INSTAGRAM_POST
CARROT_POST
BLOG_HASHTAGS
INSTAGRAM_HASHTAGS
CARROT_HASHTAGS
```

변환 규칙:

```text
BLOG_TITLES 첫 제목 → WordPress title
BLOG_POST → 본문 기본 콘텐츠
INSTAGRAM_POST → 하단 추가 섹션
CARROT_POST → 하단 추가 섹션
해시태그 3종 → WordPress tags_text
BLOG_POST 요약 → excerpt / meta_description
```

## 14.5 WordPress REST API 처리

동작:

```text
카테고리 조회
없으면 생성
태그 조회
없으면 생성
posts 엔드포인트로 글 생성
Rank Math 메타 일부 저장 시도
```

Rank Math 관련 meta key:

```text
rank_math_title
rank_math_description
rank_math_focus_keyword
rank_math_facebook_title
rank_math_facebook_description
rank_math_twitter_title
rank_math_twitter_description
```

주의:

Rank Math 관리자 화면에서 N/A로 보일 경우 WordPress 쪽 meta key REST 등록 또는 Rank Math 전용 저장 방식 확인이 필요합니다.

## 14.6 초안과 발행

허용 status:

```text
draft
pending
private
publish
```

주의:

`draft`는 `/blog/`에 바로 보이지 않습니다.

`publish` 상태만 공개 블로그 목록에 노출됩니다.

---

# 15. StoryMaker Test / Lab 구조

현재 테스트 화면 라우트:

```text
/storymaker-test
```

정적 파일:

```text
backend/app/static/storymaker-test.html
```

관련 API:

```text
POST /api/test/prompt-snapshot
```

목적:

운영 `/storymaker` 화면을 직접 깨지 않고 Prompt, Parser, AI 결과, 자동 저장 기능을 실험하는 공간입니다.

`main.py` 주석에도 TEST ONLY로 명시되어 있습니다.

삭제 시 영향 범위:

```text
main.py의 /storymaker-test 라우트
static/storymaker-test.html
common_nav.js의 TEST ONLY 버튼 블록
```

운영 `/storymaker` 라우트와 `index.html`에는 영향을 주지 않도록 설계되어 있습니다.

---

# 16. Queue / 보관 정책

문서 위치:

```text
docs/beta_queue_plan.md
```

현재 계획:

```text
사용자별 작업 폴더:
/home/bourne/StoryMaker_1/supertonic/user_jobs/{user_id}/{job_id}

작업 큐:
rendering=1
tts=1~2 동시 실행 제한

UI 표시:
대기순번
현재상태
진행률
예상안내

API:
enqueue
status
result
cancel

보관정책:
7일 지난 user_jobs 자동 정리
```

관련 파일:

```text
scripts/cleanup_storymaker_user_jobs.sh
services/storymaker-user-jobs-cleanup.service
services/storymaker-user-jobs-cleanup.timer
```

---

# 17. 현재 구현된 주요 화면

정적 파일 위치:

```text
backend/app/static
```

주요 파일:

```text
dashboard.html
  메인 대시보드

index.html
  StoryMaker 메인 콘텐츠 생성 화면

storymaker-test.html
  Test/Lab 화면

podcast.html
  Podcast Generator 화면

slideshow.html
  Slideshow Generator 화면

queue-monitor.html
  렌더링 큐 모니터 화면

about.html
  소개/랜딩 페이지

common_nav.js
  공통 네비게이션

header-nav.html
  헤더 조각
```

주의:

`index.html`은 30만 바이트가 넘는 큰 파일입니다.

수정 시 반드시 백업하고, 작은 단위로 변경해야 합니다.

---

# 18. 최근 개발 이력 Changelog

## 2026-06-24 ~ 2026-06-25

- FastAPI 기반 StoryMaker 웹앱 구조 정리
- Docker Compose 기반 backend / caddy / plausible 구성
- Google 로그인 설정 문서 작성
- Caddy 및 대시보드 관련 백업 다수 생성
- WordPress 연동 준비

## 2026-06-25

- 관리자 대시보드 및 메뉴 UI 관련 작업
- 공통 네비게이션 정리
- StoryMaker 화면 라우트 안정화
- no-cache 정적 파일 서빙 적용
- 회원가입/로그인 관련 auth bridge 백업 다수 생성

## 2026-06-26

- WordPress 자동 초안 등록 기능 구현
- `/api/wordpress/draft` 추가
- `/api/wordpress/draft-from-blocks` 추가
- BLOG 탭에서 WordPress 초안/즉시 발행 버튼 추가
- WordPress REST API 인증 성공
- WordPress 관리자 글 목록에 StoryMaker 글 생성 확인
- Podcast 화자 태그 `[남성]`, `[여성]` → `#M1`, `#F1` 변환 구조 정리
- Slideshow API에 `render_target` macmini/dell 분기 전달
- Slideshow 기본값 및 자막 관련 UI/옵션 개선
- Queue Monitor 화면 추가
- StoryMaker Test 화면 추가
- Test Prompt Snapshot 저장 API 추가
- user_jobs 7일 자동 정리 계획 및 서비스/timer 파일 추가

## 2026-06-27 기준 확인 사항

- `AI_PROJECT_GUIDE.md` v1.0 생성
- v2.0으로 확장
- 현재 main.py, prompt_builder.py, result_parser.py, models.py, database.py, podcast.py, slideshow.py, wordpress.py, docker-compose.yml, docs, reports를 확인해 문서화

---

# 19. 새 AI가 절대 함부로 수정하면 안 되는 부분

아래 파일과 규칙은 StoryMaker의 뼈대입니다.

수정은 가능하지만 반드시 백업, 영향 범위 확인, 테스트 후 진행해야 합니다.

## 19.1 Prompt 블록명

절대 임의 변경 금지:

```text
BLOG_TITLES
BLOG_POST
CARROT_TITLES
CARROT_POST
PODCAST_50
PODCAST_80
INSTAGRAM_POST
INSTAGRAM_HASHTAGS
CAROUSEL_7
NAVER_PLACE_NEWS
GOOGLE_BUSINESS_POST
BLOG_HASHTAGS
CARROT_HASHTAGS
WORDPRESS_SEO
```

블록명을 바꾸면 Parser, SNS 분리, WordPress 발행이 모두 흔들립니다.

## 19.2 result_parser.py

특히 아래 기능은 보존해야 합니다.

```text
코드블록 추출
[BLOCK:...] 파싱
중복 블록 방어
상태 문구 감지
WORDPRESS_SEO 보정
모바일 가독성 보정 호출
```

## 19.3 prompt_builder.py

Prompt v3.0 규칙은 현재 StoryMaker 출력 품질의 핵심입니다.

다음 규칙은 임의 삭제하면 안 됩니다.

```text
하나의 content 코드블록 출력
14개 블록 강제
상태 문구 금지
모바일 가독성 규칙
BLOG_POST 1500자 이상
Podcast 화자 태그 규칙
WORDPRESS_SEO 규칙
```

## 19.4 database models.py

테이블/컬럼명 변경 금지.

특히 아래 컬럼은 기능 연결점입니다.

```text
users.role
users.tier
users.wp_enabled
users.google_sub
user_personas.is_default
projects.generated_prompt
projects.raw_result
projects.parsed_result_json
```

## 19.5 docker-compose.yml의 볼륨 경로

다음 호스트 경로는 데이터 영속성과 연결되어 있습니다.

```text
/home/bourne/StoryMaker_1/database
/home/bourne/StoryMaker_1/personas
/home/bourne/StoryMaker_1/output_results
/home/bourne/StoryMaker_1/exports
/home/bourne/StoryMaker_1/backups
```

무심코 변경하면 기존 데이터가 안 보일 수 있습니다.

## 19.6 WordPress 인증 정보

`.env`의 WordPress Application Password를 문서나 로그에 노출하지 않습니다.

문서에는 항상 `********`로 표시합니다.

## 19.7 SUPERTONIC_API_KEY

Podcast / Slideshow upstream 인증에 사용됩니다.

노출 금지.

## 19.8 STORYMAKER_JWT_SECRET

JWT 인증 보안 키입니다.

운영 중 임의 변경 시 기존 로그인 세션이 깨질 수 있습니다.

## 19.9 static/index.html

현재 매우 큰 단일 화면 파일입니다.

작은 UI 수정도 예상 밖의 JS 충돌을 만들 수 있습니다.

수정 전 백업 필수.

수정 후 최소 확인:

```text
로그인
프로젝트 선택
통합 프롬프트 생성
AI 결과 붙여넣기
SNS별 분리
BLOG 탭
WordPress 버튼
```

## 19.10 /storymaker-test

Test 화면은 운영 기능을 안전하게 실험하는 공간입니다.

운영 `/storymaker`와 혼동해서 수정하면 안 됩니다.

---

# 20. 새 AI 작업 순서 권장안

새 AI가 작업을 시작하면 다음 순서로 확인합니다.

```text
1. AI_PROJECT_GUIDE.md 읽기
2. docker-compose.yml 확인
3. backend/app/main.py 확인
4. backend/app/core/prompt_builder.py 확인
5. backend/app/core/result_parser.py 확인
6. backend/app/db/models.py 확인
7. 작업 대상 API 또는 HTML 확인
8. 백업 생성
9. 최소 수정
10. py_compile 또는 테스트 실행
11. 브라우저 동작 확인
12. 변경 이력 문서화
```

---

# 21. 테스트 명령 참고

백엔드 재시작:

```bash
cd /workspace/StoryMaker/storymaker-web

docker compose restart storymaker-backend
```

강제 재생성:

```bash
cd /workspace/StoryMaker/storymaker-web

docker compose up -d --force-recreate storymaker-backend
```

WordPress 환경변수 확인:

```bash
cd /workspace/StoryMaker/storymaker-web

docker compose exec storymaker-backend env | grep WORDPRESS
```

Python 문법 확인 예:

```bash
python3 -m py_compile backend/app/main.py
python3 -m py_compile backend/app/api/wordpress.py
python3 -m py_compile backend/app/core/result_parser.py
```

---

# 22. 최종 정리

StoryMaker는 단순 프롬프트 생성기가 아닙니다.

현재는 지역 소상공인 콘텐츠 제작을 중심으로 하지만, 구조상 다음 단계로 확장되고 있습니다.

```text
AI 콘텐츠 생성기
→ SNS 패키지 생성기
→ Podcast 생성기
→ Slideshow 생성기
→ WordPress CMS 등록기
→ 통합 콘텐츠 자동화 플랫폼
```

새로운 AI는 이 프로젝트를 단순 HTML 수정 작업으로 보면 안 됩니다.

Prompt, Parser, Database, Upstream API, WordPress, 렌더링 큐가 서로 맞물린 하나의 생산 라인으로 이해해야 합니다.

이 생산 라인은 작은 톱니 하나가 어긋나면 전체 흐름이 멈춥니다.

그러므로 모든 수정은 작게, 안전하게, 백업 후, 테스트와 함께 진행합니다.
