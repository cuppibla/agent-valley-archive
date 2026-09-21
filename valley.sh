#!/usr/bin/env bash
# Boot the Archive: the agent (8440) + the app (3440). Ctrl+C stops both.
# Ports are overridable:  AGENT_PORT=8441 APP_PORT=3441 bash valley.sh
set -euo pipefail
cd "$(dirname "$0")"

AGENT_PORT="${AGENT_PORT:-8440}"
APP_PORT="${APP_PORT:-3440}"

if [ ! -f .env ]; then
  echo "No .env yet. Run:  cp .env.example .env"
  exit 1
fi
if ! .venv/bin/python -c "import forge,sys; sys.exit(0 if forge.MODE else 1)" 2>/dev/null; then
  echo "Not configured yet. Either point gcloud at a project (Vertex, the default):"
  echo "    gcloud config set project YOUR_PROJECT_ID"
  echo "or put an API key in .env — see .env.example."
  exit 1
fi

echo "VALLEY_AGENT_URL=http://127.0.0.1:${AGENT_PORT}" > site/.env.local

# The Archive (site/) is a Next.js app. Look for the `next` binary, not the
# folder: an `npm install` that was cut short — Ctrl+C, a dropped Cloud Shell,
# a full disk — leaves site/node_modules behind with nothing usable in it, the
# folder check passes, and `npm run dev` dies with `sh: next: command not
# found`. `npm ci` installs exactly what package-lock.json pins, from scratch,
# so a half-finished tree cannot survive it.
if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. The Archive (site/) is a Next.js app and needs Node 20+:"
  echo "    https://nodejs.org/en/download"
  exit 1
fi
if [ ! -x site/node_modules/.bin/next ]; then
  echo "  installing the Archive's packages (site/) — about a minute, once…"
  (cd site && if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi)
fi

cleanup() {
  # only what this script started — never the process group, which is whoever
  # launched valley.sh (a capture rig, a wrapper, a tmux pane)
  pkill -P $$ 2>/dev/null || true
  pkill -f "uvicorn archive.service:app --port $AGENT_PORT" 2>/dev/null || true
  pkill -f "next dev -p $APP_PORT" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# The 🚪 button in the app ends this process on purpose — chapter 3's blackout is
# a real restart, not an animation. Bring it back the way a deployment would.
keep_open() {
  while true; do
    .venv/bin/uvicorn archive.service:app --port "$AGENT_PORT" --log-level warning || true
    sleep 1
  done
}
keep_open &
(cd site && npm run dev -- --port "$APP_PORT") &

echo
echo "  archive → http://127.0.0.1:${AGENT_PORT}"
echo "  valley → http://localhost:${APP_PORT}"
echo
wait
