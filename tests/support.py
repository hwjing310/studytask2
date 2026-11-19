"""测试支撑：用真实 SQLite 仓储 + 进程内事件总线搭一个最小环境。

注意：本机 %TEMP% 不可写（新建文件会被拒绝），因此临时库放在 project/data/ 下。
"""

from __future__ import annotations

import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from project.notify.events import EventBus  # noqa: E402
from project.notify.inbox import InboxNotifier  # noqa: E402
from project.policy.base import PolicyFactory  # noqa: E402
from project.repo import db  # noqa: E402
from project.repo.sqlite_repo import SqliteRepositories  # noqa: E402
from project.service.activity import ActivityService  # noqa: E402
from project.service.auth import AuthService  # noqa: E402
from project.service.message import MessageService  # noqa: E402
from project.service.registration import RegistrationService  # noqa: E402

DATA_DIR = os.path.join(ROOT, "project", "data")


class Env:
    def __init__(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self.db_path = os.path.join(DATA_DIR, f"test_{uuid.uuid4().hex[:8]}.db")
        self.conn = db.connect(self.db_path)
        db.migrate(self.conn)
        db.seed(self.conn)

        self.repos = SqliteRepositories(self.conn)
        self.bus = EventBus()
        self.bus.subscribe(InboxNotifier(self.repos.messages, self.repos.notify_failures))
        self.policies = PolicyFactory()

        self.auth = AuthService(self.repos.students, self.repos.tokens)
        self.activities = ActivityService(self.repos.activities)
        self.registrations = RegistrationService(
            activities=self.repos.activities,
            registrations=self.repos.registrations,
            students=self.repos.students,
            policies=self.policies,
            bus=self.bus,
        )
        self.messages = MessageService(self.repos.messages)

    def student(self, sid: str):
        s = self.repos.students.get(sid)
        assert s is not None
        return s

    def make_activity(self, *, policy: str = "DIRECT", capacity: int = 2, start_at: str = "2099-01-01T10:00:00", title: str = "测试活动"):
        admin = self.student("admin")
        return self.activities.create(
            admin,
            {
                "title": title,
                "category": "测试",
                "start_at": start_at,
                "location": "某处",
                "capacity": capacity,
                "policy_type": policy,
            },
        )

    def cleanup(self) -> None:
        try:
            self.conn.close()
        finally:
            for suffix in ("", "-wal", "-shm"):
                path = self.db_path + suffix
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
