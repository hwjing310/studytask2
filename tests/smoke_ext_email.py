"""CR-02 邮件通知接口冒烟（需 run_ext.py 已启动）。"""

from __future__ import annotations

import json
import os
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
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
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
    s2 = expect("学生登录", "POST", "/api/login", 200,
                {"username": "s002", "password": "student123"})
    at, t2 = admin["token"], s2["token"]

    before = expect("邮件记录基线", "GET", "/api/ext/emails", 200, None, at)
    base_total = before["stats"]["total"]

    # CR2-01 直接报名通过 → 站内信 + 邮件
    act = expect("创建直接型活动", "POST", "/api/activities", 201,
                 {"title": "冒烟-邮件通知", "category": "测试",
                  "start_at": "2026-12-28T10:00:00", "location": "X",
                  "capacity": 5, "policy_type": "DIRECT"}, at)
    reg = expect("CR2-01 学生报名", "POST", f"/api/activities/{act['activity_id']}/registrations",
                 201, {}, t2)
    check("CR2-01 报名状态=APPROVED", reg.get("status") == "APPROVED", str(reg))

    mails = expect("CR2-01 邮件列表", "GET", "/api/ext/emails", 200, None, at)
    check("CR2-01 新增 1 封邮件", mails["stats"]["total"] == base_total + 1, str(mails["stats"]))
    latest = mails["items"][0]
    check("CR2-01 收件人=s002@campus.edu.cn", latest["to_addr"] == "s002@campus.edu.cn", str(latest))
    check("CR2-01 状态=SENT", latest["status"] == "SENT", str(latest))
    check("CR2-01 主题含已通过", "已通过" in latest["subject"], str(latest))

    msgs = expect("CR2-01 站内信仍在", "GET", "/api/messages", 200, None, t2)
    check("CR2-01 站内信含该活动",
          any(m["activity_id"] == act["activity_id"] for m in msgs["items"]), "no site message")

    # CR2-02 审核拒绝 → 邮件
    review = expect("创建审核型活动", "POST", "/api/activities", 201,
                    {"title": "冒烟-邮件-审核", "category": "测试",
                     "start_at": "2026-12-29T10:00:00", "location": "Y",
                     "capacity": 5, "policy_type": "REVIEW"}, at)
    rv = expect("CR2-02 学生报名审核型", "POST",
                f"/api/activities/{review['activity_id']}/registrations", 201, {}, t2)
    expect("CR2-02 管理员拒绝", "POST", f"/api/registrations/{rv['registration_id']}/reject",
           200, {}, at)
    mails2 = expect("CR2-02 邮件列表", "GET", "/api/ext/emails", 200, None, at)
    check("CR2-02 新增拒绝邮件",
          any("未通过" in m["subject"] and m["student_id"] == "s002" for m in mails2["items"]),
          str(mails2["items"][:2]))

    # CR2-03 模拟发送失败：报名仍成功、记录 FAILED
    expect("CR2-03 布置下一次失败", "POST", "/api/ext/emails/fail-next", 200, {}, at)
    act3 = expect("创建第三个活动", "POST", "/api/activities", 201,
                  {"title": "冒烟-邮件-失败", "category": "测试",
                   "start_at": "2026-12-30T10:00:00", "location": "Z",
                   "capacity": 5, "policy_type": "DIRECT"}, at)
    reg3 = expect("CR2-03 学生报名（应成功）", "POST",
                  f"/api/activities/{act3['activity_id']}/registrations", 201, {}, t2)
    check("CR2-03 报名状态=APPROVED", reg3.get("status") == "APPROVED", str(reg3))

    mails3 = expect("CR2-03 邮件列表", "GET", "/api/ext/emails", 200, None, at)
    check("CR2-03 有 1 封失败记录",
          any(m["status"] == "FAILED" for m in mails3["items"]), str(mails3["stats"]))
    stats = expect("CR2-03 活动统计", "GET", f"/api/activities/{act3['activity_id']}/stats", 200)
    check("CR2-03 报名未被回滚", stats["approved"] == 1, str(stats))

    # 学生无权查看邮件记录
    expect("学生访问邮件记录被拒", "GET", "/api/ext/emails", 403, None, t2)

    # 页面可访问
    try:
        with urllib.request.urlopen(BASE + "/api/ext/pages/emails.html", timeout=10) as resp:
            html = resp.read().decode("utf-8", "ignore")
            check("邮件记录页可访问", resp.status == 200 and "邮件通知记录" in html)
    except urllib.error.HTTPError as exc:
        check("邮件记录页可访问", False, f"got {exc.code}")

    emit(f"\n通过 {passed}，失败 {failed}")
    if failures:
        emit("失败项：" + "；".join(failures))

    try:
        report = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_ext_email.txt")
        with open(report, "w", encoding="utf-8") as fh:
            fh.write(f"base={BASE}\n" + "\n".join(lines) + f"\n\n通过 {passed}，失败 {failed}\n")
        emit(f"报告已写入：{report}")
    except OSError:
        pass
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
