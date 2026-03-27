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

## 双通道追溯模式

v0.0.10 引入双通道追溯，正向和反向使用不同的验证策略：

| 通道 | 方向 | 方法 | 回答的问题 |
| --- | --- | --- | --- |
| 正向通道 | 需求 → 代码 | 用例中介验证 | 需求是否被正确实现？ |
| 反向通道 | 代码 → 需求 | 直接代码追溯 | 代码有没有做需求之外的事？ |

### 正向通道：用例中介验证

不直接拿需求去"匹配"代码，而是先将需求拆解为结构化验证用例（具体输入→预期输出），然后 AI 逐条对照代码推理。

优势：迫使 AI 从"模糊映射"降维到"具体断言"，精度显著提升。

正向通道消费上游 `verification-test-gen` 的 `verification_cases.json`。如果上游未执行，本 skill 内置简化版用例生成。

### 反向通道：直接代码追溯

保持现有的 reverse-tracer Agent 模式 — 从代码变更出发，寻找每个变更对应的需求点。

优势：能检测"多余实现"和"范围蔓延"，这是正向通道无法做到的。

### UI 还原度检查（条件触发）

当需求有 Figma 设计稿链接时，正向通道额外执行 UI 还原度对比。使用 Figma MCP 获取设计数据/截图，Browser MCP 获取实现截图/DOM，AI 对比差异。输出 `ui_fidelity_report.json`，合并到 `coverage_report.json`。

触发条件：`design_link` 存在且前端页面可在浏览器中访问。

## 模型分层

按「错误代价」分配模型能力，详见 [CONVENTIONS.md](../../CONVENTIONS.md#模型分层策略)。

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 冗余对追溯 Agent（forward/reverse-tracer） | Opus | 追溯遗漏 = 需求缺口未被发现 |
| 正向用例中介验证 | Opus | 代码路径追踪需要深度推理 |
| UI 还原度检查 Agent | Opus | 视觉和结构差异识别需要精确对比 |
| 交叉验证和结果合并 | Sonnet | 规则化处理 |

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
| 3. map | 双通道并行：正向用例验证 + 反向代码追溯 | `code_analysis.md` |
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
