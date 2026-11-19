# 状态图：报名记录（v1.1，含候补）

> 对应 `docs/change-request.md` CR-R1–CR-R4；与 `docs/srs.md` §7 的状态表一致。
> 图文件：`state-registration.drawio`（可编辑）；本页为同源 Mermaid。

````mermaid
stateDiagram-v2
    [*] --> APPROVED: 直接型报名（未满）
    [*] --> PENDING: 审核型报名
    [*] --> WAITLISTED: 直接型报名（已满且候补未满）

    PENDING --> APPROVED: 管理员批准（名额足）
    PENDING --> REJECTED: 管理员拒绝
    PENDING --> CANCELLED: 学生取消

    WAITLISTED --> APPROVED: 有人取消后自动补位
    WAITLISTED --> CANCELLED: 学生取消候补

    APPROVED --> CANCELLED: 学生取消
    APPROVED --> [*]
    REJECTED --> [*]
    CANCELLED --> [*]
```

## 要点

- `WAITLISTED` 只在**直接型**活动满员时产生；审核型满员仍进入 `PENDING`（不占名额）。
- 补位是**系统驱动**的迁移（`WAITLISTED → APPROVED`），由 `RegistrationService._promote_next` 在取消事务之后触发。
- 取消 `WAITLISTED` 不影响名额；取消 `APPROVED` 才会释放名额并触发补位。
- 终态（`REJECTED`/`CANCELLED`）保留历史，允许学生重新申请（新建记录）。
