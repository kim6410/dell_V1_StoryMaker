# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 업체 정보 API 라우터 (companies.py)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services import StoryMakerService
from app.schemas import CompanyCreate, CompanyResponse, CommonResponse

router = APIRouter()

@router.get("/companies", response_model=CommonResponse)
def get_companies(db: Session = Depends(get_db)):
    """
    등록된 모든 업체의 정렬 목록을 반환합니다.
    """
    try:
        companies = StoryMakerService.list_companies(db)
        # ORM 객체 목록을 response 스키마 구조로 파싱
        data = [CompanyResponse.model_validate(c) for c in companies]
        return CommonResponse(ok=True, data=data, message="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/companies", response_model=CommonResponse)
def create_company(req: CompanyCreate, db: Session = Depends(get_db)):
    """
    신규 업체를 등록하거나 기존 동일한 업체의 정보를 조회하여 반환합니다.
    """
    try:
        company = StoryMakerService.get_or_create_company(db, req.name)
        data = CompanyResponse.model_validate(company)
        return CommonResponse(ok=True, data=data, message="업체가 성공적으로 조회/생성되었습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
