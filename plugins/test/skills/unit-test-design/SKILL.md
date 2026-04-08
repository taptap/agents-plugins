---
name: unit-test-design
description: >
  分析源代码文件，自动生成可执行的单元测试代码。
  输入源码文件/模块路径，输出对应语言的测试文件（如 *_test.go、test_*.py、*.test.ts、*Tests.swift）。
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

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 代码分析（analyze 阶段） | Opus | 理解代码逻辑是生成质量的天花板 |
| 测试设计和代码生成（design/generate 阶段） | Sonnet | 模板化生成 |
| 质量自检（verify 阶段） | Opus | 捕捉弱测试需要深度推理 |

## 测试生成原则

1. **忠于代码** — 严格基于源代码逻辑生成测试，不臆断未实现的行为
2. **独立原子** — 每个测试用例独立运行，无顺序依赖
3. **可运行性** — 生成的测试代码必须可编译/运行，import 路径正确
4. **惯用模式** — 遵循目标语言的测试惯用法（表驱动、参数化、BDD 等）
5. **覆盖充分** — 正向路径 + 边界值 + 错误处理 + 特殊输入
6. **验证行为而非实现** — 测试公开接口和业务不变量，不围绕当前内部实现细节写测试。判断什么是"行为"、什么是"实现细节"，以及如何确保测试的预期值有独立的真相来源，参见 [业务场景驱动设计](#业务场景驱动设计) 章节

## 业务场景驱动设计

以下原则用于解决 AI 生成测试中最隐蔽的问题：**测试从代码实现中推导预期值，导致即使业务逻辑写错了测试也能通过**。这些原则与"测试质量防线"互补——后者防止"弱测试"（断言不够强），本节防止"空测试"（断言强但真相来源错误）。

### 原则 1：独立真相来源

测试的预期值必须来自独立于被测代码的信息来源。如果预期值是从实现代码中推导的，那测试只是在"用实现验证实现"。

**判断标准**：把被测代码的实现逻辑随意改错，测试是否仍然能通过？如果能，说明测试没有独立的真相来源。

**真相来源层级**：

| 来源 | 可靠度 | 示例 |
| --- | --- | --- |
| 线上真实 API 响应（抓包） | 最高 | 抓取典型游戏的 button-flag 接口 JSON 作为 fixture |
| 产品设计文档 / Figma 设计稿 | 高 | 「免费游戏详情页底部展示获取按钮」 |
| 回归测试用例（MeterSphere 等） | 高 | 人工编写的业务场景描述 |
| 代码注释中的业务规则 | 中 | 优先级排序注释、状态机转换说明 |
| 从实现代码推导 | 低 | 看到 `flag == 7` 就断言 `flag == 7` |

**反例**：

```swift
// 这个测试在验证什么？它只是在复述代码实现。
// 如果 flag==7 的含义被改成「预购」而非「下载」，测试依然通过。
let btn = TransformerApiAppButton(flag: 7, type: "default")
XCTAssertTrue(btn.isDownload())
```

**正例**：

```swift
// 真相来源：产品规则「免费已上架 iOS 游戏的主按钮应该是下载」
// 如果判定逻辑被改错，这个测试会告诉你「免费游戏的下载按钮挂了」
@Test("免费已上架 iOS 游戏 → 主按钮=下载，无副按钮")
func freePublishedIOSGame() {
    let vm = makeButtonFlagViewModel(fixture: "free_ios_game.json")
    #expect(vm.mainFlagModel?.isDownload() == true)
}
```

### 原则 2：按行为主体分层，判断测试价值

不是所有代码层都值得单测。按行为主体分层，判断每一层的测试投入产出比：

| 层级 | 行为主体 | 测什么 | 真相来源 | 单测价值 |
| --- | --- | --- | --- | --- |
| 数据解析 | JSON → Model | 反序列化正确性 | 真实 API fixture | 有 fixture 时值得 |
| 类型识别 | Model 方法 | 简单谓词（`isX()`） | 需要产品文档 | 简单谓词不值得；复合条件值得 |
| 业务逻辑 | ViewModel / Service | 排序、过滤、状态决策 | 产品规则 | **最值得** |
| 展示决策 | ViewModel | 主/副选取、过滤规则 | 回归用例 | 值得 |

**核心判断**：问自己「如果这层的逻辑被改错了，通过什么测试能最先发现？」如果答案是集成测试或 UI 测试，那这层可能不需要单独的单测。

**应用方式**：在 analyze 阶段对每个待测函数做价值评估，低价值的函数在 `test_plan.md` 中标注跳过原因，而非机械地为所有函数生成测试。

### 原则 3：用户故事命名

测试命名应描述**用户可见的行为预期**，而非代码分支路径。

| 维度 | 差的命名 | 好的命名 |
| --- | --- | --- |
| 函数名 | `test_isDownload_defaultType_flag7_returnsTrue` | `freePublishedIOSGame` |
| 描述 | `flag==7 且 type==default 时返回 true` | `免费已上架 iOS 游戏 → 主按钮=下载，无副按钮` |
| 失败时的信息 | `flag7 的 isDownload 返回 false 了` | `免费游戏的下载按钮挂了` |
| 重构友好性 | flag 从数字改枚举 → 测试名过时 | 用户故事不变 → 测试名仍然有效 |

**各语言惯用法**：

| 语言 | 差 | 好 |
| --- | --- | --- |
| Go | `TestParseConfig_NilInput_ReturnsError` | `TestParseConfig_RejectsNilPayload` |
| Python | `test_validate_email_at_missing` | `test_email_without_at_is_rejected` |
| TypeScript | `it('returns false when flag is 0')` | `it('rejects expired promo codes')` |
| Swift | `testParseConfig_emptyData_throwsError` | `@Test("空响应体抛出解析错误")` |

### 原则 4：Fixture 驱动测试

优先使用真实数据作为测试输入，而非手工拼凑的参数组合。

**Fixture 来源优先级**：

1. **线上抓包**：从线上环境抓取典型场景的 API 响应，保存为 JSON fixture。如果有人改了判定逻辑导致线上游戏的按钮展示不对，测试会直接告诉你
2. **API 契约文档**：从 OpenAPI / Swagger 定义中构造符合契约的 fixture
3. **手工构造**：仅在无法获取真实数据时使用，且必须以业务场景命名

**Fixture 命名规范**：

- 以业务场景命名：`free_ios_game.json`、`paid_preorder_game.json`、`test_game_unqualified.json`
- 不以代码结构命名：~~`flag7_type_default.json`~~、~~`button_type_buy.json`~~
- 一个 fixture 文件 = 一种真实存在的业务状态

### 原则 5：历史 bug 驱动策略

测试策略应由历史 bug 数据驱动，而非代码覆盖率。

**执行方式**：

1. 问自己：「过去半年里，这个模块出过哪些线上 bug？」
2. 每个线上 bug 都应该对应一个防回归测试
3. 在 `test_plan.md` 中标注每个测试防护的历史 bug（如有）

**bug 类型决定测试策略**：

| 历史 bug 类型 | 应对的测试策略 |
| --- | --- |
| 重构时搞乱了优先级/排序 | 业务逻辑层的单测（验证排序结果） |
| 服务端改了字段含义客户端没跟 | fixture 驱动的集成测试（用真实 API 响应） |
| 某个版本漏追加了隐式行为 | 隐式行为的专项测试（如 didSet 自动追加） |
| 条件组合遗漏导致按钮不展示 | 多按钮组合场景的参数化测试 |

## 跳过标准（不生成的场景）

以下场景 AI 无法可靠地确定断言预期值，**不生成测试代码**，只在 test_plan.md 中记录场景描述和跳过原因，由开发者自行补充。

### 预期值无法从公开 API 确定

当断言的预期值无法仅从以下信息确定时，不生成该断言：

- 被测类型/函数的文档注释、docstring
- 类型签名和参数类型
- 公开的常量或枚举定义
- 项目中已有测试的模式（同类断言的先例）

**典型触发场景**：

- **包装器/转换器属性**：被测类型将输入包装或转换后暴露为属性（如 `ErrorWrapper.code`、`ResponseParser.statusCode`），且文档未说明属性与原始输入的映射关系。AI 无法确定属性值是原始值、转换后的值、还是分类码
- **第三方库属性语义歧义**：断言涉及第三方库类型的属性（如 `MoyaError.errorCode`），属性名暗示的含义可能与实际语义不同，且项目中无使用先例可参考
- **Mock 数据经过条件分支**：mock 数据在到达断言属性前会经过条件解析（如 JSON 反序列化尝试），不同的 mock 内容触发不同分支，导致相同输入类型但不同输出值

**跳过时在 test_plan.md 中记录**：

```markdown
| 用例 | 场景描述 | 跳过原因 |
| --- | --- | --- |
| TapError(MoyaError.statusCode(非 JSON response)) 的 code 值 | HTTP 404 响应（body 为纯文本）经 TapError 包装后的 code 属性 | TapError.code 是包装器属性，语义取决于 response body 格式，无公开文档说明非 JSON 场景的行为 |
```

### 不跳过的反例

以下场景即使涉及包装器，AI 也应正常生成测试：

- 文档注释明确说明了属性语义（如 `/// 返回 HTTP 状态码`）
- 项目中已有测试对同类场景建立了断言先例
- 被测类型是项目内部类型，源码可读且转换逻辑简单直接（无条件分支、无 fallback）
- 存在服务端 API 契约文档（OpenAPI/Swagger）定义了响应结构

更多高风险假设场景参见 [CONVENTIONS.md 高风险假设模式](../../CONVENTIONS.md#高风险假设模式)。

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

各阶段的详细步骤见 [PHASES.md](PHASES.md)。以下为概要：

| 阶段 | 名称 | 核心职责 | 关键出口条件 |
| --- | --- | --- | --- |
| 1 | init | 学习项目测试约定、检测工程配置 | 约定记录到 test_plan.md |
| 2 | analyze | 代码分析、测试价值评估 | 输出 test_plan.md（测试点清单） |
| 3 | design | 用例设计、Mock 策略、参数化评估 | test_plan.md 更新完成 |
| 4 | generate | 代码生成、断言扫描、项目集成 | 零断言/零标注检查通过 |
| 5 | verify | 独立审计 + 语义质量检查 | 审计表无 BLOCKED 项 |

## 输出格式

### test_plan.md

```markdown
# 测试计划

## 项目测试约定（Phase 1 init 产出）

（按实际项目语言填写，以下为两种示例）

**Go 项目示例：**
- 框架选择：testing + testify/assert
- 命名风格：`Test_<函数名>_<场景>_<预期>`
- Mock 模式：interface mock

**Swift 项目示例：**
- 框架选择：Swift Testing（项目已有测试全部使用 Swift Testing）
- 命名风格：`@Suite("模块名") struct XxxTests` + `@Test("用户故事描述")`
- Mock 模式：Protocol Mock + StubURLProtocol
- 全局配置依赖：Configs.singleInstance（需通过依赖注入控制）

## 文件: path/to/source（按实际项目语言填写）

### 函数签名（按实际语言格式）

| 用例 | 输入 | 预期 | 类型 | 真相来源 | 防护的错误实现 |
| --- | --- | --- | --- | --- | --- |
| 正常输入 | 典型合法输入 | 返回预期对象 | 正向 | API 契约文档 | 实现返回空对象 |
| 空输入 | 空值/零值 | 返回 error | 边界 | 函数签名约定 | 遗漏空输入校验 |
| 非法输入 | 格式错误的数据 | 返回 error | 错误 | 函数签名约定 | 吞掉解析错误 |
| nil/null 输入 | nil/null | 返回 error | 边界 | 函数签名约定 | 对 nil 直接操作 |

### 参数化测试决定

| 方法 | 是否参数化 | 理由 |
| --- | --- | --- |
| （目标函数名） | 是/否 | 纯函数，输入空间有明确的边界类别 / 输入空间极小无需参数化 |

### 跳过的用例

| 用例 | 场景描述 | 跳过原因 |
| --- | --- | --- |
| (示例) | ... | ... |
```

### test_plan.md 生命周期

`test_plan.md` 是测试设计的核心中间产物，贯穿整个执行流程：

| 阶段 | 操作 |
| --- | --- |
| Phase 1 (init) | **创建** — 记录项目测试约定（框架选择、命名风格、Mock 模式） |
| Phase 2 (analyze) | **更新** — 补充每个函数的测试点清单、价值评估、需求关联（如有上游数据） |
| Phase 3 (design) | **更新** — 补充真相来源标注、用例设计细节、参数化测试决定、全局配置依赖标注 |
| Phase 4 (generate) | **引用** — 按 test_plan.md 中的设计生成代码 |
| Phase 5 (verify) | **引用+追加** — 审计时对照 test_plan.md 检查覆盖完整性，追加未通过的自检项 |

**保留策略**：生成完成后保留在测试文件同级目录中（如 `TapTapTests/Unit/GameDetail/test_plan.md`），作为测试设计的可追溯性记录，不自动删除。后续维护测试时可参照此文件了解设计意图。如果团队不希望将 `test_plan.md` 纳入版本控制，可在 `.gitignore` 中添加 `**/test_plan.md`。

**内容更新规则**：Phase 3 和 Phase 5 可以追加内容到 test_plan.md（如补充跳过原因、未通过的自检项），但不删除已有内容。如果后续阶段发现前序阶段的结论有误（如 analyze 阶段的价值评估不准确），应在原条目旁以 `[纠正]` 标记追加修正说明，保留原始记录以便追溯。

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

## Closing Checklist（CRITICAL）

skill 执行的最终阶段（verify）完成后，**必须**逐一验证以下产出：

- [ ] 测试代码文件 — 已写入项目对应位置，可编译/运行
- [ ] `test_plan.md` — 非空，包含测试点清单和价值评估
- [ ] 断言审计通过 — 无 BLOCKED 项，WEAK 项已加强或书面说明理由

全部必须项通过后，输出完成总结。如任一必须项未满足，**停止并修复**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- **项目约定优先**：init 阶段从已有测试中学到的框架、Mock 方式、命名风格是第一优先级，METHODS.md 模板是兜底
- 生成前先检查项目已有的测试工具和 helper，优先复用
- 测试文件放在源码同级目录（Go）或 `tests/` 目录（Python，视项目结构）
- 不为 trivial 函数（getter/setter、单行委托）生成测试
- 已有测试的函数默认跳过，除非用户明确要求补充
- **框架一致性**：同一批次生成的测试文件必须使用同一个框架（不允许混用 XCTest 和 Swift Testing），详见 [PHASES.md 框架一致性规则](PHASES.md#框架一致性规则)
- **Helper 作用域**：test helper 文件以模块名为前缀命名（如 Swift `GameDetailTestHelpers.swift`、Go `game_detail_test_helper_test.go`），helper 函数加模块前缀（如 `makeGameDetailFixture()`），避免跨模块命名冲突，详见 [PHASES.md Helper 作用域规范](PHASES.md#helper-作用域规范)
- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
