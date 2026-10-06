#!/bin/zsh
set -euo pipefail
export PYTHONUNBUFFERED=1

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$ROOT_DIR/.venv/bin/python"
BUILDER="$ROOT_DIR/scripts/build_whiteboard_video.py"
DEFAULT_PROJECT="$ROOT_DIR/assets/whiteboard/whiteboard-vi"

if [[ ! -x "$PYTHON" ]]; then
  print -u2 "[error] Chưa có môi trường Python tại $PYTHON"
  print -u2 "Hãy chạy: python3 scripts/prepare_env.py"
  exit 1
fi

if [[ ! -f "$BUILDER" ]]; then
  print -u2 "[error] Không tìm thấy builder: $BUILDER"
  exit 1
fi

PROJECT_DIR="$DEFAULT_PROJECT"
if [[ $# -gt 0 && "$1" != -* ]]; then
  PROJECT_DIR="$1"
  shift
fi

if [[ ! -f "$PROJECT_DIR/scenes.manifest.json" ]]; then
  print -u2 "[error] Không tìm thấy scenes.manifest.json trong: $PROJECT_DIR"
  print -u2 "Cách dùng: ./build_video.sh [thư-mục-project] [tùy-chọn]"
  exit 1
fi

print "[build] Project: $PROJECT_DIR"
exec "$PYTHON" "$BUILDER" "$PROJECT_DIR" "$@"
