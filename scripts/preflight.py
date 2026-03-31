#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys
from typing import Dict

REQUIRED_PYTHON = (3, 11)
REQUIRED_PACKAGES: Dict[str, str] = {
    "streamlit": "1.25+",
    "pandas": "1.5+",
    "numpy": "1.23+",
    "plotly": "5.15+",
    "altair": "4.2+",
}


def fail(message: str) -> None:
    print(f"❌ {message}")
    sys.exit(1)


def ok(message: str) -> None:
    print(f"✅ {message}")


def check_python() -> None:
    current = sys.version_info[:3]
    if current < REQUIRED_PYTHON:
        fail(
            "Python 版本过低：当前 {}.{}.{}，需要 >= {}.{}。"
            "\n建议使用 Python 3.11 重新创建虚拟环境。".format(*current, *REQUIRED_PYTHON)
        )
    ok("Python 版本检查通过: {}.{}.{}".format(*current))


def check_packages() -> None:
    missing = []
    for pkg, expected in REQUIRED_PACKAGES.items():
        try:
            module = importlib.import_module(pkg)
            version = getattr(module, "__version__", "unknown")
            ok(f"{pkg} 已安装 (version={version}, expected={expected})")
        except Exception:
            missing.append(pkg)

    if missing:
        fail(
            "缺少关键依赖: {}。\n请先执行: pip install -r requirements.txt"
            .format(", ".join(missing))
        )


def main() -> None:
    print("🔍 运行启动前环境自检...")
    check_python()
    check_packages()
    print("🎉 环境自检通过，可以运行 Streamlit 应用。")


if __name__ == "__main__":
    main()
