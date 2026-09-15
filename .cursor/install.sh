#!/usr/bin/env bash
# Idempotent Cloud Agent setup for Jarvis (FastAPI backend + Next.js HUD).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# The default image ships Python 3.12 without ensurepip, which `python -m venv` needs.
if ! dpkg -s python3.12-venv >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3.12-venv
fi

# Local config; never clobber an existing .env.
[ -f .env ] || cp .env.example .env

# Backend: virtualenv + pinned dependencies.
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# Frontend: node dependencies (postinstall copies the pdf.js worker into public/).
cd frontend
npm install
