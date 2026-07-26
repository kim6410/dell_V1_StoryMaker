FROM python:3.11-slim

WORKDIR /app

# 필수 빌드 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 종속성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스코드 전체 복사
COPY . .

# 환경 변수 정의 (컨테이너 내 영속 볼륨 경로 지향)
ENV PYTHONPATH=.
ENV STORYMAKER_ENV=production
ENV STORYMAKER_DB_PATH=/data/storymaker.db
ENV STORYMAKER_PERSONA_DIR=/data/personas
ENV STORYMAKER_OUTPUT_DIR=/data/output_results
ENV STORYMAKER_EXPORT_DIR=/data/exports
ENV STORYMAKER_BACKUP_DIR=/data/backups

EXPOSE 8090

# FastAPI 구동 진입
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
