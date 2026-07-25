# StoryMaker Beta 2차 도달성 및 근거 검증 보고서

1차 감사 보고서의 내용을 바탕으로 실제 코드의 도달성(Reachability)과 근거를 읽기 전용으로 추적, 검증한 결과입니다.

---

## 1. 서버 FFmpeg 도달성 검증

**추적 대상 함수**: `beta_render_job`, `beta_make_video`, `beta_make_tts`, `beta_run_ffmpeg`

**실제 호출자 및 네트워크 흐름**:
- `beta_jobs.py` 내부의 `POST /beta-api/jobs/{beta_job_id}/render` API는 서버 CPU를 사용해 FFmpeg 렌더링을 수행합니다.
- 프론트엔드의 `static/beta-production.js` (line 546)에 `betaRenderJob()` 함수가 정의되어 있고, 내부에서 위 API를 호출합니다.
- **그러나**, 현재 주력 렌더링 흐름을 담당하는 `static/beta-browser-render.js`를 분석한 결과, 브라우저 단에서 WebGPU/WASM(WasmMediaEncoder) 및 WebCodecs를 통해 브라우저 자체 렌더링을 완주합니다. 렌더링을 마친 뒤에는 서버의 렌더 API를 호출하는 것이 아니라, `POST /beta-api/browser/jobs/{job_id}/upload`를 호출하여 **결과물(mp3, mp4)만 서버에 저장(업로드)**합니다.
- 즉, 서버 FFmpeg API는 현재 주력 UI에서 자동으로 타는 경로가 아닌 **과거 레거시(Legacy) 코드**이거나 특수 상황을 위한 **폴백(Fallback) 경로**로 추정됩니다.

**재분류 결론**:
- 기존: "동시 접속 시 서버 CPU 마비" (Critical)
- **변경**: "레거시 코드에 노출된 서버 마비 위험 (외부 사용자가 해당 렌더 API를 직접 POST 호출 시 서버 CPU를 독점할 수 있는 취약점)" (High).

---

## 2. 인증과 세션 구조 검증 (V1 재사용 경로)

**V1 로그인/세션 분석 (`auth.py`)**:
- 쿠키 이름: `storymaker_token`
- Header: `Authorization: Bearer <token>`
- 쿠키 도메인: `.mystorymaker.net`
- 현재 V1 백엔드(`storymaker-web/backend/app/api/auth.py`)는 `get_current_user` 의존성을 통해 토큰을 파싱하고 세션을 유지합니다.

**Beta API의 V1 인증 재사용 가능성**:
- `beta_jobs.py`를 보면 이미 `GET /v1-profile` 엔드포인트에서 `urllib.request`를 사용해 V1 백엔드의 `http://127.0.0.1:8011/v1-api/auth/personas`로 쿠키와 Authorization 헤더를 프록시 전송하여 인증 정보를 가져오고 있습니다.
- 따라서 Beta API에 별도의 JWT 디코딩 미들웨어를 짜는 대신, V1의 `/v1-api/auth/me` 혹은 기존 `/v1-profile` 검증 로직을 `Depends()` 형태로 묶어 각 API에 주입(Proxy Auth 방식)하면 최소한의 수정으로 인증을 재사용할 수 있습니다.

**현재 API별 인증·소유권 상태 표**:

| API | 목적 | 인증(Login) 확인 여부 | 소유권(Owner) 확인 여부 |
| :--- | :--- | :--- | :--- |
| `GET /jobs` | 작업 목록 조회 | **없음** | **없음 (모든 사용자 작업 반환)** |
| `POST /jobs` | 작업 생성 | **없음** | **없음** |
| `GET /jobs/{id}` | 작업 상세 조회 | **없음** | **없음** |
| `DELETE /jobs/{id}` | 작업 삭제 | **없음** | **없음 (타인 작업 삭제 가능)** |
| `GET /jobs/{id}/file/{name}` | 파일 조회 | **없음** | **없음** |
| `POST /browser/jobs/{id}/upload`| 브라우저 렌더 저장 | **없음** | **없음** |
| `POST /jobs/{id}/thumbnail-studio/settings`| 썸네일 설정 저장 | **없음** | **없음** |
| `POST /jobs/{id}/thumbnail-studio/{temp_id}`| 썸네일 PNG 저장 | **없음** | **없음** |
| `GET /jobs/{id}/thumbnail-studio` | 썸네일 설정 조회 | **없음** | **없음** |
| `GET /archive` (Beta) | 보관함 목록 | **없음** | **없음 (모든 사용자 작업 반환)** |

---

## 3. 최신 작업 자동 연결 개인정보 위험

**경로 검증 (`four-thumbnail/index.html` 의 `findLatestJob` -> `GET /beta-api/jobs`)**:
- `GET /beta-api/jobs`는 `SELECT beta_job_id, title... FROM beta_jobs ORDER BY created_at DESC`를 실행하여 **시스템 전체 사용자의 최신 작업**을 반환합니다.
- `index.html`은 응답받은 배열에서 `status`가 completed나 failed가 아닌 최상단 작업을 무조건 가져와 화면에 바인딩(`title`, `subtitle`, `business`, `phone` 등)합니다.
- **결론**: **사용자 A가 썸네일 스튜디오에 접속하면, 방금 작업을 생성한 사용자 B의 개인정보(업체명, 전화번호, 사진 등)가 화면에 그대로 자동 연결되어 노출**됩니다. Beta production, archive에서도 같은 API를 사용한다면 동일한 문제가 발생합니다.

---

## 4. SQLite 실제 설정 검증

실제 DB 경로(`data/storymaker_beta.db`)에 대해 Python 스크립트로 PRAGMA 및 파일 시스템을 검사한 결과입니다:

- `PRAGMA journal_mode`: **"delete"** (WAL 미적용)
- `PRAGMA busy_timeout`: **5000** (5초)
- `PRAGMA foreign_keys`: **0** (비활성화)
- `PRAGMA synchronous`: **2** (FULL)
- `beta_jobs` 테이블 인덱스: PK(`sqlite_autoindex_beta_jobs_1`)뿐이며 `created_at` 인덱스 부재.
- 컬럼 확인: `user_id` 또는 `owner_id` 컬럼 **없음**.
- 파일 존재: `-wal` 및 `-shm` 파일 **존재하지 않음**.
- **결론**: 추정이 아닌 명백한 사실로, 현재 트래픽이 몰리면 DB Lock 충돌이 일어날 수밖에 없는 구조입니다.

---

## 5. 저장공간 실측

`data/jobs` 하위 최근 100개 작업 폴더를 실측한 결과입니다:

- **작업 당 크기 분표**:
  - 대부분의 작업(이미지 미포함/테스트 등)은 KB 단위로 매우 작으나, 이미지가 포함된 경우 10MB~50MB 수준으로 널뛰기가 큽니다.
  - 최댓값(Max): **59.3MB** (`beta_20260726_042115_edb882`) - input 26MB, output 32MB.

- **저장량 재계산 (평균 50MB 기준)**:
  - 하루 1,500작업 = **75GB / 일**
  - 7일 = **525GB**
  - 30일 = **2.25TB**
  - 90일 = **6.75TB**
  - 실제로는 실패된 찌꺼기 파일과 브라우저 MP4 렌더링 파일까지 합쳐지면 3TB(한 달)에 육박할 것으로 확인됩니다.

---

## 6. 썸네일 API 검증

**`GET /jobs/{beta_job_id}/thumbnail-studio` API의 부작용**:
- 내부 함수 `beta_thumbnail_studio_dir()` 호출 시 `path.mkdir(parents=True, exist_ok=True)`를 실행합니다.
- **결과**: **GET 요청임에도 불구하고 서버의 디렉토리를 생성하는 상태 변경(Mutation)이 일어납니다.**
- **500 에러 재현**: 과거 V1 작업 등 타 소유권(root)으로 생성된 폴더 내부에 접근 시, `mkdir`이 권한 부족으로 실패하며 서버 500 에러를 발생시킵니다.

**JSON 동시 쓰기 충돌 (`result.json`)**:
- 썸네일 PNG를 개별 저장(`POST /.../thumbnail-studio/{template_id}`) 시, `beta_update_job` 등을 쓰지 않고 `result.json`을 통째로 읽어(`beta_read_json`) 수정 후 다시 덮어씁니다(`beta_write_json`).
- **결과**: 브라우저에서 16종을 `Promise.all` 처럼 동시에 쏘면, `result.json` 읽기-쓰기 레이스 컨디션이 발생해 JSON 구조가 파괴되거나 데이터가 증발합니다.

**페이지 이탈 `sendBeacon` 파싱 문제**:
- `application/json` 타입의 Blob으로 `sendBeacon`을 쏠 경우, 일부 브라우저는 CORS 보안 정책상 이를 막거나, FastAPI 측에서 Body를 온전히 읽지 못해 설정 저장이 누락될 가능성이 큽니다.

---

## 7. 보고서 재분류 및 최종 분류

**A. 확정 Critical (즉시 수정 필수)**
1. **API 전역 권한/인증(Auth) 및 소유권 누락 (IDOR, 개인정보 노출)**: 타인 작업 자동 맵핑 및 삭제 조작 가능 (실제 현재 주력 경로에서 재현됨).

**B. 확정 High (공개 전 조치 강권)**
1. **SQLite WAL 모드 부재**: 동시 다발적 썸네일 상태 저장 시 JSON 및 DB Lock 발생 (실측 검증됨).
2. **썸네일 API Race Condition**: `result.json` 동시 읽기/쓰기에 의한 파일 파괴 (실제 재현됨).
3. **GET 요청의 상태 변경 (mkdir)**: Root 소유 폴더 조회 시 500 에러 발생 (실제 재현됨).

**C. 실제 공개 전 필수 수정**
1. 썸네일 개별 16연속 다운로드 로직 방어 (ZIP 다운로드 등으로 UX/네트워크 수정).
2. 일일/작업당 업로드 파일 크기 및 갯수 제한 (Quota 방어벽).

**D. 현재는 건드리면 안 되는 부분 (레거시/폴백 코드)**
1. `beta_render_job`을 위시한 서버 FFmpeg 렌더링 파트. (현재 UI는 브라우저 WebCodecs 기반이므로, 일단 권한 인증만 막아두고 대대적 리팩터링은 유보).

**E. 최소 수정 파일과 함수**
- `beta_jobs.py`: 인증 미들웨어 추가, `mkdir` 위치 변경(GET 밖으로), SQLite 초기화 쿼리에 `WAL` 추가.

**F. 변경 순서**
1. DB WAL 프라그마 추가 및 재시작.
2. V1 `/v1-profile` 의존성을 재사용하는 `Depends(verify_owner)` 작성 후 모든 Beta 라우터에 주입.
3. `beta_jobs.py` `result.json` 동시 쓰기를 막기 위한 파일 락(Lock) 또는 패치 방식 변경.

**G. 롤백 계획**
수정 전 `beta_jobs.py` 원본 파일 및 DB `storymaker_beta.db` 파일 복사 백업 후 에러 시 즉시 롤백.

**H. E2E 검증 계획**
테스트 스크립트로 사용자 A 생성 후 사용자 B가 A의 `beta_job_id` 접근/삭제 시도 시 401/403 응답이 오는지 확인. 16종 썸네일 연속 저장 시 `result.json` 파일 포맷이 유지되는지 검증.
