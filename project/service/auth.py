"""认证服务：演示账号登录、Bearer Token 校验。"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from ..config import TOKEN_TTL_HOURS
from ..domain.errors import ForbiddenError, UnauthorizedError
from ..domain.models import Role, Student
from ..repo.db import verify_password
from ..repo.ports import StudentRepository, TokenRepository


class AuthService:
    def __init__(self, students: StudentRepository, tokens: TokenRepository) -> None:
        self._students = students
        self._tokens = tokens

    def login(self, username: str, password: str) -> dict:
        if not username or not password:
            raise UnauthorizedError("用户名或密码为空")
        student = self._students.get(username)
        if student is None or not verify_password(password, student.password_hash):
            raise UnauthorizedError("用户名或密码错误")

        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now() + timedelta(hours=TOKEN_TTL_HOURS)).replace(microsecond=0).isoformat()
        self._tokens.issue(token=token, student_id=student.student_id, role=student.role.value, expires_at=expires_at)
        return {
            "token": token,
            "expires_at": expires_at,
            "user": student.to_public(),
        }

    def authenticate(self, token: str | None) -> Student:
        if not token:
            raise UnauthorizedError("缺少登录凭证")
        record = self._tokens.get(token)
        if record is None:
            raise UnauthorizedError("登录已失效，请重新登录")
        student_id, role, expires_at = record
        if datetime.fromisoformat(expires_at) <= datetime.now():
            self._tokens.revoke(token)
            raise UnauthorizedError("登录已过期，请重新登录")
        student = self._students.get(student_id)
        if student is None:
            raise UnauthorizedError("账号不存在")
        student.role = Role(role)
        return student

    @staticmethod
    def require_admin(student: Student) -> None:
        if student.role is not Role.ADMIN:
            raise ForbiddenError("需要管理员权限")
