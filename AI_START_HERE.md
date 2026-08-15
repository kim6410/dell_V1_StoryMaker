# StoryMaker V1 AI 작업 시작 문서

최종 갱신일: 2026-07-19
대상 서버: Dell Ubuntu
프로젝트 루트: `/home/bourne/StoryMaker_1`
Windows 공유 경로: `\\192.168.0.32\StoryMaker_1`

---

## 1. 이 문서의 목적

이 파일은 AI 작업자가 StoryMaker V1 프로젝트에 처음 진입했을 때 가장 먼저 읽어야 하는 기준 문서다.

이 프로젝트는 기존 StoryMaker V2에서 필요한 기능만 옮겨 와서 만든 별도의 V1 서비스 공간이다. 목표는 단순 테스트 복사본이 아니라, 향후 독립 도메인을 연결해 실제 고객에게 제공할 수 있는 제품 서비스 환경으로 만드는 것이다.

AI는 작업을 시작하기 전에 반드시 이 문서를 끝까지 읽고 다음 원칙을 이해해야 한다.

- V1은 기존 운영 StoryMaker 및 V2 원본과 분리되어야 한다.
- 다른 프로젝트 폴더의 코드, DB, 결과물, 정적 파일을 직접 참조해서는 안 된다.
- 외부 서비스가 필요하면 파일 마운트나 직접 import가 아니라 명시적인 HTTP API로만 연결한다.
- 기존 제작 기능이 정상 작동하는 상태를 최우선으로 보존한다.
- 수정 전에 백업하고, 수정 후 실제 API와 제작 흐름을 검증한다.
- 비밀번호, 토큰, API 키, JWT 비밀값, `.env`, 인증 쿠키, 세션값은 읽거나 출력하지 않는다.

---

## 2. 프로젝트 목표

StoryMaker V1의 최종 목표는 다음과 같다.

1. 독립적인 소스 코드
2. 독립적인 프런트엔드
3. 독립적인 데이터베이스
4. 독립적인 업로드 및 제작 결과물
5. 독립적인 Docker 컨테이너
6. 독립적인 백업 체계
7. 별도 서비스 도메인과 HTTPS
8. 기존 운영 V2와 충돌하지 않는 로그인 및 Worker
9. 필요 외부 서비스는 HTTP API로만 연결
10. 실제 고객이 사용할 수 있는 안정적인 제품 서비스 공간

현재 권장 서비스 도메인 후보는 `studio.mystorymaker.net`이다. 단, 도메인 연결 작업 전에는 반드시 CORS, 쿠키, 로그인 리다이렉트, Worker API 주소, WordPress 연동 주소를 함께 검토해야 한다.

---

## 3. 절대 수정 금지 대상

다음 경로는 V1 작업 중 절대 수정, 삭제, 이동, 빌드, 배포하지 않는다.

```text
/home/bourne/StoryMaker/storymaker-web
/home/bourne/storymaker-v2-app
```

특히 아래 행동을 금지한다.

- V1 작업을 위해 운영 StoryMaker 파일을 수정하는 행위
- V2 React 원본에서 직접 빌드하거나 배포하는 행위
- V2 원본 파일을 V1 정적 폴더로 자동 복사하는 행위
- 운영 DB나 결과물 폴더를 V1에서 마운트하는 행위
- 운영 Worker 설치 경로를 V1에서 제공하는 행위
- 운영 서비스 컨테이너를 재시작하거나 재생성하는 행위

V1에 필요한 기능이 기존 프로젝트에만 존재하더라도, 먼저 구조를 분석한 뒤 필요한 코드만 V1 내부로 복제하고 V1 전용 경로로 수정해야 한다.

---

## 4. V1 루트 구조

기준 루트:

```text
/home/bourne/StoryMaker_1
```

현재 핵심 구조:

```text
/home/bourne/StoryMaker_1/
├── AI_START_HERE.md
├── storymaker-web/            V1 백엔드와 배포용 정적 파일
├── storymaker-v1-app/         V1 프런트엔드 원본
├── database/                  V1 전용 DB
├── personas/                  V1 전용 업체 및 페르소나 데이터
├── output_results/            V1 제작 결과물
├── uploads/                   V1 업로드 원본
├── exports/                   내보내기 및 다운로드 파일
├── tts_cache/                 음성 캐시
├── supertonic/                V1 관련 음원 폴더
├── logs/                      V1 로그
├── backups/                   현재 런타임 백업 마운트 경로
├── Backup/                    구버전, 수동 백업, 격리 파일 통합 보관
├── collect_backups_to_Backup.sh
└── apply_v1_isolation_compose.sh
```

`Backup` 폴더는 활성 코드가 아니다. AI는 `Backup` 안의 파일을 자동으로 import하거나 실행하거나 복원하지 않는다. 복원이 필요한 경우에만 사용자 승인 후 원래 경로와 파일 차이를 확인하고 복구한다.

---

## 5. 현재 Docker 구성

V1 백엔드 컨테이너 이름:

```text
storymaker-v1-backend
```

외부 포트:

```text
8011
```

컨테이너 내부 백엔드 포트:

```text
8090
```

기본 접속 주소:

```text
http://192.168.0.32:8011
```

Docker Compose 위치:

```text
/home/bourne/StoryMaker_1/storymaker-web/docker-compose.yml
```

현재 V1 백엔드 마운트는 다음과 같이 모두 `StoryMaker_1` 내부 경로를 사용해야 한다.

```text
/home/bourne/StoryMaker_1/storymaker-web/backend -> /app
/home/bourne/StoryMaker_1/storymaker-v1-app -> /v1_frontend
/home/bourne/StoryMaker_1/database -> /data
/home/bourne/StoryMaker_1/personas -> /data/personas
/home/bourne/StoryMaker_1/output_results -> /data/output_results
/home/bourne/StoryMaker_1/exports -> /data/exports
/home/bourne/StoryMaker_1/backups -> /data/backups
/home/bourne/StoryMaker_1/supertonic/music -> /data/music
```

다음 외부 마운트는 제거된 상태여야 한다.

```text
/home/bourne/Weather -> /workspace/Weather
```

확인 명령:

```bash
docker inspect storymaker-v1-backend \
  --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

출력에 `/home/bourne/Weather`, `/home/bourne/StoryMaker`, `/home/bourne/storymaker-v2-app`이 나타나면 고립이 깨진 것이다.

---

## 6. 현재 고립 상태에서 이미 처리된 항목

다음 항목은 이미 V1에서 제거 또는 차단되었다.

### 6.1 V2 자동 배포 라우트 차단

파일:

```text
storymaker-web/backend/app/api/admin_deploy.py
```

현재 이 파일은 다른 모듈의 import 오류를 방지하기 위해 빈 `router`만 제공하는 차단 모듈이다. V2 프런트 자동 배포 기능을 다시 구현하거나 활성화하지 않는다.

### 6.2 V2 배포 스크립트 제거

기존 파일:

```text
storymaker-web/tools/deploy_static_v2_from_dist.py
```

활성 도구 폴더에서 제거되었다. 이 파일 또는 동일 기능을 다시 만들지 않는다.

### 6.3 불필요한 Prompt Builder 복사본 제거

기존 파일:

```text
storymaker-web/backend/app/core/prompt_builder - 복사본.py
```

활성 코드 폴더에서 제거되었다. 실제 사용 파일은 정확한 import 경로를 확인한 뒤 수정한다.

### 6.4 외부 Weather 폴더 마운트 제거

Compose에서 다음 마운트가 제거되었다.

```text
/home/bourne/Weather:/workspace/Weather:ro
```

날씨 기능은 HTTP API, Home Assistant API 또는 Open-Meteo fallback을 사용한다. 외부 Weather 소스 폴더를 다시 마운트하지 않는다.

### 6.5 V1 Worker와 운영 Worker 구분

V1 Worker 표시 이름은 운영 Worker와 혼동되지 않도록 별도 이름을 사용한다.

```text
StoryMaker V1 ONLY - Isolated Gemini Worker
```

V1 Worker 설치 경로:

```text
http://192.168.0.32:8011/v1/storymaker-gemini-worker-v1.user.js
```

구 운영 Worker 설치 경로는 V1에서 제공하지 않는다.

### 6.6 운영 도메인 이동 지뢰 제거

V1의 메뉴, 로그인, 팟캐스트 이동은 가능한 한 현재 서버의 상대경로를 사용한다. 단, Gemini userscript는 `gemini.google.com`에서 실행되므로 API 호출용 명시적 백엔드 주소가 필요할 수 있다. 이 값을 무작정 상대경로로 변경하면 Worker가 Gemini 도메인으로 요청을 보내게 되므로 반드시 실행 위치를 고려한다.

---

## 7. 중요한 활성 파일

작업 전 실제 로딩 여부를 반드시 확인해야 한다.

### 백엔드

```text
storymaker-web/backend/app/main.py
storymaker-web/backend/app/settings.py
storymaker-web/backend/app/api/
storymaker-web/backend/app/core/
storymaker-web/backend/app/static/
```

### V1 정적 화면

```text
storymaker-web/backend/app/static/v1/index.html
storymaker-web/backend/app/static/v1/assets/
```

활성 번들 파일명은 변경될 수 있다. `index.html`에서 실제 로딩되는 JS와 CSS를 확인한 뒤 수정한다.

### V1 Worker

```text
storymaker-web/backend/app/static/v1/storymaker-gemini-worker-v1.user.js
```

Worker를 수정할 때는 다음을 함께 확인한다.

- `@name`
- `@namespace`
- `@version`
- `@updateURL`
- `@downloadURL`
- API 백엔드 주소
- CORS 허용 여부
- 현재 응답만 수집하는 로직
- 중복 Worker 설치 여부

### 인증 및 공통 메뉴

```text
storymaker-web/backend/app/static/app_auth.js
storymaker-web/backend/app/static/common_nav_unified.js
storymaker-web/backend/app/static/user_mode_split.js
```

이 파일들이 실제 V1 화면에서 로딩되는지 먼저 확인한다. 로딩되지 않는 파일을 수정해도 효과가 없으며, 로딩되는 파일을 모르고 삭제하면 로그인과 메뉴가 깨질 수 있다.

---

## 8. 외부 서비스 의존성 정책

V1은 완전 오프라인 제품이 아니다. 일부 외부 서비스는 기능상 필요하다. 단, 연결 방식은 HTTP API만 허용한다.

허용 가능한 외부 서비스 예:

```text
Podcast/TTS API
Weather API
Home Assistant API
WordPress REST API
Gemini 웹 및 Worker 연동
Open-Meteo API
```

금지되는 연결 방식:

- 외부 프로젝트 소스 폴더를 Docker volume으로 마운트
- 외부 프로젝트 Python 모듈을 `sys.path`에 추가
- `/home/bourne/StoryMaker` 코드 직접 import
- `/home/bourne/storymaker-v2-app` 파일 자동 복사
- 외부 DB 파일을 V1 DB처럼 직접 열기

외부 API가 장애일 때 V1 핵심 화면 전체가 죽지 않도록 timeout과 fallback을 둔다.

---

## 9. 비밀정보 및 보안 규칙

AI는 다음 파일과 값을 읽거나 출력하지 않는다.

```text
.env
.env.*
wp-config.php
secrets
secret keys
API keys
JWT secrets
passwords
tokens
cookies
session values
application passwords
```

Docker Compose에 비밀값이 직접 들어 있어도 채팅이나 보고서에 값을 복사하지 않는다. 제품 공개 전에는 비밀값을 별도 환경 파일 또는 Docker secret 방식으로 분리하고 새 값으로 교체해야 한다.

보안 수정 시 원칙:

1. 현재 값은 출력하지 않는다.
2. 변수 이름만 확인한다.
3. 새 비밀값은 사용자가 직접 입력하거나 안전한 환경변수로 주입한다.
4. 변경 후 기존 로그인, Worker, WordPress 연동을 실제 테스트한다.
5. 비밀값이 포함된 파일은 백업 위치와 권한도 확인한다.

---

## 10. 백업 정책

모든 수정은 백업 후 진행한다.

권장 백업 루트:

```text
/home/bourne/StoryMaker_1/Backup
```

백업 파일 수집 스크립트:

```bash
bash /home/bourne/StoryMaker_1/collect_backups_to_Backup.sh
```

실제 이동:

```bash
bash /home/bourne/StoryMaker_1/collect_backups_to_Backup.sh --apply
```

이 스크립트는 `.bak`, `.backup`, `.old`, `.orig`, `_before_`, `codex_backup`, `quarantine_unused` 등 정리 대상을 `Backup/collected_날짜시간` 아래 원래 상대경로를 보존하여 이동한다.

AI가 새 백업 파일을 만들 때는 다음 형식을 권장한다.

```text
파일명.before_작업명_YYYYMMDD_HHMMSS.bak
```

중요한 작업은 수정 파일 백업 외에도 다음을 기록한다.

- 작업 일시
- 수정 목적
- 수정 파일 목록
- 원래 동작
- 변경 내용
- 검증 결과
- 롤백 방법

---

## 11. 표준 작업 절차

AI는 모든 작업에서 다음 순서를 지킨다.

### 1단계: 요청 범위 확인

- 사용자가 원하는 최종 결과를 한 문장으로 정리한다.
- V1 내부 작업인지 확인한다.
- 운영 StoryMaker 또는 V2 원본에 손댈 필요가 없는지 확인한다.

### 2단계: 실제 로딩 구조 확인

- 프런트는 `index.html`에서 실제 JS/CSS 파일을 확인한다.
- 백엔드는 `main.py`와 router include 구조를 확인한다.
- Docker는 실제 Mounts와 Ports를 확인한다.
- systemd와 Docker 중 어느 방식으로 실행 중인지 확인한다.

### 3단계: 고립성 검사

다음 문자열을 활성 코드에서 검색한다.

```text
/home/bourne/StoryMaker/
/home/bourne/storymaker-v2-app
/workspace/Weather
/v2_frontend
app.mystorymaker.net
/userscript/storymaker-gemini-worker.user.js
```

검색 결과가 나왔다고 무조건 삭제하지 않는다. 외부 API URL인지 파일 경로인지 구분한다.

### 4단계: 백업

수정 대상 파일별 백업을 남긴다. 대규모 변경이면 전체 관련 폴더 백업도 고려한다.

### 5단계: 최소 수정

- 필요한 부분만 수정한다.
- 기존 제작 엔진, Queue, Worker, FFmpeg 흐름을 대공사하지 않는다.
- 새 API나 새 Worker를 만들기 전에 기존 V1 기능을 재사용할 수 있는지 확인한다.

### 6단계: 문법 검사

Python:

```bash
python3 -m compileall -q /home/bourne/StoryMaker_1/storymaker-web/backend/app
```

JavaScript 파일이 Node에서 검사 가능한 일반 JS라면:

```bash
node --check 대상파일.js
```

번들 JS는 minified 구조나 브라우저 전용 문법 때문에 `node --check`가 모든 오류를 보장하지 않는다. 실제 브라우저 테스트가 필요하다.

### 7단계: 컨테이너 적용

소스가 `/app`으로 bind mount되어 있고 uvicorn reload가 활성화된 경우 작은 Python 수정은 자동 반영될 수 있다. 하지만 Compose의 volume, environment, port, container 설정을 변경했다면 반드시 컨테이너를 재생성한다.

```bash
cd /home/bourne/StoryMaker_1/storymaker-web
docker compose up -d --force-recreate storymaker-backend
```

컨테이너 이름 충돌 시:

```bash
docker rm -f storymaker-v1-backend
cd /home/bourne/StoryMaker_1/storymaker-web
docker compose up -d --force-recreate storymaker-backend
```

### 8단계: 로그 확인

```bash
docker logs --tail 100 storymaker-v1-backend
```

정상 기준:

```text
Application startup complete
```

### 9단계: 기능 검증

최소 확인 항목:

- V1 메인 화면 접속
- 로그인 및 세션
- 업체 선택 또는 페르소나 로딩
- 글 제작
- Gemini Worker 요청과 결과 수신
- 썸네일 생성 및 조회
- 팟캐스트 생성
- 숏폼 MP4 생성
- 보관함 또는 결과물 조회
- 서로 다른 작업 ID의 결과가 섞이지 않는지 확인

### 10단계: 결과 보고

보고에는 반드시 포함한다.

- 수정 파일
- 백업 위치
- 변경 내용
- 재시작 또는 재생성 여부
- 검증 결과
- 남은 위험 요소
- 사용자가 SSH에서 실행해야 할 명령

---

## 12. 절대 하면 안 되는 작업

다음 작업은 사용자 명시 승인 없이 하지 않는다.

```text
npm run deploy
운영 V2 npm run build
운영 StoryMaker 컨테이너 재시작
DB 구조 대규모 변경
기존 결과물 전체 삭제
uploads 삭제
output_results 삭제
tts_cache 전체 삭제
Worker 전체 교체
로그인 구조 전면 개편
새 Queue/Worker/제작 엔진 추가
```

특히 파일 이름에 `v2`가 들어 있다고 해서 V2 원본이라는 뜻은 아닐 수 있다. V1 복사 과정에서 환경변수나 폴더 이름이 그대로 남은 경우가 있으므로 실제 경로와 역할을 확인해야 한다.

---

## 13. 도메인 연결 전 필수 점검

V1을 제품 서비스 공간으로 공개하기 전에 다음을 모두 확인한다.

### 인프라

- 별도 도메인 결정
- Nginx Proxy Manager 또는 Cloudflare Tunnel 연결
- HTTPS 인증서
- HTTP -> HTTPS 강제
- WebSocket 지원
- 업로드 용량 제한
- 장시간 제작 API timeout

### 애플리케이션

- CORS 허용 도메인
- 쿠키 Domain, Secure, SameSite
- 로그인/회원가입 리다이렉트
- 로그아웃 후 이동 주소
- Worker API 주소
- 정적 파일 절대 URL
- 팟캐스트 및 숏폼 결과 URL
- WordPress 콜백 및 API URL

### 보안

- 기본 관리자 계정 제거 또는 변경
- JWT secret 교체
- 초대 코드 정책 재검토
- 민감값 Compose 직접 기록 제거
- 관리자 전용 API 확인
- 사용하지 않는 debug/test API 차단
- 디렉터리 목록 노출 방지
- 로그에 토큰이나 개인정보가 남지 않는지 확인

### 운영

- DB 자동 백업
- 결과물 보관 정책
- 디스크 사용량 경고
- 컨테이너 자동 재시작
- health check
- 장애 시 롤백 절차
- 도메인 변경 후 실제 고객 흐름 테스트

---

## 14. 현재 권장 도메인 연결 예시

후보:

```text
studio.mystorymaker.net
```

Nginx Proxy Manager 예시:

```text
Domain Names: studio.mystorymaker.net
Scheme: http
Forward Hostname/IP: 192.168.0.32
Forward Port: 8011
Websockets Support: ON
Block Common Exploits: ON
SSL: Let's Encrypt
Force SSL: ON
HTTP/2: ON
```

단, 실제 적용 전 DNS, Cloudflare Proxy, 기존 Tunnel, 내부 포트 충돌을 확인한다.

---

## 15. 현재 알려진 주의점

1. `docker-compose.yml`의 `version` 키는 최신 Compose에서 obsolete 경고가 날 수 있다. 기능 장애는 아니며 나중에 제거 가능하다.
2. `backups` 폴더는 Docker에서 `/data/backups`로 마운트된다. 통합 `Backup/runtime_backups`로 옮길지 결정하기 전에는 무작정 삭제하지 않는다.
3. Gemini Worker는 Gemini 페이지에서 실행되므로 Worker의 백엔드 URL을 상대경로로 바꾸면 잘못된 도메인으로 요청할 수 있다.
4. 외부 Weather 폴더 마운트는 제거됐지만 날씨 HTTP API 의존성은 남아 있을 수 있다. 이는 정상 서비스 의존성이다.
5. V1 폴더 안에도 과거 V2 명칭이 환경변수나 함수명으로 남아 있을 수 있다. 이름만 보고 제거하지 말고 실제 역할을 확인한다.
6. `Backup` 폴더의 백업 파일이 검색 결과에 섞이지 않도록 활성 코드 검색 시 제외한다.

---

## 16. 빠른 상태 확인 명령

컨테이너 상태:

```bash
docker ps --filter name=storymaker-v1-backend
```

로그:

```bash
docker logs --tail 100 storymaker-v1-backend
```

마운트:

```bash
docker inspect storymaker-v1-backend \
  --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

포트 확인:

```bash
curl -I http://127.0.0.1:8011
```

Python 문법 검사:

```bash
python3 -m compileall -q /home/bourne/StoryMaker_1/storymaker-web/backend/app
```

외부 프로젝트 경로 검색 예시:

```bash
grep -RIn \
  --exclude-dir=Backup \
  --exclude-dir=.git \
  --exclude-dir=node_modules \
  --exclude='*.bak*' \
  -E '/home/bourne/StoryMaker/|/home/bourne/storymaker-v2-app|/workspace/Weather' \
  /home/bourne/StoryMaker_1
```

민감 파일은 검색하거나 출력하지 않는다.

---

## 17. AI 작업 시작 체크리스트

AI는 실제 수정 전에 아래 항목을 스스로 확인한다.

- [ ] 이 문서를 읽었다.
- [ ] 작업 대상이 `/home/bourne/StoryMaker_1` 내부인지 확인했다.
- [ ] 운영 StoryMaker와 V2 원본을 수정하지 않는다.
- [ ] 실제 로딩 파일과 router를 확인했다.
- [ ] 외부 폴더 참조 여부를 검사했다.
- [ ] 비밀정보를 읽거나 출력하지 않는다.
- [ ] 수정 전 백업 계획이 있다.
- [ ] 최소 수정으로 해결한다.
- [ ] 문법 검사와 실제 기능 테스트 계획이 있다.
- [ ] Compose 변경이면 컨테이너 재생성이 필요함을 이해했다.
- [ ] 완료 후 수정 파일, 백업, 검증 결과를 보고한다.

---

## 18. 최우선 운영 원칙

이 프로젝트에서 가장 중요한 것은 새로운 기능을 빨리 추가하는 것이 아니다.

가장 중요한 것은 다음 세 가지다.

1. 기존 정상 제작 흐름을 깨지 않는다.
2. V1이 다른 프로젝트 코드와 데이터에 영향을 받지 않게 한다.
3. 실제 고객이 사용할 수 있을 만큼 안정적이고 복구 가능한 구조를 만든다.

불확실한 상태에서 대규모 수정하지 않는다. 먼저 읽고, 경로를 확인하고, 백업하고, 최소 수정하고, 검증한다.

이 문서와 실제 코드가 다를 경우 실제 코드와 Docker 상태를 우선 확인하되, 차이가 발견되면 작업 결과 보고에 반드시 기록하고 이 문서도 함께 갱신한다.
