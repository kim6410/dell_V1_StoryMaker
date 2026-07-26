#!/usr/bin/env python3
"""StoryMaker V1 + Beta 완전 복구용 비공개 폴더 백업.

압축하지 않는다.
원본을 삭제하거나 이동하지 않는다.
날짜별 스냅샷에는 DB, Beta 작업/큐, 환경파일, 운영 설정을 저장한다.
대용량 결과물·모델·음악·글꼴은 Recovery_Mirror/current에 증분 복사한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path("/home/bourne/StoryMaker_1")
BACKUP_ROOT = Path("/mnt/lms_ssd/StoryMaker_Backup")
SNAPSHOT_ROOT = BACKUP_ROOT / "Full_Private"
MIRROR_ROOT = BACKUP_ROOT / "Recovery_Mirror" / "current"

SQLITE_SOURCES = [
    ROOT / "StoryMaker_beta/data/storymaker_beta.db",
    ROOT / "database/storymaker.db",
    ROOT / "database/content_intelligence.db",
    ROOT / "database/content_performance.db",
]

SNAPSHOT_DIRECTORIES = [
    (ROOT / "StoryMaker_beta/data/jobs", "beta/jobs"),
    (ROOT / "StoryMaker_beta/data/gemini_queue", "beta/gemini_queue"),
]

SECRET_FILES = [
    (ROOT / "StoryMaker_beta/.env", "secrets/StoryMaker_beta.env"),
    (ROOT / "storymaker-web/.env", "secrets/storymaker-web.env"),
    (ROOT / "supertonic/.env.v1-podcast", "secrets/supertonic.env.v1-podcast"),
]

RUNTIME_FILES = [
    (Path("/etc/systemd/system/storymaker-beta.service"), "runtime/systemd/storymaker-beta.service"),
    (Path("/etc/systemd/system/storymaker-v1-podcast-api.service"), "runtime/systemd/storymaker-v1-podcast-api.service"),
    (Path("/etc/systemd/system/storymaker-v1-supertonic3.service"), "runtime/systemd/storymaker-v1-supertonic3.service"),
    (Path("/etc/systemd/system/storymaker-beta-private-backup.service"), "runtime/systemd/storymaker-beta-private-backup.service"),
    (Path("/etc/systemd/system/storymaker-beta-private-backup.timer"), "runtime/systemd/storymaker-beta-private-backup.timer"),
]

MIRROR_DIRECTORIES = [
    (ROOT / "output_results", "v1/output_results"),
    (ROOT / "storymaker-web/backend/app/static/v1", "v1/static_v1_complete"),
    (ROOT / "storymaker-web/backend/app/assets/fonts", "v1/backend_fonts"),
    (ROOT / "supertonic/music", "v1/music"),
    (ROOT / "supertonic/user_jobs", "v1/supertonic_user_jobs"),
    (ROOT / "supertonic/slid_refactored/fonts", "v1/slideshow_fonts"),
    (ROOT / "Supertonic3", "v1/Supertonic3_runtime"),
]

SKIP_NAMES = {"__pycache__", ".git", "node_modules"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return source.stat().st_size


def copy_tree(source: Path, destination: Path, *, incremental: bool) -> dict[str, int]:
    stats = {"files_seen": 0, "files_copied": 0, "bytes_copied": 0}
    destination.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        return stats

    for current_root, dir_names, file_names in os.walk(source):
        dir_names[:] = [name for name in dir_names if name not in SKIP_NAMES]
        current = Path(current_root)
        relative = current.relative_to(source)
        target_root = destination / relative
        target_root.mkdir(parents=True, exist_ok=True)

        for file_name in file_names:
            source_file = current / file_name
            target_file = target_root / file_name
            stats["files_seen"] += 1
            should_copy = True
            if incremental and target_file.exists():
                source_stat = source_file.stat()
                target_stat = target_file.stat()
                should_copy = (
                    source_stat.st_size != target_stat.st_size
                    or int(source_stat.st_mtime) > int(target_stat.st_mtime)
                )
            if should_copy:
                stats["bytes_copied"] += copy_file(source_file, target_file)
                stats["files_copied"] += 1
    return stats


def backup_sqlite(source: Path, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=60) as source_db:
        with sqlite3.connect(destination) as destination_db:
            source_db.backup(destination_db)
            result = destination_db.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise RuntimeError(f"DB 무결성 검사 실패: {source} -> {result}")
    return {
        "source": str(source),
        "backup": str(destination),
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "integrity_check": "ok",
    }


def command_output(command: list[str]) -> str:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
    except Exception as error:
        return f"ERROR: {error}"


def main() -> int:
    if not BACKUP_ROOT.parent.is_dir():
        raise FileNotFoundError(f"DellMusic 마운트가 없습니다: {BACKUP_ROOT.parent}")

    now = datetime.now()
    snapshot_dir = SNAPSHOT_ROOT / now.strftime("%Y-%m-%d") / now.strftime("%H%M%S")
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    MIRROR_ROOT.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "created_at": now.isoformat(timespec="seconds"),
        "snapshot_dir": str(snapshot_dir),
        "mirror_dir": str(MIRROR_ROOT),
        "compressed": False,
        "automatic_deletion": False,
        "databases": [],
        "snapshot_directories": {},
        "secret_files": [],
        "runtime_files": [],
        "mirror_directories": {},
    }

    for source in SQLITE_SOURCES:
        if source.is_file():
            relative_name = source.relative_to(ROOT)
            destination = snapshot_dir / "databases" / relative_name
            manifest["databases"].append(backup_sqlite(source, destination))

    for source, relative_destination in SNAPSHOT_DIRECTORIES:
        manifest["snapshot_directories"][relative_destination] = copy_tree(
            source,
            snapshot_dir / relative_destination,
            incremental=False,
        )

    for source, relative_destination in SECRET_FILES:
        if source.is_file():
            destination = snapshot_dir / relative_destination
            copied_bytes = copy_file(source, destination)
            manifest["secret_files"].append({
                "source": str(source),
                "backup": str(destination),
                "size_bytes": copied_bytes,
                "sha256": sha256_file(destination),
                "plaintext_private_backup": True,
            })

    for source, relative_destination in RUNTIME_FILES:
        if source.is_file():
            destination = snapshot_dir / relative_destination
            copy_file(source, destination)
            manifest["runtime_files"].append(str(destination))

    runtime_snapshot = {
        "git_head": command_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
        "git_branch": command_output(["git", "-C", str(ROOT), "branch", "--show-current"]),
        "docker_ps": command_output(["docker", "ps", "--format", "{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}"]),
        "python_version": command_output(["python3", "--version"]),
        "services": {},
    }
    for service in [
        "storymaker-beta.service",
        "storymaker-v1-podcast-api.service",
        "storymaker-v1-supertonic3.service",
        "storymaker-beta-private-backup.timer",
    ]:
        runtime_snapshot["services"][service] = command_output(["systemctl", "is-active", service])
    (snapshot_dir / "runtime").mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "runtime/runtime_snapshot.json").write_text(
        json.dumps(runtime_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    for source, relative_destination in MIRROR_DIRECTORIES:
        manifest["mirror_directories"][relative_destination] = copy_tree(
            source,
            MIRROR_ROOT / relative_destination,
            incremental=True,
        )

    manifest_path = snapshot_dir / "backup_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (SNAPSHOT_ROOT / "LATEST_BACKUP.txt").write_text(
        str(snapshot_dir) + "\n",
        encoding="utf-8",
    )
    (BACKUP_ROOT / "LATEST_FULL_RECOVERY_BACKUP.txt").write_text(
        str(snapshot_dir) + "\n" + str(MIRROR_ROOT) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"BACKUP_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
