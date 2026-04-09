# 阶段流程详情

本文件定义 unit-test-design skill 的 5 个执行阶段的详细步骤。概述和设计原则见 [SKILL.md](SKILL.md)。

## 阶段 1: init — 初始化与项目测试约定学习

1. 确认输入：源码文件路径或模块目录
2. 读取源代码文件列表，过滤非代码文件
3. 识别编程语言（文件扩展名 + 构建配置文件）
4. **学习项目测试约定**（关键步骤）：
   - 使用 Glob 搜索项目中已有的测试文件（`*_test.go`、`test_*.py`、`*.test.ts`、`*Test.java`、`*Test.kt`、`*Tests.swift` 等）
   - 选取 2-3 个有代表性的已有测试文件（优先选择与待测源码同模块的），用 Read 读取
   - 从已有测试中提取以下约定：
     - **测试框架和 import**：用了什么测试库、断言库、Mock 库
     - **目录结构**：测试文件放在源码同级还是独立的 `tests/` 目录
     - **命名风格**：函数命名、文件命名、describe/context 嵌套层级
     - **Mock 模式**：用接口 Mock、依赖注入、monkey patch 还是 HTTP server
     - **数据构造**：有无 Factory/Builder/Fixture 工具函数
     - **setup/teardown 模式**：用 `TestMain`、`setUp/tearDown`、`beforeEach`、`@pytest.fixture` 还是其他
   - 将学到的约定记录到 `test_plan.md` 的开头作为「项目测试约定」章节
5. **iOS/Swift 项目额外检测**（当检测到 `.xcodeproj` 或 `.xcworkspace` 时执行）：
   - 检测 `.xctestplan` 文件 → 了解测试分组策略（哪些测试属于 Unit、哪些属于 Integration）。**关键**：解析 xctestplan JSON，检查 `testTargets` 数组中是否存在 `selectedTests` 字段 —— 如果存在则标记为「白名单模式」，Phase 4 生成代码后需要自动追加新测试到此列表
   - 识别测试框架共存情况：`import XCTest` vs `import Testing`（Swift Testing）→ 决定新测试使用哪个框架
   - 搜索 `TestInfrastructure/`、`Helpers/`、`Stubbing/` 等目录 → 发现可复用的测试基础设施（如 StubURLProtocol、JSONFixtureLoader、自定义断言 Helper）
   - 检查 `@testable import` 的模块名 → 确认测试 target 可访问的模块
   - 检查 Podfile / Package.swift 中测试 target 的依赖 → 了解可用的测试库
6. 如果项目中没有已有测试文件 → 根据构建配置推断主流框架（go.mod → testing+testify、pyproject.toml → pytest、package.json → vitest/jest、*.xcodeproj → XCTest + Swift Testing），并参考 [METHODS.md](METHODS.md) 中的参考模板

## 阶段 2: analyze — 代码分析

**上游感知**（可选）：如果工作目录中存在 `requirement_points.json`（上游 requirement-clarification 产出）或 `final_cases.json`（上游 test-case-generation 最终产出），先读取这些文件：

- 从 `requirement_points.json` 中提取 P0/P1 功能点，标记与这些功能点相关的代码模块为高优先级
- 从 `final_cases.json` 中了解已有的功能测试场景，避免重复覆盖已在功能测试中验证的纯业务逻辑

对每个源码文件：

1. **函数/方法提取**：列出所有公开和关键私有函数
2. **签名分析**：参数类型、返回值类型、错误返回
3. **逻辑分支识别**：if/switch/match 分支、循环、提前返回
4. **依赖识别**：外部依赖（数据库、HTTP 客户端、文件 IO、第三方服务）
5. **边界条件**：数值范围、空值处理、集合空/满、字符串长度
6. **需求关联**（如有上游数据）：标注函数对应的需求功能点编号（如 FP-3）
7. **测试价值评估**：对每个待测函数/方法，按 [业务场景驱动设计 - 原则 2](SKILL.md#原则-2按行为主体分层判断测试价值) 的分层标准评估是否值得单测。在 `test_plan.md` 中为每个函数标注所属分层（数据解析 / 类型识别 / 业务逻辑 / 展示决策），低价值的函数（如简单谓词、单行委托）标注跳过原因，将精力集中在业务逻辑层和展示决策层

输出 `test_plan.md`：每个函数的测试点清单，包含价值评估结论。如有上游需求数据，标注需求关联。真相来源在 Phase 3（design）中补充标注。

## 阶段 3: design — 测试设计

基于 `test_plan.md`，为每个函数设计测试用例：

1. **正向路径**：典型输入 → 预期输出
2. **边界值**：极值、零值、空值、最大值
3. **错误处理**：无效输入、依赖失败、超时
4. **Mock 策略**：确定哪些依赖需要 Mock，设计 Mock 行为
5. **用例命名**：使用用户故事风格描述测试意图，反映用户可见的行为预期（参见 [原则 3](SKILL.md#原则-3用户故事命名)）。例如用 `freePublishedIOSGame` 而非 `test_flag7_type_default_returnsTrue`
6. **Fixture 驱动**：优先寻找可用的真实数据 fixture（线上抓包 > API 契约文档 > 手工构造），fixture 文件以业务场景命名（参见 [原则 4](SKILL.md#原则-4fixture-驱动测试)）
7. **真相来源标注**：在 `test_plan.md` 中为每个用例标注预期值的真相来源（产品文档 / 线上 fixture / 回归用例 / 代码推导），便于后续审计测试是否具有独立的验证价值
8. **全局配置依赖检测**：如果被测代码依赖全局配置（如 `Configs.singleInstance`、`AppSettings.shared`、`UserDefaults` 等单例状态），在 `test_plan.md` 中标注该测试需要控制配置状态。为每个配置值的不同状态设计**独立测试用例**，通过 Mock 或依赖注入控制配置值，而非在同一测试中使用 `if/else` 条件分支（条件分支导致同一测试在不同环境下验证不同行为，违反「独立原子」原则）
9. **参数化测试评估**（硬性检查点）：对 analyze 阶段价值评估中标记为「数据解析」「业务逻辑」层的被测方法，以及签名特征为纯函数（无副作用、输出仅依赖输入）的方法，必须评估是否适合使用参数化测试（Swift Testing `@Test(arguments:)`、Go 表驱动、Python `@pytest.mark.parametrize` 等）。在 `test_plan.md` 中记录决定及理由——如果选择不使用参数化测试，必须说明为什么固定样例已经足够（如输入空间极小、无边界值变化等）

## 阶段 4: generate — 代码生成

1. **严格遵循 init 阶段学到的项目测试约定**——import 风格、Mock 方式、命名规则、目录结构必须与项目已有测试一致
2. 包含必要的 import 和 setup/teardown（复用项目已有的 helper 函数）
3. Mock 外部依赖时优先使用项目中已有的 Mock 工具和模式
4. 将测试文件写入项目约定的位置（从已有测试的目录结构推断）
5. 如果项目无已有测试 → 参考 [METHODS.md](METHODS.md) 中的参考模板
6. **出口断言扫描**（硬性出口条件）：在提交测试文件前，对每个 test 方法扫描是否包含至少 1 个断言调用（参见 [断言审计协议](../_shared/ASSERTION_AUDIT.md)）。发现零断言方法时，原地补充断言后再进入 verify 阶段。仅验证"不崩溃"的方法必须标注 `[crashSafety]` 并添加最低限度断言
7. **变异测试标注**（硬性出口条件）：对每个测试类/套件中的关键测试方法（P0 用例），必须在方法体内的注释中标注「此测试防护的典型错误实现」。例如：`// 防护：如果排序逻辑反转（降序→升序），此测试会失败`。无标注的 P0 用例不允许进入 verify 阶段。标注格式按语言惯例——Swift/Go/Java/Kotlin 使用 `//`、Python 使用 `#`
8. **iOS/Swift 项目集成**（当 init 阶段检测到 `.xcodeproj` 或 `.xcworkspace` 时执行）：
   - **Xcode 项目索引更新**：新创建的 `.swift` 测试文件必须添加到 `.xcodeproj/project.pbxproj` 对应的 test target 中，确保文件被编译。遵循项目规则「新创建的 swift 文件必须自动添加到 Xcode 索引中」
   - **xctestplan 更新**：检查 init 阶段识别的 `.xctestplan` 文件是否使用 `selectedTests` 白名单模式（`"testTargets"` 数组中包含 `"selectedTests"` 字段）。如果是，将新生成的所有 `@Suite` / `XCTestCase` 子类名追加到对应 test target 的 `selectedTests` 数组中，格式为 `"SuiteName"` 或 `"SuiteName/testMethodName"`。确保新测试能被 Test Plan 选中执行
   - **Helper 文件处理**：如果生成了 test helper 文件（Factory、Builder、Fixture Loader），同样需要添加到 pbxproj 和确认在 test target 的编译范围内
9. <a id="框架一致性规则"></a>**框架一致性**（硬性规则）：同一批次生成的所有测试文件必须使用同一个测试框架。init 阶段的框架选择结论是唯一依据——如果判定使用 Swift Testing，则全部使用 `@Suite` + `@Test` + `#expect`；如果判定使用 XCTest，则全部使用 `XCTestCase` + `XCTAssert*`。不允许同一批次中混用两种框架。具体选择规则见 [METHODS.md 的选型策略](METHODS.md#xctest-与-swift-testing-选型策略)
10. <a id="helper-作用域规范"></a>**Helper 作用域规范**：生成的 test helper 函数（Factory、Builder、make 系列方法）必须遵循以下规则：
    - helper 文件以 `{模块名}` 为前缀命名，避免通用名。示例：Swift `ButtonFlagTestHelpers.swift`、Go `button_flag_test_helper_test.go`、Python `button_flag_test_helpers.py`、TS `buttonFlagTestHelpers.ts`
    - helper 函数使用 `{模块名前缀}` 命名（如 `makeButtonFlagViewModel()`、`makeGameDetailFixture()`），避免使用无前缀的通用名（如 `makeViewModel()`、`makeModel()`）
    - 如果项目已有 helper 命名约定（从 init 阶段学到），遵循项目约定而非上述默认规则
    - helper 文件放在与测试文件同级的目录中，不跨模块共享。跨模块共用的 helper 应提取到 `TestInfrastructure/` 或 `SharedHelpers/` 目录

## 阶段 5: verify — 验证

Phase 5 拆分为两个子阶段：先执行机械审计（5a），再执行语义质量检查（5b）。

### 5a. 独立断言审计

按 [独立验证者协议](../_shared/ASSERTION_AUDIT.md) 执行断言审计，优先使用独立 agent（模式 A），不可用时降级为自审 + Grep 扫描（模式 B）。

**模式 A**（推荐）：通过 Task 工具（子代理机制）启动独立的 verify-agent。verify-agent 仅收到：

- 生成的测试文件全文
- 被测源码文件全文
- [断言审计协议](../_shared/ASSERTION_AUDIT.md)中的审计规则和弱断言定义

verify-agent **不收到** test_plan.md 或任何设计推理。以对抗性视角审计——假定每个测试都有问题，证明合格后才放行。

**模式 B**（降级）：用 Grep 工具在生成的测试文件中搜索断言 pattern，逐方法统计断言数。然后按审计输出格式逐行填写审计表格。

5a 的输出是 [审计表格](../../CONVENTIONS.md#审计输出格式)。任何 BLOCKED 项必须回到 Phase 4 修复后重新审计。

### 5b. 语义质量检查

在 5a 审计通过（无 BLOCKED 项）后，执行以下语义级别的质量检查：

1. 检查生成的测试文件语法正确性
2. 尝试编译/运行测试（`go test`、`pytest`、`npm test`、`xcodebuild test` 等）
3. 修复编译错误或导入问题
4. **语义自检**（逐项检查）：
   - 5a 标记为 WEAK 的方法是否已加强或书面说明理由？
   - 是否所有参数化测试都包含了边界和异常 case，而非只有 happy path？
   - 是否有测试 Mock 掉了被测函数自身的核心逻辑？
   - 对每个关键测试，能否说明"把实现改成哪种错误版本后此测试会失败"？
   - 纯函数/校验器是否使用了 property-based testing？
   - 如自检发现问题 → 回到 generate 阶段修复，最多重试 2 次
   - 重试后仍不通过 → 在 test_plan.md 中标注未通过的自检项
5. 5a 和 5b 的发现按 [交叉验证协议](../_shared/AGENT_PROTOCOL.md#交叉验证协议) 合并
6. 输出测试结果摘要、审计表格和质量自检报告
