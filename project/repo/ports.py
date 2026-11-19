"""仓储接口（端口）。服务层只依赖这些抽象，由 app.py 注入 SQLite 实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..domain.models import Activity, Message, Registration, RegistrationStatus, Student


class ActivityRepository(ABC):
    @abstractmethod
    def add(self, activity: Activity) -> None: ...

    @abstractmethod
    def update(self, activity: Activity) -> None: ...

    @abstractmethod
    def soft_delete(self, activity_id: str, deleted_at: str) -> None: ...

    @abstractmethod
    def get(self, activity_id: str, *, include_deleted: bool = False) -> Optional[Activity]: ...

    @abstractmethod
    def list_active(self, query: str = "") -> list[Activity]: ...

    @abstractmethod
    def count_approved(self, activity_id: str) -> int: ...

    @abstractmethod
    def count_pending(self, activity_id: str) -> int: ...


class RegistrationRepository(ABC):
    @abstractmethod
    def add(self, registration: Registration) -> None: ...

    @abstractmethod
    def update(self, registration: Registration) -> None: ...

    @abstractmethod
    def get(self, registration_id: str) -> Optional[Registration]: ...

    @abstractmethod
    def find_active(self, activity_id: str, student_id: str) -> Optional[Registration]: ...

    @abstractmethod
    def list_by_student(self, student_id: str) -> list[Registration]: ...

    @abstractmethod
    def list_by_activity_status(
        self, activity_id: str, status: RegistrationStatus
    ) -> list[Registration]: ...

    @abstractmethod
    def list_pending(self, activity_id: str | None = None) -> list[Registration]: ...


class StudentRepository(ABC):
    @abstractmethod
    def get(self, student_id: str) -> Optional[Student]: ...

    @abstractmethod
    def find_by_name(self, name: str) -> Optional[Student]: ...


class MessageRepository(ABC):
    @abstractmethod
    def add(self, message: Message) -> bool:
        """写入消息；若 (registration_id, status) 已存在则忽略并返回 False。"""

    @abstractmethod
    def list_by_student(self, student_id: str) -> list[Message]: ...

    @abstractmethod
    def mark_read(self, student_id: str, message_id: str) -> bool: ...


class NotifyFailureRepository(ABC):
    @abstractmethod
    def add(self, *, event_id: str, payload: str, error: str) -> None: ...

    @abstractmethod
    def count(self) -> int: ...


class TokenRepository(ABC):
    @abstractmethod
    def issue(self, *, token: str, student_id: str, role: str, expires_at: str) -> None: ...

    @abstractmethod
    def get(self, token: str) -> Optional[tuple[str, str, str]]:
        """返回 (student_id, role, expires_at)，不存在返回 None。"""

    @abstractmethod
    def revoke(self, token: str) -> None: ...
