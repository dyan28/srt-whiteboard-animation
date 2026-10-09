#!/bin/zsh
set -euo pipefail
export PYTHONUNBUFFERED=1

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$ROOT_DIR/.venv/bin/python"
RENAMER="$ROOT_DIR/scripts/rename_whiteboard_projects.py"

if [[ ! -x "$PYTHON" ]]; then
  print -u2 "[error] Chưa có môi trường Python tại $PYTHON"
  print -u2 "Hãy chạy: python3 scripts/prepare_env.py"
  exit 1
fi

if [[ ! -f "$RENAMER" ]]; then
  print -u2 "[error] Không tìm thấy script: $RENAMER"
  exit 1
fi

exec "$PYTHON" "$RENAMER" "$@"
