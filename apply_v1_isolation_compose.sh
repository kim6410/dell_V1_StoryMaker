#!/usr/bin/env bash
set -euo pipefail
cd /home/bourne/StoryMaker_1/storymaker-web
docker compose up -d --force-recreate storymaker-backend
