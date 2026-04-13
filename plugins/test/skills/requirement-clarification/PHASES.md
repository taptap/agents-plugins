# 需求澄清各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 无额外预取字段（使用通用 Story 预取字段集）。

## 阶段 1: init - 初始化

### 1.0 输入路由与模式识别

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认需求来源，并据此确定执行模式：

1. 工作目录中已存在上游产出文件（如 `clarified_requirements.json`）→ 本 skill 为首环节，一般不存在上游文件，跳过
2. `requirement_doc` 参数提供了本地文件 → **文档模式**，跳过在线获取，直接进入阶段 2 的文档解析
3. `story_link` 参数为 URL → **文档模式**，识别链接类型后进入阶段 2 的在线获取
4. `design_link` 参数为 Figma URL 且无 story_link / requirement_doc → **设计稿模式**，进入阶段 2 的设计稿获取
5. `requirement_text` 参数为自由文本 → **探索模式**，跳过阶段 2，直接进入阶段 3
6. `context_messages` 存在但无其他输入 → **探索模式**，合并碎片信息后进入阶段 3
7. 以上均不满足 → 停止并报错

**联合模式判定**：如同时存在 `story_link`/`requirement_doc` 和 `design_link`，进入**文档+设计稿联合模式**，阶段 2 同时获取文档和设计稿，阶段 3 执行交叉比对。

如同时存在多种输入（如 `story_link` + `context_messages`），以优先级最高的确定模式，其余作为补充上下文。

### 1.1 识别链接类型（仅文档模式 + story_link 路径）

- 飞书 Story 链接（`/story/detail/`）→ 提取 `project_key` 和 `work_item_id`
- 飞书文档链接（`/wiki/` 或 `/docx/`）→ 提取 `document_id`

### 1.2 检查预取数据

确认 Story 名称、需求文档链接、设计稿链接。预取缺失时基于已有信息继续。

## 阶段 2: fetch - 信息收集（探索模式跳过此阶段）

### 2.1 获取需求文档（必须完成）

**路径 A：本地文件**（`requirement_doc` 参数提供）
- 直接 Read 指定的本地文件

**路径 B：已预下载**
- 直接 Read `requirement_doc.md`，查看 `images/` 中关键图片

**路径 C：在线获取**

**预检**（首次调用脚本前执行）：
1. 确认 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 已设置。脚本会自动从 `.env` 文件加载（参见 [env.example](../shared-tools/scripts/env.example)），但若 shell 环境和 `.env` 均未配置，需提示用户并停止
2. 确保输出目录已创建（`mkdir -p`）

```bash
mkdir -p "$OUTPUT_DIR"
python3 $SKILLS_ROOT/shared-tools/scripts/fetch_feishu_doc.py \
  --url "<需求文档链接>" --output-dir "$OUTPUT_DIR" 2>"$OUTPUT_DIR/fetch_meta.json"
```

**文档获取失败**：需求文档是核心输入，获取失败则停止执行。

### 2.2 获取设计稿（设计稿模式必须，文档模式可选）

- **Figma 链接**：使用 `get_figma_data` 获取结构化设计数据
- **飞书文档链接**：使用 `fetch_feishu_doc.py` 获取
- 文档模式下无链接则跳过

**设计稿模式下的系统性提取**（当 design_link 为主要输入时）：

从设计稿中系统性提取以下信息作为 clarify 阶段的信息基底：
1. **页面/组件树**：识别所有页面和核心组件层级
2. **交互流**：页面跳转路径、操作触发条件
3. **状态变体**：同一组件的多种状态（空态、加载态、错误态、正常态）
4. **响应式行为**：不同屏幕尺寸下的布局差异（如有）
5. **交互细节**：手势、动效、过渡动画的标注

提取结果作为 `design_analysis` 存入内存，供 3.1 阶段反推功能点使用。

### 2.3 获取技术文档（可选）

如预取数据中包含技术文档链接，使用 `fetch_feishu_doc.py` 获取。重点提取：接口字段定义、状态枚举值、业务规则约束。

### 2.4 获取现有代码（条件触发）

当需求文档提到具体代码模块或 API 接口时，使用 GitLab/GitHub 脚本查看现有实现。

触发条件：提到具体 API、现有功能修改、具体代码模块名。不触发：全新功能、纯产品/设计变更。

## 阶段 3: clarify - 结构化澄清

本阶段是核心。根据执行模式采取不同策略。

### 3.0 信息基底准备

**文档模式**：基于 fetch 阶段获取的所有文档内容。

**探索模式**：基于 `requirement_text` 和/或 `context_messages`。先提取已知要素：
- 从文本中识别出的功能关键词、用户角色、业务场景
- 明确提到的约束或期望
- **设计意图信号**：文本中是否提及 UI 样式、视觉参考、设计稿链接
- 尚不清晰的部分（信息缺口）

如文本中未包含任何设计意图信号，在首轮问答中增加设计意图探查问题：
- 「是否已有设计稿或 UI 原型？如有请提供链接」
- 「对视觉风格有什么期望？是否有参考的产品或页面？」
- 「是否需要先产出设计稿再进入开发？」

### 3.1 提炼功能点

**文档模式**：从需求文档中提取所有功能点，逐条编号（FP-1, FP-2, ...）：
- 功能点必须从文档逐条提取，不能笼统概括
- 每个功能点应是独立的、可测试的
- 区分显式需求（文档明确提到）和隐式需求（合理推断但文档未提到）

**设计稿模式**：从设计稿反推功能点列表：
1. 基于 `design_analysis` 中提取的页面/组件树，为每个独立页面或功能模块生成功能点
2. 从交互流中识别隐含的业务逻辑（如状态变体暗示的业务规则）
3. 通过 AskUserQuestion 工具让用户确认功能点列表：「从设计稿中识别出以下功能点：① ... ② ...，是否准确？有遗漏的业务逻辑吗？」
4. 用户确认后编号（FP-1, FP-2, ...）
5. 设计稿中能确定的交互规则直接标记 `source: "design"`，无法从设计稿推断的业务规则进入维度深挖

**探索模式**：通过问答构建功能点列表：
1. 基于已有文本提出初步功能点列表
2. 通过 AskUserQuestion 工具让用户确认/补充/删减：「根据你的描述，我梳理出以下功能点：① ... ② ... ③ ...，是否准确？有遗漏吗？」
3. 用户确认后编号（FP-1, FP-2, ...），作为后续维度分析的基础

### 3.1.5 文档-设计稿交叉比对（文档+设计稿联合模式专属）

当同时拥有需求文档和设计稿时，执行交叉比对以识别两者之间的信息差异。

**Step 1：功能覆盖比对**

将文档中提炼的功能点列表与设计稿中识别的页面/组件列表做交叉匹配：
- **文档有、设计稿无**：可能是纯后端逻辑，或设计稿尚未覆盖 → 标记为待确认
- **设计稿有、文档无**：可能是隐含需求或设计超前 → 生成澄清问题：「设计稿中包含{页面/组件}，但需求文档未提及，是否属于本期范围？」

**Step 2：交互行为比对**

将设计稿中提取的交互流与文档中描述的状态流转做比对：
- **设计稿有交互细节但文档未描述**（如空态展示、手势操作、动效）→ 纳入功能点的 `interaction_rules`，标记 `source: "design"`
- **文档有状态规则但设计稿未体现**（如异常状态、权限差异展示）→ 生成澄清问题：「文档中提到{业务规则}，但设计稿中未体现对应的 UI 状态，是否需要补充设计？」

**Step 3：数据字段比对**

将设计稿中可见的表单字段、列表字段与文档中描述的数据约束做比对：
- 设计稿表单中有字段但文档未定义约束 → 生成数据约束维度的澄清问题
- 文档定义了字段但设计稿中未出现 → 标记为待确认

**Step 4：汇总差异**

将所有差异分类汇总：
- `coverage_gaps`：功能覆盖差异
- `interaction_gaps`：交互行为差异
- `data_gaps`：数据字段差异

差异列表纳入 3.3 渐进式确认的问题池，优先级等同于功能边界维度。

### 3.2 按维度分析每个功能点（支持多视角并行）

**复杂度判断**：如果功能点 >= 3 个且需求文本 > 2000 字 → 启动多视角并行分析；否则 → 单 Agent 分析。

#### 3.2.1 多视角并行分析（复杂需求）

在**单条消息**中同时发送 3 个 Task 调用，使用 [agents/requirement-understanding/](../../agents/requirement-understanding/) 下的 Agent 定义：

- **functional-perspective**（Opus）：分析功能边界、输入输出、状态流转、数据约束
- **exception-perspective**（Opus）：分析错误路径、边界条件、异常场景、容错机制
- **user-perspective**（Sonnet）：分析用户场景、交互流程、可用性、多角色行为

每个 Agent 接收完整需求文档，独立输出 findings（含 confidence 评分）。

**交叉验证**（由主 Agent 在收到 3 个 Task 结果后执行）：

1. 收集三个 Agent 的 findings 数组
2. **结构化匹配**：要求各视角 Agent 在 findings 中标注 `target_id`（关联的 FP-N 编号）。合并时先按 `target_id + category` 做初步分组，同一分组内再做语义去重（相似描述合并）
3. 同一发现被 2+ 个 Agent 独立识别 → confidence += 20（封顶 100）
4. 合并后的 findings 按 confidence 排序：
   - ≥80：标记为已确认的需求缺口，直接写入功能点的对应维度
   - 60-79：转化为需向用户提出的澄清问题
   - <60：记录但不主动提问
5. 为每个功能点计算 `confidence` 分数：已确认维度占比 × 100

**降级回退**：Task 工具不可用 → 单 Agent 逐维度分析（下方 3.2.2 流程）。

#### 3.2.2 单 Agent 分析（简单需求或降级模式）

对每个功能点，逐一检查 [CHECKLIST.md](CHECKLIST.md) 中的 12 个维度。对每个维度：

1. 在已有信息中搜索相关内容
2. 如果已明确说明 → 记录答案，标记 `source: "document"`（文档模式）或 `source: "human"`（探索模式首轮已确认）
3. 如果未说明或存在歧义 → 生成具体的澄清问题
4. 如果该维度可提出合理默认假设 → 生成带默认值的确认问题，标记待确认为 `source: "assumption"`

### 3.2.3 影响范围分析（条件触发）

当需求涉及**已有功能的修改**（而非全新功能）时，执行影响范围分析。

**触发条件**：需求文档或功能点描述中提到了现有模块/功能/实体的修改。全新功能跳过此步。

**Step 1：读取模块关系索引**

检查项目中是否存在 `module-relations.json`（由 `spec` 插件的 `module-discovery` 生成维护）：

1. 如果存在 → Read `module-relations.json`
2. 从需求中提取核心实体关键词（如「优惠券」「订单」「支付」）
3. 在 `entity_index` 中查找每个实体，获取 `referenced_by` 列表
4. 沿 `depends_on` / `depended_by` 链路向外扩展一层
5. 如果不存在 → 进入 Step 2 的定向代码扫描

**Step 2：定向代码验证**（当索引不存在或不足以回答时）

- 不做全库扫描，仅对索引中标记为不确定的关系做**定向扫描**（限定模块目录）
- 如果没有索引，使用 Grep/SemanticSearch 按关键词搜索，但限定在主要业务代码目录
- 搜索结果按模块分组，不把原始搜索结果直接交给后续步骤

**Step 3：生成影响范围报告**

将影响范围写入每个相关功能点的 `impact_scope` 字段：
- `directly_affected`: 直接引用该实体的模块（从 entity_index 或代码扫描获取）
- `indirectly_affected`: 间接依赖（沿 depended_by 链路扩展一层）
- `scope_confirmed`: 初始为 false，等待用户确认
- `data_source`: 标注数据来自 `module_relations_index` 还是 `code_scan`

**Step 4：纳入确认问题**

将影响范围发现转化为确认问题，在 3.3 渐进式确认中向用户提问：
- "修改 X 逻辑会影响以下 N 个模块：[列表]。请确认这些模块是否都在本次需求范围内？"
- 用户确认后设置 `scope_confirmed: true`

### 3.2.4 API 契约提取（条件触发）

当 `platform_scope.coordination_needed` 为 true（即前后端同时修改）时，从已有信息中提取 API 契约。

**触发条件**：`platform_scope.platforms` 同时包含前端平台（iOS/Android/Web/PC 中的任一）和后端平台（Server）。纯前端或纯后端需求跳过此步。

**Step 1：识别前后端交互点**

遍历每个功能点，识别需要前后端交互的场景：
- 功能点涉及数据提交/查询 → 需要 API
- 功能点涉及实时数据更新（WebSocket、推送）→ 需要通信协议
- 功能点涉及状态同步（如支付状态回调）→ 需要回调接口

**Step 1.5：数据充分性检查**（参见 [CONVENTIONS.md 数据充分性门控](../../CONVENTIONS.md#条件触发章节的数据充分性门控)）

在提取契约前，扫描所有源材料（需求文档、设计稿、已有代码），查找 API 相关的**具体技术证据**：
- 显式 API 路径（`/api/xxx`、`POST /xxx`）
- HTTP 方法 + 路径的技术描述
- 请求/响应字段定义或 schema
- 代码中的路由定义或 controller/handler 引用
- 技术文档中的接口规格说明

根据证据判定 `api_evidence_level`：
- `"none"`（源材料中无任何上述证据，如仅有产品 PRD、用户故事）→ **跳过 Step 2 和 Step 3**，直接进入 3.3。在内存中记录跳过原因，供 consolidate 阶段使用
- `"partial"`（有零散线索但不完整，如设计稿表单字段暗示请求字段，但无路径/方法）→ 进入 Step 2/3 但严格限制：每个字段必须有 `source` 标注，无 source 的不得出现
- `"sufficient"`（路径 + 方法 + 部分字段可从文档或代码中明确提取）→ 正常执行

> **硬规则**：禁止凭推测生成 API 路径或方法。每个契约字段必须标注 source（document/design/code）。无 source 标注的字段不得出现在契约草案中。

**Step 2：提取已知契约信息**

从需求文档、设计稿和已有代码中提取 API 相关信息：
- 需求文档中明确提到的接口路径和字段 → 标记 `source: "document"`
- 设计稿表单字段暗示的 request 字段 → 标记 `source: "design"`
- 现有代码中已存在的相关接口（通过 GitLab/GitHub 脚本查看）→ 标记 `source: "code"`

**Step 3：生成契约草案和澄清问题**

为每个前后端交互点生成初步契约草案：
- 如 `api_evidence_level` 为 `"sufficient"` 且 method、path、核心字段已知 → 生成完整契约草案（每个字段标注 source），通过 AskUserQuestion 工具确认
- 如 `api_evidence_level` 为 `"partial"` → 仅输出有 source 标注的字段，缺失部分生成针对性的澄清问题：「{功能}需要调用后端接口，请确认接口路径和核心字段」。不填充推测值作为占位
- 如 `api_evidence_level` 为 `"none"` → 此步骤已在 Step 1.5 跳过，不会到达

契约草案暂存在内存中，待 consolidate 阶段写入 `implementation_brief.json` 的 `api_contracts` 字段。

### 3.3 渐进式确认

按 SKILL.md 中定义的问题编排策略执行。所有提问**必须**通过调用 AskUserQuestion 工具完成，格式见 CONVENTIONS.md「[AskUserQuestion 交互式提问](../../CONVENTIONS.md#askuserquestion-交互式提问)」。

**首轮（骨架确认）** — 各模式均必经：
- 确认功能范围、目标用户、核心场景
- **确认平台范围**（必问）：需求涉及哪些平台？是否需要多端协调？
  - 如输入参数已提供 `platform_scope`，展示让用户确认
  - 如未提供，主动询问（示例见下方）
  - 根据回答填充 `platform_scope` 字段，决定后续是否需要提取 API 契约
- 3-4 个开放式问题
- 探索模式下此轮与 3.1 合并执行

首轮提问示例（调用 AskUserQuestion 工具）：

```json
{
  "questions": [
    {
      "question": "本次需求涉及哪些平台？",
      "header": "平台范围",
      "options": [
        {"label": "仅前端", "description": "iOS/Android/Web/PC 平台"},
        {"label": "仅后端", "description": "服务端逻辑变更"},
        {"label": "前后端同时修改", "description": "前后端联动变更"},
        {"label": "多端同步", "description": "请在回复中列出具体平台"}
      ],
      "multiSelect": false
    },
    {
      "question": "核心变更属于以下哪种类型？",
      "header": "变更类型",
      "options": [
        {"label": "新增功能模块", "description": "全新的功能模块开发"},
        {"label": "修改现有逻辑", "description": "对已有功能的行为变更"},
        {"label": "UI/交互调整", "description": "界面或交互流程变化"},
        {"label": "性能优化/重构", "description": "非功能性改进"}
      ],
      "multiSelect": true
    }
  ]
}
```

**中间轮（维度深挖）**：
- 按优先级逐维度提问：功能边界 + 平台范围 → 交互与 UI 规则 → 依赖关系（含 API 契约） → 状态流转 → 验收标准 → 异常处理 → 影响范围 → 其他
- 每次调用 AskUserQuestion 工具控制在 1-4 个问题
- 每个问题必须提供选项或默认值

**末轮（查缺补漏）**：
- 汇总已知信息让用户确认全貌
- 列出剩余 unconfirmed 项，询问用户是否需要继续澄清

**退出判断**：
- 功能边界 + 平台范围 + 验收标准 已 confirmed → 可结束（最低标准）
- 所有维度均 confirmed → 理想结束
- 用户明确表示"够了" → 立即结束，剩余标记 unconfirmed
- 达到 5 轮仍有关键维度未确认 → 结束并标记风险

### 3.4 记录澄清过程

将所有问答记录写入 `clarification_log.md`：

```markdown
# 澄清记录

## 基本信息
- 执行模式：文档模式 | 设计稿模式 | 文档+设计稿联合模式 | 探索模式
- 输入摘要：> 用户原始输入的摘要
- 问答轮次：N 轮

## FP-1: 用户注册

### 功能边界
- Q: 注册是否支持第三方登录？
- A: 本期只支持手机号注册 [source: human]

### 状态流转
- Q: 注册中途退出是否保存草稿？
- A: 不保存，需重新填写 [source: document, 见需求文档 3.2 节]

### 可测试性与验收标准
- Q: 注册成功的验收标准是什么？
- A: 用户能收到短信验证码并完成注册流程 [source: human]

## FP-2: ...
```

### 3.5 补充轮次

如果人的回答引发新的问题（如确认了某个功能后需要追问细节），进行补充轮次。结合退出条件判断是否继续，避免无限循环。

### 3.6 阶段衔接（CRITICAL）

clarify 阶段结束后，**必须立即进入阶段 4: consolidate**。

> 不要在此处创建实施计划、不要调用 CreatePlan、不要开始编码。
> consolidate 阶段生成的产物文件是整个 skill 的核心输出，跳过等同于 skill 执行失败。

如果 clarify 退出时用户已表示希望直接开始编码，仍应先完成 consolidate，
因为产物文件是下游 skill（test-case-generation、change-analysis 等）的输入依赖。

## 阶段 4: consolidate - 整合输出

### 4.1 生成 clarified_requirements.json

回读 `clarification_log.md`，将所有功能点的澄清结果整合为结构化 JSON。格式见 SKILL.md 中的输出格式定义。

关键字段说明：
- `mode`：记录本次执行模式，下游 skill 据此调整容忍度
- `confidence_level`：文档模式通常为 `high`，探索模式根据已确认维度占比判断（>80% → medium，<80% → low）
- `input_summary`：保留用户原始输入的摘要，供溯源

每个功能点的 `clarification_status`：
- `confirmed`：所有维度都已确认
- `partial`：部分维度已确认，部分待确认
- `unconfirmed`：关键维度未确认

字段按实际澄清结果填写，未涉及的维度留空数组或 null，不强制填充。

### 4.2 生成 requirement_points.json

从 clarified_requirements.json 中提取编号功能点清单，附带验收标准和测试关注维度。供下游 test-case-generation 消费。

### 4.3 标记未解决问题

将所有 `unconfirmed` 的问题汇总到 `clarified_requirements.json` 的 `open_questions` 字段，供下游 skill 作为风险输入。

### 4.4 生成 implementation_brief.json

基于 `clarified_requirements.json` 和 `platform_scope` 信息，为 coding agent 生成可直接消费的实现任务清单。

**Step 1：按平台拆分任务**

遍历每个功能点（FP-N），根据 `platform_scope.platforms` 拆分为独立的实现任务：
- 前端平台（iOS / Android / Web / PC）各自生成独立 TASK，包含 UI 规格和 API 依赖
- 后端平台（Server）生成包含 API 契约的 TASK
- 多端共享逻辑（如公共 SDK）生成 `platform: "Shared"` 的 TASK
- 单平台需求仅生成该平台的 TASK

**Step 2：整合 API 契约**

前置检查：
- 若 3.2.4 的 `api_evidence_level` 为 `"none"`（已跳过）→ `api_contracts` 设为空数组 `[]`，添加 `api_contracts_note: "API 契约信息不足，待技术方案补充后确认"`，跳过本步骤
- 若 `api_evidence_level` 为 `"partial"` → 仅写入有 source 标注的片段，每条标记 `"confirmed": false`
- 纯前端或纯后端需求跳过此步骤

将 3.2.4 阶段已提取并经用户确认的 API 契约草案写入 `api_contracts` 数组：
- 每条契约标注 `consumers`（依赖该接口的前端 TASK ID）和 `providers`（实现该接口的后端 TASK ID）
- 将契约中的 API 路径回填到对应前端 TASK 的 `api_dependencies` 和后端 TASK 的 `api_contract`

**Step 3：构建依赖图**

根据 API 依赖和功能依赖，生成 `dependency_graph`：
- 前端 TASK 依赖其 `api_dependencies` 对应的后端 TASK
- 具有前置逻辑依赖的 TASK 之间建立依赖边
- 无依赖的 TASK 值为空数组，可并行执行

**Step 4：回填 UI 规格**

如果 fetch 阶段获取了设计稿数据，将 Figma 节点信息回填到前端 TASK 的 `ui_specs` 中：
- `figma_node`：对应的 Figma 设计节点 ID
- `key_components`：页面核心 UI 组件列表
- `interaction_notes`：关键交互行为说明

### 4.5 报告章节输出规则

生成最终报告（report.md）时，条件触发章节根据分析阶段的数据充分性判定决定是否输出：

| 条件触发章节 | 对应分析步骤 | 判定字段 |
| --- | --- | --- |
| 核心 API 契约（草稿） | 3.2.4 API 契约提取 | `api_evidence_level` |

**输出规则**：
- `evidence: "none"` → 报告中**省略该章节**，可选在对应位置输出一行说明："> API 契约信息不足，待技术方案补充后确认"
- `evidence: "partial"` → 输出章节但加前缀说明："以下 API 契约仅包含源材料中明确提及的信息，未覆盖的交互点待技术方案补充"
- `evidence: "sufficient"` → 正常输出

### 4.6 输出验证（MUST）

逐一确认以下文件已写入工作目录：

1. `clarification_log.md` — 检查是否包含所有 FP 的问答记录
2. `clarified_requirements.json` — 检查 `functional_points` 数组非空
3. `requirement_points.json` — 检查编号与 clarified_requirements 一致
4. `implementation_brief.json` — 检查 `tasks` 数组非空

全部通过后，输出完成总结：

```
需求澄清完成。
- 执行模式：{mode}
- 功能点：{total_points} 个（已确认 {confirmed_points}，待确认 {total - confirmed}）
- 未解决问题：{open_question_count}
- 产物文件：4/4 已生成
```

如任一文件缺失，**停止并补生成**，不允许声明完成。
