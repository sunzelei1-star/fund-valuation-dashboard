#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="${VENV_DIR:-.venv}"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  echo "❌ 未找到虚拟环境: $VENV_DIR"
  echo "   请先运行 ./scripts/setup.sh"
  exit 1
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python scripts/preflight.py

echo "🚀 启动 Streamlit..."
exec streamlit run app.py
