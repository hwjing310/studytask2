# 类图（领域 + 分层全图）

> 图文件：`class-diagram.drawio`（可编辑）；本页为同源 Mermaid，便于在 GitHub/VS Code 直接预览。

领域模型与策略/通知/服务/仓储/Web 五层的静态结构。左半部分是业务概念，右半部分是技术实现；箭头的方向就是依赖方向，全部由外向内指向抽象。

``mermaid
classDiagram
  direction TB

  namespace Domain {
    class Activity {
      +String activityId
      +String title
      +String category
      +String startAt
      +String location
      +int capacity
      +String policyType
      +String deletedAt
      +isOpen(now) bool
      +isDeleted() bool
      +isFull(approvedCount) bool
    }
    class Student {
      +String studentId
      +String name
      +String passwordHash
      +verify(password) bool
    }
    class Registration {
      +String registrationId
      +String activityId
      +String studentId
      +String status
      +String createdAt
      +String updatedAt
      +isActive() bool
      +canCancel() bool
    }
    class Message {
      +String messageId
      +String studentId
      +String activityId
      +String content
      +String createdAt
      +bool isRead
      +markRead()
    }
    class ActivityStats {
      +int approved
      +int pending
      +int remaining
    }
  }

  namespace Policy {
    class RegistrationPolicy {
      <<interface>>
      +decide(ctx) RegistrationStatus
    }
    class DirectApprovalPolicy {
      +decide(ctx) RegistrationStatus
    }
    class ManualReviewPolicy {
      +decide(ctx) RegistrationStatus
    }
    class PolicyFactory {
      +create(policyType) RegistrationPolicy
    }
  }

  namespace Notify {
    class DomainEvent {
      <<interface>>
      +String eventId
      +String eventType
      +String occurredAt
    }
    class RegistrationEvent {
      +String registrationId
      +String activityId
      +String studentId
      +String status
      +String eventId
      +String eventType
      +String occurredAt
    }
    class EventSubscriber {
      <<interface>>
      +handle(event)
    }
    class EventBus {
      +subscribe(subscriber)
      +publish(event)
    }
    class InboxNotifier {
      +handle(event)
    }
  }

  namespace Service {
    class AuthService {
      +login(username, password) Session
    }
    class ActivityService {
      +create(adminId, dto) Activity
      +update(adminId, activityId, dto) Activity
      +softDelete(adminId, activityId)
      +list(query) list
      +get(activityId) Activity
      +stats(activityId) ActivityStats
    }
    class RegistrationService {
      +register(studentId, activityId) Registration
      +cancel(studentId, registrationId)
      +approve(adminId, registrationId)
      +reject(adminId, registrationId)
      +listMine(studentId) list
      +listPending(activityId) list
      +checkCommonRules(activity, studentId)
    }
    class MessageService {
      +listMine(studentId) list
      +markRead(studentId, messageId)
    }
  }

  namespace Repo {
    class ActivityRepository {
      <<interface>>
      +add(activity)
      +update(activity)
      +get(activityId) Activity
      +listActive(query) list
      +countApproved(activityId) int
      +countPending(activityId) int
    }
    class RegistrationRepository {
      <<interface>>
      +add(registration)
      +update(registration)
      +get(registrationId) Registration
      +findActive(activityId, studentId) Registration
      +listByStudent(studentId) list
      +listByActivityAndStatus(activityId, status) list
    }
    class StudentRepository {
      <<interface>>
      +get(studentId) Student
    }
    class MessageRepository {
      <<interface>>
      +add(message)
      +listByStudent(studentId) list
      +markRead(studentId, messageId)
    }
    class NotifyFailureRepository {
      <<interface>>
      +add(eventId, payload, error)
    }
    class SqliteRepositories {
      +connect(dbPath)
      +migrate()
    }
  }

  namespace Web {
    class AppServer {
      +ThreadingHTTPServer server
      +start(port)
    }
    class Router {
      +dispatch(request) Response
    }
    class AuthHandler
    class ActivityHandler
    class RegistrationHandler
    class MessageHandler
    class StaticHandler
    class ApiError {
      +int status
      +String code
      +String message
    }
  }

  %% 领域依赖
  Registration --> Activity
  Registration --> Student
  Message --> Student

  %% 策略
  DirectApprovalPolicy ..|> RegistrationPolicy
  ManualReviewPolicy ..|> RegistrationPolicy
  PolicyFactory ..> RegistrationPolicy
  RegistrationService --> RegistrationPolicy
  RegistrationService ..> PolicyFactory

  %% 通知
  RegistrationEvent ..|> DomainEvent
  InboxNotifier ..|> EventSubscriber
  EventBus o--> EventSubscriber
  RegistrationService ..> EventBus
  RegistrationService ..> RegistrationEvent
  InboxNotifier --> MessageRepository

  %% 服务依赖抽象
  ActivityService --> ActivityRepository
  RegistrationService --> ActivityRepository
  RegistrationService --> RegistrationRepository
  RegistrationService --> StudentRepository
  RegistrationService ..> EventBus
  MessageService --> MessageRepository
  AuthService --> StudentRepository
  InboxNotifier ..> NotifyFailureRepository

  %% 仓储实现
  SqliteRepositories ..|> ActivityRepository
  SqliteRepositories ..|> RegistrationRepository
  SqliteRepositories ..|> StudentRepository
  SqliteRepositories ..|> MessageRepository
  SqliteRepositories ..|> NotifyFailureRepository

  %% Web 层只依赖服务
  AppServer --> Router
  Router --> AuthHandler
  Router --> ActivityHandler
  Router --> RegistrationHandler
  Router --> MessageHandler
  Router --> StaticHandler
  AuthHandler --> AuthService
  ActivityHandler --> ActivityService
  RegistrationHandler --> RegistrationService
  MessageHandler --> MessageService
  ActivityHandler ..> ApiError
  RegistrationHandler ..> ApiError
``

## 要点
- - 领域层（Domain）不依赖任何其他层，Activity/Registration 自带 isOpen、isActive、canCancel 等判定，避免贫血模型。
- - 策略（Policy）：RegistrationPolicy 只有一个方法 decide(ctx)，RegistrationService 只依赖接口；PolicyFactory 负责按活动配置选实现。
- - 通知（Notify）：RegistrationService 只向 EventBus 发布 RegistrationEvent，不直接依赖 MessageRepository；InboxNotifier 作为订阅者写消息，写失败由 NotifyFailureRepository 留痕。
- - 服务层（Service）只依赖仓储**接口**，SqliteRepositories 是唯一实现，替换存储不影响业务代码。
- - Web 层（Web）只依赖服务层，Router 按路径分发到 Handler；错误统一走 ApiError。
- - 关键约束：RegistrationService 对 Activity/Registration 只做公共规则检查（名额、重复、是否开始），业务差异交给策略。

> 生成方式：Mermaid 源经 draw.io CLI 转换为 .drawio，后续如调整请在 draw.io 中编辑并同步本页。
