"""活动服务：活动 CRUD 与统计。"""

from __future__ import annotations

import uuid
from datetime import datetime

from ..domain.errors import ConflictError, NotFoundError, ValidationError
from ..domain.models import Activity, ActivityStats, PolicyType, Student, now_iso
from ..repo.ports import ActivityRepository


def _parse_dt(value: str, field: str = "start_at") -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} 必须是 ISO-8601 时间，例如 2026-12-05T14:00:00")


class ActivityService:
    def __init__(self, activities: ActivityRepository) -> None:
        self._activities = activities

    # ---------- 查询 ----------
    def list(self, query: str = "") -> list[dict]:
        result = []
        for activity in self._activities.list_active(query.strip()):
            approved = self._activities.count_approved(activity.activity_id)
            pending = self._activities.count_pending(activity.activity_id)
            waitlisted = self._activities.count_waitlisted(activity.activity_id)
            result.append(activity.to_dict(approved, pending, waitlisted))
        return result

    def get(self, activity_id: str) -> dict:
        activity = self._activities.get(activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")
        approved = self._activities.count_approved(activity_id)
        pending = self._activities.count_pending(activity_id)
        waitlisted = self._activities.count_waitlisted(activity_id)
        return activity.to_dict(approved, pending, waitlisted)

    def stats(self, activity_id: str) -> dict:
        activity = self._activities.get(activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")
        return ActivityStats(
            activity_id=activity_id,
            approved=self._activities.count_approved(activity_id),
            pending=self._activities.count_pending(activity_id),
            capacity=activity.capacity,
            waitlisted=self._activities.count_waitlisted(activity_id),
        ).to_dict()

    # ---------- 命令 ----------
    def create(self, admin: Student, payload: dict) -> dict:
        title = (payload.get("title") or "").strip()
        category = (payload.get("category") or "").strip()
        location = (payload.get("location") or "").strip()
        start_at = payload.get("start_at") or ""
        capacity_raw = payload.get("capacity")
        policy_raw = payload.get("policy_type") or PolicyType.DIRECT.value

        if not title:
            raise ValidationError("活动名称不能为空")
        if not category:
            raise ValidationError("活动类型不能为空")
        if not location:
            raise ValidationError("活动地点不能为空")
        _parse_dt(start_at)
        try:
            capacity = int(capacity_raw)
        except (TypeError, ValueError):
            raise ValidationError("人数上限必须是正整数")
        if capacity <= 0:
            raise ValidationError("人数上限必须大于 0")
        try:
            policy_type = PolicyType(str(policy_raw).upper())
        except ValueError:
            raise ValidationError("报名方式必须是 DIRECT 或 REVIEW")

        waitlist_raw = payload.get("waitlist_capacity", 0)
        try:
            waitlist_capacity = int(waitlist_raw)
        except (TypeError, ValueError):
            raise ValidationError("候补上限必须是非负整数")
        if waitlist_capacity < 0:
            raise ValidationError("候补上限必须是非负整数")

        activity = Activity(
            activity_id="a_" + uuid.uuid4().hex[:8],
            title=title,
            category=category,
            start_at=start_at,
            location=location,
            capacity=capacity,
            policy_type=policy_type,
            waitlist_capacity=waitlist_capacity,
            created_at=now_iso(),
        )
        self._activities.add(activity)
        return activity.to_dict()

    def update(self, admin: Student, activity_id: str, payload: dict) -> dict:
        activity = self._activities.get(activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")

        if "title" in payload:
            title = (payload.get("title") or "").strip()
            if not title:
                raise ValidationError("活动名称不能为空")
            activity.title = title
        if "category" in payload:
            activity.category = (payload.get("category") or "").strip() or activity.category
        if "location" in payload:
            activity.location = (payload.get("location") or "").strip() or activity.location
        if "start_at" in payload:
            _parse_dt(payload.get("start_at") or "")
            activity.start_at = payload["start_at"]
        if "capacity" in payload:
            try:
                capacity = int(payload["capacity"])
            except (TypeError, ValueError):
                raise ValidationError("人数上限必须是正整数")
            if capacity <= 0:
                raise ValidationError("人数上限必须大于 0")
            approved = self._activities.count_approved(activity_id)
            if capacity < approved:
                raise ConflictError(
                    f"已有 {approved} 人通过报名，容量不能小于该数", code="CAPACITY_BELOW_APPROVED"
                )
            activity.capacity = capacity
        if "policy_type" in payload:
            try:
                activity.policy_type = PolicyType(str(payload["policy_type"]).upper())
            except ValueError:
                raise ValidationError("报名方式必须是 DIRECT 或 REVIEW")
        if "waitlist_capacity" in payload:
            try:
                waitlist_capacity = int(payload["waitlist_capacity"])
            except (TypeError, ValueError):
                raise ValidationError("候补上限必须是非负整数")
            if waitlist_capacity < 0:
                raise ValidationError("候补上限必须是非负整数")
            activity.waitlist_capacity = waitlist_capacity

        self._activities.update(activity)
        return activity.to_dict(
            self._activities.count_approved(activity_id),
            self._activities.count_pending(activity_id),
            self._activities.count_waitlisted(activity_id),
        )

    def soft_delete(self, admin: Student, activity_id: str) -> dict:
        activity = self._activities.get(activity_id)
        if activity is None:
            raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")
        self._activities.soft_delete(activity_id, now_iso())
        return {"activity_id": activity_id, "deleted": True, "mode": "soft"}
