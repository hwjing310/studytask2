"""报名策略：抽象 + 两种实现 + 工厂。

策略只回答「本次提交应进入哪个状态」，不查库、不做名额判断、不发通知。
名额等公共规则由 RegistrationService 统一处理（见 docs/design-decisions.md D4）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..domain.models import Activity, PolicyType, RegistrationStatus, Student


@dataclass(frozen=True)
class RegistrationContext:
    """策略决策所需的输入（只读）。"""

    activity: Activity
    student: Student
    approved_count: int


class RegistrationPolicy(ABC):
    """报名规则抽象。契约：只返回 APPROVED 或 PENDING，无副作用。"""

    @abstractmethod
    def decide(self, ctx: RegistrationContext) -> RegistrationStatus:  # pragma: no cover - 抽象
        raise NotImplementedError

    @property
    @abstractmethod
    def policy_type(self) -> PolicyType:  # pragma: no cover - 抽象
        raise NotImplementedError


class DirectApprovalPolicy(RegistrationPolicy):
    """直接报名：提交即通过。"""

    @property
    def policy_type(self) -> PolicyType:
        return PolicyType.DIRECT

    def decide(self, ctx: RegistrationContext) -> RegistrationStatus:
        return RegistrationStatus.APPROVED


class ManualReviewPolicy(RegistrationPolicy):
    """审核型报名：提交后进入待审核，不占用名额。"""

    @property
    def policy_type(self) -> PolicyType:
        return PolicyType.REVIEW

    def decide(self, ctx: RegistrationContext) -> RegistrationStatus:
        return RegistrationStatus.PENDING


class PolicyFactory:
    """按活动配置选择策略实现；新增方式时只需在此注册。"""

    def __init__(self) -> None:
        self._registry: dict[PolicyType, RegistrationPolicy] = {
            PolicyType.DIRECT: DirectApprovalPolicy(),
            PolicyType.REVIEW: ManualReviewPolicy(),
        }

    def create(self, policy_type: PolicyType | str) -> RegistrationPolicy:
        if isinstance(policy_type, str):
            policy_type = PolicyType(policy_type.strip().upper())
        return self._registry[policy_type]

    def register(self, policy: RegistrationPolicy) -> None:
        self._registry[policy.policy_type] = policy
