# 断言审计与独立验证者协议

本文件定义代码生成类 skill（unit-test-design、integration-test-design）的断言审计规则和独立验证者协议。

## 断言审计协议

代码生成类 skill（unit-test-design、integration-test-design）的 verify 阶段必须执行断言审计，防止生成"看起来能过但实际不验证任何东西"的空测试。

### 语言断言模式表

以下 pattern 定义了各语言中"什么算一个断言调用"。verify 阶段按此表逐方法统计断言数。

| 语言 | 断言 pattern | 说明 |
| --- | --- | --- |
| Swift (Swift Testing) | `#expect` / `#require` | Swift Testing 宏 |
| Swift (XCTest) | `XCTAssert*` / `XCTFail` / `XCTUnwrap` | XCTest 断言家族 |
| Swift (自定义 Helper) | 方法内部调用了 `XCTAssert*` 或 `XCTFail` 的 Helper 方法（如 `assertLastVC(is:)`） | 需在 init 阶段识别项目 Helper |
| Go | `assert.*` / `require.*` / `t.Fatal*` / `t.Error*` | testify + 标准库 |
| Python | `assert ` / `pytest.raises` / `self.assert*` | pytest + unittest |
| TypeScript | `expect(` / `assert.*` | vitest / jest / chai |
| Java/Kotlin | `assert*` / `verify(` / `assertThat(` | JUnit + Mockito + AssertJ |

### 逐方法审计规则

Phase 5 必须对**每个**生成的 test 方法执行以下审计：

1. **提取断言列表**：列出方法体中匹配上述 pattern 的所有断言调用
2. **零断言检查**（硬性阻断）：断言数 == 0 → **BLOCKED**，必须补充断言或显式标注为 `[crashSafety]`
3. **弱断言检查**（软性阻断）：全部断言都是弱断言 → **WEAK**，必须加强或书面说明理由
4. **有效性检查**：对每个通过的测试回答"如果被测代码的某个分支被删掉，这个测试能发现吗？"→ 答案为"不能"则标记 **INEFFECTIVE**

### 弱断言定义

以下断言模式单独使用时视为弱断言（与其他强断言组合使用时不计为弱）：

| 语言 | 弱断言模式 | 应替换为 |
| --- | --- | --- |
| Swift | `XCTAssertNotNil(x)` 不检查 x 的类型或属性 | `XCTAssertEqual(x?.property, expected)` |
| Swift | `XCTAssertTrue(true)` 无条件通过 | 需搭配 `[crashSafety]` 标注 |
| Swift | `#expect(x != nil)` 不检查 x 的值 | `#expect(x == expectedValue)` |
| Go | `assert.NoError(t, err)` 然后结束 | + 验证返回值关键字段 |
| Go | `assert.NotNil(t, result)` | `assert.Equal(t, expected, result.Field)` |
| Python | `assert result is not None` | `assert result["key"] == expected` |
| TypeScript | `expect(result).toBeTruthy()` | `expect(result.field).toBe(expected)` |

### 高风险假设模式

以下场景中，AI 容易对预期值做出无法验证的假设。代码生成类 skill（unit-test-design、integration-test-design）应参考此表，在跳过标准中评估是否生成该测试。

| 场景 | 典型错误假设 | 风险 |
| --- | --- | --- |
| 包装器/转换器类型的属性 | 属性值 == 原始输入值 | 包装器可能转换、映射、丢弃或重新分类原始值 |
| 第三方库类型的属性 | 属性名暗示的含义就是实际语义 | `errorCode` 可能是枚举序号而非原始错误码 |
| Mock 数据经过条件解析的场景 | Mock 的输入值会原样到达断言属性 | 中间可能有 JSON 解析、类型转换、fallback 等分支 |
| 通过 test helper 间接断言的值 | helper 能捕获所有场景的结果 | helper 可能只拦截特定代码路径 |

当 AI 发现待生成的断言命中以上任一模式，且无法从公开 API 契约（文档注释、类型签名、已有测试先例）消除歧义时，应按各 SKILL.md 的跳过标准处理——不生成该断言，只在 test plan 中记录场景描述和跳过原因。

### `[crashSafety]` 标注规则

当测试目的确实是"验证不崩溃"时（例如对畸形输入的容错测试），必须同时满足：

1. 方法名或 MARK 注释中显式包含 `[crashSafety]` 标注
2. 至少包含一个最低限度断言（如 `#expect(true, "[crashSafety] 调用未崩溃")`、`XCTAssertTrue(true, "[crashSafety] ...")`）
3. 注释说明为何无法进行深度断言（例如"需要 DI 注入网络层才能验证内部行为"）

### 零断言硬规则

一个 test 方法体仅含注释或仅调用被测方法不含任何断言调用，是最严重的质量缺陷，等同于写了一个永远通过的测试。此类方法**不允许**出现在最终输出中，无例外。

### 审计输出格式

verify 阶段必须输出以下审计表格，逐方法列出审计结果：

```markdown
| 方法名 | 断言数 | 弱断言数 | 类型标注 | 结果 |
| --- | --- | --- | --- | --- |
| testParseValidJSON | 2 | 0 | - | PASS |
| testEmptyInput | 1 | 0 | - | PASS |
| testMalformedURL | 0 | 0 | [crashSafety] | PASS（已标注） |
| testDuplicateKeys | 1 | 1 | - | WEAK（需加强） |
| testMissingScheme | 0 | 0 | - | BLOCKED（零断言） |
```

审计总结：
- 硬性阻断数（BLOCKED）
- 软性阻断数（WEAK）
- 无效测试数（INEFFECTIVE）
- 审计结论：**PASS**（全部通过）/ **FAIL**（存在 BLOCKED 或 WEAK）

## 独立验证者协议

代码生成类 skill（unit-test-design、integration-test-design）的 verify 阶段存在固有的确认偏差——生成代码的 AI 自检自己的产出时，容易将注释读作断言、将意图等同于实现。本协议通过上下文隔离解决此问题。

**核心原则**：生成者（Phase 4）和验证者（Phase 5）必须是不同上下文。验证者不应看到生成推理过程，只看到生成产物。

### 模式 A：独立 Agent 审计（推荐）

当 Task 工具可用时，Phase 5 通过 Task 工具启动一个**独立的验证 agent**：

- 是一个全新 agent，没有 Phase 1-4 的上下文
- 收到的输入**仅包含**：生成的测试文件内容 + 被测源码文件内容 + 断言审计协议（本节内容）
- **不收到** test_plan.md、生成推理过程、或任何设计决策
- 以**对抗性视角**审计：假定每个测试都有问题，证明其合格后才放行

verify-agent prompt 模板：

```
你是测试质量审计员。你的任务是对以下测试代码进行断言审计。
你是刚刚启动的新 agent，不了解这些测试的设计意图——你必须仅从代码本身判断质量。

## 审计规则
对每个 test 方法：
1. 列出方法体中的所有断言调用（#expect / XCTAssert* / assert.* 等）
2. 如果断言数 == 0 → 标记为 BLOCKED（硬性阻断）
3. 如果所有断言都是弱断言 → 标记为 WEAK（软性阻断）
4. 对每个通过的测试回答："如果被测代码的某个分支被删掉，这个测试能发现吗？"
   如果答案是"不能" → 标记为 INEFFECTIVE

## 弱断言定义
{从 CONVENTIONS.md 断言审计协议的弱断言定义表注入}

## 输入
=== 测试代码 ===
{生成的测试文件全文}
=== 测试代码结束 ===

=== 被测源码 ===
{被测源文件全文}
=== 被测源码结束 ===

## 输出格式
1. 逐方法审计表格（方法名 | 断言数 | 弱断言数 | 类型标注 | 结果）
2. 审计总结（硬性阻断数 / 软性阻断数 / 无效测试数 / 结论 PASS 或 FAIL）
3. FAIL 时列出每个问题方法的具体修复建议
```

### 模式 B：自审 + Grep 扫描降级

当 Task 工具不可用时（如 context 限制、工具不可用），执行降级版本：

1. **机械扫描**（不依赖 AI 推理）：用 Grep 工具在生成的测试文件中搜索断言 pattern
   - Swift: `Grep(pattern="#expect|XCTAssert|XCTFail", path=测试文件)`
   - Go: `Grep(pattern="assert\.|require\.|t\.Fatal|t\.Error", path=测试文件)`
   - 逐方法统计断言数
2. **结构化自审**：对每个 test 方法，必须在审计表格中**逐行填写**断言调用列表，不允许只写"通过"
3. 降级审计结果标注为 `[self-audit]`（vs 独立 agent 的 `[independent-audit]`），在 quality_audit 输出中区分

### 交叉验证

当模式 A 可用时，独立审计结果和 Phase 4 出口扫描结果按以下协议合并：

| 来源 | 标记 | 处理 |
| --- | --- | --- |
| 独立审计 + 自审都发现问题 | confirmed | 硬性阻断，必须修复 |
| 仅独立审计发现 | independent-only | 回到 Phase 4 修复 |
| 仅自审发现 | self-only | 二次确认后修复 |
| 双方均未发现 | passed | 放行 |

### 降级回退

所有使用本协议的 skill 必须保留降级路径：

- Task 工具不可用 → 降级为模式 B（自审 + Grep）
- Grep 工具不可用 → 降级为纯结构化自审（必须逐方法填写审计表格）
- 任何降级均在 quality_audit 输出中标注 `audit_mode`

## 测试执行报告格式

代码生成类 skill（unit-test-design、integration-test-design）在 verify 阶段尝试执行测试后，将执行结果持久化为 `test_execution_report.json`，供下游 test-failure-analyzer 消费。

```json
{
  "execution_time": "2025-01-15T10:30:00Z",
  "command": "go test ./...",
  "language": "go",
  "exit_code": 1,
  "total_tests": 15,
  "passed": 12,
  "failed": 2,
  "skipped": 1,
  "failures": [
    {
      "test_name": "TestApplyCoupon_MaxDiscount",
      "test_file": "coupon_test.go",
      "error_message": "expected 100 but got 50",
      "stacktrace": "coupon_test.go:42: ...",
      "duration_ms": 150
    }
  ],
  "stdout_tail": "最后 50 行 stdout 输出",
  "stderr_tail": "最后 50 行 stderr 输出"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `execution_time` | string | 是 | 执行时间（ISO 8601） |
| `command` | string | 是 | 执行的测试命令 |
| `language` | string | 是 | 编程语言 |
| `exit_code` | number | 是 | 进程退出码（0 = 全部通过） |
| `total_tests` | number | 是 | 测试总数 |
| `passed` | number | 是 | 通过数 |
| `failed` | number | 是 | 失败数 |
| `skipped` | number | 是 | 跳过数 |
| `failures` | array | 是 | 失败用例详情（全部通过时为空数组） |
| `failures[].test_name` | string | 是 | 测试方法名 |
| `failures[].test_file` | string | 是 | 测试文件路径 |
| `failures[].error_message` | string | 是 | 错误信息 |
| `failures[].stacktrace` | string | 否 | 堆栈信息 |
| `stdout_tail` | string | 否 | 最后 50 行 stdout（调试用） |
| `stderr_tail` | string | 否 | 最后 50 行 stderr（调试用） |

**生成时机**：verify 阶段的 5b 步骤在执行测试命令后，解析测试输出并写入此文件。如果测试命令不可执行（环境不支持），则不生成此文件。

**下游消费**：test-failure-analyzer 的 contract 中 `test_report` 输入可直接指向此文件。
