# StoryMaker Beta 서버 복구 가이드

이 저장소에는 StoryMaker Beta를 다시 실행하는 데 필요한 소스 코드, 정적 자산, Python·Node 설치 명세와 systemd 예제가 포함됩니다.

실제 `.env`, API 키, SQLite 운영 DB, 사용자 작업 결과, 생성 미디어, 브라우저 프로필, Python 가상환경과 백업 파일은 보안 및 용량 문제로 포함하지 않습니다.

## 1. 저장소 준비

```bash
cd /home/bourne/StoryMaker_1
git clone <repository-url>
cd StoryMaker_beta
```

저장소 구조가 상위 프로젝트와 함께 복원된 경우 실제 Beta 경로로 이동합니다.

## 2. Python 환경

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

FFmpeg가 없다면 운영체제 패키지로 설치하고 `deploy/ENVIRONMENT_TEMPLATE.txt`의 경로를 환경에 맞게 조정합니다.

## 3. 환경변수

```bash
cp deploy/ENVIRONMENT_TEMPLATE.txt .env
chmod 600 .env
```

`.env`에 실제 API 키와 모델명을 서버에서 직접 입력합니다. 실제 `.env`는 Git에 커밋하지 않습니다.

## 4. 데이터 디렉터리

```bash
mkdir -p data/jobs data/gemini_queue
```

운영 DB가 필요한 경우 별도 비공개 백업의 `storymaker_beta.db`를 `data/storymaker_beta.db`로 복원합니다. DB가 없으면 애플리케이션의 초기화 동작을 먼저 확인합니다.

## 5. systemd 서비스

```bash
sudo cp deploy/systemd/storymaker-beta.service.example /etc/systemd/system/storymaker-beta.service
sudo systemctl daemon-reload
sudo systemctl enable --now storymaker-beta.service
```

사용자명이나 설치 경로가 다르면 서비스 파일을 해당 서버에 맞게 조정합니다.

## 6. 확인

```bash
systemctl is-active storymaker-beta.service
curl -f http://127.0.0.1:8021/beta/production
curl -f http://127.0.0.1:8021/beta-api/health
```

## Git에 포함하지 않는 운영 데이터

- `.env`와 모든 실제 키·토큰
- `data/storymaker_beta.db`, `*.db-wal`, `*.db-shm`
- `data/jobs/`, `data/gemini_queue/`
- Chrome·Firefox 프로필과 쿠키
- MP3, MP4, WAV, SRT 생성물
- `.venv/`, 모델 캐시, 백업 폴더
- 사용자 업로드 이미지와 영상

Git 소스 복구와 운영 데이터 복구는 별도로 관리합니다.
