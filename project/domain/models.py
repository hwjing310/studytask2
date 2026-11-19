"""领域层：实体、值对象、枚举。不依赖 Web、SQL、通知实现。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Role(str, Enum):
    STUDENT = "STUDENT"
    ADMIN = "ADMIN"


class PolicyType(str, Enum):
    DIRECT = "DIRECT"
    REVIEW = "REVIEW"


class RegistrationStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    @property
    def is_active(self) -> bool:
        """有效报名：占用「重复报名」名额，但不一定占用容量。"""
        return self in (RegistrationStatus.PENDING, RegistrationStatus.APPROVED)


def now_iso() -> str:
    """当前本地时间（秒精度），ISO-8601。"""
    return datetime.now().replace(microsecond=0).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass
class Student:
    student_id: str
    name: str
    role: Role = Role.STUDENT
    password_hash: str = ""

    def to_public(self) -> dict:
        return {"student_id": self.student_id, "name": self.name, "role": self.role.value}


@dataclass
class Activity:
    activity_id: str
    title: str
    category: str
    start_at: str
    location: str
    capacity: int
    policy_type: PolicyType
    created_at: str = field(default_factory=now_iso)
    deleted_at: Optional[str] = None

    # ---- 领域判定 ----
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def is_started(self, at: Optional[datetime] = None) -> bool:
        return parse_iso(self.start_at) <= (at or datetime.now())

    def is_open(self, at: Optional[datetime] = None) -> bool:
        """可报名：未删除且未开始。"""
        return (not self.is_deleted()) and (not self.is_started(at))

    def is_full(self, approved_count: int) -> bool:
        return approved_count >= self.capacity

    def to_dict(self, approved: int = 0, pending: int = 0) -> dict:
        remaining = max(self.capacity - approved, 0)
        return {
            "activity_id": self.activity_id,
            "title": self.title,
            "category": self.category,
            "start_at": self.start_at,
            "location": self.location,
            "capacity": self.capacity,
            "policy_type": self.policy_type.value,
            "created_at": self.created_at,
            "deleted_at": self.deleted_at,
            "approved": approved,
            "pending": pending,
            "remaining": remaining,
            "open": self.is_open() and not self.is_full(approved),
        }


@dataclass
class Registration:
    registration_id: str
    activity_id: str
    student_id: str
    status: RegistrationStatus
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def is_active(self) -> bool:
        return self.status.is_active

    def can_cancel(self) -> bool:
        return self.status in (RegistrationStatus.PENDING, RegistrationStatus.APPROVED)

    def to_dict(self) -> dict:
        return {
            "registration_id": self.registration_id,
            "activity_id": self.activity_id,
            "student_id": self.student_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Message:
    message_id: str
    student_id: str
    activity_id: str
    registration_id: str
    status: str
    content: str
    created_at: str = field(default_factory=now_iso)
    is_read: int = 0

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "student_id": self.student_id,
            "activity_id": self.activity_id,
            "registration_id": self.registration_id,
            "status": self.status,
            "content": self.content,
            "created_at": self.created_at,
            "is_read": bool(self.is_read),
        }


@dataclass
class ActivityStats:
    activity_id: str
    approved: int
    pending: int
    capacity: int

    @property
    def remaining(self) -> int:
        return max(self.capacity - self.approved, 0)

    def to_dict(self) -> dict:
        return {
            "activity_id": self.activity_id,
            "approved": self.approved,
            "pending": self.pending,
            "capacity": self.capacity,
            "remaining": self.remaining,
        }
