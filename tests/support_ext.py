"""扩展测试环境：在 support.Env（原始服务）之上装配 CR-01 扩展服务。"""

from __future__ import annotations

from support import Env

from ext.email import EmailNotifier, EmailRepository, MockEmailSender
from ext.rules import GradeRuleRepository, StudentGradeRepository
from ext.schema import migrate_ext, seed_grades
from ext.services import GradeAwareActivityService, GradeAwareRegistrationService


class ExtEnv(Env):
    def __init__(self) -> None:
        super().__init__()
        migrate_ext(self.conn)
        seed_grades(self.conn)

        self.grades = GradeRuleRepository(self.conn)
        self.student_grades = StudentGradeRepository(self.conn)
        self.emails = EmailRepository(self.conn)
        self.email_sender = MockEmailSender()
        self.bus.subscribe(EmailNotifier(self.emails, self.email_sender))

        self.activities = GradeAwareActivityService(self.repos.activities, self.grades)
        self.registrations = GradeAwareRegistrationService(
            activities=self.repos.activities,
            registrations=self.repos.registrations,
            students=self.repos.students,
            policies=self.policies,
            bus=self.bus,
            rules=self.grades,
            student_grades=self.student_grades,
        )

    def set_rule(self, activity_id: str, min_grade: int = 2, max_grade: int = 3):
        return self.grades.upsert(activity_id, min_grade, max_grade)
