# -*- coding: utf-8 -*-
"""
staged JSON 파일 기반 스토리지 엔진
"""
import os
import json
import uuid
import fcntl
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, Optional
from app.api.staged.validators import assert_staged_work_path

class StagedStorage:
    def __init__(self, root_dir: Path):
        self.root = root_dir.resolve()
        self.jobs_dir = self.root / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _get_job_dir(self, job_id: str) -> Path:
        job_path = self.jobs_dir / job_id
        # validators의 assert_staged_work_path를 거쳐 검증
        assert_staged_work_path(job_path, self.root)
        return job_path

    @contextmanager
    def lock_job(self, job_id: str) -> Generator[None, None, None]:
        """
        Job 단위 파일 락을 획득합니다 (동시 claim 경쟁 해결용).
        """
        job_dir = self._get_job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        lock_file_path = job_dir / "job.lock"
        
        # lock 파일 경로 검증
        assert_staged_work_path(lock_file_path, self.root)
        
        lock_file = open(lock_file_path, "w", encoding="utf-8")
        try:
            # 배타적 락(Exclusive Lock), 블로킹 모드
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def write_json_atomic(self, file_path: Path, data: Any) -> None:
        """
        임시 파일 작성 -> 재읽기 검증 -> flush/fsync -> os.replace 순서로 JSON을 원자적 저장합니다.
        """
        assert_staged_work_path(file_path, self.root)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        temp_suffix = f".tmp.{uuid.uuid4().hex}"
        temp_path = file_path.with_name(file_path.name + temp_suffix)
        assert_staged_work_path(temp_path, self.root)

        # 1. 파일 쓰기 및 fsync
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # 2. UTF-8 JSON 재읽기 검증
        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"JSON_VERIFICATION_FAILURE: {e}")

        # 3. 원자적 교체
        os.replace(temp_path, file_path)

    def write_raw_text_atomic(self, file_path: Path, text: str) -> None:
        """
        텍스트 파일을 원자적으로 덮어씁니다.
        """
        assert_staged_work_path(file_path, self.root)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        temp_suffix = f".tmp.{uuid.uuid4().hex}"
        temp_path = file_path.with_name(file_path.name + temp_suffix)
        assert_staged_work_path(temp_path, self.root)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, file_path)

    def read_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        JSON 파일을 안전하게 읽어옵니다.
        """
        assert_staged_work_path(file_path, self.root)
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def append_event(self, job_id: str, event_type: str, details: Dict[str, Any]) -> None:
        """
        events.jsonl 파일에 이벤트를 추가(append) 기록합니다.
        """
        job_dir = self._get_job_dir(job_id)
        events_path = job_dir / "events.jsonl"
        assert_staged_work_path(events_path, self.root)

        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event_type,
            "details": details
        }
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        
        # append 모드로 안전하게 기록
        with open(events_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
