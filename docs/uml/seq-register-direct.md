# 时序图：直接报名（自动通过）

> 图文件：`seq-register-direct.drawio`（可编辑）；本页为同源 Mermaid，便于在 GitHub/VS Code 直接预览。

学生报名直接型活动的完整调用链，含三条前置校验的失败分支。

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
  participant P as DirectApprovalPolicy
  participant BUS as EventBus
  participant N as InboxNotifier
  participant MR as MessageRepository

  S->>UI: 点击「报名」
  UI->>API: POST /api/activities/{id}/registrations
  API->>SVC: register(studentId, activityId)
  SVC->>AR: get(activityId)
  AR-->>SVC: Activity
  alt 活动不存在或已删除
    SVC-->>API: ApiError 404 ACTIVITY_NOT_FOUND
    API-->>UI: 404
  else 活动已开始
    SVC-->>API: ApiError 409 ACTIVITY_STARTED
    API-->>UI: 409
  else 可报名
    SVC->>RR: findActive(activityId, studentId)
    RR-->>SVC: null
    SVC->>AR: countApproved(activityId)
    AR-->>SVC: n
    SVC->>SVC: remaining = capacity - n
    alt remaining <= 0
      SVC-->>API: ApiError 409 CAPACITY_FULL
      API-->>UI: 409
    else 名额充足
      SVC->>PF: create(DIRECT)
      PF-->>SVC: DirectApprovalPolicy
      SVC->>P: decide(ctx)
      P-->>SVC: APPROVED
      SVC->>RR: add(Registration APPROVED)
      RR-->>SVC: ok
      SVC->>BUS: publish(RegistrationEvent APPROVED)
      BUS->>N: handle(event)
      N->>MR: add(Message 报名已通过)
      MR-->>N: ok
      N-->>BUS: done
      SVC-->>API: Registration
      API-->>UI: 200 + 报名详情
      UI-->>S: 显示「已通过」
    end
  end
``

## 要点
- - 前置校验顺序：活动存在/未删除 → 未开始 → 无有效报名 → 名额充足；每步失败都返回明确的错误码。
- - 策略只回答「通过还是待审核」，不负责名额；因此 DirectApprovalPolicy.decide 返回 APPROVED 是纯决策，没有副作用。
- - 报名先落库，再发布事件，最后写消息；写消息发生在报名提交之后（对应 BR6 的事务边界）。

> 生成方式：Mermaid 源经 draw.io CLI 转换为 .drawio，后续如调整请在 draw.io 中编辑并同步本页。
