# 统一约定

本文件定义所有 skill 共享的执行约定。各 SKILL.md 通过引用本文件来保持一致性。

## 编写规范

- `SKILL.md` 顶部优先给出 `Quick Start`，说明适用场景、必要输入、输出产物、失败门控。
- 执行细节拆到 `PHASES.md`、`CHECKLIST.md`、`METHODS.md`、`TEMPLATES.md` 等参考文档。
- 每个 skill 目录下必须包含 `contract.yaml`，定义机器可读的输入输出接口。`contract.yaml` 的编写规范见 [CONTRACT_SPEC.md](CONTRACT_SPEC.md)。
- `description` 统一写成 `做什么 + 最小输入/输出`，避免泛化触发。

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

## 回读中间文件

后续阶段需要引用之前阶段的数据时，**必须通过 Read 工具回读中间文件**，不依赖对话上下文中的记忆。

## 上游输入消费

当 skill 被编排层作为 pipeline 的一环调用时，上游 skill 的输出文件会被放置到工作目录中。

**约定**：如工作目录中已存在上游产出文件（如 `clarified_requirements.json`），优先消费该文件，跳过对应的数据获取步骤。各 PHASES.md 在 fetch/understand 阶段开头检查上游文件是否存在。

## 本地文件输入

当需求来源不是在线链接（飞书/Figma），而是本地文件（如 AI 对话后生成的 `.md` 或 `.json`）时：

1. 通过 `requirement_doc`（或对应的文件参数）传入文件路径
2. 在 init/fetch 阶段检测到本地文件时，跳过在线文档获取步骤
3. 后续分析阶段正常执行，与在线获取的文档等价处理

**输入路由优先级**（各 PHASES.md 的 init/fetch 阶段统一遵循）：

1. 工作目录中已存在上游产出文件 → 优先消费
2. `requirement_doc` 等文件参数提供了本地文件 → Read 本地文件
3. `story_link` 等链接参数为 URL → 调用对应脚本获取
4. 以上均不满足 → 停止并报错（各 skill 可根据自身特性覆盖此默认行为，如 requirement-traceability 支持降级为单边追溯，具体见各 PHASES.md）

**输入路由阶段编号**：输入路由统一放在数据获取阶段（fetch/understand）的 `X.0` 步骤。具体地：如果 skill 有独立的 init 阶段仅做预取验证，输入路由放在 phase 2（`2.0`）；如果 init 阶段包含输入路由逻辑，则放在 phase 1（`1.0`）。

## 系统预取

系统在 skill 启动前自动预取数据并嵌入 prompt。预取失败的数据在 `### 预取警告` 中说明。

通用预取字段（Story 类 skill）：Story 基本信息（名称、状态、project_key、work_item_id）、自定义字段（需求文档链接、设计稿链接、技术文档链接、负责人）。各 skill 可能额外预取特有数据（如需求文档内容、关联代码变更列表），具体字段在各 PHASES.md 顶部的"本 skill 预取字段"中声明。

## 中断恢复

Agent 因 context 截断或异常中断后恢复执行时：

1. 检查工作目录中已生成的中间文件，确认最后完成的阶段
2. 回读中间文件获取已有分析结果
3. 从中断阶段继续执行，不重新执行已完成的阶段
4. 如果中间文件不完整，从该文件对应的阶段重新开始

## 脚本路径约定

所有脚本引用使用相对于 skills 目录的路径：`skills/<skill-name>/scripts/<script>.py`。

运行时通过 `$SKILLS_ROOT` 环境变量定位 skills 目录的绝对路径。在 marketplace 插件中，`$SKILLS_ROOT` 应指向 `plugins/test/skills/`（而非仓库根目录）。如果 `$SKILLS_ROOT` 未设置，skill 应使用 SKILL.md 所在目录的相对路径来定位脚本。

> **注意**：本插件中的部分 skill（如 test-case-generation、requirement-traceability）原设计用于 pipeline 编排系统，其中 `$SKILLS_ROOT` 和「系统预取」由编排层自动处理。独立使用时需手动设置环境变量或手动准备输入文件。

## 环境变量预检

各 skill init 阶段在首次调用脚本前，必须检查该脚本所需的环境变量是否已设置。缺失时输出明确提示（变量名 + 用途 + 设置方式），并降级到不依赖该脚本的路径。

**Python 可用性预检**：首次调用 Python 脚本前检查 `python3 --version` 是否可用。不可用时降级到不依赖脚本的路径。

**脚本失败分类**：`ImportError` / `ModuleNotFoundError` 归类为确定性故障（环境缺失），不重试，直接降级。其他异常可按标准重试策略重试 1 次。

## 输出格式约定

- 结构化数据使用 JSON 格式，供下游 skill 或编排层消费
- 分析过程和中间记录使用 Markdown 格式
- 中间文件命名使用 snake_case
- JSON 文件顶层必须是数组或对象，不能是字符串
- 所有文本使用中文

## 脚本失败重试策略

所有共享脚本调用失败时，统一执行以下重试策略：

1. 检查 stderr 错误信息，判断是否为临时性故障（网络超时、限频、服务端 5xx）
2. 临时性故障：重试至少 2 次，每次间隔 3 秒
3. 确定性故障（参数错误、权限不足、404）：不重试，直接报告错误
4. 脚本执行超过 30 秒无输出：视为临时性故障，终止后重试
5. 3 次尝试后仍失败：记录错误到中间文件，按各 skill 定义的降级策略处理

## 置信度标记

分析结论中使用以下标记标注证据来源：

| 标记 | 含义 |
| --- | --- |
| `[已确认]` | 通过代码/数据/文档验证 |
| `[基于 diff]` | 仅基于 diff 推断 |
| `[推测]` | 合理推测但未验证 |
| `[待确认]` | 需要人工确认 |

## 量化置信度评分

在文本标记（`[已确认]` 等）基础上，引入 0-100 连续量化评分，用于 Agent 间结果合并和阈值过滤。

### 评分标准

| 区间 | 标签 | 含义 | 处理方式 |
| --- | --- | --- | --- |
| 90-100 | 高置信度 | 需求/代码/文档有直接证据，或双 Agent 共识 | 直接使用 |
| 70-89 | 中置信度 | 可从上下文合理推断，或单 Agent 发现 | 带标记使用 |
| 50-69 | 低置信度 | 基于领域知识的合理推测，无直接证据 | 需人工确认 |
| <50 | 丢弃 | 过度推测 | 不纳入输出 |
| `null` | 未验证 | 用例已生成但未经代码推理验证（如降级模式） | 下游按本地策略决定保留或跳过 |

### 与文本标记的映射

| 文本标记 | 量化区间 |
| --- | --- |
| `[已确认]` | 90-100 |
| `[基于 diff]` | 70-89 |
| `[推测]` | 50-69 |
| `[待确认]` | 显式人工确认标记 |

### 跨 Agent 共识规则

同一维度的 2 个 Agent 独立发现同一问题时，如双方原始 confidence 均 >= 70，则加成 `confidence += 20`（封顶 100）；任一方 < 60 则不加成，取两者算术平均值。

"同一问题"的判定标准：相同目标对象（用例/需求点/代码变更）+ 相似描述（语义匹配）。由编排层或主 Agent 在合并阶段判定。

### Pipeline 中的置信度流转

```
requirement-clarification → clarified_requirements.json (functional_point.confidence)
  → test-case-generation → final_cases.json (case.confidence + case.review_confidence)
    → requirement-traceability → traceability_matrix.json (mapping.confidence)
```

下游 skill 消费上游产出时，保留上游 confidence 字段不覆盖，在此基础上追加本阶段的评分字段。

## Agent 定义规范

所有子 Agent 的行为定义统一放在 `agents/` 目录下，作为**单一事实源**。各 PHASES.md 通过文件路径引用 Agent 定义，不内嵌 Agent prompt。

### 目录结构

```
agents/
├── AGENT_TEMPLATE.md                 # 统一模板
├── test-case-writer.md               # 测试用例生成 Agent
├── verification-test-writer.md       # 验证用例生成 Agent
├── failure-classifier.md             # 测试失败分类 Agent (预留)
├── ui-fidelity-checker.md            # UI 还原度检查 Agent
├── requirement-understanding/        # 需求理解多视角 Agent
│   ├── functional-perspective.md
│   ├── exception-perspective.md
│   └── user-perspective.md
├── test-case-generation/              # 测试用例生成评审冗余对
│   ├── review-agent-1.md
│   └── review-agent-2.md
└── requirement-traceability/         # 需求追溯 Agent（反向追溯 + 正向降级回退）
    ├── forward-tracer.md
    └── reverse-tracer.md
```

### 模板结构

每个 Agent 定义文件遵循统一结构（详见 [AGENT_TEMPLATE.md](agents/AGENT_TEMPLATE.md)）：

1. **角色定义** — 一句话描述
2. **模型** — 按模型分层策略选择
3. **执行时机** — 总是启动 / 条件性启动，并行关系
4. **分析重点** — 具体检查维度和检查点
5. **输入** — 输入数据格式和来源
6. **输出格式** — 统一 JSON 结构（agent + findings 数组，每条含 confidence）
7. **置信度评分指南** — 本 Agent 领域的具体评分标准
8. **冗余机制** — 冗余对 Agent 专用，描述对偶关系和共识规则
9. **注意事项** — Agent 特有约束

### 命名约定

- Agent 文件使用 kebab-case：`{角色描述}.md`
- 冗余对使用数字后缀：`review-agent-1.md` / `review-agent-2.md`
- 按功能域分目录：`requirement-understanding/`、`test-case-generation/`、`requirement-traceability/`

## 模型分层策略

按"错误代价"分配模型能力 —— 高风险任务（漏检成本高）使用强模型，中低风险任务使用平衡模型。

| 模型 | 适用任务 | 选择理由 |
| --- | --- | --- |
| Opus | 需求理解/澄清、覆盖度审查、根因分析、代码逻辑分析、安全分析 | 理解力决定质量天花板，漏检代价极高 |
| Sonnet | 测试用例生成、用户视角分析、报告生成、结果合并/去重 | 模板化工作，Sonnet 性价比高 |
| Haiku | 简单格式校验、规则检查（预留） | 速度优先，成本最低 |

各 Agent 定义文件中 `## 模型` 节标注推荐模型。PHASES.md 中的 Task 调用通过 `model` 参数指定。

## 多 Agent 并行执行

### 调用模式

使用 Task 工具并行启动多个 Agent 时，**在单条消息中发送所有 Task 调用**，实现真正并行。

```
Task(subagent_type="generalPurpose", model="opus", description="...", prompt="...")
Task(subagent_type="generalPurpose", model="opus", description="...", prompt="...")
Task(subagent_type="generalPurpose", model="sonnet", description="...", prompt="...")
```

总耗时 = max(单个 Agent 时间)，而非累加。

### 交叉验证协议

多 Agent 结果合并时，按以下协议处理：

1. **收集所有 Agent 结果**（TaskOutput）
2. **按维度分组**：冗余对的两个 Agent 归为同一组
3. **检测重复**：相同目标 + 相似描述 → 视为同一发现
4. **应用共识加成**：同一发现被两个 Agent 独立发现 → confidence += 20
5. **阈值过滤**：≥80 直接报告，60-79 标记人工确认，<60 丢弃

### 部分失败时的结果合并

多个 Agent 并行执行时，可能出现部分 Agent 成功、部分失败的情况。按以下规则处理：

**多视角 Agent（3+ 个独立视角）**：
- N 个 Agent 中有 1 个失败（重试后仍失败）→ 使用其余 N-1 个 Agent 的结果合并，在报告中标注"降级：{失败 Agent 名称} 未参与分析"
- N 个 Agent 中有 2+ 个失败 → 回退到主 Agent 单独分析模式
- 交叉验证时，缺失视角的维度不参与共识加成计算

**冗余对 Agent（2 个独立评审）**：
- 1 个失败（重试后仍失败）→ 使用成功 Agent 的结果作为最终结果，但：
  - 不应用共识加成（无法交叉验证）
  - 所有 findings 的 confidence 封顶 85（缺少独立验证）
  - 在报告中标注"降级：冗余对退化为单 Agent 模式"
- 2 个都失败 → 在主 Agent 中按单 Agent 模式执行

**结果合并时的冲突处理**：
- 同一目标出现矛盾结论（如 Agent A 判为 covered，Agent B 判为 missing）→ 取较低置信度的结论，并在报告中标注冲突（后续由人工裁决）

### 降级回退

所有多 Agent 阶段必须保留单 Agent 回退路径：

- Task 工具不可用 → 在主 Agent 中顺序执行各视角分析
- 需求简单（<3 个功能点）→ 跳过多 Agent，直接单 Agent 分析
- 子 Agent 执行失败 → 重试 1 次，仍失败则按上述"部分失败时的结果合并"规则处理

### 大文档分段策略

当需求文档超过预估 30K tokens 时，子 Agent 应按章节/模块分段 Read，每段独立处理后合并结果。主 Agent 在构造 Task prompt 时应提供文档结构摘要和目标章节范围，避免子 Agent 尝试 Read 完整文档导致 context 溢出。

**Token 估算经验规则**：
- 中文 1 字 ≈ 1.5-2 tokens，英文 1 词 ≈ 1-1.5 tokens
- 单次 Read 建议不超过 15K tokens（约 8000-10000 中文字或 200-300 行代码）
- 分段标准：按 `##` 二级标题或功能模块边界分段

## 功能点编号前缀

| Skill | 前缀 | 用途 |
| --- | --- | --- |
| requirement-clarification | `FP-1` / `FP-2` ... | 功能点编号 |
| test-case-generation (review 阶段) | `RP-1` / `RP-2` ... | 需求验证点编号 |
| requirement-traceability | `R-1` / `R-2` ... | 需求点编号（对照代码变更） |
| verification-test-gen | `VC-1` / `VC-2` ... | 验证用例编号 |

三套编号是同一批需求在不同 skill 作用域下的**独立编号**，不要求一一对应。它们描述的是同一份需求的不同视角：
- `FP-` 是澄清阶段识别的功能点（可能粒度较粗）
- `RP-` 是评审阶段从需求文档中提炼的验证点（可能更细）
- `R-` 是追溯阶段从需求中提取的映射锚点（有上游 FP- 时直接继承作为主键，R- 作为别名）
- `VC-` 是验证用例编号（verification-test-gen 产出，保留上游 `FP-` 作为 `requirement_id` 外键）

下游 skill 消费上游的 `requirement_points.json` 时，按内容重新编号，不继承上游前缀。

### 跨 skill ID 映射

当下游 skill 需要关联来自不同上游的数据时（如 requirement-traceability 同时消费 `requirement_points.json` 的 FP- 编号和自身的 R- 编号），优先采用**编号直接继承**：下游直接使用上游 FP- 编号作为主键关联，同时记录本地 R- 编号作为别名（如 `FP-1 = R-1`）。仅当无上游编号（独立使用）时才使用 R- 独立编号。映射表记录在中间文件中，供后续阶段使用。

## 用例 JSON 格式

所有 skill 生成的测试用例统一使用以下 JSON 格式。各 skill 的 SKILL.md 和 PHASES.md 通过引用本节保持格式一致。

```json
[
  {
    "case_id": "M1-TC-01",
    "title": "用例标题",
    "module": "模块名称",
    "priority": "P0",
    "test_method": "边界值分析",
    "confidence": 85,
    "preconditions": ["前置条件1", "前置条件2"],
    "steps": [
      {"action": "步骤一", "expected": "预期一"},
      {"action": "步骤二", "expected": "预期二"}
    ]
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `case_id` | string | 是 | 模块前缀 + 序号（如 M1-TC-01），review 阶段去重后允许断号 |
| `title` | string | 是 | 用例标题，纯业务描述，禁止包含内部编号 |
| `module` | string | 是 | 模块名称（不带编号前缀） |
| `priority` | string | 是 | P0 / P1 / P2 / P3 |
| `test_method` | string | 是 | 等价类划分 / 边界值分析 / 场景法 / 错误推测法 / 判定表法 / 状态迁移法 |
| `confidence` | number | 否 | 用例置信度（0-100），评分标准见「量化置信度评分」。test-case-generation 阶段生成 |
| `review_confidence` | number | 否 | 评审置信度（0-100），test-case-generation review 阶段冗余对评审后生成 |
| `source` | string | 否 | 用例来源：`generated`（生成阶段产出）/ `supplementary`（评审补充）。test-case-generation output 阶段标记 |
| `preconditions` | string[] | 是 | 前置条件字符串数组 |
| `steps` | array | 是 | 对象数组，每项含 `action`（操作）和 `expected`（预期结果），一一配对 |

### 通用约束

- 文件顶层必须是 JSON 数组
- `priority` 只允许 P0 / P1 / P2 / P3
- 所有文本使用中文
- 用例文本中禁止出现 ASCII 双引号，使用中文引号「」

## 双通道追溯模式

v0.0.10 起，requirement-traceability 采用双通道追溯：

| 通道 | 方向 | 方法 | 回答的问题 |
| --- | --- | --- | --- |
| 正向通道 | 需求 → 代码 | 用例中介验证 | 需求是否被正确实现？ |
| 反向通道 | 代码 → 需求 | 直接代码追溯 | 代码有没有做需求之外的事？ |

**正向通道**将需求拆解为结构化验证用例（具体输入→预期输出），AI 逐条对照代码推理。消费上游 `verification-test-gen` 的 `verification_cases.json`，或内置简化版用例生成。

**反向通道**保持 reverse-tracer Agent 模式，从代码变更出发寻找需求对应。

两个通道并行启动，结果在 output 阶段合并。

## 影响范围分析约定

requirement-clarification 在澄清阶段对已有功能的修改类需求执行影响范围分析。

**数据源优先级**：

1. `module-relations.json`（模块关系索引，由 `spec` 插件的 `module-discovery` 生成维护）→ 读取结构化的模块依赖和实体归属关系
2. 定向代码扫描（限定在主要业务代码目录，不全库扫描）→ 当索引不存在或不足以回答时使用
3. 人工确认 → 将发现的影响范围转为 ask_question 向用户确认

**`module-relations.json` 标准格式**：

```json
{
  "modules": {
    "<module-name>": {
      "owns_entities": ["实体名称"],
      "depends_on": ["依赖的模块"],
      "depended_by": ["被依赖的模块"],
      "exposes_apis": ["暴露的 API"]
    }
  },
  "entity_index": {
    "<entity-name>": {
      "owner_module": "所属模块",
      "referenced_by": ["引用该实体的模块"],
      "reference_type": {
        "<module>": "引用方式描述"
      }
    }
  }
}
```

影响范围分析结果写入 `clarified_requirements.json` 的 `functional_points[].impact_scope` 字段。

## 自循环协议

test-failure-analyzer 和 requirement-traceability 支持自循环：发现问题 → 分析 → 修复/确认 → 重新验证。

### 通用自循环规则

| 规则 | 说明 |
| --- | --- |
| 最大迭代次数 | 3 次（可通过参数覆盖） |
| 人工确认 | 每次修复方案必须让用户确认后再执行，不静默自动修复 |
| 收敛判断 | 第 N+1 轮的未解决问题集合应是第 N 轮的真子集（即数量减少且无新增问题类型）。**推荐采用集合比较**：即使总数减少，新增了上轮不存在的问题项（如新 test_name）→ 标记「部分收敛 + 新增回归」而非完全收敛。仅当总数减少且无新增项时才视为收敛中 |
| 终止条件 | 全部通过 / 达到最大次数 / 不收敛 / 用户主动终止 |

### 测试失败自循环

```
测试执行 → 失败? → AI 分类（预期变化/回归/不稳定）→ 生成修复方案 → 用户确认 → 执行修复 → 重新测试 → ...
```

AI 分类标准：

| 分类 | 判断依据 | 处理策略 |
| --- | --- | --- |
| 预期变化 | 失败断言与本次需求变更直接相关 | 更新测试预期 → 用户确认 |
| 回归问题 | 失败测试与本次变更无直接关联 | 分析根因 → 按严重程度处理 |
| 不稳定 | 时过时不过、依赖外部资源 | 自动重试 1 次 → 仍失败则上报 |

### 需求回溯自循环

```
回溯完成 → 有缺口? → 分类（未实现/多余代码/部分实现）→ 向用户确认 → 补充实现 → 重新回溯 → ...
```

## UI 还原度检查约定

当需求有 Figma 设计稿链接时，requirement-traceability 或独立的 ui-fidelity-check skill 执行 UI 还原度对比。

**工具链**：

| 工具 | 用途 |
| --- | --- |
| Figma MCP `get_screenshot` | 获取设计稿截图 |
| Figma MCP `get_design_context` | 获取结构化设计数据 |
| Browser MCP `browser_take_screenshot` | 获取实现截图 |
| Browser MCP `browser_snapshot` | 获取 DOM 结构 |

**对比维度**：布局结构、间距与尺寸、颜色与样式、字体排版、状态完整性、交互行为。

**还原度评级标准**：

| 评级 | 条件 |
| --- | --- |
| high | 无 high severity 差异，medium 差异 <= 2 |
| medium | high severity 差异 <= 1，或 medium 差异 3-5 |
| low | high severity 差异 >= 2，或 medium 差异 > 5 |

**降级**：页面不可访问时 → structural-only 模式（仅对比设计数据 vs 代码样式定义，跳过截图对比）。

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

## 验证用例 JSON 格式

verification-test-gen 生成的验证用例使用以下格式：

```json
[
  {
    "case_id": "VC-1",
    "requirement_id": "FP-1",
    "requirement_name": "功能名称",
    "case_type": "functional | boundary | error | state",
    "input": {
      "description": "输入描述",
      "params": {}
    },
    "expected": {
      "description": "预期结果描述",
      "assertion": "具体断言表达式"
    },
    "verification": {
      "method": "ai_reasoning | executable",
      "result": "pass | fail | inconclusive",
      "trace": "代码追踪路径",
      "confidence": 85
    }
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `case_id` | string | 是 | VC- 前缀 + 序号 |
| `requirement_id` | string | 是 | 对应的需求功能点编号（FP- 前缀） |
| `requirement_name` | string | 是 | 功能点名称 |
| `case_type` | string | 是 | functional / boundary / error / state |
| `input.description` | string | 是 | 输入场景的文字描述 |
| `input.params` | object | 是 | 具体的输入参数键值对 |
| `expected.description` | string | 是 | 预期结果的文字描述 |
| `expected.assertion` | string | 是 | 可验证的断言表达式 |
| `verification.method` | string | 是 | 验证方式：ai_reasoning（AI 推理）/ executable（可执行测试） |
| `verification.result` | string | 是 | pass / fail / inconclusive |
| `verification.trace` | string | 否 | 代码追踪路径（AI 推理验证时的推理链） |
| `verification.confidence` | number \| null | 是 | 0-100 置信度；降级模式（无代码可验证）时为 `null`，含义见「量化置信度评分」|

## 术语表

| 术语 | 含义 |
| --- | --- |
| TapSDK | 公司自研客户端 SDK，负责数据采集、推送和基础服务能力 |
| DE（数仓） | Data Engineering 数据工程团队，负责数据仓库和数据管道 |
| IEM | ‍智能化引擎与商业化 ，其业务范围涵盖搜索、广告、推荐领域 |
