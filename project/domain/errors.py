"""业务异常：由服务层抛出，由 Web 层统一映射为 HTTP 错误码。"""

from __future__ import annotations


class AppError(Exception):
    """带业务错误码的异常基类。"""

    status = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status:
            self.status = status

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


class ValidationError(AppError):
    status = 400
    code = "VALIDATION_ERROR"


class UnauthorizedError(AppError):
    status = 401
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status = 409
    code = "CONFLICT"
