# 2026-09-18 StoryMaker V1 지역 행사 API 2단계 준비 업무일지

## 1. 목적

한국관광공사 TourAPI 기반 지역 축제/관광 데이터의 1차 연동과 일일 DB 동기화 구조가 완료된 상태에서, 다음 단계로 **서울 열린데이터광장 → 경기데이터드림 → 울산/기타 지자체 축제·문화행사 API**를 추가하기 위한 준비사항만 정리한다.

이번 문서에서는 **추가 API를 실제 호출하거나 운영 DB에 연결하지 않는다.**

목표는 다음 채팅/작업자가 바로 착수할 수 있도록:

- 어떤 API를 우선 붙일지
- 인증키 발급이 필요한지
- 어떤 필드를 공통 DB로 정규화할지
- 중복 행사를 어떻게 판단할지
- 수집 주기와 우선순위를 어떻게 잡을지
- 현재 TourAPI 구조를 어떻게 재사용할지

를 명확히 남기는 것이다.

---

## 2. 현재 완료 상태

### 운영 대상

- StoryMaker V1: `https://app.mystorymaker.net/v1/`
- Dell repo: `/home/bourne/StoryMaker_1`
- Backend: `/home/bourne/StoryMaker_1/storymaker-web/backend`
- Backend container: `storymaker-v1-backend`

### 현재 구현된 공공데이터 수집 구조

```text
한국관광공사 TourAPI
        ↓
매일 03:20 일일 동기화
        ↓
StoryMaker SQLite
        ↓
public_event_regions
public_events
public_places
public_event_sync_runs
        ↓
Gemini 최종 프롬프트
```

### 현재 원칙

1. 프롬프트 생성 시 외부 API 직접 호출 금지
2. 외부 공공 API는 하루 1회 수집
3. DB에 저장 후 프롬프트는 DB만 조회
4. API 장애 시 전날 DB 자료로 계속 생성
5. `source + source_id` 기준 UPSERT
6. 지역/축제/관광 데이터는 Gemini SEO 보조자료로 사용
7. 업체가 행사에 참여/협찬했다고 임의 생성하지 않도록 프롬프트에 명시

### 1차 관련 커밋

```text
680e370 feat: add TourAPI local SEO context
d516d84 fix: parse TourAPI legal district codes
3c500c4 feat: sync TourAPI data daily to local DB
a2e58b4 docs: record TourAPI local SEO daily sync rollout
```

---

# 3. 2단계 우선순위

## 우선순위 1 — 서울 열린데이터광장

목표:

- TourAPI에서 누락되는 서울 지역 문화행사 보강
- 구청/공공문화시설/문화포털 기반 행사 보완
- 소규모 지역 행사 및 생활권 콘텐츠 보강

### 1차 후보 API

**서울시 문화행사 정보**

서비스명:

```text
culturalEventInfo
```

공식 데이터셋:

```text
https://data.seoul.go.kr/dataList/OA-15486/A/1/datasetView.do
```

기본 호출 형식:

```text
http://openapi.seoul.go.kr:8088/{KEY}/json/culturalEventInfo/{START_INDEX}/{END_INDEX}/
```

공식 메타정보 기준:

- 갱신주기: 매일 1회
- 분류: 문화/관광
- 원본: 서울문화포털
- JSON 사용 가능
- START_INDEX / END_INDEX 페이징
- 1회 최대 1,000건 범위 사용 가능

### 추가 후보

**서울시 공공서비스예약(종합) 정보**

목적:

- 문화행사
- 교육
- 체험
- 공공서비스 예약 기반 지역 이벤트 보강

공식 데이터셋:

```text
https://data.seoul.go.kr/dataList/OA-20497/A/1/datasetView.do
```

향후 문화/행사 카테고리만 필터링해 보조 source로 사용할지 검토한다.

### 인증

서울 열린데이터광장 별도 인증키 필요.

절차:

```text
서울 열린데이터광장 로그인
→ Open API 인증키 신청
→ 일반 인증키 발급
→ StoryMaker secret/env에 저장
```

권장 환경변수명:

```text
SEOUL_OPEN_API_KEY
SEOUL_OPEN_API_BASE=http://openapi.seoul.go.kr:8088
```

### Collector 후보 파일

```text
backend/app/integration/public_sources/seoul_events.py
```

---

# 4. 경기데이터드림 준비

## 목표

- 경기도 31개 시군 행사/문화행사 보강
- TourAPI에 없는 시군 단위 생활 행사 보완
- `SIGUN_CD` 기반 지역 필터 활용

### 우선 검토 데이터셋

**경기도 문화 행사 현황**

공식 사이트:

```text
https://data.gg.go.kr
```

데이터셋 후보:

```text
경기도 문화 행사 현황
```

경기도 내 문화 예술 관련 전시·공연·교육·행사 정보가 제공되는 데이터셋을 우선 대상으로 한다.

### 경기 OpenAPI 기본 구조

Base:

```text
https://openapi.gg.go.kr
```

일반 인자:

```text
KEY
Type=json
pIndex
pSize
```

특징:

- 인증키 없이 `sample` 사용 시 5건 정도 제한
- 정식 인증키 발급 필요
- 1회 최대 1,000건
- `SIGUN_CD` 같은 시군 필터를 데이터셋에 따라 활용 가능
- 요청횟수 제한은 공식 이용안내상 별도 제한 없음으로 안내됨

### 인증키 발급

```text
경기데이터드림 로그인
→ OpenAPI
→ 인증키 발급
→ 활용용도 입력
→ 활용 URL 입력
→ 발급 요청
```

권장 환경변수명:

```text
GYEONGGI_OPEN_API_KEY
GYEONGGI_OPEN_API_BASE=https://openapi.gg.go.kr
```

### Collector 후보 파일

```text
backend/app/integration/public_sources/gyeonggi_events.py
```

### 주의사항

경기데이터드림에는 비슷한 이름의 과거/현재 데이터셋이 여러 개 검색될 수 있으므로 실제 개발 시작 시 다음을 반드시 확인한다.

1. 데이터 기준일 최신성
2. Open API 제공 여부
3. 행사 시작/종료일 제공 여부
4. 시군코드 제공 여부
5. 주소/좌표 제공 여부
6. 원본 URL/행사 URL 제공 여부

---

# 5. 울산광역시 준비

## 목표

사용자 콘텐츠에서 울산 지역 활용도가 높으므로 우선순위를 높게 둔다.

특히 다음 지역을 세밀하게 보강한다.

```text
울산 북구
울산 중구
울산 남구
울산 동구
울주군
```

### 울산 데이터 제공 구조

울산광역시 데이터포털:

```text
https://data.ulsan.go.kr
```

울산 데이터포털은 공공데이터포털 계정/서비스키 체계와 연계하여 Open API 활용신청을 진행하는 구조이다.

기본 절차:

```text
공공데이터포털 회원가입/로그인
→ 울산 데이터포털 Open API 검색
→ 활용신청
→ 공공데이터포털 활용신청 화면
→ 개발계정 승인
→ 서비스키 발급
```

### 다음 작업에서 조사할 API 범위

```text
울산광역시 문화행사
울산광역시 축제
울산 관광행사
울산 문화재단 행사
울산 북구 문화행사
울산 중구 문화행사
울산 남구 문화행사
울산 동구 문화행사
울주군 축제/행사
```

### 우선 조사 방법

1. 울산 데이터포털 검색
2. 공공데이터포털에서 제공기관 `울산광역시` + 키워드 `축제`, `행사`, `문화행사` 검색
3. API가 없고 파일 데이터만 있는 경우 일일/주간 파일 동기화 가능 여부 검토
4. 구청/문화재단 공식 API가 없다면 RSS/공공데이터/공개 JSON 등 합법적 공개 채널 확인

### 환경변수 후보

공공데이터포털 서비스키를 별도로 요구할 경우:

```text
ULSAN_OPEN_API_KEY
```

단, TourAPI와 동일한 공공데이터포털 키를 재사용 가능한지 여부는 실제 API 신청 후 명세 기준으로 확인한다.

### Collector 후보 파일

```text
backend/app/integration/public_sources/ulsan_events.py
```

---

# 6. 기타 지자체 확장 준비

서울/경기/울산 안정화 이후 다음 순서로 확장 가능하다.

```text
부산
대구
인천
대전
광주
세종
제주
강원
충북
충남
전북
전남
경북
경남
```

모든 지자체 API를 처음부터 붙이지 않는다.

우선 기준:

1. StoryMaker 사용자 등록 지역 수
2. TourAPI 누락률
3. 데이터 갱신주기
4. API 안정성
5. 행사 시작/종료일 품질
6. 이미지/주소/좌표 제공 여부
7. 이용허락/저작권 조건

---

# 7. 공통 수집 구조 준비안

다음 작업부터는 source별 수집기를 공통 구조로 정리하는 것이 좋다.

권장 디렉터리:

```text
backend/app/integration/public_sources/
├── __init__.py
├── base.py
├── tourapi.py
├── seoul_events.py
├── gyeonggi_events.py
├── ulsan_events.py
└── normalize.py
```

현재 `public_events.py`, `public_events_store.py`를 즉시 이동하지는 않는다.

다음 API가 실제로 2개 이상 추가될 때 리팩터링하는 것이 안전하다.

---

# 8. 공통 데이터 모델 확장 준비

현재 `public_events`는 TourAPI 중심으로 설계되어 있다.

다중 source를 붙일 때 아래 필드 추가를 검토한다.

```text
source                 tourapi / seoul / gyeonggi / ulsan
source_id              원본 API의 고유 ID
source_url             원본 행사 상세 URL
source_priority        병합 우선순위
canonical_key          중복판정용 해시/키
category               축제/공연/전시/체험/교육 등
organizer              주최/주관
homepage               행사 홈페이지
lat
lng
image
image_license
copyright_text
raw_json                필요 시 원본 일부 보관
source_updated_at
synced_at
```

현재 필드를 바로 변경하지 않고, 다음 실제 API 명세를 확인한 후 마이그레이션한다.

---

# 9. 중복 행사 통합 준비

동일 행사가 여러 API에 동시에 존재할 가능성이 높다.

예:

```text
한국관광공사 TourAPI
서울 문화행사 API
서울 공공서비스예약
```

세 소스에 같은 축제가 존재할 수 있다.

### 1차 canonical key 후보

```text
normalize(title)
+ start_date
+ end_date
+ normalize(address/district)
```

### 중복 판단 보조

- 제목 유사도
- 날짜 동일/중첩
- 주소 동일
- 좌표 근접
- 홈페이지 URL 동일

### 병합 우선순위 원칙

단순히 한 source를 삭제하지 않는다.

예:

```text
행사명/기간: 공식 지자체 source 우선
이미지: 저작권 조건이 명확한 source 우선
상세설명: 더 풍부한 source 우선
좌표: 정상값이 있는 source 우선
```

병합된 결과는 Gemini에 1건만 전달한다.

---

# 10. 일일 수집 스케줄 준비안

모든 API를 동시에 03:20에 호출할 필요는 없다.

권장 분산 스케줄:

```text
03:20 TourAPI
03:35 서울
03:45 경기
03:55 울산
04:10 기타 지자체
```

장점:

- 외부 API 동시 장애/지연 영향 감소
- 로그 분석 쉬움
- API별 실패 재시도 분리
- DB write lock 집중 방지

실제 스케줄은 다음 API 구현 시 확정한다.

---

# 11. 수집 상태 모니터링 준비

현재 `public_event_sync_runs`는 TourAPI 1개 source 중심이다.

다중 source가 붙을 때 다음 필드/테이블 확장을 검토한다.

```text
source
sync_date
started_at
finished_at
status
rows_received
rows_inserted
rows_updated
rows_merged
api_calls
error_message
```

관리자 화면 또는 API에서 다음 형태로 확인 가능하게 하는 것이 좋다.

```text
TourAPI     성공 03:20 / 325건
서울        성공 03:35 / 428건
경기        성공 03:45 / 611건
울산        실패 03:55 / 재시도 예정
```

---

# 12. Gemini 프롬프트 적용 원칙

새로운 API가 추가되어도 Gemini 지침 자체를 source별로 늘리지 않는다.

Gemini에게는 **정규화/중복제거가 끝난 최종 지역 이벤트 컨텍스트**만 제공한다.

```text
외부 source 4개
    ↓
수집
    ↓
정규화
    ↓
중복 제거/병합
    ↓
DB
    ↓
Gemini에는 하나의 지역 SEO 컨텍스트
```

즉 Gemini는 데이터가 TourAPI인지 서울시인지 경기인지 알 필요가 없다.

프롬프트에는 원출처 요약만 기록한다.

---

# 13. API 키 보안 준비

추가 예정 변수:

```text
SEOUL_OPEN_API_KEY
GYEONGGI_OPEN_API_KEY
ULSAN_OPEN_API_KEY
```

원칙:

- 코드 하드코딩 금지
- Git 커밋 금지
- 프론트 JS 노출 금지
- 로그 출력 금지
- Docker 환경변수/운영 secret에서만 사용

다음 실제 연동 시 StoryMaker 운영 secret 관리 방식을 먼저 정리한다.

---

# 14. 다음 작업 시작 체크리스트

## 서울

- [ ] 서울 열린데이터광장 로그인
- [ ] 일반 인증키 발급
- [ ] `culturalEventInfo` JSON 샘플 호출
- [ ] 필드 목록 확인
- [ ] 현재/예정 행사 필터 확인
- [ ] 이미지 라이선스 필드 확인
- [ ] TourAPI 동일 행사 중복률 확인

## 경기

- [ ] 경기데이터드림 로그인
- [ ] OpenAPI 인증키 발급
- [ ] 최신 `경기도 문화 행사 현황` API 명세 확인
- [ ] 실제 서비스명 확인
- [ ] `SIGUN_CD` 필터 검증
- [ ] 시작/종료일/주소/좌표 필드 확인
- [ ] TourAPI 중복률 확인

## 울산

- [ ] 울산 데이터포털 검색
- [ ] 공공데이터포털에서 울산 행사/축제 API 검색
- [ ] 북구/중구/남구/동구/울주군 단위 데이터 여부 확인
- [ ] API vs 파일데이터 구분
- [ ] 인증키 발급 필요 여부 확인
- [ ] 최소 1개 안정적인 울산 행사 source 선정

---

# 15. 다음 채팅 작업 순서 권장

다음 채팅에서는 아래 순서로 진행한다.

```text
1. 서울 열린데이터광장 인증키 발급 여부 확인
2. culturalEventInfo 실제 샘플 호출
3. 응답 필드 분석
4. TourAPI DB와 중복 비교
5. seoul collector 구현
6. 하루 1회 DB 저장
7. Gemini DB-only 프롬프트 검증

그 다음
8. 경기데이터드림
9. 울산
10. 기타 지자체
```

서울부터 하나씩 완성한 뒤 경기/울산으로 가는 것이 안전하다.

---

# 16. 현 시점 최종 상태

이번 준비 단계에서는 **신규 외부 API 연결/키 입력/DB 마이그레이션은 하지 않았다.**

완료한 준비사항:

- 서울 우선 대상 API 확정 후보 정리
- 경기 OpenAPI 구조/인증 방식 정리
- 울산 데이터포털/공공데이터포털 연계 방식 정리
- 공통 collector 구조 설계
- 다중 source 중복제거 방향 설계
- DB 확장 필드 후보 정리
- 일일 수집 분산 스케줄 초안 작성
- API 키 보안 변수명 초안 작성
- 다음 채팅 작업 체크리스트 작성

다음 작업자는 이 문서를 기준으로 **서울 `culturalEventInfo`부터 실제 연동을 시작**하면 된다.
