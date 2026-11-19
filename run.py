"""启动入口（推荐）：python run.py --port 8000

放在仓库根目录，保证 `project` 包在 sys.path 中（便携版 Python 的 ._pth 已包含仓库根）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from project.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
