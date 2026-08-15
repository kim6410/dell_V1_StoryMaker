#!/usr/bin/env bash
set -Eeuo pipefail

# StoryMaker V1 + operating V2 critical source/database snapshot
# Windows: \\192.168.0.32\DellMusic\V2_SnapShot
# Linux:   /mnt/lms_ssd/V2_SnapShot

PARENT="/home/bourne"
V1_ROOT="/home/bourne/StoryMaker_1"
OPS_ROOT="/home/bourne/StoryMaker"
V2_SOURCE="/home/bourne/storymaker-v2-app"
DEST="/mnt/lms_ssd/V2_SnapShot"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
NAME="StoryMaker_V1_OPERATING_source_db_snapshot_${STAMP}"
ARCHIVE="${DEST}/${NAME}.tar.gz"
SHA_FILE="${ARCHIVE}.sha256"
MANIFEST="${DEST}/${NAME}.manifest.txt"
EXCLUDE_FILE="$(mktemp /tmp/storymaker_combined_snapshot_excludes.XXXXXX)"
DB_STAGE="$(mktemp -d /tmp/storymaker_db_snapshot.XXXXXX)"
RUNTIME_STAGE="$(mktemp -d /tmp/storymaker_runtime_snapshot.XXXXXX)"
MAX_FILE_MB=300

cleanup() {
  rm -f "$EXCLUDE_FILE"
  rm -rf "$DB_STAGE"
  rm -rf "$RUNTIME_STAGE"
}
trap cleanup EXIT

for required in "$V1_ROOT" "$OPS_ROOT" "$V2_SOURCE" "/mnt/lms_ssd"; do
  [[ -e "$required" ]] || { echo "ERROR: required path not found: $required" >&2; exit 1; }
done
mkdir -p \
  "$DEST" \
  "$DB_STAGE/StoryMaker/database_snapshot" \
  "$DB_STAGE/StoryMaker_1/database_snapshot" \
  "$RUNTIME_STAGE/StoryMaker/runtime_snapshot/current_projects" \
  "$RUNTIME_STAGE/StoryMaker/runtime_snapshot/test_result_packages"

# Consistent SQLite backups for both the live operational DB and V1 DB.
python3 - <<PY
import sqlite3
from pathlib import Path

pairs = [
    (
        Path('/home/bourne/StoryMaker/database/storymaker.db'),
        Path('$DB_STAGE/StoryMaker/database_snapshot/storymaker.db'),
        'operational DB',
    ),
    (
        Path('/home/bourne/StoryMaker_1/database/storymaker.db'),
        Path('$DB_STAGE/StoryMaker_1/database_snapshot/storymaker.db'),
        'V1 DB',
    ),
]

for src, dst, label in pairs:
    if not src.is_file():
        raise SystemExit(f'{label} not found: {src}')
    dst.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(src) as source, sqlite3.connect(dst) as target:
        source.backup(target)
    print(dst)
PY

# Preserve the current end-to-end production artifacts needed to roll back
# the unified V2 archive linkage without copying the entire output_results tree.
for project_name in \
  'kim_2026-07-21_팟캐스트' \
  'mob-20260721133220-5f6c24c5'; do
  project_src="$OPS_ROOT/output_results/users/default_user/projects/$project_name"
  if [[ -d "$project_src" ]]; then
    cp -a "$project_src" "$RUNTIME_STAGE/StoryMaker/runtime_snapshot/current_projects/"
  fi
done

# Keep today's result-package metadata and generated thumbnail packages.
# These packages are small compared with the full output tree and are required
# to reproduce current content/audio/thumbnail/archive relationships.
if [[ -d "$OPS_ROOT/output_results/test_result_packages" ]]; then
  while IFS= read -r -d '' package_dir; do
    cp -a "$package_dir" "$RUNTIME_STAGE/StoryMaker/runtime_snapshot/test_result_packages/"
  done < <(find "$OPS_ROOT/output_results/test_result_packages" \
    -mindepth 1 -maxdepth 1 -type d -newermt '2026-07-21 00:00:00' -print0)

  find "$OPS_ROOT/output_results/test_result_packages" \
    -maxdepth 1 -type f -newermt '2026-07-21 00:00:00' \
    \( -name '*.json' -o -name '*.txt' -o -name '*.md' -o -name '*.srt' \) \
    -exec cp -a {} "$RUNTIME_STAGE/StoryMaker/runtime_snapshot/test_result_packages/" \;
fi

cat > "$RUNTIME_STAGE/StoryMaker/runtime_snapshot/README.txt" <<EOF_RUNTIME
Runtime snapshot created: $(date --iso-8601=seconds)
Purpose: preserve the current V2 one-shot, podcast, thumbnail and slideshow linkage state before archive unification.
Included current projects when present:
- kim_2026-07-21_팟캐스트
- mob-20260721133220-5f6c24c5
- test_result_packages created or modified on 2026-07-21
The full output_results tree remains intentionally excluded.
EOF_RUNTIME

# Exclude individually oversized files from all included source roots.
{
  find "$V1_ROOT" -xdev -type f -size +"${MAX_FILE_MB}"M -printf 'StoryMaker_1/%P\n'
  find "$OPS_ROOT/storymaker-web/backend" -xdev -type f -size +"${MAX_FILE_MB}"M -printf 'StoryMaker/storymaker-web/backend/%P\n'
  find "$OPS_ROOT/database" -xdev -type f -size +"${MAX_FILE_MB}"M -printf 'StoryMaker/database/%P\n'
  find "$V2_SOURCE" -xdev -type f -size +"${MAX_FILE_MB}"M -printf 'storymaker-v2-app/%P\n'
} | sort -u > "$EXCLUDE_FILE"

cat > "$MANIFEST" <<EOF_MANIFEST
StoryMaker combined V1 + operating source/database snapshot
Created: $(date --iso-8601=seconds)
Archive: $ARCHIVE
Filename date format: YYYY-MM-DD_HHMMSS
Maximum included individual file size: ${MAX_FILE_MB} MB

Included:
- /home/bourne/StoryMaker_1 source, deployed V1 frontend, V1 DB/config/scripts/WORK_LOGS
- consistent SQLite backup at StoryMaker_1/database_snapshot/storymaker.db
- V1 membership/auth/admin/mypage files under StoryMaker_1/storymaker-web/backend/app
- /home/bourne/StoryMaker/storymaker-web/backend complete backend source
- operating membership/auth/admin/mypage files under StoryMaker/storymaker-web/backend/app
- operating MP4 quota source backend/app/api/mobile_one_shot.py
- current V2 React membership UI sources under /home/bourne/storymaker-v2-app/src
- deletion candidate backend/app/api/slideshow - 복사본.py, preserved in this snapshot before removal
- active deployed V2 files under backend/app/static/v2
- podcast.py, slideshow.py, common_archive_service.py, content_asset_service.py
- content_asset_repository.py, mobile_one_shot_repository.py and related backend DB code
- /home/bourne/StoryMaker/database current DB files and migration/inspection scripts
- consistent SQLite backup at StoryMaker/database_snapshot/storymaker.db
- /home/bourne/StoryMaker/personas
- /home/bourne/StoryMaker root-level compose/config/maintenance files
- /home/bourne/storymaker-v2-app source excluding dependencies/build output
- targeted runtime snapshot for the current one-shot/podcast/thumbnail/slideshow linkage test
- current projects: kim_2026-07-21_팟캐스트 and mob-20260721133220-5f6c24c5 when present
- test_result_packages created or modified on 2026-07-21

Excluded:
- generated media, uploads, exports, output_results, renders and caches
- node_modules, virtual environments, model payloads and Git internals
- old backup directories and archive packages
- logs, temporary files and individual files larger than ${MAX_FILE_MB} MB

Dynamically excluded oversized files:
EOF_MANIFEST
if [[ -s "$EXCLUDE_FILE" ]]; then sed 's/^/- /' "$EXCLUDE_FILE" >> "$MANIFEST"; else echo '- none' >> "$MANIFEST"; fi

COMMON_EXCLUDES=(
  --exclude-from="$EXCLUDE_FILE"
  --exclude='**/.git' --exclude='**/node_modules' --exclude='**/.venv' --exclude='**/venv'
  --exclude='**/__pycache__' --exclude='**/.pytest_cache' --exclude='**/.mypy_cache'
  --exclude='**/.ruff_cache' --exclude='**/.vite' --exclude='**/.cache'
  --exclude='**/dist' --exclude='**/build'
  --exclude='**/Backup' --exclude='**/backups' --exclude='**/backup' --exclude='**/SNAPSHOTS'
  --exclude='**/output_results' --exclude='**/outputs' --exclude='**/generated'
  --exclude='**/renders' --exclude='**/rendered' --exclude='**/media_cache'
  --exclude='**/tts_cache' --exclude='**/uploads' --exclude='**/exports' --exclude='**/logs'
  --exclude='**/*.pyc' --exclude='**/*.pyo' --exclude='**/*.log' --exclude='**/*.tmp'
  --exclude='**/*.part' --exclude='**/*.swp' --exclude='**/*.bak' --exclude='**/*.old' --exclude='**/*.orig'
  --exclude='**/*.zip' --exclude='**/*.7z' --exclude='**/*.rar' --exclude='**/*.tgz'
  --exclude='**/*.tar' --exclude='**/*.tar.gz' --exclude='**/*.tar.xz'
  --exclude='**/*.mp3' --exclude='**/*.wav' --exclude='**/*.m4a' --exclude='**/*.aac'
  --exclude='**/*.flac' --exclude='**/*.mp4' --exclude='**/*.mov' --exclude='**/*.mkv' --exclude='**/*.webm'
  --exclude='StoryMaker/Supertonic3' --exclude='StoryMaker/supertonic/user_jobs'
  --exclude='StoryMaker/supertonic/SlidShow' --exclude='StoryMaker/supertonic/music'
  --exclude='StoryMaker/database/backups_mcp' --exclude='StoryMaker/database/exports_mcp'
)

# Include V1, operational backend/DB/personas, and V2 React source.
tar --create --gzip --file "$ARCHIVE" --directory "$PARENT" \
  "${COMMON_EXCLUDES[@]}" \
  'StoryMaker_1' \
  'StoryMaker/storymaker-web/backend' \
  'StoryMaker/database' \
  'StoryMaker/personas' \
  'storymaker-v2-app' \
  --directory "$DB_STAGE" \
  'StoryMaker/database_snapshot' \
  'StoryMaker_1/database_snapshot' \
  --directory "$RUNTIME_STAGE" \
  'StoryMaker/runtime_snapshot'

sha256sum "$ARCHIVE" > "$SHA_FILE"
{
  echo
  echo "Result"
  echo "Archive size: $(du -h "$ARCHIVE" | awk '{print $1}')"
  echo "SHA-256: $(awk '{print $1}' "$SHA_FILE")"
  echo "Archive file count: $(tar -tzf "$ARCHIVE" | wc -l)"
  echo
  echo "Critical file verification:"
  for item in \
    'StoryMaker_1/storymaker-web/backend/app/db/models.py' \
    'StoryMaker_1/storymaker-web/backend/app/db/database.py' \
    'StoryMaker_1/storymaker-web/backend/app/db/repositories.py' \
    'StoryMaker_1/storymaker-web/backend/app/api/auth.py' \
    'StoryMaker_1/storymaker-web/backend/app/api/admin.py' \
    'StoryMaker_1/storymaker-web/backend/app/api/admin_members.py' \
    'StoryMaker_1/storymaker-web/backend/app/api/wordpress.py' \
    'StoryMaker_1/storymaker-web/backend/app/schemas/user.py' \
    'StoryMaker_1/storymaker-web/backend/app/schemas/__init__.py' \
    'StoryMaker_1/storymaker-web/backend/app/static/app_auth.js' \
    'StoryMaker_1/storymaker-web/backend/app/static/app_admin.js' \
    'StoryMaker_1/storymaker-web/backend/app/static/app_generator_wordpress.js' \
    'StoryMaker_1/database/storymaker.db' \
    'StoryMaker_1/database_snapshot/storymaker.db' \
    'StoryMaker/storymaker-web/backend/app/db/models.py' \
    'StoryMaker/storymaker-web/backend/app/db/database.py' \
    'StoryMaker/storymaker-web/backend/app/db/repositories.py' \
    'StoryMaker/storymaker-web/backend/app/api/auth.py' \
    'StoryMaker/storymaker-web/backend/app/api/admin.py' \
    'StoryMaker/storymaker-web/backend/app/api/admin_members.py' \
    'StoryMaker/storymaker-web/backend/app/api/wordpress.py' \
    'StoryMaker/storymaker-web/backend/app/api/mobile_one_shot.py' \
    'StoryMaker/storymaker-web/backend/app/api/slideshow - 복사본.py' \
    'StoryMaker/storymaker-web/backend/app/schemas/user.py' \
    'StoryMaker/storymaker-web/backend/app/static/app_auth.js' \
    'StoryMaker/storymaker-web/backend/app/static/app_admin.js' \
    'StoryMaker/storymaker-web/backend/app/static/app_generator_wordpress.js' \
    'StoryMaker/storymaker-web/backend/app/api/podcast.py' \
    'StoryMaker/storymaker-web/backend/app/api/slideshow.py' \
    'StoryMaker/storymaker-web/backend/app/services/common_archive_service.py' \
    'StoryMaker/storymaker-web/backend/app/services/content_asset_service.py' \
    'StoryMaker/storymaker-web/backend/app/db/content_asset_repository.py' \
    'StoryMaker/storymaker-web/backend/app/db/mobile_one_shot_repository.py' \
    'StoryMaker/storymaker-web/backend/app/static/v2/' \
    'StoryMaker/database/storymaker.db' \
    'StoryMaker/database_snapshot/storymaker.db' \
    'StoryMaker/runtime_snapshot/README.txt' \
    'StoryMaker/runtime_snapshot/current_projects/kim_2026-07-21_팟캐스트/' \
    'storymaker-v2-app/src/services/authApi.ts' \
    'storymaker-v2-app/src/components/RequireAuth.tsx' \
    'storymaker-v2-app/src/components/MyPagePanel.tsx' \
    'storymaker-v2-app/src/mobile/components/MyPageSheet.tsx' \
    'storymaker-v2-app/src/pages/AdminMemberPage.tsx' \
    'storymaker-v2-app/package.json'; do
      if tar -tzf "$ARCHIVE" | grep -Fq "$item"; then echo "- INCLUDED: $item"; else echo "- MISSING: $item"; fi
  done
} >> "$MANIFEST"

tar -tzf "$ARCHIVE" >/dev/null
sha256sum -c "$SHA_FILE"

printf '\nSnapshot created successfully.\n%s\n%s\n%s\n' "$ARCHIVE" "$SHA_FILE" "$MANIFEST"
