# StoryMaker V1 + Beta 전체 서버 복구 기준

GitHub 저장소에는 V1·Beta 실행 코드, Docker Compose, Caddy, Python 의존성, 정적 화면, systemd 예제와 복구 문서를 저장합니다.

비공개 백업 위치는 `\\192.168.0.32\DellMusic\StoryMaker_Backup`이며 Dell 내부 경로는 `/mnt/lms_ssd/StoryMaker_Backup`입니다.

## 날짜별 스냅샷

`Full_Private/YYYY-MM-DD/HHMMSS/`

포함 항목:

- Beta 운영 DB
- V1 운영 DB 3종
- Beta jobs
- Beta Gemini queue
- 서버 로컬 환경설정 파일
- 실제 systemd 서비스·타이머 설정
- Git HEAD, 브랜치, Docker 실행 상태, 서비스 상태
- SHA-256과 SQLite 무결성 검사 결과

## 대용량 복구 미러

`Recovery_Mirror/current/`

포함 항목:

- V1 output_results
- 브라우저 TTS ONNX 모델
- V1 백엔드 글꼴
- Podcast·숏폼 음악 라이브러리
- V1 Supertonic3 실행 환경

대용량 미러는 압축하지 않고 원래 폴더 구조를 유지합니다.
변경되거나 새로 생긴 파일만 갱신하며 기존 백업 파일을 자동 삭제하지 않습니다.

비공개 설정 폴더는 외부 공개 공유나 GitHub 업로드 대상이 아닙니다.

NVIDIA API 주소 변수의 기준 이름은 `NVIDIA_API_BASE`입니다.

## 자동 실행

서비스: `storymaker-beta-private-backup.service`

타이머: `storymaker-beta-private-backup.timer`

실행 시각: 매일 새벽 03:30

수동 실행:

```bash
sudo systemctl start storymaker-beta-private-backup.service
```

최근 백업 확인:

```bash
cat /mnt/lms_ssd/StoryMaker_Backup/LATEST_FULL_RECOVERY_BACKUP.txt
```

## 복구 순서

1. 새 서버에 Git 저장소를 clone합니다.
2. `storymaker-web/docker-compose.yml`과 `storymaker-web/Caddyfile`을 확인합니다.
3. Git의 환경 템플릿을 참고해 비공개 백업의 서버 로컬 환경설정 파일을 원래 위치에 복원합니다.
4. `Full_Private` 최신 스냅샷에서 V1·Beta DB와 Beta jobs·queue를 복원합니다.
5. `Recovery_Mirror/current`에서 V1 결과물, ONNX 모델, 글꼴, 음악, Supertonic3를 복원합니다.
6. Python·Node 의존성을 설치합니다.
7. systemd 서비스와 타이머를 설치하고 daemon-reload를 실행합니다.
8. Docker Compose를 기동합니다.
9. V1 로그인 → Beta 제작 → 사용자별 보관함 → 기존 MP3·MP4 열람 순서로 검증합니다.
10. 브라우저 Worker 방식은 Tampermonkey 재설치와 Gemini 재로그인이 필요합니다. API 방식은 서버 로컬 키 복원 후 사용할 수 있습니다.
