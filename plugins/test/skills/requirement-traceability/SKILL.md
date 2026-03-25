---
name: requirement-traceability
description: >
  双向追溯需求与代码变更的映射关系。输入需求描述 + 代码变更（MR/PR 或本地 diff），
  输出 traceability_matrix.json + coverage_report.json + risk_assessment.json。
---

# 需求回溯

## Quick Start

- Skill 类型：核心工作流
- 适用场景：功能开发完成后，验证代码变更是否完整覆盖需求
- 必要输入：代码变更（MR/PR 链接、本地 diff 文件、或直接提供 diff 文本）必须非空；需求描述推荐提供，缺失时基于代码变更做单边追溯（降级模式）
- 输出产物：`traceability_matrix.json`、`coverage_report.json`、`risk_assessment.json`
- 失败门控：代码变更为空时停止；无法确认的映射标记为 `[推测]`
- 执行步骤：`init → fetch → map → output`

## 核心能力

- 代码变更分析 — 解析代码 diff，分类变更文件，识别变更类型和影响范围
- 双向追溯 — 需求 → 代码 和 代码 → 需求 的双向映射
- 覆盖缺口识别 — 找出未被代码实现的需求和未关联需求的代码变更
- 风险评估 — 基于缺口和变更复杂度评估残余风险

## 追溯原则

1. **双向验证** — 需求→代码 和 代码→需求 两个方向都要检查
2. **可追溯** — 所有结论有代码/数据依据，无法确认的标注为推测
3. **风险优先** — 优先关注高风险变更和覆盖缺口
4. **分治处理** — 多个代码变更逐个分析，每个完成后立即增量写入
5. **完整性验证** — 每阶段结束确认处理进度

置信度标记见 [CONVENTIONS](../../CONVENTIONS.md#置信度标记)。

## 可用工具

### 1. MR/PR 搜索和分析脚本

用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。包括 MR/PR 搜索、diff 获取、详情查询、文件内容获取。仅当输入为 MR/PR 链接时使用。

### 2. 飞书文档获取脚本

用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。

### 3. Figma MCP

`get_figma_data(url="<链接>")` — 获取设计稿数据。仅当 fetch 阶段发现 Figma 链接时使用。

## 阶段流程

按以下 4 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证输入，确认代码变更来源 | — |
| 2. fetch | 获取需求文档和代码 diff | `analysis_checklist.md` |
| 3. map | 构建需求↔代码双向映射 | `code_analysis.md` |
| 4. output | 覆盖验证、风险评估和最终产出 | `traceability_matrix.json`、`coverage_report.json`、`risk_assessment.json` |

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `analysis_checklist.md` | fetch | 需求点和代码变更清单 |
| `code_analysis.md` | map | 逐代码变更的分析记录 |

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 代码变更必须非空，这是唯一的阻断条件
- 需求文档缺失时继续分析（降级模式），基于代码变更做单边追溯
- 代码变更支持三种来源：MR/PR 链接（GitLab/GitHub）、本地 diff 文件、直接提供的 diff 文本
