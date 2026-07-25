# Dell StoryMaker V1 00_READ_FIRST 완전 격리 및 GitHub 초기 커밋 업무일지

작성 시각: 2026-07-25 19:35:23 KST

## 1. 작업 목적

Windows PC에서 사용하던 `00_READ_FIRST.md`를 Dell Ubuntu StoryMaker V1 전용 규칙 문서로 재정비했다.

Windows 경로, Windows 전용 명령, Windows V1 커밋 이력과 기능 기준을 제거하고 Dell V1의 실제 경로·서비스·포트·백업·Git 운영 기준만 남기는 것이 목적이다.

## 2. 작업 대상

- `/home/bourne/StoryMaker_1/00_READ_FIRST.md`
- `/home/bourne/StoryMaker_1/.gitignore`
- `/home/bourne/StoryMaker_1/WORK_LOGS/2026-07-25_Dell_V1_00_READ_FIRST_완전격리_GitHub_초기커밋_업무일지.md`

## 3. 수정 전 백업

백업 위치:

`/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260725_193059_00_READ_FIRST_Dell_V1_격리_정비전`

수정 전 SHA-256:

`b20349bf03ba84be8da41427fa8fb8e1c42f08ad9622bede72c10768be383ab8`

수정 전 크기:

`32,264 bytes`

백업 폴더에는 원본 문서, SHA-256 기록, 파일 크기와 수정시간 기록을 보관했다.

## 4. Dell V1 실제 운영 상태 확인

확인된 V1 웹 컨테이너:

`storymaker-v1-backend`

확인된 V1 웹 포트:

`8011`

확인된 V1 Podcast API:

- 서비스: `storymaker-v1-podcast-api.service`
- 포트: `8003`
- 상태: active/running

확인된 V1 Supertonic3:

- 서비스: `storymaker-v1-supertonic3.service`
- 실행 루트: `/home/bourne/StoryMaker_1/Supertonic3`
- 포트: `7789`
- 상태: active/running

컨테이너 마운트는 `/home/bourne/StoryMaker_1` 아래의 backend, database, output_results, personas, exports, backups, music 경로를 사용하고 있음을 확인했다.

## 5. 문서 수정 내용

### Dell 전용 경로 통일

모든 작업 경로를 `/home/bourne/StoryMaker_1` 기준의 Linux 절대 경로로 정리했다.

Windows 드라이브 문자, 역슬래시 경로, PowerShell·CMD 명령, `cd /d` 표기를 제거했다.

### V1 독립 구성 명시

문서 상단에 웹 컨테이너, 웹 포트, Podcast API 서비스·포트, Supertonic3 서비스·포트, 데이터 루트와 결과물 루트를 명시했다.

V2, Beta, 공용 Supertonic은 수정 금지·격리 대상으로만 기록했다.

### 문서 인코딩 복구

`00_READ_FIRST.md`를 UTF-8 BOM 형식으로 저장했다.

Windows 편집기와 SMB 공유 경로에서 열어도 한글 인코딩 오판 가능성을 줄였다.

UTF-8 디코딩 검사와 대표적인 깨짐 문자열 검색을 수행했다.

### 백업 검증 절차 명령화

백업 후 다음 항목을 실제 명령으로 검증하도록 추가했다.

- 백업 폴더 존재 여부
- 백업 파일 목록
- 파일 개수
- 개별 파일 크기
- 백업 폴더 전체 크기
- SHA-256

단일 파일 백업과 여러 파일 백업의 검증 명령을 각각 문서에 추가했다.

### 최신 업무일지 선택 기준 명확화

최신 업무일지는 `WORK_LOGS` 최상위의 `*.md` 파일만 대상으로 한다.

선정 우선순위는 다음과 같이 정리했다.

1. 파일시스템 수정시간
2. 파일명 날짜 prefix와 수정시간 비교
3. 현재 작업 키워드가 포함된 관련 업무일지 추가 확인
4. `_TOOLS`, `_DIAGNOSTICS`, `_ARCHIVE` 제외

수정시간 기준 최신 10개 업무일지를 확인하는 Linux 명령도 추가했다.

### GitHub 운영 기준 정리

공식 원격 저장소를 다음으로 고정했다.

`https://github.com/kim6410/dell_V1_StoryMaker.git`

기본 브랜치는 `main`, 원격 이름은 `origin`으로 정리했다.

다른 프로젝트의 고정 커밋 번호와 Windows V1 커밋 이력은 문서에서 제거했다.

## 6. Git 추적 제외 기준

새 `.gitignore`를 생성해 다음 항목을 Git 추적에서 제외했다.

- `.env`와 비밀 설정
- Python 가상환경과 Node 모듈
- DB와 런타임 데이터
- Backup, Windows_Backup, 생성 결과물
- 모델 캐시와 Supertonic3 모델 환경
- 대형 압축 파일
- MP3, MP4, WAV, SRT
- 편집기와 운영체제 임시 파일

## 7. 검증 결과

- UTF-8 디코딩: PASS
- UTF-8 BOM: PASS
- 대표적인 한글 깨짐 문자열: 0건
- Windows 드라이브 경로: 0건
- Windows 전용 명령 표기: 0건
- `/home/bourne/StoryMaker_1` 뒤 역슬래시 혼합 경로: 0건
- Dell V1 서비스·포트 명시: PASS
- 백업 파일 개수·크기·해시 검증 명령: PASS
- 최신 업무일지 선택 명령과 기준: PASS

## 8. 절대 수정하지 않은 대상

- `/home/bourne/StoryMaker`
- `/home/bourne/StoryMaker_1/StoryMaker_beta`
- `/home/bourne/Supertonic3`
- 공용 포트 7788
- V1 데이터베이스
- 환경변수와 인증 파일
- 기존 Gemini Worker와 Queue
- 기존 브라우저 MP4 보호 번들

## 9. GitHub 커밋 및 Push 결과

이 항목은 실제 커밋과 Push 완료 후 최종 결과로 갱신한다.

## 10. 롤백 방법

`00_READ_FIRST.md`만 원복해야 할 경우 아래 백업 원본을 사용한다.

`/home/bourne/StoryMaker_1/Backup/V1_WORKING_20260725_193059_00_READ_FIRST_Dell_V1_격리_정비전/00_READ_FIRST.md`

원복 전 현재 문서를 다시 `/home/bourne/StoryMaker_1/Backup` 아래 새 시각의 백업 폴더에 보관하고, 원본과 복원본의 SHA-256을 비교한다.
