# CampusEvent — 校园活动报名与管理系统（软件工程实验二）

> 基于设计模式的校园活动报名与管理系统。
> 初始版本（baseline-v1）支持「直接报名」与「管理员审核」两类活动，报名结果通过站内消息通知；
> 第二周按教师变更单实现变更版本（change-v2）。

## 1. 环境

本项目**不依赖任何第三方库**，只用 Python 标准库（`http.server` + `sqlite3` + `unittest`）。

| 项 | 值 |
|---|---|
| 解释器 | 便携版 Python 3.12.7（仓库外，位于 `..\tools\python312\python.exe`） |
| 数据库 | SQLite（单文件 `project/data/campusevent.db`） |
| Web | `http.server`（服务端渲染 HTML，无前端框架） |
| 测试 | `unittest` + HTTP 端到端脚本 |
| 端口 | 默认 8000（可用 `--port` 覆盖） |

启动（在仓库根目录）：

```bat
tools\py.cmd run.py --port 8000
```

或直接：

```bat
..\tools\python312\python.exe run.py --port 8000
```

首次启动会自动建库、建表并写入演示账号与示例活动。

**演示账号**

| 账号 | 口令 | 角色 |
|---|---|---|
| `admin` | `admin123` | 管理员 |
| `s001` / `s002` / `s003` / `s004` / `s005` | `student123` | 学生 |

**API 冒烟**

```bat
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin123\"}"
curl http://127.0.0.1:8000/api/activities
```

## 2. 目录结构

```
studytask2/
├─ project/            应用源代码与数据初始化脚本
│  ├─ app.py           入口：HTTP 服务、路由分发
│  ├─ domain/          领域对象：Activity / Student / Registration / Message
│  ├─ policy/          报名策略（Strategy）
│  ├─ notify/          通知（Observer / 事件分发）
│  ├─ service/         业务服务：RegistrationService 等
│  ├─ repo/            SQLite 持久化
│  └─ web/             页面模板与静态资源
├─ tests/              单元测试与端到端测试
├─ docs/               SRS、用例、UML 图、变更影响分析
├─ report/             实验报告（5~8 页）与可维护性对照数据
├─ AI_DEV_LOG.md       AI 协作日志（按对话轮次记录）
├─ requirements.txt    依赖说明（本项目为空依赖）
└─ README.md
```

## 3. 前端（Vue 3 + Vite）

```bat
cd frontend
npm install
npm run dev      :: http://localhost:5173 ，/api 代理到后端 8000
npm run build    :: 产出 frontend/dist，由后端同源托管
```

> 先启动后端（8000），再 `npm run dev`；生产形态下只需跑后端，访问 `http://127.0.0.1:8000/`。

页面：登录、活动列表（按名称筛选）、活动详情（报名）、我的报名（取消）、站内消息（已读）、管理端（创建活动 / 待审核审批 / 统计 / 下架）。

## 4. 功能范围（初始版本）

| 编号 | 模块 | 说明 |
|---|---|---|
| P2-F01 | 活动管理 | 管理员创建、编辑、删除活动；名称、类型、时间、地点、人数上限、报名方式 |
| P2-F02 | 活动查看 | 学生浏览活动列表与详情，可按名称筛选 |
| P2-F03 | 报名/取消 | 报名、取消；禁止同一活动出现重复有效报名 |
| P2-F04 | 报名策略 | 直接报名自动通过；审核型报名进入待审核 |
| P2-F05 | 审批操作 | 管理员批准/拒绝待审核申请，批准时再次检查名额 |
| P2-F06 | 状态管理 | 待审核 / 已通过 / 已拒绝 / 已取消，状态转换符合规则 |
| P2-F07 | 站内通知 | 报名与审核结果写入站内消息列表 |
| P2-F08 | 统计 | 按活动查看已通过数、待审核数、剩余名额 |

> **v1.1（CR-01）新增**：直接型活动满员后进入**候补队列**（活动级 `waitlist_capacity`，默认 0 表示不开放）；已通过者取消时，候补按位次自动补位并通知。详见 `docs/change-request.md` 与 `docs/change-impact.md`。

## 4. 设计要点（详见 docs/）

- **策略模式**：`RegistrationPolicy` 抽象「报名如何处理」，`DirectApprovalPolicy` 与 `ManualReviewPolicy` 为两种实现；名额检查作为公共规则留在 `RegistrationService`。
- **观察者/事件通知**：报名领域事件经 `EventBus` 分发给 `InboxNotifier` 等订阅者，通知失败只留痕、不回滚报名事务。
- **SOLID**：服务依赖抽象（策略接口、通知接口、仓储接口），而非具体实现。

## 5. 版本标签

| 标签 | 含义 |
|---|---|
| `baseline-v1` | 初始版本完成并通过 C1–C10 验收 |
| `change-v2` | 完成教师变更单并通过全量回归 |

## 6. 验收用例

见 `docs/test-cases.md`（C1–C10）与 `tests/`。
