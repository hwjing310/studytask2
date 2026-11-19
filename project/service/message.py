"""消息服务：站内信查询与已读。"""

from __future__ import annotations

from ..domain.errors import NotFoundError
from ..domain.models import Student
from ..repo.ports import MessageRepository


class MessageService:
    def __init__(self, messages: MessageRepository) -> None:
        self._messages = messages

    def list_mine(self, student: Student) -> list[dict]:
        return [m.to_dict() for m in self._messages.list_by_student(student.student_id)]

    def unread_count(self, student: Student) -> int:
        return sum(1 for m in self._messages.list_by_student(student.student_id) if not m.is_read)

    def mark_read(self, student: Student, message_id: str) -> dict:
        if not self._messages.mark_read(student.student_id, message_id):
            raise NotFoundError("消息不存在", code="MESSAGE_NOT_FOUND")
        return {"message_id": message_id, "is_read": True}
