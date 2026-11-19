"""通知订阅者：写失败要留痕且不影响业务；重复事件不产生重复消息。"""

from __future__ import annotations

import unittest

from support import Env

from project.domain.models import Message
from project.notify.events import RegistrationEvent
from project.notify.inbox import InboxNotifier
from project.repo.ports import MessageRepository, NotifyFailureRepository


class BoomMessageRepository(MessageRepository):
    def add(self, message: Message) -> bool:  # noqa: ARG002
        raise RuntimeError("disk full (injected)")

    def list_by_student(self, student_id: str):  # noqa: ARG002
        return []

    def mark_read(self, student_id: str, message_id: str) -> bool:  # noqa: ARG002
        return False


class CaptureFailureRepository(NotifyFailureRepository):
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, *, event_id: str, payload: str, error: str) -> None:
        self.rows.append((event_id, payload, error))

    def count(self) -> int:
        return len(self.rows)


def make_event(status: str = "APPROVED") -> RegistrationEvent:
    return RegistrationEvent.build(
        registration_id="r_test",
        activity_id="a_test",
        student_id="s001",
        status=status,
        activity_title="测试活动",
        version=1,
    )


class InboxNotifierTest(unittest.TestCase):
    def test_message_written_on_success(self):
        env = Env()
        try:
            notifier = InboxNotifier(env.repos.messages, env.repos.notify_failures)
            notifier.handle(make_event())
            messages = env.repos.messages.list_by_student("s001")
            self.assertEqual(len(messages), 1)
            self.assertIn("测试活动", messages[0].content)
            self.assertEqual(env.repos.notify_failures.count(), 0)
        finally:
            env.cleanup()

    def test_failure_is_recorded_and_swallowed(self):
        failures = CaptureFailureRepository()
        notifier = InboxNotifier(BoomMessageRepository(), failures)

        # 不抛异常（BR6：通知失败不得影响业务）
        notifier.handle(make_event())

        self.assertEqual(len(failures.rows), 1)
        event_id, payload, error = failures.rows[0]
        self.assertEqual(event_id, "r_test:APPROVED:v1")
        self.assertIn("r_test", payload)
        self.assertIn("disk full", error)

    def test_duplicate_event_writes_once(self):
        env = Env()
        try:
            notifier = InboxNotifier(env.repos.messages, env.repos.notify_failures)
            event = make_event()
            notifier.handle(event)
            notifier.handle(event)
            notifier.handle(event)
            self.assertEqual(len(env.repos.messages.list_by_student("s001")), 1)
        finally:
            env.cleanup()

    def test_unknown_event_type_ignored(self):
        env = Env()
        try:
            notifier = InboxNotifier(env.repos.messages, env.repos.notify_failures)
            notifier.handle(make_event("CANCELLED"))  # 有文案，应写入
            self.assertEqual(len(env.repos.messages.list_by_student("s001")), 1)
        finally:
            env.cleanup()


if __name__ == "__main__":
    unittest.main()
