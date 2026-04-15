---
name: integration-test-design
description: >
  分析 API 接口、服务模块或客户端模块，自动生成可执行的集成测试代码。
  支持后端服务（API/数据库/消息队列）和客户端应用（路由导航/网络请求/跨模块数据流）。
  输入 API 定义/服务路径/客户端模块路径，输出集成测试文件。
  触发：集成测试、API 测试、integration test、接口测试、服务测试、端到端测试代码。
---

# 集成测试设计

## Quick Start

- Skill 类型：代码级测试生成
- 适用场景：为 API 接口、数据库交互、服务间调用、客户端路由导航、网络请求链路、跨模块数据流生成集成测试代码
- 必要输入：API 定义文件（OpenAPI/Proto/路由文件）或服务模块路径或客户端模块路径（至少一个）
- 输出产物：可执行的集成测试代码文件、`integration_test_plan.md`（测试场景清单）
- 失败门控：输入文件不可读时停止；测试代码必须基于实际接口/模块定义
- 执行步骤：`init → analyze → design → generate → verify`

## 核心能力

- API 分析 — 解析 OpenAPI/Swagger、Proto、路由定义，提取接口契约
- 服务分析 — 识别数据库交互、外部服务调用、消息队列消费
- 客户端模块分析 — 识别路由注册、网络请求定义、通知监听、跨模块数据流
- 场景设计 — 设计端到端测试场景（请求 → 处理 → 响应 → 副作用验证）
- 测试数据构造 — 生成测试 fixtures 和数据工厂
- 环境隔离 — 事务回滚、临时数据库、容器化测试环境（后端）；URLProtocol Stub、Router 拦截、内存 UserDefaults（客户端）

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| API/服务分析（analyze 阶段） | Opus | 理解接口契约和服务交互 |
| 场景设计和代码生成（design/generate 阶段） | Sonnet | 模板化生成 |
| 质量自检（verify 阶段） | Opus | 捕捉浅层断言需要深度推理 |

## 测试生成原则

1. **接口驱动** — 基于 API 契约或代码接口定义生成测试
2. **环境隔离** — 测试间无数据污染，支持并行执行
3. **端到端验证** — 验证完整的请求→响应链路，包括副作用
4. **数据自治** — 每个测试自行构造和清理数据，不依赖共享 seed 数据
5. **可重复执行** — 测试幂等，多次运行结果一致
6. **深度断言** — 不只验证 status code，必须验证响应体关键字段和数据库副作用

## 跳过标准与测试质量防线

通用规则见 [TEST_QUALITY_GUIDELINES.md](../_shared/TEST_QUALITY_GUIDELINES.md)（跳过标准、防硬编码、防 Mock 滥用、变异测试思维）。以下为集成测试特有的补充：

### 跳过标准补充：test helper 适用范围不明确

当使用测试 helper（拦截器、stub）进行断言，但无法确认被测场景是否流经 helper 的拦截点时，**不生成使用该 helper 的断言**。

**判断方法**：读 helper 的 install/register 方法（这是 helper 的公开 API，不是实现细节），确认它挂载在哪个调用点上。然后判断被测场景是否一定经过该调用点。

- **确定经过** → 正常使用 helper 断言
- **确定不经过**（如已知走另一个分支） → 使用其他断言方式（如 `assertNoRouteTriggered()`）
- **不确定** → 不生成该断言，在 integration_test_plan.md 中记录场景和跳过原因

**典型触发场景**：

- 路由 handler 返回的对象可能实现特殊协议（如 ActionType），走自定义分派而非标准 push/present
- 网络请求在某些错误条件下可能绕过 URLProtocol（如 DNS 预解析失败）
- 通知监听器在某些状态下可能未注册

### 防浅层断言

集成测试最常见的问题是"只验证 HTTP 状态码就结束了"。必须遵循：

- **响应体断言**：API 测试不能只检查 `status == 200`，必须验证响应 body 中的关键业务字段（ID、状态、计算结果等）
- **副作用验证**：写操作（POST/PUT/DELETE）必须验证数据库/缓存/队列中的实际变更，不只信任 API 返回值
- **副作用验证要具体**：不只检查 `COUNT(*) == 1`，要检查记录的关键字段值（状态、金额、关联 ID 等）
- **错误响应验证**：错误场景不只检查 4xx/5xx 状态码，还要验证错误消息中包含有意义的信息（错误类型或字段名）

| 弱断言（禁止） | 强断言（替代） |
| --- | --- |
| 只检查 `status == 201` | + 验证返回的 `id` 非空 + 用该 `id` 查询 DB 确认记录存在 |
| 只检查 `status == 409` | + 验证错误消息包含冲突字段名（如 `"email"`) |
| 用 `COUNT(*) == 1` 验证副作用 | + 查询记录并验证 `status`、`amount` 等关键字段 |
| 只检查删除返回 `204` | + 查询 DB 确认记录已不存在或标记为已删除 |

### 防 Mock 滥用补充

- **不 Mock 被测服务本身的核心链路**：集成测试的价值在于验证组件间的真实交互。如果 Mock 掉了被测服务内部的业务逻辑（如校验、状态转换），测试就退化成了单元测试
- **Mock 只用于不可控的外部系统**：第三方支付、短信网关、外部 API 等。内部数据库、缓存应使用真实实例（可以是测试专用实例）
- **Mock 外部服务时也要测试失败场景**：不只 Mock 成功返回，还要测试外部服务返回错误、超时时被测服务的行为

### 防硬编码补充

- **测试数据不应从源代码中复制常量**：如果代码中定义了 `MaxRetries = 3`，测试不应硬编码 3 次循环来验证，而应验证"超过限制后行为正确"这个不变量
- **参数化 API 测试**：同一个接口的正向/异常/边界场景应使用表驱动/参数化，不要为每个场景单独写重复的 setup 代码
- **测试应能在数据库 schema 不变的前提下自由修改测试数据**：如果把测试中的用户名从 "Alice" 改成 "Bob" 测试就挂了，说明测试依赖了不该依赖的具体值

### 防拦截盲区

使用测试 helper 前，先读其 install/register 方法确认拦截点——这是使用正确工具的前提，不是追踪实现细节：

- helper 的拦截点说明了它能捕获什么、不能捕获什么
- "没有被拦截"本身是可断言的行为——用 `assertNoRouteTriggered()` 等空断言
- 如果确认被测场景不经过拦截点但有其他合适的断言方式，正常生成
- 如果不确定，走跳过标准

## 测试类型

### 后端服务

| 类型 | 说明 | 典型场景 |
| --- | --- | --- |
| API 测试 | HTTP/gRPC 请求 → 响应断言 | REST API CRUD、gRPC 服务方法 |
| 数据库测试 | 操作 → 数据库状态验证 | Repository 层、数据迁移 |
| 服务间调用 | 模拟上下游服务交互 | 微服务调用链、消息队列消费 |
| 中间件测试 | 认证、限流、日志等中间件 | Auth middleware、Rate limiter |

### 客户端应用（iOS/Android/桌面端）

| 类型 | 说明 | 典型场景 |
| --- | --- | --- |
| 路由导航 | URL → 路由匹配 → VC/页面实例化 → 参数传递 | Deep Link、Universal Link、Scheme URL |
| 网络 Stub | 请求拦截 → 模拟响应 → 业务处理验证 | API 调用链路、错误降级、认证过期处理 |
| 通知处理 | 推送/本地通知接收 → 解析 → 路由跳转或状态变更 | 登录成功刷新、推送跳转、App 状态同步 |
| 跨模块数据流 | 模块 A 事件 → 模块 B 响应 → 最终状态 | 登录→首页刷新、支付成功→订单更新 |

各类型的详细方法论和代码模板见 [METHODS.md](METHODS.md)。

**框架适配策略**：与 unit-test-design 一致，本 skill 不预设固定框架，而是从项目已有集成测试代码中学习约定。METHODS.md 提供的是语言无关的测试设计原则和参考模板，当项目中没有已有测试可参考时作为兜底。

## 阶段流程（5 阶段）

### 阶段 1: init — 初始化与项目测试约定学习

1. 确认输入类型：API 定义文件 / 服务模块路径 / 客户端模块路径 / 技术方案文档
2. 识别项目类型和技术栈：
   - **后端服务**：Web 框架、ORM、HTTP 客户端等
   - **客户端应用**：UI 框架（UIKit/SwiftUI）、响应式框架（RxSwift/Combine）、路由框架、网络层
3. 检查项目测试基础设施：
   - **后端**：docker-compose.test.yml、测试数据库配置等
   - **客户端**：TestInfrastructure 目录、Stub/Mock Helper、.xctestplan 等
4. **学习项目集成测试约定**（关键步骤）：
   - 使用 Glob 搜索项目中已有的集成测试文件（`tests/integration/`、`*_integration_test.go`、`tests/api/`、`e2e/`、`*IntegrationTests.swift` 等目录和命名模式）
   - 选取 2-3 个有代表性的已有集成测试文件，用 Read 读取
   - 从已有测试中提取以下约定：
     - **测试框架**：用了什么 HTTP 测试客户端（httptest、supertest、httpx、URLProtocol 等）
     - **隔离策略**：事务回滚、testcontainers、内存 DB、URLProtocol 注册/反注册、Router 拦截器
     - **数据构造模式**：Factory 函数、Fixture 文件、Builder 模式、JSONFixtureLoader
     - **认证处理**：测试如何获取/Mock 认证 token
     - **目录结构和命名**：测试文件放在哪里，怎么命名
   - 将学到的约定记录到 `integration_test_plan.md` 的开头作为「项目测试约定」章节
5. **iOS/Swift 项目额外检测**（当检测到 `.xcodeproj` 或 `.xcworkspace` 时执行）：
   - 检测 `.xctestplan` 文件 → 找到 IntegrationTests 测试计划，了解已有集成测试分组
   - 搜索 `TestInfrastructure/`、`Helpers/`、`Stubbing/` 等目录 → 发现可复用的基础设施（StubURLProtocol、RouterTestHelper、NotificationTestHelper、XCTestCase+Async 等）
   - 检查 Fastlane 配置 → 了解集成测试的运行方式（scan lane、device 配置等）
   - 检测 `@testable import` 的模块名和 Podfile 测试 target 依赖
6. 如果项目中没有已有集成测试文件 → 根据项目技术栈推断合理默认值，参考 [METHODS.md](METHODS.md)

### 阶段 2: analyze — 接口分析

**上游感知**（可选）：如果工作目录中存在 `requirement_points.json`（上游 requirement-clarification 产出），先读取：
- 提取 P0/P1 功能点，标记与这些功能点相关的 API 端点为高优先级
- 在 `integration_test_plan.md` 中标注每个端点对应的需求功能点编号

**API 定义分析**（后端服务）：
1. 解析 OpenAPI/Swagger → 提取 endpoints、参数、响应 schema
2. 解析 Proto → 提取 service methods、message types
3. 解析路由文件 → 提取 handler 映射

**服务模块分析**（后端服务）：
1. 识别数据库操作（CRUD、事务、批量操作）
2. 识别外部服务调用（HTTP client、gRPC client）
3. 识别中间件链（认证、授权、限流、日志）
4. 识别异步操作（消息队列、定时任务）

**客户端模块分析**（iOS/Android 等）：
1. 识别路由注册（Router.register、路由表定义、Deep Link 映射）
2. 识别网络请求定义（API 路径、请求参数、响应 Model）
3. 识别通知监听（NotificationCenter、自定义事件总线）
4. 识别跨模块数据流（Delegate、Closure 回调、RxSwift/Combine 订阅）
5. 识别登录门控逻辑（需要认证的功能、登录拦截机制）

输出 `integration_test_plan.md`：接口清单和测试场景矩阵。

### 阶段 3: design — 测试场景设计

为每个接口/操作设计测试场景：

1. **正向场景**：正常请求 → 成功响应 → 副作用验证
2. **参数验证**：缺失字段、非法类型、超出范围
3. **权限控制**：未认证、权限不足、跨租户访问
4. **业务规则**：状态约束、唯一性约束、关联完整性
5. **并发场景**：竞态条件、乐观锁冲突（如适用）
6. **数据准备策略**：确定每个场景的 setup 和 teardown

### 阶段 4: generate — 代码生成

1. **严格遵循 init 阶段学到的项目测试约定**——HTTP 客户端、数据库策略、认证方式、目录结构必须与项目已有测试一致
2. 复用项目已有的测试 helper（HTTP client wrapper、数据工厂、断言工具），不重复造轮子
3. 按场景生成测试代码，Mock 外部服务时使用项目中已有的 Mock 模式
4. 包含 setup（数据准备）和 teardown（数据清理），遵循项目已有的隔离策略
5. 将测试文件写入项目约定的位置（从已有测试的目录结构推断）
6. 如果项目无已有集成测试 → 参考 [METHODS.md](METHODS.md) 中的参考模板
7. **出口断言扫描**（硬性出口条件）：在提交测试文件前，对每个 test 方法扫描是否包含至少 1 个断言调用（参见 [断言审计协议](../_shared/ASSERTION_AUDIT.md)）。发现零断言方法时，原地补充断言后再进入 verify 阶段。目的确实是"验证不崩溃"的方法必须标注 `[crashSafety]` 并添加最低限度断言

### 阶段 5: verify — 验证

Phase 5 拆分为两个子阶段：先执行机械审计（5a），再执行语义质量检查（5b）。

#### 5a. 独立断言审计

按 [独立验证者协议](../_shared/ASSERTION_AUDIT.md) 执行断言审计，优先使用独立 agent（模式 A），不可用时降级为自审 + Grep 扫描（模式 B）。

**模式 A**（推荐）：通过 Task 工具启动独立的 verify-agent。verify-agent 仅收到：
- 生成的测试文件全文
- 被测源码文件全文
- [断言审计协议](../_shared/ASSERTION_AUDIT.md)中的审计规则和弱断言定义

verify-agent **不收到** integration_test_plan.md 或任何设计推理。以对抗性视角审计——假定每个测试都有问题，证明合格后才放行。

**模式 B**（降级）：用 Grep 工具在生成的测试文件中搜索断言 pattern，逐方法统计断言数。然后按审计输出格式逐行填写审计表格。

5a 的输出是 [审计表格](../../CONVENTIONS.md#审计输出格式)。任何 BLOCKED 项必须回到 Phase 4 修复后重新审计。

#### 5b. 语义质量检查

在 5a 审计通过（无 BLOCKED 项）后，执行以下语义级别的质量检查：

1. 检查生成的测试文件语法正确性
2. 检查依赖是否完整（测试框架、HTTP 客户端库等）
3. 如测试环境可用，尝试运行测试
4. **语义自检**（逐项检查）：
   - 5a 标记为 WEAK 的方法是否已加强或书面说明理由？
   - API 测试是否都验证了响应体关键字段，而非只检查状态码？
   - 写操作测试是否都验证了数据库副作用？副作用验证是否具体到字段级别？
   - 是否有测试 Mock 掉了被测服务内部的业务逻辑？
   - 错误场景是否验证了具体的错误类型/消息，而非只检查 4xx？
   - 对每个关键场景，能否说明"把实现改成哪种错误版本后此测试会失败"？
   - **客户端特有检查项**（如适用）：
     - 路由测试是否验证了 VC 类型和参数值，而非只检查"有路由被触发"？
     - `RouterBase.open(xxx)` + 仅注释无断言 → 零断言（5a 应已拦截，此处做语义确认）
     - `XCTAssertNotNil(vc)` 不验证 vc 类型和属性 → 弱断言，必须加强为 `assertLastVC(is:)` + 属性验证
     - `manager.someMethod(input)` 无后续断言 → 零断言（仅调用不验证）
     - 网络 Stub 测试是否同时验证了请求参数（path、method、headers）和响应处理（数据解析、UI 状态）？
     - 通知测试是否验证了通知 userInfo 的消费和实际副作用（路由跳转、数据刷新）？
     - 错误场景是否验证了降级行为（如 401 触发登出、断网显示错误提示）？
     - setUp/tearDown 是否正确隔离了 URLProtocol、Router 拦截器、单例状态？
     - 使用 test helper 断言时，是否确认了被测场景的代码路径会经过 helper 的拦截点？不确定的是否已按跳过标准处理？
     - 对包装器/错误转换类型的断言，预期值是否来自 API 文档/注释的明确说明而非属性名的直觉推断？无法确认的是否已按跳过标准处理？
   - 如自检发现问题 → 回到 generate 阶段修复，最多重试 2 次
   - 重试后仍不通过 → 在 integration_test_plan.md 中标注未通过的自检项
5. 5a 和 5b 的发现按 [交叉验证协议](../_shared/AGENT_PROTOCOL.md#交叉验证协议) 合并
6. 输出测试结果摘要、审计表格和质量自检报告

## 输出格式

### integration_test_plan.md

```markdown
# 集成测试计划

## API: POST /api/v1/users

| 场景 | 请求 | 预期响应 | 副作用 | 类型 |
| --- | --- | --- | --- | --- |
| 创建用户成功 | `{"name": "Alice", "email": "a@b.com"}` | 201, 返回 user ID | DB 新增记录 | 正向 |
| 邮箱重复 | `{"name": "Bob", "email": "a@b.com"}` | 409 Conflict | 无变更 | 业务规则 |
| 缺失必填字段 | `{"name": ""}` | 400, 错误信息 | 无变更 | 参数验证 |
| 未认证 | 无 Auth Header | 401 | 无变更 | 权限 |
```

### 测试代码文件

直接写入项目测试目录（如 `tests/integration/`）。

## 环境隔离策略

### 后端服务

| 策略 | 说明 | 适用场景 |
| --- | --- | --- |
| 事务回滚 | 每个测试在事务中执行，结束后回滚 | 数据库测试 |
| 临时数据库 | 每次测试创建独立数据库/schema | 需要 DDL 测试 |
| Docker Compose | 启动完整依赖栈 | 多服务集成 |
| TestContainers | 程序化管理容器生命周期 | CI 环境 |
| 内存替代 | 使用 SQLite/内存 store 替代生产数据库 | 快速反馈 |

### 客户端应用（iOS/Android）

| 策略 | 说明 | 适用场景 |
| --- | --- | --- |
| URLProtocol 注册/反注册 | setUp 注册 StubURLProtocol，tearDown 反注册并清空 handler | 网络请求测试 |
| Router 拦截器 | install() 安装拦截器捕获路由，uninstall() 移除并清空路由表 | 路由导航测试 |
| 内存 UserDefaults | 使用独立 suiteName 的 UserDefaults 实例，tearDown 中 removeSuite | 持久化/配置测试 |
| NotificationCenter 隔离 | 使用独立 NotificationCenter 实例，或 tearDown 中 removeObserver | 通知处理测试 |
| 单例状态重置 | setUp 中将单例恢复初始状态，tearDown 中再次清理 | 跨模块状态测试 |

## Closing Checklist（CRITICAL）

skill 执行的最终阶段（verify）完成后，**必须**逐一验证以下产出：

- [ ] 集成测试代码文件 — 已写入项目测试目录，可编译/运行
- [ ] `integration_test_plan.md` — 非空，包含测试场景清单
- [ ] 断言审计通过 — 无 BLOCKED 项，WEAK 项已加强或书面说明理由

全部必须项通过后，输出完成总结。如任一必须项未满足，**停止并修复**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- **项目约定优先**：init 阶段从已有测试中学到的框架、数据库策略、Mock 方式是第一优先级，METHODS.md 模板是兜底
- 优先复用项目已有的测试 helper 和数据工厂
- API 测试应覆盖完整的 HTTP 请求（headers、auth、content-type）
- 数据库测试必须包含数据清理逻辑，避免测试间污染
- 不为纯代理/透传接口生成测试（应在上游测试）
- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
