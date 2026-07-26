#!/usr/bin/env python3
"""23:59 스케줄 등록용 진입점. 현재 cron/systemd에는 등록하지 않았다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.cleanup import purge_daily_content


if __name__ == "__main__":
    print(purge_daily_content())
