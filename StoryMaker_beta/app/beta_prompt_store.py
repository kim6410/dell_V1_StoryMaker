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
    "cafe",
    "dessert",
    "bakery",
    "bakery_dessert",
    "restaurant",
    "meat_korean",
    "mealkit_sidedish",
    "food",
    "food_service",
    "delivery_food",
    "takeout",
    "bar",
    "pub",
    "pub_bar",
    "kids_cafe",
}

SEED_TEMPLATES: Final[dict[str, tuple[str, str, str, str]]] = {
    "local_professional_service": (
        "로컬 전문 서비스",
        "local_service",
        "1.0",
        "local_professional_service.md",
    ),
    "food_service": (
        "외식·카페 업종",
        "food",
        "1.2",
        "food_service.md",
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
                ON CONFLICT(industry_key) DO NOTHING
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
