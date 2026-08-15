#!/usr/bin/env bash
set -Eeuo pipefail

# StoryMaker V1 전용 3시간 전 롤백 스크립트
# 기본값은 점검만 수행합니다.
# 실제 복원: sudo APPLY=YES bash rollback_storymaker_v1_3h.sh
#
# 절대 수정 금지:
#   /home/bourne/StoryMaker/storymaker-web
#   /home/bourne/storymaker-v2-app

V1_ROOT="/home/bourne/StoryMaker_1/storymaker-web"
HOURS_AGO="${HOURS_AGO:-3}"
APPLY="${APPLY:-NO}"
STAMP="$(date +%Y%m%d_%H%M%S)"
SAFE_BACKUP_ROOT="/home/bourne/StoryMaker_1/ROLLBACK_BACKUPS"
CURRENT_BACKUP="${SAFE_BACKUP_ROOT}/before_rollback_${STAMP}"
TARGET_EPOCH="$(date -d "${HOURS_AGO} hours ago" +%s)"
TARGET_TEXT="$(date -d "@${TARGET_EPOCH}" '+%Y-%m-%d %H:%M:%S %Z')"

die() {
  echo "[ERROR] $*" >&2
  exit 1
}

log() {
  echo "[$(date '+%H:%M:%S')] $*"
}

[[ -d "$V1_ROOT" ]] || die "V1 경로가 없습니다: $V1_ROOT"

REAL_V1="$(realpath "$V1_ROOT")"
[[ "$REAL_V1" == "/home/bourne/StoryMaker_1/storymaker-web" ]] \
  || die "안전장치 실패: 예상하지 못한 V1 경로입니다: $REAL_V1"

cd "$V1_ROOT"

log "대상: $V1_ROOT"
log "목표 시각: $TARGET_TEXT"
log "모드: $([[ "$APPLY" == "YES" ]] && echo '실제 복원' || echo '점검 전용')"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
  [[ "$(realpath "$REPO_ROOT")" == "$REAL_V1" ]] \
    || die "Git 루트가 V1 루트와 다릅니다: $REPO_ROOT"

  TARGET_COMMIT="$(git rev-list -1 --before="$TARGET_TEXT" HEAD || true)"
  [[ -n "$TARGET_COMMIT" ]] || die "목표 시각 이전 Git 커밋을 찾지 못했습니다."

  log "현재 커밋: $(git rev-parse --short HEAD)"
  log "복원 커밋: $(git rev-parse --short "$TARGET_COMMIT")"
  git show -s --format='[TARGET] %h %ci %s' "$TARGET_COMMIT"

  log "현재 작업 트리 상태:"
  git status --short || true

  log "복원 시 변경될 파일:"
  git diff --name-status "$TARGET_COMMIT"..HEAD || true
  git diff --name-status "$TARGET_COMMIT" || true

  if [[ "$APPLY" != "YES" ]]; then
    echo
    log "점검만 완료했습니다."
    log "실제 복원 명령:"
    echo "sudo APPLY=YES HOURS_AGO=${HOURS_AGO} bash $0"
    exit 0
  fi

  mkdir -p "$CURRENT_BACKUP"
  log "현재 V1 전체 안전 백업 생성: $CURRENT_BACKUP/v1_before_rollback.tar.gz"
  tar \
    --exclude='./node_modules' \
    --exclude='./.git' \
    -czf "$CURRENT_BACKUP/v1_before_rollback.tar.gz" \
    -C "$V1_ROOT" .

  git status --porcelain=v1 > "$CURRENT_BACKUP/git_status_before.txt"
  git rev-parse HEAD > "$CURRENT_BACKUP/git_head_before.txt"
  git diff > "$CURRENT_BACKUP/uncommitted_changes_before.patch" || true
  git diff --cached > "$CURRENT_BACKUP/staged_changes_before.patch" || true

  log "Git 기준 복원 시작"
  git reset --hard "$TARGET_COMMIT"
  git clean -fd

  log "복원 완료"
  git show -s --format='[NOW] %h %ci %s' HEAD

  if [[ -f package.json ]] && command -v npm >/dev/null 2>&1; then
    log "package.json 확인됨. 자동 build/deploy는 실행하지 않습니다."
  fi

  log "V2와 기존 StoryMaker 경로는 수정하지 않았습니다."
  log "다음 단계: V1 서비스/컨테이너 재시작 후 브라우저 강력 새로고침 및 MP3·MP4 실제 검증"
  exit 0
fi

echo
log "이 V1 경로는 Git 저장소가 아닙니다."
log "파일 백업이나 스냅샷의 정확한 구조를 모르는 상태에서 자동 덮어쓰기는 위험하므로 중단합니다."
log "현재 시각 기준 최근 변경 파일 목록:"
find "$V1_ROOT" -type f -newermt "${HOURS_AGO} hours ago" \
  -not -path '*/node_modules/*' \
  -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' 2>/dev/null \
  | sort || true

echo
die "Git이 없어 안전한 자동 롤백을 수행하지 않았습니다. 백업 경로를 지정한 복원 스크립트가 별도로 필요합니다."
