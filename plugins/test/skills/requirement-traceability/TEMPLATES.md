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

## coverage_report.json

### 完整结构

```json
{
  "requirement_coverage": { ... },
  "code_traceability": { ... },
  "tracing_metadata": { ... },
  "gaps": [ ... ]
}
```

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
