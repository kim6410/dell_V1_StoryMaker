# -*- coding: utf-8 -*-
"""
StoryMaker 웹앱 백엔드 데이터베이스 연결 설정 모듈 (database.py)
SQLite WAL 모드 활성화 및 최적화 PRAGMA를 적용합니다.
"""
import os
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.settings import settings

# SQLite 연결을 위한 데이터베이스 URL 생성
# 예: sqlite:////home/bourne/StoryMaker_1/database/storymaker.db
DATABASE_URL = f"sqlite:///{settings.STORYMAKER_DB_PATH}"

# 커넥션 풀 및 스레드 호환성 설정
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# SQLite 연결 시 WAL 모드 및 최적화 설정을 위한 이벤트 리스너 등록
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        # Windows Docker bind mount에서는 WAL 보조 파일 잠금이 불안정할 수 있어
        # 환경변수로 저널 모드를 분리합니다. 기본값은 기존 운영과 같은 WAL입니다.
        journal_mode = os.getenv("STORYMAKER_SQLITE_JOURNAL_MODE", "WAL").strip().upper()
        if journal_mode not in {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}:
            journal_mode = "WAL"
        cursor.execute(f"PRAGMA journal_mode={journal_mode}")
        # 데이터 유실 방지와 성능 타협점인 NORMAL 동기화 설정
        cursor.execute("PRAGMA synchronous=NORMAL")
        # 외래키 제약조건 강제 활성화
        cursor.execute("PRAGMA foreign_keys=ON")
        # 락 발생 시 최대 5초 대기 (database is locked 에러 방지)
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

# 스레드 단위 세션 팩토리 생성
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

# ORM 모델용 기본 선언 클래스
Base = declarative_base()


def migrate_user_auth_columns() -> None:
    """기존 SQLite users 테이블에 소셜 로그인 컬럼을 멱등적으로 추가합니다."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("users")}
    statements = []
    if "google_sub" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN google_sub TEXT")
    if "avatar_url" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    if "auth_provider" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'local' NOT NULL")
    if "tier" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN tier TEXT DEFAULT 'free' NOT NULL")
    if "wp_enabled" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN wp_enabled BOOLEAN DEFAULT 1 NOT NULL")

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub "
            "ON users (google_sub) WHERE google_sub IS NOT NULL"
        ))
        if "user_personas" in inspector.get_table_names():
            persona_columns = {column["name"] for column in inspector.get_columns("user_personas")}
            if "is_default" not in persona_columns:
                connection.execute(text("ALTER TABLE user_personas ADD COLUMN is_default BOOLEAN DEFAULT 0 NOT NULL"))
            if "industry_key" not in persona_columns:
                connection.execute(text("ALTER TABLE user_personas ADD COLUMN industry_key TEXT DEFAULT 'general' NOT NULL"))
            if "website_url" not in persona_columns:
                connection.execute(text("ALTER TABLE user_personas ADD COLUMN website_url TEXT DEFAULT '' NOT NULL"))
            if "region" not in persona_columns:
                connection.execute(text("ALTER TABLE user_personas ADD COLUMN region TEXT DEFAULT '' NOT NULL"))
            if "default_style" not in persona_columns:
                connection.execute(text("ALTER TABLE user_personas ADD COLUMN default_style TEXT DEFAULT '네이버 블로그' NOT NULL"))
            if "default_tones_json" not in persona_columns:
                connection.execute(text("ALTER TABLE user_personas ADD COLUMN default_tones_json TEXT DEFAULT '[]' NOT NULL"))
            if "blog_content_length" not in persona_columns:
                try:
                    db_path = Path(settings.STORYMAKER_DB_PATH)
                    if db_path.exists():
                        backup_path = db_path.with_name(db_path.name + ".bak_blog_length_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
                        shutil.copy2(db_path, backup_path)
                        print(f"[migration] user_personas blog_content_length backup created: {backup_path}")
                except Exception as exc:
                    print(f"[migration] user_personas blog_content_length backup skipped: {exc}")
                connection.execute(text("ALTER TABLE user_personas ADD COLUMN blog_content_length INTEGER DEFAULT 1500 NOT NULL"))
            connection.execute(text("UPDATE user_personas SET default_style = '네이버 블로그' WHERE default_style IS NULL OR default_style = ''"))
            connection.execute(text("UPDATE user_personas SET blog_content_length = 1500 WHERE blog_content_length IS NULL OR blog_content_length NOT IN (1200, 1500, 2000)"))
            connection.execute(text("UPDATE user_personas SET default_tones_json = '[\"따뜻함\", \"전문가\", \"친근함\", \"신뢰감\", \"현장감\", \"진정성\", \"차분함\", \"활기\", \"담백함\", \"순박함\", \"진지함\"]' WHERE default_tones_json IS NULL OR default_tones_json = '' OR default_tones_json = '[]'"))
            connection.execute(text(
                "UPDATE user_personas SET is_default = 1 "
                "WHERE id IN (SELECT MAX(id) FROM user_personas GROUP BY user_id) "
                "AND user_id NOT IN (SELECT user_id FROM user_personas WHERE is_default = 1)"
            ))

def migrate_region_options() -> None:
    """마이페이지 지역 선택 목록 테이블을 만들고 기본 지역 데이터를 시드합니다."""
    now_text = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    region_options = [
        ("서울특별시", "", "metro", 1),
        ("부산광역시", "", "metro", 2),
        ("대구광역시", "", "metro", 3),
        ("인천광역시", "", "metro", 4),
        ("광주광역시", "", "metro", 5),
        ("대전광역시", "", "metro", 6),
        ("울산광역시", "", "metro", 7),
        ("세종특별자치시", "", "special", 8),
        ("경기도", "", "province", 9),
        ("강원특별자치도", "", "province", 10),
        ("충청북도", "", "province", 11),
        ("충청남도", "", "province", 12),
        ("전북특별자치도", "", "province", 13),
        ("전라남도", "", "province", 14),
        ("경상북도", "", "province", 15),
        ("경상남도", "", "province", 16),
        ("제주특별자치도", "", "province", 17),
        ("수원시", "경기도", "city", 101),
        ("용인시", "경기도", "city", 102),
        ("고양시", "경기도", "city", 103),
        ("창원시", "경상남도", "city", 104),
        ("성남시", "경기도", "city", 105),
        ("화성시", "경기도", "city", 106),
        ("청주시", "충청북도", "city", 107),
        ("부천시", "경기도", "city", 108),
        ("안산시", "경기도", "city", 109),
        ("안양시", "경기도", "city", 110),
        ("평택시", "경기도", "city", 111),
        ("포항시", "경상북도", "city", 112),
        ("천안시", "충청남도", "city", 113),
        ("전주시", "전북특별자치도", "city", 114),
        ("김해시", "경상남도", "city", 115),
    ]
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS region_options ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR(50) NOT NULL, "
            "parent_name VARCHAR(50) DEFAULT '' NOT NULL, "
            "region_type VARCHAR(20) DEFAULT 'province' NOT NULL, "
            "sort_order INTEGER DEFAULT 0 NOT NULL, "
            "is_active BOOLEAN DEFAULT 1 NOT NULL, "
            "created_at VARCHAR(20) NOT NULL, "
            "updated_at VARCHAR(20) NOT NULL, "
            "CONSTRAINT uq_region_options_name UNIQUE (name)"
            ")"
        ))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_region_options_name ON region_options (name)"))
        for name, parent_name, region_type, sort_order in region_options:
            connection.execute(text(
                "INSERT INTO region_options (name, parent_name, region_type, sort_order, is_active, created_at, updated_at) "
                "VALUES (:name, :parent_name, :region_type, :sort_order, 1, :created_at, :updated_at) "
                "ON CONFLICT(name) DO UPDATE SET "
                "parent_name = excluded.parent_name, "
                "region_type = excluded.region_type, "
                "sort_order = excluded.sort_order, "
                "is_active = 1, "
                "updated_at = excluded.updated_at"
            ), {
                "name": name,
                "parent_name": parent_name,
                "region_type": region_type,
                "sort_order": sort_order,
                "created_at": now_text,
                "updated_at": now_text,
            })


def migrate_industry_prompt_templates() -> None:
    """관리자 수정용 업종별 프롬프트 템플릿 테이블을 만들고 기본 데이터를 시딩합니다."""
    now_text = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    templates = [
        ("general", "일반 소상공인", "공통", "입력자료와 업체 페르소나를 우선하여 업종에 맞게 유연하게 작성합니다.", "문제 상황 → 해결 과정 → 결과 → 고객 가치 → 마무리", "지역명, 서비스명, 고객 문제, 문의 유도", "친근하지만 과장 없는 설명", "확인되지 않은 최저가, 무조건, 완벽 같은 단정 표현"),
        ("home_repair", "집수리/인테리어", "홈 케어 및 생활 시공", "울산에서 오랜 현장 경험을 가진 오박사 만능인테리어 기준으로 작성합니다. 집수리, 욕실, 방수, 도배, 장판, 보일러, 전기, 디지털도어락, 문 교체, 철거 같은 생활 시공을 실제 현장 이야기처럼 풀어냅니다. 문제 증상, 원인 진단, 작업 과정, 결과, 사후 관리 팁을 구체적으로 담고 고객이 안심할 수 있게 설명합니다.", "고객 불편과 현장 상황 → 방문 지역과 공간 상태 → 원인 진단 → 작업 과정 → 작업 후 변화 → 생활 관리 팁 → 연락 유도", "울산 집수리, 울산 북구 집수리, 욕실 리모델링, 누수 수리, 방수 공사, 도배 장판, 보일러 점검, 전기 수리, 디지털도어락, 문 교체, 타일 보수, 생활 인테리어, 오박사 만능인테리어", "40년 이상 현장을 다닌 생활 기술자의 말투로 작성합니다. 따뜻하지만 허세 없이, 고객의 불편을 먼저 이해하고 원인을 쉽게 설명합니다. 문장은 사람 냄새가 나야 하며 같은 표현을 반복하지 않습니다. 지역명은 자연스럽게 여러 번 분산 배치하고, 전화번호는 마지막 문의 문장에 한 번만 넣습니다.", "무조건, 완벽, 최저가, 100% 해결 같은 단정 표현. 경쟁업체 비방. 과도한 공포 마케팅. 확인되지 않은 보증. 같은 지역명과 같은 문장 구조의 반복. 전화번호 반복 노출."),
        ("boiler_facility", "보일러/설비", "홈 케어 및 생활 시공", "난방, 온수, 배관, 누수 문제를 안전과 생활 불편 중심으로 설명합니다.", "증상 → 점검 → 원인 → 조치 → 재발 방지", "보일러, 온수, 배관, 난방, 누수, 설비", "안전하고 신뢰감 있는 기술자 말투", "자격 없는 수리 표현, 과도한 위험 조장"),
        ("appliance_clean", "가전 세척/케어", "홈 케어 및 생활 시공", "에어컨, 세탁기, 후드 등 생활 가전의 위생과 체감 변화를 중심으로 작성합니다.", "오염 상태 → 분해/세척 → 결과 → 관리법", "에어컨청소, 세탁기청소, 냄새, 곰팡이, 위생", "깔끔하고 생활감 있는 설명", "건강 효과 단정, 의학적 효능 주장"),
        ("general_cleaning", "종합 청소", "홈 케어 및 생활 시공", "입주, 이사, 상가, 정기 청소의 전후 변화와 신뢰감을 중심으로 작성합니다.", "공간 상태 → 청소 범위 → 작업 과정 → 전후 변화", "입주청소, 이사청소, 상가청소, 정기청소", "성실하고 꼼꼼한 현장 말투", "무조건 새집처럼 같은 과장"),
        ("window_screen", "방충망/창호", "홈 케어 및 생활 시공", "생활 불편, 환기, 벌레 차단, 창호 사용감을 중심으로 작성합니다.", "불편 상황 → 제품/상태 확인 → 교체/수리 → 사용감", "방충망, 창호, 샷시, 환기, 벌레차단", "담백하고 실용적인 설명", "단열 성능 과장"),
        ("key_doorlock", "열쇠/도어락", "홈 케어 및 생활 시공", "보안, 긴급 상황, 교체 필요성을 신뢰감 있게 설명합니다.", "상황 발생 → 확인 → 교체/개방 → 사용 안내", "도어락, 열쇠, 번호키, 현관문, 보안", "침착하고 빠른 대응 느낌", "불안 조장, 범죄 악용 표현"),
        ("lighting_electric", "조명/전기공사", "홈 케어 및 생활 시공", "전기 안전, 조도 개선, 공간 분위기 변화를 중심으로 작성합니다.", "불편/고장 → 안전 확인 → 시공 → 결과", "조명, 전기공사, 콘센트, LED, 차단기", "정확하고 안전 중심 말투", "무자격 시공처럼 보이는 표현"),
        ("drain_unclog", "하수구/싱크대 막힘", "홈 케어 및 생활 시공", "냄새, 역류, 막힘 같은 생활 불편을 원인과 해결 중심으로 작성합니다.", "증상 → 원인 확인 → 작업 → 관리 팁", "하수구막힘, 싱크대막힘, 배수구, 냄새, 역류", "현장감 있고 안심시키는 말투", "혐오감 과도 강조"),
        ("restaurant", "음식점", "외식 및 라이프스타일", "음식, 온도, 향, 식감, 손님 분위기를 중심으로 작성합니다.", "계절감 → 메뉴 소개 → 식재료 → 조리 과정 → 맛 표현 → 재방문 유도", "맛집, 점심, 저녁, 가족외식, 메뉴명, 지역명", "따뜻하고 먹음직스러운 표현", "맛 보장, 건강 효능 단정"),
        ("meat_korean", "고깃집/한식", "외식 및 라이프스타일", "불향, 식사 자리, 가족/단체 모임, 반찬 구성을 중심으로 작성합니다.", "방문 상황 → 대표 메뉴 → 굽는 장면 → 식사 분위기 → 재방문", "고깃집, 한식, 숯불, 회식, 가족외식", "정겹고 푸짐한 말투", "원산지나 품질 근거 없는 단정"),
        ("cafe", "카페", "외식 및 라이프스타일", "공간 분위기, 커피 향, 디저트, 머무는 시간을 감성적으로 표현합니다.", "공간 분위기 → 향 → 음료 → 디저트 → 머무는 시간", "카페, 커피, 디저트, 분위기, 데이트", "차분하고 감성적인 말투", "지나친 감성 과장"),
        ("bakery_dessert", "베이커리/디저트", "외식 및 라이프스타일", "갓 구운 향, 식감, 선물/간식 상황을 중심으로 작성합니다.", "제품 소개 → 식감 → 어울리는 상황 → 구매 유도", "베이커리, 디저트, 빵집, 케이크, 선물", "부드럽고 달콤한 표현", "원재료 효능 과장"),
        ("pub_bar", "이자카야/포차", "외식 및 라이프스타일", "퇴근 후 분위기, 안주, 대화, 편안한 시간을 중심으로 작성합니다.", "하루 마무리 → 안주/메뉴 → 분위기 → 방문 유도", "이자카야, 포차, 술집, 안주, 모임", "편안하고 살짝 경쾌한 말투", "과음 조장"),
        ("mealkit_sidedish", "밀키트/반찬가게", "외식 및 라이프스타일", "집밥, 간편함, 신선함, 가족 식탁을 중심으로 작성합니다.", "고민 상황 → 메뉴 구성 → 조리/보관 → 식탁 활용", "반찬가게, 밀키트, 집밥, 도시락, 간편식", "생활밀착형 친근한 말투", "건강 효능 단정"),
        ("workshop_class", "공방/원데이클래스", "외식 및 라이프스타일", "체험 과정, 완성 결과, 추억과 선물 가치를 중심으로 작성합니다.", "참여 계기 → 체험 과정 → 완성품 → 추억", "공방, 원데이클래스, 체험, 취미, 만들기", "따뜻하고 섬세한 말투", "누구나 전문가처럼 된다는 과장"),
        ("partyroom_studio", "파티룸/스튜디오", "외식 및 라이프스타일", "공간, 사진, 모임 목적, 예약 장점을 중심으로 작성합니다.", "모임 목적 → 공간 소개 → 이용 장면 → 예약 안내", "파티룸, 스튜디오, 생일파티, 촬영, 모임", "밝고 실용적인 말투", "수용 인원 과장"),
        ("camping", "캠핑장", "외식 및 라이프스타일", "계절, 날씨, 자연 풍경, 가족·연인·친구 체험을 중심으로 작성합니다.", "도착 → 풍경 → 시설 → 체험 → 야경 → 추억 → 예약 유도", "캠핑장, 가족캠핑, 글램핑, 바베큐, 자연", "여행 에세이처럼 여유 있는 말투", "안전/시설 과장"),
        ("beauty_wellness", "뷰티/웰니스 일반", "뷰티 및 웰니스", "변화, 관리 과정, 편안함, 재방문 관리를 중심으로 작성합니다.", "고민 → 상담 → 관리 과정 → 변화 → 홈케어", "뷰티, 관리, 피부, 헤어, 웰니스", "섬세하고 배려 있는 말투", "의학적 효과 단정"),
        ("hair_salon", "미용실/헤어샵", "뷰티 및 웰니스", "상담, 얼굴형/스타일, 시술 과정, 손질법을 중심으로 작성합니다.", "고민 → 상담 → 시술 → 완성 → 손질 팁", "미용실, 헤어샵, 커트, 염색, 펌", "감각적이지만 과하지 않은 전문가 말투", "시술 결과 보장"),
        ("nail_art", "네일아트/패디", "뷰티 및 웰니스", "디자인, 색감, 계절감, 손끝 분위기를 중심으로 작성합니다.", "디자인 선택 → 시술 과정 → 완성 느낌 → 유지 팁", "네일, 패디, 젤네일, 네일아트, 디자인", "섬세하고 감각적인 말투", "유지 기간 단정"),
        ("skin_care", "피부관리/에스테틱", "뷰티 및 웰니스", "피부 고민, 상담, 관리 과정, 편안함을 중심으로 작성합니다.", "고민 → 상담 → 관리 → 체감 변화 → 홈케어", "피부관리, 에스테틱, 탄력, 보습, 진정", "차분하고 신뢰감 있는 말투", "치료, 완치 같은 의료 표현"),
        ("fitness_pt", "피트니스/PT", "뷰티 및 웰니스", "목표, 운동 습관, 자세 교정, 꾸준함을 중심으로 작성합니다.", "목표 → 현재 상태 → 운동 과정 → 변화 → 루틴", "PT, 헬스, 다이어트, 근력, 운동", "동기부여형이지만 현실적인 말투", "단기간 감량 보장"),
        ("body_massage", "바디케어/마사지", "뷰티 및 웰니스", "피로, 휴식, 관리 과정, 편안한 시간을 중심으로 작성합니다.", "피로 상황 → 관리 과정 → 휴식감 → 재방문", "마사지, 바디케어, 피로, 릴렉스, 관리", "부드럽고 안정적인 말투", "치료 효과 단정"),
        ("car_repair", "자동차 정비/카센터", "자동차 및 이동 수단", "증상, 점검, 부품, 안전 운행을 중심으로 작성합니다.", "증상 → 점검 → 원인 → 정비 → 안전 안내", "자동차정비, 카센터, 엔진오일, 브레이크, 점검", "정확하고 신뢰감 있는 정비사 말투", "위험 과장, 불필요한 교체 유도"),
        ("car_detailing", "디테일링/손세차", "자동차 및 이동 수단", "전후 변화, 광택, 실내 청결, 관리 만족감을 중심으로 작성합니다.", "차량 상태 → 작업 과정 → 전후 변화 → 관리 팁", "손세차, 디테일링, 광택, 실내클리닝, 유리막", "깔끔하고 디테일한 말투", "복원 한계 과장"),
        ("car_rental", "렌트카/출장차량", "자동차 및 이동 수단", "편리함, 일정, 차량 상태, 이동 목적을 중심으로 작성합니다.", "이용 상황 → 차량/서비스 → 편의성 → 예약 안내", "렌트카, 차량대여, 출장차량, 공항픽업", "친절하고 실용적인 말투", "보험/요금 조건 불명확 표현"),
        ("pet_beauty_hotel", "애견 미용/호텔", "반려동물 및 가족 케어", "반려동물의 편안함, 미용 과정, 보호자 안심을 중심으로 작성합니다.", "상담 → 상태 확인 → 미용/케어 → 보호자 안내", "애견미용, 애견호텔, 반려견, 목욕, 케어", "따뜻하고 조심스러운 말투", "동물 상태 과장, 의료 행위 표현"),
        ("veterinary_clinic", "동물병원", "반려동물 및 가족 케어", "보호자의 걱정, 진료 과정, 예방 관리 안내를 중심으로 작성합니다.", "증상/상담 → 진료 → 안내 → 관리 팁", "동물병원, 예방접종, 건강검진, 반려동물", "차분하고 신뢰감 있는 말투", "진단/치료 결과 단정"),
        ("flower_shop", "꽃집/플라워샵", "반려동물 및 가족 케어", "꽃의 색감, 선물 상황, 마음 전달을 중심으로 작성합니다.", "상황 → 꽃 선택 → 디자인 → 전달 감정", "꽃집, 꽃다발, 플라워샵, 선물, 기념일", "섬세하고 따뜻한 말투", "꽃 지속기간 과장"),
        ("kids_cafe", "키즈카페/어린이시설", "반려동물 및 가족 케어", "아이의 놀이, 안전, 부모의 휴식, 시설 안내를 중심으로 작성합니다.", "방문 상황 → 놀이공간 → 안전/위생 → 이용 안내", "키즈카페, 어린이시설, 실내놀이터, 가족나들이", "밝고 안심시키는 말투", "안전 보장 단정"),
        ("real_estate", "공인중개사", "로컬 전문 서비스 및 교육", "입지, 생활권, 거래 신뢰, 상담 과정을 중심으로 작성합니다.", "고객 니즈 → 매물/지역 → 장점 → 상담 유도", "부동산, 공인중개사, 아파트, 상가, 전세, 월세", "신중하고 정보 중심 말투", "시세 상승 보장"),
        ("education_academy", "보습/입시학원", "로컬 전문 서비스 및 교육", "학습 고민, 커리큘럼, 관리 방식, 성장 과정을 중심으로 작성합니다.", "학습 고민 → 진단 → 수업 방식 → 관리 → 상담 유도", "학원, 입시, 보습, 내신, 공부습관", "믿음직하고 차분한 교육자 말투", "성적 향상 보장"),
        ("study_cafe", "공유오피스/스터디카페", "로컬 전문 서비스 및 교육", "집중 환경, 좌석, 이용 편의, 조용한 분위기를 중심으로 작성합니다.", "이용 목적 → 공간 소개 → 편의시설 → 이용 안내", "스터디카페, 공유오피스, 공부공간, 좌석, 집중", "깔끔하고 정보 중심 말투", "절대 조용함 같은 단정"),
        ("professional_service", "행정사/세무사", "로컬 전문 서비스 및 교육", "복잡한 절차, 서류, 상담 신뢰, 문제 해결을 중심으로 작성합니다.", "고민/상황 → 절차 설명 → 준비 서류 → 상담 안내", "행정사, 세무사, 신고, 서류, 상담", "정확하고 차분한 전문가 말투", "법률/세무 결과 보장"),
        ("moving_service", "이삿짐/용달", "로컬 전문 서비스 및 교육", "이사 상황, 짐 운반, 시간 약속, 안전한 이동을 중심으로 작성합니다.", "이사 상황 → 견적/준비 → 운반 과정 → 마무리", "이사, 용달, 원룸이사, 사무실이사, 운반", "성실하고 현장감 있는 말투", "파손 없음 보장 단정"),
        ("logistics", "물류/3PL", "로컬 전문 서비스 및 교육", "정확성, 오배송 감소, 출고 속도, 재고 관리, 비용 효율을 중심으로 작성합니다.", "입고 → 보관 → 포장 → 출고 → 배송 안정성 → 고객사 효율", "물류대행, 3PL, 풀필먼트, 택배대행, 재고관리", "감성보다 신뢰, 시스템, 운영 안정성 중심", "100% 무오류 같은 과장")
    ]
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS industry_prompt_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                industry_key VARCHAR(50) NOT NULL UNIQUE,
                label VARCHAR(100) NOT NULL,
                category VARCHAR(100) NOT NULL DEFAULT '기타',
                prompt_guidance TEXT NOT NULL DEFAULT '',
                content_flow TEXT NOT NULL DEFAULT '',
                keyword_hint TEXT NOT NULL DEFAULT '',
                tone_hint TEXT NOT NULL DEFAULT '',
                avoid_hint TEXT NOT NULL DEFAULT '',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at VARCHAR(20) NOT NULL,
                updated_at VARCHAR(20) NOT NULL
            )
        """))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_industry_prompt_templates_key ON industry_prompt_templates (industry_key)"))
        for idx, item in enumerate(templates, start=1):
            connection.execute(text("""
                INSERT OR IGNORE INTO industry_prompt_templates
                (industry_key, label, category, prompt_guidance, content_flow, keyword_hint, tone_hint, avoid_hint, is_active, sort_order, created_at, updated_at)
                VALUES (:industry_key, :label, :category, :prompt_guidance, :content_flow, :keyword_hint, :tone_hint, :avoid_hint, 1, :sort_order, :created_at, :updated_at)
            """), {
                "industry_key": item[0],
                "label": item[1],
                "category": item[2],
                "prompt_guidance": item[3],
                "content_flow": item[4],
                "keyword_hint": item[5],
                "tone_hint": item[6],
                "avoid_hint": item[7],
                "sort_order": idx,
                "created_at": now_text,
                "updated_at": now_text,
            })
        connection.execute(text("""
            UPDATE industry_prompt_templates
            SET
                label = :label,
                category = :category,
                prompt_guidance = :prompt_guidance,
                content_flow = :content_flow,
                keyword_hint = :keyword_hint,
                tone_hint = :tone_hint,
                avoid_hint = :avoid_hint,
                is_active = 1,
                updated_at = :updated_at
            WHERE industry_key = 'home_repair'
              AND prompt_guidance = '문제 증상, 원인, 안전 확인, 작업 결과를 구체적으로 작성합니다.'
        """), {
            "label": "집수리/인테리어",
            "category": "홈 케어 및 생활 시공",
            "prompt_guidance": "울산에서 오랜 현장 경험을 가진 오박사 만능인테리어 기준으로 작성합니다. 집수리, 욕실, 방수, 도배, 장판, 보일러, 전기, 디지털도어락, 문 교체, 철거 같은 생활 시공을 실제 현장 이야기처럼 풀어냅니다. 문제 증상, 원인 진단, 작업 과정, 결과, 사후 관리 팁을 구체적으로 담고 고객이 안심할 수 있게 설명합니다.",
            "content_flow": "고객 불편과 현장 상황 → 방문 지역과 공간 상태 → 원인 진단 → 작업 과정 → 작업 후 변화 → 생활 관리 팁 → 연락 유도",
            "keyword_hint": "울산 집수리, 울산 북구 집수리, 욕실 리모델링, 누수 수리, 방수 공사, 도배 장판, 보일러 점검, 전기 수리, 디지털도어락, 문 교체, 타일 보수, 생활 인테리어, 오박사 만능인테리어",
            "tone_hint": "40년 이상 현장을 다닌 생활 기술자의 말투로 작성합니다. 따뜻하지만 허세 없이, 고객의 불편을 먼저 이해하고 원인을 쉽게 설명합니다. 문장은 사람 냄새가 나야 하며 같은 표현을 반복하지 않습니다. 지역명은 자연스럽게 여러 번 분산 배치하고, 전화번호는 마지막 문의 문장에 한 번만 넣습니다.",
            "avoid_hint": "무조건, 완벽, 최저가, 100% 해결 같은 단정 표현. 경쟁업체 비방. 과도한 공포 마케팅. 확인되지 않은 보증. 같은 지역명과 같은 문장 구조의 반복. 전화번호 반복 노출.",
            "updated_at": now_text,
        })


def migrate_weather_tables() -> None:
    """날씨 시간별 원본과 일별 요약 테이블을 멱등적으로 생성합니다."""
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS weather_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region VARCHAR(50) NOT NULL,
                weather VARCHAR(50) NOT NULL,
                temperature FLOAT,
                source VARCHAR(50) NOT NULL DEFAULT 'prompt_builder',
                observed_at VARCHAR(20) NOT NULL,
                created_at VARCHAR(20) NOT NULL
            )
        """))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_weather_snapshots_region ON weather_snapshots (region)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_weather_snapshots_observed_at ON weather_snapshots (observed_at)"))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS weather_daily_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region VARCHAR(50) NOT NULL,
                date VARCHAR(10) NOT NULL,
                avg_temp FLOAT,
                min_temp FLOAT,
                max_temp FLOAT,
                dominant_weather VARCHAR(50),
                summary_text TEXT,
                created_at VARCHAR(20) NOT NULL,
                CONSTRAINT uq_weather_daily_region_date UNIQUE (region, date)
            )
        """))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_weather_daily_summaries_region ON weather_daily_summaries (region)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_weather_daily_summaries_date ON weather_daily_summaries (date)"))


def migrate_project_assets_table() -> None:
    """프로젝트 산출물 메타데이터 테이블을 생성하고 Mission 7 확장 컬럼을 보강합니다."""
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS project_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username VARCHAR(100) DEFAULT '',
                project_id INTEGER,
                project_key VARCHAR(160) NOT NULL,
                asset_group_key VARCHAR(100) DEFAULT '',
                version INTEGER DEFAULT 1,
                is_active BOOLEAN DEFAULT 1,
                asset_type VARCHAR(30) NOT NULL,
                role VARCHAR(60) DEFAULT '',
                original_filename VARCHAR(255) DEFAULT '',
                stored_filename VARCHAR(255) NOT NULL,
                relative_path TEXT NOT NULL,
                public_url TEXT NOT NULL,
                company_name VARCHAR(160) DEFAULT '',
                keyword VARCHAR(160) DEFAULT '',
                alt_text TEXT DEFAULT '',
                caption TEXT DEFAULT '',
                mime_type VARCHAR(100) DEFAULT '',
                file_size INTEGER DEFAULT 0,
                display_order INTEGER DEFAULT 0,
                width INTEGER,
                height INTEGER,
                duration_seconds FLOAT,
                status TEXT DEFAULT 'READY' CHECK(status IN ('READY', 'PROCESSING', 'FAILED', 'DELETED')),
                source TEXT DEFAULT 'UPLOAD' CHECK(source IN ('UPLOAD', 'AI', 'SLIDESHOW', 'THUMBNAIL', 'VIDEO', 'IMPORT')),
                tags TEXT DEFAULT '',
                created_at VARCHAR(20) NOT NULL,
                updated_at VARCHAR(20) NOT NULL
            )
        """))

        inspector = inspect(engine)
        existing = {column["name"] for column in inspector.get_columns("project_assets")}
        alter_statements = []
        if "asset_group_key" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN asset_group_key VARCHAR(100) DEFAULT ''")
        if "version" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN version INTEGER DEFAULT 1")
        if "is_active" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN is_active BOOLEAN DEFAULT 1")
        if "width" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN width INTEGER")
        if "height" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN height INTEGER")
        if "duration_seconds" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN duration_seconds FLOAT")
        if "status" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN status TEXT DEFAULT 'READY' CHECK(status IN ('READY', 'PROCESSING', 'FAILED', 'DELETED'))")
        if "source" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN source TEXT DEFAULT 'UPLOAD' CHECK(source IN ('UPLOAD', 'AI', 'SLIDESHOW', 'THUMBNAIL', 'VIDEO', 'IMPORT'))")
        if "tags" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN tags TEXT DEFAULT ''")
        if "display_order" not in existing:
            alter_statements.append("ALTER TABLE project_assets ADD COLUMN display_order INTEGER DEFAULT 0")
        for statement in alter_statements:
            connection.execute(text(statement))

        connection.execute(text("""
            UPDATE project_assets
            SET asset_group_key = CASE
                WHEN asset_group_key IS NULL OR asset_group_key = '' THEN 'legacy_' || id
                ELSE asset_group_key
            END,
            version = CASE WHEN version IS NULL OR version < 1 THEN 1 ELSE version END,
            is_active = CASE WHEN is_active IS NULL THEN 1 ELSE is_active END,
            status = CASE
                WHEN status IN ('READY', 'PROCESSING', 'FAILED', 'DELETED') THEN status
                WHEN status IS NULL OR status = '' THEN 'READY'
                ELSE 'READY'
            END,
            source = CASE
                WHEN source IN ('UPLOAD', 'AI', 'SLIDESHOW', 'THUMBNAIL', 'VIDEO', 'IMPORT') THEN source
                WHEN lower(COALESCE(source, '')) LIKE '%slide%' THEN 'SLIDESHOW'
                WHEN lower(COALESCE(source, '')) LIKE '%thumb%' THEN 'THUMBNAIL'
                WHEN lower(COALESCE(source, '')) LIKE '%video%' THEN 'VIDEO'
                WHEN lower(COALESCE(source, '')) LIKE '%ai%' THEN 'AI'
                WHEN lower(COALESCE(source, '')) LIKE '%import%' THEN 'IMPORT'
                ELSE 'UPLOAD'
            END,
            tags = COALESCE(tags, ''),
            display_order = COALESCE(display_order, 0)
        """))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_user_id ON project_assets (user_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_project_id ON project_assets (project_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_project_key ON project_assets (project_key)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_asset_group_key ON project_assets (asset_group_key)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_asset_type ON project_assets (asset_type)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_role ON project_assets (role)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_status ON project_assets (status)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_source ON project_assets (source)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_is_active ON project_assets (is_active)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_display_order ON project_assets (display_order)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_project_assets_created_at ON project_assets (created_at)"))


# FastAPI 라우터에서 의존성 주입(Dependency Injection)으로 사용할 세션 제너레이터
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
