# -*- coding: utf-8 -*-
"""
StoryMaker 단계별 제작 전용 백엔드 격리 API 라우터 (staged_generation.py)
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_optional_current_user
from app.db.database import get_db
from app.db.models import User

router = APIRouter()

# 1. 물리 저장소 경로 완전 격리 설정
OUTPUT_ROOT = Path(os.getenv("STORYMAKER_OUTPUT_DIR", "/home/bourne/StoryMaker_1/output_results"))
STAGED_ROOT = OUTPUT_ROOT / "staged_generation"
TRIGGERS_DIR = STAGED_ROOT / "triggers"
RESULTS_DIR = STAGED_ROOT / "results"

# 디렉토리 미리 생성
TRIGGERS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# 2. 단계별 전용 작업 ID 독립 검증 함수
def validate_staged_job_id(job_id: str) -> bool:
    if not job_id:
        return False
    
    # 경로 문자 차단 (경로 탈출 공격 방어)
    if "/" in job_id or "\\" in job_id or ".." in job_id:
        return False
    
    # 금지된 공용/딸깍 접두사 명시적 거부
    if (
        job_id.startswith("mob-") or 
        job_id.startswith("thumbnail_") or 
        job_id.startswith("storymaker_main_")
    ):
        return False
    
    # 허용 패턴 1: stage-YYYYMMDDHHMMSS-xxxxxxxx (알파뉴메릭 1자 이상)
    # 허용 패턴 2: storymaker_stage_YYYYMMDDHHMMSS_xxxxxxxx (알파뉴메릭 1자 이상)
    pattern1 = r"^stage-\d{14}-[a-zA-Z0-9]+$"
    pattern2 = r"^storymaker_stage_\d{14}_[a-zA-Z0-9]+$"
    
    if re.match(pattern1, job_id) or re.match(pattern2, job_id):
        return True
    return False


# 3. 원자적 저장을 위한 Helper 함수
def atomic_write_json(file_path: Path, data: Any):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, file_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise e


def atomic_write_text(file_path: Path, content: str):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, file_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise e


# 4. Pydantic 요청 스키마 정의
class StagedTriggerStartRequest(BaseModel):
    job_id: str
    project_title: str
    prompt: str
    action: str = "GENERATE_STAGED_ARTICLE"


class StagedResultPackageRequest(BaseModel):
    job_id: str
    project_title: str
    result_text: str
    result_raw: str
    result_clean: str
    result_json: Optional[Dict[str, Any]] = None
    source: str = "staged-worker"


# 5. API 라우터 구현

@router.post("/trigger-start", status_code=status.HTTP_201_CREATED)
def trigger_start(
    req: StagedTriggerStartRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    단계별 제작 전용 작업(Trigger)을 대기 상태(pending)로 생성합니다.
    """
    # 1) 작업 ID 검증
    if not validate_staged_job_id(req.job_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid staged job_id format."
        )
    
    trigger_file = TRIGGERS_DIR / f"{req.job_id}.json"
    result_package_file = RESULTS_DIR / req.job_id / "result_package.json"
    
    # 2) 중복 생성 거부
    if trigger_file.exists() or result_package_file.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job ID already exists."
        )
    
    # 3) 로그인 사용자 정보 반영 및 메타데이터 작성
    now_str = datetime.now().isoformat()
    trigger_data = {
        "job_id": req.job_id,
        "project_title": req.project_title,
        "prompt": req.prompt,
        "action": req.action,
        "status": "pending",
        "user_id": current_user.id if current_user else None,
        "username": current_user.username if current_user else None,
        "created_at": now_str,
        "updated_at": now_str
    }
    
    # 4) 원자적 저장
    try:
        atomic_write_json(trigger_file, trigger_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save trigger: {str(exc)}"
        )
        
    return {"ok": True, "message": "Trigger queued successfully", "data": trigger_data}


@router.get("/trigger-status")
def trigger_status(
    job_id: str = Query(..., description="Staged Job ID"),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    단계별 제작 전용 작업의 상태(trigger status)를 반환합니다.
    """
    # 1) 작업 ID 검증
    if not validate_staged_job_id(job_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid staged job_id format."
        )
        
    trigger_file = TRIGGERS_DIR / f"{job_id}.json"
    if not trigger_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staged Job not found."
        )
        
    try:
        trigger_data = json.loads(trigger_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read trigger status: {str(exc)}"
        )
        
    return {
        "ok": True,
        "job_id": job_id,
        "status": trigger_data.get("status", "pending"),
        "data": trigger_data
    }


@router.post("/result-package")
def save_result_package(
    req: StagedResultPackageRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    단계별 제작 작업 결과(staged-worker 생성 결과)를 전용 저장소에 저장하고 큐를 완료 처리합니다.
    """
    # 1) 작업 ID 검증
    if not validate_staged_job_id(req.job_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid staged job_id format."
        )
        
    job_dir = RESULTS_DIR / req.job_id
    result_package_file = job_dir / "result_package.json"
    
    # 2) Idempotent(멱등성) 처리: 중복 저장인 경우 기존 데이터를 보존하고 성공 리턴
    if result_package_file.exists():
        try:
            existing_data = json.loads(result_package_file.read_text(encoding="utf-8"))
            return {
                "ok": True, 
                "message": "Result package already exists (Idempotent success).", 
                "data": existing_data
            }
        except Exception:
            pass # 손상된 파일 등의 경우 계속 진행하여 덮어쓰기 허용

    # 3) 트리거 상태 completed 변경
    trigger_file = TRIGGERS_DIR / f"{req.job_id}.json"
    if trigger_file.exists():
        try:
            trigger_data = json.loads(trigger_file.read_text(encoding="utf-8"))
            trigger_data["status"] = "completed"
            trigger_data["updated_at"] = datetime.now().isoformat()
            atomic_write_json(trigger_file, trigger_data)
        except Exception:
            pass
            
    # 4) 결과물들 폴더에 원자적 저장
    now_str = datetime.now().isoformat()
    payload = {
        "ok": True,
        "created_at": now_str,
        "updated_at": now_str,
        "job_id": req.job_id,
        "project_title": req.project_title,
        "source": req.source,
        "result_text": req.result_clean,
        "result_raw_length": len(req.result_raw),
        "result_clean_length": len(req.result_clean),
        "result_json": req.result_json or {},
        "user_id": current_user.id if current_user else None,
        "username": current_user.username if current_user else None,
    }
    
    try:
        atomic_write_text(job_dir / "result_raw.md", req.result_raw)
        atomic_write_text(job_dir / "result_clean.md", req.result_clean)
        atomic_write_json(result_package_file, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save result files: {str(exc)}"
        )
        
    # 5) staged 전용 최신 결과(latest.json) 갱신
    latest_file = STAGED_ROOT / "latest.json"
    try:
        atomic_write_json(latest_file, payload)
    except Exception:
        pass
        
    # 6) staged 전용 결과 상태판(result_status.json) 업데이트
    status_file = STAGED_ROOT / "result_status.json"
    status_data = {}
    if status_file.exists():
        try:
            status_data = json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    status_data[req.job_id] = {
        "status": "completed",
        "updated_at": now_str
    }
    try:
        atomic_write_json(status_file, status_data)
    except Exception:
        pass
        
    return {"ok": True, "message": "Result package saved successfully", "data": payload}


@router.get("/result-package/latest")
def get_latest_result(
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    디버깅용: staged 전용 latest.json 결과를 반환합니다.
    """
    latest_file = STAGED_ROOT / "latest.json"
    if not latest_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Latest staged result not found."
        )
        
    try:
        data = json.loads(latest_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read latest result: {str(exc)}"
        )
    return data


@router.get("/result-package/{job_id}")
def get_result_by_job_id(
    job_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    특정 staged Job ID의 결과 패키지를 반환합니다. (다른 작업 결과 반환 fallback 금지)
    """
    # 1) 작업 ID 검증
    if not validate_staged_job_id(job_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid staged job_id format."
        )
        
    result_package_file = RESULTS_DIR / job_id / "result_package.json"
    if not result_package_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result package for this job_id not found."
        )
        
    try:
        data = json.loads(result_package_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read result package: {str(exc)}"
        )
    return data
