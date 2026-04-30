# 集成测试设计各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 不依赖 Story 预取，输入来源为 API 定义/服务模块/客户端模块路径。

## 阶段 1: init — 初始化与项目测试约定学习

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

## 阶段 2: analyze — 接口分析

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

**归属判断**（关键步骤）：对每个识别到的场景按 [集成测试价值评估](SKILL.md#集成测试价值评估) 的归属规则判断，遵守 [UNIT_VS_INTEGRATION_BOUNDARIES](../_shared/UNIT_VS_INTEGRATION_BOUNDARIES.md)：

- 属于 integration → 进入测试场景矩阵
- 应归属 unit / E2E → 在「跳过的场景」表格中记录归属和理由，**不生成集成测试**
- 纯透传 / 无价值 → 在「跳过的场景」表格中记录

输出 `integration_test_plan.md`：接口清单 + 测试场景矩阵 + 跳过的场景表格。

## 阶段 3: design — 测试场景设计

为每个接口/操作设计测试场景：

1. **正向场景**：正常请求 → 成功响应 → 副作用验证
2. **参数验证**：缺失字段、非法类型、超出范围
3. **权限控制**：未认证、权限不足、跨租户访问
4. **业务规则**：状态约束、唯一性约束、关联完整性
5. **并发场景**：竞态条件、乐观锁冲突（如适用）
6. **数据准备策略**：确定每个场景的 setup 和 teardown

## 阶段 4: generate — 代码生成

1. **严格遵循 init 阶段学到的项目测试约定**——HTTP 客户端、数据库策略、认证方式、目录结构必须与项目已有测试一致
2. 复用项目已有的测试 helper（HTTP client wrapper、数据工厂、断言工具），不重复造轮子
3. 按场景生成测试代码，Mock 外部服务时使用项目中已有的 Mock 模式
4. 包含 setup（数据准备）和 teardown（数据清理），遵循项目已有的隔离策略
5. 将测试文件写入项目约定的位置（从已有测试的目录结构推断）
6. 如果项目无已有集成测试 → 参考 [METHODS.md](METHODS.md) 中的参考模板
7. **出口断言扫描**（硬性出口条件）：在提交测试文件前，对每个 test 方法扫描是否包含至少 1 个断言调用（参见 [断言审计协议](../_shared/ASSERTION_AUDIT.md)）。发现零断言方法时，原地补充断言后再进入 verify 阶段。目的确实是"验证不崩溃"的方法必须标注 `[crashSafety]` 并添加最低限度断言

## 阶段 5: verify — 验证

Phase 5 拆分为两个子阶段：先执行机械审计（5a），再执行语义质量检查（5b）。

### 5a. 独立断言审计

按 [独立验证者协议](../_shared/ASSERTION_AUDIT.md) 执行断言审计，优先使用独立 agent（模式 A），不可用时降级为自审 + Grep 扫描（模式 B）。

**模式 A**（推荐）：通过 Task 工具启动独立的 verify-agent。verify-agent 仅收到：
- 生成的测试文件全文
- 被测源码文件全文
- [断言审计协议](../_shared/ASSERTION_AUDIT.md)中的审计规则和弱断言定义

verify-agent **不收到** integration_test_plan.md 或任何设计推理。以对抗性视角审计——假定每个测试都有问题，证明合格后才放行。

**模式 B**（降级）：用 Grep 工具在生成的测试文件中搜索断言 pattern，逐方法统计断言数。然后按审计输出格式逐行填写审计表格。

5a 的输出是 [审计表格](../_shared/ASSERTION_AUDIT.md#审计输出格式)。任何 BLOCKED 项必须回到 Phase 4 修复后重新审计。

### 5b. 语义质量检查

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
