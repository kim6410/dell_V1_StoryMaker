#!/usr/bin/env bash
set -euo pipefail
python3 -m py_compile \
  /home/bourne/StoryMaker/nemotron-lab/backend/schemas.py \
  /home/bourne/StoryMaker/nemotron-lab/backend/usage_store.py \
  /home/bourne/StoryMaker/nemotron-lab/backend/service.py \
  /home/bourne/StoryMaker/nemotron-lab/backend/cleanup.py \
  /home/bourne/StoryMaker/nemotron-lab/backend/router.py
docker compose -f /home/bourne/StoryMaker/storymaker-web/docker-compose.yml config --quiet
echo NEMOTRON_PREFLIGHT_OK
