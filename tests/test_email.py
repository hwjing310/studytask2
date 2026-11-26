"""CR-02 模拟邮件通知：单元测试。

覆盖：通过/拒绝触发、待审核不触发、事件去重、发送失败留痕且不影响报名。
"""

from __future__ import annotations

import unittest

from support_ext import ExtEnv

from project.notify.events import RegistrationEvent


class EmailNotifierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = ExtEnv()
        self.svc = self.env.registrations
        self.admin = self.env.student("admin")
        self.s2 = self.env.student("s002")

    def tearDown(self) -> None:
        self.env.cleanup()

    def _direct_activity(self, *, capacity: int = 5):
        return self.env.activities.create(
            self.admin,
            {
                "title": "邮件测试活动",
                "category": "测试",
                "start_at": "2099-09-01T10:00:00",
                "location": "某处",
                "capacity": capacity,
                "policy_type": "DIRECT",
            },
        )

    def _review_activity(self, *, capacity: int = 5):
        return self.env.activities.create(
            self.admin,
            {
                "title": "邮件测试-审核型",
                "category": "测试",
                "start_at": "2099-09-02T10:00:00",
                "location": "某处",
                "capacity": capacity,
                "policy_type": "REVIEW",
            },
        )

    def test_direct_approval_sends_email(self):
        act = self._direct_activity()
        self.svc.register(self.s2, act["activity_id"])

        rows = self.env.emails.list_recent()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "SENT")
        self.assertEqual(rows[0].to_addr, "s002@campus.edu.cn")
        self.assertIn("已通过", rows[0].subject)
        self.assertIn(act["title"], rows[0].body)

    def test_pending_does_not_send(self):
        act = self._review_activity()
        self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(len(self.env.emails.list_recent()), 0)

    def test_approve_and_reject_send(self):
        act = self._review_activity()
        r1 = self.svc.register(self.s2, act["activity_id"])
        self.svc.approve(self.admin, r1["registration_id"])

        r2 = self.svc.register(self.env.student("s003"), act["activity_id"])
        self.svc.reject(self.admin, r2["registration_id"])

        rows = self.env.emails.list_recent()
        self.assertEqual(len(rows), 2)
        self.assertTrue(any("已通过" in r.subject for r in rows))
        self.assertTrue(any("未通过" in r.subject for r in rows))

    def test_duplicate_event_sends_once(self):
        act = self._direct_activity()
        reg = self.svc.register(self.s2, act["activity_id"])
        before = len(self.env.emails.list_recent())

        event = RegistrationEvent.build(
            registration_id=reg["registration_id"],
            activity_id=act["activity_id"],
            student_id=self.s2.student_id,
            status="APPROVED",
            activity_title=act["title"],
            version=1,
        )
        self.env.bus.publish(event)
        self.env.bus.publish(event)

        self.assertEqual(len(self.env.emails.list_recent()), before)

    def test_failure_recorded_but_registration_kept(self):
        self.env.email_sender.arm_failure()
        act = self._direct_activity()
        reg = self.svc.register(self.s2, act["activity_id"])

        # 报名仍然成功
        self.assertEqual(reg["status"], "APPROVED")
        self.assertEqual(self.env.activities.stats(act["activity_id"])["approved"], 1)

        rows = self.env.emails.list_recent()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "FAILED")
        self.assertIn("injected", rows[0].error or "")

        # 失败后下一次恢复正常
        act2 = self._direct_activity()
        self.svc.register(self.env.student("s003"), act2["activity_id"])
        latest = self.env.emails.list_recent()[0]
        self.assertEqual(latest.status, "SENT")

    def test_stats(self):
        act = self._direct_activity()
        self.svc.register(self.s2, act["activity_id"])
        stats = self.env.emails.stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["sent"], 1)
        self.assertEqual(stats["failed"], 0)


if __name__ == "__main__":
    unittest.main()
