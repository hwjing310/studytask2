"""SQLite 仓储实现。只做持久化，不含业务规则。"""

from __future__ import annotations

import sqlite3
from typing import Optional

from ..domain.models import (
    Activity,
    Message,
    PolicyType,
    Registration,
    RegistrationStatus,
    Role,
    Student,
    now_iso,
)
from .ports import (
    ActivityRepository,
    MessageRepository,
    NotifyFailureRepository,
    RegistrationRepository,
    StudentRepository,
    TokenRepository,
)


def _activity(row: sqlite3.Row) -> Activity:
    return Activity(
        activity_id=row["activity_id"],
        title=row["title"],
        category=row["category"],
        start_at=row["start_at"],
        location=row["location"],
        capacity=row["capacity"],
        policy_type=PolicyType(row["policy_type"]),
        waitlist_capacity=row["waitlist_capacity"],
        created_at=row["created_at"],
        deleted_at=row["deleted_at"],
    )


def _registration(row: sqlite3.Row) -> Registration:
    return Registration(
        registration_id=row["registration_id"],
        activity_id=row["activity_id"],
        student_id=row["student_id"],
        status=RegistrationStatus(row["status"]),
        waitlist_position=row["waitlist_position"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _message(row: sqlite3.Row) -> Message:
    return Message(
        message_id=row["message_id"],
        student_id=row["student_id"],
        activity_id=row["activity_id"],
        registration_id=row["registration_id"],
        status=row["status"],
        content=row["content"],
        created_at=row["created_at"],
        is_read=row["is_read"],
    )


class SqliteActivityRepository(ActivityRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, activity: Activity) -> None:
        self._conn.execute(
            """INSERT INTO activities(activity_id,title,category,start_at,location,capacity,policy_type,waitlist_capacity,created_at,deleted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
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
                activity.deleted_at,
            ),
        )
        self._conn.commit()

    def update(self, activity: Activity) -> None:
        self._conn.execute(
            """UPDATE activities SET title=?, category=?, start_at=?, location=?, capacity=?,
               policy_type=?, waitlist_capacity=? WHERE activity_id=?""",
            (
                activity.title,
                activity.category,
                activity.start_at,
                activity.location,
                activity.capacity,
                activity.policy_type.value,
                activity.waitlist_capacity,
                activity.activity_id,
            ),
        )
        self._conn.commit()

    def soft_delete(self, activity_id: str, deleted_at: str) -> None:
        self._conn.execute(
            "UPDATE activities SET deleted_at=? WHERE activity_id=? AND deleted_at IS NULL",
            (deleted_at, activity_id),
        )
        self._conn.commit()

    def get(self, activity_id: str, *, include_deleted: bool = False) -> Optional[Activity]:
        sql = "SELECT * FROM activities WHERE activity_id=?"
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        row = self._conn.execute(sql, (activity_id,)).fetchone()
        return _activity(row) if row else None

    def list_active(self, query: str = "") -> list[Activity]:
        sql = "SELECT * FROM activities WHERE deleted_at IS NULL"
        params: list = []
        if query:
            sql += " AND title LIKE ?"
            params.append(f"%{query}%")
        sql += " ORDER BY start_at ASC"
        return [_activity(r) for r in self._conn.execute(sql, params).fetchall()]

    def count_approved(self, activity_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM registrations WHERE activity_id=? AND status='APPROVED'",
            (activity_id,),
        ).fetchone()
        return int(row["n"])

    def count_pending(self, activity_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM registrations WHERE activity_id=? AND status='PENDING'",
            (activity_id,),
        ).fetchone()
        return int(row["n"])

    def count_waitlisted(self, activity_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM registrations WHERE activity_id=? AND status='WAITLISTED'",
            (activity_id,),
        ).fetchone()
        return int(row["n"])


class SqliteRegistrationRepository(RegistrationRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, registration: Registration) -> None:
        self._conn.execute(
            """INSERT INTO registrations(registration_id,activity_id,student_id,status,waitlist_position,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                registration.registration_id,
                registration.activity_id,
                registration.student_id,
                registration.status.value,
                registration.waitlist_position,
                registration.created_at,
                registration.updated_at,
            ),
        )
        self._conn.commit()

    def update(self, registration: Registration) -> None:
        self._conn.execute(
            "UPDATE registrations SET status=?, waitlist_position=?, updated_at=? WHERE registration_id=?",
            (
                registration.status.value,
                registration.waitlist_position,
                registration.updated_at,
                registration.registration_id,
            ),
        )
        self._conn.commit()

    def get(self, registration_id: str) -> Optional[Registration]:
        row = self._conn.execute(
            "SELECT * FROM registrations WHERE registration_id=?", (registration_id,)
        ).fetchone()
        return _registration(row) if row else None

    def find_active(self, activity_id: str, student_id: str) -> Optional[Registration]:
        row = self._conn.execute(
            """SELECT * FROM registrations
               WHERE activity_id=? AND student_id=? AND status IN ('PENDING','APPROVED','WAITLISTED')
               LIMIT 1""",
            (activity_id, student_id),
        ).fetchone()
        return _registration(row) if row else None

    def list_by_student(self, student_id: str) -> list[Registration]:
        rows = self._conn.execute(
            "SELECT * FROM registrations WHERE student_id=? ORDER BY created_at DESC",
            (student_id,),
        ).fetchall()
        return [_registration(r) for r in rows]

    def list_by_activity_status(
        self, activity_id: str, status: RegistrationStatus
    ) -> list[Registration]:
        rows = self._conn.execute(
            "SELECT * FROM registrations WHERE activity_id=? AND status=? ORDER BY created_at ASC",
            (activity_id, status.value),
        ).fetchall()
        return [_registration(r) for r in rows]

    def list_pending(self, activity_id: str | None = None) -> list[Registration]:
        if activity_id:
            rows = self._conn.execute(
                """SELECT * FROM registrations WHERE activity_id=? AND status='PENDING'
                   ORDER BY created_at ASC""",
                (activity_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM registrations WHERE status='PENDING'
                   ORDER BY created_at ASC"""
            ).fetchall()
        return [_registration(r) for r in rows]

    def next_waitlist_position(self, activity_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(waitlist_position), 0) + 1 AS n FROM registrations WHERE activity_id=?",
            (activity_id,),
        ).fetchone()
        return int(row["n"])

    def first_waitlisted(self, activity_id: str) -> Optional[Registration]:
        row = self._conn.execute(
            """SELECT * FROM registrations
               WHERE activity_id=? AND status='WAITLISTED'
               ORDER BY waitlist_position ASC, created_at ASC
               LIMIT 1""",
            (activity_id,),
        ).fetchone()
        return _registration(row) if row else None


class SqliteStudentRepository(StudentRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, student_id: str) -> Optional[Student]:
        row = self._conn.execute(
            "SELECT * FROM students WHERE student_id=?", (student_id,)
        ).fetchone()
        if not row:
            return None
        return Student(
            student_id=row["student_id"],
            name=row["name"],
            role=Role(row["role"]),
            password_hash=row["password_hash"],
        )

    def find_by_name(self, name: str) -> Optional[Student]:
        row = self._conn.execute("SELECT * FROM students WHERE name=?", (name,)).fetchone()
        if not row:
            return None
        return Student(
            student_id=row["student_id"],
            name=row["name"],
            role=Role(row["role"]),
            password_hash=row["password_hash"],
        )


class SqliteMessageRepository(MessageRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, message: Message) -> bool:
        cur = self._conn.execute(
            """INSERT OR IGNORE INTO messages
               (message_id,student_id,activity_id,registration_id,status,content,created_at,is_read)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                message.message_id,
                message.student_id,
                message.activity_id,
                message.registration_id,
                message.status,
                message.content,
                message.created_at,
                message.is_read,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_by_student(self, student_id: str) -> list[Message]:
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE student_id=? ORDER BY created_at DESC",
            (student_id,),
        ).fetchall()
        return [_message(r) for r in rows]

    def mark_read(self, student_id: str, message_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE messages SET is_read=1 WHERE message_id=? AND student_id=?",
            (message_id, student_id),
        )
        self._conn.commit()
        return cur.rowcount > 0


class SqliteNotifyFailureRepository(NotifyFailureRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, *, event_id: str, payload: str, error: str) -> None:
        self._conn.execute(
            "INSERT INTO notify_failures(event_id,payload,error,created_at) VALUES (?,?,?,?)",
            (event_id, payload, error, now_iso()),
        )
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM notify_failures").fetchone()
        return int(row["n"])


class SqliteTokenRepository(TokenRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def issue(self, *, token: str, student_id: str, role: str, expires_at: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO tokens(token,student_id,role,expires_at) VALUES (?,?,?,?)",
            (token, student_id, role, expires_at),
        )
        self._conn.commit()

    def get(self, token: str) -> Optional[tuple[str, str, str]]:
        row = self._conn.execute(
            "SELECT student_id, role, expires_at FROM tokens WHERE token=?", (token,)
        ).fetchone()
        if not row:
            return None
        return row["student_id"], row["role"], row["expires_at"]

    def revoke(self, token: str) -> None:
        self._conn.execute("DELETE FROM tokens WHERE token=?", (token,))
        self._conn.commit()


class SqliteRepositories:
    """一次性把全部仓储实例装好，供 app.py 注入。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.activities = SqliteActivityRepository(conn)
        self.registrations = SqliteRegistrationRepository(conn)
        self.students = SqliteStudentRepository(conn)
        self.messages = SqliteMessageRepository(conn)
        self.notify_failures = SqliteNotifyFailureRepository(conn)
        self.tokens = SqliteTokenRepository(conn)
