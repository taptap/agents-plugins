# 需求澄清各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 无额外预取字段（使用通用 Story 预取字段集）。

## 阶段 1: init - 初始化

### 1.0 输入路由与模式识别

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认需求来源，并据此确定执行模式：

1. 工作目录中已存在上游产出文件（如 `clarified_requirements.json`）→ 本 skill 为首环节，一般不存在上游文件，跳过
2. `requirement_doc` 参数提供了本地文件 → **文档模式**，跳过在线获取，直接进入阶段 2 的文档解析
3. `story_link` 参数为 URL → **文档模式**，识别链接类型后进入阶段 2 的在线获取
4. `requirement_text` 参数为自由文本 → **探索模式**，跳过阶段 2，直接进入阶段 3
5. `context_messages` 存在但无其他输入 → **探索模式**，合并碎片信息后进入阶段 3
6. 以上均不满足 → 停止并报错

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
```bash
python3 $SKILLS_ROOT/shared-tools/scripts/fetch_feishu_doc.py \
  --url "<需求文档链接>" --output-dir . 2>fetch_meta.json
```

**文档获取失败**：需求文档是核心输入，获取失败则停止执行。

### 2.2 获取设计稿（可选）

- **Figma 链接**：使用 `get_figma_data` 获取结构化设计数据
- **飞书文档链接**：使用 `fetch_feishu_doc.py` 获取
- 无链接则跳过

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
- 尚不清晰的部分（信息缺口）

### 3.1 提炼功能点

**文档模式**：从需求文档中提取所有功能点，逐条编号（FP-1, FP-2, ...）：
- 功能点必须从文档逐条提取，不能笼统概括
- 每个功能点应是独立的、可测试的
- 区分显式需求（文档明确提到）和隐式需求（合理推断但文档未提到）

**探索模式**：通过问答构建功能点列表：
1. 基于已有文本提出初步功能点列表
2. 通过 ask_question 让用户确认/补充/删减：「根据你的描述，我梳理出以下功能点：① ... ② ... ③ ...，是否准确？有遗漏吗？」
3. 用户确认后编号（FP-1, FP-2, ...），作为后续维度分析的基础

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

### 3.3 渐进式确认

按 SKILL.md 中定义的问题编排策略执行：

**首轮（骨架确认）** — 探索模式必经，文档模式酌情：
- 确认功能范围、目标用户、核心场景
- 2-3 个开放式问题
- 探索模式下此轮与 3.1 合并执行

**中间轮（维度深挖）**：
- 按优先级逐维度提问：功能边界 → 验收标准 → 状态流转 → 异常处理 → 交互规则 → 其他
- 每次 ask_question 控制在 3-5 个问题
- 每个问题提供选项或默认值

**末轮（查缺补漏）**：
- 汇总已知信息让用户确认全貌
- 列出剩余 unconfirmed 项，询问用户是否需要继续澄清

**退出判断**：
- 功能边界 + 验收标准 已 confirmed → 可结束（最低标准）
- 所有维度均 confirmed → 理想结束
- 用户明确表示"够了" → 立即结束，剩余标记 unconfirmed
- 达到 5 轮仍有关键维度未确认 → 结束并标记风险

### 3.4 记录澄清过程

将所有问答记录写入 `clarification_log.md`：

```markdown
# 澄清记录

## 基本信息
- 执行模式：文档模式 | 探索模式
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
