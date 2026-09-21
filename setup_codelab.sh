#!/usr/bin/env bash
# The Archive — one-shot environment setup for the CODELAB (uv path).
# Safe to re-run any number of times.
#
# Run ./setup_project.sh FIRST. That one makes the project and puts billing on
# it; this one turns that project into a working lab environment:
#   • aiplatform.googleapis.com + bigquery.googleapis.com enabled on it
#   • .venv built by uv, dependencies pinned by uv.lock
#   • site/node_modules for the Archive (a Next.js app), pinned by package-lock.json
#   • a root .env pointing the lab at Vertex AI on that project
#   • one real Gemini call, so you find out here and not in chapter one
#
# It never prompts and never blocks waiting for input. Every failure exits
# non-zero with a fix to try.
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\n\033[1m%s\033[0m\n' "$1"; }
tick() { printf '  ✓ %s\n' "$1"; }
info() { printf '  · %s\n' "$1"; }
warn() { printf '  ! %s\n' "$1" >&2; }

# Print a block of guidance and stop. Never waits for input: this script has
# to survive being run non-interactively.
die() {
    printf '\n\033[1m✗ %s\033[0m\n\n' "$1" >&2
    shift
    for line in "$@"; do printf '%s\n' "$line" >&2; done
    printf '\n' >&2
    exit 1
}

say "Agent Valley · The Archive · setup"

# ── 0 · gcloud, an account, and a project ─────────────────────────────────────
# ./setup_project.sh leaves all three in place. If any is missing, the honest
# answer is to send you back there rather than half-configure the lab.
command -v gcloud >/dev/null 2>&1 || die \
    "gcloud not found." \
    "This script is written for Cloud Shell, where gcloud is preinstalled." \
    "On a laptop, install the Google Cloud SDK first:" \
    "  https://cloud.google.com/sdk/docs/install"

if [ -z "$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)" ]; then
    die "No active gcloud account." \
        "Authenticate, then re-run this script:" \
        "  gcloud auth login"
fi

# `gcloud config get project` is the modern spelling; `get-value` is the one
# older SDKs understand. ~/project_id.txt is what ./setup_project.sh wrote, and
# is the tiebreaker when gcloud has no project selected.
PROJECT="$(gcloud config get project 2>/dev/null \
    || gcloud config get-value project 2>/dev/null || true)"
PROJECT="$(printf '%s' "$PROJECT" | tr -d '[:space:]')"
case "$PROJECT" in
    "(unset)"|"unset") PROJECT="" ;;
esac

PROJECT_FILE="$HOME/project_id.txt"
if [ -z "$PROJECT" ] && [ -f "$PROJECT_FILE" ]; then
    PROJECT="$(tr -d '[:space:]' < "$PROJECT_FILE" || true)"
    if [ -n "$PROJECT" ]; then
        info "gcloud had no project selected — taking $PROJECT from $PROJECT_FILE"
        gcloud config set project "$PROJECT" >/dev/null 2>&1 || true
    fi
fi

if [ -z "$PROJECT" ]; then
    die "No Google Cloud project selected." \
        "./setup_project.sh makes a project, links billing, and records the id" \
        "in ~/project_id.txt. Run it first:" \
        "" \
        "  ./setup_project.sh" \
        "" \
        "Already have a project you want to use? Point gcloud at it instead:" \
        "  gcloud config set project YOUR_PROJECT_ID"
fi

tick "project: $PROJECT"

# ── 1 · the APIs this lab calls ────────────────────────────────────────────────
# Week three was Gemini-on-Vertex and nothing else. The Archive needs more. The
# tower in chapters 4-5 is Vertex AI Memory Bank, which lives on an Agent
# Engine, and Agent Engine rides the same aiplatform.googleapis.com as the
# generative calls — one enable covers both. The warehouse in chapter 6 is
# BigQuery, and that is the second one. Enabling is idempotent, so re-runs are
# free — and if you did an earlier week on this project, Vertex AI is already on.
say "1 · Cloud APIs"

LAB_APIS="aiplatform.googleapis.com bigquery.googleapis.com"

# One call for both: gcloud takes a list, and a single round trip is quicker
# than one per API. The tick loop below still names them one at a time.
if ! ENABLE_ERR="$(gcloud services enable $LAB_APIS \
        --project="$PROJECT" -q 2>&1)"; then
    die "Could not enable $LAB_APIS on $PROJECT." \
        "gcloud said:" \
        "" \
        "$ENABLE_ERR" \
        "" \
        "If that mentions 403 or PERMISSION_DENIED, the project is simply too" \
        "new — its IAM policy is still propagating. Wait a minute, then run:" \
        "" \
        "  ./setup_codelab.sh" \
        "" \
        "If it mentions billing, link a billing account and re-run:" \
        "  https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT"
fi
for api in $LAB_APIS; do
    tick "$api enabled"
done

# ── 2 · python env + deps (uv owns both) ──────────────────────────────────────
say "2 · Python environment"

# uv may have just been installed into ~/.local/bin by the codelab's curl
# one-liner, in a shell that has not re-read its PATH yet. Look there before
# giving up on it.
if ! command -v uv >/dev/null 2>&1 && [ -x "$HOME/.local/bin/uv" ]; then
    PATH="$HOME/.local/bin:$PATH"
    export PATH
fi

if ! command -v uv >/dev/null 2>&1; then
  printf '  ✗ uv not found. Install it, then re-run ./setup_codelab.sh:\n' >&2
  printf '      curl -LsSf https://astral.sh/uv/install.sh | sh\n' >&2
  exit 1
fi
# uv is the only dependency path here: `uv venv` makes .venv, `uv sync` installs
# exactly what uv.lock pins. Nothing is pip-installed on the side.
#
# Some uv versions refuse to create a venv over one that already exists, which
# would make a second run of this script fail on a clean environment. Only
# create it when it is not there; `uv sync` reconciles it either way.
if [ -d .venv ]; then
    info "reusing the existing .venv"
else
    uv venv
fi
uv sync
tick "uv env + google-adk / google-genai / fastapi + uvicorn / pillow (locked by uv.lock)"

# ── 2b · the Archive's own packages ───────────────────────────────────────────
# The Archive itself (site/) is a Next.js app, and `bash valley.sh` in chapter
# one needs its packages. Install them here, where a minute's wait is expected,
# rather than silently inside valley.sh — an install interrupted there used to
# leave a site/node_modules with no `next` in it, and the next `bash valley.sh`
# died with `sh: next: command not found`. `npm ci` installs exactly what
# package-lock.json pins. Skipped when the binary is already in place, so
# re-runs cost nothing. A failure here is a warning, not a stop: valley.sh
# makes the same check and retries the install itself.
say "2b · The Archive's packages (site/)"

if ! command -v npm >/dev/null 2>&1; then
    warn "npm not found. The agent side works without it, but site/ (the Archive)"
    warn "and 'bash valley.sh' need Node 20+:  https://nodejs.org/en/download"
else
    NODE_MAJOR="$(node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1)"
    if [ -n "$NODE_MAJOR" ] && [ "$NODE_MAJOR" -lt 20 ]; then
        warn "node $(node -v) is older than Next.js wants (20+); the Archive may not start."
    fi
    if [ -x site/node_modules/.bin/next ]; then
        tick "site/node_modules already has next — nothing to install"
    else
        info "npm ci in site/ — about a minute…"
        if (cd site && npm ci --no-audit --no-fund); then
            tick "site/ packages installed (npm ci, pinned by package-lock.json)"
        else
            warn "npm ci failed in site/. 'bash valley.sh' will try again; or by hand:"
            warn "  cd site && npm ci"
        fi
    fi
fi

# ── 3 · credentials and .env ──────────────────────────────────────────────────
# In Cloud Shell application-default credentials are already there, so this is
# a check and not a login: `gcloud auth application-default login` opens a
# browser and waits, which would hang this script. On a laptop without ADC we
# warn and tell you the command to run yourself.
say "3 · Credentials"

if [ -f "$HOME/.config/gcloud/application_default_credentials.json" ] \
   || [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] \
   || [ -n "${CLOUD_SHELL:-}" ]; then
    tick "application-default credentials present"
else
    warn "no application-default credentials found."
    warn "If the Gemini call below fails, run this once and re-run the script:"
    warn "  gcloud auth application-default login"
fi

# The lab reads exactly these five — the same ones .env.example documents,
# with the Vertex AI option chosen for you. The credential is your gcloud
# identity, so there is nothing to paste into this file and nothing to leak
# out of it.
#
# A re-run rewrites those five and keeps everything else — including the
# AGENT_ENGINE line scripts/make_tower.py writes in chapter 4, which is why
# that name is not in the list below. If you added your own settings to .env by
# hand, this script is not going to eat them.
ENV_KEPT=""
if [ -f .env ]; then
    ENV_KEPT="$(grep -vE '^[[:space:]]*(GOOGLE_GENAI_USE_VERTEXAI|GOOGLE_CLOUD_PROJECT|GOOGLE_CLOUD_LOCATION|MEMORY_BANK_LOCATION|BQ_DATASET)[[:space:]]*=' .env || true)"
fi

{
  echo "GOOGLE_GENAI_USE_VERTEXAI=TRUE"
  echo "GOOGLE_CLOUD_PROJECT=$PROJECT"
  # global, not a region: Gemini here runs on dynamic shared quota, so one
  # busy region can 429 through no fault of the student. global draws on
  # capacity across regions. ADK loads .env OVER shell exports, so this
  # file is what actually decides the endpoint.
  echo "GOOGLE_CLOUD_LOCATION=global"
  # Two locations, on purpose: Memory Bank is a regional service and "global"
  # is not one of its regions, so the tower gets us-central1 while the
  # generative calls above stay on global.
  echo "MEMORY_BANK_LOCATION=us-central1"
  # Chapter 6's warehouse: the BigQuery dataset scripts/season.sh loads into.
  echo "BQ_DATASET=archive"
  if [ -n "$ENV_KEPT" ]; then
      printf '%s\n' "$ENV_KEPT"
  fi
} > .env
tick "wrote .env — Vertex AI on project $PROJECT"
if [ -n "$ENV_KEPT" ]; then
    info "kept the other lines that were already in .env"
fi

# ── 4 · prove the model answers ───────────────────────────────────────────────
# The only check worth having: a real call to a real model over the credentials
# this lab will actually use. Everything above is a guess until this line ticks.
#
# The model is read out of archive/agent.py rather than written here. This check
# used to name gemini-2.5-flash while the lab ran gemini-3-flash-preview, which
# made it worse than no check at all: access to the two is granted separately,
# so a project that could reach 2.5 and not 3 got a green tick here and a 403 in
# chapter one — precisely the failure this section exists to catch. One string,
# one place, and grepping it costs nothing and imports nothing.
say "4 · Live check"

LAB_MODEL="$(sed -n 's/^MODEL = "\(.*\)"$/\1/p' archive/agent.py | head -1)"
if [ -z "$LAB_MODEL" ]; then
    LAB_MODEL="gemini-3-flash-preview"
    warn "could not read MODEL from archive/agent.py — checking $LAB_MODEL instead"
fi

export GOOGLE_GENAI_USE_VERTEXAI="TRUE"
export GOOGLE_CLOUD_PROJECT="$PROJECT"
export GOOGLE_CLOUD_LOCATION="global"
export LAB_MODEL

if CHECK_OUT="$(uv run python - <<'PY' 2>&1
import os

from google import genai
from google.genai import types as gt

client = genai.Client()
r = client.models.generate_content(
    model=os.environ["LAB_MODEL"],
    contents="Reply with exactly: the archive is open.",
    config=gt.GenerateContentConfig(
        thinking_config=gt.ThinkingConfig(thinking_budget=0), temperature=0.0))
print(r.text.strip())
PY
)"; then
    tick "$LAB_MODEL: $(printf '%s' "$CHECK_OUT" | tail -1)"
else
    case "$CHECK_OUT" in
        *403*|*PERMISSION_DENIED*)
            die "Gemini answered 403 on $PROJECT." \
                "Nothing is broken — a project this new is still propagating its" \
                "IAM policy, and Vertex AI says no until it finishes. Wait a" \
                "minute, then run:" \
                "" \
                "  ./setup_codelab.sh" \
                "" \
                "It will reuse $PROJECT and pick up where this left off." \
                "" \
                "Vertex AI said:" \
                "" \
                "$CHECK_OUT"
            ;;
        *404*|*NOT_FOUND*|*not\ found*)
            die "Vertex AI does not recognise $LAB_MODEL." \
                "$LAB_MODEL is a PREVIEW model id, and preview ids get retired" \
                "on a schedule that has nothing to do with this lab. If this" \
                "codelab has been sitting on a shelf for a while, that is the" \
                "likely cause and it is a one-line fix." \
                "" \
                "Find the current id:" \
                "  https://cloud.google.com/vertex-ai/generative-ai/docs/models" \
                "" \
                "Then set it in archive/agent.py — this check reads the model from" \
                "there, so the two cannot disagree:" \
                "" \
                "  MODEL = \"the-current-id\"" \
                "" \
                "Vertex AI said:" \
                "" \
                "$CHECK_OUT"
            ;;
        *)
            die "The Gemini call failed on $PROJECT." \
                "Vertex AI said:" \
                "" \
                "$CHECK_OUT" \
                "" \
                "If that mentions credentials, run this once and re-run the script:" \
                "  gcloud auth application-default login" \
                "" \
                "If it mentions billing, link a billing account and re-run:" \
                "  https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT"
            ;;
    esac
fi

say "Setup finished. Next:  uv run python scripts/preflight.py"
printf '\n'
