# -*- coding: utf-8 -*-
"""
staged API 라우터 정의
"""
from fastapi import APIRouter, Depends, Request, HTTPException, status
from app.api.staged.schemas import (
    StagedJobCreate,
    StagedJobResponse,
    StagedWorkerClaimResponse,
    StagedWorkerHeartbeat,
    StagedWorkerComplete,
    StagedWorkerFail,
    StagedJobCancel
)
from app.api.staged.service import StagedGenerationService
from app.integration.staged_access import require_staged_access

router = APIRouter(dependencies=[Depends(require_staged_access)])

def get_service(request: Request) -> StagedGenerationService:
    service = getattr(request.app.state, "staged_service", None)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="STAGED_SERVICE_NOT_INITIALIZED"
        )
    return service


@router.post("/jobs", response_model=StagedJobResponse, status_code=status.HTTP_201_CREATED)
def create_staged_job(payload: StagedJobCreate, request: Request):
    service = get_service(request)
    try:
        status_payload = service.create_job(payload.project_title, payload.prompt)
        return {
            "ok": True,
            "data": {
                "job_id": status_payload["job_id"],
                "status": status_payload["status"]
            }
        }
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "JOB_CREATION_FAILED",
                "message": f"작업 생성 실패: {str(e)}"
            }
        }

@router.get("/jobs/{job_id}", response_model=StagedJobResponse)
def get_staged_job(job_id: str, request: Request):
    service = get_service(request)
    try:
        status_payload = service.get_job_status(job_id)
        if not status_payload:
            return {
                "ok": False,
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": "해당 작업을 찾을 수 없습니다."
                }
            }
        return {
            "ok": True,
            "data": status_payload
        }
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "STATUS_LOOKUP_FAILED",
                "message": str(e)
            }
        }

@router.get("/worker/jobs/claim", response_model=StagedWorkerClaimResponse)
def claim_staged_job(worker_id: str, request: Request):
    if len(worker_id) > 100:
        return {
            "ok": False,
            "error": {
                "code": "INVALID_PAYLOAD",
                "message": "worker_id 길이가 너무 깁니다."
            }
        }
    service = get_service(request)
    try:
        claimed = service.claim_job(worker_id)
        return {
            "ok": True,
            "data": claimed
        }
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "CLAIM_FAILED",
                "message": str(e)
            }
        }

@router.post("/worker/jobs/{job_id}/heartbeat", response_model=StagedJobResponse)
def heartbeat_staged_job(job_id: str, payload: StagedWorkerHeartbeat, request: Request):
    service = get_service(request)
    try:
        service.heartbeat(job_id, payload.claim_id, payload.worker_id)
        return {"ok": True, "data": {"message": "heartbeat_success"}}
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "HEARTBEAT_FAILED",
                "message": str(e)
            }
        }

@router.post("/worker/jobs/{job_id}/complete", response_model=StagedJobResponse)
def complete_staged_job(job_id: str, payload: StagedWorkerComplete, request: Request):
    service = get_service(request)
    try:
        service.complete_job(job_id, payload.claim_id, payload.worker_id, payload.raw_text)
        return {"ok": True, "data": {"message": "complete_success"}}
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "COMPLETE_FAILED",
                "message": str(e)
            }
        }

@router.post("/worker/jobs/{job_id}/fail", response_model=StagedJobResponse)
def fail_staged_job(job_id: str, payload: StagedWorkerFail, request: Request):
    service = get_service(request)
    try:
        service.fail_job(job_id, payload.claim_id, payload.worker_id, payload.error_message)
        return {"ok": True, "data": {"message": "fail_success"}}
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "FAIL_FAILED",
                "message": str(e)
            }
        }

@router.post("/jobs/{job_id}/cancel", response_model=StagedJobResponse)
def cancel_staged_job(job_id: str, payload: StagedJobCancel, request: Request):
    service = get_service(request)
    try:
        service.cancel_job(job_id)
        return {"ok": True, "data": {"message": "cancel_success"}}
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "CANCEL_FAILED",
                "message": str(e)
            }
        }
