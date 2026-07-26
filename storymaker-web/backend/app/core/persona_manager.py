# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드용 persona_manager 모듈
기존 Tkinter UI 종속성과 하드코딩된 전역 경로가 제거된 순수 비즈니스 로직입니다.
"""
import sqlite3
from pathlib import Path
from datetime import datetime

def now_iso() -> str:
    """
    현재 시간을 ISO 형식 문자열로 반환합니다.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sync_persona_files_to_company_db(db_path: str, persona_dir: str) -> None:
    """
    로컬 텍스트 파일(personas/*.txt) 형태로 저장된 업체 정보와
    데이터베이스(companies 테이블)의 데이터를 동기화합니다.
    """
    db_path_obj = Path(db_path)
    persona_dir_obj = Path(persona_dir)
    
    # 저장 경로 보장
    db_path_obj.parent.mkdir(parents=True, exist_ok=True)
    persona_dir_obj.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path_obj))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                persona_text TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT 'db',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        stamp = now_iso()
        # txt 파일들을 순회하며 DB에 동기화
        for path in sorted(persona_dir_obj.glob("*.txt")):
            company = path.stem.strip()
            persona_text = path.read_text(encoding="utf-8").strip()
            existing = conn.execute("SELECT id, persona_text FROM companies WHERE name=?", (company,)).fetchone()
            if existing:
                # DB의 persona_text가 비어있고 파일에 내용이 존재하면 파일 내용으로 복원
                if not (existing["persona_text"] or "").strip() and persona_text:
                    conn.execute(
                        "UPDATE companies SET persona_text=?, updated_at=?, source_type='file' WHERE id=?",
                        (persona_text, stamp, existing["id"]),
                    )
            else:
                # 새로운 업체 등록
                conn.execute(
                    "INSERT INTO companies(name, persona_text, source_type, created_at, updated_at) VALUES (?, ?, 'file', ?, ?)",
                    (company, persona_text, stamp, stamp),
                )
        conn.commit()
    finally:
        conn.close()


def list_personas(db_path: str, persona_dir: str) -> list:
    """
    등록된 모든 업체의 이름 리스트를 알파벳/가나다 순으로 정렬하여 반환합니다.
    """
    _sync_persona_files_to_company_db(db_path, persona_dir)
    db_path_obj = Path(db_path)
    persona_dir_obj = Path(persona_dir)
    
    conn = sqlite3.connect(str(db_path_obj))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT name FROM companies ORDER BY name COLLATE NOCASE ASC").fetchall()
        names = [r["name"] for r in rows if (r["name"] or "").strip()]
        if names:
            return names
    finally:
        conn.close()
        
    return sorted([p.stem for p in persona_dir_obj.glob("*.txt")])


def load_persona_text(company: str, db_path: str, persona_dir: str) -> str:
    """
    지정된 업체의 페르소나 설명 텍스트를 로드하여 반환합니다.
    데이터베이스 검색을 우선하며, 없을 경우 로컬 파일에서 읽습니다.
    """
    company = (company or "").strip()
    if not company:
        return ""
        
    _sync_persona_files_to_company_db(db_path, persona_dir)
    db_path_obj = Path(db_path)
    persona_dir_obj = Path(persona_dir)
    
    conn = sqlite3.connect(str(db_path_obj))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT persona_text FROM companies WHERE name=?", (company,)).fetchone()
        if row and (row["persona_text"] or "").strip():
            return row["persona_text"]
    finally:
        conn.close()
        
    # 파일 폴백
    path = persona_dir_obj / f"{company}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def save_persona_text(company: str, text: str, db_path: str, persona_dir: str) -> None:
    """
    업체의 페르소나 설명 텍스트를 데이터베이스와 로컬 파일에 동시에 저장합니다.
    """
    company = (company or "").strip()
    if not company:
        return
        
    clean_text = (text or "").strip()
    stamp = now_iso()
    _sync_persona_files_to_company_db(db_path, persona_dir)
    db_path_obj = Path(db_path)
    persona_dir_obj = Path(persona_dir)
    
    conn = sqlite3.connect(str(db_path_obj))
    conn.row_factory = sqlite3.Row
    try:
        existing = conn.execute("SELECT id FROM companies WHERE name=?", (company,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE companies SET persona_text=?, updated_at=?, source_type='db' WHERE id=?",
                (clean_text, stamp, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO companies(name, persona_text, source_type, created_at, updated_at) VALUES (?, ?, 'db', ?, ?)",
                (company, clean_text, stamp, stamp),
            )
        conn.commit()
    finally:
        conn.close()
        
    # 로컬 파일에도 보관
    path = persona_dir_obj / f"{company}.txt"
    path.write_text(clean_text + "\n", encoding="utf-8")
