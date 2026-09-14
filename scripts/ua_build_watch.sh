#!/usr/bin/env bash
# Watcher: cho may ranh (khong con tien trinh agy nao) roi build lai graph UA
# cho vietbank-sme, sau do tra 3 repo con ve nhanh cu va ghi status.
#
#   ua_build_watch.sh            chay that
#   ua_build_watch.sh --dry-run  chi in ra cac buoc, khong doi nhanh, khong chay agy
#
# Khong dung toi job agy khac (khong pkill), khong sua config.yaml, khong restart service.

set -uo pipefail

readonly ROOT="/home/zane/Desktop/work/vietbank/vietbank-sme"
readonly OMNI="$ROOT/vietbank-sme-omni"
readonly EKYC="$ROOT/viet-bank-ekyc-sme"
readonly COMMON="$ROOT/dvnh-common"

readonly STATE_DIR="/home/zane/.hermes/state"
readonly LOCK_FILE="$STATE_DIR/ua_build.lock"
readonly PROMPT_FILE="$STATE_DIR/ua_build_prompt.txt"
readonly RESTORE_SH="$STATE_DIR/ua_build_restore.sh"
readonly STATUS_FILE="$STATE_DIR/ua_build_status.txt"

readonly LOG_FILE="/home/zane/.hermes/logs/ua_build_watch.log"
readonly BUILD_LOG="/tmp/ua_vbsme_build.log"

readonly GRAPH_JSON="$ROOT/.ua/knowledge-graph.json"
readonly META_JSON="$ROOT/.ua/meta.json"

readonly WAIT_MAX_SECONDS=43200   # 12 gio
readonly POLL_SECONDS=60          # moi 60s kiem tra mot lan
readonly IDLE_STREAK_NEEDED=5     # sach lien tuc 5 lan = 5 phut
readonly BUILD_TIMEOUT=20000      # timeout(1) cho agy

readonly AGY_MODEL="claude-opus-4-6-thinking"   # model agy dung de build graph UA

DRY_RUN=0
LOCK_HELD=0
BUILD_START=""
BUILD_END=""
BUILD_RC=""

ts() { date '+%Y-%m-%d %H:%M:%S'; }

log() {
  local line
  line="[$(ts)] $*"
  printf '%s\n' "$line" | tee -a "$LOG_FILE"
}

die() {
  log "LOI: $*"
  exit 1
}

parse_args() {
  [[ $# -eq 0 ]] && return 0
  [[ $# -eq 1 && "$1" == "--dry-run" ]] && { DRY_RUN=1; return 0; }
  printf 'Dung: %s [--dry-run]\n' "$0" >&2
  exit 64
}

# --- lock ------------------------------------------------------------------

lock_owner_alive() {
  local pid
  pid="$(head -n1 "$LOCK_FILE" 2>/dev/null | tr -dc '0-9')"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

acquire_lock() {
  if (set -o noclobber; printf 'pid=%s\nstart=%s\n' "$$" "$(ts)" > "$LOCK_FILE") 2>/dev/null; then
    LOCK_HELD=1
    log "Da lay lock $LOCK_FILE (pid $$)"
    return 0
  fi
  if lock_owner_alive; then
    log "Da co lock $LOCK_FILE cua tien trinh con song -> thoat ngay (idempotent)"
    exit 0
  fi
  log "Lock $LOCK_FILE cu, chu so huu da chet -> thu hoi"
  rm -f "$LOCK_FILE"
  (set -o noclobber; printf 'pid=%s\nstart=%s\n' "$$" "$(ts)" > "$LOCK_FILE") 2>/dev/null \
    || { log "Khong lay duoc lock sau khi thu hoi -> thoat"; exit 0; }
  LOCK_HELD=1
  log "Da lay lock $LOCK_FILE (pid $$)"
}

release_lock() {
  [[ $LOCK_HELD -eq 1 ]] || return 0
  rm -f "$LOCK_FILE"
  LOCK_HELD=0
}

# --- cho may ranh ----------------------------------------------------------

agy_count() {
  pgrep -x agy.real 2>/dev/null | wc -l
}

wait_for_idle() {
  local deadline=$(( SECONDS + WAIT_MAX_SECONDS ))
  local streak=0
  local running

  log "Bat dau vong cho: toi da ${WAIT_MAX_SECONDS}s, moi ${POLL_SECONDS}s kiem tra 'pgrep -x agy.real', can ${IDLE_STREAK_NEEDED} lan sach lien tiep"

  while [[ $SECONDS -lt $deadline ]]; do
    running="$(agy_count)"
    if [[ "$running" -gt 0 ]]; then
      [[ $streak -gt 0 ]] && log "Con $running tien trinh agy.real -> reset bo dem (dang o $streak/${IDLE_STREAK_NEEDED})"
      streak=0
      sleep "$POLL_SECONDS"
      continue
    fi
    streak=$(( streak + 1 ))
    log "Khong co agy.real ($streak/${IDLE_STREAK_NEEDED})"
    [[ $streak -ge $IDLE_STREAK_NEEDED ]] && { log "May da ranh lien tuc $(( IDLE_STREAK_NEEDED * POLL_SECONDS ))s -> chay tiep"; return 0; }
    sleep "$POLL_SECONDS"
  done

  log "Het 12 gio cho ma may van chua ranh -> bo qua lan build nay"
  return 1
}

# --- chuyen nguon ----------------------------------------------------------

run_step() {
  local desc="$1"; shift
  log "  \$ $*"
  "$@" >>"$LOG_FILE" 2>&1 || { log "  -> THAT BAI: $desc"; return 1; }
  return 0
}

prepare_sources() {
  log "Chuyen nguon 3 repo con"
  run_step "omni checkout dev-sit"        git -C "$OMNI" checkout dev-sit                  || return 1
  run_step "omni ff-only origin/dev-sit"  git -C "$OMNI" merge --ff-only origin/dev-sit    || return 1
  run_step "ekyc checkout dev"            git -C "$EKYC" checkout dev                      || return 1
  run_step "ekyc ff-only origin/dev"      git -C "$EKYC" merge --ff-only origin/dev        || return 1
  run_step "dvnh-common checkout v5.0.9"  git -C "$COMMON" checkout v5.0.9                 || return 1
  log "Nguon da san sang"
  return 0
}

# --- build -----------------------------------------------------------------

run_build() {
  BUILD_START="$(ts)"
  log "Bat dau build UA (log chi tiet: $BUILD_LOG, timeout ${BUILD_TIMEOUT}s)"
  cd "$ROOT" || return 1
  timeout "$BUILD_TIMEOUT" agy \
    --model "$AGY_MODEL" \
    --effort high \
    --print-timeout 300m \
    --dangerously-skip-permissions \
    -p "$(cat "$PROMPT_FILE")" >>"$BUILD_LOG" 2>&1
  BUILD_RC=$?
  BUILD_END="$(ts)"
  log "Build ket thuc, exit code = $BUILD_RC"
  return 0
}

restore_sources() {
  log "Tra 3 repo con ve nhanh cu: sh $RESTORE_SH"
  sh "$RESTORE_SH" >>"$LOG_FILE" 2>&1
  log "Restore exit code = $?"
}

artifact_line() {
  local path="$1"
  [[ -f "$path" ]] || { printf '  %-22s KHONG CO\n' "$(basename "$path")"; return 0; }
  printf '  %-22s CO, %s (%s bytes)\n' "$(basename "$path")" \
    "$(du -h "$path" | cut -f1)" "$(stat -c%s "$path")"
}

write_status() {
  local outcome="$1"
  {
    printf 'UA BUILD STATUS (vietbank-sme)\n'
    printf 'Ghi luc      : %s\n' "$(ts)"
    printf 'Ket qua      : %s\n' "$outcome"
    printf 'Bat dau build: %s\n' "${BUILD_START:-n/a}"
    printf 'Ket thuc     : %s\n' "${BUILD_END:-n/a}"
    printf 'Exit code    : %s\n' "${BUILD_RC:-n/a}"
    printf 'Artifact (%s/.ua):\n' "$ROOT"
    artifact_line "$GRAPH_JSON"
    artifact_line "$META_JSON"
    printf 'Log watcher  : %s\n' "$LOG_FILE"
    printf 'Log build    : %s\n' "$BUILD_LOG"
  } > "$STATUS_FILE"
  log "Da ghi status -> $STATUS_FILE"
}

cleanup() {
  release_lock
}

# --- dry run ---------------------------------------------------------------

dry_run() {
  local running
  running="$(agy_count)"
  cat <<TXT
=== DRY RUN: $0 --dry-run ===
Khong doi nhanh, khong chay agy, khong ghi status, khong lay lock.

1. Lock      : $LOCK_FILE
   Hien tai  : $([[ -e "$LOCK_FILE" ]] && echo "DANG TON TAI -> ban that se thoat ngay" || echo "chua co -> ban that se tao va giu")

2. Vong cho  : toi da ${WAIT_MAX_SECONDS}s (12h), moi ${POLL_SECONDS}s chay 'pgrep -x agy.real'
   Con agy    -> reset bo dem; sach ${IDLE_STREAK_NEEDED} lan lien tiep ($(( IDLE_STREAK_NEEDED * POLL_SECONDS ))s) -> chay tiep
   Ngay bay gio: $running tien trinh agy.real$([[ "$running" -gt 0 ]] && echo " -> se phai cho" || echo " -> dem nguoc bat dau ngay")

3. Chuyen nguon (SE KHONG chay o dry-run):
   git -C $OMNI checkout dev-sit
   git -C $OMNI merge --ff-only origin/dev-sit
   git -C $EKYC checkout dev
   git -C $EKYC merge --ff-only origin/dev
   git -C $COMMON checkout v5.0.9
   Nhanh hien tai:
$(printf '     %-22s %s\n' "vietbank-sme-omni" "$(git -C "$OMNI" branch --show-current 2>/dev/null || echo '?')" )
$(printf '     %-22s %s\n' "viet-bank-ekyc-sme" "$(git -C "$EKYC" branch --show-current 2>/dev/null || echo '?')" )
$(printf '     %-22s %s\n' "dvnh-common" "$(git -C "$COMMON" branch --show-current 2>/dev/null || git -C "$COMMON" describe --tags 2>/dev/null || echo '?')" )

4. Build (SE KHONG chay o dry-run):
   cd $ROOT
   timeout $BUILD_TIMEOUT agy --model $AGY_MODEL --effort high --print-timeout 300m \\
     --dangerously-skip-permissions -p "\$(cat $PROMPT_FILE)" >> $BUILD_LOG 2>&1
   Prompt file: $([[ -f "$PROMPT_FILE" ]] && echo "CO ($(stat -c%s "$PROMPT_FILE") bytes)" || echo "KHONG CO -> ban that se dung lai")

5. Sau build (du thanh cong hay loi):
   sh $RESTORE_SH   -> $([[ -f "$RESTORE_SH" ]] && echo "CO" || echo "KHONG CO -> ban that se bao loi")
   ghi $STATUS_FILE (moc bat dau/ket thuc, exit code, artifact)
   Artifact kiem tra:
$(artifact_line "$GRAPH_JSON")
$(artifact_line "$META_JSON")

6. Log moi buoc kem timestamp -> $LOG_FILE

Khong pkill, khong sua config.yaml, khong restart service.
=== HET DRY RUN ===
TXT
}

# --- main ------------------------------------------------------------------

main() {
  parse_args "$@"
  mkdir -p "$(dirname "$LOG_FILE")" "$STATE_DIR"

  [[ $DRY_RUN -eq 1 ]] && { dry_run; exit 0; }

  trap cleanup EXIT INT TERM

  log "===== ua_build_watch bat dau (pid $$) ====="
  acquire_lock

  [[ -f "$PROMPT_FILE" ]] || die "Thieu prompt file $PROMPT_FILE"
  [[ -f "$RESTORE_SH" ]]  || die "Thieu restore script $RESTORE_SH"
  [[ -d "$ROOT" ]]        || die "Thieu thu muc nguon $ROOT"

  wait_for_idle || { write_status "TIMEOUT - het 12h cho, khong build"; log "===== ket thuc (timeout) ====="; exit 2; }

  prepare_sources || {
    log "Chuyen nguon that bai -> khong build, tra lai nhanh cu"
    restore_sources
    write_status "LOI CHUYEN NGUON - khong build"
    log "===== ket thuc (loi chuyen nguon) ====="
    exit 3
  }

  run_build
  restore_sources
  write_status "$([[ "${BUILD_RC:-1}" -eq 0 ]] && echo "BUILD XONG (exit 0)" || echo "BUILD LOI (exit ${BUILD_RC})")"
  log "===== ket thuc (exit code build = ${BUILD_RC}) ====="
  exit "${BUILD_RC:-1}"
}

main "$@"
