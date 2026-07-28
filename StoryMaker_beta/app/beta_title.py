from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_TITLE_PREFIX_RE = re.compile(
    r"^\s*(?:(?:\(\s*\d+\s*\)|\[\s*\d+\s*\]|\d+\s*[.)．、:：])\s*)+"
)


def clean_beta_title(value: object, fallback: str = "") -> str:
    """Remove only leading numbered-list markers such as '1.', '1)', '(1)', '[1]'."""
    raw = str(value or "").strip()
    cleaned = _TITLE_PREFIX_RE.sub("", raw).strip()
    return cleaned or str(fallback or "").strip()


def persist_beta_job_title(db_path: Path, beta_job_id: str, title: object) -> str:
    """Normalize and persist one Beta job title in the beta_jobs table."""
    cleaned = clean_beta_title(title)
    if not cleaned or not beta_job_id or not db_path.is_file():
        return cleaned
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE beta_jobs SET title=? WHERE beta_job_id=?",
            (cleaned, str(beta_job_id)),
        )
        connection.commit()
    return cleaned
