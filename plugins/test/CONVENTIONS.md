# 统一约定

本文件定义所有 skill 共享的执行约定。各 SKILL.md 通过引用本文件来保持一致性。

## 编写规范

- `SKILL.md` 顶部优先给出 `Quick Start`，说明适用场景、必要输入、输出产物、失败门控。
- 执行细节拆到 `PHASES.md`、`CHECKLIST.md`、`METHODS.md`、`TEMPLATES.md` 等参考文档。
- 每个 skill 目录下必须包含 `contract.yaml`，定义机器可读的输入输出接口。`contract.yaml` 的编写规范见 [CONTRACT_SPEC.md](CONTRACT_SPEC.md)。
- `description` 统一写成 `做什么 + 最小输入/输出`，避免泛化触发。

## 阶段执行保障

适用于所有包含多阶段流程的 skill。

1. **阶段必须按序执行**：不允许跳过、合并或重排阶段。
2. **阶段结束 ≠ skill 结束**：某个中间阶段的退出条件满足后，必须继续执行下一阶段，而非终止 skill。
3. **产物文件必须生成**：skill 的 `contract.yaml` 中定义的所有 `output.files` 必须在最终阶段生成，缺少任一文件即为执行失败。
4. **禁止提前进入下游操作**：在所有阶段完成前，不允许执行下游操作（如创建实施计划、开始编码、调用其他 skill）。
5. **完成验证**：最终阶段结束后，逐一校验产物文件是否存在且内容有效，全部通过后才能声明完成。

## 断言审计协议

详见 [skills/_shared/ASSERTION_AUDIT.md](skills/_shared/ASSERTION_AUDIT.md)。

## 独立验证者协议

详见 [skills/_shared/ASSERTION_AUDIT.md](skills/_shared/ASSERTION_AUDIT.md)。

## 回读中间文件

后续阶段需要引用之前阶段的数据时，**必须通过 Read 工具回读中间文件**，不依赖对话上下文中的记忆。

## 上游输入消费

当 skill 被编排层作为 pipeline 的一环调用时，上游 skill 的输出文件会被放置到工作目录中。

**约定**：如工作目录中已存在上游产出文件（如 `clarified_requirements.json`），优先消费该文件，跳过对应的数据获取步骤。各 PHASES.md 在 fetch/understand 阶段开头检查上游文件是否存在。

> 当 `$TEST_WORKSPACE` 已设置时，本节中的「工作目录」指 `$TEST_WORKSPACE` 所指向的目录。

## 输出工作区

通过本地 AI 工作流（非 pipeline 编排）调用多个 skill 时，各 skill 的产物默认散落在各自目录中，无法按需求维度组织。输出工作区解决这一问题。

### `$TEST_WORKSPACE` 环境变量

| 状态 | 行为 |
| --- | --- |
| 已设置 | 所有 skill 的输出文件写入 `$TEST_WORKSPACE`，上游文件也从该目录查找 |
| 未设置 | 行为不变（写入当前工作目录），向后兼容 |

### 命名约定

工作区目录位于 `plugins/test/workspace/` 下，以需求名 kebab-case 命名：

```
plugins/test/workspace/
├── add-coupon-feature/          # 需求1：所有 skill 产物汇聚于此
│   ├── clarification_log.md
│   ├── clarified_requirements.json
│   ├── requirement_points.json
│   ├── final_cases.json
│   ├── traceability_matrix.json
│   └── ...
└── user-registration-refactor/  # 需求2
    └── ...
```

`workspace/` 目录已加入 `.gitignore`，不会被提交。

### 本地工作流示例

```bash
export TEST_WORKSPACE=plugins/test/workspace/add-coupon-feature
mkdir -p $TEST_WORKSPACE
# 1. 运行 requirement-clarification → 产出写入 $TEST_WORKSPACE
# 2. 运行 test-case-generation → 从 $TEST_WORKSPACE 找到上游文件，产出也写入此处
# 3. 运行 requirement-traceability → 同上
```

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

## ask_question 输出格式

所有 skill 需要向用户提问并等待回答时，**必须**使用以下结构化格式输出，确保平台能将问题渲染为可点击的交互式卡片。

### 格式规范

输出一行 `AskUserQuestion` 标记，紧接一个 JSON code fence：

````
AskUserQuestion
```json
{
  "questions": [
    {
      "question": "完整的问题文本",
      "header": "简短标题（2-6 字）",
      "options": [
        {"label": "选项显示文本"},
        {"label": "另一选项", "description": "补充说明（可选）"}
      ],
      "multiSelect": false
    }
  ]
}
```
````

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `questions` | array | 是 | 问题列表，每次 3-5 个 |
| `questions[].question` | string | 是 | 完整问题描述 |
| `questions[].header` | string | 是 | 简短标题，用于卡片标题栏 |
| `questions[].options` | array | 是 | 选项列表，至少 2 个 |
| `questions[].options[].label` | string | 是 | 选项显示文本 |
| `questions[].options[].description` | string | 否 | 选项补充说明 |
| `questions[].multiSelect` | boolean | 否 | 是否允许多选，默认 `false` |

### 约束

- 每次提问控制在 **3-5 个问题**
- 每个问题必须提供 **选项或默认值**，降低用户认知负担
- `AskUserQuestion` 标记行前后不要夹杂其他文字；分析说明放在标记行之前单独输出
- 不要在 JSON 中使用 Markdown 格式（如 `**加粗**`），保持纯文本

### 示例

```
分析完成，需要您确认以下信息：

AskUserQuestion
```json
{
  "questions": [
    {
      "question": "本次需求涉及哪些平台？",
      "header": "平台范围",
      "options": [
        {"label": "仅前端（iOS/Android/Web/PC）"},
        {"label": "仅后端"},
        {"label": "前后端同时修改"},
        {"label": "多端同步", "description": "请在回复中列出具体平台"}
      ],
      "multiSelect": false
    },
    {
      "question": "核心变更是什么？请选择最接近的描述",
      "header": "核心变更",
      "options": [
        {"label": "新增功能模块"},
        {"label": "修改现有功能逻辑"},
        {"label": "UI/交互调整"},
        {"label": "性能优化/重构"}
      ],
      "multiSelect": true
    }
  ]
}
```
```

## 脚本失败重试策略

所有共享脚本调用失败时，统一执行以下重试策略：

1. 检查 stderr 错误信息，判断是否为临时性故障（网络超时、限频、服务端 5xx）
2. 临时性故障：重试至少 2 次，每次间隔 3 秒
3. 确定性故障（参数错误、权限不足、404）：不重试，直接报告错误
4. 脚本执行超过 30 秒无输出：视为临时性故障，终止后重试
5. 3 次尝试后仍失败：记录错误到中间文件，按各 skill 定义的降级策略处理

## 条件触发章节的数据充分性门控

条件触发的分析步骤或报告章节，在触发条件满足后，仍需通过**数据充分性检查**。源材料中不存在该章节所需的具体信息时，必须跳过该章节，不得凭推测生成内容。

### 三级判定

| 级别 | `evidence` 值 | 含义 | 处理方式 |
| --- | --- | --- | --- |
| 充分 | `"sufficient"` | 源材料有明确可引用的信息（如 API 路径、字段定义、代码引用） | 正常生成该章节 |
| 部分 | `"partial"` | 有零散线索但不完整（如设计稿表单字段暗示请求字段，但无路径/方法） | 仅输出有 `source` 标注的内容，缺失部分生成澄清问题，不填充推测值 |
| 无 | `"none"` | 源材料中无任何相关技术信息 | **整节跳过**，不生成任何内容 |

### 核心规则

1. **禁止凭推测生成内容**：每个输出字段必须标注 `source`（document / design / code / human）。无 source 标注的字段不得出现在输出中
2. **跳过优于捏造**：信息不足时跳过整节，远好于生成看似合理但无依据的内容
3. **报告输出规则**：`evidence: "none"` 时报告中省略该章节，可选输出一行占位说明（如 "API 契约信息不足，待技术方案补充后确认"）；`evidence: "partial"` 时章节需加前缀说明 "以下仅包含源材料中明确提及的信息"

### 适用范围

此约定适用于所有 skill 中的条件触发章节。各 PHASES.md 应在条件触发步骤中引用此约定执行数据充分性检查。

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

详见 [skills/_shared/AGENT_PROTOCOL.md](skills/_shared/AGENT_PROTOCOL.md)。

## 模型分层策略

按"错误代价"分配模型能力 —— 高风险任务（漏检成本高）使用强模型，中低风险任务使用平衡模型。

| 模型 | 适用任务 | 选择理由 |
| --- | --- | --- |
| Opus | 需求理解/澄清、覆盖度审查、根因分析、代码逻辑分析、安全分析 | 理解力决定质量天花板，漏检代价极高 |
| Sonnet | 测试用例生成、用户视角分析、报告生成、结果合并/去重 | 模板化工作，Sonnet 性价比高 |
| Haiku | 简单格式校验、规则检查（预留） | 速度优先，成本最低 |

各 Agent 定义文件中 `## 模型` 节标注推荐模型。PHASES.md 中的 Task 调用通过 `model` 参数指定。

## 多 Agent 并行执行

详见 [skills/_shared/AGENT_PROTOCOL.md](skills/_shared/AGENT_PROTOCOL.md)。

## 功能点编号前缀

| Skill | 前缀 | 用途 |
| --- | --- | --- |
| requirement-clarification | `FP-1` / `FP-2` ... | 功能点编号 |
| test-case-generation (review 阶段) | `RP-1` / `RP-2` ... | 需求验证点编号 |
| requirement-traceability | `R-1` / `R-2` ... | 需求点编号（对照代码变更） |
| verification-test-generation | `VC-1` / `VC-2` ... | 验证用例编号 |

三套编号是同一批需求在不同 skill 作用域下的**独立编号**，不要求一一对应。它们描述的是同一份需求的不同视角：
- `FP-` 是澄清阶段识别的功能点（可能粒度较粗）
- `RP-` 是评审阶段从需求文档中提炼的验证点（可能更细）
- `R-` 是追溯阶段从需求中提取的映射锚点（有上游 FP- 时直接继承作为主键，R- 作为别名）
- `VC-` 是验证用例编号（verification-test-generation 产出，保留上游 `FP-` 作为 `requirement_id` 外键）

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
| `title` | string | 是 | 用例标题，纯业务描述。禁止包含：内部编号、优先级前缀（P0/P1/P2/P3）、测试方法或分类前缀（如「等价类-有效类：」「等价类-无效类：」「场景法：」等）。这些信息已由 `priority` 和 `test_method` 字段承载 |
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

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## 影响范围分析约定

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## 自循环协议

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## UI 还原度检查约定

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## 测试执行报告格式

详见 [skills/_shared/ASSERTION_AUDIT.md](skills/_shared/ASSERTION_AUDIT.md)。

## 验证用例 JSON 格式

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## 术语表

| 术语 | 含义 |
| --- | --- |
| TapSDK | 公司自研客户端 SDK，负责数据采集、推送和基础服务能力 |
| DE（数仓） | Data Engineering 数据工程团队，负责数据仓库和数据管道 |
| IEM | ‍智能化引擎与商业化 ，其业务范围涵盖搜索、广告、推荐领域 |
| 冗余对评审 | 2 个独立 Agent 对同一输入并行评审，合并结果时对共识发现加成置信度 |
| 正向追溯 | 需求 → 验证用例 → 代码，验证需求是否被实现 |
| 反向追溯 | 代码变更 → 需求，验证代码变更是否有需求支撑 |
| 数据充分性门控 | 条件触发的分析章节在信息不足时跳过，不凭推测生成内容 |
| 置信度加成 | 2+ Agent 独立确认同一发现时 confidence += 20（封顶 100） |
