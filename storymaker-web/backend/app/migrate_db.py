# -*- coding: utf-8 -*-
"""
StoryMaker SQLite DB 마이그레이션 스크립트
기존 구버전 projects 테이블 구조를 새 규격의 스키마로 이관하고, 
users 테이블에 관리자 대시보드용 신규 컬럼(is_active, last_login_at, last_activity_at)을 안전하게 추가합니다.
"""
import os
import sys
import json
import sqlite3
from datetime import datetime

# 패키지 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine, Base, SessionLocal
from app.db.models import Company, Persona, Project, User
from app.core.security import hash_password

DB_PATH = os.getenv("STORYMAKER_DB_PATH", "/home/bourne/StoryMaker_1/database/storymaker.db")

def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def migrate():
    print("=== StoryMaker 데이터베이스 마이그레이션 시작 ===")
    
    if not os.path.exists(DB_PATH):
        print(f"오류: DB 파일이 존재하지 않습니다: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. 기존 테이블 목록 조회
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    
    # 2. projects 가 기존 구버전 구조인지 확인 (project_name 컬럼이 있는지)
    if "projects" in tables:
        cur.execute("PRAGMA table_info(projects)")
        cols = [row[1] for row in cur.fetchall()]
        
        if "project_name" in cols:
            print("구버전 'projects' 테이블 감지. 백업 및 이름 변경 진행...")
            if "projects_old" in tables:
                print("이전 'projects_old' 테이블이 존재합니다. 안전을 위해 삭제 후 백업합니다.")
                cur.execute("DROP TABLE projects_old")
            
            conn.commit()
            cur.execute("ALTER TABLE projects RENAME TO projects_old")
            conn.commit()
            print("projects -> projects_old 이름 변경 완료.")
        else:
            print("이미 신규 규격의 'projects' 테이블이거나 구버전이 아닙니다. projects 테이블 마이그레이션을 스킵합니다.")
    else:
        print("'projects' 테이블이 존재하지 않습니다. 새로 생성합니다.")

    # 3. users 테이블 신규 컬럼들 추가
    if "users" in tables:
        cur.execute("PRAGMA table_info(users)")
        user_cols = [row[1] for row in cur.fetchall()]
        
        if "is_active" not in user_cols:
            print("users 테이블에 'is_active' 컬럼 추가 중...")
            cur.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL")
            conn.commit()
        if "last_login_at" not in user_cols:
            print("users 테이블에 'last_login_at' 컬럼 추가 중...")
            cur.execute("ALTER TABLE users ADD COLUMN last_login_at VARCHAR(20)")
            conn.commit()
        if "last_activity_at" not in user_cols:
            print("users 테이블에 'last_activity_at' 컬럼 추가 중...")
            cur.execute("ALTER TABLE users ADD COLUMN last_activity_at VARCHAR(20)")
            conn.commit()
        if "google_sub" not in user_cols:
            print("users 테이블에 'google_sub' 컬럼 추가 중...")
            cur.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
            conn.commit()
        if "avatar_url" not in user_cols:
            print("users 테이블에 'avatar_url' 컬럼 추가 중...")
            cur.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
            conn.commit()
        if "auth_provider" not in user_cols:
            print("users 테이블에 'auth_provider' 컬럼 추가 중...")
            cur.execute("ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'local' NOT NULL")
            conn.commit()
        if "wordpress_user_id" not in user_cols:
            print("users 테이블에 'wordpress_user_id' 컬럼 추가 중...")
            cur.execute("ALTER TABLE users ADD COLUMN wordpress_user_id INTEGER")
            conn.commit()
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub) WHERE google_sub IS NOT NULL")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_wordpress_user_id ON users (wordpress_user_id) WHERE wordpress_user_id IS NOT NULL")
        conn.commit()
        print("users 테이블 컬럼 동기화 완료.")
    else:
        print("users 테이블이 존재하지 않습니다. 신규로 자동 생성됩니다.")

    conn.close()

    # 4. SQLAlchemy를 이용해 새로운 규격으로 테이블들 생성
    print("신규 스키마 테이블 생성 및 동기화 중...")
    Base.metadata.create_all(bind=engine)
    print("테이블 생성 완료.")

    # 5. 데이터 이관 진행
    db = SessionLocal()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    
    if "projects_old" not in tables:
        print("이관할 구버전 백업 테이블(projects_old)이 존재하지 않아 projects 데이터 마이그레이션을 조기 종료합니다.")
        db.close()
        conn.close()
        return

    # 구버전 프로젝트 데이터 조회
    cur.execute("""
        SELECT id, project_name, company_name, persona_text, base_content, 
               reference_text, style_name, ai_preset, prompt_markdown, 
               created_at, updated_at, result_raw, result_blocks_json 
        FROM projects_old
    """)
    old_projects = cur.fetchall()
    print(f"이관 대상 구버전 프로젝트 수: {len(old_projects)}개")

    # 기본 관리자 유저 ID 획득 (user_id 맵핑용)
    admin_user = db.query(User).filter(User.role == "admin").first()
    admin_id = admin_user.id if admin_user else 1

    for row in old_projects:
        (old_id, project_name, company_name, persona_text, base_content,
         reference_text, style_name, ai_preset, prompt_markdown,
         created_at, updated_at, result_raw, result_blocks_json) = row

        # 중복 인서트 방지 (이미 이관된 프로젝트 ID가 있는 경우 스킵)
        exists = db.query(Project).filter(Project.id == old_id).first()
        if exists:
            continue

        print(f" -> 프로젝트 이관 중: [{project_name}] (업체: {company_name})")

        # 5-1. 업체 정보 조회 및 생성
        company = db.query(Company).filter(Company.name == company_name.strip()).first()
        if not company:
            company = Company(
                name=company_name.strip(),
                created_at=created_at or now_iso(),
                updated_at=updated_at or now_iso()
            )
            db.add(company)
            db.commit()
            db.refresh(company)

        # 5-2. 페르소나 설정
        if persona_text and persona_text.strip():
            persona = db.query(Persona).filter(Persona.company_id == company.id).first()
            if not persona:
                persona = Persona(
                    company_id=company.id,
                    content=persona_text.strip(),
                    created_at=created_at or now_iso(),
                    updated_at=updated_at or now_iso()
                )
                db.add(persona)
                db.commit()

        # 5-3. 키워드 정보 취합
        cur.execute("SELECT keyword FROM project_keywords WHERE project_id = ? ORDER BY position ASC", (old_id,))
        kws = [k[0] for k in cur.fetchall()]
        keywords_json = json.dumps(kws)

        # 5-4. 신규 프로젝트 레코드 빌드 및 인서트
        parsed_json_str = "{}"
        if result_blocks_json:
            try:
                parsed_dict = json.loads(result_blocks_json)
                if isinstance(parsed_dict, dict):
                    parsed_json_str = json.dumps(parsed_dict)
            except Exception:
                pass

        new_project = Project(
            id=old_id,
            company_id=company.id,
            user_id=admin_id,
            title=project_name,
            base_content=base_content,
            reference_text=reference_text or "없음",
            keywords=keywords_json,
            style=style_name,
            ai_preset=ai_preset,
            generated_prompt=prompt_markdown,
            raw_result=result_raw,
            parsed_result_json=parsed_json_str,
            created_at=created_at or now_iso(),
            updated_at=updated_at or now_iso()
        )
        db.add(new_project)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"   ! 오류 발생 (프로젝트 ID {old_id} 이관 실패, ID 충돌 가능성으로 인해 자동 우회 인서트합니다): {e}")
            new_project.id = None
            db.add(new_project)
            db.commit()

    print("=== 데이터 이관 완료 ===")
    db.close()
    conn.close()

if __name__ == "__main__":
    migrate()
