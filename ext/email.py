"""CR-02：模拟邮件通知（观察者订阅者 + Mock 发件器 + 发送记录）。

契约（对应教师变更单）：
- 报名通过 / 审核通过 / 拒绝三类事件：站内信继续，同时发模拟邮件；
- 邮件失败只记录错误，不影响已提交的报名（订阅者绝不向事件总线抛异常）；
- 同一事件（event_id）只发一次：唯一索引 + INSERT OR IGNORE 双重保证。
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from project.domain.models import now_iso
from project.notify.events import DomainEvent, EventSubscriber, RegistrationEvent

log = logging.getLogger("campusevent.ext.email")

EMAIL_DOMAIN = "campus.edu.cn"

_TEMPLATES = {
    "APPROVED": ("报名结果通知：已通过", "你报名的活动「{title}」已通过{RESULT}。"),
    "REJECTED": ("报名结果通知：未通过", "你报名的活动「{title}」未通过审核。"),
}

_PROMOTED_SUFFIX = "（候补自动补位）"


@dataclass
class EmailRecord:
    id: int
    event_id: str
    registration_id: str
    student_id: str
    to_addr: str
    subject: str
    body: str
    status: str
    error: str | None
    created_at: str
    sent_at: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "registration_id": self.registration_id,
            "student_id": self.student_id,
            "to_addr": self.to_addr,
            "subject": self.subject,
            "body": self.body,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
        }


class EmailRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def begin(self, *, event_id: str, registration_id: str, student_id: str,
              to_addr: str, subject: str, body: str) -> int | None:
        """占位插入；若同一 event_id 已存在返回 None（用于去重）。"""
        cur = self._conn.execute(
            """INSERT OR IGNORE INTO ext_emails
               (event_id, registration_id, student_id, to_addr, subject, body, status, created_at)
               VALUES (?,?,?,?,?,?,'SENDING',?)""",
            (event_id, registration_id, student_id, to_addr, subject, body, now_iso()),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            return None
        return int(cur.lastrowid)

    def mark_sent(self, row_id: int) -> None:
        self._conn.execute(
            "UPDATE ext_emails SET status='SENT', sent_at=? WHERE id=?", (now_iso(), row_id)
        )
        self._conn.commit()

    def mark_failed(self, row_id: int, error: str) -> None:
        self._conn.execute(
            "UPDATE ext_emails SET status='FAILED', error=? WHERE id=?", (error[:500], row_id)
        )
        self._conn.commit()

    def list_recent(self, limit: int = 50) -> list[EmailRecord]:
        rows = self._conn.execute(
            "SELECT * FROM ext_emails ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            EmailRecord(
                id=r["id"],
                event_id=r["event_id"],
                registration_id=r["registration_id"],
                student_id=r["student_id"],
                to_addr=r["to_addr"],
                subject=r["subject"],
                body=r["body"],
                status=r["status"],
                error=r["error"],
                created_at=r["created_at"],
                sent_at=r["sent_at"],
            )
            for r in rows
        ]

    def stats(self) -> dict:
        row = self._conn.execute(
            """SELECT
                 SUM(CASE WHEN status='SENT' THEN 1 ELSE 0 END) AS sent,
                 SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS failed,
                 COUNT(*) AS total
               FROM ext_emails"""
        ).fetchone()
        return {"sent": row["sent"] or 0, "failed": row["failed"] or 0, "total": row["total"] or 0}


class MockEmailSender:
    """模拟 SMTP：不联网；可注入一次失败用于演示 CR2-03。"""

    def __init__(self) -> None:
        self._fail_next = False

    def arm_failure(self) -> None:
        self._fail_next = True

    def disarm(self) -> None:
        self._fail_next = False

    @property
    def failing(self) -> bool:
        return self._fail_next

    def send(self, to_addr: str, subject: str, body: str) -> None:
        if self._fail_next:
            self._fail_next = False
            raise RuntimeError("mock-smtp: 550 mailbox unavailable (injected failure)")
        log.info("mock email sent to=%s subject=%s", to_addr, subject)


class EmailNotifier(EventSubscriber):
    """把报名事件翻译成模拟邮件；失败只留痕，绝不抛出。"""

    def __init__(self, repo: EmailRepository, sender: MockEmailSender) -> None:
        self._repo = repo
        self._sender = sender

    def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, RegistrationEvent):
            return
        if event.status not in _TEMPLATES:
            return  # 只处理「通过 / 拒绝」

        subject_tpl, body_tpl = _TEMPLATES[event.status]
        suffix = _PROMOTED_SUFFIX if event.event_type == "registration.promoted" else ""
        title = event.activity_title or event.activity_id
        subject = subject_tpl
        body = body_tpl.format(title=title, RESULT=suffix)
        to_addr = f"{event.student_id}@{EMAIL_DOMAIN}"

        try:
            row_id = self._repo.begin(
                event_id=event.event_id,
                registration_id=event.registration_id,
                student_id=event.student_id,
                to_addr=to_addr,
                subject=subject,
                body=body,
            )
        except Exception:  # noqa: BLE001
            log.exception("email record failed event=%s", event.event_id)
            return

        if row_id is None:
            log.info("email skipped (duplicate event) event=%s", event.event_id)
            return

        try:
            self._sender.send(to_addr, subject, body)
        except Exception as exc:  # noqa: BLE001 - 邮件失败不得影响报名
            log.warning("email failed event=%s err=%s", event.event_id, exc)
            self._repo.mark_failed(row_id, str(exc))
            return

        self._repo.mark_sent(row_id)
