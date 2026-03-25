---
name: bug-fix-review
description: >
  分析 Bug 修复代码变更的完整性和残余风险。输入 Bug 链接或本地 Bug 描述文件，
  输出 fix_analysis.json + risk_assessment.json。
---

# Bug 修复分析

## Quick Start

- Skill 类型：独立 skill
- 适用场景：Bug 修复的 MR/PR 合并后，分析修复的完整性、副作用和残余风险
- 必要输入：Bug 链接或本地 Bug 描述文件（至少一个）；关联代码变更（MR/PR）必须非空
- 输出产物：`fix_analysis.json`、`risk_assessment.json`、`code_analysis.md`
- 失败门控：关联代码变更为空时停止
- 执行步骤：`init → fetch → analyze → output`

## 核心能力

- Bug 信息提取 — 解析 Bug 描述、优先级、严重程度
- 代码变更分析 — 获取 MR/PR diff，分类变更文件
- 根因分析 — 基于代码变更推断缺陷根因
- 修复完整性评估 — 判断修复是否完整，是否有副作用
- 残余风险评估 — 评估修复后的残余风险和回归建议

## 分析原则

1. **代码驱动** — 所有结论基于实际代码变更
2. **置信度标注** — 根因分析标注置信度（已确认/基于 diff/推测）
3. **副作用关注** — 修复变更是否可能引入新问题
4. **回归建议** — 输出具体的回归测试建议

## 可用工具

### 1. MR/PR 搜索和分析脚本

用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。

### 2. 飞书文档获取脚本

用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。

## 阶段流程

按以下 4 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证 Bug 信息和代码变更列表 | — |
| 2. fetch | 获取 Bug 详情和代码 diff | `bug_description.md`、`analysis_checklist.md` |
| 3. analyze | 根因分析 + 修复完整性评估 | `code_analysis.md`、`fix_analysis.json` |
| 4. output | 风险评估和最终产出 | `risk_assessment.json` |

## 输出格式

### fix_analysis.json

```json
{
  "bug_id": "...",
  "bug_name": "...",
  "severity": "...",
  "root_cause": {
    "description": "...",
    "confidence": "[已确认] | [基于 diff] | [推测]",
    "affected_files": ["..."]
  },
  "fix_assessment": {
    "completeness": "complete | partial | insufficient",
    "changes_summary": ["..."],
    "side_effects": [
      { "description": "...", "risk_level": "high | medium | low" }
    ]
  },
  "regression_suggestions": ["..."]
}
```

### risk_assessment.json

```json
{
  "overall_risk": "high | medium | low",
  "risk_factors": [
    {
      "factor": "...",
      "severity": "high | medium | low",
      "evidence": "...",
      "recommendation": "..."
    }
  ],
  "summary": "...",
  "action_items": ["..."]
}
```

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 关联代码变更（MR/PR）必须非空
- Bug 描述中如含飞书链接，用 `fetch_feishu_doc.py` 获取补充信息
