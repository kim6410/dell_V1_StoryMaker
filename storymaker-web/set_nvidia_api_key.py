#!/usr/bin/env python3

from __future__ import annotations

import getpass
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


ENV_PATH = Path("/home/bourne/StoryMaker_1/storymaker-web/.env")
KEY_NAME = "NVIDIA_API_KEY"


def main() -> None:
    print(f"저장 대상: {ENV_PATH}")
    print("입력한 API 키는 화면에 표시되지 않습니다.")

    api_key = getpass.getpass("NVIDIA API KEY 입력: ").strip()

    if not api_key:
        raise SystemExit("빈 값은 저장하지 않습니다.")

    if "\n" in api_key or "\r" in api_key:
        raise SystemExit("API 키에 줄바꿈이 포함되어 있어 저장하지 않습니다.")

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing_text = ""

    if ENV_PATH.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = ENV_PATH.with_name(f".env.backup_{timestamp}")

        shutil.copy2(ENV_PATH, backup_path)
        os.chmod(backup_path, 0o600)

        existing_text = ENV_PATH.read_text(
            encoding="utf-8",
            errors="surrogateescape",
        )

        print(f"기존 설정 백업 완료: {backup_path}")

    original_lines = existing_text.splitlines()
    updated_lines: list[str] = []
    key_replaced = False

    for line in original_lines:
        stripped = line.lstrip()

        if stripped.startswith(f"{KEY_NAME}="):
            if not key_replaced:
                updated_lines.append(f"{KEY_NAME}={api_key}")
                key_replaced = True

            # 중복된 NVIDIA_API_KEY 항목은 저장하지 않습니다.
            continue

        updated_lines.append(line)

    if not key_replaced:
        if updated_lines and updated_lines[-1] != "":
            updated_lines.append("")

        updated_lines.append(f"{KEY_NAME}={api_key}")

    new_text = "\n".join(updated_lines) + "\n"

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=ENV_PATH.parent,
            prefix=".env.nvidia.",
            delete=False,
        ) as temp_file:
            temp_file.write(new_text)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)

        os.chmod(temp_path, 0o600)
        os.replace(temp_path, ENV_PATH)
        os.chmod(ENV_PATH, 0o600)

    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    print("NVIDIA_API_KEY 저장 완료")
    print("API 키 값은 출력하지 않았습니다.")
    print(f"파일 권한: {oct(ENV_PATH.stat().st_mode & 0o777)}")


if __name__ == "__main__":
    main()
