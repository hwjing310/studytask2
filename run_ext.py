"""扩展版启动入口：在原应用之上装配 CR-01 年级限定功能。

用法：
    python run_ext.py --port 8000
    python run_ext.py --port 8001 --db path/to/db.sqlite

与原入口的关系：原 `run.py` / `project.app` 一行未改；本文件复刻其装配步骤，
再替换为扩展版服务并注入扩展路由。
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from project.app import configure_logging
from project.config import DB_PATH, DEFAULT_PORT
from project.notify.events import EventBus
from project.notify.inbox import InboxNotifier
from project.policy.base import PolicyFactory
from project.repo import db
from project.repo.sqlite_repo import SqliteRepositories
from project.service.auth import AuthService
from project.service.message import MessageService
from project.web.server import App, build_server

import ext.api  # noqa: F401  导入即完成路由注入
from ext.rules import GradeRuleRepository, StudentGradeRepository
from ext.schema import migrate_ext, seed_grades
from ext.services import GradeAwareActivityService, GradeAwareRegistrationService


def build_ext_app(db_path: str) -> App:
    conn = db.connect(db_path)
    db.migrate(conn)
    db.seed(conn)
    migrate_ext(conn)
    seed_grades(conn)

    repos = SqliteRepositories(conn)
    grades = GradeRuleRepository(conn)
    student_grades = StudentGradeRepository(conn)

    bus = EventBus()
    bus.subscribe(InboxNotifier(repos.messages, repos.notify_failures))

    auth = AuthService(repos.students, repos.tokens)
    activities = GradeAwareActivityService(repos.activities, grades)
    registrations = GradeAwareRegistrationService(
        activities=repos.activities,
        registrations=repos.registrations,
        students=repos.students,
        policies=PolicyFactory(),
        bus=bus,
        rules=grades,
        student_grades=student_grades,
    )
    messages = MessageService(repos.messages)

    app = App(
        auth=auth,
        activities=activities,
        registrations=registrations,
        messages=messages,
        db_path=db_path,
    )
    app.grades = grades  # 供 ext.api 使用
    app.student_grades = student_grades
    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CampusEvent（含 CR-01 年级限定扩展）")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args(argv)

    configure_logging()
    log = logging.getLogger("campusevent.ext")
    app = build_ext_app(args.db)
    server = build_server(app, args.port)

    def _stop(signum, frame):  # noqa: ANN001, ARG001
        log.info("收到退出信号 %s，正在关闭…", signum)
        server.shutdown()

    try:
        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
    except (ValueError, OSError):
        pass

    log.info("CampusEvent(ext) 已启动： http://127.0.0.1:%d （数据库：%s）", args.port, args.db)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
