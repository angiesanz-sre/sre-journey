#!/usr/bin/env bash
set -euo pipefail
# Usage: ./backup.sh SRC_DIR DEST_DIR
SRC="${1:-./}"
DST="${2:-./backups}"
mkdir -p "$DST"
tar -czf "${DST}/backup-$(date +%F-%H%M).tar.gz" "$SRC"   --exclude='./backups' --exclude='./tmp' --exclude='./.git' --exclude='./__pycache__'
find "$DST" -type f -name "backup-*.tar.gz" -mtime +7 -delete
echo "[OK] backup created in $DST"
