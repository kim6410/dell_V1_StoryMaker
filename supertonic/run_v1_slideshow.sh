#!/usr/bin/env bash
set -euo pipefail

V1_ROOT="/home/bourne/StoryMaker_1/supertonic"
MAC_USER="bourne"
MAC_HOST="192.168.0.34"
SSH_KEY="/home/bourne/.ssh/storymaker_macmini_ed25519"
REMOTE_WORKER_DIR="/Users/bourne/storymaker-worker"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <V1 render_job.json>" >&2
  exit 2
fi

JSON_PATH="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$1")"
case "$JSON_PATH" in
  "$V1_ROOT"/user_jobs/*/render_job.json) ;;
  *)
    echo "ERROR: render job must be inside V1 user_jobs: $JSON_PATH" >&2
    exit 3
    ;;
esac

[[ -f "$JSON_PATH" ]] || { echo "ERROR: missing render job: $JSON_PATH" >&2; exit 4; }
[[ -f "$SSH_KEY" ]] || { echo "ERROR: missing Mac mini SSH key" >&2; exit 5; }

readarray -t JOB_VALUES < <(python3 - "$JSON_PATH" "$V1_ROOT" <<'PY'
import json, re, sys
from pathlib import Path

job_path = Path(sys.argv[1]).resolve()
v1_root = Path(sys.argv[2]).resolve()
data = json.loads(job_path.read_text(encoding="utf-8"))

job_id = str(data.get("job_id", ""))
if not re.fullmatch(r"[A-Za-z0-9_-]+", job_id):
    raise SystemExit("ERROR: unsafe job_id")

for key in ("image_dir", "mp3_path", "output_mp4"):
    p = Path(str(data.get(key, ""))).resolve()
    if v1_root != p and v1_root not in p.parents:
        raise SystemExit(f"ERROR: {key} escapes V1 root: {p}")

srt_raw = str(data.get("srt_path", "") or "")
if srt_raw:
    srt = Path(srt_raw).resolve()
    if v1_root != srt and v1_root not in srt.parents:
        raise SystemExit(f"ERROR: srt_path escapes V1 root: {srt}")

print(job_id)
print(Path(data["image_dir"]).resolve())
print(Path(data["mp3_path"]).resolve())
print(Path(srt_raw).resolve() if srt_raw else "")
print(Path(data["output_mp4"]).resolve())
PY
)

JOB_ID="${JOB_VALUES[0]}"
IMAGE_DIR="${JOB_VALUES[1]}"
MP3_PATH="${JOB_VALUES[2]}"
SRT_PATH="${JOB_VALUES[3]}"
OUTPUT_MP4="${JOB_VALUES[4]}"

[[ -d "$IMAGE_DIR" ]] || { echo "ERROR: missing V1 image directory: $IMAGE_DIR" >&2; exit 6; }
[[ -s "$MP3_PATH" ]] || { echo "ERROR: missing V1 MP3: $MP3_PATH" >&2; exit 7; }
mkdir -p "$(dirname "$OUTPUT_MP4")"

SSH_OPTS=(-F /dev/null -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no)
REMOTE_JOB_DIR="$REMOTE_WORKER_DIR/tmp/v1_job_$JOB_ID"
REMOTE_OUTPUT_NAME="$(basename "$OUTPUT_MP4")"

cleanup_remote() {
  ssh "${SSH_OPTS[@]}" "$MAC_USER@$MAC_HOST" "rm -rf '$REMOTE_JOB_DIR'" >/dev/null 2>&1 || true
}
trap cleanup_remote EXIT

ssh "${SSH_OPTS[@]}" "$MAC_USER@$MAC_HOST" "rm -rf '$REMOTE_JOB_DIR' && mkdir -p '$REMOTE_JOB_DIR/images' '$REMOTE_JOB_DIR/output'"
scp "${SSH_OPTS[@]}" -r "$IMAGE_DIR"/. "$MAC_USER@$MAC_HOST:$REMOTE_JOB_DIR/images/"
scp "${SSH_OPTS[@]}" "$MP3_PATH" "$MAC_USER@$MAC_HOST:$REMOTE_JOB_DIR/audio.mp3"
if [[ -n "$SRT_PATH" && -f "$SRT_PATH" ]]; then
  scp "${SSH_OPTS[@]}" "$SRT_PATH" "$MAC_USER@$MAC_HOST:$REMOTE_JOB_DIR/subtitles.srt"
fi
scp "${SSH_OPTS[@]}" "$JSON_PATH" "$MAC_USER@$MAC_HOST:$REMOTE_JOB_DIR/job.json"

ssh "${SSH_OPTS[@]}" "$MAC_USER@$MAC_HOST" "python3 '$REMOTE_WORKER_DIR/scripts/slideshow_worker.py' --job-dir '$REMOTE_JOB_DIR'"
scp "${SSH_OPTS[@]}" "$MAC_USER@$MAC_HOST:$REMOTE_JOB_DIR/output/$REMOTE_OUTPUT_NAME" "$OUTPUT_MP4"

[[ -s "$OUTPUT_MP4" ]] || { echo "ERROR: Mac mini result missing: $OUTPUT_MP4" >&2; exit 8; }
echo "SUCCESS: V1 Mac mini fallback result: $OUTPUT_MP4"
