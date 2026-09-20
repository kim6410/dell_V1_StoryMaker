#!/bin/sh
set -eu
if /usr/bin/docker exec storymaker-v1-backend test -f /app/scripts/v1_weather_hourly_collector.py; then
  /usr/bin/docker exec storymaker-v1-backend python /app/scripts/v1_weather_hourly_collector.py --sync-only
else
  echo "warning: /app/scripts/v1_weather_hourly_collector.py missing; continuing with KMA grid collector"
fi
exec /home/bourne/Weather/.venv/bin/python /home/bourne/StoryMaker_1/scripts/v1_weather_kma_grid_collector.py
