"""站内信订阅者：把报名事件翻译成站内消息；失败留痕但不影响业务。"""

from __future__ import annotations

import json
import logging
import uuid

from ..domain.models import Message, RegistrationStatus
from ..notify.events import DomainEvent, EventSubscriber, RegistrationEvent
from ..repo.ports import MessageRepository, NotifyFailureRepository

log = logging.getLogger("campusevent.inbox")

_TEXT = {
    RegistrationStatus.APPROVED.value: "你报名的活动「{title}」已通过。",
    RegistrationStatus.PENDING.value: "你报名的活动「{title}」已提交，等待管理员审核。",
    RegistrationStatus.REJECTED.value: "你报名的活动「{title}」未通过审核。",
    RegistrationStatus.CANCELLED.value: "你已取消活动「{title}」的报名。",
}


class InboxNotifier(EventSubscriber):
    def __init__(self, messages: MessageRepository, failures: NotifyFailureRepository) -> None:
        self._messages = messages
        self._failures = failures

    def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, RegistrationEvent):
            return
        if event.status not in _TEXT:
            return

        content = _TEXT[event.status].format(title=event.activity_title or event.activity_id)
        message = Message(
            message_id="m_" + uuid.uuid4().hex[:12],
            student_id=event.student_id,
            activity_id=event.activity_id,
            registration_id=event.registration_id,
            status=event.status,
            content=content,
        )
        try:
            self._messages.add(message)
        except Exception as exc:  # noqa: BLE001 - BR6：留痕、不回滚
            log.warning("notify failed event=%s err=%s", event.event_id, exc)
            try:
                self._failures.add(
                    event_id=event.event_id,
                    payload=json.dumps(
                        {
                            "registration_id": event.registration_id,
                            "activity_id": event.activity_id,
                            "student_id": event.student_id,
                            "status": event.status,
                        },
                        ensure_ascii=False,
                    ),
                    error=str(exc),
                )
            except Exception:  # noqa: BLE001
                log.exception("failed to record notify failure event=%s", event.event_id)
