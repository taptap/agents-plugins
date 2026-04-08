# 测试用例生成各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 额外预取：测试用例链接、需求文档内容（预下载到 `requirement_doc.md`）。

## 阶段 1: init - 初始化

> 如果系统预取了数据，本阶段仅需验证和确认。

1. 检查预取数据：Story 名称、需求文档链接、设计稿链接
2. 记录 `work_item_id` 和 `project_key`
3. 回退：预取数据缺失时基于已有信息继续

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
- 需求简单（< 3 功能点或文本 ≤ 2000 字）→ 跳过多视角分析，直接进入 decompose
- Task 工具不可用 → 在主 Agent 中顺序执行三个视角的分析（功能→异常→用户），不跳过

## 阶段 3: decompose - 功能拆解

### 3.0 简单需求快速路径

如需求功能点 < 3 个（从上游 `requirement_points.json` 或文档分析判断）：
- 跳过功能拆解，视为单模块
- 跳过 `context_summary.md` 生成
- 直接进入阶段 4 的直接生成模式（4.2）

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

## 阶段 4: generate - 并行生成

### 4.1 使用子 Agent 生成（模块 >= 3 个）

对每个功能模块，通过 Task 工具调用 test-case-writer 子 Agent。Agent 的完整行为定义见 [agents/test-case-writer.md](../../agents/test-case-writer.md)。

**Task 调用要点**：

1. 不要将 `context_summary.md` 内联到 Task prompt，Agent 会自行 Read
2. 只需提供：模块名称、模块需求（从 `decomposition.md` 中提取）、适用测试方法、模块索引
3. 指定 `model="sonnet"`（按模型分层策略，用例生成使用 Sonnet）
4. 每条用例必须包含 `confidence` 字段（0-100），评分标准见 Agent 定义文件

**并行策略**：在单条消息中同时发起所有模块的 Task 调用，实现真正并行。

### 4.1.1 子 Agent 失败处理

1. Task 返回后用 Glob 确认 `module_{index}_cases.json` 是否存在
2. 文件不存在或为空：重试 1 次
3. JSON 格式错误：严重问题才修复，轻微格式问题由后端 `post_complete` 自动修正
4. 重试仍失败：在主 Agent 中直接生成
5. 所有模块处理完后再进入 review 阶段

### 4.2 直接生成（模块 < 3 个，或简单需求快速路径）

在主 Agent 中按模块顺序生成所有用例，写入对应的 `module_{N}_cases.json`（N 从 1 开始，如 `module_1_cases.json`）。简单需求快速路径（阶段 3.0）视为单模块，写入 `module_1_cases.json`。

## 阶段 5: review - 自审 + 冗余对评审

本阶段包含两个子流程：先做快速自审（去重 + 覆盖度检查），再启动冗余对 Agent 做 4 维度深度评审。

### 5.1 合并 module 文件为 test_cases.json

将所有 `module_{N}_cases.json` 合并为单个 `test_cases.json`（顶层 JSON 数组）。每条用例的 `module` 字段标识归属模块，`confidence` 字段保留。

### 5.2 快速自审

> 格式校验（priority 合规、steps/expected 对齐）由后端 `post_complete` 自动完成，AI 只需关注内容质量。

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

自审完成后将修改后的结果写回 `test_cases.json`。

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

## 任务
按角色定义独立执行 4 维度评审，输出 JSON 格式的 dimension_scores + findings + coverage_gaps。
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

### 5.7 为用例标注 review_confidence

对每条用例根据评审结果标注 `review_confidence`（0-100）：

- **无问题的用例**：review_confidence = 两个 Agent 的 4 维度评分等权平均，取两个 Agent 的平均值
- **有问题的用例**：在上述基础分上扣减 — high severity 问题扣 20 分、medium 扣 10 分、low 扣 5 分，下限为 0

## 阶段 6: confirm - 用户确认

本阶段将 review 阶段标记为「待用户确认」的问题抛给用户。

### 6.1 收集待确认问题

从 phase 5.6 的合并结果中提取 60 ≤ confidence < 80 的 findings。如果没有待确认问题，跳过本阶段直接进入 phase 7。

### 6.2 向用户呈现

使用 CONVENTIONS.md「ask_question 输出格式」提供结构化选项，降低用户认知负担。

**首先**提供批量处理选项：

````
AskUserQuestion
```json
{
  "questions": [
    {
      "question": "评审发现 {N} 个待确认问题，您希望如何处理？",
      "header": "批量处理",
      "options": [
        {"label": "接受全部建议修改"},
        {"label": "逐条确认", "description": "逐个展示每个问题"},
        {"label": "驳回全部", "description": "保持原样"}
      ],
      "multiSelect": false
    }
  ]
}
```
````

如用户选择**逐条确认**，则逐个展示，每个问题包含 Agent 判断摘要和操作选项：

````
AskUserQuestion
```json
{
  "questions": [
    {
      "question": "{问题描述}（涉及用例 {case_id}，共识置信度 {merged_confidence}）",
      "header": "问题 1",
      "options": [
        {"label": "接受建议修改", "description": "{suggestion}"},
        {"label": "驳回（保持原样）"},
        {"label": "补充说明", "description": "请在回复中补充"}
      ],
      "multiSelect": false
    }
  ]
}
```
````

### 6.3 应用用户决策

根据用户回复逐项处理：

- **接受修改**：按建议修改 `test_cases.json` 中的对应用例
- **驳回**：保持原样，在 `tc_gen_review.md` 中标记为「用户已驳回」
- **补充说明**：根据用户补充信息更新用例或标记

### 6.4 降级处理

如果用户在对话中未明确回复每个问题（如只说"都接受"或"继续"）：
- "都接受" / 类似肯定回复 → 全部按建议修改
- "继续" / 未回复具体问题 → 保持原样，在报告中标注为「未确认」

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

如有补充用例写入 `supplementary_cases.json`。如无覆盖缺口则跳过。

### 7.2 生成 final_cases.json

合并评审后的用例 + 补充用例为完整集合：

1. 从 `test_cases.json` 中保留所有用例（已含 review 阶段的修改）
2. 追加 `supplementary_cases.json` 中的补充用例（如有）
3. 为每条用例标记 `source` 字段（`generated` 或 `supplementary`）
4. 写入 `final_cases.json`

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
