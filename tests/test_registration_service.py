"""报名服务单测：名额、重复、状态机、权限、幂等。"""

from __future__ import annotations

import unittest

from support import Env

from project.domain.errors import ConflictError, ForbiddenError, NotFoundError
from project.domain.models import RegistrationStatus
from project.notify.events import RegistrationEvent


class RegistrationServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = Env()
        self.svc = self.env.registrations
        self.s1 = self.env.student("s001")
        self.s2 = self.env.student("s002")

    def tearDown(self) -> None:
        self.env.cleanup()

    # ---------- 直接报名 ----------
    def test_direct_register_auto_approved_and_notified(self):
        act = self.env.make_activity(policy="DIRECT", capacity=2)
        reg = self.svc.register(self.s1, act["activity_id"])

        self.assertEqual(reg["status"], "APPROVED")
        stats = self.env.activities.stats(act["activity_id"])
        self.assertEqual((stats["approved"], stats["pending"], stats["remaining"]), (1, 0, 1))

        msgs = self.env.messages.list_mine(self.s1)
        self.assertEqual(len(msgs), 1)
        self.assertIn(act["title"], msgs[0]["content"])

    def test_duplicate_active_registration_rejected(self):
        act = self.env.make_activity(capacity=5)
        self.svc.register(self.s1, act["activity_id"])
        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s1, act["activity_id"])
        self.assertEqual(ctx.exception.code, "ALREADY_REGISTERED")

    def test_capacity_full_rejected(self):
        act = self.env.make_activity(capacity=1)
        self.svc.register(self.s1, act["activity_id"])
        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(ctx.exception.code, "CAPACITY_FULL")

    # ---------- 审核型 ----------
    def test_review_register_pending_does_not_consume_capacity(self):
        act = self.env.make_activity(policy="REVIEW", capacity=1)
        reg = self.svc.register(self.s1, act["activity_id"])

        self.assertEqual(reg["status"], "PENDING")
        stats = self.env.activities.stats(act["activity_id"])
        self.assertEqual((stats["approved"], stats["pending"], stats["remaining"]), (0, 1, 1))

        # 待审核不占名额：第二个人仍可提交
        reg2 = self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(reg2["status"], "PENDING")

    def test_approve_moves_to_approved_and_notifies(self):
        act = self.env.make_activity(policy="REVIEW", capacity=2)
        reg = self.svc.register(self.s1, act["activity_id"])

        admin = self.env.student("admin")
        approved = self.svc.approve(admin, reg["registration_id"])
        self.assertEqual(approved["status"], "APPROVED")

        stats = self.env.activities.stats(act["activity_id"])
        self.assertEqual((stats["approved"], stats["pending"], stats["remaining"]), (1, 0, 1))

        statuses = [m["status"] for m in self.env.messages.list_mine(self.s1)]
        self.assertIn("PENDING", statuses)
        self.assertIn("APPROVED", statuses)

    def test_approve_when_capacity_full_keeps_pending(self):
        act = self.env.make_activity(policy="REVIEW", capacity=1)
        reg1 = self.svc.register(self.s1, act["activity_id"])
        reg2 = self.svc.register(self.s2, act["activity_id"])
        admin = self.env.student("admin")

        self.svc.approve(admin, reg1["registration_id"])
        with self.assertRaises(ConflictError) as ctx:
            self.svc.approve(admin, reg2["registration_id"])
        self.assertEqual(ctx.exception.code, "CAPACITY_FULL")

        stats = self.env.activities.stats(act["activity_id"])
        self.assertEqual((stats["approved"], stats["pending"]), (1, 1))

    def test_approve_non_pending_is_conflict(self):
        act = self.env.make_activity(policy="REVIEW", capacity=2)
        reg = self.svc.register(self.s1, act["activity_id"])
        admin = self.env.student("admin")
        self.svc.approve(admin, reg["registration_id"])

        with self.assertRaises(ConflictError) as ctx:
            self.svc.approve(admin, reg["registration_id"])
        self.assertEqual(ctx.exception.code, "INVALID_STATE")

    def test_reject_pending(self):
        act = self.env.make_activity(policy="REVIEW", capacity=2)
        reg = self.svc.register(self.s1, act["activity_id"])
        admin = self.env.student("admin")

        rejected = self.svc.reject(admin, reg["registration_id"])
        self.assertEqual(rejected["status"], "REJECTED")

        # 被拒后可再次申请（历史记录保留）
        again = self.svc.register(self.s1, act["activity_id"])
        self.assertEqual(again["status"], "PENDING")
        self.assertNotEqual(again["registration_id"], reg["registration_id"])

    # ---------- 取消 ----------
    def test_cancel_own_registration(self):
        act = self.env.make_activity(capacity=2)
        reg = self.svc.register(self.s1, act["activity_id"])

        cancelled = self.svc.cancel(self.s1, reg["registration_id"])
        self.assertEqual(cancelled["status"], "CANCELLED")
        stats = self.env.activities.stats(act["activity_id"])
        self.assertEqual(stats["approved"], 0)

        # 取消后可再次报名
        again = self.svc.register(self.s1, act["activity_id"])
        self.assertEqual(again["status"], "APPROVED")

    def test_cancel_others_registration_forbidden(self):
        act = self.env.make_activity(capacity=2)
        reg = self.svc.register(self.s1, act["activity_id"])

        with self.assertRaises(ForbiddenError) as ctx:
            self.svc.cancel(self.s2, reg["registration_id"])
        self.assertEqual(ctx.exception.code, "NOT_OWNER")

    def test_cancel_twice_conflict(self):
        act = self.env.make_activity(capacity=2)
        reg = self.svc.register(self.s1, act["activity_id"])
        self.svc.cancel(self.s1, reg["registration_id"])

        with self.assertRaises(ConflictError) as ctx:
            self.svc.cancel(self.s1, reg["registration_id"])
        self.assertEqual(ctx.exception.code, "INVALID_STATE")

    # ---------- 时间与存在性 ----------
    def test_started_activity_cannot_register(self):
        act = self.env.make_activity(start_at="2020-01-01T10:00:00")
        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s1, act["activity_id"])
        self.assertEqual(ctx.exception.code, "ACTIVITY_STARTED")

    def test_deleted_activity_not_found(self):
        act = self.env.make_activity()
        admin = self.env.student("admin")
        self.env.activities.soft_delete(admin, act["activity_id"])

        with self.assertRaises(NotFoundError):
            self.svc.register(self.s1, act["activity_id"])

    # ---------- 通知幂等 ----------
    def test_repeated_event_does_not_duplicate_message(self):
        act = self.env.make_activity(capacity=2)
        reg = self.svc.register(self.s1, act["activity_id"])
        before = len(self.env.messages.list_mine(self.s1))

        # 模拟事件重复投递（同一 event_id）
        event = RegistrationEvent.build(
            registration_id=reg["registration_id"],
            activity_id=act["activity_id"],
            student_id=self.s1.student_id,
            status="APPROVED",
            activity_title=act["title"],
            version=1,
        )
        self.env.bus.publish(event)
        self.env.bus.publish(event)

        after = len(self.env.messages.list_mine(self.s1))
        self.assertEqual(before, after, "同一事件重复投递不应产生多条消息")


if __name__ == "__main__":
    unittest.main()
