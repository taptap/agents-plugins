# 测试用例生成各阶段详细操作指南

## 大文件写入规则（全阶段适用）

Write 工具的 `content` 参数受 LLM 输出 token 上限约束。超限时 JSON 会在中途截断，导致 `JSON Parse error: Expected '}'` 工具调用失败。遵循以下规则：

- **JSON 文件（用例集）**：超过 50 条用例时，用 Bash 执行 Python 脚本完成文件合并/写入，不要通过 Write 工具直接输出大 JSON
- **Markdown 文件（评审报告）**：控制在 200 行以内，只记录结论摘要，不要复制 Agent 原始输出的完整内容
- **通用判断**：如果预估 Write content 超过 4000 字符，改用 Bash + Python 脚本写入

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 额外预取：测试用例链接、需求文档内容（预下载到 `requirement_doc.md`）。

## 阶段 1: init - 初始化

> 如果系统预取了数据，本阶段仅需验证和确认。

1. 检查预取数据：Story 名称、需求文档链接、设计稿链接
2. 记录 `work_item_id` 和 `project_key`
3. 回退：预取数据缺失时基于已有信息继续

### 1.5 重入检查

检查 `re_entry_phase` 参数：

1. **未提供** → 正常从 init 开始执行
2. **已提供** → 执行前置文件校验：
   - 确认工作目录中存在该阶段之前所有阶段的必要产物文件
   - 校验依据：
     - `understand` → 需要 `requirement_doc.md` 或上游 `clarified_requirements.json`
     - `decompose` → 需要 `requirement_doc.md` + `sufficiency_assessment.json`
     - `generate` → 需要 `decomposition.md`
     - `review` → 需要 `module_*_cases.json`（至少 1 个）
   - 前置文件缺失 → 停止并报错「重入失败：缺少 {file}，请从更早的阶段开始」
   - 前置文件存在 → 跳到指定阶段开始执行

3. **如同时提供了 `requirement_change_summary`**：
   - 将变更摘要追加到 `requirement_change_log.md`（追加模式，带时间戳，格式 `## YYYY-MM-DD HH:MM 变更`）
   - 重入 `understand` 时：重新执行需求理解（含充分性门控），变更摘要作为额外上下文注入分析
   - 重入 `decompose` 时：回读已有 `decomposition.md`，仅更新受变更影响的模块拆解，保留未变更模块
   - 重入 `generate` 时：回读 `decomposition.md` 获取模块清单及各模块功能描述，将 `requirement_change_summary` 与每个模块的功能描述比对，判断变更是否影响该模块。仅重新生成受影响模块的 `module_{N}_cases.json`，保留未受影响模块的已有文件
   - 重入 `review` 时：全量重新评审（变更可能影响跨模块覆盖度），从 5.1 合并开始

## 阶段 2: understand - 需求理解

本阶段目标：深入理解需求的业务背景、功能逻辑和交互细节。

### 2.0 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认需求来源：

1. 工作目录中存在上游产出文件（`clarified_requirements.json`）→ 直接读取，跳过 2.1（需求文档获取）；仍执行 2.2（设计稿）和 2.3（技术文档）以获取最新数据
2. 如存在 `requirement_points.json` → 读取作为功能点清单的参考
3. `requirement_doc` 参数提供了本地文件 → Read 本地文件作为需求文档，跳过 2.1 的在线获取
4. `story_link` 参数为 URL → 执行 2.1 在线获取
5. 以上均不满足 → 停止并报错

### 2.1 获取并阅读需求文档

- 如 `requirement_doc` 参数提供了本地文件：直接 Read 该文件
- 如 `requirement_doc.md` 已预下载：直接 Read
- 如未预下载，使用脚本获取：
  ```bash
  python3 $SKILLS_ROOT/shared-tools/scripts/fetch_feishu_doc.py \
    --url "<需求文档链接>" --output-dir . 2>fetch_meta.json
  ```
- 需求文档链接为空且无上游输入和本地文件时停止并报告错误

### 2.2 获取设计稿（如有）

- Figma 链接：使用 `get_figma_data` 获取结构化设计数据
- 飞书文档链接：使用 `fetch_feishu_doc.py` 获取
- 关注：页面状态（默认/空/加载/错误）、交互触发条件、条件展示逻辑

### 2.3 获取技术文档（如有）

如预取数据包含技术文档链接，使用 `fetch_feishu_doc.py` 获取。重点提取：接口字段定义、状态枚举值、业务规则约束。

### 2.5 需求充分性门控

在进入多视角分析或功能拆解之前，对已收集的全部输入材料（需求文档、设计稿、技术文档、上游澄清结果）进行最低充分性评估。复用 [CONVENTIONS.md](../../CONVENTIONS.md#条件触发章节的数据充分性门控) 的三级判定模式。

#### 评估维度

| 维度 | `sufficient` | `partial` | `none` |
| --- | --- | --- | --- |
| 功能范围 | 3+ 个可区分的功能行为，边界清晰 | 1-2 个功能行为，或行为描述但边界模糊 | 无法识别任何具体功能行为（如「优化登录体验」） |
| 验收标准 | 有明确的业务规则或可验证条件 | 有隐含规则但未明确表述（如设计稿暗示但无文字说明） | 无规则、无条件、无可验证的预期 |
| 输入输出 | 描述了字段、数据结构、UI 元素或接口参数 | 部分字段定义或仅有 UI 草图无逻辑说明 | 无数据模型、无字段描述、无接口信息 |
| 状态/流程 | 描述了状态流转、业务流程或用户操作路径 | 部分流程或仅单步描述，缺少完整路径 | 无流程信息、无状态定义 |

#### 消费上游信号

**信号来源 1：工作目录中的 `clarified_requirements.json`**（上游 requirement-clarification 产出）

- `confidence_level == "low"` → 等同于存在 none 维度，触发暂停
- `open_question_count > 3` → 触发暂停，提示用户先解决未澄清问题
- 存在 `clarification_status == "unconfirmed"` 的功能点 → 在充分性报告中标注，不单独触发暂停

**信号来源 2：prompt 末尾平台注入的「同 Story 已完成的分析（上游参考信息）」块**

平台后端会把同一 Story 下已完成的 `requirement_review` / `change_analysis` 结构化摘要注入到 prompt 末尾。当存在该块时，按以下规则消费：

- **`requirement_review` 块**（来自 RR workflow `extract_story_output`）：
  - `verdict == "not_ready"` → **强制暂停**：直接调用 AskUserQuestion 提示用户「需求评审判定 not_ready，建议先解决阻断项后再生成用例」，3 个选项（修复需求 / 继续生成并标注风险 confidence_ceiling=50 / 终止）
  - `verdict == "ready_with_conditions"` → 不暂停，但在 `context_summary.md` 中标注"基于 RR 条件就绪状态生成"，受影响的功能点 confidence 上限设为 80
  - `blocking_issues` 列表非空 → 在阶段 4 多视角分析时，**优先把每条 blocking_issue 转化为待覆盖的异常场景**，不能漏

- **`change_analysis` 块**（来自 CA workflow `extract_story_output`）：
  - `new_features` 列表非空 → **必须为每条 new_feature 至少生成 1 条用例**，在用例 metadata 标注 `source: ca_new_feature`，避免漏覆盖变更新增功能点
  - `changed_modules` → 拆解模块时（阶段 3）优先按这个清单对齐，模块名命中的优先级高
  - `risk_count > 0` 或 `risk_breakdown.high > 0` → 在阶段 4 加入"风险点专项验证"维度，每个 high 风险至少 1 条针对性用例

- **冲突处理**：若 RR `verdict == "not_ready"` 同时 CA 有 `new_features`，**仍以 RR 暂停为准**，CA 信息留待用户决策后消费

- **缺失即跳过**：上游块本身不存在或字段缺失 → 不阻断、不暂停，按其他信号正常推进

#### 决策逻辑

1. **全部 sufficient** → 正常继续，设 `confidence_ceiling = 100`
2. **全部至少 partial（无 none）** → 继续执行但设 `confidence_ceiling = 70`，后续生成的所有用例 confidence 封顶于此值
3. **任一维度 none 且无上游 clarified_requirements** → 暂停，向用户呈现充分性报告并请求决策：

调用 AskUserQuestion 工具（按 [输出溯源原则](../../CONVENTIONS.md#输出溯源原则) 标注 `evidence_tag` + `evidence_ref`，本场景是固定处置选项，标 `derived` 且 `evidence_ref` 必须含 `sufficiency_assessment.json` 中具体维度名的原文摘录。下方示例的 `{维度名}` 是占位符，AI 必须替换为真实维度名如 `performance` / `error_handling`，保留花括号视为违规）：

```json
{
  "questions": [
    {
      "question": "需求文档在以下维度信息不足，可能导致生成的用例包含推测性内容：\n{逐维度列出 none/partial 的具体缺失说明}\n\n您希望如何处理？",
      "header": "充分性检查",
      "evidence_ref": "sufficiency_assessment.json 中『{具体维度名}: none』",
      "options": [
        {"label": "补充需求信息", "description": "请在回复中补充缺失的内容，将重新评估", "evidence_tag": "derived", "evidence_ref": "sufficiency_assessment.json『{维度名}: none』"},
        {"label": "继续生成（标注风险）", "description": "用例将标记为低置信度（上限 50），需人工逐条确认", "evidence_tag": "derived", "evidence_ref": "sufficiency_assessment.json『{维度名}: none』"},
        {"label": "终止生成", "description": "建议先完善需求或执行 requirement-clarification 后重试", "evidence_tag": "derived", "evidence_ref": "sufficiency_assessment.json『{维度名}: none』"}
      ],
      "multiSelect": false
    }
  ]
}
```

#### 补充循环

- 用户选择「补充需求信息」→ 将补充内容合并到 `requirement_doc.md`（追加到末尾，标注「用户补充」），重新执行 2.5 评估
- 最多循环 **2 次**，第 3 次仍不足 → 仅提供「继续生成（标注风险）」和「终止生成」两个选项
- 用户选择「继续生成（标注风险）」→ 设 `confidence_ceiling = 50`
- 用户选择「终止生成」→ 停止 skill，写入 `sufficiency_assessment.json` 后输出错误信息

#### 产物

写入 `sufficiency_assessment.json`：

```json
{
  "overall": "sufficient | partial | insufficient",
  "dimensions": {
    "functional_scope": {"level": "sufficient", "evidence": "识别到 5 个独立功能：..."},
    "acceptance_criteria": {"level": "partial", "evidence": "仅有隐含规则..."},
    "input_output": {"level": "sufficient", "evidence": "文档描述了 3 个表单字段..."},
    "state_flow": {"level": "none", "evidence": "未提及任何状态流转或操作流程"}
  },
  "upstream_signals": {
    "has_clarified_requirements": false,
    "confidence_level": null,
    "open_question_count": 0,
    "unconfirmed_points": [],
    "rr_verdict": null,
    "rr_blocking_count": 0,
    "ca_new_feature_count": 0,
    "ca_high_risk_count": 0
  },
  "user_decision": "proceed_with_risk | supplemented | aborted | null",
  "confidence_ceiling": 100,
  "supplement_rounds": 0
}
```

#### 阶段 2.5 完成检查（强制）

使用 Glob 工具确认 `sufficiency_assessment.json` 存在且非空。`user_decision == "aborted"` 时停止 skill。

### 2.4 多视角并行分析（条件启动）

> 仅当无上游 `clarified_requirements.json` 且需求复杂（>= 3 个功能点 + 文本 > 2000 字）时启动。
> 上游已通过 requirement-clarification 做过多视角分析时跳过。

在**单条消息**中同时发送 3 个 Task 调用，使用 [agents/requirement-understanding/](../../agents/requirement-understanding/) 下的 Agent 定义。

**Task prompt 示例**（以 functional-perspective 为例，其余两个结构相同）：

```
你是功能视角分析 Agent。请先 Read agents/requirement-understanding/functional-perspective.md 获取你的完整角色定义和输出格式要求。

## 需求文档
请 Read ./requirement_doc.md 获取完整需求文档。

## 任务
按角色定义中的「分析重点」逐项分析，输出 JSON 格式的 findings。
每条 finding 必须包含 confidence 评分（0-100）。
```

- **functional-perspective**：指定 `model="opus"`
- **exception-perspective**：指定 `model="opus"`
- **user-perspective**：指定 `model="sonnet"`

主 Agent 在收到 3 个 Task 结果后执行合并：
1. 收集三个 Agent 的 findings 数组
2. 按 `category` 分组，比对 — 相同功能点 + 相似描述 → 同一发现，confidence += 20
3. 合并后的 findings 作为 decompose 阶段的补充输入，交叉验证的发现（2+ Agent 确认，confidence ≥ 80）在拆解时优先考虑

**降级回退**：
- 需求简单（< 3 功能点**且**文本 ≤ 2000 字**且** `sufficiency_assessment.overall == "sufficient"`）→ 跳过多视角 Agent 调用，但主 Agent 仍执行单视角快速分析（功能 + 异常两个维度，各 3-5 条 findings），作为 decompose 阶段的补充输入
- 需求简单但 `sufficiency_assessment.overall != "sufficient"` → 不跳过，执行完整多视角分析（信息不足的需求需要更多交叉验证）
- Task 工具不可用 → 在主 Agent 中顺序执行三个视角的分析（功能→异常→用户），不跳过

## 阶段 3: decompose - 功能拆解

### 3.0 简单需求快速路径

如需求功能点 < 3 个（从上游 `requirement_points.json` 或文档分析判断）：

- **充分 + 简单**（`sufficiency_assessment.overall == "sufficient"`）→ 仍走快速路径，但**必须生成 `decomposition.md`**（即使单模块也要列出功能描述、验收标准、适用测试方法、需覆盖场景），跳过 `context_summary.md`，进入阶段 4 的直接生成模式（4.2）
- **不充分 + 简单**（`sufficiency_assessment.overall != "sufficient"`）→ **不走快速路径**，执行完整的 3.1-3.2 流程。信息不足的需求需要更多结构化分析而非更少

### 3.1 拆解功能模块

基于需求理解（或上游 `clarified_requirements.json`），将需求拆解为独立的功能模块：

- 一个独立的页面/视图 → 一个模块
- 一组相关的 CRUD 操作 → 一个模块
- 一个独立的业务流程 → 一个模块

### 3.2 为每个模块定义测试范围

根据模块功能特征，识别适用的测试设计方法（参考 SKILL.md「方法选择指引」）。

```markdown
### 模块 {N}: {模块名称}

**功能描述**：{该模块做什么}

**验收标准**：
1. {具体可验证的标准}

**适用测试方法**：
- {方法1}：{应用点说明}

**需要覆盖的场景**：
- 正向：{正常使用流程}
- 边界：{边界值场景}
- 异常：{异常路径场景}

**预估用例数**：约 X-Y 条
```

### 3.3 提炼全局上下文摘要

从需求文档（或上游 `clarified_requirements.json`）中提炼跨模块的全局上下文，写入 `context_summary.md`。控制在 500-1500 字。按需包含：产品背景、用户角色、全局业务规则、数据约束、关键状态定义、共用交互约定。

### 3.4 输出

1. 将拆解结果写入 `decomposition.md`
2. 将全局上下文写入 `context_summary.md`

**拆解决策**：
- 模块 < 3 个：不拆分子 Agent，跳过 `context_summary.md`
- 模块 >= 3 个：使用子 Agent 并行生成，必须生成 `context_summary.md`

### 阶段 3 完成检查（强制）

使用 Glob 工具确认以下文件存在：

1. `decomposition.md` — 必须存在且非空；缺失则补生成
2. `context_summary.md` — 模块 >= 3 时必须存在；缺失则补生成
3. **停止条件**：`decomposition.md` 补生成后仍为空 → **停止整个 skill**，输出错误「功能拆解失败，无法继续」

## 阶段 4: generate - 并行生成

### 4.1 使用子 Agent 生成（模块 >= 3 个）

对每个功能模块，通过 Task 工具调用 test-case-writer 子 Agent。Agent 的完整行为定义见 [agents/test-case-writer.md](../../agents/test-case-writer.md)。

**Task 调用要点**：

1. 不要将 `context_summary.md` 内联到 Task prompt，Agent 会自行 Read
2. 只需提供：模块名称、模块需求（从 `decomposition.md` 中提取）、适用测试方法、模块索引
3. 指定 `model="sonnet"`（按模型分层策略，用例生成使用 Sonnet）
4. 每条用例必须包含 `confidence` 字段（0-100），评分标准见 Agent 定义文件
5. Task prompt 中告知 `confidence_ceiling` 值（从 `sufficiency_assessment.json` 读取）：生成的用例 `confidence` 不得超过此值

**并行策略**：在单条消息中同时发起所有模块的 Task 调用，实现真正并行。

### 4.1.1 子 Agent 失败处理

1. Task 返回后用 Glob 确认 `module_{index}_cases.json` 是否存在
2. 文件不存在或为空：重试 1 次
3. JSON 格式错误：MCP tool `mcp__cases__save_test_cases` 已在生成阶段强约束字段，理论上不会出现格式错；如确实失败说明逻辑错（如 cases 数组为空、文件路径越权），按错误信息修正后重试
4. 重试仍失败：在主 Agent 中直接生成
5. 所有模块处理完后再进入 review 阶段

### 4.2 直接生成（模块 < 3 个，或简单需求快速路径）

在主 Agent 中按模块顺序生成所有用例，调用 `mcp__cases__save_test_cases(file_path='<workdir>/module_{N}_cases.json', cases=[...])` 写入对应模块文件（N 从 1 开始）。简单需求快速路径（阶段 3.0）视为单模块，写入 `module_1_cases.json`。**禁止用 Write 工具直接写 *_cases.json**。

生成前回读 `sufficiency_assessment.json` 获取 `confidence_ceiling`，所有用例的 `confidence` 不得超过此值。

### 阶段 4 完成检查（强制）

使用 Glob 工具搜索 `module_*_cases.json`，将结果与 `decomposition.md` 中的模块清单逐一比对：

1. **逐模块校验**：对每个模块 N，检查 `module_{N}_cases.json` 是否在 Glob 结果中存在
2. **缺失处理**：文件不存在 → 重试子 Agent 1 次；重试仍失败 → 在主 Agent 中直接生成该模块用例（fallback）
3. **非空校验**：文件存在但 Read 后内容为空或非合法 JSON 数组 → 删除后按缺失处理
4. **停止条件**：fallback 生成后文件仍为空 → **停止整个 skill**，输出错误「模块 {N} 用例生成失败，无法继续」

全部模块文件校验通过后，方可进入阶段 5。

## 阶段 5: review - 自审 + 冗余对评审

本阶段包含两个子流程：先做快速自审（去重 + 覆盖度检查），再启动冗余对 Agent 做 4 维度深度评审。

### 5.1 合并 module 文件为 test_cases.json

将所有 `module_{N}_cases.json` 合并为单个 `test_cases.json`（顶层 JSON 数组）。每条用例的 `module` 字段标识归属模块，`confidence` 字段保留。

**实现方式**：用 Bash 脚本（jq 或 Python）做纯数据合并 —— 读取所有 `module_*_cases.json`、concat 成数组、写入 `test_cases.json`。Bash 脚本不经过 LLM 输出层，避免 token 截断；数据已是 MCP tool 校验过的合法用例，无需再走 schema 校验。

> 模型有强烈偏好走 `mcp__cases__save_test_cases` 时也允许，但用例数 > 50 条会触发 token 截断风险，优先用 Bash。

### 5.2 快速自审

> 格式校验（priority 合规、steps/expected 配对、字段名拼写）由 `mcp__cases__save_test_cases` 的 input_schema 在生成阶段强制，违反直接被 API 拒绝。本节只关注内容质量（去重、覆盖度、置信度），不必再操心字段格式。

**跨模块去重**（两步法）：
1. **字面去重**（快速）：使用 Grep 搜索 `test_cases.json` 中的 `"title"` 字段，标记完全相同或高度相似的标题对
2. **语义去重**（精确）：对 Grep 未标记但 title 语义相似的用例对（如「验证空密码登录」vs「密码为空时登录」），由 AI 逐对比对判定是否为实质性重复

有重复则保留更完整的，删除冗余。

**覆盖度检查**：回读 `decomposition.md`，逐模块检查每个验收标准是否有对应用例，是否覆盖了边界和异常场景。

**方法覆盖度检查**：核对 `decomposition.md` 中的「适用测试方法」与实际生成用例的 `test_method` 字段。缺失方法的补充用例直接追加到 `test_cases.json`。

**置信度过滤**：
- confidence < 50 → 删除（过度推测）
- 50 ≤ confidence < 70 → 标记为「需人工确认」（保留但标注）
- confidence ≥ 70 → 正常保留

自审完成后将修改后的结果写回 `test_cases.json`：少量改动（如删除几条、补充少量用例）调用 `mcp__cases__save_test_cases`；大批量改动建议先 Read + Bash 脚本处理后写回。**禁止用 Write 直接写 *_cases.json**。

### 5.3 提炼需求功能点清单（供评审使用）

如果工作目录中已存在上游 `requirement_points.json`，直接使用。

否则，基于需求文档和 `decomposition.md`，提炼编号功能点清单写入 `requirement_points.md`：

```markdown
### 模块A: xxx

- RP-1: {功能点} — 验收标准: {标准}
- RP-2: {功能点} — 验收标准: {标准}
```

规则：`RP-` 前缀全局递增，按模块分组，每个功能点含描述 + 验收标准。

### 5.4 启动冗余对评审

#### 5.4.0 大用例集分批

当 `test_cases.json` 中用例数超过 50 条时，按 `module` 字段分批（每批 20-30 条），每批独立构造 Task prompt 发送给两个 review Agent。各批次的 Agent 结果在 5.6 统一合并。

用例数 ≤ 50 时，全量发送给 Agent（不分批）。

#### 5.4.1 Task 调用

在**单条消息**中同时发送 2 个 Task 调用（如分批则每批各 2 个），使用 [agents/test-case-generation/](../../agents/test-case-generation/) 下的 Agent 定义。

**Task prompt 示例**（以 review-agent-1 为例，review-agent-2 结构相同）：

```
你是测试评审 Agent #1。请先 Read agents/test-case-generation/review-agent-1.md 获取你的完整角色定义和输出格式要求。

## 输入数据
1. 请 Read ./requirement_points.md（或 ./requirement_points.json）获取需求功能点清单
2. 请 Read ./test_cases.json 获取待评审的测试用例
3. 请 Read $SKILLS_ROOT/test-case-generation/CHECKLIST.md 获取 4 维度评审检查项
4. 如存在 ./context_summary.md 或 ./decomposition.md，请 Read 获取补充上下文
5. 如存在 ./sufficiency_assessment.json，请 Read 获取需求充分性评估结果

## 任务
按角色定义独立执行评审，输出 JSON 格式的 dimension_scores + findings + coverage_gaps。
如 sufficiency_assessment.overall 不为 "sufficient"，在评审过程中启动推测性内容审查（角色定义中的第 3 节），将推测性细节纳入 findings 输出。
```

- **review-agent-1**：Agent 定义见 [review-agent-1.md](../../agents/test-case-generation/review-agent-1.md)，指定 `model="opus"`
- **review-agent-2**：Agent 定义见 [review-agent-2.md](../../agents/test-case-generation/review-agent-2.md)，指定 `model="opus"`

两个 Agent 接收相同输入，独立按 [CHECKLIST.md](CHECKLIST.md) 的 4 维度评审。

### 5.5 降级回退

- Task 工具不可用 → 在主 Agent 中按 4 维度逐项单 Agent 评审（参照 CHECKLIST.md）
- 单个 Agent 失败 → 重试 1 次，仍失败则使用另一个 Agent 的结果（单 Agent 模式）

### 5.6 合并结果与共识加成

收集两个 Agent 的结果后：

1. **对齐 findings**：相同 `affected_cases` + 相同 `category` → 视为同一发现
2. **共识加成**：两个 Agent 都发现的问题 → confidence += 20（封顶 100）
3. **按置信度分层**：
   - confidence ≥ 80 → **直接确认**（写入 `tc_gen_review.md`，自动应用修改建议）
   - 60 ≤ confidence < 80 → **待用户确认**（标记，进入 phase 6）
   - confidence < 60 → **丢弃**
4. **维度评分合并**：取两个 Agent 的 `dimension_scores` 平均值
5. **coverage_gaps 合并**：取并集，重复项取较高 confidence

将合并结果写入 `tc_gen_review.md`。

> **防截断规则**：`tc_gen_review.md` 只记录评审结论摘要，不要复制 Agent 的完整原始输出。格式要求：维度评分表（4 行）+ 确认的问题列表（每项一行：affected_cases、category、suggestion）+ coverage_gaps 列表。总长度控制在 200 行以内。如果 findings 超过 20 条，只保留 confidence 最高的 20 条。

### 5.7 为用例标注 review_confidence

对每条用例根据评审结果标注 `review_confidence`（0-100）：

- **无问题的用例**：review_confidence = 两个 Agent 的 4 维度评分等权平均，取两个 Agent 的平均值
- **有问题的用例**：在上述基础分上扣减 — high severity 问题扣 20 分、medium 扣 10 分、low 扣 5 分，下限为 0

## 阶段 6: confirm - 用户确认

本阶段将 review 阶段标记为「待用户确认」的问题抛给用户。

### 6.0 确认策略判定

检查 `confirm_policy` 参数：

- `confirm_policy = "accept_all"` → 自动接受所有评审建议（将所有 60 ≤ confidence < 80 的 findings 视为已确认），跳过用户交互，直接进入 phase 7
- `confirm_policy = "interactive"` 或未提供（默认）→ 执行 6.1 及后续的用户确认流程

### 6.1 收集待确认问题

从 phase 5.6 的合并结果中提取 60 ≤ confidence < 80 的 findings。如果没有待确认问题，跳过本阶段直接进入 phase 7。

### 6.2 向用户呈现

调用 AskUserQuestion 工具提供结构化选项（格式见 CONVENTIONS.md「[AskUserQuestion 交互式提问](../../CONVENTIONS.md#askuserquestion-交互式提问)」），降低用户认知负担。

> **CRITICAL — 选项溯源**：本阶段选项是固定处置选项（接受/驳回/补充），属于元操作。`evidence_tag` 标 `derived`，`evidence_ref` 必须包含 phase 5.6 合并结果中对应 finding 的原文摘录（用 `「」` 圈出 finding 关键描述）。**禁止**在 option label/description 中编造未在 finding 原文出现的具体名词（用例新字段、新版本号、新 API 路径 等）。详见 [输出溯源原则](../../CONVENTIONS.md#输出溯源原则)。
>
> **占位符必须替换**：下方示例的 `{N}` / `{finding_id}` / `{finding 原文摘录}` 等花括号占位符，AI 生成时**必须**替换为真实的 finding 编号和原话。保留花括号会通过 schema 但属于违规。

**首先**提供批量处理选项：

```json
{
  "questions": [
    {
      "question": "评审发现 {N} 个待确认问题，您希望如何处理？",
      "header": "批量处理",
      "evidence_ref": "phase 5.6 合并结果『发现 {N} 个待确认 findings』",
      "options": [
        {"label": "接受全部建议修改", "description": "一次性采纳所有评审建议", "evidence_tag": "derived", "evidence_ref": "phase 5.6 findings『{N} 个待确认』"},
        {"label": "逐条确认", "description": "逐个展示每个问题", "evidence_tag": "derived", "evidence_ref": "phase 5.6 findings『{N} 个待确认』"},
        {"label": "驳回全部", "description": "保持原样", "evidence_tag": "derived", "evidence_ref": "phase 5.6 findings『{N} 个待确认』"}
      ],
      "multiSelect": false
    }
  ]
}
```

如用户选择**逐条确认**，则逐个展示，每个问题包含 Agent 判断摘要和操作选项：

```json
{
  "questions": [
    {
      "question": "{问题描述}（涉及用例 {case_id}，共识置信度 {merged_confidence}）",
      "header": "问题 1",
      "evidence_ref": "tc_gen_review.md {finding_id}『{finding 原文摘录}』",
      "options": [
        {"label": "接受建议修改", "description": "{suggestion}", "evidence_tag": "derived", "evidence_ref": "tc_gen_review.md {finding_id}『{finding 原文摘录}』"},
        {"label": "驳回（保持原样）", "description": "不做修改，保留当前用例", "evidence_tag": "derived", "evidence_ref": "tc_gen_review.md {finding_id}『{finding 原文摘录}』"},
        {"label": "补充说明（请在回复中补充）", "description": "用户在回复中补充", "evidence_tag": "unknown", "evidence_ref": null}
      ],
      "multiSelect": false
    }
  ]
}
```

### 6.3 应用用户决策

根据用户回复逐项处理：

- **接受修改**：按建议修改 `test_cases.json` 中的对应用例
- **驳回**：保持原样，在 `tc_gen_review.md` 中标记为「用户已驳回」
- **补充说明**：根据用户补充信息更新用例或标记

### 6.4 降级处理

如果用户在对话中未明确回复每个问题（如只说"都接受"或"继续"）：
- "都接受" / 类似肯定回复 → 全部按建议修改
- "继续" / 未回复具体问题 → 保持原样，在报告中标注为「未确认」

### 阶段 6 完成检查（强制）

使用 Glob 工具确认以下文件存在：

1. `test_cases.json` — 必须存在且非空；缺失则回退到阶段 5.1 重新合并
2. `tc_gen_review.md` — 必须存在且非空；缺失则在主 Agent 中按 CHECKLIST.md 单 Agent 补评审
3. **停止条件**：`test_cases.json` 补生成后仍为空 → **停止整个 skill**，输出错误「用例合并失败，无法继续」

## 阶段 7: output - 最终输出

### 7.1 生成补充用例

基于 review 阶段的 `coverage_gaps`，为覆盖缺口生成补充用例：

```json
[
  {
    "case_id": "SUP-TC-01",
    "title": "用例标题",
    "module": "模块名称",
    "priority": "P0",
    "test_method": "场景法",
    "confidence": 85,
    "source": "supplementary",
    "preconditions": ["前置条件"],
    "steps": [{"action": "操作", "expected": "预期"}]
  }
]
```

如有补充用例，调用 `mcp__cases__save_test_cases(file_path='<workdir>/supplementary_cases.json', cases=[...])` 写入。如无覆盖缺口则跳过、不调用 tool。**禁止用 Write 直接写 *_cases.json**。

### 7.2 生成 final_cases.json

合并评审后的用例 + 补充用例为完整集合：

1. 从 `test_cases.json` 中保留所有用例（已含 review 阶段的修改）
2. 追加 `supplementary_cases.json` 中的补充用例（如有）
3. 为每条用例标记 `source` 字段（`generated` 或 `supplementary`）
4. 写入 `final_cases.json`

**实现方式（强制 Bash 路径）**：用 Bash 执行 Python/jq 脚本合并 —— 读取 `test_cases.json` + `supplementary_cases.json`、添加 `source` 字段、写入 `final_cases.json`。Bash 路径不经过 LLM 输出层，避免 token 截断；输入数据已是 MCP tool 校验过的合法用例，无需再走 schema 校验。

> 禁止用 Write 直接写 `final_cases.json`（会被 hook 拒绝）；也不建议用 `mcp__cases__save_test_cases` —— 用例总数通常超过 50 条，纯 LLM 输出路径会触发 token 截断。

### 7.3 生成评审摘要

回读所有中间文件，生成 `review_summary.json`：

```json
{
  "total_cases_generated": 0,
  "total_cases_final": 0,
  "coverage_rate": "0%",
  "issues_found": 0,
  "consensus_issues": 0,
  "cases_supplemented": 0,
  "user_confirmed_count": 0,
  "review_mode": "redundancy-pair",
  "dimension_scores": {
    "coverage": "...",
    "completeness": "...",
    "correctness": "...",
    "standards": "..."
  },
  "priority_distribution": {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
}
```
