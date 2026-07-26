#!/usr/bin/env python3
"""StoryMaker Beta 비공개 운영 데이터 폴더형 백업.

대상
- StoryMaker_beta/data/storymaker_beta.db
- StoryMaker_beta/data/jobs/

목적지
- /mnt/lms_ssd/StoryMaker_Backup/Beta_Private/YYYY-MM-DD/HHMMSS/

원본 파일은 변경하거나 삭제하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SOURCE_ROOT = Path("/home/bourne/StoryMaker_1/StoryMaker_beta")
SOURCE_DB = SOURCE_ROOT / "data" / "storymaker_beta.db"
SOURCE_JOBS = SOURCE_ROOT / "data" / "jobs"
BACKUP_ROOT = Path("/mnt/lms_ssd/StoryMaker_Backup/Beta_Private")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_jobs(source: Path, destination: Path) -> tuple[int, int]:
    file_count = 0
    total_bytes = 0
    destination.mkdir(parents=True, exist_ok=True)

    if not source.exists():
        return file_count, total_bytes

    for current_root, dir_names, file_names in os.walk(source):
        current_root_path = Path(current_root)
        relative_root = current_root_path.relative_to(source)
        destination_root = destination / relative_root
        destination_root.mkdir(parents=True, exist_ok=True)

        for directory_name in dir_names:
            (destination_root / directory_name).mkdir(parents=True, exist_ok=True)

        for file_name in file_names:
            source_file = current_root_path / file_name
            destination_file = destination_root / file_name
            copy_file(source_file, destination_file)
            file_count += 1
            total_bytes += source_file.stat().st_size

    return file_count, total_bytes


def backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=30) as source_db:
        with sqlite3.connect(destination) as destination_db:
            source_db.backup(destination_db)
            check = destination_db.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise RuntimeError(f"백업 DB integrity_check 실패: {check}")


def main() -> int:
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(f"DB 파일이 없습니다: {SOURCE_DB}")

    if not BACKUP_ROOT.parent.is_dir():
        raise FileNotFoundError(f"DellMusic 마운트 경로가 없습니다: {BACKUP_ROOT.parent}")

    now = datetime.now()
    backup_dir = BACKUP_ROOT / now.strftime("%Y-%m-%d") / now.strftime("%H%M%S")
    database_dir = backup_dir / "database"
    jobs_dir = backup_dir / "jobs"
    backup_db = database_dir / SOURCE_DB.name

    backup_dir.mkdir(parents=True, exist_ok=False)

    backup_sqlite(SOURCE_DB, backup_db)
    job_file_count, job_total_bytes = copy_jobs(SOURCE_JOBS, jobs_dir)

    manifest = {
        "created_at": now.isoformat(timespec="seconds"),
        "source_root": str(SOURCE_ROOT),
        "backup_root": str(backup_dir),
        "database": {
            "source": str(SOURCE_DB),
            "backup": str(backup_db),
            "size_bytes": backup_db.stat().st_size,
            "sha256": sha256_file(backup_db),
            "integrity_check": "ok",
        },
        "jobs": {
            "source": str(SOURCE_JOBS),
            "backup": str(jobs_dir),
            "file_count": job_file_count,
            "total_bytes": job_total_bytes,
        },
        "compressed": False,
        "automatic_deletion": False,
    }

    manifest_path = backup_dir / "backup_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    latest_file = BACKUP_ROOT / "LATEST_BACKUP.txt"
    latest_file.write_text(str(backup_dir) + "\n", encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"BACKUP_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
