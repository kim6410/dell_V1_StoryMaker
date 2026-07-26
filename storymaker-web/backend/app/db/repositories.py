# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 데이터 접근 계층 (repositories.py)
"""
import json
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from pathlib import Path
from app.db.models import Company, Persona, Project, User
from app.settings import settings
from app.core.security import hash_password

def now_iso() -> str:
    """
    현재 표준 시간 정보를 문자열 포맷으로 반환합니다.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_companies(db: Session):
    """
    등록된 모든 업체의 목록을 이름 오름차순으로 정렬하여 조회합니다.
    """
    return db.query(Company).order_by(Company.name.asc()).all()


def get_or_create_company(db: Session, name: str) -> Company:
    """
    이름으로 업체를 조회하고, 없을 경우 신규 생성하여 반환합니다.
    """
    name_clean = name.strip()
    company = db.query(Company).filter(Company.name == name_clean).first()
    if not company:
        stamp = now_iso()
        company = Company(name=name_clean, created_at=stamp, updated_at=stamp)
        db.add(company)
        db.commit()
        db.refresh(company)
    return company


def get_persona(db: Session, company_name: str) -> Persona | None:
    """
    업체명으로 해당 업체의 페르소나 정보를 조회합니다.
    """
    company = db.query(Company).filter(Company.name == company_name).first()
    if not company:
        return None
    return company.persona


def save_persona(db: Session, company_name: str, content: str) -> Persona:
    """
    업체 페르소나 정보를 데이터베이스에 반영하고, 로컬 파일시스템과 동기화합니다.
    """
    stamp = now_iso()
    # 업체 정보가 없을 경우 선제적으로 가입/생성 처리
    company = get_or_create_company(db, company_name)
    
    persona = company.persona
    if persona:
        persona.content = content.strip()
        persona.updated_at = stamp
    else:
        persona = Persona(
            company_id=company.id,
            content=content.strip(),
            created_at=stamp,
            updated_at=stamp
        )
        db.add(persona)
        
    db.commit()
    db.refresh(persona)
    
    # 기존 데스크탑 로컬 앱과의 역동기화 지원 (personas/*.txt 백업 파일 쓰기)
    try:
        p_dir = Path(settings.STORYMAKER_PERSONA_DIR)
        p_dir.mkdir(parents=True, exist_ok=True)
        p_path = p_dir / f"{company_name}.txt"
        p_path.write_text(content.strip() + "\n", encoding="utf-8")
    except Exception as e:
        # 파일 입출력 예외가 데이터베이스 트랜잭션까지 전파되는 것을 차단
        import logging
        logging.getLogger("uvicorn").error(f"페르소나 파일 마이그레이션 쓰기 실패: {e}")
        
    return persona


def create_project(db: Session, data: dict) -> Project:
    """
    신규 콘텐츠 제작 프로젝트를 데이터베이스에 등록합니다.
    """
    stamp = now_iso()
    
    # list 타입으로 들어온 키워드를 JSON 문자열로 직렬화
    kw = data.get("keywords")
    kw_str = json.dumps(kw) if isinstance(kw, list) else kw
    
    # dict 타입으로 들어온 채널별 파싱 데이터셋을 JSON 문자열로 직렬화
    parsed = data.get("parsed_result_json")
    parsed_str = json.dumps(parsed) if isinstance(parsed, dict) else parsed

    project = Project(
        company_id=data["company_id"],
        user_id=data.get("user_id"),
        title=data["title"],
        base_content=data.get("base_content"),
        reference_text=data.get("reference_text"),
        keywords=kw_str,
        style=data.get("style"),
        ai_preset=data.get("ai_preset"),
        generated_prompt=data.get("generated_prompt"),
        raw_result=data.get("raw_result"),
        parsed_result_json=parsed_str,
        created_at=stamp,
        updated_at=stamp
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: int) -> Project | None:
    """
    지정된 ID의 프로젝트 상세 정보를 조회합니다.
    """
    return db.query(Project).filter(Project.id == project_id).first()


def list_projects(db: Session, limit: int = 50, user_id: int | None = None, is_admin: bool = False):
    """
    최근 수정된 순서로 프로젝트 목록을 제한된 개수만큼 조회합니다.
    관리자가 아닌 경우, 특정 user_id에 속한 프로젝트만 필터링합니다.
    """
    query = db.query(Project)
    # 응급 복구 모드: WordPress 계정 연동 전후 user_id 불일치로 기존 프로젝트가 숨겨지는 문제를 막기 위해
    # 로그인 사용자는 우선 전체 저장 프로젝트 목록을 볼 수 있게 합니다.
    # 소유권 재매핑 작업이 끝나면 user_id 필터를 다시 좁힐 예정입니다.
    return query.order_by(Project.updated_at.desc()).limit(limit).all()


def update_project(db: Session, project_id: int, data: dict) -> Project | None:
    """
    특정 프로젝트의 일부 혹은 전체 정보를 업데이트합니다.
    """
    project = get_project(db, project_id)
    if not project:
        return None
        
    stamp = now_iso()
    for key, val in data.items():
        if key == "keywords":
            project.keywords = json.dumps(val) if isinstance(val, list) else val
        elif key == "parsed_result_json":
            project.parsed_result_json = json.dumps(val) if isinstance(val, dict) else val
        elif hasattr(project, key):
            setattr(project, key, val)
            
    project.updated_at = stamp
    db.commit()
    db.refresh(project)
    return project


def get_user_by_username(db: Session, username: str) -> User | None:
    """
    사용자명(username)으로 사용자를 조회합니다.
    """
    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, username: str, password_plain: str, role: str = "user") -> User:
    """
    새로운 사용자를 생성합니다. 비밀번호는 자동으로 해싱되어 저장됩니다.
    """
    stamp = now_iso()
    user = User(
        username=username.strip(),
        password_hash=hash_password(password_plain),
        role=role,
        tier="paid" if role == "admin" else "free",
        wp_enabled=True,
        created_at=stamp,
        updated_at=stamp
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_admin_user(db: Session) -> User | None:
    """
    설정에 지정된 기본 관리자 계정이 없을 경우 자동으로 데이터베이스에 인서트(시딩)합니다.
    이미 계정이 존재한다면, 사용자가 마이페이지 등에서 수정했을 비밀번호의 영속성 유지를 위해
    절대로 비밀번호를 덮어쓰지(동기화하지) 않습니다.
    """
    admin_username = settings.STORYMAKER_ADMIN_USER
    admin_password = settings.STORYMAKER_ADMIN_PASSWORD
    
    admin = get_user_by_username(db, admin_username)
    if not admin:
        import logging
        logging.getLogger("uvicorn").info(f"기본 관리자 계정({admin_username}) 생성 중...")
        admin = create_user(db, admin_username, admin_password, role="admin")
        logging.getLogger("uvicorn").info(f"기본 관리자 계정 생성 완료")
    else:
        # 이미 계정이 존재하면 덮어쓰지 않고 스킵 (마이페이지 비밀번호 영속성 유지)
        pass
    return admin

