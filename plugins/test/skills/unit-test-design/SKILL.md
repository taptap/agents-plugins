---
name: unit-test-design
description: >
  分析源代码文件，自动生成可执行的单元测试代码。
  输入源码文件/模块路径，输出对应语言的测试文件（如 *_test.go、test_*.py、*.test.ts）。
---

# 单元测试设计

## Quick Start

- Skill 类型：代码级测试生成
- 适用场景：为已有代码自动生成单元测试，覆盖函数/方法级别的逻辑验证
- 必要输入：源代码文件路径或模块目录路径（至少一个）
- 输出产物：可执行的测试代码文件、`test_plan.md`（测试点清单）
- 失败门控：源代码文件不可读时停止；测试代码必须基于实际代码逻辑，不凭空构造
- 执行步骤：`init → analyze → design → generate → verify`

## 核心能力

- 代码分析 — 解析函数签名、参数类型、返回值、错误路径、分支逻辑
- 测试点识别 — 识别正向路径、边界值、错误处理、边缘条件
- 框架适配 — 根据语言自动选择测试框架和惯用模式
- Mock 生成 — 为外部依赖（数据库、HTTP、文件系统）生成 Mock/Stub
- 测试代码生成 — 输出可直接编译/运行的测试文件

## 测试生成原则

1. **忠于代码** — 严格基于源代码逻辑生成测试，不臆断未实现的行为
2. **独立原子** — 每个测试用例独立运行，无顺序依赖
3. **可运行性** — 生成的测试代码必须可编译/运行，import 路径正确
4. **惯用模式** — 遵循目标语言的测试惯用法（表驱动、参数化、BDD 等）
5. **覆盖充分** — 正向路径 + 边界值 + 错误处理 + 特殊输入
6. **验证行为而非实现** — 测试公开接口和业务不变量，不围绕当前内部实现细节写测试

## 测试质量防线

AI 生成的测试容易出现"看起来能过但实际不验证任何东西"的问题。以下规则用于防止测试本身的质量缺陷。

### 防硬编码过测

AI 有倾向只针对一个具体样例写测试，实现如果改坏了测试仍然通过。必须遵循：

- **参数化优先**：能做参数化/表驱动测试时，不只保留单个 happy path 样例。至少包含 3 类输入：正常值、边界值、异常值
- **反例必须有**：除了验证"正确输入→正确输出"，还要验证"错误输入→预期拒绝"。如果一个校验函数对所有输入都返回 true，你的测试应该能捕获这个 bug
- **Property-Based Testing**：对纯函数、转换器、校验器、序列化/反序列化等场景，优先考虑基于属性的随机化测试，而非只用固定样例。例如：`encode(decode(x)) == x`，`validate(validInput) == true && validate(invalidInput) == false`。详见 [METHODS.md](METHODS.md) 中的 Property-Based Testing 章节
- **不围绕实现细节背答案**：如果测试中出现从源代码中复制的常量或计算逻辑，这个测试就是在用实现验证实现，没有价值

### 断言质量要求

弱断言是 AI 生成测试最常见的问题。以下模式禁止出现：

| 弱断言（禁止） | 强断言（替代） | 原因 |
| --- | --- | --- |
| `assert.NoError(t, err)` 然后结束 | `assert.NoError(t, err)` + 验证返回值的关键字段 | 不验证返回值等于没测 |
| `assert.NotNil(t, result)` | `assert.Equal(t, expectedValue, result.Field)` | "不是 nil"不说明值是否正确 |
| `assert.True(t, len(items) > 0)` | `assert.Len(t, items, expectedLen)` 或验证具体元素 | "非空"不验证内容 |
| `assert.Error(t, err)` | `assert.ErrorIs(t, err, ErrNotFound)` 或 `assert.Contains(t, err.Error(), "not found")` | 任何 error 都能通过 |
| `assert.Equal(t, 200, resp.StatusCode)` 然后结束 | 同时验证响应体关键字段 | 状态码正确不代表数据正确 |

### 防 Mock 滥用

Mock 的目的是隔离外部依赖，不是跳过被测逻辑：

- **不 Mock 正在验证的核心逻辑**：如果测试 `UserService.CreateUser`，不应该 Mock 掉 `UserService` 内部的业务校验逻辑，只 Mock 它依赖的 `UserRepository`
- **Mock 只用于外部边界**：数据库、HTTP 调用、文件系统、第三方 SDK。被测模块内部的函数调用不应 Mock
- **Mock 返回值要合理**：Mock 的返回值应反映真实服务的行为特征（包括错误场景），不要只返回空成功

### 变异测试思维

生成测试时，思考"如果实现被改成以下错误版本，这组测试能否发现"：

- 条件判断反转（`>` 变 `<`，`==` 变 `!=`）
- 错误被吞掉（`return nil` 替代 `return err`）
- 边界值差一（`>=` 变 `>`）
- 默认值兜底掩盖了逻辑缺失
- 硬编码返回值替代真实计算

在 `test_plan.md` 中为关键测试标注「此测试防护的典型错误实现」，例如：

```markdown
| 用例 | 输入 | 预期 | 防护的错误实现 |
| --- | --- | --- | --- |
| 负数金额 | amount=-1 | 返回 error | 实现中遗漏金额校验（直接入库） |
| 边界值 0 | amount=0 | 返回 error | 校验写成 `amount < 0` 而非 `amount <= 0` |
```

### 防耦合实现细节

- **测试行为，不测调用链**：验证"给定输入，得到预期输出"，不验证"内部按什么顺序调用了哪些方法"
- **重构友好**：如果只是改变内部实现（提取方法、更换算法）但行为不变，测试不应大面积失败
- **不验证 AI 输出的具体文本**：如果被测函数生成描述性文本或日志，验证结构/格式/关键字段，不验证完整文本内容

## 框架适配策略

本 skill 不预设固定框架列表，而是**从项目已有测试代码中学习**测试约定。这样无论项目用什么语言、什么框架，生成的测试都能与项目现有风格保持一致。

[METHODS.md](METHODS.md) 提供的是**语言无关的测试设计原则和参考模板**，当项目中没有已有测试可参考时作为兜底。

## 阶段流程（5 阶段）

### 阶段 1: init — 初始化与项目测试约定学习

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
5. 如果项目中没有已有测试文件 → 根据构建配置推断主流框架（go.mod → testing+testify、pyproject.toml → pytest、package.json → vitest/jest），并参考 [METHODS.md](METHODS.md) 中的参考模板

### 阶段 2: analyze — 代码分析

**上游感知**（可选）：如果工作目录中存在 `requirement_points.json`（上游 requirement-clarification 产出）或 `test_cases.json`（上游 test-design 产出），先读取这些文件：
- 从 `requirement_points.json` 中提取 P0/P1 功能点，标记与这些功能点相关的代码模块为高优先级
- 从 `test_cases.json` 中了解已有的功能测试场景，避免重复覆盖已在功能测试中验证的纯业务逻辑

对每个源码文件：

1. **函数/方法提取**：列出所有公开和关键私有函数
2. **签名分析**：参数类型、返回值类型、错误返回
3. **逻辑分支识别**：if/switch/match 分支、循环、提前返回
4. **依赖识别**：外部依赖（数据库、HTTP 客户端、文件 IO、第三方服务）
5. **边界条件**：数值范围、空值处理、集合空/满、字符串长度
6. **需求关联**（如有上游数据）：标注函数对应的需求功能点编号（如 FP-3）

输出 `test_plan.md`：每个函数的测试点清单。如有上游需求数据，标注需求关联。

### 阶段 3: design — 测试设计

基于 `test_plan.md`，为每个函数设计测试用例：

1. **正向路径**：典型输入 → 预期输出
2. **边界值**：极值、零值、空值、最大值
3. **错误处理**：无效输入、依赖失败、超时
4. **Mock 策略**：确定哪些依赖需要 Mock，设计 Mock 行为
5. **用例命名**：清晰描述测试意图（如 `TestParseConfig_EmptyInput_ReturnsError`）

### 阶段 4: generate — 代码生成

1. **严格遵循 init 阶段学到的项目测试约定**——import 风格、Mock 方式、命名规则、目录结构必须与项目已有测试一致
2. 包含必要的 import 和 setup/teardown（复用项目已有的 helper 函数）
3. Mock 外部依赖时优先使用项目中已有的 Mock 工具和模式
4. 将测试文件写入项目约定的位置（从已有测试的目录结构推断）
5. 如果项目无已有测试 → 参考 [METHODS.md](METHODS.md) 中的参考模板

### 阶段 5: verify — 验证

1. 检查生成的测试文件语法正确性
2. 尝试编译/运行测试（`go test`、`pytest`、`npm test` 等）
3. 修复编译错误或导入问题
4. **质量自检**（逐项检查）：
   - 是否存在"只断言无错误但不验证返回值"的弱断言？
   - 是否所有参数化测试都包含了边界和异常 case，而非只有 happy path？
   - 是否有测试 Mock 掉了被测函数自身的核心逻辑？
   - 对每个关键测试，能否说明"把实现改成哪种错误版本后此测试会失败"？
   - 纯函数/校验器是否使用了 property-based testing？
   - 如自检发现问题 → 回到 generate 阶段修复，最多重试 2 次
   - 重试后仍不通过 → 在 test_plan.md 中标注未通过的自检项
5. 输出测试结果摘要和质量自检报告

## 输出格式

### test_plan.md

```markdown
# 测试计划

## 文件: path/to/source.go

### func ParseConfig(data []byte) (*Config, error)

| 用例 | 输入 | 预期 | 类型 |
| --- | --- | --- | --- |
| 正常 JSON | `{"key": "value"}` | 返回 Config 对象 | 正向 |
| 空输入 | `[]byte{}` | 返回 error | 边界 |
| 非法 JSON | `invalid` | 返回 error | 错误 |
| nil 输入 | `nil` | 返回 error | 边界 |
```

### 测试代码文件

直接写入项目对应位置，如 `path/to/source_test.go`。

## Mock 策略

Mock 方式应从项目已有测试中学习。如果项目中无已有测试可参考，以下为各语言的常见默认选择：

| 依赖类型 | Go | Python | TypeScript | Java/Kotlin | Swift |
| --- | --- | --- | --- | --- | --- |
| 接口 | Mock struct / testify mock | unittest.mock | vi.fn() / jest.mock() | Mockito / MockK | Protocol Mock |
| HTTP | httptest.Server | responses / httpx_mock | msw / nock | MockWebServer | URLProtocol Mock |
| 数据库 | sqlmock / 接口抽象 | pytest fixtures | 内存 DB / mock | @DataJpaTest / H2 | 内存 store |
| 文件系统 | testing/fstest | tmp_path fixture | memfs | @TempDir | FileManager mock |

## 注意事项

- **项目约定优先**：init 阶段从已有测试中学到的框架、Mock 方式、命名风格是第一优先级，METHODS.md 模板是兜底
- 生成前先检查项目已有的测试工具和 helper，优先复用
- 测试文件放在源码同级目录（Go）或 `tests/` 目录（Python，视项目结构）
- 不为 trivial 函数（getter/setter、单行委托）生成测试
- 已有测试的函数默认跳过，除非用户明确要求补充
- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
