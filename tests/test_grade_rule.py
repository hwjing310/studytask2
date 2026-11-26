"""CR-01 年级限定报名：单元测试（对应 CR1-01 ~ CR1-04 与公共约束）。"""

from __future__ import annotations

import unittest

from support_ext import ExtEnv

from project.domain.errors import ConflictError


class GradeRuleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = ExtEnv()
        self.svc = self.env.registrations
        self.s1 = self.env.student("s001")  # 大一
        self.s2 = self.env.student("s002")  # 大二
        self.s3 = self.env.student("s003")  # 大三
        self.s4 = self.env.student("s004")  # 大四

    def tearDown(self) -> None:
        self.env.cleanup()

    def _limited_activity(self, *, capacity: int = 5, start_at: str = "2099-08-01T10:00:00"):
        created = self.env.activities.create(
            self.env.student("admin"),
            {
                "title": "年级限定活动",
                "category": "测试",
                "start_at": start_at,
                "location": "某处",
                "capacity": capacity,
                "policy_type": "DIRECT",
            },
        )
        self.env.set_rule(created["activity_id"], 2, 3)
        return created

    def test_grade_seeded(self):
        self.assertEqual(self.env.student_grades.get_grade("s001"), 1)
        self.assertEqual(self.env.student_grades.get_grade("s002"), 2)
        self.assertEqual(self.env.student_grades.get_grade("s003"), 3)
        self.assertEqual(self.env.student_grades.get_grade("s004"), 4)

    # CR1-01
    def test_sophomore_allowed(self):
        act = self._limited_activity()
        reg = self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(reg["status"], "APPROVED")

    # CR1-02
    def test_junior_allowed(self):
        act = self._limited_activity()
        reg = self.svc.register(self.s3, act["activity_id"])
        self.assertEqual(reg["status"], "APPROVED")

    # CR1-03
    def test_freshman_rejected_with_reason(self):
        act = self._limited_activity()
        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s1, act["activity_id"])
        self.assertEqual(ctx.exception.code, "GRADE_NOT_ALLOWED")
        self.assertIn("大二", ctx.exception.message)
        self.assertIn("大一", ctx.exception.message)
        # 未产生报名记录
        self.assertEqual(self.env.activities.stats(act["activity_id"])["approved"], 0)

    # CR1-04
    def test_senior_rejected(self):
        act = self._limited_activity()
        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s4, act["activity_id"])
        self.assertEqual(ctx.exception.code, "GRADE_NOT_ALLOWED")

    def test_rule_removed_allows_everyone(self):
        act = self._limited_activity()
        self.env.grades.delete(act["activity_id"])
        reg = self.svc.register(self.s1, act["activity_id"])
        self.assertEqual(reg["status"], "APPROVED")

    def test_grade_change_takes_effect(self):
        act = self._limited_activity()
        self.env.student_grades.set_grade("s001", 2)
        reg = self.svc.register(self.s1, act["activity_id"])
        self.assertEqual(reg["status"], "APPROVED")

    def test_capacity_still_enforced(self):
        act = self._limited_activity(capacity=1)
        self.svc.register(self.s2, act["activity_id"])
        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s3, act["activity_id"])
        self.assertEqual(ctx.exception.code, "CAPACITY_FULL")

    def test_duplicate_still_enforced(self):
        act = self._limited_activity()
        self.svc.register(self.s2, act["activity_id"])
        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(ctx.exception.code, "ALREADY_REGISTERED")

    def test_started_activity_still_enforced(self):
        act = self._limited_activity(start_at="2020-01-01T10:00:00")
        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(ctx.exception.code, "ACTIVITY_STARTED")

    def test_activity_list_exposes_grade_rule(self):
        act = self._limited_activity()
        items = {a["activity_id"]: a for a in self.env.activities.list()}
        self.assertIsNotNone(items[act["activity_id"]]["grade_rule"])
        self.assertEqual(items[act["activity_id"]]["grade_rule"]["label"], "大二、大三")

        plain = self.env.activities.create(
            self.env.student("admin"),
            {
                "title": "普通活动",
                "category": "测试",
                "start_at": "2099-08-02T10:00:00",
                "location": "某处",
                "capacity": 3,
                "policy_type": "DIRECT",
            },
        )
        items = {a["activity_id"]: a for a in self.env.activities.list()}
        self.assertIsNone(items[plain["activity_id"]]["grade_rule"])

    def test_unregistered_grade_rejected(self):
        act = self._limited_activity()
        self.env.conn.execute("UPDATE students SET grade=NULL WHERE student_id='s002'")
        self.env.conn.commit()
        with self.assertRaises(ConflictError) as ctx:
            self.svc.register(self.s2, act["activity_id"])
        self.assertEqual(ctx.exception.code, "GRADE_MISSING")


if __name__ == "__main__":
    unittest.main()
