# StoryMaker V1 작업 시작 전 필독

## 최우선: Git + 비공개 전체 서버 복구 기준

StoryMaker V1·Beta 복구는 GitHub 소스와 DellMusic 비공개 백업을 함께 사용합니다.

- GitHub: V1·Beta 코드, Docker Compose, Caddy, 설치 명세, 복구 문서
- 비공개 백업: `\\192.168.0.32\DellMusic\StoryMaker_Backup`
- 백업 스크립트: `\\192.168.0.32\StoryMaker_1\Git_추가_비공개_백업`
- 전체 복구 문서: `/home/bourne/StoryMaker_1/FULL_SERVER_RECOVERY.md`
- 자동 백업: 매일 새벽 03:30
- 백업 방식: 압축하지 않는 날짜별 폴더 + 대용량 증분 미러
- 자동 삭제: 금지

날짜별 `Full_Private`에는 V1·Beta DB, Beta jobs·Gemini queue, 서버 로컬 환경설정, 실제 systemd 설정과 실행 상태를 저장합니다.

`Recovery_Mirror/current`에는 V1 output_results, 브라우저 TTS ONNX 모델, 백엔드 글꼴, 음악 라이브러리, Supertonic3 실행 환경을 저장합니다.

복구 전에는 반드시 다음을 확인합니다.

```bash
cat /mnt/lms_ssd/StoryMaker_Backup/LATEST_FULL_RECOVERY_BACKUP.txt
systemctl status storymaker-beta-private-backup.timer --no-pager
git -C /home/bourne/StoryMaker_1 status
git -C /home/bourne/StoryMaker_1 log --oneline --decorate -5
```

비공개 백업의 서버 로컬 환경설정 파일은 GitHub나 외부 공개 공유에 올리지 않습니다.

NVIDIA API 주소 환경변수의 정식 기준 이름은 `NVIDIA_API_BASE`입니다.

---

## 최우선: Git 외 Beta 비공개 자동 백업

GitHub에 포함하지 않는 StoryMaker Beta 운영 데이터는 아래 자동 백업을 최우선 복구 기준으로 사용합니다.

- 백업 대상 DB: `/home/bourne/StoryMaker_1/StoryMaker_beta/data/storymaker_beta.db`
- 백업 대상 작업 폴더: `/home/bourne/StoryMaker_1/StoryMaker_beta/data/jobs/`
- Dell 백업 위치: `/mnt/lms_ssd/StoryMaker_Backup/Beta_Private/`
- Windows 공유 위치: `\\192.168.0.32\DellMusic\StoryMaker_Backup\Beta_Private\`
- 관리 스크립트 위치: `/home/bourne/StoryMaker_1/Git_추가_비공개_백업/`
- Windows 관리 경로: `\\192.168.0.32\StoryMaker_1\Git_추가_비공개_백업\`
- 자동 실행 시각: 매일 새벽 03:30
- 백업 형식: 압축하지 않은 날짜·시간별 폴더
- DB 백업 방식: SQLite 온라인 백업 API와 integrity_check
- 기존 백업 자동 삭제: 하지 않음

백업 실행 파일:

```bash
/usr/bin/python3 /home/bourne/StoryMaker_1/Git_추가_비공개_백업/backup_beta_private.py
```

자동 백업 상태 확인:

```bash
systemctl status storymaker-beta-private-backup.timer
systemctl list-timers storymaker-beta-private-backup.timer
journalctl -u storymaker-beta-private-backup.service -n 100 --no-pager
```

최근 성공 백업 위치 확인:

```bash
cat /mnt/lms_ssd/StoryMaker_Backup/Beta_Private/LATEST_BACKUP.txt
```

이 백업은 원본 DB와 jobs를 삭제하거나 이동하지 않습니다.

복구 작업 전에는 반드시 이 백업의 `backup_manifest.json`, DB SHA-256, `integrity_check = ok`, jobs 파일 수를 먼저 확인합니다.

이 문서는 `/home/bourne/StoryMaker_1`에서 작업하는 사람과 AI가 가장 먼저 읽어야 하는 최상위 작업 규칙입니다.

## 최우선: GitHub SSH 푸시 운영 기준

Dell 서버의 StoryMaker V1 저장소는 GitHub SSH 인증이 완료된 상태입니다.

- 로컬 저장소: `/home/bourne/StoryMaker_1`
- 원격 저장소: `git@github.com:kim6410/dell_V1_StoryMaker.git`
- 원격 이름: `origin`
- 기본 브랜치: `main`
- SSH 인증 계정: `kim6410`
- 인증 확인 완료: `ssh -T git@github.com`
- Push 성공 확인 완료: `main -> origin/main`

앞으로 AI는 사용자가 GitHub Push를 요청하면 HTTPS 비밀번호나 Personal Access Token을 요구하지 말고, 먼저 아래 상태를 확인한 뒤 SSH로 직접 Push합니다.

```bash
cd /home/bourne/StoryMaker_1
git status
git branch --show-current
git remote -v
git log --oneline --decorate -5
git push origin main
```

Push 전에는 반드시 미커밋 변경, 미추적 파일, 현재 브랜치, Push 대상 커밋을 확인합니다.

사용자가 승인하지 않은 파일을 임의로 `git add .` 하거나 커밋하지 않습니다.

이미 커밋된 정상 변경만 Push하는 경우에는 작업 트리의 다른 미커밋·미추적 파일을 건드리지 않습니다.

Push 후에는 로컬 `HEAD`, `origin/main`, `git ls-remote --heads origin main`의 커밋이 일치하는지 확인하고 성공 여부를 사용자에게 보고합니다.

이 문서의 규칙은 다른 임시 메모, 채팅 내용, 실험 스크립트보다 우선합니다.


## 1. 작업 대상

작업 루트:

`/home/bourne/StoryMaker_1`

V1 접속 주소:

`http://127.0.0.1:8011/v1`

주요 백엔드 컨테이너:

`storymaker-v1-backend`

이 환경은 Dell Ubuntu 서버에서 독립 운영하는 StoryMaker V1입니다.

프로젝트 루트는 `/home/bourne/StoryMaker_1`입니다.

이 문서와 모든 작업 기준은 Dell Ubuntu 서버 내부 경로만 사용합니다.

다른 운영 계열인 V2(`/home/bourne/StoryMaker`), Beta(`/home/bourne/StoryMaker_1/StoryMaker_beta`) 및 공용 음성 환경과 파일·서비스·포트·데이터를 섞지 않습니다.

Dell V1의 실제 독립 구성은 다음과 같습니다.

- V1 웹 컨테이너: `storymaker-v1-backend`
- V1 웹 포트: `8011`
- V1 Podcast API 서비스: `storymaker-v1-podcast-api.service`
- V1 Podcast API 포트: `8003`
- V1 Supertonic3 서비스: `storymaker-v1-supertonic3.service`
- V1 Supertonic3 포트: `7789`
- V1 데이터 루트: `/home/bourne/StoryMaker_1/database`
- V1 결과물 루트: `/home/bourne/StoryMaker_1/output_results`


## 2. 루트 폴더 파일 생성 금지

`/home/bourne/StoryMaker_1` 루트에는 새로운 임시 파일, 진단 파일, 패치 파일, 로그 파일, 테스트 파일을 생성하지 않습니다.

루트에 새로 둘 수 있는 문서는 이 `00_READ_FIRST.md`처럼 사용자가 명시적으로 승인한 최상위 관리 문서뿐입니다.

작업 중 생성되는 임시 파일과 도구는 반드시 목적에 맞는 하위 폴더에서 사용합니다.

루트에 이미 존재하는 실행 파일, 환경 파일, 백업 스크립트, 서비스 시작 파일은 임의로 이동하거나 이름을 바꾸지 않습니다.


## 3. 환경 파일 삭제 금지

다음 종류의 파일과 폴더는 사용자의 명시적 승인 없이 삭제하지 않습니다.

- `.env` 및 환경 설정 파일
- Python 가상환경
- Node 관련 환경 파일
- Docker Compose 파일
- 데이터베이스 파일
- 모델 캐시
- 실행 스크립트
- 서비스 시작 파일
- 인증·세션 관련 파일
- 사용자 페르소나 데이터
- 음악·음성 모델 파일
- 기존 백업 파일

환경 파일이 불필요하거나 잘못된 것으로 보여도 바로 삭제하지 않습니다.

먼저 실제 사용 여부를 확인하고, 백업한 뒤, 사용자에게 근거를 설명한 후 처리합니다.


## 4. WORK_LOGS 사용 원칙

업무일지 폴더:

`/home/bourne/StoryMaker_1/WORK_LOGS`

모든 업무는 작업을 마친 뒤 반드시 이 폴더에 업무일지를 작성합니다.

업무일지에는 다음 내용을 포함합니다.

- 작업 일시
- 작업 목적
- 수정한 파일
- 생성한 파일
- 삭제하거나 비활성화한 파일
- 수정 전 백업 위치
- 적용한 변경 내용
- 검사 및 테스트 결과
- 정상 확인 항목
- 미확인 항목
- 남은 문제
- 다음 작업 순서
- 절대 수정 금지 범위
- 롤백 방법

`/home/bourne/StoryMaker_1/WORK_LOGS`에는 최종 업무일지 MD 파일만 루트에 둡니다.

업무일지가 아닌 패치 스크립트, 진단 결과, HTML 스냅샷, 임시 텍스트, 비교 도구, 출력 로그를 WORK_LOGS 루트에 올려놓고 사용하지 않습니다.

필요한 보조 자료는 아래처럼 하위 폴더에 분리합니다.

- `/home/bourne/StoryMaker_1/WORK_LOGS/_TOOLS`
- `/home/bourne/StoryMaker_1/WORK_LOGS/_DIAGNOSTICS`
- `/home/bourne/StoryMaker_1/WORK_LOGS/_ARCHIVE`

업무가 끝난 뒤 WORK_LOGS 루트에는 업무일지 이외의 파일이 남지 않도록 정리합니다.


## 5. 백업 폴더 원칙

공식 백업 폴더:

`/home/bourne/StoryMaker_1/Backup`

모든 중요 백업은 반드시 `/home/bourne/StoryMaker_1/Backup`에 생성합니다.

기존 소문자 `backups` 폴더나 임시 작업 폴더는 런타임 데이터용일 수 있으므로 공식 수정 전 백업 위치로 사용하지 않습니다.

기존 `/home/bourne/StoryMaker_1/Backup`의 파일과 폴더는 절대 삭제하지 않습니다.

용량이 커 보여도 임의로 정리하거나 덮어쓰지 않습니다.

백업 이름은 날짜와 시간을 포함해 고유하게 만듭니다.

권장 형식:

`V1_WORKING_YYYYMMDD_HHMMSS_작업명`

예시:

`V1_WORKING_20260723_104500_대시보드_연구실_인라인_수정전`

같은 이름의 기존 백업에 덮어쓰지 않습니다.


## 6. 위험 작업 전 백업 의무

다음 작업을 하기 전에는 반드시 `/home/bourne/StoryMaker_1/Backup`에 날짜와 시간별 백업을 먼저 생성합니다.

- 파일 삭제
- 파일 이동
- 파일명 변경
- 기존 파일 덮어쓰기
- 코드 수정
- 환경 설정 변경
- 데이터베이스 변경
- Docker Compose 변경
- 컨테이너 설정 변경
- 프런트엔드 번들 변경
- API 수정
- 인증·세션 로직 수정
- 보관함 저장 구조 수정
- 미디어 생성 흐름 수정
- 대량 문자열 치환
- 롤백
- 다른 백업본 적용

작은 수정이라도 운영 동작에 영향을 줄 수 있으면 백업을 생략하지 않습니다.

백업이 완료되기 전에는 실제 수정 작업을 시작하지 않습니다.

백업 후에는 대상 파일 존재 여부, 파일 개수, 전체 크기, 개별 파일 크기와 SHA-256을 실제 명령으로 검증합니다.

단일 파일 백업 검증 예시:

```bash
BACKUP_DIR="/home/bourne/StoryMaker_1/Backup/V1_WORKING_YYYYMMDD_HHMMSS_작업명_수정전"
test -d "$BACKUP_DIR"
find "$BACKUP_DIR" -type f -printf '%p | %s bytes\n'
find "$BACKUP_DIR" -type f | wc -l
du -sb "$BACKUP_DIR"
sha256sum "$BACKUP_DIR/백업파일명"
```

여러 파일 백업 검증 예시:

```bash
BACKUP_DIR="/home/bourne/StoryMaker_1/Backup/V1_WORKING_YYYYMMDD_HHMMSS_작업명_수정전"
find "$BACKUP_DIR" -type f -printf '%p | %s bytes\n' | sort
find "$BACKUP_DIR" -type f | wc -l
du -sb "$BACKUP_DIR"
find "$BACKUP_DIR" -type f -exec sha256sum -- {} + | sort
```

검증 결과에서 파일 개수가 예상보다 적거나, 파일 크기가 0이거나, 해시 계산이 실패하면 수정 작업을 시작하지 않습니다.


## 6-1. 위험도별 백업 적용 기준

Git을 도입했더라도 `/home/bourne/StoryMaker_1/Backup` 백업 원칙은 유지합니다.

다만 모든 작업에 동일한 크기의 전체 백업을 요구하지 않고, 실제 위험도에 따라 백업 범위를 구분합니다.

### 낮은 위험 작업

다음 작업은 기존 파일을 변경하지 않는 조회·검사 작업입니다.

- 파일 읽기
- 파일명 검색
- 로그 확인
- Git 상태 확인
- Git Diff 확인
- 해시 확인
- 문법 검사
- HTTP 상태 확인
- 컨테이너·포트 상태 확인

낮은 위험 작업은 별도 백업 없이 바로 진행할 수 있습니다.

단, 조회 과정에서 기존 파일을 수정하거나 생성하지 않습니다.

### 중간 위험 작업

다음 작업은 단일 파일 또는 명확한 소규모 기능 묶음의 부분 수정입니다.

- Python 함수 한 곳 수정
- HTML·CSS·JavaScript 블록 한 곳 수정
- 문구·경로·설정값의 제한적 수정
- 새 V1 전용 브리지 파일 생성
- 관련 파일 2~5개 이내의 동일 기능 수정

중간 위험 작업은 수정 대상 파일 또는 관련 파일 세트만 `/home/bourne/StoryMaker_1/Backup`에 날짜·시간별로 백업하면 됩니다.

권장 형식:

`V1_WORKING_YYYYMMDD_HHMMSS_작업명_수정전`

수정 후에는 반드시 `git diff`, 문법 검사, 실제 동작 검증을 수행합니다.

### 높은 위험 작업

다음 작업은 전체 복구가 필요할 수 있으므로 Dell V1 전용 전체 백업 절차를 먼저 수행합니다.

- `.env` 또는 인증·비밀 설정 변경
- 데이터베이스 변경
- Docker Compose·컨테이너 설정 변경
- Python 가상환경 변경
- Supertonic3 패키지·모델 캐시 변경
- 프런트 핵심 번들 교체
- 여러 시점의 백업본 적용 또는 롤백
- 여러 핵심 파일을 동시에 변경
- 대규모 문자열 치환
- 폴더 이동·이름 변경·비활성화
- 복원 실패 시 서비스 전체가 멈출 수 있는 변경

Git은 코드와 문서의 빠른 타임머신이며, 전체 백업을 대신하지 않습니다.

Git에서 제외되는 `.env`, DB, 가상환경, 모델, 대형 바이너리, 생성 미디어는 반드시 `/home/bourne/StoryMaker_1/Backup`으로 보호합니다.

### 사용자 승인 범위

사용자가 현재 대화에서 특정 기능의 수정 진행을 명확히 승인한 경우, 그 기능 범위 안의 관련 파일은 파일마다 반복 승인받지 않고 순차적으로 백업·수정·검증할 수 있습니다.

다만 아래 상황에서는 다시 사용자에게 보고하고 승인을 받습니다.

- 처음 합의한 작업 범위를 벗어나는 경우
- 절대 수정 금지 대상이 포함되는 경우
- 삭제·이동·이름 변경이 필요한 경우
- DB·환경변수·Docker·가상환경을 변경해야 하는 경우
- 기존 변경 내용을 덮어쓰거나 롤백해야 하는 경우
- 예상보다 수정 파일 수가 크게 늘어나는 경우


## 7. 절대 수정 금지 범위

다음 대상은 사용자의 별도 지시가 없으면 수정하지 않습니다.

- Dell 운영 V2
- 공용 StoryMaker
- 공용 Supertonic3 루트 `/home/bourne/Supertonic3`
- 공용 포트 7788
- 기존 Gemini Worker
- 기존 Queue
- 기존 브라우저 MP4 엔진 보호 번들
- 기존 딸깍 제작의 정상 동작 파일
- 공용 데이터베이스와 운영 데이터

특히 아래 보호 파일은 직접 수정하지 않습니다.

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/assets/BrowserMp4TestPage-CmPBgwv3.js`

필요한 기능은 별도 브리지 파일, V1 전용 HTML, V1 전용 JavaScript, V1 전용 API로 연결합니다.


## 8. 작업 전 확인 순서

`/home/bourne/StoryMaker_1`에 처음 접속한 사람과 AI는 다른 파일을 보기 전에 반드시 루트의 이 문서부터 읽습니다.

첫 진입 필수 순서:

1. `/home/bourne/StoryMaker_1/00_READ_FIRST.md`를 처음부터 끝까지 읽습니다.
2. `/home/bourne/StoryMaker_1/WORK_LOGS`의 최상위 `*.md` 파일만 대상으로 수정시간을 확인합니다.
3. 파일시스템 수정시간 기준으로 가장 최근 업무일지 1개를 먼저 읽습니다.
4. 파일명 앞의 `YYYY-MM-DD` 날짜가 수정시간과 다르면 수정시간을 우선하되, 차이를 기록하고 날짜 기준 최신 문서도 함께 확인합니다.
5. 현재 작업과 직접 관련된 이전 업무일지도 함께 읽습니다.
6. 최근 업무일지에 기록된 완료 항목, 미확인 항목, 남은 문제, 다음 작업 순서, 절대 수정 금지 범위를 정리합니다.
7. 현재 파일 상태와 업무일지 내용이 일치하는지 확인합니다.
8. 현재 작업 대상 파일과 절대 수정 금지 파일을 구분합니다.
9. 현재 실행 중인 컨테이너와 포트를 확인합니다.
10. 브라우저에서 현재 정상 상태를 먼저 확인합니다.
11. `/home/bourne/StoryMaker_1/Backup`에 만들 백업 이름과 범위를 정합니다.
12. 변경 범위를 최소화합니다.

최신 업무일지 선택 명령 예시:

```bash
find /home/bourne/StoryMaker_1/WORK_LOGS -maxdepth 1 -type f -name '*.md' -printf '%T@ %TY-%Tm-%Td %TH:%TM:%TS %f\n' | sort -nr | head -n 10
```

선정 기준은 다음 순서입니다.

1. `WORK_LOGS` 최상위의 Markdown 업무일지인지 확인
2. 수정시간이 가장 최근인지 확인
3. 파일명 날짜 prefix와 수정시간이 일치하는지 확인
4. 현재 작업 키워드가 포함된 관련 업무일지도 추가 확인
5. `_TOOLS`, `_DIAGNOSTICS`, `_ARCHIVE` 하위 자료는 최신 업무일지 후보에서 제외

최근 업무일지를 읽지 않은 상태에서는 코드 수정, 파일 생성, 파일 이동, 파일명 변경, 삭제, 롤백을 시작하지 않습니다.

업무일지의 내용과 현재 실제 파일 상태가 다르면 추측해서 수정하지 않습니다.

먼저 파일 해시, 수정시간, 참조 위치, 컨테이너 마운트, HTTP 제공 경로를 확인하고 차이를 업무일지에 기록합니다.

기존 기능이 정상인지 확인하지 않은 상태에서 먼저 파일을 수정하지 않습니다.


## 9. 수정 원칙

한 번에 여러 기능을 크게 바꾸지 않습니다.

한 항목씩 수정하고 매 단계마다 실제 동작을 확인합니다.

서로 다른 시점의 백업 파일을 임의로 섞지 않습니다.

같은 기능 묶음은 같은 백업 시점의 파일 세트로 취급합니다.

HTML, JavaScript, Python 파일은 UTF-8 인코딩을 유지합니다. 최상위 관리 문서인 `00_READ_FIRST.md`는 Windows 편집기에서도 한글이 깨지지 않도록 UTF-8 BOM 형식으로 유지합니다.

### 9-1. 전체 덮어쓰기 금지

기존 코드를 수정할 때 파일 전체를 통째로 다시 작성해 덮어쓰는 방식은 원칙적으로 금지합니다.

수정은 반드시 아래 방식 중 하나로 진행합니다.

- 수정 전 코드와 수정 후 코드의 차이점만 정확히 지정하는 부분 치환
- 수정 대상 함수 하나만 교체
- 수정 대상 HTML·CSS·JavaScript 블록만 교체
- 파일 끝에 독립적인 V1 전용 브리지 파일을 추가하고 기존 파일은 최소 연결만 수행

`// 기존 코드 동일`, `나머지 생략`, `중략`처럼 일부 코드가 생략된 결과물로 기존 파일 전체를 덮어쓰지 않습니다.

전체 파일 쓰기가 불가피한 경우에는 작업 전에 반드시 아래를 비교하고 기록합니다.

1. 원본 파일의 전체 라인 수와 바이트 크기
2. 수정 결과 파일의 전체 라인 수와 바이트 크기
3. 주요 함수·클래스·라우트·스크립트 참조 개수
4. 원본에 있던 식별자와 핵심 문자열의 누락 여부
5. `기존 코드 동일`, `생략`, `TODO`, 빈 함수와 같은 의도치 않은 축약 여부
6. 원본과 수정본의 Diff 확인
7. 문법 검사와 실제 동작 검증

라인 수가 크게 줄었거나 주요 함수가 누락되면 파일을 적용하지 않고 원본으로 복원합니다.

### 9-2. 부분 수정과 Diff 기록

파일을 수정할 때는 가능한 한 수정 전 코드와 수정 후 코드를 업무일지에 기록합니다.

업무일지에는 최소한 아래 내용을 남깁니다.

- 수정 파일 경로
- 수정 함수 또는 블록 이름
- 변경 전 핵심 코드
- 변경 후 핵심 코드
- 변경 이유
- 영향 범위
- 원복 방법

여러 파일을 한꺼번에 수정하지 말고, 파일별로 백업·수정·검증을 끝낸 뒤 다음 파일로 넘어갑니다.

### 9-3. 안전한 파일 저장 방식

기존 파일을 대상으로 한 리디렉션 덮어쓰기와 전체 파일 재작성은 기존 내용을 통째로 교체할 수 있으므로 코드 수정에 사용하지 않습니다.

기존 파일 수정은 우선 안전한 문자열 치환 또는 패치 방식으로 진행합니다.

전체 파일 저장이 꼭 필요하면 `/home/bourne/StoryMaker_1/Backup` 백업, 라인 수·바이트 수·Diff 선검증, 사용자 승인까지 완료한 뒤 진행합니다.

전역 `fetch`, XHR, `console`, DOM을 반복적으로 가로채는 임시 디버그 코드는 넣지 않습니다.

React 상태를 외부 MutationObserver나 반복 클릭으로 강제 조작하지 않습니다.


## 10. 삭제·이동·이름 변경 원칙

파일이나 폴더를 바로 삭제하거나 이동하지 않습니다.

삭제, 이동, 이름 변경이 필요할 때는 아래 절차를 순서대로 모두 수행합니다.

1. 실제 사용 여부 확인
2. 참조 위치 검색
3. 대상 파일과 관련 파일 전체를 `/home/bourne/StoryMaker_1/Backup`에 날짜·시간별로 백업
4. 백업 파일 존재, 크기, 경로 확인
5. 가능하면 SHA-256 해시 기록
6. 삭제 대신 우선 비활성 이름으로 변경하거나 별도 비활성 폴더로 이동
7. 서비스 또는 컨테이너 재시작
8. 브라우저와 API에서 실제 동작 검증
9. 기존 기능 회귀 확인
10. 작업 결과를 업무일지에 기록
11. 사용자 승인 후 최종 삭제 여부 검토

이 과정에서 만들어지는 모든 단계별 백업은 예외 없이 `/home/bourne/StoryMaker_1/Backup`에 날짜와 시간별로 저장합니다.

원본 백업, 비활성 처리 전 백업, 이동 전 백업, 최종 삭제 검토 전 백업을 서로 구분해 남깁니다.

권장 백업 이름:

`V1_WORKING_YYYYMMDD_HHMMSS_대상명_삭제전`

`V1_WORKING_YYYYMMDD_HHMMSS_대상명_이동전`

`V1_WORKING_YYYYMMDD_HHMMSS_대상명_비활성전`

`V1_WORKING_YYYYMMDD_HHMMSS_대상명_최종삭제검토전`

권장 비활성 이름:

`파일명.disabled_YYYYMMDD_HHMMSS`

비활성 이름으로 변경한 파일도 사용자 승인 전에는 삭제하지 않습니다.

파일을 다른 폴더로 이동해야 할 경우에도 원본 위치의 백업과 이동 후 상태를 모두 `/home/bourne/StoryMaker_1/Backup`에 보존합니다.


## 10-1. 파괴적 CLI 명령어 실행 및 제안 금지

AI와 작업자는 대량 삭제, 재귀 삭제, 강제 덮어쓰기, 와일드카드 일괄 처리가 포함된 명령어를 직접 실행하거나 사용자에게 그대로 제안하지 않습니다.

금지 명령어와 구문 예시는 다음과 같습니다.

- Bash: `rm -rf`
- Bash: `find ... -delete`
- Bash: 기존 파일 대상 `truncate`
- Bash: 기존 파일 대상 `sed -i` 일괄 치환
- 파일 목록 확인 없는 재귀 삭제·이동 명령
- 모든 셸: 와일드카드 `*`를 사용한 삭제·이동·덮어쓰기
- 모든 셸: 기존 파일을 대상으로 한 리디렉션 덮어쓰기 `>`
- 디렉터리 전체를 대상으로 하는 재귀 복사·이동·삭제

파일 삭제나 이동이 필요한 경우에는 반드시 단일 파일 또는 단일 폴더의 절대 경로를 명시합니다.

대상 경로, 사용 여부, 참조 위치, 백업 위치, 예상 영향 범위를 사용자에게 보고하고 승인을 받은 뒤 처리합니다.

여러 파일을 처리해야 하더라도 먼저 대상 목록을 명시적으로 출력하고 사용자의 승인을 받은 뒤 파일별로 하나씩 처리합니다.

경로가 비어 있거나 변수 값이 확인되지 않은 상태에서는 삭제·이동·덮어쓰기 명령을 실행하지 않습니다.


## 10-2. AI 작업 시작 전 안전 점검 선언

AI가 파일 수정, 생성, 이동, 이름 변경, 비활성화, 삭제, 롤백 작업을 시작하기 전에는 답변 최상단에 아래 형식의 안전 점검을 먼저 선언합니다.

```text
[AI 작업 전 안전 점검]
1. 백업 확인: /home/bourne/StoryMaker_1/Backup 경로에 수정 전 백업을 수행했는가? (예/아니오)
2. 절대 수정 금지 대상 포함 여부: (없음 / 대상 명시)
3. 수정 방식: 전체 덮어쓰기가 아닌 안전한 부분 수정인가? (예/아니오)
4. 파괴적 명령어 사용 여부: (없음 / 명령어와 필요성 명시)
5. 검증 계획: 수정 후 수행할 문법·HTTP·브라우저·회귀 검증 항목
```

백업이 아직 완료되지 않았다면 `아니오`라고 명시하고, 실제 수정 전에 먼저 백업을 완료한 뒤 `예` 상태를 확인합니다.

이 체크인은 단순 문구가 아니라 실제 작업 상태와 일치해야 합니다.


## 10-3. Git 및 도구 권한 가드레일 권장

`/home/bourne/StoryMaker_1`은 장기적으로 로컬 Git 저장소로 관리하는 것을 권장합니다.

Git 도입 시 기대 효과는 다음과 같습니다.

- 수정 전후 Diff 확인
- 의도치 않은 파일 누락 탐지
- 파일별 변경 이력 확인
- 실수로 덮어쓴 코드 복원
- 정상 시점 태그와 커밋 관리

다만 Git 저장소 초기화, 전체 파일 등록, 복원 명령 실행은 기존 백업 체계를 대체하지 않습니다.

Git을 도입하더라도 모든 위험 작업 전 공식 백업은 계속 `/home/bourne/StoryMaker_1/Backup`에 날짜와 시간별로 생성합니다.

Git 초기화와 첫 커밋은 프로젝트 용량, 모델 캐시, 가상환경, 데이터베이스, 생성 결과물과 비밀정보를 제외할 `.gitignore` 범위를 먼저 설계하고 사용자의 명시적 승인을 받은 뒤 진행합니다.

AI 에이전트와 파일 도구에는 가능한 경우 아래 권한 제한을 적용합니다.

- 파일 삭제는 사용자 확인 필수
- 기존 파일 전체 덮어쓰기는 사용자 확인 필수
- 폴더 재귀 작업은 사용자 확인 필수
- 절대 수정 금지 경로는 쓰기 권한 차단
- 명령 실행 전 대상 경로 미리보기
- 변경 후 Diff 확인


## 10-4. Git 작업 시작·종료 필수 절차

AI는 `/home/bourne/StoryMaker_1`에서 파일 작업을 시작하기 전에 반드시 Git 상태를 확인합니다.

작업 시작 시 AI는 아래 명령을 직접 실행합니다.

```bash
cd /home/bourne/StoryMaker_1
git status
```

`git status` 결과에 기존 변경 파일, 삭제 파일, 새 파일이 있으면 AI는 수정 작업을 시작하기 전에 사용자에게 아래 내용을 먼저 보고합니다.

- 현재 변경 파일 목록
- 삭제로 표시된 파일 목록
- 새로 생성된 비추적 파일 목록
- 이번 작업과 관련된 변경인지 여부
- 기존 변경 내용을 보존해야 하는지 여부

기존 변경 사항이 발견되면 AI는 임의로 덮어쓰기, 복원, 스테이징, 커밋하지 않습니다.

사용자에게 현재 상태를 설명하고 작업 계속 여부를 확인받은 뒤 진행합니다.

작업 종료 후에는 반드시 아래 순서로 진행합니다.

1. 문법 검사, HTTP 확인, 브라우저 테스트, 기존 기능 회귀 검증을 완료합니다.
2. `/home/bourne/StoryMaker_1/WORK_LOGS`에 업무일지를 작성합니다.
3. `git status`를 실행해 최종 변경 파일을 확인합니다.
4. 사용자에게 커밋 예정 파일 목록과 커밋 메시지를 제안합니다.
5. 사용자에게 Git 저장 여부를 질문합니다.
6. 커밋 전 `/home/bourne/StoryMaker_1/Backup/V1_WORKING_YYYYMMDD_HHMMSS_작업명` 형식으로 고정 백업을 생성하고, 수정 대상 파일·크기·SHA-256을 기록합니다.
7. 사용자가 명시적으로 승인한 경우에만 `git add`와 `git commit`을 실행합니다.
8. 원격 저장소 Push도 사용자가 명시적으로 승인한 경우에만 `git push origin main`으로 실행합니다.
9. 커밋·Push 완료 후 커밋 번호, 커밋 메시지, 원격 브랜치와 Push 결과를 사용자에게 보고합니다.

AI가 사용자에게 물어야 하는 기본 질문 형식:

```text
[Git 저장 확인]
현재 작업과 업무일지가 정상 검증되었습니다.
변경 파일: (파일 목록)
제안 커밋 메시지: "(실제 작업 내용을 구체적으로 작성)"
이 상태를 Git에 저장할까요?
```

사용자가 `저장`, `커밋`, `진행`, `예`, `ㅇㅇ` 등 명시적으로 승인하면 아래 순서로 실행할 수 있습니다.

```bash
cd /home/bourne/StoryMaker_1
git status
git add -- "정확한 파일 경로 1" "정확한 파일 경로 2"
git commit -m "사용자가 승인한 구체적인 작업 내용"
```

가능하면 `git add .`보다 실제 수정한 파일 경로를 명시하는 방식을 우선합니다.

파일이 많아 `git add .`가 필요한 경우에는 먼저 `git status`로 전체 대상 목록을 확인하고, 사용자의 명시적 승인을 받은 뒤에만 실행합니다.

AI는 아래 작업을 사용자 승인 없이 자동 실행하지 않습니다.

- `git add .`
- `git commit`
- `git restore`
- `git reset`
- `git clean`
- 브랜치 전환
- 태그 삭제
- 커밋 수정 또는 이력 재작성

커밋 메시지는 `수정`, `백업`, `작업 완료`처럼 모호하게 작성하지 않습니다.

권장 형식:

`기능명 + 실제 변경 내용 + 검증 상태`

예시:

`AI 연구실 인라인 분리 연결 및 브라우저 검증 완료`

`단계별 제작 5단계 미리보기 설정 저장 기능 추가`

`팟캐스트 완료 상태 덮어쓰기 오류 수정 및 회귀 확인`

Git 커밋은 `/home/bourne/StoryMaker_1/Backup` 백업을 대신하지 않습니다.

위험 작업 전에는 Git 상태와 관계없이 반드시 `/home/bourne/StoryMaker_1/Backup`에 날짜·시간별 백업을 먼저 생성합니다.


## 10-5. Git 타임머신 운영 세부 원칙

이 항목은 10-3의 Git 안전망 원칙과 10-4의 작업 시작·종료 절차를 보완합니다.

### Git과 공식 백업의 역할 구분

Git은 코드·설정·업무일지의 변경 이력을 빠르게 비교하고 복구하는 타임머신입니다.

Git이 주로 보호하는 항목:

- Python·JavaScript·HTML·CSS 소스
- 실행 스크립트와 일반 설정 파일
- 업무일지와 관리 문서
- 수정 전후 Diff와 커밋 이력

`/home/bourne/StoryMaker_1/Backup`이 반드시 보호해야 하는 항목:

- `.env`와 비밀정보
- 데이터베이스
- Python 가상환경
- Supertonic3 패키지와 모델 캐시
- Docker 볼륨과 런타임 데이터
- 생성된 MP3·SRT·MP4·이미지
- `.gitignore`에 의해 Git에서 제외된 파일

Git 커밋이 있다고 해서 전체 시스템 복원이 가능하다고 판단하지 않습니다.

### 작업 시작 시 추가 확인

`git status`와 함께 가능한 경우 아래 항목을 확인합니다.

```bash
git branch --show-current
git log --oneline --decorate -5
```

현재 브랜치와 최근 정상 커밋을 확인해 잘못된 브랜치에서 수정하거나 오래된 기준으로 작업하는 사고를 방지합니다.

기존 변경 파일이 발견되면 다음처럼 분류해 보고합니다.

- 수정됨
- 새 파일
- 삭제됨
- 현재 작업과 관련 있음
- 현재 작업과 관련 없음
- Git 추적 제외로 별도 백업이 필요한 파일

### 커밋 단위

커밋은 파일 한 개 기준이 아니라 하나의 기능 또는 하나의 문제 해결 단위로 만듭니다.

좋은 커밋 메시지 예:

- `V1 팟캐스트 완료 상태 덮어쓰기 방지`
- `단계별 MP4 이미지 조회 API 추가`
- `V1 백업에 가상환경과 모델 캐시 포함`

피해야 할 커밋 메시지 예:

- `수정`
- `업데이트`
- `테스트`
- `파일 변경`

서로 관계없는 기능을 하나의 커밋에 섞지 않습니다.

### 스테이징 안전 확인

사용자가 Git 저장을 승인하면 실제 수정 파일 경로만 명시해 스테이징합니다.

```bash
git add -- "정확한 파일 경로 1" "정확한 파일 경로 2"
```

커밋 전에 반드시 아래 명령으로 스테이징된 내용을 확인합니다.

```bash
git diff --cached
```

예상하지 않은 파일, 비밀정보, 다른 작업의 변경이 포함되면 커밋하지 않고 사용자에게 보고합니다.

커밋 후에는 다음을 확인합니다.

```bash
git status
git log --oneline --decorate -3
```

작업 트리가 깨끗한지, 방금 생성된 커밋이 실제 작업 내용과 일치하는지 확인합니다.

### 자동 커밋 금지

작업 완료, 문법 검사 통과, 업무일지 작성은 Git 커밋 승인을 의미하지 않습니다.

AI는 사용자가 현재 변경 파일과 제안 커밋 메시지를 확인하고 명시적으로 승인한 경우에만 커밋합니다.

사용자가 커밋을 보류하면 변경 파일과 업무일지는 작업 트리에 그대로 보존하고 임의로 되돌리거나 정리하지 않습니다.


## 10-6. 현재 원격 Git 저장소 운영 정보

StoryMaker V1의 공식 원격 Git 저장소는 다음과 같습니다.

```text
https://github.com/kim6410/dell_V1_StoryMaker.git
```

원격 이름:

```text
origin
```

기본 브랜치:

```text
main
```

현재 로컬 브랜치도 `main`으로 통일되어 있으며 다음 관계를 유지합니다.

```text
local main -> origin/main
```

원격 저장소 연결 명령:

```bash
git remote add origin https://github.com/kim6410/dell_V1_StoryMaker.git
```

이미 `origin`이 존재하면 새로 추가하지 않고 아래 명령으로 현재 주소를 확인합니다.

```bash
git remote -v
```

브랜치 이름을 `main`으로 맞추는 명령:

```bash
git branch -M main
```

원격 저장소로 최초 Push 또는 추적 브랜치 설정:

```bash
git push -u origin main
```

이후 일반 Push:

```bash
git push
```

2026-07-25 Dell V1 신규 원격 저장소 기준:

```text
원격 저장소: https://github.com/kim6410/dell_V1_StoryMaker.git
기본 브랜치: main
현재 상태: 신규 빈 저장소
최초 연결·커밋·Push: 사용자 승인 후 진행
```

Dell V1 저장소는 다른 프로젝트의 커밋 이력과 혼동하지 않습니다.

실제 `git remote -v`, `git branch --show-current`, `git status`를 확인한 뒤 연결하며 강제 Push와 원격 이력 재작성은 금지합니다.

원격에 반영된 커밋 정보는 작업 시점마다 `git log`와 `git ls-remote` 결과로 확인하며 이 문서에 오래된 고정 커밋 번호를 남기지 않습니다.

작업 종료 시 Git 저장을 승인받은 경우에는 커밋 후 아래 항목을 반드시 확인합니다.

```bash
git status
git branch -vv
git remote -v
git log --oneline --decorate -3
git ls-remote --heads origin main
```

로컬 `HEAD`, `origin/main`, `git ls-remote`의 커밋 번호가 동일해야 원격 업로드 완료로 판정합니다.

원격 Push는 `/home/bourne/StoryMaker_1/Backup` 백업을 대신하지 않습니다. 코드와 문서는 Git으로 추적하되 DB, 환경 파일, 생성 미디어, 가상환경, 모델 캐시와 Git 제외 파일은 계속 `/home/bourne/StoryMaker_1/Backup`으로 보호합니다.


## 11. 검증 원칙

수정 후에는 가능한 범위에서 아래 검사를 수행합니다.

- Python 문법 검사
- JavaScript 문법 검사
- HTML 로딩 확인
- HTTP 200 확인
- 컨테이너 상태 확인
- 브라우저 새 세션 테스트
- 개발자도구 오류 확인
- API 응답 확인
- 생성 파일 존재 확인
- 파일 크기 확인
- `result.json` 반영 확인
- 보관함 표시 확인
- 기존 기능 회귀 테스트

문법 검사만 통과한 상태를 실제 기능 성공으로 기록하지 않습니다.

브라우저에서 실제 완주하지 않은 기능은 반드시 `미확인` 또는 `실사용 검증 필요`로 기록합니다.


## 12. 성공 판정 원칙

다음 항목이 모두 확인되기 전에는 최종 성공으로 단정하지 않습니다.

- 사용자가 실제 화면에서 기능을 실행함
- 브라우저 오류가 없음
- 요청 API가 정상 응답함
- 결과 파일이 실제 생성됨
- 현재 작업 ID에 결과가 연결됨
- 보관함에서 재생 또는 열람 가능함
- 새로고침 후 상태가 유지됨
- 기존 기능이 깨지지 않음


## 13. 롤백 원칙

문제가 발생하면 추가 패치를 계속 덧붙이기보다 마지막 정상 백업으로 돌아갑니다.

롤백 전에도 현재 문제 상태를 `/home/bourne/StoryMaker_1/Backup`에 별도로 백업합니다.

롤백 후에는 아래 내용을 비교합니다.

- 파일 해시
- 파일 크기
- 로딩 스크립트 순서
- API 경로
- 컨테이너 상태
- 브라우저 캐시 버전


## 14. 현재 핵심 업무일지

가장 먼저 읽을 단계별 제작 업무일지:

`/home/bourne/StoryMaker_1/WORK_LOGS/2026-07-23_V1_단계별제작_팟캐스트_MP4_연결_업무일지.md`

기존 딸깍 제작 프런트 복구 업무일지:

`/home/bourne/StoryMaker_1/WORK_LOGS/2026-07-23_V1_팟캐스트_MP3_MP4_프런트엔드_불안정_복구_업무일지.md`

최근 업무일지가 새로 생기면 날짜와 수정 시간을 기준으로 가장 최신 문서를 우선 읽습니다.


## 15. 현재 주요 파일

단계별 제작 화면:

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/staged-production.html`

단계별 전용 MP4 화면:

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/staged-browser-mp4.html`

단계별 전용 MP4 JavaScript:

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/staged-browser-mp4.js`

모바일 원샷 API:

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/api/mobile_one_shot.py`

보관함 API:

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/api/content_board.py`

V1 대시보드 인라인 연구실 연결:

`/home/bourne/StoryMaker_1/storymaker-web/backend/app/static/v1/v1-dashboard-inline-labs.js`


## 16. 작업 종료 시 필수 절차

작업이 끝나면 아래 절차를 반드시 수행합니다.

1. 수정 파일 목록 정리
2. 백업 위치 기록
3. 문법 및 기본 동작 검사
4. 실제 브라우저 테스트
5. 기존 기능 회귀 확인
6. 남은 문제 구분
7. `/home/bourne/StoryMaker_1/WORK_LOGS`에 업무일지 MD 생성
8. WORK_LOGS 루트의 업무일지 외 파일 정리
9. 사용자에게 완료·미완료 범위를 정확히 보고


## 17. 금지 사항

- 백업 없이 수정하지 않습니다.
- 백업 파일을 삭제하지 않습니다.
- 루트에 임시 파일을 생성하지 않습니다.
- WORK_LOGS 루트에 업무일지 외 파일을 쌓아두지 않습니다.
- 환경 파일을 임의로 삭제하지 않습니다.
- 공용 V2와 V1 파일을 혼합하지 않습니다.
- 정상 작동 중인 보호 번들을 직접 수정하지 않습니다.
- 확인하지 않은 성공을 보고하지 않습니다.
- 임시 진단 코드를 운영 상태로 남기지 않습니다.
- 사용자 승인 없이 대규모 구조 변경을 하지 않습니다.


## 18. 불확실할 때의 원칙

작업 범위가 불명확하거나 어떤 파일이 실제 사용본인지 확실하지 않으면 추측해서 수정하지 않습니다.

먼저 파일 참조, 실행 프로세스, 컨테이너 마운트, HTTP 제공 경로, 최근 업무일지를 확인합니다.

확인 자료가 부족하면 사용자에게 현재 확인된 사실과 필요한 추가 자료를 요청합니다.


마지막 갱신일:

2026-07-23
