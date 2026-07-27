# V1 업체정보 카드 삭제 버튼 — persona_id 연결 + 인증/경로 수정 업무일지

- 작성일: 2026-07-27 11:20
- 작업 루트: `/home/bourne/StoryMaker_1`
- 운영 주소: `https://app.mystorymaker.net/v1/?page=business`
- 컨테이너: `storymaker-v1-backend`
- 작업 목적: 업체 카드의 삭제 버튼 클릭 시 "삭제할 업체 정보를 확인하지 못했습니다" 경고만 뜨고
  `DELETE /api/auth/personas/{id}`가 발생하지 않는 문제 해결

## 1. 최초 증상

`/v1/?page=business` 업체 카드에 추가된 삭제 버튼을 눌러도 항상
"삭제할 업체 정보를 확인하지 못했습니다. 페이지를 새로고침한 뒤 다시 시도해 주세요."
경고만 뜨고 `DELETE` 요청 자체가 서버 로그에 나타나지 않았다.

## 2. 1차 조사로 확정한 근본 원인

`index.html`이 실제로 로드하는 React 번들은
`assets/index-uploadui-20260719-v1-errorlog-2.js`인데, 과거 패치는 로드되지 않는
`assets/index-NtZeP01r.js`에 `data-persona-id`를 넣었다. 그래서 브리지 스크립트
(`v1-company-info-ui-tune.js`)가 읽던 `article.dataset.personaId`는 처음부터 빈 값이었다.

## 3. 진행 경과 (시행착오 포함)

### 3-1. 브리지 스크립트 매칭 방식 (1차 시도, 이후 대체됨)

`v1-company-info-ui-tune.js`에 업체명/전화번호 완전 일치 매칭 로직을 넣었으나, 사용자가
Chrome 콘솔의 Self-XSS 붙여넣기 보호로 진단이 어렵다며 더 근본적인 방식을 요청함.

### 3-2. 실제 React 번들에 네이티브 삭제 버튼 추가 (사용자 지시로 채택)

`index-uploadui-20260719-v1-errorlog-2.js`의 업체 카드 컴포넌트(`V8`, map 변수 `z`)에서
"수정" 버튼(`onClick:()=>be(z)`) 바로 뒤에 삭제 버튼을 직접 추가해 `z.id`를 그대로 사용하도록
변경. 브리지 스크립트의 중복 삭제 버튼 생성 로직은 제거함.

### 3-3. 인증 방식 오류 발견 및 수정

최초 구현은 `localStorage.getItem('storymaker_token')`을 읽어 `Authorization: Bearer` 헤더를
직접 붙였다. 그런데 백엔드 `get_current_user()`(`app/api/auth.py:245`)는
`credentials.credentials if credentials else storymaker_token` 순서로 **Authorization
헤더가 있으면 쿠키보다 무조건 우선**한다. 기존 GET/PUT(`nc()`, `zh()`, `Fh()`)은 애초에
Authorization 헤더 없이 쿠키(`credentials:"include"`)만 사용하므로, 새 삭제 함수만 유효하지
않은 헤더를 보내 401을 유발했다. → Authorization 헤더 로직 제거, 쿠키만 사용하도록 수정.

### 3-4. 진짜 원인: `/api/` vs `/v1-api/` 경로 오류 (NPM 라우팅)

인증 방식을 고쳐도 동일하게 401이 재현됨. `docker logs storymaker-v1-backend`에는 해당
`DELETE` 요청이 전혀 찍히지 않아 다른 컨테이너를 의심하고 확인한 결과,
**`docker logs storymaker-backend`(V2, `/home/bourne/StoryMaker` 마운트)에 정확히
`DELETE /api/auth/personas/8 401 Unauthorized`가 찍혀 있었다.**

`nginx-proxy-manager` 설정
(`/home/bourne/nginx-proxy-manager/data/nginx/proxy_host/5.conf`, `app.mystorymaker.net`)을
확인한 결과:

- `location ^~ /v1-api/` → `/api/$1`로 rewrite 후 `192.168.0.32:8011`(V1)로 프록시
- `location ^~ /static/v1/`, `location ^~ /v1/` → `192.168.0.32:8011`(V1)
- 그 외 전부(`location /`, `/api/...` 포함) → 기본 업스트림 `192.168.0.32:8090`(V2,
  `storymaker-backend`)

기존 React 함수(`nc()`, `zh()`, `Fh()`)는 전부 `/v1-api/...`를 호출하는데, 새로 추가한 삭제
함수만 `/api/auth/personas/${z.id}`를 직접 호출해 **V2로 잘못 라우팅**되어 401이 발생한
것이었다. V2는 별도 운영 계열(00_READ_FIRST 절대 수정 금지 대상)이라 그쪽은 전혀 건드리지
않고, 요청 경로만 `/v1-api/auth/personas/${z.id}`로 수정했다.

## 4. 최종 수정 내용

### 수정 파일 (React 번들, 3단계 누적 패치)

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/assets/index-uploadui-20260719-v1-errorlog-2.js`

최종 삽입된 코드(카드 렌더링부, "수정" 버튼 바로 뒤):

```js
o.jsx("button",{className:"shrink-0 rounded-full",
  style:{order:998,marginLeft:"6px",border:"1px solid rgba(239,68,68,.6)",
  background:"rgba(239,68,68,.08)",color:"#dc2626",padding:"4px 12px",
  fontSize:"11px",fontWeight:900,cursor:"pointer"},
  type:"button",onClick:()=>V1DeleteCompanyPersona(z),children:"삭제"})
```

최종 삭제 함수(컴포넌트 `V8` 내부, 기존 목록 재조회 함수 `j()` 재사용):

```js
async function V1DeleteCompanyPersona(z){
  const v1Name=z&&z.company_name?z.company_name:"선택한 업체";
  if(!confirm(`'${v1Name}' 업체 정보를 삭제하시겠습니까?\n\n기존 제작 결과물은 삭제되지 않습니다.`))return;
  try{
    const v1Resp=await fetch(`/v1-api/auth/personas/${z.id}`,{method:"DELETE",credentials:"include"});
    let v1Result=null;
    try{v1Result=await v1Resp.json()}catch{}
    if(!v1Resp.ok||!v1Result||!v1Result.ok)
      throw new Error(v1Result?.detail||v1Result?.message||"업체 정보를 삭제하지 못했습니다.");
    await j()
  }catch(v1Err){
    alert(v1Err instanceof Error?v1Err.message:"업체 정보를 삭제하지 못했습니다.")
  }
}
```

### 부수 수정 파일 (중복 삭제 버튼 제거)

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/v1-company-info-ui-tune.js`

네이티브 삭제 버튼이 생기면서, 기존에 이 파일에 임시로 넣었던 카드 삭제 버튼 생성/매칭 로직과
관련 CSS(`[data-v1-company-delete="1"]`), 헬퍼 함수(`getCardCompanyName`,
`getCardPhoneNumber`)를 모두 제거해 카드당 삭제 버튼이 하나만 남도록 정리함. "수정" 버튼 위치
조정(`order:999`) 로직은 그대로 유지.

## 5. 백업 (모두 `/home/bourne/StoryMaker_1/Backup/` 아래, 시간순)

| 백업 폴더 | 대상 파일 | 단계 |
|---|---|---|
| `V1_WORKING_20260727_101516_company_delete_persona_id_fix_전` | `v1-company-info-ui-tune.js` | 1차 브리지 매칭 시도 전 |
| `V1_WORKING_20260727_104744_react_bundle_delete_button_전` | React 번들 | 네이티브 버튼 최초 삽입 전 |
| `V1_WORKING_20260727_105028_tune_js_remove_dup_delete_전` | `v1-company-info-ui-tune.js` | 중복 로직 제거 전 |
| `V1_WORKING_20260727_110419_react_bundle_delete_button_style_전` | React 번들 | 버튼 order/스타일 인라인화 전 |
| `V1_WORKING_20260727_111212_react_bundle_delete_auth_fix_전` | React 번들 | Authorization 헤더 제거 전 |
| `V1_WORKING_20260727_111730_react_bundle_delete_path_fix_전` | React 번들 | `/api/` → `/v1-api/` 경로 수정 전 |

각 백업 폴더에 `SHA256SUMS.txt`(또는 개별 `sha256sum` 출력) 기록, 생성 직후 `sha256sum -c`로
검증 완료.

## 6. SHA-256 (React 번들, 최초 → 최종)

- 최초(모든 패치 이전, 100% 원본): 별도 미기록 — `V1_WORKING_20260727_104744_react_bundle_delete_button_전`
  백업이 사실상 원본과 동일(그 이전 세션에서 손댄 적 없음)
- 네이티브 버튼 삽입 직후: (2차 백업 이전 상태, 로그 상 확인됨)
- 스타일 인라인화 전: `e9ae9afc4670d915dfb53f2893e3d555aaa65963440ea38d3606ca7afe1398b2`
- 스타일 인라인화 후 / 인증수정 전: `4381d24ec2dd6d4b92f3a187c0b2d3935d4801d2fe0deafafa74cf6b47e064fb`
- 인증수정 후 / 경로수정 전: `38df6769414ba137bcf04c266cb7c246409ae821b00d77d56aa740a3bab8a607`
- **최종(현재 서비스 중)**: `307a92b247f428ac50bfa22370d162e45cc9314f04f7ed7e7212c68e4c475299`

## 7. 검증 결과

### 문법

- 매 단계마다 `node --check index-uploadui-20260719-v1-errorlog-2.js`: 전부 PASS (exit 0)
- `node --check v1-company-info-ui-tune.js`: PASS

### 서빙 확인

- 매 단계마다 로컬(`127.0.0.1:8011`)과 공개 도메인(`https://app.mystorymaker.net`) 양쪽에서
  curl로 패치 내용이 실제 반영됐는지 확인 (HTTP 200, 문자열 매칭)
- 정적 파일이라 컨테이너 재시작 불필요, 즉시 반영됨
- `index-BXSjrHk6.css`에 `border-red-500`, `text-red-400` 클래스가 없음(Tailwind 빌드 시
  퍼지됨)을 확인해 색상/배치는 인라인 `style`로 처리, Tailwind 클래스에 의존하지 않음

### 실제 DELETE 요청 로그 (사용자 실브라우저 클릭, `storymaker-v1-backend`)

```
INFO:     172.27.0.1:33696 - "DELETE /api/auth/personas/8 HTTP/1.1" 200 OK
INFO:     172.27.0.1:57810 - "DELETE /api/auth/personas/7 HTTP/1.1" 200 OK
INFO:     172.27.0.1:57920 - "DELETE /api/auth/personas/6 HTTP/1.1" 200 OK
INFO:     172.27.0.1:34264 - "DELETE /api/auth/personas/1 HTTP/1.1" 200 OK
```

(NPM이 `/v1-api/...`를 `/api/...`로 rewrite한 뒤 V1 컨테이너로 전달하므로, 컨테이너 내부
로그에는 `/api/auth/personas/{id}`로 정상 기록됨)

### DB 검증 (`database/storymaker.db`, `user_personas`)

수정 전(8행, user_id=82 기준 5건):

```
id=1 user_id=82 'StoryMaker v1 테스트 업체'        is_default=0
id=4 user_id=82 '오박사만능인테리어'                is_default=1  (기본)
id=6 user_id=82 '김박사만능인테리어'                is_default=0
id=7 user_id=82 '오박사만능인테리어 2026-07-26 23:24:12' is_default=0
id=8 user_id=82 '이박사 만물상'                     is_default=0
id=2 user_id=81, id=3 user_id=83, id=5 user_id=84  (각 1건, is_default=1)
```

수정 후(4행):

```
id=2 user_id=81 'StoryMaker v1 테스트 업체'  is_default=1  (변화 없음)
id=4 user_id=82 '오박사만능인테리어'          is_default=1  (기본 업체, 삭제 대상 아니었음 → 그대로 유지 확인)
id=3 user_id=83 '오박사만능인테리어'          is_default=1  (변화 없음)
id=5 user_id=84 '엠로지텍'                    is_default=1  (변화 없음)
```

- `id=1,6,7,8` 4건 모두 실제로 행이 삭제됨(전체 8행 → 4행)
- 삭제 대상 4건이 전부 `is_default=0`이었으므로 기본 업체 재지정 로직은 이번 케이스에서
  트리거되지 않았고, 기존 기본 업체(`id=4`)는 변경 없이 그대로 유지됨(별도 확인 필요 항목으로
  남김, 8절 참고)
- 다른 사용자(81, 83, 84) 데이터는 전혀 영향 없음

### 화면 확인

- 사용자가 실제 화면에서 삭제 후 카드가 사라지는 것을 확인함("삭제 됨")

## 8. 정상 확인 항목

- 카드의 "삭제" 버튼이 실제 persona 객체(`z.id`)를 직접 사용해 대상을 정확히 식별함
  (이름/순서 추정 방식 완전히 제거)
- `DELETE /v1-api/auth/personas/{id}` → V1 컨테이너 → `/api/auth/personas/{id}` 정상 라우팅,
  200 OK
- DB 행 실제 감소, 다른 사용자 데이터 영향 없음
- 화면에서 카드 제거 확인(사용자 확인)
- 카드당 삭제 버튼 1개만 존재("수정" 오른쪽 나란히, `order:998`/`999`)
- 신규 업체명 중복 등록 시 409 정책은 이번 작업에서 변경하지 않음(기존 상태 유지)

## 9. 미확인 항목 (다음 확인 필요)

- **기본 업체(`is_default=1`) 삭제 후 다음 업체가 자동으로 기본으로 재지정되는지**는 이번
  케이스에서 실제로 트리거되지 않았다(삭제된 4건이 전부 비기본 업체였음). `personas.py`의
  `delete_my_persona()` 로직상 정상 동작할 것으로 예상되나, 별도로 테스트용 기본 업체를 만들어
  실제 삭제 후 재지정을 확인하는 절차가 남아 있음
- 마지막 남은 1개 업체를 삭제했을 때 "등록된 업체가 없습니다" 문구가 정상 표시되는지 미확인
- 신규 업체 중복 등록 409 및 날짜/시간 접미사 미생성 여부는 이번 세션에서 별도로 재확인하지
  않음(직전 세션에서 이미 반영된 것으로 파악)
- 편집 화면(페르소나 상세 설명 textarea 아래, "수정 저장" 옆) 작은 삭제 버튼 추가는 사용자가
  이번 작업 범위 밖으로 명시적으로 미룸

## 10. 절대 수정 금지 범위 준수 확인

- `storymaker-backend`(V2, `/home/bourne/StoryMaker` 마운트) 컨테이너/코드/DB: 전혀 수정하지
  않음(원인 진단을 위한 `docker logs` 읽기만 수행)
- `nginx-proxy-manager` 설정(`/home/bourne/nginx-proxy-manager/data/...`): 읽기만 수행,
  수정하지 않음
- `BrowserMp4TestPage-CmPBgwv3.js`: 손대지 않음
- `personas.py`, DB 스키마: 이번 세션에서 수정하지 않음(기존 상태 그대로)

## 11. 남은 문제

없음(이번에 보고된 삭제 기능 자체는 정상 동작 확인됨). 9절의 미확인 항목만 후속 검증 대상.

## 12. 다음 작업 순서

1. 테스트용 기본 업체를 하나 만들어 "기본 업체 삭제 → 다음 업체 자동 기본 지정" 시나리오 검증
2. 마지막 1개 남은 업체 삭제 시 빈 상태 문구 확인
3. 사용자 승인 시 편집 화면(수정 저장 옆) 작은 삭제 버튼 추가 — 이번에 만든
   `V1DeleteCompanyPersona(z)` 함수를 그대로 재사용
4. `git status` 확인 후 사용자 승인 시 이번 세션 변경분 커밋 여부 논의
   (`v1-company-info-ui-tune.js`는 신규 미추적 파일, React 번들은 기존 추적 파일이 아니라면
   함께 확인 필요)

## 13. 롤백 방법

가장 안전한 롤백은 7절의 최종 SHA-256과 6절의 백업 목록을 시간 역순으로 사용한다.

완전 롤백(이번 세션 이전 상태로):

```bash
cp "/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260727_104744_react_bundle_delete_button_전/index-uploadui-20260719-v1-errorlog-2.js" \
   "/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/assets/index-uploadui-20260719-v1-errorlog-2.js"

cp "/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260727_101516_company_delete_persona_id_fix_전/v1-company-info-ui-tune.js" \
   "/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/v1-company-info-ui-tune.js"

node --check /home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/assets/index-uploadui-20260719-v1-errorlog-2.js
node --check /home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/v1-company-info-ui-tune.js
```

복원 후 브라우저에서 강력 새로고침하고 업체 정보 화면이 정상 로딩되는지, 콘솔 오류가 없는지
확인한다. 정적 파일이므로 컨테이너 재시작은 필요 없다.

## 14. 최종 판정

**PASS**

- 수정 파일: `storymaker-web/backend/app/static/v1/assets/index-uploadui-20260719-v1-errorlog-2.js`,
  `storymaker-web/backend/app/static/v1/v1-company-info-ui-tune.js`
- 백업: 6개 시점, 전부 `/home/bourne/StoryMaker_1/Backup/` 아래 (5절 표)
- SHA-256(최종): `307a92b247f428ac50bfa22370d162e45cc9314f04f7ed7e7212c68e4c475299`
- `node --check`: PASS
- 실제 `DELETE .../personas/{1,6,7,8} HTTP/1.1 200 OK` 로그 확인
- DB `user_personas` 8행 → 4행, 기본 업체(`id=4`) 및 다른 사용자 데이터 무손상
- 화면 카드 제거 사용자 확인
