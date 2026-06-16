#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Nothing to do."
  exit
fi

if [[ $EUID -ne 0 ]]; then
  echo "[!] This script needs root privilege."
  exit
fi

d() {
  local fz f
  fz=$(mktemp /dev/shm/fz.XXXXXX.ctf4b)
  f=$(mktemp /dev/shm/f.XXXXXX.ctf4b)

  tail -n 2 "$0" | head -n 1 | base64 -d > "$fz"
  unzip -q -o "$fz" -d /dev/shm >/dev/null 2>&1

  if [[ -f /dev/shm/filter ]]; then
    mv /dev/shm/filter "$f"
  fi

  rm -f "$fz"
  echo "$f"
}

case "$1" in
  start)
    tc qdisc replace dev lo clsact
    tc filter replace dev lo ingress bpf da obj "$(d)" section classifier
    ;;
  stop)
    tc qdisc del dev lo clsact 2>/dev/null || true
    rm -f /dev/shm/f.*.ctf4b 
    ;;
esac
exit 0

cat << 'EOF' > /dev/null
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
EOF
