---
name: change-analysis
description: >
  分析代码变更的影响面和测试覆盖。输入 Story/Bug 链接或需求文档 + 代码变更（MR/PR 或本地 diff），
  输出 change_analysis.json + change_coverage_report.json + 可选 supplementary_cases.json。
  触发：变更分析、影响分析、测试覆盖分析、Bug 修复分析。
---

# 代码变更影响分析

## Quick Start

- Skill 类型：核心工作流
- 适用场景：分析 Story 关联代码变更对功能、调用链、测试覆盖的影响；或分析 Bug 修复变更的完整性与残余风险
- 必要输入：代码变更（MR/PR 链接、本地 diff、或直接提供 diff 文本）必须非空；需求来源（Story/Bug 链接或本地文档）推荐提供
- 输出产物：
  - Story 场景：`change_analysis.json`、`code_change_analysis.md`、`test_coverage_report.md`、`change_coverage_report.json`、可选 `supplementary_cases.json`
  - Bug 场景：`change_analysis.json`、`code_change_analysis.md`、`change_fix_analysis.json`、`risk_assessment.json`
- 失败门控：关联代码变更（MR/PR/diff）不能为空；无法确认的信息必须标记为"推测"或"待确认"
- 执行步骤：Story 7 阶段 / Bug 5 阶段，详见 [PHASES.md](PHASES.md)

## 意图识别

根据用户输入确定执行路径：

| 输入 | 动作 |
|------|------|
| Story 链接 / 需求文档 + 代码变更 | → Story 场景（7 阶段） |
| Bug 链接 / Bug 描述 + 代码变更 | → Bug 场景（5 阶段） |
| 仅 MR/PR 链接无需求来源 | → 询问关联 Story/Bug，或降级为纯代码变更分析 |
| 本地 diff + 需求文档 | → 根据需求类型判断场景 |
| 模糊输入 | → 询问用户提供需求来源和代码变更 |

## 场景说明

- **Story 场景**：7 阶段 — init → fetch → diff/context/callgraph → impact → coverage → generate → output
- **Bug 场景**：5 阶段 — init → fetch → diff/context → analyze → output（不做覆盖评估和用例生成）

## 与其他 skill 的关系

- **requirement-traceability**：专注需求与代码的双通道追溯矩阵。本 skill 的 Story 场景侧重影响面和测试覆盖，追溯矩阵请使用 requirement-traceability
- **test-case-generation**：本 skill 的补充用例是针对变更覆盖缺口的补充，完整的需求驱动用例生成请使用 test-case-generation

## 分析原则

1. **系统性** — 按标准化工作流逐步分析
2. **可追溯** — 所有结论有代码/数据依据；无法确认的标注为"推测"或"基于 diff"，禁止将推测标注为"已确认"
3. **风险优先** — 优先关注高风险变更
4. **清单驱动** — fetch 完成后创建 `change_checklist.md`，后续逐项处理并标记状态；每阶段结束输出完成度
5. **分治处理** — 多 MR 逐个分析，每个完成后立即增量写入 `code_change_analysis.md`

## 置信度标记

| 标记 | 含义 |
| --- | --- |
| 已确认 | 通过代码/数据验证 |
| 基于 diff | 仅基于 diff 推断 |
| 推测 | 合理推测但未验证 |

置信度量化评分见 [CONVENTIONS](../../CONVENTIONS.md#量化置信度评分)。

## 交叉验证（可选）

当运行环境支持并行 Agent 且变更文件 > 3 个时，阶段 3-5 可启用交叉验证模式（详见 [AGENT_PROTOCOL — 交叉验证协议](../_shared/AGENT_PROTOCOL.md#交叉验证协议)）：

- **视角 A（代码分析）**：聚焦变更影响面、调用链追踪、风险识别
- **视角 B（测试覆盖）**：聚焦覆盖缺口、测试建议、回归范围
- 两个视角独立分析后交叉验证，双方确认的风险标记为 confirmed
- 不满足条件时退回单 Agent 串行分析（默认流程）

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 影响面评估、根因分析 | Opus | 遗漏关键影响 = 生产事故 |
| 代码变更分析 | Opus | 代码路径追踪需要深度推理 |
| 测试覆盖评估 | Sonnet | 规则化比对 |
| 用例生成、报告输出 | Sonnet | 模板化工作 |

## 可用工具

共享脚本（飞书/GitLab/GitHub）用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。以下为本 skill 特有工具：

### 1. MR/PR 搜索脚本

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/search_mrs.py <story_id>
python3 $SKILLS_ROOT/shared-tools/scripts/search_prs.py <story_id>
```

自动搜索所有仓库中关联的 MR/PR，输出 JSON 到 stdout。

### 2. GitLab 辅助脚本

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-diff <project_path> <mr_iid>
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-detail <project_path> <mr_iid>
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py file-content <project_path> <file_path> [--ref master]
```

### 3. GitHub 辅助脚本

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-diff <owner/repo> <pr_number>
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-detail <owner/repo> <pr_number>
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py file-content <owner/repo> <file_path> [--ref main]
```

### 4. Figma MCP

仅当 fetch 阶段发现 Figma 链接时使用（设计稿在变更分析中优先级低），按分级协议获取，详见 [shared-tools/SKILL.md](../shared-tools/SKILL.md#figma-设计稿获取)。

## 按需扩展模块

| 模块 | 触发方式 | 文档 |
| ---- | -------- | ---- |
| Android 三方交互外部影响评估 | **阶段 3A 强制执行命中检测**，命中时自动激活 | [EXTERNAL-IMPACT.md](EXTERNAL-IMPACT.md) |

> ⚠️ **Android MR 必须执行命中检测**：凡仓库名/路径含 `android` 的 MR，在阶段 3A 必须将所有变更文件路径与 EXTERNAL-IMPACT.md「命中判断规则」表逐条比对，并将检测结果（命中/未命中）写入 `change_checklist.md`。**不允许静默跳过**。

命中后在 `code_change_analysis.md` 追加外部影响评估章节、在 `test_coverage_report.md` 追加外部影响测试访问评估章节，并将新增用例合并写入 `supplementary_cases.json`。

## 阶段流程

### Story 场景（7 阶段）

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证输入，确认代码变更来源 | — |
| 2. fetch | 获取需求文档和代码变更列表 | `change_checklist.md` |
| 3. diff/context/callgraph | 逐代码变更深度分析 | `code_change_analysis.md` |
| 4. impact | 影响面评估 | 追加写入 `code_change_analysis.md` |
| 5. coverage | 测试覆盖评估 | `test_coverage_report.md` |
| 6. generate | 为覆盖缺口生成补充用例 | `supplementary_cases.json` |
| 7. output | 结构化输出 | `change_analysis.json`、`change_coverage_report.json` |

> **Android 三方交互命中时（按需）**：`code_change_analysis.md` 追加外部影响评估章节，`test_coverage_report.md` 追加外部影响测试访问评估章节，`supplementary_cases.json` 合并外部影响建议用例。不新增文件，详见 [EXTERNAL-IMPACT.md](EXTERNAL-IMPACT.md)。

### Bug 场景（5 阶段）

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证 Bug 信息和代码变更 | — |
| 2. fetch | 获取 Bug 详情和代码 diff | `bug_description.md`、`change_checklist.md` |
| 3. diff/context | 逐代码变更分析 | `code_change_analysis.md` |
| 4. analyze | 根因分析 + 修复完整性评估 | `change_fix_analysis.json` |
| 5. output | 风险评估和最终产出 | `change_analysis.json`、`risk_assessment.json` |

各阶段详细操作见 [PHASES.md](PHASES.md)。

## 输出格式

### change_analysis.json（通用）

```json
{
  "scenario": "story | bug",
  "summary": "一句话总结",
  "risk_level": "high | medium | low",
  "changes_analyzed": 3,
  "key_findings": ["..."],
  "action_items": ["..."]
}
```

### change_coverage_report.json（Story 场景）

```json
{
  "coverage_rate": "75%",
  "total_change_points": 12,
  "covered": 9,
  "gaps": [
    {
      "change_point": "变更点描述",
      "risk_level": "high | medium | low",
      "recommendation": "建议"
    }
  ]
}
```

### change_fix_analysis.json（Bug 场景）

```json
{
  "bug_name": "...",
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

### supplementary_cases.json（Story 场景，可选）

使用 [CONVENTIONS.md 用例 JSON 格式](../../CONVENTIONS.md#用例-json-格式)。

## Closing Checklist（CRITICAL）

skill 执行的最终阶段完成后，**必须**根据场景逐一验证以下产出文件：

**Story 场景：**
- [ ] `change_analysis.json` — 非空，包含变更分类和影响面分析
- [ ] `code_change_analysis.md` — 非空，包含代码变更分析过程
- [ ] `test_coverage_report.md` — 非空，包含测试覆盖评估
- [ ] `change_coverage_report.json` — 非空，包含结构化覆盖数据
- [ ] `supplementary_cases.json` — 可选，仅当存在测试覆盖缺口时生成

**Bug 场景：**
- [ ] `change_analysis.json` — 非空，包含变更分类和影响面分析
- [ ] `code_change_analysis.md` — 非空，包含代码变更分析过程
- [ ] `change_fix_analysis.json` — 非空，包含修复完整性评估

全部必须项通过后，输出完成总结。如任一必须文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 约束规则

- **只写分析** — 只产出分析报告和用例 JSON，不修改源代码
- **数据门控** — 代码变更（MR/PR/diff）不能为空；需求文档缺失时降级继续，基于代码变更生成分析
- **引用格式** — 引用对象使用完整自然语言描述，不使用编号缩写
- **中间文件回读** — 后续阶段引用前序数据必须通过 Read 工具回读文件，不依赖上下文记忆
- **语言** — Chat 输出和报告使用中文；技术术语、文件路径、函数名保持原样
- 回读中间文件、中断恢复、脚本路径等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- **Android MR 三方交互检测强制执行** — 阶段 3A 必须对 Android MR 执行命中检测并将结果写入 `change_checklist.md`，检测结果是后续阶段 4 和阶段 6 是否激活外部影响评估的依据
