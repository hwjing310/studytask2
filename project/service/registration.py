"""报名服务：编排报名、取消、审批；名额等公共规则集中在此（D4）。"""

from __future__ import annotations

import uuid

from ..domain.errors import ConflictError, ForbiddenError, NotFoundError
from ..domain.models import (
    Activity,
    PolicyType,
    Registration,
    RegistrationStatus,
    Role,
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

    def participants(self, activity_id: str) -> dict:
        """管理员视角：某活动的已通过 / 候补 / 待审核名单。"""
        activity = self._activities.get(activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")

        def rows(status: RegistrationStatus) -> list[dict]:
            items = [
                self._decorate(r, with_student=True)
                for r in self._registrations.list_by_activity_status(activity_id, status)
            ]
            if status is RegistrationStatus.WAITLISTED:
                items.sort(key=lambda x: (x.get("waitlist_position") or 0, x["created_at"]))
            else:
                items.sort(key=lambda x: x["updated_at"], reverse=True)
            return items

        return {
            "activity_id": activity_id,
            "title": activity.title,
            "capacity": activity.capacity,
            "approved": rows(RegistrationStatus.APPROVED),
            "waitlisted": rows(RegistrationStatus.WAITLISTED),
            "pending": rows(RegistrationStatus.PENDING),
        }

    # ---------------- 命令 ----------------
    def register(self, student: Student, activity_id: str) -> dict:
        if student.role is Role.ADMIN:
            raise ForbiddenError("管理员账号不参与报名，请使用学生账号演示", code="ADMIN_CANNOT_REGISTER")
        activity = self._activities.get(activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")
        if activity.is_started():
            raise ConflictError("活动已开始，无法报名", code="ACTIVITY_STARTED")
        if self._registrations.find_active(activity_id, student.student_id):
            raise ConflictError("你已报名该活动", code="ALREADY_REGISTERED")

        approved = self._activities.count_approved(activity_id)
        policy = self._policies.create(activity.policy_type)

        # 直接型：提交即占名额。名额满时按 CR-01 进入候补；未配置候补则保持原错误
        if policy.policy_type is PolicyType.DIRECT and activity.is_full(approved):
            waitlisted = self._activities.count_waitlisted(activity_id)
            if activity.waitlist_capacity <= 0:
                raise ConflictError("名额已满", code="CAPACITY_FULL")
            if activity.is_waitlist_full(waitlisted):
                raise ConflictError("名额与候补均已满", code="WAITLIST_FULL")
            position = self._registrations.next_waitlist_position(activity_id)
            registration = Registration(
                registration_id="r_" + uuid.uuid4().hex[:10],
                activity_id=activity_id,
                student_id=student.student_id,
                status=RegistrationStatus.WAITLISTED,
                waitlist_position=position,
                created_at=now_iso(),
                updated_at=now_iso(),
            )
            self._registrations.add(registration)
            self._publish(registration, activity, version=1)
            return self._decorate(registration)

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

        was_approved = registration.status is RegistrationStatus.APPROVED
        registration.status = RegistrationStatus.CANCELLED
        registration.waitlist_position = None
        registration.updated_at = now_iso()
        self._registrations.update(registration)

        activity = self._activities.get(registration.activity_id, include_deleted=True)
        if activity:
            self._publish(registration, activity, version=2)
            if was_approved:
                self._promote_next(activity)

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

    def waitlist(self, admin: Student, registration_id: str) -> dict:
        """管理员把待审核申请转为候补（CR-02）。

        - 仅 PENDING 可转；
        - 活动未配置候补上限（0）时，自动设为该活动的容量，避免“按钮点了没反应”；
        - 名额释放时由 _promote_next 按位次自动转为已通过。
        """
        registration = self._require(registration_id)
        if registration.status is not RegistrationStatus.PENDING:
            raise ConflictError("只有待审核的申请可以转为候补", code="INVALID_STATE")

        activity = self._activities.get(registration.activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")

        if activity.waitlist_capacity <= 0:
            activity.waitlist_capacity = max(activity.capacity, 1)
            self._activities.update(activity)

        waitlisted = self._activities.count_waitlisted(activity.activity_id)
        if activity.is_waitlist_full(waitlisted):
            raise ConflictError("候补名额已满", code="WAITLIST_FULL")

        registration.status = RegistrationStatus.WAITLISTED
        registration.waitlist_position = self._registrations.next_waitlist_position(activity.activity_id)
        registration.updated_at = now_iso()
        self._registrations.update(registration)
        self._publish(registration, activity, version=2)
        return self._decorate(registration)
    def _promote_next(self, activity: Activity) -> None:
        """取消已通过报名后，按候补顺序补位（CR-R3）。"""
        for _ in range(5):  # 防御：跳过已被其他并发操作处理的候补
            candidate = self._registrations.first_waitlisted(activity.activity_id)
            if candidate is None:
                return
            approved = self._activities.count_approved(activity.activity_id)
            if activity.is_full(approved):
                return
            candidate.status = RegistrationStatus.APPROVED
            candidate.waitlist_position = None
            candidate.updated_at = now_iso()
            self._registrations.update(candidate)
            self._publish(candidate, activity, version=2, event_type="registration.promoted")
            return

    def _require(self, registration_id: str) -> Registration:
        registration = self._registrations.get(registration_id)
        if registration is None:
            raise NotFoundError("报名记录不存在", code="REGISTRATION_NOT_FOUND")
        return registration

    def _publish(
        self,
        registration: Registration,
        activity: Activity,
        *,
        version: int,
        event_type: str = "registration.status_changed",
    ) -> None:
        self._bus.publish(
            RegistrationEvent.build(
                registration_id=registration.registration_id,
                activity_id=registration.activity_id,
                student_id=registration.student_id,
                status=registration.status.value,
                activity_title=activity.title,
                version=version,
                event_type=event_type,
                waitlist_position=registration.waitlist_position,
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
