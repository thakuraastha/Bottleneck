#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$project_dir/.venv313/bin/python"
dashboard_dir="$project_dir/frontend/dashboard"
api_pid=""

cleanup() {
  if [[ -n "$api_pid" ]] && kill -0 "$api_pid" 2>/dev/null; then
    kill "$api_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -x "$python_bin" ]]; then
  echo "Python environment missing. Follow the one-time setup in docs/FACULTY_DEMO.md."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is missing. Install Node.js 22 or newer, then run this script again."
  exit 1
fi

mkdir -p "$project_dir/work"

if curl --silent --fail http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "API already running at http://127.0.0.1:8000"
else
  echo "Starting Bottleneck API..."
  (
    cd "$project_dir"
    PYTHONPATH=backend "$python_bin" scripts/start_api.py
  ) >"$project_dir/work/api.log" 2>&1 &
  api_pid="$!"

  for _ in {1..40}; do
    if curl --silent --fail http://127.0.0.1:8000/health >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done

  if ! curl --silent --fail http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "API did not start. Check work/api.log for details."
    exit 1
  fi
fi

if [[ ! -d "$dashboard_dir/node_modules" ]]; then
  echo "Installing dashboard dependencies (first run only)..."
  (cd "$dashboard_dir" && corepack pnpm install --frozen-lockfile)
fi

echo
echo "Bottleneck is ready:"
echo "  Dashboard: http://127.0.0.1:3000"
echo "  API docs:  http://127.0.0.1:8000/docs"
echo "Press Ctrl+C to stop the demo."
echo

cd "$dashboard_dir"
BOTTLENECK_API_URL=http://127.0.0.1:8000 \
  corepack pnpm dev --hostname 127.0.0.1 --port 3000
