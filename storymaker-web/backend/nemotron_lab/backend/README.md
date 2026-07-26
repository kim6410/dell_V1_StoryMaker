# Nemotron Lab Backend

이 폴더는 독립 실험 API 전용입니다.

현재 상태는 UI Shell 단계이며, StoryMaker `main.py`에 라우터를 마운트하지 않았습니다. NVIDIA 모델 호출, 기존 작업 큐 접근, Gemini Worker 접근, 운영 결과 저장은 모두 비활성 상태입니다.

향후 연결 시에도 `/api/nemotron-lab/*` 전용 경로와 이 폴더의 데이터 저장소만 사용합니다.
