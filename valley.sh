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
[ -d site/node_modules ] || (cd site && npm install)

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
