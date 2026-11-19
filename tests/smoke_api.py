"""API 冒烟/验收脚本（标准库 urllib，无第三方依赖）。

用法：
    python tests/smoke_api.py [base_url]

默认 base_url = http://127.0.0.1:8000
退出码：0 全部通过；1 有失败。
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
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
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


def expect_status(name: str, method: str, path: str, want: int, body=None, token=None):
    status, payload = call(method, path, body, token)
    check(f"{name} -> {want}", status == want, f"got {status} {payload}")
    return payload


def main() -> int:
    # ---------- 登录 ----------
    admin = expect_status("管理员登录", "POST", "/api/login", 200,
                          {"username": "admin", "password": "admin123"})
    s1 = expect_status("学生A登录", "POST", "/api/login", 200,
                       {"username": "s001", "password": "student123"})
    s2 = expect_status("学生B登录", "POST", "/api/login", 200,
                       {"username": "s002", "password": "student123"})
    s3 = expect_status("学生C登录", "POST", "/api/login", 200,
                       {"username": "s003", "password": "student123"})
    at, t1, t2, t3 = admin["token"], s1["token"], s2["token"], s3["token"]

    expect_status("错误口令被拒", "POST", "/api/login", 401,
                  {"username": "admin", "password": "wrong"})

    # ---------- C1 创建直接报名活动 ----------
    act = expect_status("C1 创建直接型活动", "POST", "/api/activities", 201,
                        {"title": "冒烟-羽毛球", "category": "体育",
                         "start_at": "2026-12-30T14:00:00", "location": "体育馆",
                         "capacity": 2, "policy_type": "DIRECT"}, at)
    aid = act["activity_id"]
    check("C1 剩余名额=2", act["remaining"] == 2, str(act))

    # ---------- C2 直接报名自动通过 ----------
    r1 = expect_status("C2 学生A报名直接型", "POST", f"/api/activities/{aid}/registrations", 201, {}, t1)
    check("C2 状态=APPROVED", r1.get("status") == "APPROVED", str(r1))
    msgs = expect_status("C2 学生A消息列表", "GET", "/api/messages", 200, None, t1)
    check("C2 收到 1 条通知", len(msgs["items"]) == 1, str(msgs))

    # ---------- C3 重复报名 ----------
    dup = expect_status("C3 重复报名被拒", "POST", f"/api/activities/{aid}/registrations", 409, {}, t1)
    check("C3 错误码=ALREADY_REGISTERED",
          (dup or {}).get("error", {}).get("code") == "ALREADY_REGISTERED", str(dup))

    # ---------- C4 名额上限 ----------
    expect_status("C4 学生B报名成功", "POST", f"/api/activities/{aid}/registrations", 201, {}, t2)
    full = expect_status("C4 学生C名额已满", "POST", f"/api/activities/{aid}/registrations", 409, {}, t3)
    check("C4 错误码=CAPACITY_FULL",
          (full or {}).get("error", {}).get("code") == "CAPACITY_FULL", str(full))
    stats = expect_status("C4 统计", "GET", f"/api/activities/{aid}/stats", 200)
    check("C4 已通过=2 剩余=0", (stats["approved"], stats["remaining"]) == (2, 0), str(stats))

    # ---------- C5 审核型报名 ----------
    rev = expect_status("C5 创建审核型活动", "POST", "/api/activities", 201,
                        {"title": "冒烟-编程马拉松", "category": "学术",
                         "start_at": "2026-12-31T09:00:00", "location": "A301",
                         "capacity": 2, "policy_type": "REVIEW"}, at)
    rid_act = rev["activity_id"]
    rp = expect_status("C5 学生A报名审核型", "POST", f"/api/activities/{rid_act}/registrations", 201, {}, t1)
    check("C5 状态=PENDING", rp.get("status") == "PENDING", str(rp))
    st = expect_status("C5 审核型统计", "GET", f"/api/activities/{rid_act}/stats", 200)
    check("C5 待审核=1 已通过=0 剩余=2",
          (st["pending"], st["approved"], st["remaining"]) == (1, 0, 2), str(st))

    # ---------- C6 批准 ----------
    ap = expect_status("C6 批准", "POST", f"/api/registrations/{rp['registration_id']}/approve", 200, {}, at)
    check("C6 状态=APPROVED", ap.get("status") == "APPROVED", str(ap))
    msgs1 = expect_status("C6 学生A消息", "GET", "/api/messages", 200, None, t1)
    check("C6 累计 3 条消息（报名通过 + 待审核 + 审核通过）", len(msgs1["items"]) == 3, str(msgs1))

    # ---------- C7 拒绝 ----------
    rp2 = expect_status("C7 学生B报名审核型", "POST", f"/api/activities/{rid_act}/registrations", 201, {}, t2)
    rj = expect_status("C7 拒绝", "POST", f"/api/registrations/{rp2['registration_id']}/reject", 200, {}, at)
    check("C7 状态=REJECTED", rj.get("status") == "REJECTED", str(rj))

    # ---------- C8 批准时名额已满 ----------
    rp3 = expect_status("C8 学生C报名（占满第 2 个）", "POST", f"/api/activities/{rid_act}/registrations", 201, {}, t3)
    expect_status("C8 批准学生C", "POST", f"/api/registrations/{rp3['registration_id']}/approve", 200, {}, at)
    rp4 = expect_status("C8 学生B再次申请（被拒后可重申）", "POST", f"/api/activities/{rid_act}/registrations", 201, {}, t2)
    over = expect_status("C8 满员后批准失败", "POST", f"/api/registrations/{rp4['registration_id']}/approve", 409, {}, at)
    check("C8 错误码=CAPACITY_FULL",
          (over or {}).get("error", {}).get("code") == "CAPACITY_FULL", str(over))
    st2 = expect_status("C8 统计", "GET", f"/api/activities/{rid_act}/stats", 200)
    check("C8 已通过=2 不超卖", st2["approved"] == 2, str(st2))

    # ---------- C9 取消 ----------
    cx = expect_status("C9 学生A取消已通过报名", "POST",
                       f"/api/registrations/{rp['registration_id']}/cancel", 200, {}, t1)
    check("C9 状态=CANCELLED", cx.get("status") == "CANCELLED", str(cx))
    st3 = expect_status("C9 统计", "GET", f"/api/activities/{rid_act}/stats", 200)
    check("C9 已通过=1 剩余=1", (st3["approved"], st3["remaining"]) == (1, 1), str(st3))

    # ---------- 边界 ----------
    expect_status("E1 活动已开始报名被拒", "POST", "/api/activities", 201,
                  {"title": "冒烟-已开始", "category": "其他", "start_at": "2020-01-01T00:00:00",
                   "location": "X", "capacity": 5, "policy_type": "DIRECT"}, at)
    started = call("POST", "/api/activities", {"title": "冒烟-已开始2", "category": "其他",
                                               "start_at": "2020-01-01T00:00:00", "location": "X",
                                               "capacity": 5, "policy_type": "DIRECT"}, at)
    started_id = started[1]["activity_id"]
    expect_status("E1 已开始活动不可报名", "POST", f"/api/activities/{started_id}/registrations", 409, {}, t1)

    expect_status("E3 非本人取消失败", "POST",
                  f"/api/registrations/{rp3['registration_id']}/cancel", 403, {}, t1)
    expect_status("E4 学生创建活动被拒", "POST", "/api/activities", 403,
                  {"title": "x", "category": "x", "start_at": "2026-12-01T00:00:00",
                   "location": "x", "capacity": 1, "policy_type": "DIRECT"}, t1)
    expect_status("E5 容量非法", "POST", "/api/activities", 400,
                  {"title": "x", "category": "x", "start_at": "2026-12-01T00:00:00",
                   "location": "x", "capacity": 0, "policy_type": "DIRECT"}, at)
    expect_status("E6 报名方式非法", "POST", "/api/activities", 400,
                  {"title": "x", "category": "x", "start_at": "2026-12-01T00:00:00",
                   "location": "x", "capacity": 1, "policy_type": "XX"}, at)
    pending = expect_status("E7 管理员待审核列表", "GET", "/api/registrations/pending", 200, None, at)
    check("E7 待审核列表可取", isinstance(pending.get("items"), list), str(pending))
    expect_status("E8 学生访问待审核列表被拒", "GET", "/api/registrations/pending", 403, None, t1)

    # ---------- 软删除 ----------
    expect_status("软删除活动", "DELETE", f"/api/activities/{aid}", 200, None, at)
    gone = expect_status("删除后详情 404", "GET", f"/api/activities/{aid}", 404)

    print(f"\n通过 {passed}，失败 {failed}")
    if failures:
        print("失败项：" + "；".join(failures))

    # 同时写一份 UTF-8 报告，便于贴进实验报告（控制台编码可能是 GBK）
    try:
        import os

        report = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_run.txt")
        with open(report, "w", encoding="utf-8") as fh:
            fh.write(f"base={BASE}\n")
            fh.write("\n".join(lines))
            fh.write(f"\n\n通过 {passed}，失败 {failed}\n")
        print(f"报告已写入：{report}")
    except OSError:
        pass

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
