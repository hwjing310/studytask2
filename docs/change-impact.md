# 变更影响分析（CR-01 候补队列）

| 项 | 内容 |
|---|---|
| 变更编号 | CR-01（候补队列） |
| 基线 | `baseline-v1`（commit `082ba7d`） |
| 分析日期 | 2026-11-19 |
| 状态 | **实现前分析**（「实际」列在 change-v2 完成后回填） |

---

## 1. 变更摘要

直接型活动满员后，报名由「直接报错」改为「进入候补队列」；已通过者取消时，候补按顺序自动补位并通知。
审核型活动行为不变。

## 2. 受影响模块

| 层 | 对象 | 影响类型 | 说明 |
|---|---|---|---|
| 数据库 | `activities` | 加列 | `waitlist_capacity INTEGER NOT NULL DEFAULT 0` |
| 数据库 | `registrations` | 加列 + 改约束 | `waitlist_position INTEGER NULL`；有效报名唯一索引需包含 `WAITLISTED` |
| 领域 | `RegistrationStatus` | 加枚举值 | 新增 `WAITLISTED`；`is_active` 需包含它 |
| 领域 | `Registration` | 加字段 | `waitlist_position`；`can_cancel` 覆盖候补 |
| 领域 | `Activity` | 加字段/判定 | `waitlist_capacity`、`is_waitlist_full(n)` |
| 领域 | `ActivityStats` | 加字段 | `waitlisted` |
| 仓储 | `RegistrationRepository` | 加方法 | `next_waitlist_position`、`first_waitlisted`、`count_waitlisted` |
| 服务 | `RegistrationService` | 改逻辑 | 满员分支、取消后的补位、统计口径 |
| 服务 | `ActivityService` | 小改 | 创建/更新支持 `waitlist_capacity`；统计透传 |
| 通知 | `InboxNotifier` | 加文案 | `WAITLISTED` 与「已补位」 |
| Web | `server.py` | 无结构变化 | 新错误码 `WAITLIST_FULL` 自动透传；响应加字段 |
| 前端 | `ActivityListView` / `DetailView` / `AdminView` | 展示与表单 | 显示候补人数/位次；管理端可配候补上限 |
| 测试 | 单测 + 冒烟 | 新增 | CR-AC1–AC6 与回归 |

## 3. 关键设计决策：候补逻辑放在哪里？

| 方案 | 说明 | 判断 |
|---|---|---|
| A. 新增 `WaitlistPolicy` 策略 | 让 `policy_type` 出现第三种取值 | **否决**：活动是「直接/审核」是业务配置，与「满员后怎么办」不是同一维度；把候补做成策略会让一个活动只能二选一 |
| B. 策略返回 `APPROVED`，服务层把「满员」改判为候补 | 策略语义不变，容量规则仍在服务层 | **采用**：与 D4 一致（名额是活动不变量，归服务层）；新增策略类型不必改服务 |
| C. 在 `Activity` 实体里做 | 实体需要知道已通过人数 | 否决：实体不持有全部报名，只能依赖仓储，污染领域层 |

**结论**：候补是**容量规则的延伸**，放在 `RegistrationService`，策略保持不变。
这也是对 D4 的直接验证：若当初把名额判断塞进策略，本次要在两个策略实现里各改一遍。

## 4. 预计代码差异

| 文件 | 类型 | 预计改动 |
|---|---|---|
| `project/domain/models.py` | 修改 | +20 行（枚举、字段、判定、统计） |
| `project/repo/db.py` | 修改 | +12 行（建表与迁移） |
| `project/repo/ports.py` | 修改 | +6 行（3 个方法签名） |
| `project/repo/sqlite_repo.py` | 修改 | +45 行（3 个查询 + 映射） |
| `project/service/registration.py` | 修改 | +40 行（满员分支、补位、统计） |
| `project/service/activity.py` | 修改 | +8 行（候补上限校验） |
| `project/notify/inbox.py` | 修改 | +6 行（2 条文案） |
| `frontend/src/views/*.vue` | 修改 | +30 行（展示与表单） |
| `tests/*` | 新增/修改 | +80 行（CR 用例） |

**预计修改的核心业务类数 = 2**（`Registration`、`RegistrationService`），其余为仓储/展示/测试。
若实际超过 2，说明 D4 的「规则集中」假设不成立，需在报告中如实说明。

## 5. 风险与应对

| 风险 | 说明 | 应对 |
|---|---|---|
| R1 并发补位导致超卖 | 两人同时取消，同一候补被补两次 | 补位在单事务内完成：先 `UPDATE … WHERE status='WAITLISTED' ORDER BY position LIMIT 1` 并校验 `rowcount=1` |
| R2 唯一索引与旧数据冲突 | 旧表可能已有两条 `APPROVED`（理论上不会） | 迁移时先检查，冲突则中止并输出报告 |
| R3 候补上限为 0 的语义 | 0 表示不开放候补 | 明确默认 0；建表默认 0，前端需要显式填写 |
| R4 审核型活动误入候补 | 逻辑分支写错 | 仅在 `policy.decide() == APPROVED` 且满员时进入候补；审核型返回 `PENDING`，天然不进该分支 |
| R5 通知重复 | 取消与补位各发一条 | 沿用 `(registration_id, status)` 唯一索引；补位事件用新状态值，不冲突 |

## 6. 新增与回归测试计划

| 类型 | 用例 |
|---|---|
| 新增（验收） | CR-AC1 候补成功；CR-AC2 候补满；CR-AC3 自动补位；CR-AC4 取消候补；CR-AC5 统计字段；CR-AC6 全量回归 |
| 新增（单元） | 候补位次递增；候补上限边界（0 / 1 / 多）；补位只补一个；补位后顺序重排；并发取消的超卖保护 |
| 回归 | `tests/run_tests.py` 全量；`tests/smoke_api.py` C1–C10 + E1–E10 |

## 7. 工作量与质量（已回填）

| 指标 | 预计 | 实际 |
|---|---|---|
| 新增类数 | 0 | **0**（候补未引入新类，只在既有类上加字段与方法） |
| 修改的核心业务类数 | 2 | **3**（`domain/models.py`、`service/registration.py`、`service/activity.py`） |
| 修改的总文件数 | 9 | **22**（含文档 4、测试 5、前端 4、后端 8、配置 1） |
| 改动行数 | — | **711**（+675 / −35，`git diff --numstat`） |
| 回归失败数 | 0 | **0**（单测 41/41、冒烟 70/70） |
| 新增测试数 | 12 | **8 个单测用例 + 18 条冒烟断言** |
| AI 交互轮次 | 6 | **8**（含 2 次返工，见 §8） |
| 修改总时长 | 2–3 小时 | **约 1.5 小时**（按交互轮次估算，非精确计时） |

## 8. 反思结论

**为什么修改范围合理**

- 领域层只加字段与判定，没有改变任何既有方法的语义；仓储层只新增查询，没有重写已有 SQL；
- 前端只做展示与表单，接口层（`server.py`）**零改动**——因为错误码与响应结构本来就是通用的；
- 策略层（`policy/`）**完全没动**，验证了「活动类型」与「满员后怎么办」确实是两个维度。

**预测偏差（如实记录）**

- 预测「修改的核心业务类 = 2」，实际 **3**：多出来的 `service/activity.py` 是为了让管理员能配置 `waitlist_capacity`（字段校验与透传）。
- 这说明 D4 的判断（**规则**集中在服务层）成立，但估算时低估了**字段面**的连带改动。结论应修正为：「规则集中」能收敛逻辑改动，但新增聚合字段仍会牵动创建/更新入口。

**两次返工**

1. `RegistrationRepository.find_active` 仍只查 `PENDING/APPROVED`，与「候补也算有效报名」不一致，导致重复报名靠数据库唯一索引兜底并抛 `IntegrityError`（不是友好的 409）。改为三状态查询后，单测 `test_waitlisted_counts_as_active` 通过。
2. 详情页「加入候补」按钮沿用了 `activity.open` 作为可用条件，而满员时 `open=false`，按钮被禁用。改为 `open || hasWaitlist`。

**如果重做一次**

- 会先在 `find_active` 一处定义「有效报名」的常量集合（`ACTIVE_STATUSES`），避免状态值散落在 SQL、领域属性、测试三处；
- 会把「候补上限」放进创建活动时的表单默认值提示（当前默认 0，演示时容易忘填导致仍报 `CAPACITY_FULL`）。
