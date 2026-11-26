"""扩展层数据库变更：新增列与表，全部幂等。"""

from __future__ import annotations

import sqlite3

from project.domain.models import now_iso

GRADE_LABELS = {1: "大一", 2: "大二", 3: "大三", 4: "大四"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ext_activity_grade_rules (
    activity_id TEXT PRIMARY KEY REFERENCES activities(activity_id),
    min_grade   INTEGER NOT NULL CHECK (min_grade BETWEEN 1 AND 4),
    max_grade   INTEGER NOT NULL CHECK (max_grade BETWEEN 1 AND 4),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    CHECK (min_grade <= max_grade)
);

CREATE TABLE IF NOT EXISTS ext_emails (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL UNIQUE,
    registration_id TEXT NOT NULL,
    student_id      TEXT NOT NULL,
    to_addr         TEXT NOT NULL,
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('SENDING','SENT','FAILED')),
    error           TEXT,
    created_at      TEXT NOT NULL,
    sent_at         TEXT
);

CREATE INDEX IF NOT EXISTS ix_ext_emails_created ON ext_emails(created_at DESC);
"""

# 演示账号的初始年级：覆盖 CR1-01 ~ CR1-04 的四种情况
DEMO_GRADES = {
    "s001": 1,  # 大一（应被拒绝）
    "s002": 2,  # 大二（应通过）
    "s003": 3,  # 大三（应通过）
    "s004": 4,  # 大四（应被拒绝）
    "s005": 2,  # 大二
}


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def migrate_ext(conn: sqlite3.Connection) -> None:
    """给 students 增加 grade 列（若不存在），并建规则表。"""
    if "grade" not in _columns(conn, "students"):
        conn.execute("ALTER TABLE students ADD COLUMN grade INTEGER")
    conn.executescript(SCHEMA)
    conn.commit()


def seed_grades(conn: sqlite3.Connection) -> None:
    """仅补齐 grade 为空的演示账号，不覆盖管理员手工设置的值。"""
    for student_id, grade in DEMO_GRADES.items():
        conn.execute(
            "UPDATE students SET grade=? WHERE student_id=? AND grade IS NULL",
            (grade, student_id),
        )
    conn.commit()


def grade_label(grade: int | None) -> str:
    if grade is None:
        return "未登记"
    return GRADE_LABELS.get(grade, f"{grade}年级")


def now() -> str:
    return now_iso()
