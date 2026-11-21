"""SQLite 连接、建表、种子数据、口令哈希。"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3

from ..domain.models import Activity, PolicyType, Role, Student, now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id    TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'STUDENT',
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,
    start_at    TEXT NOT NULL,
    location    TEXT NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    policy_type TEXT NOT NULL CHECK (policy_type IN ('DIRECT','REVIEW')),
    waitlist_capacity INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    deleted_at  TEXT
);

CREATE TABLE IF NOT EXISTS registrations (
    registration_id TEXT PRIMARY KEY,
    activity_id     TEXT NOT NULL REFERENCES activities(activity_id),
    student_id      TEXT NOT NULL REFERENCES students(student_id),
    status          TEXT NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED','WAITLISTED')),
    waitlist_position INTEGER,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_registration_active
    ON registrations(activity_id, student_id)
    WHERE status IN ('PENDING','APPROVED','WAITLISTED');

CREATE INDEX IF NOT EXISTS ix_registration_activity_status
    ON registrations(activity_id, status);

CREATE TABLE IF NOT EXISTS messages (
    message_id      TEXT PRIMARY KEY,
    student_id      TEXT NOT NULL,
    activity_id     TEXT NOT NULL,
    registration_id TEXT NOT NULL,
    status          TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    is_read         INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_message_once
    ON messages(registration_id, status);

CREATE TABLE IF NOT EXISTS notify_failures (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   TEXT NOT NULL,
    payload    TEXT NOT NULL,
    error      TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tokens (
    token      TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def hash_password(password: str, *, iterations: int = 120_000) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations_s, salt, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "pbkdf2":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations_s)
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    # CR-01 迁移：旧库补列 + 重建 registrations（CHECK 约束需要包含 WAITLISTED）
    _ensure_column(conn, "activities", "waitlist_capacity", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "registrations", "waitlist_position", "INTEGER")
    _rebuild_registrations_v2(conn)


def _table_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row["sql"] if row else ""


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        conn.commit()


def _rebuild_registrations_v2(conn: sqlite3.Connection) -> None:
    """SQLite 无法修改 CHECK 约束，只能重建表；用事务保证要么全成要么全回滚。"""
    if "WAITLISTED" in _table_sql(conn, "registrations"):
        return

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    previous = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN")
        conn.execute(
            """CREATE TABLE registrations_new (
                   registration_id TEXT PRIMARY KEY,
                   activity_id     TEXT NOT NULL REFERENCES activities(activity_id),
                   student_id      TEXT NOT NULL REFERENCES students(student_id),
                   status          TEXT NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED','WAITLISTED')),
                   waitlist_position INTEGER,
                   created_at      TEXT NOT NULL,
                   updated_at      TEXT NOT NULL
               )"""
        )
        conn.execute(
            """INSERT INTO registrations_new
               (registration_id, activity_id, student_id, status, waitlist_position, created_at, updated_at)
               SELECT registration_id, activity_id, student_id, status, NULL, created_at, updated_at
               FROM registrations"""
        )
        conn.execute("DROP TABLE registrations")
        conn.execute("ALTER TABLE registrations_new RENAME TO registrations")
        conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS ux_registration_active
               ON registrations(activity_id, student_id)
               WHERE status IN ('PENDING','APPROVED','WAITLISTED')"""
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS ix_registration_activity_status
               ON registrations(activity_id, status)"""
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.isolation_level = previous
        conn.execute("PRAGMA foreign_keys = ON")


DEMO_STUDENTS = [
    ("admin", "管理员", Role.ADMIN, "admin123"),
    ("s001", "张同学", Role.STUDENT, "student123"),
    ("s002", "李同学", Role.STUDENT, "student123"),
    ("s003", "王同学", Role.STUDENT, "student123"),
    ("s004", "赵同学", Role.STUDENT, "student123"),
    ("s005", "钱同学", Role.STUDENT, "student123"),
]

DEMO_ACTIVITIES = [
    Activity(
        activity_id="a001",
        title="羽毛球社招新",
        category="体育",
        start_at="2026-12-05T14:00:00",
        location="体育馆 2 号场",
        capacity=2,
        policy_type=PolicyType.DIRECT,
        waitlist_capacity=2,
        created_at=now_iso(),
    ),
    Activity(
        activity_id="a002",
        title="编程马拉松（24h）",
        category="学术",
        start_at="2026-12-12T09:00:00",
        location="实验楼 A301",
        capacity=2,
        policy_type=PolicyType.REVIEW,
        created_at=now_iso(),
    ),
    Activity(
        activity_id="a003",
        title="校园歌手大赛",
        category="文艺",
        start_at="2026-12-18T19:00:00",
        location="大学生活动中心",
        capacity=50,
        policy_type=PolicyType.REVIEW,
        created_at=now_iso(),
    ),
    Activity(
        activity_id="a004",
        title="人工智能前沿讲座",
        category="学术",
        start_at="2026-12-10T14:00:00",
        location="图书馆报告厅",
        capacity=120,
        policy_type=PolicyType.DIRECT,
        created_at=now_iso(),
    ),
    Activity(
        activity_id="a005",
        title="摄影展志愿者招募（限额 3 人）",
        category="志愿",
        start_at="2026-12-08T09:00:00",
        location="图书馆一层",
        capacity=3,
        policy_type=PolicyType.DIRECT,
        waitlist_capacity=3,
        created_at=now_iso(),
    ),
    Activity(
        activity_id="a006",
        title="读书会（仅 1 个名额）",
        category="社团",
        start_at="2026-12-15T18:30:00",
        location="图书馆研讨室 3",
        capacity=1,
        policy_type=PolicyType.DIRECT,
        waitlist_capacity=2,
        created_at=now_iso(),
    ),
]


def seed(conn: sqlite3.Connection) -> None:
    """种子数据：学生与示例活动均按 id 幂等补种，已有数据不会被覆盖或重复。"""
    for student_id, name, role, password in DEMO_STUDENTS:
        conn.execute(
            "INSERT OR IGNORE INTO students(student_id, name, role, password_hash) VALUES (?,?,?,?)",
            (student_id, name, role.value, hash_password(password)),
        )
    for activity in DEMO_ACTIVITIES:
        conn.execute(
            """INSERT OR IGNORE INTO activities(activity_id,title,category,start_at,location,capacity,policy_type,waitlist_capacity,created_at,deleted_at)
               VALUES (?,?,?,?,?,?,?,?,?,NULL)""",
            (
                activity.activity_id,
                activity.title,
                activity.category,
                activity.start_at,
                activity.location,
                activity.capacity,
                activity.policy_type.value,
                activity.waitlist_capacity,
                activity.created_at,
            ),
        )
    conn.commit()
