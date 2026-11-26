"""组合式扩展：继承原服务，只覆写必要方法，不修改原实现。

- GradeAwareRegistrationService：在调用原 register() 之前增加年级校验
  （名额、开始时间、重复报名等公共规则仍由原实现处理）
- GradeAwareActivityService：在返回的活动数据上补充 grade_rule 字段
"""

from __future__ import annotations

from project.domain.errors import ConflictError, NotFoundError
from project.service.activity import ActivityService
from project.service.registration import RegistrationService

from .rules import GradeRuleRepository, StudentGradeRepository
from .schema import grade_label


class GradeAwareRegistrationService(RegistrationService):
    def __init__(
        self,
        *,
        activities,
        registrations,
        students,
        policies,
        bus,
        rules: GradeRuleRepository,
        student_grades: StudentGradeRepository,
    ) -> None:
        super().__init__(
            activities=activities,
            registrations=registrations,
            students=students,
            policies=policies,
            bus=bus,
        )
        self._rules = rules
        self._student_grades = student_grades

    def register(self, student, activity_id: str) -> dict:
        activity = self._activities.get(activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")

        rule = self._rules.get(activity_id)
        if rule is not None:
            grade = self._student_grades.get_grade(student.student_id)
            if grade is None:
                raise ConflictError(
                    "你的年级尚未登记，无法报名年级限定活动",
                    code="GRADE_MISSING",
                )
            if not rule.allows(grade):
                raise ConflictError(
                    f"该活动仅限{rule.label}报名（你的年级：{grade_label(grade)}）",
                    code="GRADE_NOT_ALLOWED",
                )

        return super().register(student, activity_id)


class GradeAwareActivityService(ActivityService):
    def __init__(self, activities, rules: GradeRuleRepository) -> None:
        super().__init__(activities)
        self._rules = rules

    def list(self, query: str = "") -> list[dict]:
        items = super().list(query)
        rules = self._rules.list_all()
        for item in items:
            rule = rules.get(item["activity_id"])
            item["grade_rule"] = rule.to_dict() if rule else None
        return items

    def get(self, activity_id: str) -> dict:
        data = super().get(activity_id)
        rule = self._rules.get(activity_id)
        data["grade_rule"] = rule.to_dict() if rule else None
        return data
