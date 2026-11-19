"""策略层单测：契约（输出只有 APPROVED/PENDING）+ 工厂映射。"""

from __future__ import annotations

import unittest

from support import Env  # noqa: F401  （确保 sys.path 注入）

from project.domain.models import PolicyType, RegistrationStatus
from project.policy.base import (
    DirectApprovalPolicy,
    ManualReviewPolicy,
    PolicyFactory,
    RegistrationContext,
)


class PolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = Env()
        self.activity = self.env.repos.activities.get("a001")
        self.student = self.env.student("s001")
        self.ctx = RegistrationContext(
            activity=self.activity, student=self.student, approved_count=0
        )

    def tearDown(self) -> None:
        self.env.cleanup()

    def test_direct_policy_returns_approved(self):
        self.assertIs(
            DirectApprovalPolicy().decide(self.ctx), RegistrationStatus.APPROVED
        )

    def test_review_policy_returns_pending(self):
        self.assertIs(ManualReviewPolicy().decide(self.ctx), RegistrationStatus.PENDING)

    def test_policies_are_pure(self):
        """策略不得有副作用：连续调用结果一致，且不改动上下文。"""
        policy = DirectApprovalPolicy()
        first = policy.decide(self.ctx)
        second = policy.decide(self.ctx)
        self.assertEqual(first, second)
        self.assertEqual(self.ctx.approved_count, 0)

    def test_factory_maps_policy_type(self):
        factory = PolicyFactory()
        self.assertIsInstance(factory.create(PolicyType.DIRECT), DirectApprovalPolicy)
        self.assertIsInstance(factory.create("REVIEW"), ManualReviewPolicy)
        self.assertIsInstance(factory.create("direct"), DirectApprovalPolicy)

    def test_factory_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            PolicyFactory().create("WAITLIST")


if __name__ == "__main__":
    unittest.main()
