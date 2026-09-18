# 2026-09-18 StoryMaker V1 TourAPI 지역축제·관광 DB 일일동기화 / Gemini SEO 프롬프트 연동 업무일지

## 1. 작업 목적

StoryMaker V1(`https://app.mystorymaker.net/v1/`)에서 네이버 블로그, 인스타그램, 당근, 네이버 플레이스, Google Business, 카드뉴스, 팟캐스트 등 SNS/지역 콘텐츠를 생성할 때 **사용자가 선택한 지역의 실제 축제·행사·관광 데이터를 자동 참고자료로 활용**하여 지역 검색 노출(로컬 SEO)을 강화하는 기능을 추가하였다.

초기 아이디어는 프롬프트 생성 시마다 한국관광공사 TourAPI를 실시간 호출하는 방식이었으나, 운영 안정성·API 트래픽·응답속도·외부 장애 격리를 고려하여 최종적으로 다음 구조로 전환하였다.

```text
한국관광공사 TourAPI KorService2
        ↓ 하루 1회 동기화
StoryMaker SQLite DB
        ↓ 로컬 조회만 수행
Gemini 최종 프롬프트 지역 SEO 컨텍스트
        ↓
블로그 / 인스타 / 당근 / 플레이스 / 구글 / 카드뉴스 / 팟캐스트
```

핵심 원칙은 **콘텐츠 생성 시점에는 TourAPI를 직접 호출하지 않는다**는 것이다.

---

## 2. 대상 서비스 및 기준 경로

- 운영 서비스: `https://app.mystorymaker.net/v1/`
- Dell 프로젝트 루트: `/home/bourne/StoryMaker_1`
- V1 백엔드/웹: `/home/bourne/StoryMaker_1/storymaker-web`
- FastAPI 백엔드 컨테이너: `storymaker-v1-backend`
- 운영 DB: StoryMaker SQLite(`STORYMAKER_DB_PATH`, 컨테이너 기준 `/data/storymaker.db`)
- TourAPI Base URL: `https://apis.data.go.kr/B551011/KorService2`
- 인증키는 코드/Git에 저장하지 않고 `TOUR_API_KEY` 환경변수로만 사용

---

## 3. 한국관광공사 OpenAPI 신청 및 확인

사용 API:

`한국관광공사_국문 관광정보 서비스_GW`

개발계정 승인 완료 후 KorService2 상세기능 사용 가능 상태를 확인하였다.

### 이번 구현에서 직접 사용하는 주요 엔드포인트

- `/ldongCode2` : 법정동 시도/시군구 코드
- `/searchFestival2` : 행사·축제 목록
- `/areaBasedList2` : 지역 관광·생활권 데이터
- 향후 상세 화면 확장용
  - `/detailCommon2`
  - `/detailIntro2`
  - `/detailInfo2`
  - `/detailImage2`

기존 `areaCode2`, `categoryCode2`는 API 문서에서 삭제 예정으로 표시되어 있으므로 신규 구현 기준에서 제외하였다.

---

## 4. 인증키 운영 방식

TourAPI 서비스키는 채팅/코드/커밋에 포함하지 않고 런타임 환경변수로 주입하도록 구성하였다.

Docker Compose에는 아래 환경변수를 읽도록 추가했다.

```text
TOUR_API_KEY
TOUR_API_BASE=https://apis.data.go.kr/B551011/KorService2
TOUR_API_MOBILE_APP=StoryMaker
STORYMAKER_PUBLIC_EVENTS_CACHE_DIR=/data/public_events_cache
```

실제 운영 컨테이너에 키를 주입 후 재생성하여 적용 여부를 검증했다.

보안 주의:

- API 키를 JS/프론트엔드에 포함하지 않는다.
- Git 저장소에 하드코딩하지 않는다.
- 로그에 키 자체를 출력하지 않는다.
- 운영환경 재생성 시 `TOUR_API_KEY` 누락 여부를 확인해야 한다.

현재 키는 실행 컨테이너에 정상 적용되어 실제 TourAPI 호출 성공까지 검증하였다.

---

## 5. 1차 실시간 연동 구현

### 신규 파일

`storymaker-web/backend/app/integration/public_events.py`

주요 역할:

- TourAPI 공통 클라이언트
- `ldongCode2` 지역/시군구 조회
- `searchFestival2` 행사 조회
- `areaBasedList2` 관광정보 조회
- 행사 상세 API 보조 메서드
- 공공데이터 응답을 StoryMaker 공통 필드로 정규화
- API 오류 시 프롬프트 생성 전체가 실패하지 않도록 fail-safe 처리

### API 라우터

`storymaker-web/backend/app/api/public_events.py`

신규 API:

```text
GET  /api/public-events/status
GET  /api/public-events/regions
GET  /api/public-events/districts
GET  /api/public-events/festivals
GET  /api/public-events/places
GET  /api/public-events/festivals/{content_id}
POST /api/public-events/sync-now
```

기본적으로 로그인 인증을 요구한다.
수동 동기화는 관리자 권한만 허용한다.

비로그인 상태에서 `/api/public-events/status` 호출 시 HTTP 401이 반환되는 것을 확인하여 인증 게이트가 정상 동작함을 검증했다.

---

## 6. TourAPI 실제 응답 차이 및 수정 사항

문서 예시와 실제 `ldongCode2` 응답 필드 구조가 달랐다.

문서에서 기대한 필드:

```text
lDongRegnCd
lDongRegnNm
lDongSignguCd
lDongSignguNm
```

실제 응답:

```json
{
  "rnum": 1,
  "code": "110",
  "name": "종로구"
}
```

따라서 파서가 `code / name`도 수용하도록 수정하였다.

수정 커밋:

```text
d516d84 fix: parse TourAPI legal district codes
```

실측 결과:

- 전국 광역지역: 16개 정상 조회
- 서울특별시 코드: `11`
- 서울 동작구 코드: `590`
- 울산광역시 코드: `31`
- 울산 북구 코드: `200`

지역 문자열 해석도 다음처럼 정상 확인하였다.

```text
서울 동작구 → 서울특별시 / 동작구
울산 북구 → 울산광역시 / 북구
```

---

## 7. Gemini 최종 프롬프트 연동

기존 StoryMaker V1 통합 프롬프트 생성기는 이미 다음을 생성하고 있었다.

- BLOG_TITLES
- BLOG_POST
- NAVER_PLACE_NEWS
- GOOGLE_BUSINESS_POST
- BLOG_HASHTAGS
- CARROT_TITLES
- CARROT_POST
- CARROT_HASHTAGS
- INSTAGRAM_POST
- INSTAGRAM_HASHTAGS
- CAROUSEL_7
- PODCAST_50
- PODCAST_80

여기에 지역 공공데이터 컨텍스트를 추가하였다.

### 프롬프트 내 추가 블록

```text
## 지역 관광·축제 SEO 참고
```

그리고 Gemini가 공공데이터를 단순 나열하지 않고 **SNS별 검색노출 목적에 맞게 자연스럽게 사용**하도록 채널별 규칙을 추가하였다.

### 블로그

- 제목 5개 중 최소 3개는 `지역명 + 핵심 서비스/주제` 조합을 자연스럽게 포함
- 축제명은 실제 글과 자연스럽게 연결되는 경우 최대 1개 제목에서 보조적으로 사용
- 첫 2개 문단에 지역명과 핵심 서비스/주제를 자연스럽게 배치
- 지역명은 제목·첫 문단·소제목·본문·마무리에 분산하고 반복 도배 금지

### 네이버 플레이스

- 실제 업체 현장 소식이 중심
- 지역명 + 서비스명을 첫 문단에 포함
- 업체가 행사에 참가/협찬했다는 오해가 생기는 표현 금지

### Google Business

- 지역 + 서비스 카테고리 + 실제 해결내용 우선
- 관광/행사는 지역 맥락 보조로만 사용

### Instagram

- 첫 2줄은 실제 현장/주제 중심
- 행사와 주제가 맞을 때만 지역 분위기를 1회 정도 활용
- 지역 발견성은 해시태그에서 강화

### 당근

- 구·동 단위 생활권 표현 우선
- 동네 이웃 글처럼 자연스럽게 작성

### 카드뉴스 / 팟캐스트

- 공공행사 데이터를 억지 소재로 만들지 않음
- 실제 서비스/문제해결 콘텐츠를 주인공으로 유지

### 공통 안전/품질 규칙

Gemini 프롬프트에 아래 원칙을 명시하였다.

- 공공데이터는 지역 생활 맥락 참고자료일 뿐 업체와 행사 간 직접 관계를 뜻하지 않는다.
- 참가·협찬·후원·납품·시공 사실을 입력자료 없이 생성하지 않는다.
- 방문객수, 순위, 후기, 할인, 주차 가능 여부 등 확인되지 않은 정보를 만들지 않는다.
- 지난 행사를 현재 진행 중이라고 표현하지 않는다.
- 검색 노출을 위해 같은 키워드/지역명을 기계적으로 반복하지 않는다.
- 업체 서비스와 사용자가 입력한 실제 내용이 항상 콘텐츠의 주인공이다.

초기 실시간 API 방식에서는 테스트 프롬프트 약 12,740자 수준으로 상세 지침이 정상 포함되는 것을 확인했다.

---

## 8. 실시간 API 호출 구조를 일일 DB 동기화 구조로 변경

운영 최적화를 위해 최종적으로 **프롬프트 생성 시 API 직접 호출을 제거**하였다.

신규 파일:

`storymaker-web/backend/app/integration/public_events_store.py`

### 동기화 기본 정책

```text
매일 03:20
```

- 지역코드/시군구 코드 동기화
- 전국 축제 데이터 동기화
- 등록된 StoryMaker 업체 지역의 관광·생활권 정보 동기화
- 당일 성공 동기화가 이미 있으면 중복 실행하지 않음
- 서버 재시작 후에도 같은 날 다시 불필요하게 수집하지 않음

### 축제 수집 범위

- 과거 7일
- 미래 90일

즉 현재 진행 중이거나 가까운 미래에 예정된 행사 중심으로 저장한다.

### 관광/생활권 수집 범위

전체 26만여 관광 데이터를 매일 전부 긁는 방식은 개발계정 트래픽과 불필요한 저장량을 크게 증가시키므로 사용하지 않았다.

대신 `user_personas`에 실제 등록된 업체 지역을 추출하여 해당 지역 위주로 `areaBasedList2`를 하루 1회 수집한다.

이 방식은 사용자 지역이 늘어나면 자동으로 수집 대상도 확장된다.

---

## 9. 신규 DB 테이블

### `public_event_regions`

법정동 지역코드 저장.

주요 필드:

```text
region_code
region_name
district_code
district_name
updated_at
```

`region_code + district_code` UNIQUE.

### `public_events`

축제·행사 정규화 데이터.

주요 필드:

```text
source
source_id
content_type_id
title
start_date
end_date
address
tel
image
thumbnail
mapx
mapy
region_code
district_code
region_name
district_name
festival_type
progress_type
copyright_code
source_modified_at
synced_at
```

`source + source_id(contentid)` UNIQUE로 UPSERT 처리하여 매일 동기화해도 중복 생성되지 않는다.

### `public_places`

관광·생활권 참고 데이터.

주요 필드:

```text
source
source_id
content_type_id
title
address
image
thumbnail
mapx
mapy
region_code
district_code
region_name
district_name
synced_at
```

### `public_event_sync_runs`

수집 이력/감사용 테이블.

주요 필드:

```text
started_at
finished_at
status
sync_date
event_count
place_count
region_count
api_calls
detail
```

이를 통해 마지막 동기화 시각과 성공/실패, API 호출량 등을 추적할 수 있다.

---

## 10. 최초 실제 DB 동기화 결과

2026-09-18 첫 강제 동기화를 실제로 실행하였다.

결과:

```text
region_count : 285
festival rows fetched : 325
places fetched : 250
API calls : 26
status : success
```

DB 중복 UPSERT 처리 후 실제 저장 상태 확인:

```text
public_events       : 325
public_places       : 247
public_event_regions: 285
```

관광정보 250건 입력 시 동일 contentid가 여러 지역조건에서 겹치는 항목이 존재하여 UNIQUE UPSERT 후 247건으로 정규화된 상태이다.

최초 성공 동기화 기록:

```text
2026-09-18T12:58:46+09:00
```

---

## 11. DB-only 프롬프트 검증

가장 중요한 운영 검증으로, 테스트 프로세스에서 의도적으로 `TOUR_API_KEY`를 제거한 상태에서 프롬프트를 생성하였다.

```text
env -u TOUR_API_KEY
```

그 상태에서도 StoryMaker DB에 저장된 데이터를 이용하여 다음 프롬프트 블록이 정상 생성되었다.

```text
### [StoryMaker 지역 공공데이터 DB 기반 SEO 컨텍스트]
- 기준 지역: ...
- DB 최근 동기화: ...
- 원출처: 한국관광공사 TourAPI KorService2 / StoryMaker 일일 동기화 DB
- 중요: 이 프롬프트 생성 시점에는 외부 TourAPI를 호출하지 않고 로컬 DB만 조회했습니다.
```

따라서 콘텐츠 생성 흐름은 이제 TourAPI 상태/속도/트래픽 한도와 직접 연결되지 않는다.

장점:

1. 프롬프트 생성 속도 개선
2. 외부 API 장애 시에도 기존 DB 데이터 사용 가능
3. API 트래픽 절감
4. 동일 데이터 반복 호출 방지
5. 향후 서울/경기/울산 등 다중 공공API 통합이 쉬움

---

## 12. 지역 fallback 정확도 개선

DB-only 검증 과정에서 `서울 동작구`에 해당 시군구 행사 데이터가 없을 경우 서울 전체 행사로 fallback되어 다음과 같이 다른 구 행사까지 프롬프트에 들어가는 문제를 발견하였다.

예:

- 중구 행사
- 종로구 행사

이는 지역 SEO 정확도를 해칠 수 있으므로 수정하였다.

최종 규칙:

```text
시군구가 명확히 지정된 경우
→ 해당 시군구 데이터만 사용
→ 없으면 비움
→ 광역시 전체 행사로 임의 fallback 하지 않음
```

광역지역만 선택한 경우에만 해당 시도 전체 데이터를 사용한다.

예:

```text
서울 동작구 → 동작구 데이터만
서울 → 서울 전체 가능
울산 북구 → 북구 데이터만
울산 → 울산 전체 가능
```

---

## 13. 수집 스케줄러 동작

백엔드 startup 시 `start_public_events_scheduler()` 실행.

스케줄러 정책:

- 서버 기동 직후 약 20초 안정화 대기
- 15분마다 동기화 필요 여부 확인
- 매일 03:20 이후 오늘 성공 동기화가 없을 경우 1회 실행
- 성공 후 같은 날 재수집 금지
- 동시 수집 방지 Lock 사용

즉 정확히 03:20에 프로세스가 잠시 내려가 있더라도 이후 서버가 살아나면 당일 미수집 상태를 확인하여 자동 보완한다.

---

## 14. 운영 검증

확인 항목:

```text
https://app.mystorymaker.net/v1/
```

Dell 로컬 V1 응답:

```text
/v1/ → HTTP 200
```

공공데이터 API 인증:

```text
/api/public-events/status → 비로그인 HTTP 401
```

정상.

백엔드 컨테이너:

```text
storymaker-v1-backend
```

정상 실행 확인.

---

## 15. 관련 Git 커밋

### 1차 TourAPI 연결

```text
680e370 feat: add TourAPI local SEO context
```

주요 내용:

- TourAPI 클라이언트
- public-events API
- Gemini 지역 SEO 프롬프트 컨텍스트
- Docker 환경변수 연결

### 법정동 응답 파서 수정

```text
d516d84 fix: parse TourAPI legal district codes
```

### 일일 DB 동기화 구조 전환

```text
3c500c4 feat: sync TourAPI data daily to local DB
```

주요 내용:

- 프롬프트 시 실시간 API 호출 제거
- SQLite 일일 수집 구조
- 수집 이력 테이블
- 전국 축제/등록 지역 관광정보 동기화
- DB-only Gemini 프롬프트 생성

---

## 16. 현재 남은 운영 주의사항

### 16.1 인증키 영구 보존

현재 `TOUR_API_KEY`는 운영 컨테이너에 적용되어 정상 동작한다.

다만 운영자가 추후 아래와 같이 컨테이너를 새로 생성할 경우:

```text
docker compose up -d --force-recreate
```

환경변수 전달이 누락되면 키가 비어질 수 있으므로 StoryMaker 운영용 보안 환경파일/secret 영역에 `TOUR_API_KEY`를 영구 설정하는 작업이 필요하다.

보안상 Git에는 절대 기록하지 않는다.

### 16.2 이미지 사용권

TourAPI의 이미지 데이터는 `cpyrhtDivCd` 등 공공누리/저작권 조건이 있으므로 프롬프트 단계에서는 이미지 사용 권한이 확보됐다고 간주하지 않는다.

향후 실제 이미지 자동첨부 기능을 만들 경우 저작권 코드별 사용정책을 별도 필터링해야 한다.

### 16.3 전체 관광DB 수집 금지

TourAPI 약 26만 건 전체를 매일 전량 저장하는 방식은 현재 목적에는 불필요하다.

현재처럼:

```text
전국 축제 = 전체 동기화
관광정보 = 실제 사용자 등록 지역 위주
```

가 운영 효율 측면에서 적절하다.

---

# 17. 다음 채팅에서 이어서 할 작업

다음 단계는 **다른 지역 축제·문화행사 공공API를 추가하여 TourAPI 누락분을 보강하는 것**이다.

우선순위 후보:

## A. 서울 열린데이터광장

목표:

- 서울시 문화행사 정보
- 구청/문화기관 행사
- TourAPI에 없는 소규모 생활행사 보완

수집 구조:

```text
서울 API
  ↓ 하루 1회
공통 public_events DB
  ↓ 중복 제거/정규화
Gemini 지역 SEO
```

## B. 경기데이터드림

목표:

- 경기도 31개 시군 문화행사/축제
- 시군 단위 생활밀착 행사 보완

## C. 울산 및 광역지자체 데이터

사용자의 울산 지역 콘텐츠 활용도가 높으므로 다음과 같은 지역 데이터 확인 필요.

- 울산광역시 공공데이터
- 북구/중구/남구/동구/울주군 행사
- 문화재단/관광/구청 행사 API 또는 공공데이터포털 연계 API

## D. 이후 확장 후보

- 부산
- 대구
- 인천
- 대전
- 광주
- 세종
- 제주
- 각 도/시군구 공공데이터

---

## 18. 다중 API 통합 시 반드시 유지할 설계 원칙

다음 API를 추가할 때도 프롬프트가 각 외부 API를 직접 호출하게 만들지 않는다.

모든 소스는 다음 구조를 따른다.

```text
외부 공공API
   ↓ 일 1회 collector
정규화
   ↓
public_events / public_places
   ↓
중복 제거
   ↓
Gemini는 로컬 DB만 조회
```

추가 권장 필드:

```text
source              # tourapi / seoul / gyeonggi / ulsan ...
source_id
source_priority
canonical_key
region_code
district_code
title
start_date
end_date
address
lat/lng
image
homepage
organizer
copyright
synced_at
```

중복 판단 기준 후보:

```text
정규화된 행사명
+ 시작일
+ 종료일
+ 지역/주소
```

동일 행사가 TourAPI와 서울시 API에 동시에 존재할 경우 더 상세하고 최신인 소스를 우선하되 다른 소스의 정보를 병합할 수 있도록 설계하는 것이 좋다.

---

## 19. 최종 상태

2026-09-18 기준:

- 한국관광공사 TourAPI 연결 완료
- 실제 인증키 적용 및 API 0000/OK 확인
- 법정동 시도/시군구 정상 해석
- 전국 축제 데이터 첫 DB 동기화 성공
- 등록 업체 지역 관광정보 동기화 성공
- Gemini 프롬프트 DB-only 조회 전환 완료
- 시군구 오염 fallback 제거 완료
- 일일 03:20 자동수집 구조 구현
- V1 서비스 HTTP 200 정상
- 기존 SNS 통합 콘텐츠 생성 구조 유지

다음 작업자는 **서울시 / 경기 / 울산 등 지자체 공공API를 조사하고, 현재 `public_events` 저장구조를 공통 수집 허브로 확장**하면 된다.
