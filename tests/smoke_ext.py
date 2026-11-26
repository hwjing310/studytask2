"""CR-01 扩展接口冒烟测试（需先启动 run_ext.py）。

用法：
    python tests/smoke_ext.py [base_url]
默认 http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")

passed = 0
failed = 0
failures: list[str] = []
lines: list[str] = []


def emit(text: str) -> None:
    print(text)
    lines.append(text)


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    url = BASE + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        emit(f"PASS  {name}")
    else:
        failed += 1
        failures.append(name)
        emit(f"FAIL  {name}  {detail}")


def expect(name: str, method: str, path: str, want: int, body=None, token=None):
    status, payload = call(method, path, body, token)
    check(f"{name} -> {want}", status == want, f"got {status} {payload}")
    return payload


def main() -> int:
    admin = expect("管理员登录", "POST", "/api/login", 200,
                   {"username": "admin", "password": "admin123"})
    s1 = expect("大一学生登录", "POST", "/api/login", 200,
                {"username": "s001", "password": "student123"})
    s2 = expect("大二学生登录", "POST", "/api/login", 200,
                {"username": "s002", "password": "student123"})
    s4 = expect("大四学生登录", "POST", "/api/login", 200,
                {"username": "s004", "password": "student123"})
    at, t1, t2, t4 = admin["token"], s1["token"], s2["token"], s4["token"]

    # 重置基线（脚本可重复执行）：s001 回到大一、s004 回到大四
    expect("重置 s001 年级=大一", "PUT", "/api/ext/grade/students/s001", 200, {"grade": 1}, at)
    expect("重置 s004 年级=大四", "PUT", "/api/ext/grade/students/s004", 200, {"grade": 4}, at)

    # 新建一个直接报名活动
    act = expect("创建直接型活动", "POST", "/api/activities", 201,
                 {"title": "冒烟-年级限定", "category": "测试",
                  "start_at": "2026-12-29T10:00:00", "location": "X",
                  "capacity": 5, "policy_type": "DIRECT"}, at)
    aid = act["activity_id"]

    # 配置规则：仅大二、大三
    rule = expect("CR1 设置年级规则", "PUT", f"/api/ext/grade/rules/{aid}", 200,
                  {"min_grade": 2, "max_grade": 3}, at)
    check("CR1 规则标签=大二、大三", rule.get("label") == "大二、大三", str(rule))

    # 活动列表带上 grade_rule
    acts = expect("活动列表", "GET", "/api/activities", 200)
    item = next(a for a in acts["items"] if a["activity_id"] == aid)
    check("CR1 列表含 grade_rule", item.get("grade_rule") is not None, str(item))

    # CR1-03/04：大一、大四被拒且提示原因
    denied1 = expect("CR1-03 大一报名被拒", "POST", f"/api/activities/{aid}/registrations", 409, {}, t1)
    check("CR1-03 错误码=GRADE_NOT_ALLOWED",
          (denied1 or {}).get("error", {}).get("code") == "GRADE_NOT_ALLOWED", str(denied1))
    check("CR1-03 提示含年级",
          "大一" in (denied1 or {}).get("error", {}).get("message", ""), str(denied1))
    expect("CR1-04 大四报名被拒", "POST", f"/api/activities/{aid}/registrations", 409, {}, t4)

    # CR1-01：大二通过
    r2 = expect("CR1-01 大二报名通过", "POST", f"/api/activities/{aid}/registrations", 201, {}, t2)
    check("CR1-01 状态=APPROVED", r2.get("status") == "APPROVED", str(r2))

    # 学生年级列表与权限
    students = expect("管理员查看学生年级", "GET", "/api/ext/grade/students", 200, None, at)
    s002_row = next(s for s in students["items"] if s["student_id"] == "s002")
    check("年级=2（大二）", s002_row["grade"] == 2, str(s002_row))
    expect("学生无权查看年级表", "GET", "/api/ext/grade/students", 403, None, t1)

    # 改年级后放开：把 s001 改为大二，再报名另一个活动
    expect("修改 s001 年级", "PUT", "/api/ext/grade/students/s001", 200, {"grade": 2}, at)
    act2 = expect("再建活动", "POST", "/api/activities", 201,
                  {"title": "冒烟-年级限定2", "category": "测试",
                   "start_at": "2026-12-30T10:00:00", "location": "Y",
                   "capacity": 5, "policy_type": "DIRECT"}, at)
    expect("设置规则2", "PUT", f"/api/ext/grade/rules/{act2['activity_id']}", 200,
           {"min_grade": 2, "max_grade": 3}, at)
    r1 = expect("改年级后可报名", "POST", f"/api/activities/{act2['activity_id']}/registrations", 201, {}, t1)
    check("改年级后状态=APPROVED", r1.get("status") == "APPROVED", str(r1))

    # 审核型活动不允许配置年级规则
    review = expect("创建审核型活动", "POST", "/api/activities", 201,
                    {"title": "冒烟-审核型", "category": "测试",
                     "start_at": "2026-12-31T10:00:00", "location": "Z",
                     "capacity": 5, "policy_type": "REVIEW"}, at)
    expect("审核型不可设年级规则", "PUT", f"/api/ext/grade/rules/{review['activity_id']}", 400,
           {"min_grade": 2, "max_grade": 3}, at)

    # 取消规则后无限制
    expect("取消规则", "DELETE", f"/api/ext/grade/rules/{aid}", 200, None, at)
    expect("取消后大四可报名", "POST", f"/api/activities/{aid}/registrations", 201, {}, t4)

    # 独立配置页可访问（HTML，不按 JSON 解析）
    try:
        with urllib.request.urlopen(BASE + "/api/ext/pages/grade.html", timeout=10) as resp:
            html = resp.read().decode("utf-8", "ignore")
            check("配置页 /api/ext/pages/grade.html 可访问",
                  resp.status == 200 and "年级限定" in html, f"status={resp.status}")
    except urllib.error.HTTPError as exc:
        check("配置页可访问", False, f"got {exc.code}")

    emit(f"\n通过 {passed}，失败 {failed}")
    if failures:
        emit("失败项：" + "；".join(failures))

    try:
        import os

        report = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_ext_run.txt")
        with open(report, "w", encoding="utf-8") as fh:
            fh.write(f"base={BASE}\n" + "\n".join(lines) + f"\n\n通过 {passed}，失败 {failed}\n")
        emit(f"报告已写入：{report}")
    except OSError:
        pass
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
