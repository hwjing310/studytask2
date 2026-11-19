# 时序图：审核型报名（进入待审核）

> 图文件：`seq-register-review.drawio`（可编辑）；本页为同源 Mermaid，便于在 GitHub/VS Code 直接预览。

同一入口、不同策略：审核型活动不走容量检查，直接创建 PENDING。

``mermaid
sequenceDiagram
  autonumber
  actor S as 学生
  participant UI as Vue 前端
  participant API as RegistrationHandler
  participant SVC as RegistrationService
  participant AR as ActivityRepository
  participant RR as RegistrationRepository
  participant PF as PolicyFactory
  participant P as ManualReviewPolicy
  participant BUS as EventBus
  participant N as InboxNotifier

  S->>UI: 点击「报名」（审核型活动）
  UI->>API: POST /api/activities/{id}/registrations
  API->>SVC: register(studentId, activityId)
  SVC->>AR: get(activityId)
  AR-->>SVC: Activity(policyType=REVIEW)
  SVC->>RR: findActive(activityId, studentId)
  RR-->>SVC: null
  SVC->>SVC: 待审核不占名额，跳过容量检查
  SVC->>PF: create(REVIEW)
  PF-->>SVC: ManualReviewPolicy
  SVC->>P: decide(ctx)
  P-->>SVC: PENDING
  SVC->>RR: add(Registration PENDING)
  RR-->>SVC: ok
  SVC->>BUS: publish(RegistrationEvent PENDING)
  BUS->>N: handle(event)
  N->>N: 写入「已提交，等待审核」站内消息
  SVC-->>API: Registration
  API-->>UI: 200 + 状态 PENDING
  UI-->>S: 显示「待审核」
  Note over SVC,AR: 统计口径：待审核不计入已通过数，因此剩余名额不变
``

## 要点
- - 待审核不占名额（BR3），因此跳过 countApproved 与容量判断。
- - 与直接报名的差异只体现在两处：策略实现、是否做容量检查；这正是引入策略模式后主流程无需 if 活动类型 的证据。
- - 消息文案不同（「已提交，等待审核」），由订阅者根据事件状态决定。

> 生成方式：Mermaid 源经 draw.io CLI 转换为 .drawio，后续如调整请在 draw.io 中编辑并同步本页。
