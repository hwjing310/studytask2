"""全局配置：路径、常量。"""

from __future__ import annotations

import os

# project/ 目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "campusevent.db")

# 前端构建产物（Vite build 输出）
FRONTEND_ROOT = os.path.join(os.path.dirname(BASE_DIR), "frontend")
DIST_DIR = os.path.join(FRONTEND_ROOT, "dist")

# 登录态
TOKEN_TTL_HOURS = 12

# 默认端口
DEFAULT_PORT = 8000
