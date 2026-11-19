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
    created_at  TEXT NOT NULL,
    deleted_at  TEXT
);

CREATE TABLE IF NOT EXISTS registrations (
    registration_id TEXT PRIMARY KEY,
    activity_id     TEXT NOT NULL REFERENCES activities(activity_id),
    student_id      TEXT NOT NULL REFERENCES students(student_id),
    status          TEXT NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED')),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_registration_active
    ON registrations(activity_id, student_id)
    WHERE status IN ('PENDING','APPROVED');

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


DEMO_STUDENTS = [
    ("admin", "管理员", Role.ADMIN, "admin123"),
    ("s001", "张同学", Role.STUDENT, "student123"),
    ("s002", "李同学", Role.STUDENT, "student123"),
    ("s003", "王同学", Role.STUDENT, "student123"),
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
]


def seed(conn: sqlite3.Connection) -> None:
    """仅在空库时写入演示数据。"""
    cur = conn.execute("SELECT COUNT(*) AS n FROM students")
    if cur.fetchone()["n"] > 0:
        return
    for student_id, name, role, password in DEMO_STUDENTS:
        conn.execute(
            "INSERT INTO students(student_id, name, role, password_hash) VALUES (?,?,?,?)",
            (student_id, name, role.value, hash_password(password)),
        )
    for activity in DEMO_ACTIVITIES:
        conn.execute(
            """INSERT INTO activities(activity_id,title,category,start_at,location,capacity,policy_type,created_at,deleted_at)
               VALUES (?,?,?,?,?,?,?,?,NULL)""",
            (
                activity.activity_id,
                activity.title,
                activity.category,
                activity.start_at,
                activity.location,
                activity.capacity,
                activity.policy_type.value,
                activity.created_at,
            ),
        )
    conn.commit()
