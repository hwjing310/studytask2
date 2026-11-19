# 时序图：审批批准（名额兜底）

> 图文件：`seq-approve.drawio`（可编辑）；本页为同源 Mermaid，便于在 GitHub/VS Code 直接预览。

管理员批准待审核报名的调用链，重点是「批准时再次检查名额」。

``mermaid
sequenceDiagram
  autonumber
  actor A as 管理员
  participant UI as Vue 前端
  participant API as RegistrationHandler
  participant SVC as RegistrationService
  participant RR as RegistrationRepository
  participant AR as ActivityRepository
  participant BUS as EventBus
  participant N as InboxNotifier

  A->>UI: 待审核列表点击「批准」
  UI->>API: POST /api/registrations/{id}/approve
  API->>SVC: approve(adminId, registrationId)
  SVC->>RR: get(registrationId)
  RR-->>SVC: Registration(PENDING)
  alt 状态不是 PENDING
    SVC-->>API: ApiError 409 INVALID_STATE
    API-->>UI: 409「状态已变更」
  else 状态合法
    SVC->>AR: countApproved(activityId)
    AR-->>SVC: n
    SVC->>SVC: remaining = capacity - n
    alt remaining <= 0
      SVC-->>API: ApiError 409 CAPACITY_FULL
      Note over SVC,RR: 状态保持 PENDING，不写库
      API-->>UI: 409「名额已满，无法批准」
    else 名额充足
      SVC->>RR: update(status=APPROVED)
      RR-->>SVC: ok
      SVC->>BUS: publish(RegistrationEvent APPROVED)
      BUS->>N: handle(event)
      N->>N: 写入「审核通过」站内消息
      SVC-->>API: Registration + stats
      API-->>UI: 200
      UI-->>A: 列表移除，统计刷新
    end
  end
``

## 要点
- - 状态校验（必须 PENDING）与容量校验（剩余 > 0）是两道独立闸门，任一失败都不改库。
- - 容量不足时状态保持 PENDING，既未超卖也未丢申请，管理员可等有人取消后再批。
- - 成功后发布 APPROVED 事件，由订阅者写「审核通过」消息；通知失败不回滚状态（BR6）。

> 生成方式：Mermaid 源经 draw.io CLI 转换为 .drawio，后续如调整请在 draw.io 中编辑并同步本页。
