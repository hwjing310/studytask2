"""应用入口：装配依赖、初始化数据库、启动 HTTP 服务。

用法：
    python -m project.app --port 8000
    python -m project.app --db path/to/db.sqlite --port 8001
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from .config import DB_PATH, DEFAULT_PORT
from .notify.events import EventBus
from .notify.inbox import InboxNotifier
from .policy.base import PolicyFactory
from .repo import db
from .repo.sqlite_repo import SqliteRepositories
from .service.activity import ActivityService
from .service.auth import AuthService
from .service.message import MessageService
from .service.registration import RegistrationService
from .web.server import App, build_server


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def build_app(db_path: str) -> App:
    conn = db.connect(db_path)
    db.migrate(conn)
    db.seed(conn)

    repos = SqliteRepositories(conn)

    # 通知：事件总线 + 站内信订阅者（失败留痕，不影响业务）
    bus = EventBus()
    bus.subscribe(InboxNotifier(repos.messages, repos.notify_failures))

    auth = AuthService(repos.students, repos.tokens)
    activities = ActivityService(repos.activities)
    registrations = RegistrationService(
        activities=repos.activities,
        registrations=repos.registrations,
        students=repos.students,
        policies=PolicyFactory(),
        bus=bus,
    )
    messages = MessageService(repos.messages)
    return App(
        auth=auth,
        activities=activities,
        registrations=registrations,
        messages=messages,
        db_path=db_path,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CampusEvent 校园活动报名与管理系统")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口（默认 8000）")
    parser.add_argument("--db", default=DB_PATH, help="SQLite 数据库文件路径")
    args = parser.parse_args(argv)

    configure_logging()
    log = logging.getLogger("campusevent")
    app = build_app(args.db)
    server = build_server(app, args.port)

    def _stop(signum, frame):  # noqa: ANN001, ARG001
        log.info("收到退出信号 %s，正在关闭…", signum)
        server.shutdown()

    try:
        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
    except (ValueError, OSError):
        pass  # 某些平台/线程环境不支持

    log.info("CampusEvent 已启动： http://127.0.0.1:%d  （数据库：%s）", args.port, args.db)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        log.info("已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
