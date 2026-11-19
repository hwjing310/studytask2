"""报名服务：编排报名、取消、审批；名额等公共规则集中在此（D4）。"""

from __future__ import annotations

import uuid

from ..domain.errors import ConflictError, ForbiddenError, NotFoundError
from ..domain.models import (
    Activity,
    PolicyType,
    Registration,
    RegistrationStatus,
    Student,
    now_iso,
)
from ..notify.events import EventBus, RegistrationEvent
from ..policy.base import PolicyFactory, RegistrationContext
from ..repo.ports import ActivityRepository, RegistrationRepository, StudentRepository


class RegistrationService:
    def __init__(
        self,
        activities: ActivityRepository,
        registrations: RegistrationRepository,
        students: StudentRepository,
        policies: PolicyFactory,
        bus: EventBus,
    ) -> None:
        self._activities = activities
        self._registrations = registrations
        self._students = students
        self._policies = policies
        self._bus = bus

    # ---------------- 查询 ----------------
    def list_mine(self, student: Student) -> list[dict]:
        return [self._decorate(r) for r in self._registrations.list_by_student(student.student_id)]

    def list_pending(self, activity_id: str | None = None) -> list[dict]:
        if activity_id:
            activity = self._activities.get(activity_id)
            if activity is None:
                raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")
            rows = self._registrations.list_by_activity_status(activity_id, RegistrationStatus.PENDING)
        else:
            rows = self._registrations.list_pending(activity_id=None)
        return [self._decorate(r, with_student=True) for r in rows]

    # ---------------- 命令 ----------------
    def register(self, student: Student, activity_id: str) -> dict:
        activity = self._activities.get(activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")
        if activity.is_started():
            raise ConflictError("活动已开始，无法报名", code="ACTIVITY_STARTED")
        if self._registrations.find_active(activity_id, student.student_id):
            raise ConflictError("你已报名该活动", code="ALREADY_REGISTERED")

        approved = self._activities.count_approved(activity_id)
        policy = self._policies.create(activity.policy_type)

        # 直接型：提交即占名额，必须先确认有余量；审核型不占名额，提交时不校验
        if policy.policy_type is PolicyType.DIRECT and activity.is_full(approved):
            raise ConflictError("名额已满", code="CAPACITY_FULL")

        ctx = RegistrationContext(activity=activity, student=student, approved_count=approved)
        status = policy.decide(ctx)

        registration = Registration(
            registration_id="r_" + uuid.uuid4().hex[:10],
            activity_id=activity_id,
            student_id=student.student_id,
            status=status,
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        self._registrations.add(registration)
        self._publish(registration, activity, version=1)
        return self._decorate(registration)

    def cancel(self, student: Student, registration_id: str) -> dict:
        registration = self._require(registration_id)
        if registration.student_id != student.student_id:
            raise ForbiddenError("只能取消自己的报名", code="NOT_OWNER")
        if not registration.can_cancel():
            raise ConflictError("当前状态不可取消", code="INVALID_STATE")
        registration.status = RegistrationStatus.CANCELLED
        registration.updated_at = now_iso()
        self._registrations.update(registration)
        activity = self._activities.get(registration.activity_id, include_deleted=True)
        if activity:
            self._publish(registration, activity, version=2)
        return self._decorate(registration)

    def approve(self, admin: Student, registration_id: str) -> dict:
        registration = self._require(registration_id)
        if registration.status is not RegistrationStatus.PENDING:
            raise ConflictError("该申请状态已变更，请刷新", code="INVALID_STATE")

        activity = self._activities.get(registration.activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")

        approved = self._activities.count_approved(activity.activity_id)
        if activity.is_full(approved):
            raise ConflictError("名额已满，无法批准", code="CAPACITY_FULL")

        registration.status = RegistrationStatus.APPROVED
        registration.updated_at = now_iso()
        self._registrations.update(registration)
        self._publish(registration, activity, version=2)
        return self._decorate(registration)

    def reject(self, admin: Student, registration_id: str) -> dict:
        registration = self._require(registration_id)
        if registration.status is not RegistrationStatus.PENDING:
            raise ConflictError("该申请状态已变更，请刷新", code="INVALID_STATE")
        registration.status = RegistrationStatus.REJECTED
        registration.updated_at = now_iso()
        self._registrations.update(registration)
        activity = self._activities.get(registration.activity_id, include_deleted=True)
        if activity:
            self._publish(registration, activity, version=2)
        return self._decorate(registration)

    # ---------------- 内部 ----------------
    def _require(self, registration_id: str) -> Registration:
        registration = self._registrations.get(registration_id)
        if registration is None:
            raise NotFoundError("报名记录不存在", code="REGISTRATION_NOT_FOUND")
        return registration

    def _publish(self, registration: Registration, activity: Activity, *, version: int) -> None:
        self._bus.publish(
            RegistrationEvent.build(
                registration_id=registration.registration_id,
                activity_id=registration.activity_id,
                student_id=registration.student_id,
                status=registration.status.value,
                activity_title=activity.title,
                version=version,
            )
        )

    def _decorate(self, registration: Registration, *, with_student: bool = False) -> dict:
        data = registration.to_dict()
        activity = self._activities.get(registration.activity_id, include_deleted=True)
        data["activity_title"] = activity.title if activity else "(活动已删除)"
        data["activity_start_at"] = activity.start_at if activity else None
        if with_student:
            student = self._students.get(registration.student_id)
            data["student_name"] = student.name if student else registration.student_id
        return data
