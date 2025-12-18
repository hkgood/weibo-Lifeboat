#!/usr/bin/env python3
"""
Launch the macOS-friendly GUI for this project.

Usage:
  python run_gui.py
  python -m src.gui.app
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from src.gui.app import main


if __name__ == "__main__":
    # Guardrail: many crashes/missing deps come from accidentally using the system Python
    # instead of the project's venv. Provide a clear hint.
    try:
        import PySide6  # noqa: F401
    except Exception:
        venv_py = Path(__file__).resolve().parent / ".venv" / "bin" / "python"
        msg = [
            "[weibo-backup] PySide6 未安装 / 当前解释器不包含依赖。",
            "请使用项目的虚拟环境启动：",
            f"  {venv_py} {Path(__file__).name}" if venv_py.exists() else "  . .venv/bin/activate && python run_gui.py",
        ]
        print("\n".join(msg), file=sys.stderr)
        raise SystemExit(1)

    # Optional: show which style is being forced (for crash triage).
    pref = (os.environ.get("WEIBO_GUI_STYLE") or "auto").strip()
    if pref:
        print(f"[weibo-backup] WEIBO_GUI_STYLE={pref}", file=sys.stderr)

    raise SystemExit(main())


