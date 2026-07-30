#!/bin/sh
set -eu
/usr/bin/docker exec storymaker-v1-backend python /app/scripts/v1_weather_hourly_collector.py --sync-only
exec /home/bourne/Weather/.venv/bin/python /home/bourne/StoryMaker_1/scripts/v1_weather_kma_grid_collector.py
