from __future__ import annotations

import os
import sys

import httpx

BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
API_KEY = os.getenv("NVIDIA_API_KEY", "").strip()

CANDIDATE_MARKERS = (
    "nemotron",
    "glm",
    "deepseek",
    "riva-translate",
    "magpie",
    "retriever",
    "content-safety",
    "ocr",
)


def main() -> int:
    if not API_KEY:
        print("CATALOG_ERROR=NO_API_KEY")
        return 2

    try:
        response = httpx.get(
            f"{BASE_URL}/models",
            headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"},
            timeout=25.0,
        )
        print(f"HTTP_STATUS={response.status_code}")
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"CATALOG_ERROR={type(exc).__name__}:{str(exc)[:240]}")
        return 1

    items = payload.get("data", []) if isinstance(payload, dict) else []
    ids = sorted({str(item.get("id", "")).strip() for item in items if isinstance(item, dict) and item.get("id")})
    matches = [model_id for model_id in ids if any(marker in model_id.lower() for marker in CANDIDATE_MARKERS)]

    print(f"MODEL_COUNT={len(ids)}")
    print(f"MATCH_COUNT={len(matches)}")
    for model_id in matches:
        print(f"MODEL={model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
