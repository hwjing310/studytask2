"""统一的测试入口：跑全部 unittest，并把 UTF-8 报告写到 tests/last_unit.txt。

用法：
    python tests/run_tests.py
退出码 0 = 全过。
"""

from __future__ import annotations

import io
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "last_unit.txt")


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(HERE, top_level_dir=HERE)

    buf = io.StringIO()
    started = time.time()
    result = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
    elapsed = time.time() - started

    report = buf.getvalue()
    summary = (
        f"\n运行用例：{result.testsRun}，失败：{len(result.failures)}，"
        f"错误：{len(result.errors)}，跳过：{len(result.skipped)}，耗时：{elapsed:.1f}s\n"
    )
    text = report + summary

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)

    # 控制台可能是 GBK，英文摘要更稳
    print(f"tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}")
    print(f"report -> {OUT}")
    if not result.wasSuccessful():
        for case, tb in result.failures + result.errors:
            print("FAILED:", case)
            print(tb.splitlines()[-1] if tb else "")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
