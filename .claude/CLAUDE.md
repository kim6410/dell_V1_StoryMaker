# StoryMaker V1 (Dell)

<!-- 이 파일은 공용 작업공간 규칙을 이 프로젝트로 연결하는 얇은 연결 문서입니다.
     프로젝트 고유 규칙은 00_READ_FIRST.md가 원본이며, 여기에 복사하지 않습니다. -->

## 최우선 문서

- 이 프로젝트의 최우선 기준은 `/home/bourne/StoryMaker_1/00_READ_FIRST.md`다.
- 아래 공용 규칙과 `00_READ_FIRST.md`가 충돌하면 **항상 `00_READ_FIRST.md`를 따른다.**
- `00_READ_FIRST.md`는 분량이 크므로 전체를 한 번에 읽지 않는다. 작업 종류에 맞는 절만 읽는다.
  - 파일 생성·수정 전: `9. 수정 원칙`, `10. 삭제·이동·이름 변경 원칙`
  - Git 작업 전: `10-4. Git 작업 시작·종료 필수 절차`
  - 백업 판단: `6-1. 위험도별 백업 적용 기준`

## 공용 작업공간 규칙 연결

@/home/bourne/CLAUDE_WORKSPACE/CLAUDE.md

## 이 프로젝트 정체성

작업 루트는 `/home/bourne/StoryMaker_1`이다. Windows PC의 `F:\StoryMaker_V1`과 혼동하지 않는다.

| 구성 | 값 |
| --- | --- |
| V1 웹 컨테이너 | `storymaker-v1-backend` |
| V1 웹 포트 | `8011` |
| V1 Podcast API | `storymaker-v1-podcast-api.service` / 포트 `8003` |
| V1 음성 엔진 | `storymaker-v1-supertonic3.service` / 포트 `7789` |
| 데이터 루트 | `/home/bourne/StoryMaker_1/database` |
| 결과물 루트 | `/home/bourne/StoryMaker_1/output_results` |
| 외부 접속 | `https://app.mystorymaker.net/v1/` |
| 내부 접속 | `http://127.0.0.1:8011/v1` |

## 절대 수정 금지

다음은 사용자의 별도 지시가 없으면 읽기만 하고 수정하지 않는다.

- Dell 운영 V2 `/home/bourne/StoryMaker`
- Beta `/home/bourne/StoryMaker_1/StoryMaker_beta`
- 공용 Supertonic3 `/home/bourne/Supertonic3`
- 공용 음성 포트 `7788`
- 기존 Gemini Worker, 기존 Queue, 공용 DB와 운영 데이터
- 보호 번들 `storymaker-web/backend/app/static/v1/assets/BrowserMp4TestPage-CmPBgwv3.js`

필요한 기능은 위 파일을 고치지 말고 V1 전용 브리지 파일, V1 전용 HTML/JS, V1 전용 API로 연결한다.

## V1 Worker 주의사항

- V1 Worker와 Beta Worker를 같은 Chrome 프로필이나 같은 Gemini 탭에서 동시에 실행하지 않는다.
- V1을 점검할 때는 Beta Worker를 먼저 비활성화한다.
- V1 Worker는 V1 화면에서 만든 작업만 처리해야 한다.
- Worker 원본 경로: `storymaker-web/backend/app/static/v1/storymaker-gemini-worker-v1.user.js`

## 루트 폴더 규칙

`00_READ_FIRST.md` 2절에 따라 프로젝트 루트에는 임시 파일, 진단 파일, 패치 파일, 로그 파일, 테스트 파일을 만들지 않는다. 작업 중 산출물은 목적에 맞는 하위 폴더에서 다룬다.

## 작업 종료 조건

`00_READ_FIRST.md`의 미추적 파일 규칙에 따라, 종료 시 `git status --short` 출력이 0줄이어야 완료로 판정한다. 다른 작업자가 수정 중인 파일이 남아 있으면 임의로 처리하지 않고 보류한다.

## 업무일지

작업을 마치면 `/home/bourne/StoryMaker_1/WORK_LOGS/YYYY-MM-DD_작업명.md`에 기록한다. 공용 작업공간 자체를 바꾼 경우에만 `/home/bourne/CLAUDE_WORKSPACE/WORK_LOGS/`에 기록한다.
