"""打包扩展版部署产物：build/CampusEvent-ext-<stamp>.zip

与 tools/package.py 的区别：额外包含 ext/ 与 run_ext.py（不改原打包脚本）。
"""

from __future__ import annotations

import os
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "build")

INCLUDE = [
    "project",
    "frontend/dist",
    "tests",
    "docs",
    "ext",
    "run.py",
    "run_ext.py",
    "README.md",
    "requirements.txt",
]

EXCLUDE_DIRS = {"__pycache__", "node_modules", ".git", "data"}
EXCLUDE_SUFFIX = (".db", ".db-wal", ".db-shm", ".log", ".err", ".pyc")


def should_skip(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    return path.endswith(EXCLUDE_SUFFIX)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M")
    out = os.path.join(OUT_DIR, f"CampusEvent-ext-{stamp}.zip")

    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in INCLUDE:
            target = os.path.join(ROOT, item)
            if os.path.isfile(target):
                zf.write(target, item)
                count += 1
                continue
            if not os.path.isdir(target):
                print(f"skip (missing): {item}")
                continue
            for dirpath, dirnames, files in os.walk(target):
                dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
                for name in files:
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, ROOT).replace("\\", "/")
                    if should_skip(rel):
                        continue
                    zf.write(full, rel)
                    count += 1

    print(f"packed {count} files -> {out} ({os.path.getsize(out) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
