from __future__ import annotations

import os
import runpy
from pathlib import Path

ENV_PATH = Path('/home/bourne/StoryMaker_1/storymaker-web/.env')
APP_PATH = Path('/home/bourne/StoryMaker_1/supertonic/app.py')

for raw_line in ENV_PATH.read_text(encoding='utf-8').splitlines():
    line = raw_line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if key:
        os.environ.setdefault(key, value)

os.chdir(APP_PATH.parent)
runpy.run_path(str(APP_PATH), run_name='__main__')
