# StoryMaker Dell V1 보안 2차 조치: 비활성 파일 차단 확장, CSRF Origin 검증, 쿠키 도메인 축소

## 작업 일시

2026-09-02

## 작업 목적

2026-07-27 1차 보안 조치(전체구조 조사보고서, JWT 회전/결과물 접근/Argon2 인수인계, RateLimit 1차적용) 이후 남아 있던 미해결 항목 중 아래 3건을 진행:

- CONF-5 후속: 정적 폴더 백업파일 차단 목록에 `.disabled_` 패턴 누락
- CONF-9: 상태 변경 API에 CSRF Origin 검증 부재
- CONF-7: 인증 쿠키 도메인이 `.mystorymaker.net` 전체에 공유됨

작업 시작 전 `git status --short --branch`로 `/home/bourne/StoryMaker_1`과 `storymaker-web` 모두 클린 상태(브랜치 main, origin과 동일)임을 확인 후 시작했다.

## 수정한 파일

1. `storymaker-web/backend/app/main.py`
   - `NoCacheStaticFiles._BLOCKED_BACKUP_MARKERS` 목록에 `.disabled_` 패턴 추가.
2. `storymaker-web/backend/app/api/auth.py`
   - `_ALLOWED_ORIGIN_HOSTS` 상수와 `_verify_same_origin_request()` 함수 신규 추가(main.py의 CORS allow_origins 4개 도메인과 동일한 목록 재사용).
   - `POST /auth/logout`, `PUT /auth/settings`에 `Depends(_verify_same_origin_request)` 적용.
   - `AUTH_COOKIE_DOMAIN`을 `.mystorymaker.net`에서 `app.mystorymaker.net`(실제 V1 호스트)으로 축소.
   - `_auth_cookie_scope()`의 `is_public_domain` 판정을 `hostname == "app.mystorymaker.net"` 단일 조건으로 축소(기존에는 `mystorymaker.net` 및 모든 하위 서브도메인 전체가 해당됨).

## 생성한 파일

- 본 업무일지
- 아래 3건의 수정 전 백업(모두 `/home/bourne/StoryMaker_1/Backup`)

## 삭제하거나 비활성화한 파일

없음.

## 수정 전 백업 위치

- `Backup/V1_WORKING_20260902_223854_disabled파일차단_수정전/main.py`
- `Backup/V1_WORKING_20260902_224113_CSRF_origin검증_수정전/auth.py`
- `Backup/V1_WORKING_20260902_224333_쿠키도메인축소_수정전/auth.py`

각 백업 디렉터리에서 파일 존재·SHA-256 확인 완료.

## 적용한 변경 내용

### 1. disabled 정적 파일 노출 차단

static/v1 안에 남아 있던 v1-podcast-frontend-recovery.js.disabled_20260723_0648 등 3개 파일이 기존 차단 목록(backup_, before_, bak_, old_, ~)에 걸리지 않아 200으로 그대로 열람 가능했다. 목록에 disabled_ 패턴을 추가해 동일하게 404 처리했다.

### 2. CSRF Origin 검증

auth.py의 상태 변경 라우트 중 비밀번호 변경 라우트는 현재 비밀번호 재확인을 이미 요구하고 있어 Origin 위조만으로는 악용이 사실상 어렵다고 판단해 이번 범위에서 제외했다. 실질적으로 별도 보호가 없던 로그아웃과 설정변경 라우트에 Origin/Referer 검증을 추가했다. Origin과 Referer가 모두 없는 요청(브라우저 외 클라이언트)은 기존 동작을 보존하기 위해 통과시킨다.

### 3. 인증 쿠키 도메인 축소

기존에는 호스트가 mystorymaker.net이거나 그 하위 모든 서브도메인이면 무조건 .mystorymaker.net 전체 공유 쿠키를 발급했다. 이 쿠키는 V1 백엔드가 직접 발급 검증하는 JWT이며 WordPress가 읽거나 쓰지 않는 것을 auth.py 전체 검토로 확인했다. storymaker-beta.service가 Independent Server로 별도 등록되어 있어 V1과 Beta 간 의도된 쿠키 공유(SSO) 근거를 찾지 못했다. 이에 따라 실제 V1 운영 호스트인 app.mystorymaker.net 단일 호스트로 좁혔다.

## 검사 및 테스트 결과

- python3 -m py_compile: main.py, auth.py 각 수정 직후 PASS
- git diff로 각 변경이 의도한 범위만 포함하는지 확인(PASS)
- uvicorn --reload가 매 수정 후 정상 재적재됨을 docker logs storymaker-v1-backend로 확인, 재시작 중 예외 없음
- 내부(127.0.0.1:8011) 확인:
  - disabled 파일: 404 (수정 전 200)
  - index.html, voicebox-studio.js 등 정상 정적 자산: 200 유지
  - 로그아웃, 설정변경 라우트를 인증 없이 호출 시 401(정상, get_current_user가 Origin 검증보다 먼저 평가됨)
- 외부(https://app.mystorymaker.net) 확인:
  - /v1/: 200
  - /v1-api/auth/me(미인증): 401

## 정상 확인 항목

- 세 변경 모두 문법 오류 없이 반영, 서비스가 예외 없이 재기동
- 기존 정적 자산, 인증 실패 응답 동작에 회귀 없음(확인된 범위 내)
- disabled 우회 경로가 실제로 차단됨을 직접 재현 확인

## 미확인 항목

CSRF Origin 검증이 실제 로그인 세션(쿠키 보유 상태)에서 위조 Origin 요청을 403으로 막는지는 실행 검증하지 못했다. 실제 로그인을 수행하지 않는다는 원칙에 따라 유효한 세션 없이는 이 경로를 끝까지 재현할 수 없었다. 코드 검토로는 Depends 순서상 get_current_user가 먼저 평가되므로, 유효한 인증(쿠키 또는 Authorization 헤더)이 있는 요청에서만 Origin 검증이 실행된다. 이는 정확히 CSRF 위협 모델(공격자가 피해자의 유효한 쿠키를 이용)과 일치하지만 end-to-end 실행 증거는 아니다.

쿠키 도메인 축소 이후 실제 로그인 흐름에서 app.mystorymaker.net에 정상적으로 쿠키가 재발급되는지도 같은 이유로 실행 검증하지 못했다. 코드 경로(_auth_cookie_scope)는 정적으로 확인했다.

app.mystorymaker.net 외에 V1 인증 쿠키를 실제로 필요로 하는 다른 서브도메인이 전혀 없다는 것은 코드, 서비스 목록 조사에 근거한 판단이며, 100% 배제는 못한다.

## 남은 문제

2026-07-27 조사 이후 여전히 미해결인 항목:

- 이메일 인증 미검증(가입 시 pending registration 미도입)
- V1 로컬 계정과 WordPress 원장 이원화
- WordPress Application 인증정보 401 추정 지속 여부(재확인 필요)
- 기존 SHA-256 해시 계정의 Argon2 전환 정책 미확정
- except Exception 패턴 199건, 표본 조사만 수행하고 전수 개선은 미착수
- 나머지 상태 변경 API 전체에 대한 CSRF Origin 검증 확대는 이번 범위 밖(가장 위험했던 비밀번호 변경 라우트는 현재 비밀번호 재확인으로 이미 별도 보호되어 있음을 확인)

## 다음 작업 순서

1. 사용자 승인 하에 실제 로그인 세션으로 CSRF 차단, 쿠키 도메인 축소 end-to-end 검증
2. WordPress Application 인증정보 재발급 필요 여부 확인(외부 WordPress 관리자 작업 필요, 이 세션에서 자격증명 미보유)
3. 이메일 인증(pending registration) 설계 및 구현 여부 결정
4. 나머지 상태 변경 API의 CSRF 적용 범위 확대 검토

## 절대 수정 금지 범위

이번 작업에서 V2, Beta, 공용 Supertonic3, 포트 7788, BrowserMp4TestPage-CmPBgwv3.js는 열람 수정하지 않았다.

## 롤백 방법

각 항목의 수정 전 백업 위치에 있는 파일을 그대로 복사해 덮어쓴 뒤, 컨테이너 재적재(docker logs로 reload 확인) 및 위 검증 항목을 재실행한다. 세 변경은 서로 다른 커밋 단위로 분리 가능하므로 문제 발생 시 git diff로 개별 되돌리기도 가능하다.
