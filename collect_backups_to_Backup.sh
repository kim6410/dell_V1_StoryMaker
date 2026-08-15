#!/usr/bin/env bash
set -Eeuo pipefail

# StoryMaker_1 백업/잔존 파일 일괄 수집기
# 기본 동작은 미리보기(dry-run)이며, 실제 이동은 --apply 옵션이 필요합니다.
# 대상 위치: /home/bourne/StoryMaker_1/Backup/collected_YYYYMMDD_HHMMSS

ROOT="/home/bourne/StoryMaker_1"
BACKUP_ROOT="$ROOT/Backup"
MODE="dry-run"

usage() {
  cat <<'EOF'
사용법:
  ./collect_backups_to_Backup.sh           # 이동 대상 미리보기
  ./collect_backups_to_Backup.sh --apply   # 실제 이동

수집 대상:
  - ROOT 바로 아래 backups, quarantine_unused_*, codex_stage_* 폴더
  - 프로젝트 내부의 이름이 backup/backups인 폴더
  - *.bak, *.bak.*, *.backup, *.backup.*, *.orig, *.old, *.save, *~
  - 이름에 _before_, _backup_, .bak_가 포함된 파일

절대 제외:
  Backup, database, output_results, uploads, tts_cache, logs, exports,
  personas, supertonic, storymaker-web의 실행 원본, .git, node_modules,
  venv/.venv, __pycache__, 현재 실행 스크립트
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
elif [[ "${1:-}" == "--apply" ]]; then
  MODE="apply"
elif [[ $# -gt 0 ]]; then
  echo "알 수 없는 옵션: $1" >&2
  usage >&2
  exit 2
fi

if [[ ! -d "$ROOT" ]]; then
  echo "오류: ROOT가 없습니다: $ROOT" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="$BACKUP_ROOT/collected_$STAMP"
MANIFEST="$DEST/manifest.tsv"

# 이동 금지 경로. 이 하위는 검색 자체를 하지 않습니다.
PRUNE=(
  "$BACKUP_ROOT"
  "$ROOT/database"
  "$ROOT/output_results"
  "$ROOT/uploads"
  "$ROOT/tts_cache"
  "$ROOT/logs"
  "$ROOT/exports"
  "$ROOT/personas"
  "$ROOT/supertonic"
  "$ROOT/.git"
)

is_protected() {
  local path="$1"
  local protected
  for protected in "${PRUNE[@]}"; do
    [[ "$path" == "$protected" || "$path" == "$protected"/* ]] && return 0
  done
  case "$path" in
    */node_modules|*/node_modules/*|*/.venv|*/.venv/*|*/venv|*/venv/*|*/__pycache__|*/__pycache__/*|*/.pytest_cache|*/.pytest_cache/*)
      return 0
      ;;
  esac
  return 1
}

add_candidate() {
  local path="$1"
  [[ -e "$path" ]] || return 0
  [[ "$path" == "$0" ]] && return 0
  is_protected "$path" && return 0
  printf '%s\0' "$path"
}

collect_candidates() {
  # 루트에서 확실히 불필요한 격리/작업 폴더
  local p
  for p in \
    "$ROOT/backups" \
    "$ROOT"/quarantine_unused_* \
    "$ROOT"/codex_stage_*; do
    [[ -e "$p" ]] && add_candidate "$p"
  done

  # 프로젝트 내부 백업 파일과 백업 폴더
  while IFS= read -r -d '' p; do
    add_candidate "$p"
  done < <(
    find "$ROOT" -mindepth 2 \
      \( -path "$BACKUP_ROOT" -o -path "$BACKUP_ROOT/*" \
         -o -path '*/node_modules' -o -path '*/node_modules/*' \
         -o -path '*/.git' -o -path '*/.git/*' \
         -o -path '*/.venv' -o -path '*/.venv/*' \
         -o -path '*/venv' -o -path '*/venv/*' \
         -o -path '*/__pycache__' -o -path '*/__pycache__/*' \
         -o -path '*/.pytest_cache' -o -path '*/.pytest_cache/*' \
         -o -path "$ROOT/database" -o -path "$ROOT/database/*" \
         -o -path "$ROOT/output_results" -o -path "$ROOT/output_results/*" \
         -o -path "$ROOT/uploads" -o -path "$ROOT/uploads/*" \
         -o -path "$ROOT/tts_cache" -o -path "$ROOT/tts_cache/*" \
         -o -path "$ROOT/logs" -o -path "$ROOT/logs/*" \
         -o -path "$ROOT/exports" -o -path "$ROOT/exports/*" \
         -o -path "$ROOT/personas" -o -path "$ROOT/personas/*" \
         -o -path "$ROOT/supertonic" -o -path "$ROOT/supertonic/*" \) -prune \
      -o \( \
        -type d \( -iname backup -o -iname backups \) \
        -o -type f \( \
          -iname '*.bak' -o -iname '*.bak.*' \
          -o -iname '*.backup' -o -iname '*.backup.*' \
          -o -iname '*.orig' -o -iname '*.old' -o -iname '*.save' \
          -o -name '*~' \
          -o -iname '*_before_*' -o -iname '*_backup_*' -o -iname '*.bak_*' \
        \) \
      \) -print0
  )
}

mapfile -d '' CANDIDATES < <(collect_candidates | sort -z -u)

if [[ ${#CANDIDATES[@]} -eq 0 ]]; then
  echo "수집 대상이 없습니다."
  exit 0
fi

echo "모드: $MODE"
echo "대상 루트: $ROOT"
echo "수집 위치: $DEST"
echo "발견 개수: ${#CANDIDATES[@]}"
echo

for src in "${CANDIDATES[@]}"; do
  rel="${src#$ROOT/}"
  printf '[대상] %s\n' "$rel"
done

if [[ "$MODE" == "dry-run" ]]; then
  echo
  echo "미리보기만 완료했습니다. 실제 이동 명령:"
  echo "  $0 --apply"
  exit 0
fi

mkdir -p "$DEST"
printf 'moved_at\ttype\tsource\tdestination\n' > "$MANIFEST"

moved=0
failed=0
for src in "${CANDIDATES[@]}"; do
  [[ -e "$src" ]] || continue
  rel="${src#$ROOT/}"
  dst="$DEST/$rel"
  mkdir -p "$(dirname "$dst")"

  # 동일 이름 충돌 방지
  if [[ -e "$dst" ]]; then
    dst="${dst}.moved_$STAMP"
  fi

  if mv -- "$src" "$dst"; then
    type="file"
    [[ -d "$dst" ]] && type="dir"
    printf '%s\t%s\t%s\t%s\n' "$(date -Iseconds)" "$type" "$src" "$dst" >> "$MANIFEST"
    printf '[이동 완료] %s\n' "$rel"
    moved=$((moved + 1))
  else
    printf '[이동 실패] %s\n' "$rel" >&2
    failed=$((failed + 1))
  fi
done

cat > "$DEST/RESTORE_GUIDE.txt" <<EOF
StoryMaker_1 백업 수집 결과
생성 시각: $(date -Iseconds)
원본 루트: $ROOT
수집 폴더: $DEST

복원 방법:
manifest.tsv에서 source와 destination을 확인한 뒤,
복원할 항목만 destination에서 source 위치로 되돌리십시오.
실행 중인 서비스 파일은 반드시 중지/백업 후 복원하십시오.
EOF

echo
echo "완료: 이동 $moved개 / 실패 $failed개"
echo "목록: $MANIFEST"
echo "윈도우 경로: \\\\192.168.0.32\\StoryMaker_1\\Backup\\collected_$STAMP"

[[ $failed -eq 0 ]]
