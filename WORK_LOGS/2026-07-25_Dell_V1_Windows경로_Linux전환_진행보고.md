# Dell V1 Windows 경로 Linux 전환 진행 보고

작성일: 2026-07-25

## 작업 원칙

- `StoryMaker_beta`는 수정하지 않음
- Mac mini `192.168.0.34` 슬라이드쇼 분산 경로 유지
- Windows 5800X `192.168.0.62` 의존성 제거 상태 유지
- 삭제 없이 `Windows_Backup`에 원본 보존
- 대응이 명확한 경로만 Dell 로컬 경로로 치환
- 실제 대응 파일이 없는 경로는 수정 중지

## 이동 완료

1차 보관:

`/home/bourne/StoryMaker_1/Windows_Backup/2026-07-25_Windows_이전잔재_1차`

2차 보관:

`/home/bourne/StoryMaker_1/Windows_Backup/2026-07-25_Windows_이전잔재_2차`

각 폴더의 `MOVE_MANIFEST.json`에 원본 경로, 목적지, 크기, SHA-256 기록.

## Linux 경로 전환 완료

- `supertonic/settings.json`
  - `F:\Supertonic3\음악`
  - `/home/bourne/StoryMaker_1/supertonic/music`

- `supertonic/podcast_generator.pyw`
  - `F:\Supertonic3`
  - `/home/bourne/StoryMaker_1/Supertonic3`

- `supertonic/SLID_Maker.pyw`
  - Windows 글꼴 경로를 Dell 설치 글꼴 경로로 변경
  - Windows VLC 후보 경로를 Dell Linux 경로로 변경

- `supertonic/fm_paths.py`
  - Windows VLC 후보 경로 제거
  - `/usr/bin/vlc`, `/usr/local/bin/vlc`만 사용

- `supertonic/user_jobs/default/slideshow_*/render_job.json`
  - `F:\StoryMaker_V1` 경로를 `/home/bourne/StoryMaker_1`로 변환

- `supertonic/JSON/SLID_gpt - #Ubcf5#Uc0ac#Ubcf8.py`
  - Windows 글꼴 경로를 Dell Linux 글꼴로 변경

수정 전 원본 및 SHA-256:

- `/home/bourne/StoryMaker_1/Windows_Backup/2026-07-25_Windows경로_Linux전환_1차`
- `/home/bourne/StoryMaker_1/Windows_Backup/2026-07-25_Windows경로_Linux전환_3차`
- `/home/bourne/StoryMaker_1/Windows_Backup/2026-07-25_Windows경로_Linux전환_4차`

## 수정 중지 항목

다음 설정에는 Windows 경로가 남아 있으나, 대응되는 실제 파일을 Dell에서 찾지 못함.

- `supertonic/slid_refactored/SETTING.json`
- `supertonic/slid_refactored/slid_ui_state.json`

찾지 못한 원본 파일:

- `KakaoTalk_20240909_162252544.mp4`
- `KakaoTalk_20240919_180036037.mp4`
- `KakaoTalk_20240920_175224694.mp4`
- `KakaoTalk_20240921_220408238.mp4`
- `하수_20260313_051713.mp3`
- `하수_20260313_051713.srt`

실제 파일이 없는데 임의의 Dell 경로로 바꾸면 UI에서 존재하지 않는 파일을 정상 파일로 오인할 수 있어 수정 중지함.

## 5800X 연관성

Dell에서 `192.168.0.62`로 나가는 트래픽은 UFW 출력 규칙으로 차단됨.

현재 보이는 연결은 5800X에서 Dell로 들어오는 SSH 22와 Samba 445 연결뿐임.

V1 컨테이너 환경변수에는 `192.168.0.62`, `8011`, `8021` 직접 연결값 없음.

Dell V1 실행은 5800X API, DB, 파일 공유에 의존하지 않는 상태로 확인됨.

## 검증 결과

- V1 로컬 HTTP 200
- `https://app.mystorymaker.net/v1/` HTTP 200
- Podcast API 8003 HTTP 200
- `storymaker-v1-podcast-api.service` active
- `storymaker-v1-supertonic3.service` active
- Backend restart count 0
- 수정 Python 문법 검사 통과
- 수정 JSON 파싱 통과

## 남은 주의 사항

`Supertonic3/.venv/site-packages` 내부의 `C:\` 문자열은 Python 패키지의 Windows 호환 코드와 테스트 예시임.

이 문자열은 5800X 또는 Windows 파일을 실제로 참조하는 운영 링크가 아니며 수정하면 가상환경을 손상시킬 수 있으므로 제외함.
