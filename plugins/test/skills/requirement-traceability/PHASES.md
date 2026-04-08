# 需求回溯各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 额外预取：关联代码变更列表（GitLab MR / GitHub PR）。预取数据仅在 MR/PR 模式下可用；本地 diff 模式无预取。

## 阶段 1: init - 输入验证

确认代码变更来源（唯一阻断条件）。需求来源的路由统一在阶段 2 的 2.0 步骤中处理。

### 1.1 确认代码变更来源

收集所有代码变更来源（可同时提供多个）：

1. `code_diff_text` 参数非空 → 纳入 **文本 diff**
2. `code_diff` 参数提供了文件路径列表 → 逐个 Read，纳入 **文件 diff**
3. `code_changes` 参数提供了 MR/PR 链接列表 → 纳入 **MR/PR 列表**
4. 预取数据中有关联代码变更列表 → 合并到 MR/PR 列表（去重）
5. 以上均为空时，预取数据中有 `work_item_id` → 用 `search_mrs.py` / `search_prs.py` 搜索，仍为 0 → **停止**
6. 以上均不满足 → **停止**

后续阶段同时处理所有来源的 diff 数据。

### 1.2 MR/PR 模式下的 provider 判断

仅 MR/PR 模式需要：从链接或预取数据的 `provider` 字段判断代码托管平台（GitLab / GitHub）。

## 阶段 2: fetch - 数据获取

### 2.0 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认需求来源：

1. 工作目录中存在上游产出文件（`clarified_requirements.json`）→ 读取作为需求理解基础，跳过 2.1
2. 如存在 `requirement_points.json` → 读取作为需求点清单
3. `requirement_doc` 参数提供了本地文件 → Read 本地文件作为需求文档，跳过 2.1 的在线获取
4. `story_link` 参数为 URL → 执行 2.1 在线获取
5. 以上均不满足 → 基于代码变更做单边追溯（降级模式）

### 2.1 获取需求文档（可选）

本步骤仅在 2.0 路由到步骤 4（`story_link` 为 URL）时执行：

- 已预下载：Read `requirement_doc.md`
- 未预下载：用 `fetch_feishu_doc.py` 获取
- 链接为空且无上游输入和本地文件：基于代码变更继续

### 2.2 获取设计稿（可选）

有 Figma 链接时使用 `get_figma_data`，有飞书链接时用 `fetch_feishu_doc.py`。

### 2.3 获取代码变更数据

根据 init 阶段确定的模式：

**文本模式 / 文件模式**：diff 内容已在 init 阶段获取，跳过此步。

**MR/PR 模式**：使用预取的代码变更列表或参数提供的链接。为空回退：用 `search_mrs.py` / `search_prs.py` 搜索。

### 2.4 创建分析清单

写入 `traceability_checklist.md`：需求点清单（R1, R2...）、代码变更清单、统计。

## 阶段 3: map - 构建映射矩阵（冗余对并行）

本阶段使用冗余对模式：forward-tracer 和 reverse-tracer 两个 Agent 并行独立分析，在阶段 4 交叉验证。

### 3.0 准备 diff 数据

**重要**：冒烟测试模式下，分析对象是 MR/PR 的 diff 内容（即将合入的代码变更），不是目标分支的当前状态。MR 的 merge_status（opened/merged/closed）不影响 diff 的获取和分析。

MR/PR 模式下，先获取所有代码变更的 diff：

```bash
# GitLab
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-diff <project_path> <mr_iid>
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-detail <project_path> <mr_iid>
# GitHub
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-diff <owner/repo> <pr_number>
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-detail <owner/repo> <pr_number>
```

文本模式 / 文件模式：diff 内容已就绪。

### 3.1 检查上游验证用例与 ID 映射

检查工作目录中是否存在 `verification_cases.json`（上游 verification-test-generation 产出）：

1. 如果存在 → Read 该文件，用于正向通道的用例中介验证
2. 如果不存在 → 在 3.2 中使用内置简化版用例生成

**ID 映射**：上游 verification_cases.json 中 `requirement_id` 使用 `FP-` 前缀（来自 requirement-clarification），采用**编号直接继承**策略：

1. 回读 `traceability_checklist.md` 中的需求点列表
2. 回读 `verification_cases.json` 中的 requirement_id（FP-1, FP-2...）
3. **直接使用上游 FP- 编号作为主键关联**，同时记录本地 R- 编号作为别名（如 `FP-1 = R-1 (用户注册)`）
4. 将映射表追加写入 `traceability_checklist.md` 的末尾
5. 后续正向通道消费 verification_cases 时，通过 FP- 主键直接关联，无需语义匹配

> 仅当无上游 FP- 编号（独立使用模式）时，才使用 R- 独立编号，无需建立映射。

同时检查 `ui_fidelity_report.json` 是否存在（上游 UI 还原度检查产出）：
1. 如果存在 → 在 4.4 中直接合并到 traceability_coverage_report.json
2. 如果不存在且有 design_link → 在 3.4 中触发 UI 还原度检查

同时检查 `api_contract_report.json` 是否存在（上游 api-contract-validation 产出）：
1. 如果存在 → 在 4.4 中直接合并到 traceability_coverage_report.json，跳过 3.2.5 的内置检查
2. 如果不存在且代码变更涉及 API 相关文件 → 在 3.2.5 中触发内置契约感知检查

### 3.2 正向通道：用例中介验证

**有上游 verification_cases.json 时**：

直接消费上游验证用例，对每条用例执行代码路径追踪：

1. 回读 `verification_cases.json`
2. **可追踪性评估**（前置）：对每条用例先评估代码路径的静态可追踪性——调用链超过 3 层、包含动态分派、调用目标跨服务 → 直接标记 `inconclusive`；diff-only 模式下 confidence 上限 70。详细规则参照 [verification-test-generation/PHASES.md](../verification-test-generation/PHASES.md) 4.2.0 节
3. 对每条通过可追踪性评估的 verification case：
   - 读取用例的 input 和 expected
   - 在代码中找到对应的入口函数/API
   - 追踪 input 在代码中的执行路径
   - 判断执行结果是否符合 expected
   - 标记 pass/fail/inconclusive + confidence
4. 将验证结果写入 `forward_verification.json`

**无上游 verification_cases.json 时（内置简化版）**：

1. 从 `traceability_checklist.md` 的需求点中提取验收标准
2. 为每条验收标准生成 1-2 条简化验证用例（输入→预期）
3. 对每条用例执行上述代码路径追踪
4. 注意：内置版的用例覆盖面不如上游 verification-test-generation 完整

**降级**：如果代码不可读或 diff 信息不足 → 降级为传统 forward-tracer 模式。降级时 forward-tracer 输出 `{agent, requirement_to_code}` 格式（`status: covered/partial/missing`），需适配为 `forward_verification.json` 格式后写入：

| forward-tracer status | 映射后 result | confidence 处理 |
| --- | --- | --- |
| `covered` | `pass` | 保留 forward-tracer 的 confidence |
| `partial` | `inconclusive` | confidence 取 forward-tracer 值的 80%（部分实现无法判定 pass） |
| `missing` | `fail` | 保留 forward-tracer 的 confidence |

### 3.2.5 API 契约感知检查（条件触发）

当前后端同步开发时，代码变更可能存在接口契约不一致。本步骤在正向通道完成后执行轻量级 API 契约校验。

**触发条件**（满足任一即触发）：

1. 代码变更文件中包含 API 相关模式（网络请求路径定义、API 模型/DTO、请求参数构造、路由定义等）
2. `traceability_checklist.md` 中的需求点涉及接口交互（关键词：接口、API、数据获取、请求、网络等）
3. `code_changes` 或 `backend_changes` 中同时存在前端和后端 MR/PR

以上条件均不满足 → 跳过，在 traceability_coverage_report.json 中记录 `api_contract.overall_consistency: "N/A"`。

**上游优先**：如果工作目录已有 `api_contract_report.json`（上游 api-contract-validation 产出）→ 跳过内置检查，在阶段 4 直接合并。

**内置轻量级检查流程**：

1. **分类 API 相关变更**：从 diff 中识别以下文件类型
   - 前端：网络请求路径枚举/常量、API 响应模型（Codable/Decodable/DTO）、请求参数构造
   - 后端：路由定义、Controller/Handler、响应结构体/序列化器

2. **提取接口签名**：从 diff 中提取每个涉及的 API 端点的关键信息
   - 请求路径（URL path）
   - 请求方法（GET/POST/PUT/DELETE）
   - 请求参数名和类型
   - 响应字段名和类型

3. **交叉比对**：对每个涉及的端点，在前端和后端的变更之间做一致性检查
   - **路径一致性**：前端调用路径 vs 后端路由定义
   - **字段名一致性**：前端模型字段名 vs 后端响应字段名（注意命名风格转换，如 snake_case ↔ camelCase）
   - **类型一致性**：前端字段类型 vs 后端字段类型（如 String vs Int 不匹配）
   - **必填字段完整性**：后端标记为必填的请求参数，前端是否都传递了

4. **可选：OpenAPI 基准校验**：如果提供了 `openapi_spec` 参数
   - 将前端模型和后端实现分别与 OpenAPI 定义比对
   - 偏离 OpenAPI 定义的一方标记为不一致来源

5. **写入结果**：生成契约检查摘要，追加到 `code_analysis.md`

**降级**：

- 仅有前端变更无后端变更（或反之）→ 仅检查与 OpenAPI spec 的一致性（如有 spec），否则仅记录 API 相关变更的概要，不做一致性判定
- diff 信息不足以提取接口签名 → 标记为 `inconclusive`，在报告中注明原因

### 3.3 反向通道：直接代码追溯

保持现有 reverse-tracer Agent 模式不变。在**单条消息**中与正向通道并行启动：

**Task prompt 示例**：

```
你是反向追溯 Agent。请先 Read agents/requirement-traceability/reverse-tracer.md 获取你的完整角色定义和输出格式要求。

## 需求点清单
请 Read ./traceability_checklist.md 获取需求点列表（R1, R2...）。

## 代码变更
{diff 内容直接内联，或指示 "请 Read ./diff.txt 获取代码变更"}

## 需求文档（如有）
请 Read ./requirement_doc.md 获取需求文档。如文件不存在则基于 traceability_checklist.md 中的需求描述进行追溯。

## 任务
按角色定义执行反向追溯，输出 JSON 格式的 code_to_requirement 映射。每条映射必须包含 confidence 评分（0-100）。
```

- **reverse-tracer**：Agent 定义见 [reverse-tracer.md](../../agents/requirement-traceability/reverse-tracer.md)，指定 `model="opus"`

### 3.4 UI 还原度检查（条件触发）

**触发条件**：需求有 `design_link`（Figma 链接）且前端页面可在浏览器中访问。

如果工作目录已有 `ui_fidelity_report.json`（上游产出）→ 跳过，在阶段 4 直接使用。

否则执行内置 UI 还原度检查：

**MCP 可用性探测**（前置）：

1. **Figma MCP 探测**：尝试调用 Figma MCP 的 `get_screenshot`，如连接失败或工具不存在 → 跳过整个 UI 还原度检查，在报告中记录降级原因 `figma_mcp_unavailable`
2. **Browser MCP 探测**：尝试调用 Browser MCP 的 `browser_snapshot`，如连接失败 → 降级为 structural-only 模式（仅对比 Figma 结构化数据 vs 代码样式定义）

探测通过后执行：

1. 使用 Figma MCP `get_screenshot` 获取设计稿截图
2. 使用 Figma MCP `get_design_context` 获取结构化设计数据
3. 使用 Browser MCP `browser_take_screenshot` 获取实现截图
4. 使用 Browser MCP `browser_snapshot` 获取 DOM 结构
5. 启动 ui-fidelity-checker Agent（见 agents/ui-fidelity-checker.md）进行对比
6. 输出 `ui_fidelity_report.json`

**降级**：页面不可访问时 → 仅对比 Figma 结构化数据 vs 代码中的样式定义，跳过截图对比。

### 3.5 降级回退

- Task 工具不可用 → 在主 Agent 中顺序执行正向验证和反向追溯
- 单个通道失败 → 重试 1 次，仍失败则在主 Agent 中接管该方向的追溯
- 两个通道都失败 → 回退到原有的逐代码变更循环分析模式

### 3.6 记录中间结果

两个通道完成后，将各自的结果写入 `code_analysis.md`，标注来源通道。

## 阶段 4: output - 交叉验证与风险评估

**前提**：回读 `code_analysis.md` 和 `traceability_checklist.md`，以及两个 Agent 的输出。

### 4.1 交叉验证

> `trace_direction` 字段由本阶段根据两个通道的结果**计算得出**，不由 Agent 直接输出。

在原有交叉验证基础上，新增正向验证结果的合并：

1. 回读 `forward_verification.json` 和 reverse-tracer 的输出
2. 对每个需求点：
   - 正向用例验证 pass → 需求实现确认（confidence 取用例验证的 confidence）
   - 正向用例验证 fail → 标记为实现缺口
   - 正向用例 inconclusive + reverse-tracer 确认 → 使用 reverse-tracer 的 confidence
3. 反向追溯的"未归属代码变更"保持原有逻辑

对每个映射对判定方向：
   - **双向确认**：正向和反向都确认同一映射 → `trace_direction: "bidirectional"`，confidence = max(两个通道的 confidence) + 20（封顶 100）
   - **仅正向确认**：正向找到但反向未找到 → `trace_direction: "forward-only"`，保留正向通道的 confidence
   - **仅反向确认**：反向找到但正向未找到 → `trace_direction: "reverse-only"`，保留 reverse-tracer 的 confidence
   - **均未找到**：确认为覆盖缺口

### 4.2 覆盖缺口汇总

- 需求侧缺口：需求点无对应代码变更 → 标记 `missing`
- 代码侧未追溯：代码变更无对应需求 → 标记 `untraced`

### 4.3 生成 traceability_matrix.json

格式见 [TEMPLATES.md](TEMPLATES.md#traceability_matrixjson)。包含 `requirement_to_code`、`code_to_requirement` 两个视角，每条映射含 `confidence` 和 `trace_direction` 字段。

### 4.4 生成 traceability_coverage_report.json

格式见 [TEMPLATES.md](TEMPLATES.md#coverage_reportjson)。包含需求覆盖率、代码追溯率、缺口清单和双向确认率。

在原有覆盖率统计基础上，新增：

- `verification_channel`: 标注使用的验证通道（"dual_channel" | "forward_only" | "reverse_only"）
- `forward_verification_rate`: 正向用例验证通过率
- `ui_fidelity`: 如果有 `ui_fidelity_report.json`，按以下字段映射合并 UI 还原度数据：

```json
{
  "ui_fidelity": {
    "overall_fidelity": "high | medium | low",
    "comparison_mode": "visual+structural | structural-only",
    "total_differences": 5,
    "by_severity": { "high": 1, "medium": 2, "low": 2 },
    "state_coverage_rate": "80%",
    "source": "ui-fidelity-check | inline"
  }
}
```

映射规则：
1. `overall_fidelity` ← `ui_fidelity_report.json` 顶层 `overall_fidelity`
2. `comparison_mode` ← `ui_fidelity_report.json` 顶层 `comparison_mode`
3. `total_differences` ← `differences` 数组长度
4. `by_severity` ← 按 `differences[].severity` 分组计数
5. `state_coverage_rate` ← `ui_fidelity_report.json` 的 `states_coverage.coverage_rate`
6. `source` ← `"ui-fidelity-check"`（上游产出）或 `"inline"`（本 skill 内置检查）
7. 如无 `ui_fidelity_report.json` 且未执行 UI 检查 → `ui_fidelity` 字段不写入

- `api_contract`: 如果有 `api_contract_report.json`（上游产出）或 3.2.5 内置检查结果，按以下字段映射合并 API 契约数据：

```json
{
  "api_contract": {
    "overall_consistency": "consistent | inconsistent | partial | N/A",
    "checked_endpoints": 3,
    "issues_found": 1,
    "issues": [
      {
        "endpoint": "/api/v2/user/profile",
        "type": "field_mismatch | type_mismatch | path_mismatch | missing_param",
        "severity": "high | medium | low",
        "frontend_expects": "user_name: String",
        "backend_provides": "username: String",
        "source_mr": "ios/taptap-ios!456"
      }
    ],
    "source": "api-contract-validation | inline"
  }
}
```

映射规则：
1. `overall_consistency` ← 上游 `api_contract_report.json` 的 `overall_consistency`，或内置检查的计算结果（全部一致 → `consistent`，存在 high → `inconsistent`，仅 medium/low → `partial`）
2. `checked_endpoints` ← 检查过的接口端点数
3. `issues` ← 上游的 `issues` 数组或内置检查发现的问题列表
4. `source` ← `"api-contract-validation"`（上游产出）或 `"inline"`（本 skill 内置检查）
5. 如 3.2.5 未触发且无上游报告 → `api_contract` 字段不写入

### 4.5 生成 risk_assessment.json

格式见 [TEMPLATES.md](TEMPLATES.md#risk_assessmentjson)。

风险评估维度：
- 需求覆盖率显著低于预期（大量需求点未被实现）→ 高风险
- 存在未追溯的代码变更（可能的范围蔓延）→ 中风险
- 高复杂度变更未映射到明确需求 → 高风险
- 双向确认率低（正反向结果分歧大）→ 额外风险标记
- API 契约存在 high 级别不一致（前后端字段/类型/路径不匹配）→ 高风险
- API 契约存在 medium 级别不一致（命名风格差异、可选字段遗漏等）→ 中风险

### 4.6 缺陷提取与优先级判定（smoke-test 模式）

仅当 `mode == "smoke-test"` 时执行，否则跳过。

回读 `forward_verification.json`、`traceability_coverage_report.json`、`traceability_matrix.json`，从以下来源提取缺陷：

**来源 1：正向验证失败**

从 `forward_verification.json` 中提取 `result: "fail"` 且 `confidence >= 70` 的条目：

- 缺陷名称 = 关联需求点名称 + 验证用例的场景描述
- 预期结果 = `expected` 字段原文
- 实际结果 = 从 `trace` 字段推导（代码执行路径偏离预期的关键分支点或返回值）
- 优先级判定：confidence >= 85 → P0；confidence >= 70 → P1
- `evidence.source` = `"forward_verification"`，`evidence.source_id` = 对应 `case_id`

**来源 2：需求实现缺失**

从 `traceability_coverage_report.json` 的 `gaps[]` 中提取 `type == "requirement_not_implemented"` 的条目：

- 缺陷名称 = 需求点名称 + "实现缺失"
- 预期结果 = 需求点描述（从 `traceability_checklist.md` 或 `traceability_matrix.json` 中获取）
- 实际结果 = "代码变更中未发现对应实现"
- 优先级判定：`risk_level == "high"` → P0；`risk_level == "medium"` → P1
- `evidence.source` = `"coverage_gap"`

**来源 3：API 契约不一致**

从 `traceability_coverage_report.json` 的 `api_contract.issues[]` 中提取 severity 为 high 或 medium 的条目：

- 缺陷名称 = 端点路径 + 不一致类型描述
- 预期结果 = 前端期望的定义
- 实际结果 = 后端实际提供的定义
- 优先级判定：`severity == "high"` → P0（类型不匹配、路径不匹配、必填参数缺失）；`severity == "medium"` → P1
- `evidence.source` = `"api_contract"`

**来源 4：UI 还原度差异（条件触发）**

当 `traceability_coverage_report.json` 中存在 `ui_fidelity` 且有 high severity 差异时：

- 优先级：统一为 P1（UI 差异通常不构成 P0 阻断）
- `evidence.source` = `"ui_fidelity"`

**排除规则（MR 流程状态）**：

以下情况不提取为缺陷，仅在 `smoke_test_report.json` 的 `excluded_items` 中记录：

1. MR/PR 处于 opened/draft 状态导致的「代码未合入目标分支」— 这是流程状态而非实现缺陷。冒烟测试基于 MR diff 评估实现质量，不关注合并状态
2. 多个 MR/PR 拆分交付同一需求时，部分 MR 尚未创建或处于早期阶段 — 仅评估已提供的 MR diff 内容
3. 需求实现分布在多个 MR 中，且当前仅提供了部分 MR — 基于已有 diff 评估，未覆盖的部分标记为 `out_of_scope` 而非 `implementation_missing`

判断标准：如果需求对应的代码变更**存在于已提供的 MR diff 中**（无论 MR 是否已合并），则该需求视为「已有实现」，应进入正向验证通道评估实现质量，而非直接标记为缺失。

**去重规则**：同一需求点（`requirement_ref` 相同）从多个来源命中时，合并为一个缺陷，取最高优先级，在 `evidence` 中记录所有命中来源。

**confidence 过滤**：来源 1 中 confidence < 70 的 fail 项不提取为缺陷，仅在 `smoke_test_report.json` 的 `low_confidence_items` 中记录供参考。

将提取结果暂存，供 4.7 写入文件。

### 4.7 生成冒烟测试报告（smoke-test 模式）

仅当 `mode == "smoke-test"` 时执行，否则跳过。

1. **写入 `defect_list.json`**：将 4.6 提取的缺陷按优先级排序（P0 在前），格式见 [TEMPLATES.md](TEMPLATES.md#defect_listjson)
2. **写入 `smoke_test_report.json`**：汇总验证统计和缺陷统计，格式见 [TEMPLATES.md](TEMPLATES.md#smoke_test_reportjson)
3. **P0 门控判定**：
   - `defect_list.json` 中 `priority == "P0"` 的缺陷数 > 0 → `verdict: "fail"`，`fail_reason` 列出 P0 缺陷摘要
   - P0 缺陷数 == 0 → `verdict: "pass"`
4. **Chat 输出冒烟测试结论**：

```
冒烟测试结论：{verdict}
- 验证点：{total_points} 个（通过 {passed}，失败 {failed}，待定 {inconclusive}）
- 缺陷：{total_defects} 个（P0: {p0}, P1: {p1}, P2: {p2}）
{如有排除项: "- 排除项：{excluded_count} 个（MR 流程状态相关，不计入缺陷）"}
{如 verdict == "fail": "P0 缺陷列表：\n" + 逐条列出 P0 缺陷名称}
```

## 阶段 5: loop - 回溯自循环（条件触发）

> **smoke-test 模式行为**：当 `mode == "smoke-test"` 时，跳过 Phase 5 整个自循环阶段。冒烟测试场景不做交互式缺口修复，4.7 产出即为最终结果。

当 traceability_coverage_report.json 存在 `missing` 或 `partial` 状态的需求点时，自动进入缺口修复循环。

### 5.0 触发判定

回读 `traceability_coverage_report.json`，检查以下条件：

1. `gaps` 数组中是否存在 `status == "missing"` 或 `status == "partial"` 的条目
2. 如果 gaps 为空 → **跳过 Phase 5**，回溯完成
3. 如果存在缺口 → 进入 5.1

### 5.1 缺口分类

对每个缺口（gap）进行分类，确定修复方式：

| 缺口类型 | 判定条件 | 修复方式 |
| --- | --- | --- |
| 实现缺失 | 需求点在代码中完全无对应变更 | 需要补充代码实现 |
| 实现不完整 | 需求点有部分实现但不完整 | 需要补充缺失的代码逻辑 |
| 追溯失败 | 实现可能存在但 AI 未能识别映射 | 用户确认映射关系后标记为 covered |
| 需求变更 | 需求点已废弃或延期 | 用户确认后标记为 `deferred` |

将分类结果追加到 `traceability_coverage_report.json` 的 `gap_classification` 字段。

### 5.2 用户确认

将缺口分类结果和修复建议输出给用户，等待确认：

```markdown
## 回溯缺口汇总

| 编号 | 需求点 | 缺口类型 | 建议动作 |
| --- | --- | --- | --- |
| R3 | 密码强度校验 | 实现缺失 | 需补充代码实现 |
| R5 | 导出功能 | 追溯失败 | 请确认映射关系 |

请确认以上分类是否正确，并指示下一步动作：
1. 修复缺口（补充实现后重跑回溯）
2. 标记为延期（从当前覆盖率统计中排除）
3. 手动确认映射（修正 AI 追溯结果）
```

**用户无响应 → 停止自循环**，输出当前状态即为最终结果。

### 5.3 增量重跑

用户确认修复后：

1. 仅对**用户确认需要重新追溯的需求点**执行增量分析（不重跑全量）
2. 重新获取相关代码变更的最新 diff（代码可能已更新）
3. 使用与 Phase 3.2 一致的验证方式（有 verification_cases 时用用例中介验证，否则用内置简化版），仅对修复的需求点对应的验证用例增量执行。forward-tracer 仅在与首次全量验证相同的降级条件触发时才使用
4. 合并增量结果到 `traceability_matrix.json` 和 `traceability_coverage_report.json`
5. 回到 5.0 重新判定缺口

### 5.4 收敛与退出

自循环的退出条件（满足任一即退出）：

1. **全部覆盖**：所有需求点状态为 `covered` 或 `deferred` → 输出最终报告
2. **达到最大轮次**：默认最大 3 轮（可通过 `max_loop_iterations` 参数调整），超过后强制退出并在报告中标注未收敛的缺口
3. **无进展**：本轮与上轮的缺口列表完全一致（无新覆盖的需求点）→ 强制退出，标注为"需人工介入"
4. **用户主动终止**：用户在 5.2 步骤选择停止

退出时更新 `traceability_coverage_report.json` 的 `loop_metadata` 字段：

```json
{
  "loop_metadata": {
    "iterations_run": 2,
    "max_iterations": 3,
    "exit_reason": "all_covered | max_iterations | no_progress | user_terminated",
    "unresolved_gaps": ["R3"]
  }
}
```
