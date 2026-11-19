"""C10：进程重启后数据一致（活动、报名、统计、消息）。

启动真实后端子进程 → 造数据 → 终止 → 重新启动 → 比对快照。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request

from support import Env  # noqa: F401  （注入 sys.path）
from support import ROOT

PORT = 8031
BASE = f"http://127.0.0.1:{PORT}"
DB_PATH = os.path.join(ROOT, "project", "data", "restart_test.db")


def http(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8") or "null")


def wait_health(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _ = http("GET", "/api/health")
            if status == 200:
                return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.25)
    return False


class RestartConsistencyTest(unittest.TestCase):
    def setUp(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = DB_PATH + suffix
            if os.path.exists(path):
                os.remove(path)
        self.proc = None

    def tearDown(self) -> None:
        self._stop()
        for suffix in ("", "-wal", "-shm"):
            path = DB_PATH + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _start(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "run.py", "--port", str(PORT), "--db", DB_PATH],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not wait_health():
            self._stop()
            self.fail("后端未能在 20s 内启动")

    def _stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        self.proc = None

    def test_data_survives_restart(self):
        # ---------- 第一次启动：造数据 ----------
        self._start()
        _, admin = http("POST", "/api/login", {"username": "admin", "password": "admin123"})
        _, s1 = http("POST", "/api/login", {"username": "s001", "password": "student123"})
        _, s2 = http("POST", "/api/login", {"username": "s002", "password": "student123"})

        _, act = http(
            "POST",
            "/api/activities",
            {
                "title": "重启一致性-审核活动",
                "category": "测试",
                "start_at": "2099-05-01T10:00:00",
                "location": "A101",
                "capacity": 2,
                "policy_type": "REVIEW",
            },
            admin["token"],
        )
        aid = act["activity_id"]

        _, r1 = http("POST", f"/api/activities/{aid}/registrations", {}, s1["token"])
        _, _ = http("POST", f"/api/activities/{aid}/registrations", {}, s2["token"])
        http("POST", f"/api/registrations/{r1['registration_id']}/approve", {}, admin["token"])

        _, stats_before = http("GET", f"/api/activities/{aid}/stats")
        _, msgs_before = http("GET", "/api/messages", None, s1["token"])
        _, mine_before = http("GET", "/api/registrations/mine", None, s1["token"])

        self.assertEqual(stats_before["approved"], 1)
        self.assertEqual(stats_before["pending"], 1)
        self.assertGreaterEqual(len(msgs_before["items"]), 2)

        # ---------- 停止并重启 ----------
        self._stop()
        time.sleep(0.3)
        self._start()

        _, admin2 = http("POST", "/api/login", {"username": "admin", "password": "admin123"})
        _, s12 = http("POST", "/api/login", {"username": "s001", "password": "student123"})

        _, stats_after = http("GET", f"/api/activities/{aid}/stats")
        _, msgs_after = http("GET", "/api/messages", None, s12["token"])
        _, mine_after = http("GET", "/api/registrations/mine", None, s12["token"])

        self.assertEqual(stats_before, stats_after, "重启后统计应完全一致")
        self.assertEqual(len(msgs_before["items"]), len(msgs_after["items"]))
        self.assertEqual(len(mine_before["items"]), len(mine_after["items"]))
        self.assertEqual(
            [r["registration_id"] for r in mine_before["items"]],
            [r["registration_id"] for r in mine_after["items"]],
        )

        # 活动详情仍可查
        status, detail = http("GET", f"/api/activities/{aid}")
        self.assertEqual(status, 200)
        self.assertEqual(detail["title"], "重启一致性-审核活动")


if __name__ == "__main__":
    unittest.main()
