"""扩展路由：年级规则配置、学生年级维护、独立配置页。

不修改原 web 层：这里用原 `route` 装饰器定义处理函数，
再在导入时把函数注入 `project.web.server` 模块命名空间，
原 `collect_routes()` 扫描时会自动纳入。
"""

from __future__ import annotations

import os
import uuid

from project.domain.errors import NotFoundError, ValidationError
from project.web.server import Response, json_body, req_app, require_user, route

from .schema import grade_label

EXT_DIR = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(EXT_DIR, "pages")


def _admin(req):
    user = require_user(req)
    req_app(req).auth.require_admin(user)
    return user


def _parse_grade(value, field: str = "grade") -> int:
    try:
        grade = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} 必须是 1~4 的整数")
    if grade < 1 or grade > 4:
        raise ValidationError(f"{field} 必须是 1~4 的整数")
    return grade


@route("GET", r"/api/ext/grade/rules")
def ext_list_rules(req) -> Response:
    _admin(req)
    app = req_app(req)
    items = []
    for activity in app.activities.list(""):
        items.append(
            {
                "activity_id": activity["activity_id"],
                "title": activity["title"],
                "policy_type": activity["policy_type"],
                "capacity": activity["capacity"],
                "grade_rule": activity.get("grade_rule"),
            }
        )
    return json_body({"items": items})


@route("PUT", r"/api/ext/grade/rules/(?P<activity_id>[^/]+)")
def ext_set_rule(req) -> Response:
    _admin(req)
    app = req_app(req)
    activity_id = req.params["activity_id"]

    try:
        activity = app.activities.get(activity_id)
    except NotFoundError:
        raise NotFoundError("活动不存在或已下架", code="ACTIVITY_NOT_FOUND")
    if activity["policy_type"] != "DIRECT":
        raise ValidationError("年级限定仅适用于「直接报名」型活动")

    min_grade = _parse_grade(req.body.get("min_grade"), "最小年级")
    max_grade = _parse_grade(req.body.get("max_grade"), "最大年级")
    if min_grade > max_grade:
        raise ValidationError("最小年级不能大于最大年级")

    rule = app.grades.upsert(activity_id, min_grade, max_grade)
    return json_body(rule.to_dict())


@route("DELETE", r"/api/ext/grade/rules/(?P<activity_id>[^/]+)")
def ext_delete_rule(req) -> Response:
    _admin(req)
    app = req_app(req)
    deleted = app.grades.delete(req.params["activity_id"])
    return json_body({"activity_id": req.params["activity_id"], "deleted": deleted})


@route("GET", r"/api/ext/grade/students")
def ext_list_students(req) -> Response:
    _admin(req)
    app = req_app(req)
    return json_body({"items": app.student_grades.list_students()})


@route("PUT", r"/api/ext/grade/students/(?P<student_id>[^/]+)")
def ext_set_student_grade(req) -> Response:
    _admin(req)
    app = req_app(req)
    student_id = req.params["student_id"]
    grade = _parse_grade(req.body.get("grade"))
    if not app.student_grades.set_grade(student_id, grade):
        raise NotFoundError("学生不存在", code="STUDENT_NOT_FOUND")
    return json_body(
        {"student_id": student_id, "grade": grade, "grade_label": grade_label(grade)}
    )


@route("GET", r"/api/ext/grade/me")
def ext_my_grade(req) -> Response:
    user = require_user(req)
    app = req_app(req)
    grade = app.student_grades.get_grade(user.student_id)
    return json_body(
        {
            "student_id": user.student_id,
            "name": user.name,
            "grade": grade,
            "grade_label": grade_label(grade),
        }
    )


@route("GET", r"/api/ext/emails")
def ext_list_emails(req) -> Response:
    _admin(req)
    app = req_app(req)
    try:
        limit = int(req.param("limit") or 50)
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 200))
    return json_body(
        {
            "items": [e.to_dict() for e in app.emails.list_recent(limit)],
            "stats": app.emails.stats(),
            "armed_failure": app.email_sender.failing,
        }
    )


@route("POST", r"/api/ext/emails/fail-next")
def ext_arm_email_failure(req) -> Response:
    _admin(req)
    app = req_app(req)
    app.email_sender.arm_failure()
    return json_body({"armed": True, "message": "下一次邮件发送将模拟失败（用于演示 CR2-03）"})


@route("POST", r"/api/ext/emails/fail-cancel")
def ext_cancel_email_failure(req) -> Response:
    _admin(req)
    app = req_app(req)
    app.email_sender.disarm()
    return json_body({"armed": False, "message": "已取消模拟失败"})


@route("POST", r"/api/ext/emails/test-send")
def ext_test_email(req) -> Response:
    """发一封测试邮件，便于不依赖报名流程验证邮件链路。"""
    _admin(req)
    app = req_app(req)
    event_id = "test:" + uuid.uuid4().hex[:12]
    row_id = app.emails.begin(
        event_id=event_id,
        registration_id="-",
        student_id=req.user.student_id,
        to_addr=f"{req.user.student_id}@campus.edu.cn",
        subject="测试邮件：模拟发送",
        body="这是一封由邮件记录页触发的测试邮件，用于验证 MockEmailSender 链路。",
    )
    try:
        app.email_sender.send(f"{req.user.student_id}@campus.edu.cn", "测试邮件：模拟发送", "test")
    except Exception as exc:  # noqa: BLE001
        app.emails.mark_failed(row_id, str(exc))
        return json_body({"status": "FAILED", "error": str(exc), "event_id": event_id})
    app.emails.mark_sent(row_id)
    return json_body({"status": "SENT", "event_id": event_id})


@route("GET", r"/api/ext/pages/(?P<name>[A-Za-z0-9_\-]+\.html)")
def ext_page(req) -> Response:
    """独立页面（原前端 dist 不变），只允许读取 ext/pages 下的 html。"""
    name = req.params["name"]
    path = os.path.normpath(os.path.join(PAGES_DIR, name))
    if not path.startswith(os.path.abspath(PAGES_DIR)) or not os.path.isfile(path):
        raise NotFoundError("页面不存在", code="PAGE_NOT_FOUND")
    with open(path, "rb") as fh:
        data = fh.read()
    return Response(status=200, raw=data, content_type="text/html; charset=utf-8")


# ---- 注入原 web 模块命名空间，供 collect_routes() 扫描 ----
import project.web.server as _server_module  # noqa: E402

for _fn in (
    ext_list_rules,
    ext_set_rule,
    ext_delete_rule,
    ext_list_students,
    ext_set_student_grade,
    ext_my_grade,
    ext_list_emails,
    ext_arm_email_failure,
    ext_cancel_email_failure,
    ext_test_email,
    ext_page,
):
    setattr(_server_module, f"_ext_route_{_fn.__name__}", _fn)
