from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Final


ROOT: Final[Path] = Path(
    os.getenv("STORYMAKER_BETA_ROOT", "/home/bourne/StoryMaker_1/StoryMaker_beta")
)
PROMPT_DB_PATH: Final[Path] = Path(
    os.getenv(
        "STORYMAKER_PROMPT_DB",
        "/home/bourne/StoryMaker_1/data/prompt_db/storymaker_prompts.db",
    )
)
TEMPLATE_DIR: Final[Path] = ROOT / "data" / "prompt_templates"

DEFAULT_PROMPT_KEY: Final[str] = "local_professional_service"

FOOD_INDUSTRY_KEYS: Final[set[str]] = {
    "bar",
    "bakery",
    "bakery_dessert",
    "bbq",
    "beef_ribs",
    "bunsik_korean_snack",
    "cafe",
    "chinese_restaurant",
    "dakgalbi",
    "delivery_food",
    "dessert",
    "dosirak_catering",
    "fastfood_burger",
    "food",
    "food_service",
    "fruit_shop",
    "hof_pub",
    "japanese_restaurant",
    "jokbal_bossam",
    "kids_cafe",
    "latenight_food",
    "mealkit_sidedish",
    "meat_korean",
    "noodle_soup",
    "omakase",
    "pizza_western",
    "pork_ribs",
    "pub",
    "pub_bar",
    "restaurant",
    "seolleongtang_gomtang",
    "takeout",
    "teppanyaki",
    "traditional_dessert",
    "tteokgalbi",
    "vietnamese_pho",
    "wine_bar",
}

LOCAL_PROFESSIONAL_INDUSTRY_KEYS: Final[set[str]] = {
    "home_repair",
    "boiler_facility",
    "appliance_clean",
    "general_cleaning",
    "window_screen",
    "key_doorlock",
    "lighting_electric",
    "drain_unclog",
}

MEDICAL_HEALTH_INDUSTRY_KEYS: Final[set[str]] = {
    "안경원",
    "dental_clinic",
    "oriental_clinic",
    "pharmacy",
    "plastic_surgery",
    "orthopedic",
    "internal_medicine",
    "general_surgery",
}

LIFESTYLE_EXPERIENCE_SPACE_INDUSTRY_KEYS: Final[set[str]] = {
    "workshop_class",
    "partyroom_studio",
    "camping",
    "handcraft_workshop",
    "small_theater",
    "vr_game_center",
    "event_planning",
}

AUTOMOTIVE_MOBILITY_INDUSTRY_KEYS: Final[set[str]] = {
    "car_repair",
    "car_detailing",
    "car_rental",
    "tire_shop",
    "bicycle_shop",
    "car_window_tinting",
    "car_dent_paint",
    "used_car_dealer",
    "driving_school",
}

LOCAL_PROFESSIONAL_EDUCATION_INDUSTRY_KEYS: Final[set[str]] = {
    "real_estate",
    "education_academy",
    "study_cafe",
    "professional_service",
    "moving_service",
    "logistics",
    "photo_studio",
    "tutoring_lesson",
    "labor_attorney",
    "english_academy",
    "art_academy",
    "math_academy",
    "clothing_repair",
    "music_academy",
    "martial_arts_gym",
    "coding_academy",
    "legal_service",
    "fortune_telling",
    "unmanned_studycafe",
}

SPORTS_TRAVEL_LEISURE_INDUSTRY_KEYS: Final[set[str]] = {
    "golf_lesson",
    "screen_golf",
    "travel_agency",
    "pension_poolvilla",
    "indoor_fishing_leisure",
}

PET_FAMILY_CARE_INDUSTRY_KEYS: Final[set[str]] = {
    "pet_beauty_hotel",
    "veterinary_clinic",
    "flower_shop",
    "kids_cafe",
    "kids_education",
    "pet_hospital",
    "child_birth_party",
    "silver_care",
    "childcare",
    "grooming_supply",
    "pet_kindergarten",
    "pet_bakery",
    "pet_funeral",
    "postnatal_care",
    "funeral_service",
}

BEAUTY_WELLNESS_INDUSTRY_KEYS: Final[set[str]] = {
    "beauty_wellness",
    "hair_salon",
    "nail_art",
    "skin_care",
    "fitness_pt",
    "body_massage",
    "eyelash_brow",
    "yoga_pilates",
    "waxing_shop",
    "body_profile_pt",
    "scalp_hair_loss",
    "body_alignment",
}

SEED_TEMPLATES: Final[dict[str, tuple[str, str, str, str]]] = {
    "local_professional_service": (
        "로컬 전문 서비스",
        "local_service",
        "3.9",
        "local_professional_service.md",
    ),
    "food_service": (
        "외식·카페 업종",
        "food",
        "4.3",
        "food_service.md",
    ),
    "medical_health": (
        "의료·건강 업종",
        "medical",
        "1.0",
        "medical_health.md",
    ),
    "automotive_mobility": (
        "자동차 및 이동 수단 업종",
        "automotive",
        "1.0",
        "automotive_mobility.md",
    ),
    "pet_family_care": (
        "반려동물 및 가족 케어 업종",
        "pet_family",
        "1.0",
        "pet_family_care.md",
    ),
    "local_professional_education": (
        "로컬 전문 서비스 및 교육 업종",
        "professional_education",
        "1.0",
        "local_professional_education.md",
    ),
    "sports_travel_leisure": (
        "스포츠·여행 및 레저 업종",
        "sports_travel",
        "1.0",
        "sports_travel_leisure.md",
    ),
    "lifestyle_experience_space": (
        "라이프스타일·체험 및 공간 업종",
        "lifestyle",
        "1.0",
        "lifestyle_experience_space.md",
    ),
    "beauty_wellness": (
        "뷰티 및 웰니스 업종",
        "beauty",
        "1.0",
        "beauty_wellness.md",
    ),
}


def _now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    PROMPT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(PROMPT_DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _read_seed(filename: str) -> str:
    path = TEMPLATE_DIR / filename
    text = path.read_text(encoding="utf-8").strip()
    if len(text) < 500:
        raise RuntimeError(f"프롬프트 원본이 너무 짧습니다: {path}")
    return text


def ensure_prompt_database() -> Path:
    stamp = _now_text()
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS prompt_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                category_group TEXT NOT NULL,
                version TEXT NOT NULL,
                content TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prompt_category_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                industry_key TEXT NOT NULL UNIQUE,
                prompt_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(prompt_key) REFERENCES prompt_templates(prompt_key)
            );

            CREATE INDEX IF NOT EXISTS ix_prompt_templates_active
                ON prompt_templates(is_active, prompt_key);
            CREATE INDEX IF NOT EXISTS ix_prompt_category_prompt_key
                ON prompt_category_mappings(prompt_key);
            """
        )

        for prompt_key, (name, category_group, seed_version, filename) in SEED_TEMPLATES.items():
            existing = connection.execute(
                "SELECT version FROM prompt_templates WHERE prompt_key=?",
                (prompt_key,),
            ).fetchone()
            seed_content = _read_seed(filename)
            if existing:
                current_version = str(existing["version"] or "0")
                try:
                    current_parts = tuple(int(part) for part in current_version.split("."))
                    seed_parts = tuple(int(part) for part in seed_version.split("."))
                except ValueError:
                    current_parts = (9999,)
                    seed_parts = (0,)
                if current_parts < seed_parts:
                    connection.execute(
                        """
                        UPDATE prompt_templates
                        SET name=?, category_group=?, version=?, content=?, updated_at=?
                        WHERE prompt_key=?
                        """,
                        (name, category_group, seed_version, seed_content, stamp, prompt_key),
                    )
                continue
            connection.execute(
                """
                INSERT INTO prompt_templates (
                    prompt_key, name, category_group, version, content,
                    is_active, is_default, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    prompt_key,
                    name,
                    category_group,
                    seed_version,
                    seed_content,
                    1 if prompt_key == DEFAULT_PROMPT_KEY else 0,
                    stamp,
                    stamp,
                ),
            )

        for industry_key in sorted(FOOD_INDUSTRY_KEYS):
            connection.execute(
                """
                INSERT INTO prompt_category_mappings (
                    industry_key, prompt_key, created_at, updated_at
                ) VALUES (?, 'food_service', ?, ?)
                ON CONFLICT(industry_key) DO UPDATE SET
                    prompt_key=excluded.prompt_key,
                    updated_at=excluded.updated_at
                """,
                (industry_key, stamp, stamp),
            )

        for industry_key in sorted(LOCAL_PROFESSIONAL_INDUSTRY_KEYS):
            connection.execute(
                """
                INSERT INTO prompt_category_mappings (
                    industry_key, prompt_key, created_at, updated_at
                ) VALUES (?, 'local_professional_service', ?, ?)
                ON CONFLICT(industry_key) DO UPDATE SET
                    prompt_key=excluded.prompt_key,
                    updated_at=excluded.updated_at
                """,
                (industry_key, stamp, stamp),
            )

        for industry_key in sorted(MEDICAL_HEALTH_INDUSTRY_KEYS):
            connection.execute(
                """
                INSERT INTO prompt_category_mappings (
                    industry_key, prompt_key, created_at, updated_at
                ) VALUES (?, 'medical_health', ?, ?)
                ON CONFLICT(industry_key) DO UPDATE SET
                    prompt_key=excluded.prompt_key,
                    updated_at=excluded.updated_at
                """,
                (industry_key, stamp, stamp),
            )

        for industry_key in sorted(AUTOMOTIVE_MOBILITY_INDUSTRY_KEYS):
            connection.execute(
                """
                INSERT INTO prompt_category_mappings (
                    industry_key, prompt_key, created_at, updated_at
                ) VALUES (?, 'automotive_mobility', ?, ?)
                ON CONFLICT(industry_key) DO UPDATE SET
                    prompt_key=excluded.prompt_key,
                    updated_at=excluded.updated_at
                """,
                (industry_key, stamp, stamp),
            )

        for industry_key in sorted(LOCAL_PROFESSIONAL_EDUCATION_INDUSTRY_KEYS):
            connection.execute(
                """
                INSERT INTO prompt_category_mappings (
                    industry_key, prompt_key, created_at, updated_at
                ) VALUES (?, 'local_professional_education', ?, ?)
                ON CONFLICT(industry_key) DO UPDATE SET
                    prompt_key=excluded.prompt_key,
                    updated_at=excluded.updated_at
                """,
                (industry_key, stamp, stamp),
            )

        for industry_key in sorted(SPORTS_TRAVEL_LEISURE_INDUSTRY_KEYS):
            connection.execute(
                """
                INSERT INTO prompt_category_mappings (
                    industry_key, prompt_key, created_at, updated_at
                ) VALUES (?, 'sports_travel_leisure', ?, ?)
                ON CONFLICT(industry_key) DO UPDATE SET
                    prompt_key=excluded.prompt_key,
                    updated_at=excluded.updated_at
                """,
                (industry_key, stamp, stamp),
            )

        for industry_key in sorted(PET_FAMILY_CARE_INDUSTRY_KEYS):
            connection.execute(
                """
                INSERT INTO prompt_category_mappings (
                    industry_key, prompt_key, created_at, updated_at
                ) VALUES (?, 'pet_family_care', ?, ?)
                ON CONFLICT(industry_key) DO UPDATE SET
                    prompt_key=excluded.prompt_key,
                    updated_at=excluded.updated_at
                """,
                (industry_key, stamp, stamp),
            )

        for industry_key in sorted(LIFESTYLE_EXPERIENCE_SPACE_INDUSTRY_KEYS):
            connection.execute(
                """
                INSERT INTO prompt_category_mappings (
                    industry_key, prompt_key, created_at, updated_at
                ) VALUES (?, 'lifestyle_experience_space', ?, ?)
                ON CONFLICT(industry_key) DO UPDATE SET
                    prompt_key=excluded.prompt_key,
                    updated_at=excluded.updated_at
                """,
                (industry_key, stamp, stamp),
            )

        for industry_key in sorted(BEAUTY_WELLNESS_INDUSTRY_KEYS):
            connection.execute(
                """
                INSERT INTO prompt_category_mappings (
                    industry_key, prompt_key, created_at, updated_at
                ) VALUES (?, 'beauty_wellness', ?, ?)
                ON CONFLICT(industry_key) DO UPDATE SET
                    prompt_key=excluded.prompt_key,
                    updated_at=excluded.updated_at
                """,
                (industry_key, stamp, stamp),
            )
        connection.commit()
    return PROMPT_DB_PATH


def normalize_industry_key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def select_prompt_key(industry_key: object) -> str:
    ensure_prompt_database()
    normalized = normalize_industry_key(industry_key)
    if normalized:
        with _connect() as connection:
            row = connection.execute(
                """
                SELECT m.prompt_key
                FROM prompt_category_mappings AS m
                JOIN prompt_templates AS t ON t.prompt_key=m.prompt_key
                WHERE m.industry_key=? AND t.is_active=1
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            if row:
                return str(row["prompt_key"])
    return DEFAULT_PROMPT_KEY


def load_prompt_template(industry_key: object) -> tuple[str, str, str]:
    prompt_key = select_prompt_key(industry_key)
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT prompt_key, version, content
            FROM prompt_templates
            WHERE prompt_key=? AND is_active=1
            LIMIT 1
            """,
            (prompt_key,),
        ).fetchone()
        if not row and prompt_key != DEFAULT_PROMPT_KEY:
            row = connection.execute(
                """
                SELECT prompt_key, version, content
                FROM prompt_templates
                WHERE prompt_key=? AND is_active=1
                LIMIT 1
                """,
                (DEFAULT_PROMPT_KEY,),
            ).fetchone()
        if not row:
            raise RuntimeError("활성 프롬프트를 찾지 못했습니다.")
        return str(row["content"]), str(row["prompt_key"]), str(row["version"])


def save_prompt_template(industry_key: object, content: str) -> tuple[str, str]:
    prompt = str(content or "").strip()
    if len(prompt) < 500:
        raise ValueError("프롬프트 내용이 너무 짧습니다.")
    prompt_key = select_prompt_key(industry_key)
    stamp = _now_text()
    with _connect() as connection:
        row = connection.execute(
            "SELECT version FROM prompt_templates WHERE prompt_key=? AND is_active=1 LIMIT 1",
            (prompt_key,),
        ).fetchone()
        if not row:
            raise RuntimeError("활성 프롬프트를 찾지 못했습니다.")
        current = str(row["version"] or "1.0")
        parts = current.split(".", 1)
        try:
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            version = f"{major}.{minor + 1}"
        except ValueError:
            version = current
        connection.execute(
            "UPDATE prompt_templates SET content=?, version=?, updated_at=? WHERE prompt_key=?",
            (prompt, version, stamp, prompt_key),
        )
        connection.commit()
    return prompt_key, version
