#!/usr/bin/env bash
set -euo pipefail

# example checks (edit to your machine)
CMD_OK="$(command -v docker || true)"
PING_OK="$(ping -c1 8.8.8.8 >/dev/null 2>&1 && echo ok || echo fail)"

FAILS=0

if [[ -z "$CMD_OK" ]]; then
  echo "docker: NOT FOUND"; ((FAILS++))
else
  echo "docker: OK"
fi

if [[ "$PING_OK" != "ok" ]]; then
  echo "network: FAIL"; ((FAILS++))
else
  echo "network: OK"
fi

[[ $FAILS -gt 0 ]] && exit 1 || exit 0
