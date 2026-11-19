"""HTTP 层：路由、鉴权、JSON 编解码、静态资源托管。

约束：本层只做协议转换与错误码映射，业务规则一律在 service 层。
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import parse_qs, unquote, urlparse

from ..config import DIST_DIR
from ..domain.errors import AppError, NotFoundError, UnauthorizedError
from ..domain.models import Student
from ..service.activity import ActivityService
from ..service.auth import AuthService
from ..service.message import MessageService
from ..service.registration import RegistrationService

log = logging.getLogger("campusevent.web")

MAX_BODY = 1 * 1024 * 1024  # 1MB


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    body: dict
    user: Optional[Student]
    request_id: str

    def param(self, key: str, default: str = "") -> str:
        values = self.query.get(key) or [default]
        return values[0]


@dataclass
class Response:
    status: int = 200
    payload: object = None
    raw: Optional[bytes] = None
    content_type: str = "application/json; charset=utf-8"
    headers: Optional[dict[str, str]] = None


class App:
    """组装好的应用依赖（由 app.py 创建后注入 server）。"""

    def __init__(
        self,
        auth: AuthService,
        activities: ActivityService,
        registrations: RegistrationService,
        messages: MessageService,
        db_path: str,
    ) -> None:
        self.auth = auth
        self.activities = activities
        self.registrations = registrations
        self.messages = messages
        self.db_path = db_path


Route = tuple[str, re.Pattern, Callable[[Request], Response]]


def route(method: str, pattern: str) -> Callable:
    compiled = re.compile(pattern)

    def decorator(func: Callable[[Request], Response]):
        func.__route__ = (method, compiled)  # type: ignore[attr-defined]
        return func

    return decorator


def json_body(data: object, status: int = 200, headers: Optional[dict] = None) -> Response:
    return Response(status=status, payload=data, headers=headers)


def collect_routes() -> list[Route]:
    """扫描本模块中带 @route 标记的函数（模块加载后调用一次即可）。"""
    routes: list[Route] = []
    for value in globals().values():
        meta = getattr(value, "__route__", None)
        if meta and callable(value):
            routes.append((meta[0], meta[1], value))
    return routes


# --------------------------------------------------------------------------- #
# 路由处理函数
# --------------------------------------------------------------------------- #
@route("GET", r"/api/health")
def health(req: Request) -> Response:
    app: App = req_app(req)
    size = os.path.getsize(app.db_path) if os.path.exists(app.db_path) else 0
    return json_body({"status": "ok", "db_size": size, "time": _now()})


@route("POST", r"/api/login")
def login(req: Request) -> Response:
    app: App = req_app(req)
    username = str(req.body.get("username") or "").strip()
    password = str(req.body.get("password") or "")
    return json_body(app.auth.login(username, password))


@route("GET", r"/api/activities")
def list_activities(req: Request) -> Response:
    app: App = req_app(req)
    return json_body({"items": app.activities.list(req.param("q"))})


@route("GET", r"/api/activities/(?P<activity_id>[^/]+)")
def get_activity(req: Request) -> Response:
    app: App = req_app(req)
    return json_body(app.activities.get(req.params["activity_id"]))


@route("GET", r"/api/activities/(?P<activity_id>[^/]+)/stats")
def activity_stats(req: Request) -> Response:
    app: App = req_app(req)
    return json_body(app.activities.stats(req.params["activity_id"]))


@route("POST", r"/api/activities")
def create_activity(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    app.auth.require_admin(user)
    return json_body(app.activities.create(user, req.body), status=201)


@route("PUT", r"/api/activities/(?P<activity_id>[^/]+)")
def update_activity(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    app.auth.require_admin(user)
    return json_body(app.activities.update(user, req.params["activity_id"], req.body))


@route("DELETE", r"/api/activities/(?P<activity_id>[^/]+)")
def delete_activity(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    app.auth.require_admin(user)
    return json_body(app.activities.soft_delete(user, req.params["activity_id"]))


# --------------------------------------------------------------------------- #
# 报名与审批
# --------------------------------------------------------------------------- #
@route("POST", r"/api/activities/(?P<activity_id>[^/]+)/registrations")
def create_registration(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    return json_body(app.registrations.register(user, req.params["activity_id"]), status=201)


@route("GET", r"/api/registrations/mine")
def my_registrations(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    return json_body({"items": app.registrations.list_mine(user)})


@route("GET", r"/api/registrations/pending")
def pending_registrations(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    app.auth.require_admin(user)
    activity_id = req.param("activity_id") or None
    return json_body({"items": app.registrations.list_pending(activity_id)})


@route("POST", r"/api/registrations/(?P<registration_id>[^/]+)/cancel")
def cancel_registration(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    return json_body(app.registrations.cancel(user, req.params["registration_id"]))


@route("POST", r"/api/registrations/(?P<registration_id>[^/]+)/approve")
def approve_registration(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    app.auth.require_admin(user)
    return json_body(app.registrations.approve(user, req.params["registration_id"]))


@route("POST", r"/api/registrations/(?P<registration_id>[^/]+)/reject")
def reject_registration(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    app.auth.require_admin(user)
    return json_body(app.registrations.reject(user, req.params["registration_id"]))


# --------------------------------------------------------------------------- #
# 站内消息
# --------------------------------------------------------------------------- #
@route("GET", r"/api/messages")
def list_messages(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    return json_body({"items": app.messages.list_mine(user)})


@route("GET", r"/api/messages/unread-count")
def unread_count(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    return json_body({"count": app.messages.unread_count(user)})


@route("POST", r"/api/messages/(?P<message_id>[^/]+)/read")
def read_message(req: Request) -> Response:
    app: App = req_app(req)
    user = require_user(req)
    return json_body(app.messages.mark_read(user, req.params["message_id"]))


# --------------------------------------------------------------------------- #
# 请求上下文工具
# --------------------------------------------------------------------------- #
_STORE: dict[str, App] = {}


def set_app(app: App) -> None:
    _STORE["app"] = app


def req_app(req: Request) -> App:  # 由 handler 在调用前注入
    return getattr(req, "_app")  # type: ignore[attr-defined]


def require_user(req: Request) -> Student:
    if req.user is None:
        raise UnauthorizedError("请先登录")
    return req.user


def _now() -> str:
    from ..domain.models import now_iso

    return now_iso()


# --------------------------------------------------------------------------- #
# HTTP Handler
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    server_version = "CampusEvent/1.0"

    # 静默默认日志，改用 logging
    def log_message(self, fmt: str, *args) -> None:  # noqa: D401
        log.info("%s - %s", self.address_string(), fmt % args)

    # ---- 分发 ----
    def _dispatch(self) -> None:
        request_id = uuid.uuid4().hex[:8]
        try:
            parsed = urlparse(self.path)
            body = self._read_json()
            req = Request(
                method=self.command,
                path=parsed.path,
                query=parse_qs(parsed.query),
                body=body,
                user=self._authenticate(),
                request_id=request_id,
            )
            setattr(req, "_app", self.server.app)  # type: ignore[attr-defined]

            if req.path.startswith("/api/"):
                response = self._handle_api(req)
            else:
                response = self._serve_static(req.path)

        except AppError as exc:
            response = Response(status=exc.status, payload=exc.to_dict())
            log.warning("[%s] %s %s -> %s %s", request_id, self.command, self.path, exc.status, exc.code)
        except Exception:  # noqa: BLE001
            log.exception("[%s] unhandled error on %s %s", request_id, self.command, self.path)
            response = Response(
                status=500,
                payload={"error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"}},
            )

        self._write(response)

    def _handle_api(self, req: Request) -> Response:
        allowed: set[str] = set()
        for method, pattern, func in self.server.routes:  # type: ignore[attr-defined]
            match = pattern.fullmatch(req.path)
            if not match:
                continue
            allowed.add(method)
            if method != req.method:
                continue
            setattr(req, "params", match.groupdict())
            response = func(req)
            if not isinstance(response, Response):
                response = json_body(response)
            return response
        if allowed:
            raise AppError("方法不允许", code="METHOD_NOT_ALLOWED", status=405)
        raise NotFoundError("接口不存在", code="API_NOT_FOUND")

    def _authenticate(self) -> Optional[Student]:
        header = self.headers.get("Authorization") or ""
        if not header.lower().startswith("bearer "):
            return None
        token = header[7:].strip()
        try:
            return self.server.app.auth.authenticate(token)  # type: ignore[attr-defined]
        except AppError:
            return None

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise AppError("请求体过大", code="PAYLOAD_TOO_LARGE", status=413)
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AppError("请求体不是合法 JSON", code="INVALID_JSON", status=400)
        if not isinstance(data, dict):
            raise AppError("请求体必须是 JSON 对象", code="INVALID_JSON", status=400)
        return data

    def _serve_static(self, path: str) -> Response:
        if not os.path.isdir(DIST_DIR):
            html = (
                "<!doctype html><meta charset='utf-8'>"
                "<h1>CampusEvent 后端已启动</h1>"
                "<p>前端尚未构建。开发时运行 <code>npm run dev</code>（frontend/），"
                "或执行 <code>npm run build</code> 生成 <code>frontend/dist</code> 后刷新。</p>"
                "<p>API 健康检查：<a href='/api/health'>/api/health</a></p>"
            ).encode("utf-8")
            return Response(status=200, raw=html, content_type="text/html; charset=utf-8")

        rel = unquote(path).lstrip("/")
        target = os.path.normpath(os.path.join(DIST_DIR, rel))
        if not target.startswith(os.path.abspath(DIST_DIR)):
            raise NotFoundError("文件不存在", code="STATIC_NOT_FOUND")
        if os.path.isdir(target):
            target = os.path.join(target, "index.html")
        if not os.path.exists(target):
            # SPA 回退
            target = os.path.join(DIST_DIR, "index.html")
            if not os.path.exists(target):
                raise NotFoundError("文件不存在", code="STATIC_NOT_FOUND")
        with open(target, "rb") as fh:
            data = fh.read()
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        return Response(status=200, raw=data, content_type=ctype)

    def _write(self, response: Response) -> None:
        body = response.raw
        if body is None:
            body = json.dumps(response.payload, ensure_ascii=False).encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        for key, value in (response.headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # ---- HTTP 方法 ----
    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch()

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._write(Response(status=204))


def build_server(app: App, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.app = app  # type: ignore[attr-defined]
    server.routes = collect_routes()  # type: ignore[attr-defined]
    return server
