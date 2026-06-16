#!/bin/sh
set -eu

if [ -z "${FLAG+x}" ]; then
  FLAG='ctf4b{**REDACTED**}'
fi
export FLAG
export DISPLAY="${DISPLAY:-:99}"
display_number="${DISPLAY#:}"

node - <<'NODE'
const fs = require("fs");
const flag = process.env.FLAG || "ctf4b{**REDACTED**}";
fs.writeFileSync("/app/extension/secret.js", `self.FLAG = ${JSON.stringify(flag)};\n`);
NODE

rm -f "/tmp/.X${display_number}-lock" "/tmp/.X11-unix/X${display_number}"
Xvfb "$DISPLAY" -screen 0 1280x720x24 >/tmp/xvfb.log 2>&1 &
xvfb_pid="$!"

for _ in $(seq 1 50); do
  if [ -S "/tmp/.X11-unix/X${display_number}" ]; then
    break
  fi
  if ! kill -0 "$xvfb_pid" 2>/dev/null; then
    cat /tmp/xvfb.log >&2
    exit 1
  fi
  sleep 0.1
done

if [ ! -S "/tmp/.X11-unix/X${display_number}" ]; then
  cat /tmp/xvfb.log >&2
  exit 1
fi

cd /app/app
node src/server.js &
app_pid="$!"

term() {
  kill "$app_pid" "$xvfb_pid" 2>/dev/null || true
}
trap term INT TERM

wait "$app_pid"
status="$?"
kill "$xvfb_pid" 2>/dev/null || true
wait "$xvfb_pid" 2>/dev/null || true
exit "$status"
