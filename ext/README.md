# ext/ — CR-01 年级限定 / CR-02 模拟邮件（零侵入扩展）

本目录实现实验二教师隐藏变更单：**CR-01 年级限定报名** 与 **CR-02 模拟邮件通知**。

## 零修改声明

**`project/`、`frontend/src/`、`run.py` 下没有任何文件被修改。**

| 需求 | 实现方式 | 是否改原文件 |
|---|---|---|
| `Student.grade` | `ext/schema.py` 启动时 `ALTER TABLE students ADD COLUMN grade` | 否（改库不改代码） |
| 年级规则 | 新表 `ext_activity_grade_rules(activity_id, min_grade, max_grade)` | 否 |
| 报名拦截 | `ext/services.py` 继承 `RegistrationService`，仅覆写 `register()` 增加年级校验 | 否（新增类） |
| 活动数据带规则 | 继承 `ActivityService`，在返回值上补 `grade_rule` 字段 | 否（新增类） |
| 邮件通知 | `ext/email.py` 新增 `EmailNotifier` 订阅者，在 `run_ext.py` 里挂到原 `EventBus` | 否（新增订阅者） |
| 邮件记录 | 新表 `ext_emails(event_id UNIQUE, …)`，失败留痕、事件去重 | 否 |
| 新接口 | `ext/api.py` 用原 `route` 装饰器定义，导入时 `setattr` 注入原 web 模块命名空间，由 `collect_routes()` 自动收录 | 否（运行时注入） |
| 配置页面 | `ext/pages/grade.html`、`ext/pages/emails.html`，由新增路由提供 | 否（原 dist 不动） |
| 启动 | `run_ext.py` 复刻原装配步骤并替换为扩展服务 | 否（新增入口） |

## 为什么接口在 `/api/ext/…`

原 `project/web/server.py` 只把 `/api/` 前缀的请求交给路由，其余走静态资源（SPA 回退）。
为了不修改该判断，扩展接口必须挂在 `/api/ext/` 下；配置页地址为
`/api/ext/pages/grade.html`。

## 目录

```
ext/
├─ schema.py     建列/建表/种子年级（幂等）
├─ rules.py      规则仓储 + 学籍年级仓储
├─ services.py   GradeAwareRegistrationService / GradeAwareActivityService
├─ api.py        扩展路由 + 注入
├─ pages/
│  └─ grade.html 独立配置页（原生 JS，无需构建）
└─ README.md
run_ext.py       扩展版启动入口
tests/support_ext.py、tests/test_grade_rule.py、tests/smoke_ext.py
```

## 启动

```bat
tools\py.cmd run_ext.py --port 8000
```

原入口仍可用（`run.py`，无年级功能），两者共用同一个 SQLite 文件；
扩展表/列由 `run_ext.py` 启动时自动创建，幂等。

## 演示数据（学生年级）

| 账号 | 年级 | 用途 |
|---|---|---|
| s001 | 大一(1) | CR1-03 被拒 |
| s002 | 大二(2) | CR1-01 通过 |
| s003 | 大三(3) | CR1-02 通过 |
| s004 | 大四(4) | CR1-04 被拒 |
| s005 | 大二(2) | 候补/其他演示 |

年级可在配置页修改，或调用 `PUT /api/ext/grade/students/{id}`。

## 接口

### CR-01 年级规则

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/ext/grade/rules` | 活动列表 + 年级规则（管理员） |
| PUT | `/api/ext/grade/rules/{activity_id}` | 设置/更新规则 `{min_grade,max_grade}`，仅直接报名型 |
| DELETE | `/api/ext/grade/rules/{activity_id}` | 取消限定 |
| GET | `/api/ext/grade/students` | 学生年级列表（管理员） |
| PUT | `/api/ext/grade/students/{student_id}` | 修改学生年级 `{grade}` |
| GET | `/api/ext/grade/me` | 当前登录人的年级 |
| GET | `/api/ext/pages/grade.html` | 年级配置页（独立页面） |

### CR-02 模拟邮件

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/ext/emails?limit=50` | 最近的邮件记录 + 统计（管理员） |
| POST | `/api/ext/emails/fail-next` | 布置「下一次发送失败」，用于演示 CR2-03 |
| GET | `/api/ext/pages/emails.html` | 邮件记录页（独立页面） |

**邮件触发范围**：`APPROVED`（直接报名通过 / 审核通过 / 候补补位）与 `REJECTED`；
`PENDING`、`WAITLISTED`、`CANCELLED` 不发邮件（站内信仍照常）。

**语义保证**

- 去重：`ext_emails.event_id` 唯一索引 + `INSERT OR IGNORE`，同一事件重复投递只记一条；
- 失败：只把该行置为 `FAILED` 并记录错误，**不抛出、不回滚报名**；
- 站内信与邮件相互独立，任一方失败不影响另一方。

## 行为契约

1. 只有**配置了规则**的活动才校验年级；未配置的活动行为与原来完全一致。
2. 年级不符 → `409 GRADE_NOT_ALLOWED`，消息含「仅限大二、大三报名（你的年级：大一）」。
3. 年级未登记 → `409 GRADE_MISSING`。
4. 名额、活动开始时间、重复报名等公共规则仍由原 `RegistrationService` 执行（先年级后公共规则，均不通过则不落库）。
5. 审核型活动**不允许**配置年级规则（返回 400）；其原有流程不变。

## 测试

```bat
tools\py.cmd tests\run_tests.py                              :: 65 项单测（CR-01 12 项 + CR-02 6 项）
tools\py.cmd run_ext.py --port 8090 --db project\data\ext_smoke.db
tools\py.cmd tests\smoke_ext.py http://127.0.0.1:8090        :: 30 项 CR-01 扩展冒烟
tools\py.cmd tests\smoke_ext_email.py http://127.0.0.1:8090  :: 28 项 CR-02 邮件冒烟
tools\py.cmd tests\smoke_api.py http://127.0.0.1:8090        :: 88 项原有用例回归（CR1-05 / CR2-05）
```

## 已知限制

- `run_ext.py` 复刻了 `project/app.py` 的装配逻辑（约 30 行）。若原装配变更（新增服务/订阅者），需要同步 `run_ext.py`——这是「零修改」的代价。
- 扩展接口必须以 `/api/ext/` 开头（受原路由前缀判断约束）。
- 配置页复用主站的 `localStorage.ce_token`，需先在主站以管理员登录。
