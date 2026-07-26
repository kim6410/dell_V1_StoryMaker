# -*- coding: utf-8 -*-
"""
staged 경계 및 데이터 검증 모듈
"""
import re
from pathlib import Path

JOB_ID_REGEX = re.compile(r"^stage-\d{14}-[a-f0-9]{8}$")

FORBIDDEN_MOBILE_ROOTS = [
    Path("/home/bourne/StoryMaker_1/output_results/test_triggers"),
    Path("/home/bourne/StoryMaker_1/output_results/test_result_packages"),
    Path("/home/bourne/StoryMaker_1/output_results/test_thumbnail_jobs"),
    Path("/home/bourne/StoryMaker_1/output_results/mobile_one_shot"),
    Path("/home/bourne/StoryMaker_1/output_results/mobile_one_shot_jobs"),
    Path("/home/bourne/StoryMaker_1/output_results/podcast"),
    Path("/home/bourne/StoryMaker_1/output_results/slideshow"),
]

def assert_staged_work_path(path: Path, root: Path) -> Path:
    """
    지정된 path가 root 하위에 속해 있으며, 금지된 딸깍 경로를 참조하지 않는지 검증합니다.
    """
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
    except Exception as e:
        raise RuntimeError(f"PATH_RESOLVE_FAILURE: {e}")

    # 1. 금지된 모바일 딸깍 경로 접촉 검사
    for forbidden in FORBIDDEN_MOBILE_ROOTS:
        try:
            res_forbidden = forbidden.resolve()
            if resolved_path == res_forbidden or resolved_path.is_relative_to(res_forbidden):
                raise RuntimeError("MOBILE_PATH_ACCESS_BLOCKED")
        except FileNotFoundError:
            # 테스트 환경 등에서 디렉토리가 없을 시 패스
            continue

    # 2. .. 문자가 경로 부품에 남아있는지 검증
    if ".." in path.parts or ".." in resolved_path.parts:
        raise RuntimeError("PATH_TRAVERSAL_ATTEMPT_DETECTED")

    # 3. 상위 탈출 검증 (is_relative_to 사용)
    if not resolved_path.is_relative_to(resolved_root):
        raise RuntimeError("STAGED_PATH_BOUNDARY_VIOLATION")

    return resolved_path

def validate_job_id(job_id: str) -> bool:
    """
    staged 규격에 부합하는 Job ID인지 검증합니다.
    """
    if not job_id:
        return False
    # 정규식 패턴 및 모바일 접두사 금지 검증
    if not JOB_ID_REGEX.match(job_id):
        return False
    if job_id.startswith("mob-") or "storymaker_main" in job_id:
        return False
    return True
