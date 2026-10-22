#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$project_dir/.venv313/bin/python"
dashboard_dir="$project_dir/frontend/vanilla"
api_pid=""
web_pid=""

cleanup() {
  if [[ -n "$api_pid" ]] && kill -0 "$api_pid" 2>/dev/null; then
    kill "$api_pid" 2>/dev/null || true
  fi
  if [[ -n "$web_pid" ]] && kill -0 "$web_pid" 2>/dev/null; then
    kill "$web_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -x "$python_bin" ]]; then
  echo "Python environment missing. Follow the one-time setup in docs/FACULTY_DEMO.md."
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

echo "Starting vanilla HTML/CSS/JS dashboard..."
"$python_bin" -m http.server 3000 --bind 127.0.0.1 --directory "$dashboard_dir" \
  >"$project_dir/work/frontend.log" 2>&1 &
web_pid="$!"

for _ in {1..20}; do
  if curl --silent --fail http://127.0.0.1:3000/ >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

if ! curl --silent --fail http://127.0.0.1:3000/ >/dev/null 2>&1; then
  echo "Dashboard did not start. Check work/frontend.log for details."
  exit 1
fi

echo
echo "Bottleneck is ready:"
echo "  Dashboard: http://127.0.0.1:3000"
echo "  API docs:  http://127.0.0.1:8000/docs"
echo "  A2A card:  http://127.0.0.1:8000/a2a/.well-known/agent-card.json"
echo "Press Ctrl+C to stop the demo."
echo

wait "$web_pid"
