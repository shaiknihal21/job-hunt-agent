#!/bin/bash
# Start the job hunt agent from anywhere in the project.
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend" || exit 1

if [ ! -d ".venv" ]; then
  echo "Setting up Python environment (first time only)..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -q
fi

if [ ! -d "$HOME/.cache/ms-playwright/chromium-"* ] 2>/dev/null && \
   [ ! -d "$HOME/Library/Caches/ms-playwright/chromium-"* ] 2>/dev/null; then
  echo "Installing Playwright browser (first time only)..."
  .venv/bin/playwright install chromium
fi

source .venv/bin/activate
python -m app "$@"
