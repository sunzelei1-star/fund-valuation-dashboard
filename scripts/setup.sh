#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
VENV_DIR="${VENV_DIR:-.venv}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "❌ 未找到 $PYTHON_BIN。请先安装 Python 3.11，或使用 PYTHON_BIN 指定解释器。"
  echo "   例如: PYTHON_BIN=python3 ./scripts/setup.sh"
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    print(f"❌ Python 版本过低: {sys.version.split()[0]}，需要 >= 3.11")
    raise SystemExit(1)
print(f"✅ Python 版本可用: {sys.version.split()[0]}")
PY

echo "📦 创建虚拟环境: $VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "⬆️ 升级 pip"
python -m pip install --upgrade pip

echo "📚 安装依赖 requirements.txt"
pip install -r requirements.txt

echo "🩺 执行启动前自检"
python scripts/preflight.py

echo "✅ 环境准备完成。运行: ./scripts/run.sh"
