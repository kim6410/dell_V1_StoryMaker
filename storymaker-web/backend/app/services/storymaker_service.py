# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 비즈니스 서비스 계층 (storymaker_service.py)
API 라우터와 데이터 접근 계층(Repository), 코어 연산 모듈을 조정합니다.
"""
import json
from typing import Optional
from sqlalchemy.orm import Session
from app.db import repositories
from app.core import prompt_builder, result_parser, keyword_extractor
from app.schemas import (
    PromptRequest, 
    ResultParseRequest, 
    KeywordExtractRequest,
    ProjectCreate,
    ProjectUpdate
)

def map_project_to_response(project) -> dict:
    """
    DB에 JSON 문자열(String)로 저장되어 있는 키워드와 파싱 딕셔너리 데이터를
    Pydantic DTO 형식(List, Dict)에 맞추어 역직렬화 및 매핑을 보장하는 헬퍼 함수입니다.
    """
    if not project:
        return {}
        
    # keywords 역직렬화
    keywords = []
    if project.keywords:
        try:
            keywords = json.loads(project.keywords)
            if not isinstance(keywords, list):
                keywords = [keywords]
        except Exception:
            # 포맷 실패 시 콤마 구분 폴백 처리
            keywords = [k.strip() for k in project.keywords.split(",") if k.strip()]
            
    # parsed_result_json 역직렬화
    parsed = {}
    if project.parsed_result_json:
        try:
            parsed = json.loads(project.parsed_result_json)
            if not isinstance(parsed, dict):
                parsed = {}
        except Exception:
            parsed = {}
            
    company_name = ""
    try:
        company_name = project.company.name if project.company else ""
    except Exception:
        company_name = ""
            
    return {
        "id": project.id,
        "company_id": project.company_id,
        "company": company_name,
        "company_name": company_name,
        "title": project.title,
        "base_content": project.base_content,
        "reference_text": project.reference_text,
        "keywords": keywords,
        "style": project.style,
        "ai_preset": project.ai_preset,
        "generated_prompt": project.generated_prompt,
        "raw_result": project.raw_result,
        "parsed_result_json": parsed,
        "created_at": project.created_at,
        "updated_at": project.updated_at
    }


class StoryMakerService:
    @staticmethod
    def list_companies(db: Session):
        """
        등록된 모든 업체의 목록을 조회합니다.
        """
        return repositories.list_companies(db)
        
    @staticmethod
    def get_or_create_company(db: Session, name: str):
        """
        업체명을 조회하여 반환하거나 새로 가입시킵니다.
        """
        return repositories.get_or_create_company(db, name)
        
    @staticmethod
    def get_persona(db: Session, company_name: str):
        """
        특정 업체의 페르소나 정보를 반환합니다.
        """
        return repositories.get_persona(db, company_name)
        
    @staticmethod
    def save_persona(db: Session, company_name: str, content: str):
        """
        특정 업체의 페르소나를 저장하고 물리 파일에 동기화합니다.
        """
        return repositories.save_persona(db, company_name, content)
        
    @staticmethod
    def generate_prompt(req: PromptRequest) -> str:
        """
        입력 파라미터를 사용해 최종 AI 생성 지시 프롬프트 마크다운을 반환합니다.
        """
        return prompt_builder.build_prompt_markdown(
            company=req.company,
            persona=req.persona,
            base_content=req.base_content,
            reference_text=req.reference_text,
            keywords=req.keywords,
            style=req.style,
            ai_preset=req.ai_preset,
            emotion_levels=getattr(req, "tones", None),
            region=getattr(req, "region", None),
            industry_key=getattr(req, "industry_key", "general") or "general",
            blog_content_length=getattr(req, "blog_content_length", 1500),
            phone_number=getattr(req, "phone_number", "")
        )
        
    @staticmethod
    def parse_result(req: ResultParseRequest) -> dict:
        """
        ChatGPT 원문 결과 텍스트를 구조화된 채널별 블록 딕셔너리로 분류합니다.
        """
        parsed_blocks, cleaned_body = result_parser.parse_result_blocks(req.raw_result)
        return {
            "blocks": parsed_blocks,
            "cleaned_text": cleaned_body
        }
        
    @staticmethod
    def extract_keywords(req: KeywordExtractRequest) -> list:
        """
        여러 텍스트 본문 내에서 빈도수와 불용어를 분석하여 주요 SEO 추천 태그 목록을 빌드합니다.
        """
        return keyword_extractor.extract_keyword_candidates(*req.texts)

    # --------------------------------------------------------------------------
    # 프로젝트 CRUD 서비스 메서드군 추가
    # --------------------------------------------------------------------------
    @staticmethod
    def create_project(db: Session, req: ProjectCreate, user_id: int | None = None) -> dict:
        """
        신규 마케팅 프로젝트 데이터를 전달받아 DB에 생성하고 규격에 맞게 반환합니다.
        """
        # Pydantic 모델을 dict로 변환하여 레포지토리에 이관
        project_data = req.model_dump()
        if user_id is not None:
            project_data["user_id"] = user_id
        project = repositories.create_project(db, project_data)
        return map_project_to_response(project)

    @staticmethod
    def get_project(db: Session, project_id: int) -> Optional[dict]:
        """
        ID로 프로젝트 단건 상세 정보를 조회하여 변환 매핑 후 반환합니다.
        """
        project = repositories.get_project(db, project_id)
        if not project:
            return None
        return map_project_to_response(project)

    @staticmethod
    def list_projects(db: Session, limit: int = 50, user_id: int | None = None, is_admin: bool = False) -> list:
        """
        최근 갱신된 순서로 프로젝트 경량 목록을 반환합니다.
        """
        projects = repositories.list_projects(db, limit, user_id, is_admin)
        return [map_project_to_response(p) for p in projects]

    @staticmethod
    def update_project(db: Session, project_id: int, req: ProjectUpdate) -> Optional[dict]:
        """
        지정된 ID의 기존 프로젝트 정보를 선택적으로 갱신하고 수정본을 반환합니다.
        """
        update_data = req.model_dump(exclude_unset=True)
        project = repositories.update_project(db, project_id, update_data)
        if not project:
            return None
        return map_project_to_response(project)
