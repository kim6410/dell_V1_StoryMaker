# -*- coding: utf-8 -*-
"""
staged 백엔드 비즈니스 로직 및 파서 서비스
"""
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from app.api.staged.storage import StagedStorage
from app.api.staged.validators import validate_job_id

ALL_DEFINED_BLOCKS = {
    "BLOG_TITLES",
    "BLOG_POST",
    "NAVER_PLACE_NEWS",
    "GOOGLE_BUSINESS_POST",
    "BLOG_HASHTAGS",
    "CARROT_TITLES",
    "CARROT_POST",
    "CARROT_HASHTAGS",
    "INSTAGRAM_POST",
    "INSTAGRAM_HASHTAGS",
    "CAROUSEL_7",
    "PODCAST_50",
    "PODCAST_80"
}

REQUIRED_BLOCK_KEYS = {
    "BLOG_TITLES",
    "BLOG_POST",
    "NAVER_PLACE_NEWS",
    "GOOGLE_BUSINESS_POST",
    "INSTAGRAM_POST",
    "CAROUSEL_7"
}

class StagedGenerationService:
    def __init__(self, storage: StagedStorage, lease_duration: int = 120):
        self.storage = storage
        self.lease_duration = lease_duration

    def create_job(self, project_title: str, prompt: str) -> Dict[str, Any]:
        """
        새로운 staged 작업을 생성합니다. (article_pending 상태로 진입)
        """
        # job_id 생성 규칙 준수: stage-YYYYMMDDHHMMSS-xxxxxxxx (랜덤 8자리 소문자/숫자)
        import random
        import string
        
        now = datetime.now()
        stamp = now.strftime("%Y%m%d%H%M%S")
        
        # 중복 방지를 위한 retry 루프
        for _ in range(5):
            rand = "".join(random.choices("abcdef" + string.digits, k=8))
            job_id = f"stage-{stamp}-{rand}"
            if validate_job_id(job_id):
                job_dir = self.storage._get_job_dir(job_id)
                if not job_dir.exists():
                    break
        else:
            raise RuntimeError("JOB_ID_GENERATION_CONFLICT")

        job_dir.mkdir(parents=True, exist_ok=True)
        iso_now = datetime.utcnow().isoformat() + "Z"

        request_payload = {
            "job_id": job_id,
            "action": "GENERATE_STAGED_ARTICLE",
            "project_title": project_title,
            "prompt": prompt,
            "created_at": iso_now,
            "schema_version": "staged-request-v1"
        }
        status_payload = {
            "job_id": job_id,
            "status": "article_pending",
            "worker_id": None,
            "claim_id": None,
            "attempt": 0,
            "claimed_at": None,
            "heartbeat_at": None,
            "lease_expires_at": None,
            "error": None,
            "updated_at": iso_now
        }

        self.storage.write_json_atomic(job_dir / "request.json", request_payload)
        self.storage.write_json_atomic(job_dir / "status.json", status_payload)
        self.storage.append_event(job_id, "job_created", {"status": "article_pending"})

        return status_payload

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        작업 상태를 조회합니다.
        """
        if not validate_job_id(job_id):
            raise ValueError("INVALID_JOB_ID")
        
        job_dir = self.storage._get_job_dir(job_id)
        status_path = job_dir / "status.json"
        if not status_path.exists():
            return None
        return self.storage.read_json(status_path)

    def claim_job(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        대기 중이거나 임대 만료된 작업을 수주합니다. (article_pending -> article_claimed)
        """
        # jobs 디렉토리 하위의 모든 디렉토리를 탐색하여 pending 대상 탐색
        if not self.storage.jobs_dir.exists():
            return None

        # 생성 시간 순 정렬을 위해 생성시간 수집
        candidates = []
        for p in self.storage.jobs_dir.iterdir():
            if p.is_dir() and validate_job_id(p.name):
                status_path = p / "status.json"
                if status_path.exists():
                    try:
                        status_data = self.storage.read_json(status_path)
                        if status_data:
                            candidates.append((status_data, status_path))
                    except Exception:
                        continue

        # 생성된 지 오래된 순으로 정렬
        candidates.sort(key=lambda x: x[0].get("updated_at", ""))

        now_utc = datetime.utcnow()

        for status_data, status_path in candidates:
            job_id = status_data["job_id"]
            
            # job lock 획득 후 안전하게 상태 재확인
            with self.storage.lock_job(job_id):
                status_data = self.storage.read_json(status_path)
                if not status_data:
                    continue

                # claim 수주 가능 조건: status == 'article_pending'
                # 또는 status == 'article_claimed' 이며 lease가 만료됨
                is_pending = status_data["status"] == "article_pending"
                is_expired_claim = False
                if status_data["status"] == "article_claimed" and status_data["lease_expires_at"]:
                    try:
                        expire_time = datetime.fromisoformat(status_data["lease_expires_at"].rstrip("Z"))
                        if now_utc > expire_time:
                            is_expired_claim = True
                    except Exception:
                        pass

                if is_pending or is_expired_claim:
                    # 새로운 수주 수행
                    import uuid
                    claim_id = f"cl-{uuid.uuid4().hex}"
                    iso_now = now_utc.isoformat() + "Z"
                    lease_time = (now_utc + timedelta(seconds=self.lease_duration)).isoformat() + "Z"

                    status_data["status"] = "article_claimed"
                    status_data["worker_id"] = worker_id
                    status_data["claim_id"] = claim_id
                    status_data["attempt"] = status_data.get("attempt", 0) + 1
                    status_data["claimed_at"] = iso_now
                    status_data["heartbeat_at"] = iso_now
                    status_data["lease_expires_at"] = lease_time
                    status_data["updated_at"] = iso_now

                    self.storage.write_json_atomic(status_path, status_data)
                    self.storage.append_event(job_id, "job_claimed", {
                        "claim_id": claim_id,
                        "worker_id": worker_id,
                        "attempt": status_data["attempt"]
                    })

                    # request 프롬프트 로드하여 함께 전달
                    req_data = self.storage.read_json(status_path.parent / "request.json") or {}

                    return {
                        "job_id": job_id,
                        "claim_id": claim_id,
                        "lease_expires_at": lease_time,
                        "prompt": req_data.get("prompt", ""),
                        "action": "GENERATE_STAGED_ARTICLE"
                    }
        return None

    def heartbeat(self, job_id: str, claim_id: str, worker_id: str) -> None:
        """
        작업 임대를 연장합니다.
        """
        if not validate_job_id(job_id):
            raise ValueError("INVALID_JOB_ID")

        with self.storage.lock_job(job_id):
            status_data = self.get_job_status(job_id)
            if not status_data:
                raise ValueError("JOB_NOT_FOUND")

            if status_data["status"] != "article_claimed":
                raise ValueError("JOB_NOT_CLAIMED")
            if status_data["claim_id"] != claim_id or status_data["worker_id"] != worker_id:
                raise ValueError("CLAIM_MISMATCH")

            now_utc = datetime.utcnow()
            # 임대 만료 여부 확인
            if status_data["lease_expires_at"]:
                expire_time = datetime.fromisoformat(status_data["lease_expires_at"].rstrip("Z"))
                if now_utc > expire_time:
                    raise ValueError("LEASE_EXPIRED")

            # 임대 시간 연장
            iso_now = now_utc.isoformat() + "Z"
            lease_time = (now_utc + timedelta(seconds=self.lease_duration)).isoformat() + "Z"
            status_data["heartbeat_at"] = iso_now
            status_data["lease_expires_at"] = lease_time
            status_data["updated_at"] = iso_now

            self.storage.write_json_atomic(self.storage._get_job_dir(job_id) / "status.json", status_data)

    def fail_job(self, job_id: str, claim_id: str, worker_id: str, error_message: str) -> None:
        """
        작업 실패 상태로 전이합니다.
        """
        if not validate_job_id(job_id):
            raise ValueError("INVALID_JOB_ID")

        with self.storage.lock_job(job_id):
            status_data = self.get_job_status(job_id)
            if not status_data:
                raise ValueError("JOB_NOT_FOUND")

            if status_data["status"] != "article_claimed":
                raise ValueError("JOB_NOT_CLAIMED")
            if status_data["claim_id"] != claim_id or status_data["worker_id"] != worker_id:
                raise ValueError("CLAIM_MISMATCH")

            iso_now = datetime.utcnow().isoformat() + "Z"
            status_data["status"] = "failed"
            status_data["error"] = error_message
            status_data["updated_at"] = iso_now

            self.storage.write_json_atomic(self.storage._get_job_dir(job_id) / "status.json", status_data)
            self.storage.append_event(job_id, "job_failed", {"error": error_message})

    def cancel_job(self, job_id: str) -> None:
        """
        작업을 취소합니다.
        """
        if not validate_job_id(job_id):
            raise ValueError("INVALID_JOB_ID")

        with self.storage.lock_job(job_id):
            status_data = self.get_job_status(job_id)
            if not status_data:
                raise ValueError("JOB_NOT_FOUND")

            # 허용 상태: pending, claimed
            if status_data["status"] not in ("article_pending", "article_claimed"):
                raise ValueError("CANCEL_REJECTED")

            iso_now = datetime.utcnow().isoformat() + "Z"
            status_data["status"] = "cancelled"
            status_data["updated_at"] = iso_now

            self.storage.write_json_atomic(self.storage._get_job_dir(job_id) / "status.json", status_data)
            self.storage.append_event(job_id, "job_cancelled", {})

    def parse_gemini_text(self, raw_text: str) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        """
        제미나이 마크다운 raw text를 파싱하여 13개 블록 데이터로 분리하고 검증합니다.
        """
        # [BLOCK:NAME] ... [BLOCK:END] 슬라이싱 추출
        # 정규식 패턴을 사용해 [BLOCK:이름]과 [BLOCK:END] 사이의 텍스트 수집
        pattern = re.compile(r"\[BLOCK:([A-Za-z0-9_]+)\](.*?)\[BLOCK:END\]", re.DOTALL)
        matches = pattern.findall(raw_text)

        blocks = {}
        duplicate_blocks = []
        unknown_blocks = []
        empty_blocks = []

        for name, content in matches:
            name = name.strip()
            content = content.strip("\r\n").strip("\n")  # 앞뒤 개행 제거
            
            if name not in ALL_DEFINED_BLOCKS:
                unknown_blocks.append(name)
                continue

            if name in blocks:
                duplicate_blocks.append(name)
            
            blocks[name] = content
            if not content.strip():
                empty_blocks.append(name)

        # 누락 블록 확인
        missing_required = []
        for req in REQUIRED_BLOCK_KEYS:
            if req not in blocks:
                missing_required.append(req)

        # PODCAST_50 및 PODCAST_80 상호 보완 체크
        has_podcast_50 = "PODCAST_50" in blocks and blocks["PODCAST_50"].strip()
        has_podcast_80 = "PODCAST_80" in blocks and blocks["PODCAST_80"].strip()
        if not has_podcast_50 and not has_podcast_80:
            missing_required.append("PODCAST_50/PODCAST_80")

        # [BLOCK:END] 누락 검증 (원문에 [BLOCK:이름] 은 있지만 block 매치 개수와 다르면 포맷 누락 존재)
        tag_starts = [t for t in re.findall(r"\[BLOCK:([A-Za-z0-9_]+)\]", raw_text) if t != "END"]
        tag_ends = re.findall(r"\[BLOCK:END\]", raw_text)
        
        # unmatched end tags 판단용
        if len(tag_starts) != len(tag_ends):
            # parse 에러로 간주하기 위해 missing_required에 마킹 주입
            missing_required.append("UNMATCHED_BLOCK_END")

        validation = {
            "missing_blocks": missing_required,
            "duplicate_blocks": duplicate_blocks,
            "unknown_blocks": unknown_blocks,
            "empty_blocks": empty_blocks
        }

        return blocks, validation

    def complete_job(self, job_id: str, claim_id: str, worker_id: str, raw_text: str) -> None:
        """
        Worker로부터 결과를 접수받아 파싱 및 검증한 뒤 완료 처리합니다.
        """
        if not validate_job_id(job_id):
            raise ValueError("INVALID_JOB_ID")

        if len(raw_text.encode("utf-8")) > 512000:
            raise ValueError("RAW_TEXT_LIMIT_EXCEEDED")

        with self.storage.lock_job(job_id):
            status_data = self.get_job_status(job_id)
            if not status_data:
                raise ValueError("JOB_NOT_FOUND")

            # 멱등성(Idempotency) 보장: 이미 완료된 작업이면 즉시 리턴
            if status_data["status"] == "article_completed":
                return

            if status_data["status"] != "article_claimed":
                raise ValueError("JOB_NOT_CLAIMED")
            if status_data["claim_id"] != claim_id or status_data["worker_id"] != worker_id:
                raise ValueError("CLAIM_MISMATCH")

            now_utc = datetime.utcnow()
            # 임대 만료 여부 확인
            if status_data["lease_expires_at"]:
                expire_time = datetime.fromisoformat(status_data["lease_expires_at"].rstrip("Z"))
                if now_utc > expire_time:
                    raise ValueError("LEASE_EXPIRED")

            job_dir = self.storage._get_job_dir(job_id)

            # 1. status -> article_result_received 전이 및 raw_result.txt 저장
            status_data["status"] = "article_result_received"
            self.storage.write_json_atomic(job_dir / "status.json", status_data)
            self.storage.write_raw_text_atomic(job_dir / "raw_result.txt", raw_text)

            # 2. status -> article_validating 및 파싱 검증
            status_data["status"] = "article_validating"
            self.storage.write_json_atomic(job_dir / "status.json", status_data)

            blocks, validation = self.parse_gemini_text(raw_text)

            # 3. 필수 검증 필터 통과 확인
            is_valid = (
                not validation["missing_blocks"] and
                not validation["duplicate_blocks"] and
                not validation["empty_blocks"] and
                not validation["unknown_blocks"]
            )

            iso_now = now_utc.isoformat() + "Z"
            if not is_valid:
                # 검증 실패 시 status -> failed 전이 후 저장
                status_data["status"] = "failed"
                status_data["error"] = f"VALIDATION_FAILED: {validation}"
                status_data["updated_at"] = iso_now
                self.storage.write_json_atomic(job_dir / "status.json", status_data)
                self.storage.append_event(job_id, "job_failed", {"error": status_data["error"]})
                raise ValueError("ARTICLE_VALIDATION_FAILED")

            # 4. 검증 성공 시 article_result.json 저장
            result_payload = {
                "job_id": job_id,
                "result_schema_version": "13-block-v1",
                "raw_text_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
                "blocks": blocks,
                "validation": validation,
                "completed_at": iso_now
            }
            self.storage.write_json_atomic(job_dir / "article_result.json", result_payload)

            # 5. events 기록 및 status -> article_completed 전이
            self.storage.append_event(job_id, "article_result_saved", {})
            
            status_data["status"] = "article_completed"
            status_data["updated_at"] = iso_now
            self.storage.write_json_atomic(job_dir / "status.json", status_data)
            
            self.storage.append_event(job_id, "job_completed", {"status": "article_completed"})
