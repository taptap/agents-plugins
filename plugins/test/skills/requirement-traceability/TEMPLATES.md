# 需求回溯输出格式定义

## traceability_matrix.json

双向映射矩阵，包含两个视角的追溯数据。

### 完整结构

```json
{
  "requirement_to_code": [ ... ],
  "code_to_requirement": [ ... ]
}
```

### requirement_to_code（需求→代码）

每个需求点映射到实现它的代码变更：

```json
{
  "requirement_id": "R1",
  "requirement_name": "用户注册功能",
  "code_changes": [
    {
      "change_id": "project/path!123",
      "change_title": "feat: add user registration",
      "change_summary": "新增 RegisterController 和 UserService.register 方法",
      "files_changed": ["src/controller/register.py", "src/service/user.py"],
      "confidence": 90,
      "confidence_label": "[已确认]",
      "trace_direction": "bidirectional"
    }
  ],
  "status": "covered | partial | missing"
}
```

`change_id` 取值：MR/PR 模式下为 MR/PR 标识（如 `project/path!123` 或 `owner/repo#456`）；本地 diff 模式下为文件名或自动生成的序号（如 `diff-1`）。

`confidence` 取值 0-100，量化置信度评分。`confidence_label` 为向后兼容的文本标签，映射关系见 [CONVENTIONS.md](../../CONVENTIONS.md#量化置信度评分)。

`trace_direction` 取值：`bidirectional`（正反向 Agent 都确认）、`forward-only`（仅正向确认）、`reverse-only`（仅反向确认）。双向确认的映射 confidence 已包含 +20 共识加成。

### code_to_requirement（代码→需求）

每个代码变更映射到对应的需求点：

```json
{
  "change_id": "project/path!123",
  "change_title": "feat: add user registration",
  "change_type": "API | 逻辑 | 数据 | 配置",
  "risk_level": "high | medium | low",
  "mapped_requirements": ["R1", "R3"],
  "status": "traced | untraced"
}
```

## traceability_coverage_report.json

### 完整结构

```json
{
  "requirement_coverage": { ... },
  "code_traceability": { ... },
  "tracing_metadata": { ... },
  "gaps": [ ... ],
  "api_contract": { ... },
  "ui_fidelity": { ... }
}
```

> `api_contract` 和 `ui_fidelity` 为条件字段，仅在对应检查触发时写入。

### requirement_coverage（需求覆盖率）

```json
{
  "total": 10,
  "covered": 8,
  "partial": 1,
  "missing": 1,
  "rate": "80%"
}
```

### code_traceability（代码追溯率）

```json
{
  "total_changes": 15,
  "traced": 12,
  "untraced": 3,
  "rate": "80%"
}
```

### tracing_metadata（追溯元数据）

```json
{
  "tracing_mode": "redundancy-pair",
  "bidirectional_confirmation_rate": "75%",
  "forward_only_count": 2,
  "reverse_only_count": 1,
  "avg_confidence": 82
}
```

### gaps（缺口清单）

```json
[
  {
    "type": "requirement_not_implemented",
    "id": "R5",
    "description": "用户密码重置功能未在代码变更中体现",
    "risk_level": "high",
    "recommendation": "确认是否在本期范围内，如是则需补充实现"
  },
  {
    "type": "code_not_traced",
    "id": "diff-3",
    "description": "日志格式调整未关联到任何需求点",
    "risk_level": "low",
    "recommendation": "确认是否为技术重构或范围蔓延"
  }
]
```

## risk_assessment.json

### 完整结构

```json
{
  "overall_risk": "...",
  "risk_factors": [ ... ],
  "summary": "...",
  "action_items": [ ... ]
}
```

### 示例

```json
{
  "overall_risk": "medium",
  "risk_factors": [
    {
      "factor": "R5 用户密码重置功能未实现",
      "severity": "high",
      "evidence": "需求文档明确列出但无对应代码变更",
      "recommendation": "与开发确认是否遗漏"
    },
    {
      "factor": "3 个代码变更未关联需求",
      "severity": "medium",
      "evidence": "code_traceability 追溯率 80%，存在未归属变更",
      "recommendation": "确认是否为计划内的技术重构"
    }
  ],
  "summary": "8/10 需求点已实现，3/15 代码变更未归属，1 个高风险缺口需确认",
  "action_items": [
    "与开发确认 R5 密码重置功能的实现计划",
    "确认 3 个未归属代码变更的意图"
  ]
}
```

## forward_verification.json (v2)

正向用例中介验证结果。**顶层是平铺 JSON 数组**。**权威 schema 在 `_shared/schemas/forward_verification.schema.json`**；本节是人话索引，schema 与本节冲突时以 schema 为准。完整字段表见 [`_shared/TRACEABILITY_PROTOCOL.md`](../_shared/TRACEABILITY_PROTOCOL.md#forward_verificationjson-格式v2)。

> **v2 关键变化**：pass 必须带 `evidence`；pass + conf<70 schema 拒绝；ext_deps 非空的 pass 下游降级为 MS Prepare（不再是「Pass + caveat」）。

| 路径 | 来源 PHASES 步骤 | `case_id` 命名 | 必有字段 |
| --- | --- | --- | --- |
| 用例中介验证（常态） | 3.2.3 | 上游 `final_cases.json` 的 `case_id`（如 `M1-TC-01`） | `case_id` / `requirement_id` / `result` / `confidence` + 按 result 分支必填 evidence / actual / inconclusive_reason |
| 正向降级 / forward fallback | 3.2.4 | `FORWARD-TRACER-{requirement_id}` | 同上 |
| coverage-report 兜底合成 | 4.6 | `FORWARD-TRACER-FP-{N}` | `case_id` / `requirement_id` / `requirement_name` / `result` / `confidence` / `trace` / `source: "synthesized_from_coverage_report"`；兜底版 evidence 可缺，但下游 4.6a schema 校验会要求补 |

落盘后必须跑 `metersphere_helper.py validate-fv` 校验。

### 示例

```json
[
  {
    "case_id": "M1-TC-01",
    "requirement_id": "FP-1",
    "result": "pass",
    "confidence": 90,
    "trace": "applyCoupon(100, 50) -> min(coupon, order) -> min(100, 50) -> 50 == expected 50 ✓",
    "expected": "actual_discount == 50",
    "evidence": {
      "code_location": ["src/coupon.go:42"],
      "verification_logic": "min(coupon, order) 直接返回较小值，与 expected 50 一致",
      "considered_failure_modes": [
        {"mode": "coupon 为负数", "ruled_out_by": "上层 validateCoupon 已拦截负数（src/coupon.go:18）"}
      ]
    },
    "external_dependencies": {"types": [], "notes": ""}
  },
  {
    "case_id": "M2-TC-03",
    "requirement_id": "FP-2",
    "result": "inconclusive",
    "confidence": 50,
    "trace": "processor.Execute() 为接口方法，实际实现取决于运行时注入",
    "expected": "Review 类通知不展示『不再通知』",
    "actual": "无法在 diff 中确定具体 processor 实现",
    "inconclusive_reason": "dynamic_dispatch"
  },
  {
    "case_id": "FORWARD-TRACER-FP-3",
    "requirement_id": "FP-3",
    "requirement_name": "用户注销",
    "result": "fail",
    "confidence": 70,
    "trace": "兜底合成：源自 traceability_coverage_report.json 的 per-FP verdict，未做用例级代码路径追踪",
    "source": "synthesized_from_coverage_report"
  }
]
```

> 旧版本曾用 `{ source, total_cases, results: [...], summary: {...} }` 包装结构 + `case_id: "VC-1"` + `input` / `code_location` 字段。已废弃，下游消费方（metersphere-sync / 4S.1 缺陷提取）只读上述平铺数组格式。

## api_contract（traceability_coverage_report.json 内嵌字段）

API 契约一致性检查结果（条件产出，仅当代码变更涉及 API 交互时写入）。

### 完整结构

```json
{
  "overall_consistency": "consistent | inconsistent | partial | N/A",
  "checked_endpoints": 3,
  "issues_found": 1,
  "issues": [
    {
      "endpoint": "/api/v2/user/profile",
      "type": "field_mismatch | type_mismatch | path_mismatch | missing_param | extra_field",
      "severity": "high | medium | low",
      "description": "前端模型字段名与后端响应字段名不匹配",
      "frontend_expects": "user_name: String",
      "backend_provides": "username: String",
      "source_mr": "ios/taptap-ios!456",
      "confidence": 85
    }
  ],
  "source": "api-contract-validation | inline"
}
```

`overall_consistency` 取值：
- `consistent` — 所有检查的端点前后端定义一致
- `inconsistent` — 存在 high 级别不一致问题
- `partial` — 仅存在 medium / low 级别问题
- `N/A` — 未触发契约检查（代码变更不涉及 API）

`issues[].type` 取值：
- `field_mismatch` — 字段名不匹配（如 `user_name` vs `username`）
- `type_mismatch` — 字段类型不匹配（如 `String` vs `Int`）
- `path_mismatch` — 请求路径不一致
- `missing_param` — 后端要求的必填参数前端未传递
- `extra_field` — 前端期望的字段后端未提供

`issues[].severity` 判定规则：
- `high` — 类型不匹配、路径不匹配、必填参数缺失（会导致运行时错误）
- `medium` — 字段名不匹配但可能是命名风格差异（snake_case vs camelCase）、可选字段遗漏
- `low` — 前端有冗余字段（后端不提供但前端声明为可选）、字段顺序差异

## ui_fidelity_report.json

UI 还原度检查报告（条件产出）。

### 完整结构

```json
{
  "design_url": "https://figma.com/design/xxx/...",
  "page_url": "http://localhost:3000/coupon",
  "overall_fidelity": "high | medium | low",
  "comparison_mode": "visual+structural | structural-only",
  "summary": "一句话总结还原度情况",
  "statistics": {
    "total_differences": 5,
    "high_severity_count": 0,
    "medium_severity_count": 2,
    "low_severity_count": 3
  },
  "states_coverage": {
    "expected_states": ["default", "loading", "empty", "error"],
    "implemented_states": ["default", "loading", "error"],
    "missing_states": ["empty"],
    "coverage_rate": "75%"
  },
  "differences": [
    {
      "id": "UI-DIFF-1",
      "category": "spacing | color | typography | layout | missing_state | interaction",
      "severity": "high | medium | low",
      "design_value": "padding: 16px",
      "actual_value": "padding: 12px",
      "location": "优惠券卡片容器",
      "confidence": 85
    }
  ]
}
```

## defect_list.json

缺陷列表（smoke-test 模式条件产出）。从 forward_verification 的 fail 项、coverage gaps、API 契约问题中提取。

### 完整结构

```json
{
  "defects": [ ... ],
  "summary": { ... }
}
```

### defects

```json
{
  "id": "DEFECT-1",
  "name": "用户注册时密码强度校验缺失",
  "priority": "P0 | P1 | P2",
  "category": "implementation_missing | logic_error | api_inconsistency | ui_deviation",
  "description": "详细缺陷描述，包括背景、影响范围",
  "expected_result": "密码长度小于 8 位时应拒绝注册并提示'密码长度不足'",
  "actual_result": "代码中 validatePassword() 未检查长度限制，任意长度密码均可通过校验",
  "evidence": {
    "source": "forward_verification | coverage_gap | api_contract | ui_fidelity",
    "source_id": "VC-3",
    "requirement_ref": "R3",
    "code_location": "src/service/user.py:42",
    "confidence": 85
  },
  "related_mr": "project/path!123"
}
```

`priority` 判定规则：

- `P0` — 核心功能缺失或逻辑错误（forward_verification fail + confidence >= 85）；需求实现完全缺失且 risk_level == high；API 契约 high 级别不一致
- `P1` — 功能部分缺失或中等置信度逻辑错误（forward_verification fail + confidence >= 70）；需求实现缺失且 risk_level == medium；API 契约 medium 级别不一致；UI 高严重度差异
- `P2` — 其他已确认问题（partial 实现且 confidence 低、UI 中低严重度差异等）

`category` 取值：

- `implementation_missing` — 需求实现完全缺失（来自 coverage gaps）
- `logic_error` — 实现存在但逻辑不符合预期（来自 forward_verification fail）
- `api_inconsistency` — 前后端 API 契约不一致（来自 api_contract issues）
- `ui_deviation` — UI 还原度偏差（来自 ui_fidelity differences）

### summary

```json
{
  "total": 5,
  "by_priority": {
    "P0": 1,
    "P1": 2,
    "P2": 2
  },
  "by_category": {
    "implementation_missing": 1,
    "logic_error": 2,
    "api_inconsistency": 1,
    "ui_deviation": 1
  }
}
```

## smoke_test_report.json

冒烟测试报告（smoke-test 模式条件产出）。汇总验证统计和缺陷统计，包含 pass/fail 判定。

### 完整结构

```json
{
  "verdict": "pass | fail",
  "fail_reason": "发现 1 个 P0 缺陷：用户注册时密码强度校验缺失",
  "verification_summary": {
    "total_points": 20,
    "passed": 15,
    "failed": 3,
    "inconclusive": 2,
    "verification_rate": "90%"
  },
  "defect_summary": {
    "total": 5,
    "by_priority": {
      "P0": 1,
      "P1": 2,
      "P2": 2
    },
    "by_category": {
      "implementation_missing": 1,
      "logic_error": 2,
      "api_inconsistency": 1,
      "ui_deviation": 1
    }
  },
  "traceability_summary": {
    "requirement_coverage_rate": "80%",
    "code_traceability_rate": "85%",
    "bidirectional_confirmation_rate": "75%"
  },
  "low_confidence_items": [
    {
      "case_id": "VC-12",
      "requirement_ref": "R8",
      "result": "fail",
      "confidence": 55,
      "reason": "confidence < 70，未纳入缺陷列表"
    }
  ],
  "excluded_items": [
    {
      "requirement_ref": "R3",
      "exclusion_reason": "mr_not_merged",
      "detail": "MR !3606 处于 opened 状态，但 diff 中包含该需求的实现代码",
      "mr_ref": "project/path!3606"
    }
  ],
  "scope": "基于 3 个 MR 的代码变更和 20 个功能验证点"
}
```

`verdict` 判定规则：
- `fail` — `defect_summary.by_priority.P0 > 0`
- `pass` — `defect_summary.by_priority.P0 == 0`

`fail_reason`：仅当 `verdict == "fail"` 时填写，列出 P0 缺陷名称摘要。

`low_confidence_items`：forward_verification 中 `result == "fail"` 但 `confidence < 70` 的条目，未纳入 defect_list.json 但需关注。

`excluded_items`：因 MR 流程状态而排除、不计入缺陷的条目。每条记录包含需求引用、排除原因和详情。

`excluded_items[].exclusion_reason` 取值：
- `mr_not_merged` — MR 未合并，但 diff 中包含该需求的实现代码
- `out_of_scope` — 需求实现在未提供的 MR 中，不在本次评估范围
- `partial_mr_set` — 多 MR 拆分交付同一需求，仅提供了部分 MR

`traceability_summary`：从 `traceability_coverage_report.json` 中提取关键指标，便于快速了解回溯质量。

---

## report.md（smoke-test 模式专用，5S.2 阶段产出）

> 仅 `mode=smoke-test` 模式触发本节。最终上传到飞书云文档作为「冒烟测试报告」给 PM/Dev/QA 阅读。
>
> **关于符号约定**：状态标记使用中文方括号（`[通过]/[不通过]`、`[已覆盖]/[范围外]`、`[实证]/[推测]`），**禁止使用 emoji** ⭕/✅/⚠️/❌、**禁止 ASCII** `[OK]/[!]/[X]`、**禁止装饰性 emoji** 📋/🐛/📊/💡 章节前缀——实测飞书 import 会自动转换或破坏内容。

### 完整报告示例骨架

> 设计原则：飞书云文档名已经是「{需求名称}-冒烟测试报告-{YYYYMMDDHH}」，故 report.md **不写 H1 标题**，避免飞书导入后出现重复标题。

```markdown
## 0. 冒烟测试结论

判定：[通过] PASS
P0 缺陷数：0；存在 N 个 P1 级别缺陷，需在提测前修复。
整体置信度：均值 X%（最低 R6c 80%，最高 R6a 90%）。

**元数据**
- 需求名称：XXX
- 需求链接：https://...
- 需求文档：https://...
- 代码变更：cps/xxx-android!N — Draft: feat: XXX
- 测试用例：共 17 条（P0: 6, P1: 11）
- 报告时间：YYYY-MM-DD
- 分析方式：AI 静态分析（基于 MR diff） + 实机验证补充

## 1. 核心指标

- 验证点：13 个（[通过] 10 / [待定] 3）
- 需求覆盖率（范围内）：100%（8/8）
- 代码追溯率：100%（11/11 文件）
- 缺陷：2 个（P0: 0 / P1: 2 / P2: 0）

## 2. P0 用例评估（共 6/17）

> 仅列 P0 用例的逐条评估；P1+P2 用例的整体通过情况见 §3 双通道追溯结论。

- **{用例ID hex}** [P0] {用例名} — [通过]
- · 评估理由：{1-2 句}

- **{用例ID hex}** [P0] {用例名} — [待定]
- · 评估理由：{1-2 句，含未实证原因}

## 3. 双通道追溯结论

### 3.1 需求覆盖矩阵
- **R3** 版本更新页文案和进度展示 — [已覆盖] 置信度 87% [双向]
- **R6a** 无新宿主+已下载 → 显示"重启" — [已覆盖] 置信度 90% [双向]
- **R6c** 无新宿主+下载失败 → 显示插件大小 — [已覆盖] 置信度 80% [双向]
- **R1** 升级提示时机 — [范围外]
- **R2** 升级提示频率 — [范围外]

> 「[范围外]」说明：R1/R2/S1 属于已有基础设施，不在本 MR 实现范围内，不计入覆盖率缺口。

### 3.2 代码变更追溯
- DownSpeed.java → R3 [已覆盖]
- PluginUpgrade.kt（新增）→ R6b/R6c/R6d/R5 [已覆盖]
- ...

未追溯变更：0 个（本次 MR 所有变更文件都映射到了 R1-R7 需求点，无范围外改动）。

## 4. 缺陷清单

### DEF-01 [P1] 弱网/大文件场景下载进度条长时间停在 98% 附近

- 关联需求：R6b
- 关联用例：f9536a50（P1）
- 置信度：80% [推测，需实机验证]

**问题描述**
PluginUpgrade.kt 中使用假进度模拟，FAKE_DOWNLOAD_PROGRESS_PARTS=50，假进度总时长约 9.8 秒。当真实下载耗时超过 9.8 秒，进度条将长时间停在约 98%。

**预期行为**：进度条在接近 100% 后平滑等待，不出现长时间视觉卡顿。

> 以下代码块仅 Dev 排查问题时阅读，PM/QA 可跳过。

\```kotlin
// PluginUpgrade.kt - performDownload()
private const val FAKE_DOWNLOAD_PROGRESS_PARTS = 50
private const val FAKE_DOWNLOAD_PROGRESS_INTERVAL_MS = 200L
\```

**修复建议**：loop 结束后改为以低速率继续推进假进度（如每隔 1 秒 +0.1%），或切换为不确定性加载动画。

### DEF-02 [P1] 插件 size=0 时下载失败后按钮右侧显示"0 B"无意义文案
...

## 5. 其他观察

- **测试用例更新建议**：用例 18a970c3 步骤描述与实际行为不符，建议更新用例步骤
- **代码质量**：UpgradeStatusPresenterImpl.update() 中存在冗余的第二次调用，建议清理
- **待验证项（实机）**：用例 0fc33983「插件下载时不可暂停」的按钮交互超出 diff 可见范围
```

### 各章节格式规则

**第 0 章「冒烟测试结论」**

- 第一行格式固定：`判定：{标记} PASS|FAIL`，标记两选一：`[通过]` / `[不通过]`
  - **禁止 emoji** ✅/❌ 与 ASCII `[OK]/[X]`
- 紧跟一行 P0 缺陷数 + P1 缺陷数说明
- 必须包含「整体置信度」均值 + 最高/最低（来自需求覆盖矩阵）
- 元数据末尾必须包含 `分析方式：AI 静态分析（基于 MR diff）+ 实机验证补充`

**第 1 章「核心指标」**

- 用 bullet 列表（**不使用 markdown 表格**）
- 验证点用 `[通过]/[待定]/[失败]` 标状态计数
- 缺陷数按 P0/P1/P2 分级

**第 2 章「P0 用例评估（共 N/总数）」**

- 标题必须明确分子分母：`P0 用例评估（共 6/17）`，避免读者误以为只有 6 条用例
- 每个用例用「粗体用例 ID + bullet 列表」格式（参照 test-case-review TEMPLATES.md §6）：
  - `- **{用例ID}** [P0] {用例名} — [通过/待定/失败]`
  - `- · 评估理由：{1-2 句}`

**第 3 章「双通道追溯结论」**

- §3.1 需求覆盖矩阵：bullet 列表（**不使用表格**），格式 `- **{需求点ID}** {描述} — [已覆盖] 置信度 X% [双向/单向]` 或 `[范围外]`
- §3.2 代码变更追溯：bullet 列表，格式 `- {文件名} → {对应需求点列表} [已覆盖]`
- §3.2 末尾给出未追溯变更明确表述（**禁止"无范围蔓延"等含糊文案**）

**第 4 章「缺陷清单」**

- 每个缺陷用 `### DEF-NN [P0/P1/P2] {缺陷名}` H3 标题
- 必填字段：关联需求 / 关联用例 / 置信度（含 [实证]/[推测] 标记）
- 「问题描述」用普通段落
- 「预期行为」用粗体小节
- **代码块前必须加 quote 提示** `> 以下代码块仅 Dev 排查问题时阅读，PM/QA 可跳过`
- 「修复建议」用粗体小节

**第 5 章「其他观察」**

- 用 bullet 列表
- 每条用粗体短词分类：`**测试用例更新建议**` / `**代码质量**` / `**待验证项（实机）**`

### 关键约束

- 整份报告使用纯文本和分隔线排版，**不使用 markdown 表格**（飞书 import 后表格被拆成离散 text block，看起来像散文）
- 不写 H1 标题（飞书 doc 名已包含「{需求名称}-冒烟测试报告-{YYYYMMDDHH}」）
- **状态符号统一使用中文方括号**（非 emoji 非 ASCII）：
  - 测试结论：`[通过]` / `[不通过]`
  - 用例评估：`[通过]` / `[待定]` / `[失败]`
  - 需求覆盖：`[已覆盖]` / `[范围外]`
  - 实证置信度：`[实证]` / `[推测]`
  - 优先级：`[P0]` / `[P1]` / `[P2]`
- **禁止 emoji**：⭕ ✅ ⚠️ ❌（飞书 import 会破坏 — ❌ 触发 bitable，⭕ 转 `?` 或乱码）
- **禁止装饰性 emoji 章节前缀**：📋 🐛 📊 💡 — 飞书 import 会自动转 `[Doc] [Bug] [Chart] [Tip]` ASCII 形式
- **禁止 AI 助手署名**「本报告由 QA AI 助手...」— 用元数据「分析方式：AI 静态分析 + 实机验证补充」替代
- **代码块前必须加 quote 提示**「以下代码块仅 Dev 排查问题时阅读，PM/QA 可跳过」
- **§2 标题必须明确分子分母** `P0 用例评估（共 6/17）`，避免读者误以为只有 P0 用例
- **§3.2 未追溯变更必须明确表述**，禁止"无范围蔓延"等含糊文案
- **置信度逐条标注且需汇总到 §0**：每个需求点行尾标置信度 X%，§0 元数据汇总均值 + 极值

