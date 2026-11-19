"""活动服务单测：参数校验、容量下调保护、软删除可见性。"""

from __future__ import annotations

import unittest

from support import Env

from project.domain.errors import ConflictError, NotFoundError, ValidationError


class ActivityServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = Env()
        self.admin = self.env.student("admin")
        self.svc = self.env.activities

    def tearDown(self) -> None:
        self.env.cleanup()

    def _payload(self, **over):
        base = {
            "title": "测试活动",
            "category": "体育",
            "start_at": "2099-01-01T10:00:00",
            "location": "体育馆",
            "capacity": 10,
            "policy_type": "DIRECT",
        }
        base.update(over)
        return base

    def test_create_ok(self):
        created = self.svc.create(self.admin, self._payload())
        self.assertEqual(created["title"], "测试活动")
        self.assertEqual(created["remaining"], 10)
        self.assertTrue(created["open"])

    def test_title_required(self):
        with self.assertRaises(ValidationError):
            self.svc.create(self.admin, self._payload(title="  "))

    def test_capacity_must_be_positive(self):
        for bad in (0, -1, "abc", None):
            with self.assertRaises(ValidationError):
                self.svc.create(self.admin, self._payload(capacity=bad))

    def test_policy_type_must_be_known(self):
        with self.assertRaises(ValidationError):
            self.svc.create(self.admin, self._payload(policy_type="LOTTERY"))

    def test_start_at_must_be_iso(self):
        with self.assertRaises(ValidationError):
            self.svc.create(self.admin, self._payload(start_at="下周一下午"))

    def test_update_capacity_below_approved_conflicts(self):
        created = self.svc.create(self.admin, self._payload(capacity=2))
        self.env.registrations.register(self.env.student("s001"), created["activity_id"])
        self.env.registrations.register(self.env.student("s002"), created["activity_id"])

        with self.assertRaises(ConflictError) as ctx:
            self.svc.update(self.admin, created["activity_id"], {"capacity": 1})
        self.assertEqual(ctx.exception.code, "CAPACITY_BELOW_APPROVED")

    def test_soft_delete_hides_activity(self):
        created = self.svc.create(self.admin, self._payload())
        self.svc.soft_delete(self.admin, created["activity_id"])

        with self.assertRaises(NotFoundError):
            self.svc.get(created["activity_id"])
        titles = [a["title"] for a in self.svc.list()]
        self.assertNotIn(created["title"], titles)

    def test_list_filter_by_title(self):
        self.svc.create(self.admin, self._payload(title="篮球赛"))
        self.svc.create(self.admin, self._payload(title="朗诵比赛"))
        found = self.svc.list("篮球")
        self.assertEqual([a["title"] for a in found], ["篮球赛"])

    def test_stats_shape(self):
        created = self.svc.create(self.admin, self._payload(capacity=3))
        stats = self.svc.stats(created["activity_id"])
        self.assertEqual(
            set(stats),
            {"activity_id", "approved", "pending", "waitlisted", "capacity", "remaining"},
        )
        self.assertEqual(stats["remaining"], 3)


if __name__ == "__main__":
    unittest.main()
