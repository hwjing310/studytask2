"""领域事件与事件总线（观察者模式）。

约定：
- 事件在业务事务提交**之后**发布；
- 订阅者自行处理失败并留痕，不得向调用方抛异常（BR6）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Iterable

from ..domain.models import now_iso

log = logging.getLogger("campusevent.events")


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    event_type: str
    occurred_at: str = field(default_factory=now_iso)


@dataclass(frozen=True)
class RegistrationEvent(DomainEvent):
    """报名/审批状态变化事件。event_id 由「报名ID + 状态 + 版本」构成，便于幂等。"""

    registration_id: str = ""
    activity_id: str = ""
    student_id: str = ""
    status: str = ""
    activity_title: str = ""

    @staticmethod
    def build(
        *,
        registration_id: str,
        activity_id: str,
        student_id: str,
        status: str,
        activity_title: str,
        version: int = 1,
    ) -> "RegistrationEvent":
        return RegistrationEvent(
            event_id=f"{registration_id}:{status}:v{version}",
            event_type="registration.status_changed",
            registration_id=registration_id,
            activity_id=activity_id,
            student_id=student_id,
            status=status,
            activity_title=activity_title,
        )


class EventSubscriber(ABC):
    @abstractmethod
    def handle(self, event: DomainEvent) -> None:  # pragma: no cover - 抽象
        raise NotImplementedError


class EventBus:
    """最简单的进程内同步事件总线。"""

    def __init__(self) -> None:
        self._subscribers: list[EventSubscriber] = []

    def subscribe(self, subscriber: EventSubscriber) -> None:
        self._subscribers.append(subscriber)

    def subscribers(self) -> Iterable[EventSubscriber]:
        return tuple(self._subscribers)

    def publish(self, event: DomainEvent) -> None:
        for subscriber in list(self._subscribers):
            try:
                subscriber.handle(event)
            except Exception:  # noqa: BLE001 - 订阅者失败不得影响业务
                log.exception("subscriber failed: %s event=%s", type(subscriber).__name__, event.event_id)
