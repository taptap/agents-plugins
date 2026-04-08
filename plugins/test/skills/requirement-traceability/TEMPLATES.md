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

## forward_verification.json

正向用例中介验证结果。

### 完整结构

```json
{
  "source": "upstream | inline",
  "total_cases": 15,
  "results": [
    {
      "case_id": "VC-1",
      "requirement_id": "R1",
      "input": {"coupon_amount": 100, "order_amount": 50},
      "expected": "actual_discount == 50",
      "result": "pass | fail | inconclusive",
      "confidence": 90,
      "trace": "applyCoupon() -> min(coupon, order) -> min(100, 50) -> 50 == expected 50",
      "code_location": "coupon-service/apply.go:42"
    }
  ],
  "summary": {
    "passed": 12,
    "failed": 2,
    "inconclusive": 1,
    "pass_rate": "80%"
  }
}
```

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
