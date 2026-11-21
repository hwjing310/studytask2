# AI_DEV_LOG — AI 协作日志

> 用途：记录关键 AI 协作过程，供实验报告与答辩使用。
> 规则：每次关键交互记一条，写清「我提出的意图 / AI 给出的方案 / 我的判断与取舍」。
> 署名：周静文　242806010206　24计科2班

## 记录格式

```
### YYYY-MM-DD HH:MM · <阶段>
- 我的意图：
- AI 输出摘要：
- 我的判断（采纳 / 修改 / 拒绝）及理由：
- 影响的文件：
- 对应 Git 提交：
```

---

## 阶段 0：环境与骨架

### 2026-11-14 · 环境搭建
- 我的意图：在不安装第三方依赖的前提下搭好可运行环境。
- AI 输出摘要：探测本机 JDK/Python/Node 情况，发现原 Python 安装已失效；改用便携版 Python 3.12.7（华为云镜像），确认 `sqlite3` 3.45.3、`http.server`、`unittest` 可用。
- 我的判断：采纳。理由是零依赖、可随项目迁移、与指导书 `requirements.txt`/`pytest` 风格一致。
- 影响的文件：`README.md`、`requirements.txt`、`.gitignore`、`tools/py.cmd`
- 对应 Git 提交：（待提交）

---

## 阶段 1：需求分析

### 2026-11-14 · SRS 与用例
- 我的意图：把指导书 3.2 与附录B 的条款转成可设计、可测试的基线文档。
- AI 输出摘要：产出 `docs/srs.md`（范围/角色/技术约束/P2-F01~F08/BR1~BR7/数据/非功能/状态机/API 约定）、`docs/use-cases.md`（14 个用例 + 3 个详细用例）、`docs/test-cases.md`（C1–C10 + E1–E10）。
- 我的判断：采纳。补充了指导书未写明但会影响实现的三处取舍声明：软删除（BR7）、通知失败不回滚（BR6）、名额检查归公共规则而非策略。
- 影响的文件：`docs/srs.md`、`docs/use-cases.md`、`docs/test-cases.md`
- 对应 Git 提交：（待提交）

---

## 阶段 2：UML 设计

### 2026-11-14 · 类图与时序图
- 我的意图：按指导书要求给出可评审的静态结构与两张以上交互图，并留下「设计先行」的证据链。
- AI 输出摘要：Mermaid 绘图后用本机 draw.io CLI 转成 `.drawio` 双份交付——`class-diagram`（领域 + 分层全图，约 30 个类）、`seq-register-direct`、`seq-register-review`、`seq-approve`；另写 `design-principles.md`（SRP/OCP/LSP/ISP/DIP 逐条落位、任务B 名额归属论证、任务C 通知事务边界与幂等、任务D 评审清单）。
- 我的判断：采纳。类图选择「全分层」而非只画领域，理由是评分项明确看「职责划分与依赖方向」，分层图能直接证明 DIP；时序图多给一张审核型报名，用来证明「同一入口、不同策略」。
- 影响的文件：`docs/uml/*`（8 个文件）、`docs/design-principles.md`
- 对应 Git 提交：（待提交）

---

## 阶段 3：设计决策

### 2026-11-19 · 设计模式决策报告
- 我的意图：在让 AI 写代码之前，把六个关键设计点的取舍、代价与失效信号写成可评审的文档。
- AI 输出摘要：`docs/design-decisions.md`——D1 策略（对比 if-else/状态/模板方法）、D2 观察者（对比直调/消息队列/触发器）、D3 Repository、D4 名额归属、D5 软删除、D6 Vue3+Vite；另含被否决方案汇总、可维护性指标口径（第2周填）、5 条设计风险与「候补队列」变更演练预案。
- 我的判断：采纳。特意保留「失效信号」与「假设被推翻会怎样」，用来在第 2 周区分「设计缺陷」与「需求变化」，而不是事后找理由。
- 影响的文件：`docs/design-decisions.md`
- 对应 Git 提交：（待提交）

---

## 阶段 4：后端骨架与数据层

### 2026-11-19 · 分层骨架 + SQLite + 三个可用接口
- 我的意图：先让后端独立可跑、可验证，再上前端；避免「前后端同时半成品」。
- AI 输出摘要：完成 20 个 Python 文件（约 1300 行）——`domain`（实体/枚举/异常）、`policy`（策略接口 + 两实现 + 工厂）、`notify`（事件 + 总线 + 站内信订阅者）、`repo`（端口 + SQLite 实现，6 张表 + 有效报名部分唯一索引）、`service`（认证、活动）、`web`（路由/鉴权/错误映射/静态托管）、`app.py` + `run.py`；种子数据为 4 个账号 + 2 个示例活动。
- 我的判断：采纳。接口只放出 health/login/activities 三组，报名与审批留到第 6 步，避免未验证的死代码。
- 实测结果：`/api/health` 200；`admin` 登录 200；活动列表 2 条且中文正常；创建活动 201；无 token 401；学生创建 403；不存在活动 404；软删除后列表不再返回。
- 踩坑记录：便携版 Python 的 `python312._pth` 不含工作目录，`-m project.app` 找不到包 → 在 `._pth` 里加入仓库根，并补了 `run.py` 入口。另：清理测试数据时 `LIKE 'a_%'` 的下划线是通配符，误删了 a001/a002 种子行，已用重 seed 脚本恢复（数据无损失，仅为演示数据）。
- 影响的文件：`project/**`（20 个 .py）、`run.py`、`README.md`、`tools/python312/python312._pth`
- 对应 Git 提交：（待提交）

---

## 阶段 5：前端与端到端打通

### 2026-11-19 · 报名/审批接口 + Vue3 全页面
- 我的意图：让学生端页面都有真实数据，而不是空壳；同时验证「开发代理」与「生产托管」两种形态。
- AI 输出摘要：
  - 后端补 `RegistrationService`（报名/取消/审批，名额检查留在服务层）、`MessageService`，新增 8 个接口；
  - 前端 Vite+Vue3（JS）7 个页面 + 2 个基础模块（api/store），无 vue-router（用 `state.view` 切页，减少依赖）；
  - `tests/smoke_api.py`：50+ 断言，覆盖 C1–C9、E1/E3–E8 与软删除。
- 我的判断：采纳。放弃 vue-router 是权衡：本项目只有 6 个视图、无深链接需求，用状态切页可少一个依赖与一套 history 配置。
- 实测：冒烟 **52/52 通过**；`GET /` 返回构建后的 index.html，静态资源 200；`vite dev` 下 `/api` 代理正常且中文无乱码。
- 踩坑记录：
  1) `%TEMP%` 目录不允许创建新文件/子目录（sqlite 报 `unable to open database file`），改用仓库内 `project/data/*.db`；
  2) Vite 8 只监听 `localhost`（IPv6），用 `127.0.0.1:5180` 连不上，需用 `localhost`；
  3) 冒烟脚本把结果写 `tests/last_run.txt`（UTF-8），因为 PowerShell 控制台是 GBK，直接看会乱码。
- 影响的文件：`project/service/{registration,message}.py`、`project/web/server.py`、`project/app.py`、`frontend/**`、`tests/smoke_api.py`
- 对应 Git 提交：（待提交）

---

## 阶段 6：测试与基线

### 2026-11-19 · 单测 33 项 + C10 重启 + baseline-v1
- 我的意图：把「关键规则」钉死在自动化测试里，再用 Git 标签把验收状态固定下来，供第 2 周对比。
- AI 输出摘要：
  - `tests/test_policy.py`（策略契约与工厂）、`test_registration_service.py`（名额/重复/状态机/权限/幂等 13 例）、`test_notify.py`（失败留痕与去重）、`test_activity_service.py`（参数校验与容量下调保护）、`test_restart.py`（C10：真启停子进程比对快照）；
  - `tests/run_tests.py` 统一入口，报告写 `tests/last_unit.txt`（UTF-8）。
- 我的判断：采纳「关键规则」而非全量覆盖：33 个用例已覆盖全部评分点相关分支，继续堆覆盖率对 2 周工期性价比低。
- 实测：**33/33 通过**（15.8s），其中 C10 用例真实终止并重启进程后统计/消息/报名记录完全一致。
- 修正记录：策略工厂原来不接受小写 `direct`（`PolicyType('direct')` 抛错），改为 `strip().upper()`；测试里「容量下调」用例原本传 0（先命中了正整数校验），改为「已通过 2 人、下调到 1」才真正命中 `CAPACITY_BELOW_APPROVED`。
- 基线：`git init` + 首次提交（72 个文件，0.17 MB）+ 标签 `baseline-v1`（含 52 项冒烟、33 项单测结果）。
- 影响的文件：`tests/**`、`project/policy/base.py`、`tests/last_unit.txt`、`.gitignore`
- 对应 Git 提交：`baseline-v1`

---

## 阶段 7：变更单与影响分析

### 2026-11-19 · CR-01 候补队列
- 我的意图：在动手改代码之前，先把「教师会怎么提变更、我要改哪些地方、为什么这样改」写成可评审的材料。
- AI 输出摘要：`docs/change-request.md`（正式变更单：背景、6 条规则、接口兼容约定、CR-AC1–AC6 验收标准、约束与交付物清单）；`docs/change-impact.md`（受影响模块表、候补逻辑归属的三方案对比、预计差异行数、5 条风险与应对、测试计划、待回填指标）。
- 我的判断：采纳。影响分析里明确写了「预计修改的核心业务类 = 2」，把它当作对 D4 的可证伪预测——若实际超过 2，说明当初「名额规则集中」的判断有误，报告里要如实写。
- 影响的关键决策：候补**不做成策略**（否决方案 A），而是容量规则在服务层的延伸（方案 B）；理由是「活动类型」与「满员后怎么办」是两个维度。
- 影响的文件：`docs/change-request.md`、`docs/change-impact.md`
- 对应 Git 提交：（随 change-v2 一起提交）

---

## 阶段 8：实现 change-v2

### 2026-11-19 · CR-01 候补队列落地
- 我的意图：在 `change/cr-01` 分支上按影响分析实现，不重建项目、不引入依赖，并保留可对比的 Git 差异。
- AI 输出摘要：
  - 迁移：`activities.waitlist_capacity`、`registrations.waitlist_position`；因 SQLite 不能改 CHECK，用事务重建 `registrations` 表并保留数据（在真实旧库上验证通过）；
  - 领域/服务：满员转候补、候补上限、取消已通过后按序补位（含 `registration.promoted` 事件）、统计加 `waitlisted`；
  - 前端：候补状态与位次、取消候补、管理端候补上限与统计；
  - 测试：`test_waitlist.py` 8 例、冒烟新增 18 条断言；全量 41 单测 + 70 冒烟全部通过。
- 我的判断：采纳。策略层与 Web 层零改动，符合影响分析的预测。
- 返工（记录下来，写进报告）：
  1) `find_active` 未包含 `WAITLISTED`，导致重复报名落到数据库唯一索引异常，而非 409；
  2) 详情页按钮用 `open` 判断，满员时被禁用，改为 `open || hasWaitlist`。
- 指标：新增类 0；核心业务文件 3；总改动 32 文件（代码 +492/−35，生产代码 +269/−30）；回归失败 0。
- 影响的文件：`project/**`、`frontend/src/**`、`tests/**`、`docs/{srs,change-impact}.md`、`docs/uml/{class-diagram,state-registration}.*`
- 对应 Git 提交：`change-v2`

---

## 阶段 9：可发现性改进（部署后）

### 2026-11-19 · 活动详情页回显「我的报名状态」
- 背景：答辩预演时发现，状态只在「我的报名」页可见，详情页报名后仅弹提示，容易被误认为「状态没有变化」。
- 改动：详情页加载时并行拉取 `/registrations/mine` 并按 `activity_id` 过滤，命中则显示状态徽章与候补位次；有效报名隐藏「报名」按钮、显示「取消报名/取消候补」，终态显示「可重新报名」。
- 验证：重新构建（87 KB JS）→ 打包 → 上传覆盖 `frontend/dist` → 公网 `index.html` 已指向新 bundle，且 bundle 内含「我的报名状态」「取消候补」字样。
- 影响文件：`frontend/src/views/ActivityDetailView.vue`、`report/项目总结.md`
- 对应 Git 提交：`change-v2`（随最终提交）

### 2026-11-19 · 演示账号扩到 5 个学生
- 需求：答辩时多人同时演示，学生账号不够。
- 改动：`DEMO_STUDENTS` 增加 `s004 赵同学`、`s005 钱同学`；`seed()` 改为**幂等补种**（`INSERT OR IGNORE` 学生账号，示例活动仅在空库写入），这样已部署的实例升级后也能补上新账号，不必删库。
- 验证：重新打包上传并重启后，公网 `s001`–`s005` 全部可登录（姓名与角色正确）。
- 影响文件：`project/repo/db.py`、`README.md`、`report/项目总结.md`

### 2026-11-21 · 示例活动扩到 6 个 + 登录页列全账号
- 背景：老师反馈「部署的没有多个示例」，且登录页只显示 admin/s001 两个快捷按钮，看起来像没同步。
- 改动：
  1. `DEMO_ACTIVITIES` 扩到 6 个：a001 羽毛球（直接，候补 2）、a002 编程马拉松（审核）、a003 校园歌手大赛（审核）、a004 AI 讲座（直接，120 人）、a005 摄影展志愿者（直接，容量 3 + 候补 3）、a006 读书会（直接，容量 1 + 候补 2）；
  2. `seed()` 对活动也改为 `INSERT OR IGNORE`，已部署实例重启即补出新活动，不覆盖已有数据；
  3. 登录页补齐账号说明（s001 张 / s002 李 / s003 王 / s004 赵 / s005 钱），并增加 s002 快捷按钮。
- 验证：公网 `GET /api/activities` 返回 6 条；新 bundle `index-DazssvbG.js` 同时包含「s005」与「我的报名状态」字样；服务重启后 health 正常。
- 影响文件：`project/repo/db.py`、`frontend/src/views/LoginView.vue`、`docs/deploy.md`

### 2026-11-21 · CR-02：管理员手动转候补 + 禁止管理员报名
- 反馈：管理端待审核列表只有「批准/拒绝」，无法把学生排进候补；且管理员能自己报名（自批自报）。
- 改动：
  1. `RegistrationService.waitlist()`：PENDING → WAITLISTED，按 `next_waitlist_position` 分配位次；活动 `waitlist_capacity=0` 时自动补成容量；满员返回 `WAITLIST_FULL`；
  2. 新接口 `POST /api/registrations/{id}/waitlist`（仅管理员）；
  3. `register()` 拒绝管理员（403 `ADMIN_CANNOT_REGISTER`），前端详情页对管理员隐藏报名按钮；
  4. 管理端每行新增「转候补」按钮；补位逻辑沿用 CR-01（取消已通过→候补首位自动 APPROVED）。
- 验证：单测 46/46（新增 5 例）、冒烟 84/84（新增 14 条断言）；公网实测「转候补→位次 1→自动补成上限 1→取消后自动通过→管理员报名 403」全部符合预期。
- 影响文件：`project/service/registration.py`、`project/web/server.py`、`frontend/src/views/{AdminView,ActivityDetailView}.vue`、`tests/{test_waitlist,smoke_api}.py`、`docs/{change-request,test-cases}.md`、`README.md`

---

<!-- 后续阶段在此追加 -->
