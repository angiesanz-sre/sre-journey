#!/usr/bin/env bash
set -euo pipefail
# Usage: ./log_rotator.sh "/path/to/*.log" KEEP_COUNT
PATTERN="${1:-./tmp/logs/*.log}"
KEEP="${2:-5}"

rotate_file () {
  local f="$1"
  if [[ -f "$f" ]]; then
    gzip -c "$f" > "${f}.$(date +%F).gz" || true
    : > "$f"
  fi
  ls -1t "${f}."*.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f
}

for f in $PATTERN; do
  rotate_file "$f"
done
echo "[OK] rotation done for pattern=$PATTERN keep=$KEEP"
