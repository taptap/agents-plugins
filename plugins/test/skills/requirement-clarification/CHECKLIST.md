# 澄清维度清单

本文件提供 `requirement-clarification` 在 `clarify` 阶段的检查项和使用策略。

12 维度检查点和问题模板见 [共享维度框架](../_shared/REQUIREMENT_DIMENSIONS.md)。

## 使用策略

### 维度优先级

功能边界 + 平台范围 → 交互与 UI 规则 → 依赖关系（含 API 契约） → 状态流转 → 验收标准 → 异常处理 → 影响范围 → 其他

### 渐进式提问

- clarify 阶段先提炼功能点，再按功能点 × 维度矩阵逐项检查
- 文档已明确说明的标记 `source: "document"`，不向人提问
- 需要人工确认的按优先级分组批量提问，每次 3-5 个
- 对用户不关心的维度提出默认假设，标记 `source: "assumption"` 让用户确认
- 探索模式下首轮重点在功能边界、平台范围和设计意图探查，避免过早深挖细节

### 退出条件

- 功能边界 + 平台范围 + 验收标准 已 confirmed → 可结束（最低标准）
- 所有维度均 confirmed → 理想结束
- 用户明确表示"够了" → 立即结束，剩余标记 unconfirmed
- 达到 5 轮仍有关键维度未确认 → 结束并标记风险

### 文档质量校对（必做）

12 维度功能点分析完成后，对 PRD 文档本身执行 [PRD 文档质量校对](../_shared/REQUIREMENT_DIMENSIONS.md#附加项prd-文档质量校对)（错别字 / 术语一致性 / 易读性 / 文案-设计稿一致性 / 数字单位一致性）。命中项写入 `clarified_requirements.json` 的 `doc_quality_issues` 数组（每条含 `category` / `evidence`（PRD 原文摘录）/ `suggestion` / `severity`）。错别字 / 数字单位歧义视为待 PM 确认的阻断级问题，须在澄清问答中向用户确认；术语漂移、易读性问题作为关注项记录、不主动追问。

### 分类变量正向枚举（必做）

12 维度分析过程中对 `business_rules` / `state_transitions[].rules` / `interaction_rules` 的每条文本做句式 lint：禁止出现「X 不…」「非 X」「除 X 外」「仅 X 才…」等否定/例外句式（隐含的"其他"会塌缩 N 元枚举为 2 元，导致下游开发实现错配）。命中即触发 3.2.6 流程：识别隐含分类变量 → 在源材料中查全集 → 缺失部分通过 AskUserQuestion 追问 → 改写规则为正向枚举 → 把分类变量登记到该功能点的 `enum_factors` 数组（每条含 `id` / `name` / `values[]` / `open_set` / `source` / `covered_by_rules`）。

详细执行流程见 [PHASES.md 3.2.6](PHASES.md#326-分类变量的正向枚举必做)。功能点不涉及分类变量时仍须写 `enum_factors: []` 显式声明，禁止省略。
