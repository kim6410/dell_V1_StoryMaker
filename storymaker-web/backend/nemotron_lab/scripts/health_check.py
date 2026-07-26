#!/usr/bin/env python3
"""Nemotron Lab 독립성 및 현재 Shell 상태 확인."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.service import NemotronLabService
from backend.usage_store import storage_status


if __name__ == "__main__":
    print({"service": NemotronLabService().status(), "storage": storage_status()})
