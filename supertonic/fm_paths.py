# -*- coding: utf-8 -*-
"""Runtime path helpers for SLID_Maker on the StoryMaker server."""

import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SLID_RUNTIME_DIR = BASE_DIR / "slid_runtime"


def ensure_dirs(*paths):
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


def find_vlc_executable():
    candidates = [
        shutil.which("vlc"),
        "/usr/bin/vlc",
        "/usr/local/bin/vlc",
    ]
    for item in candidates:
        if item and Path(item).exists():
            return str(item)
    return ""


def hide_console():
    # Windows GUI helper compatibility. No action is needed on the Linux server.
    return None


ensure_dirs(SLID_RUNTIME_DIR)
