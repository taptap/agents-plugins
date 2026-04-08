---
name: bug-fix-review
description: >
  [已废弃] Bug 修复分析能力已合并到 change-analysis（Bug 场景）。
  当用户提到 Bug 修复分析时，引导到 change-analysis。
---

# Bug 修复分析（已废弃）

本 skill 的全部能力已合并到 [change-analysis](../change-analysis/SKILL.md) 的 Bug 场景。

使用方式：调用 change-analysis 并提供 Bug 链接 + 代码变更，即可获得完整的根因分析、修复完整性评估和 `risk_assessment.json` 输出。

按「错误代价」分配模型能力，详见 [CONVENTIONS.md](../../CONVENTIONS.md#模型分层策略)。

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 根因分析、修复完整性评估 | Opus | 误判根因 = 修复方向错误 |
| 副作用评估 | Opus | 遗漏副作用 = 引入新缺陷 |
| 报告生成 | Sonnet | 模板化输出 |

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
| 3. analyze | 根因分析 + 修复完整性评估 | `code_analysis.md`、`bug_fix_analysis.json` |
| 4. output | 风险评估和最终产出 | `risk_assessment.json` |

## 输出格式

### bug_fix_analysis.json

```json
{
  "bug_id": "...",
  "bug_name": "...",
  "severity": "...",
  "root_cause": {
    "description": "...",
    "confidence": 85,
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

## 与其他 skill 的关系

- **change-analysis**：提供 Story/Bug 双场景的完整变更分析。本 skill 专注 Bug 修复的深度根因分析和修复完整性评估，可被 change-analysis 的 Bug 场景调用以获取更深度的分析

## Closing Checklist（CRITICAL）

skill 执行的最终阶段（output）完成后，**必须**逐一验证以下产出文件：

- [ ] `bug_fix_analysis.json` — 非空，包含 root_cause 和 fix_assessment 字段
- [ ] `risk_assessment.json` — 非空，包含 overall_risk 和 risk_factors
- [ ] `code_analysis.md` — 非空，包含逐文件分析记录

全部必须项通过后，输出完成总结。如任一必须文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 代码变更（MR/PR 链接、本地 diff 文件、diff 文本）必须至少有一个来源非空
- Bug 描述中如含飞书链接，用 `fetch_feishu_doc.py` 获取补充信息
