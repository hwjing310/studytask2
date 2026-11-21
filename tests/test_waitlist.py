"""CR-01 候补队列：验收与边界（CR-AC1–CR-AC5）。"""

from __future__ import annotations

import unittest

from support import Env

from project.domain.errors import ConflictError


class WaitlistTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = Env()
        self.svc = self.env.registrations
        self.admin = self.env.student("admin")
        self.s1 = self.env.student("s001")
        self.s2 = self.env.student("s002")
        self.s3 = self.env.student("s003")

    def tearDown(self) -> None:
        self.env.cleanup()

    def _make(self, *, capacity=1, waitlist=2):
        created = self.env.activities.create(
            self.admin,
            {
                "title": "CR-候补测试",
                "category": "测试",
                "start_at": "2099-06-01T10:00:00",
                "location": "某处",
                "capacity": capacity,
                "policy_type": "DIRECT",
                "waitlist_capacity": waitlist,
            },
        )
        return created

    # CR-AC1 候补成功且位次递增
    def test_full_then_waitlist_with_position(self):
        act = self._make(capacity=1, waitlist=2)
        self.svc.register(self.s1, act["activity_id"])

        first = self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(first["status"], "WAITLISTED")
        self.assertEqual(first["waitlist_position"], 1)

        second = self.svc.register(self.s3, act["activity_id"])
        self.assertEqual(second["waitlist_position"], 2)

        stats = self.env.activities.stats(act["activity_id"])
        self.assertEqual((stats["approved"], stats["waitlisted"], stats["remaining"]), (1, 2, 0))

    # CR-AC2 候补满
    def test_waitlist_full(self):
        act = self._make(capacity=1, waitlist=1)
        self.svc.register(self.s1, act["activity_id"])
        self.svc.register(self.s2, act["activity_id"])

        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s3, act["activity_id"])
        self.assertEqual(ctx.exception.code, "WAITLIST_FULL")

    def test_waitlist_disabled_keeps_old_error(self):
        act = self._make(capacity=1, waitlist=0)
        self.svc.register(self.s1, act["activity_id"])

        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(ctx.exception.code, "CAPACITY_FULL")

    # CR-AC3 取消已通过 → 最早候补自动补位
    def test_cancel_promotes_first_waitlisted(self):
        act = self._make(capacity=1, waitlist=2)
        r1 = self.svc.register(self.s1, act["activity_id"])
        r2 = self.svc.register(self.s2, act["activity_id"])
        r3 = self.svc.register(self.s3, act["activity_id"])
        self.assertEqual(r3["waitlist_position"], 2)

        self.svc.cancel(self.s1, r1["registration_id"])

        promoted = self.env.repos.registrations.get(r2["registration_id"])
        self.assertEqual(promoted.status.value, "APPROVED")
        self.assertIsNone(promoted.waitlist_position)

        still = self.env.repos.registrations.get(r3["registration_id"])
        self.assertEqual(still.status.value, "WAITLISTED")

        stats = self.env.activities.stats(act["activity_id"])
        self.assertEqual((stats["approved"], stats["waitlisted"]), (1, 1))

        contents = [m["content"] for m in self.env.messages.list_mine(self.s2)]
        self.assertTrue(any("补位" in c for c in contents), contents)

    # CR-AC4 取消候补不影响名额
    def test_cancel_waitlisted(self):
        act = self._make(capacity=1, waitlist=2)
        self.svc.register(self.s1, act["activity_id"])
        r2 = self.svc.register(self.s2, act["activity_id"])

        cancelled = self.svc.cancel(self.s2, r2["registration_id"])
        self.assertEqual(cancelled["status"], "CANCELLED")

        stats = self.env.activities.stats(act["activity_id"])
        self.assertEqual((stats["approved"], stats["waitlisted"], stats["remaining"]), (1, 0, 0))

        # 取消后可再次报名（此时仍满员 → 重新候补）
        again = self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(again["status"], "WAITLISTED")

    # CR-AC5 统计字段
    def test_stats_exposes_waitlisted(self):
        act = self._make(capacity=1, waitlist=1)
        stats = self.env.activities.stats(act["activity_id"])
        self.assertIn("waitlisted", stats)
        self.assertEqual(stats["waitlisted"], 0)

    # CR-R6 候补也算有效报名
    def test_waitlisted_counts_as_active(self):
        act = self._make(capacity=1, waitlist=2)
        self.svc.register(self.s1, act["activity_id"])
        self.svc.register(self.s2, act["activity_id"])

        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(ctx.exception.code, "ALREADY_REGISTERED")

    # 审核型不受候补影响
    def test_review_activity_unaffected(self):
        act = self.env.activities.create(
            self.admin,
            {
                "title": "CR-审核不受影响",
                "category": "测试",
                "start_at": "2099-06-02T10:00:00",
                "location": "某处",
                "capacity": 1,
                "policy_type": "REVIEW",
                "waitlist_capacity": 5,
            },
        )
        r1 = self.svc.register(self.s1, act["activity_id"])
        self.svc.approve(self.admin, r1["registration_id"])

        r2 = self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(r2["status"], "PENDING", "审核型满员时应进入待审核而非候补")

        with self.assertRaises(ConflictError) as ctx:
            self.svc.approve(self.admin, r2["registration_id"])
        self.assertEqual(ctx.exception.code, "CAPACITY_FULL")

        self.assertEqual(self.env.activities.stats(act["activity_id"])["waitlisted"], 0)


class AdminWaitlistTest(unittest.TestCase):
    """CR-02：管理员把待审核申请手动转为候补。"""

    def setUp(self) -> None:
        self.env = Env()
        self.svc = self.env.registrations
        self.admin = self.env.student("admin")
        self.s1 = self.env.student("s001")
        self.s2 = self.env.student("s002")

    def tearDown(self) -> None:
        self.env.cleanup()

    def _review_activity(self, *, capacity=1, waitlist=0):
        return self.env.activities.create(
            self.admin,
            {
                "title": "CR-02 数字建模比赛",
                "category": "学术",
                "start_at": "2099-07-01T10:00:00",
                "location": "机房",
                "capacity": capacity,
                "policy_type": "REVIEW",
                "waitlist_capacity": waitlist,
            },
        )

    def test_waitlist_pending_and_autoset_capacity(self):
        act = self._review_activity(capacity=1, waitlist=0)
        reg = self.svc.register(self.s1, act["activity_id"])
        self.assertEqual(reg["status"], "PENDING")

        moved = self.svc.waitlist(self.admin, reg["registration_id"])
        self.assertEqual(moved["status"], "WAITLISTED")
        self.assertEqual(moved["waitlist_position"], 1)

        # 未配置候补上限时自动补成容量
        self.assertEqual(self.env.activities.get(act["activity_id"])["waitlist_capacity"], 1)

    def test_waitlist_only_for_pending(self):
        act = self._review_activity(capacity=2, waitlist=2)
        reg = self.svc.register(self.s1, act["activity_id"])
        self.svc.approve(self.admin, reg["registration_id"])

        with self.assertRaises(ConflictError) as ctx:
            self.svc.waitlist(self.admin, reg["registration_id"])
        self.assertEqual(ctx.exception.code, "INVALID_STATE")

    def test_waitlist_full(self):
        act = self._review_activity(capacity=5, waitlist=1)
        r1 = self.svc.register(self.s1, act["activity_id"])
        r2 = self.svc.register(self.s2, act["activity_id"])
        self.svc.waitlist(self.admin, r1["registration_id"])

        with self.assertRaises(ConflictError) as ctx:
            self.svc.waitlist(self.admin, r2["registration_id"])
        self.assertEqual(ctx.exception.code, "WAITLIST_FULL")

    def test_waitlisted_promoted_when_slot_frees(self):
        act = self._review_activity(capacity=1, waitlist=0)
        r1 = self.svc.register(self.s1, act["activity_id"])
        self.svc.approve(self.admin, r1["registration_id"])

        r2 = self.svc.register(self.s2, act["activity_id"])
        self.svc.waitlist(self.admin, r2["registration_id"])

        # 名额释放 → 候补者自动通过
        self.svc.cancel(self.s1, r1["registration_id"])
        promoted = self.env.repos.registrations.get(r2["registration_id"])
        self.assertEqual(promoted.status.value, "APPROVED")

    def test_admin_cannot_register(self):
        act = self.env.make_activity(capacity=5)
        with self.assertRaises(Exception) as ctx:
            self.svc.register(self.admin, act["activity_id"])
        self.assertEqual(getattr(ctx.exception, "code", None), "ADMIN_CANNOT_REGISTER")


if __name__ == "__main__":
    unittest.main()
