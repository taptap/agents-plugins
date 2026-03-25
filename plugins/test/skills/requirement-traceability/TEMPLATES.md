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
      "confidence": "[已确认]"
    }
  ],
  "status": "covered | partial | missing"
}
```

`change_id` 取值：MR/PR 模式下为 MR/PR 标识（如 `project/path!123` 或 `owner/repo#456`）；本地 diff 模式下为文件名或自动生成的序号（如 `diff-1`）。

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
