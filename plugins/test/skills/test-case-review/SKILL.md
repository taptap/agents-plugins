---
name: test-case-review
description: >
  评审已有测试用例的覆盖度和质量。输入测试用例 + 需求文档，
  输出 review_result.json + review_summary.md + 可选 supplementary_cases.json。
  触发：用例评审、测试覆盖率、补充用例、用例质量。
---

# 测试用例评审

## Quick Start

- Skill 类型：独立 skill
- 适用场景：对照需求文档和设计稿评审已有测试用例，识别覆盖缺口和质量问题，并生成补充用例
- 必要输入：测试用例（JSON 文件、文本或上游产出）必须非空；需求来源（链接或本地文档）推荐提供
- 输出产物：`review_result.json`、`review_summary.md`、可选 `supplementary_cases.json`、`requirement_points.md`
- 失败门控：测试用例为空时停止；未在需求或用例中出现的信息不能凭经验下结论
- 执行步骤：`init → fetch → understand → review → summary → output`

## 与其他 skill 的关系

- **test-case-generation**：生成新测试用例（含内置快速评审）。本 skill 专注于**独立深度评审已有用例**，可接收 test-case-generation 的 `final_cases.json` 作为输入
- **change-analysis**：分析代码变更的测试覆盖。本 skill 不涉及代码变更分析，专注用例本身质量

> **注意**：如果输入的用例来自 `test-case-generation` 的 `final_cases.json`（已含冗余对评审），本 skill 的评审价值有限——建议仅在需要额外独立视角评审、或用例经过人工修改后使用。

## 核心能力

- 需求理解 — 解析需求文档，提炼编号功能点清单（RP-1, RP-2, ...）
- 设计稿对照 — 解析设计稿，对照页面状态和交互逻辑
- 4 维度评审 — 需求覆盖率、场景完整性、用例正确性、用例规范性
- 补充用例生成 — 生成补充用例写入 JSON 文件
- 报告输出 — 生成评审报告

## 评审原则

1. **需求驱动** — 以需求文档为基准，所有结论基于实际数据
2. **逐项验证** — 功能点清单逐项检查，不允许跳过
3. **防幻觉** — 禁止猜测，未在文档或用例中出现的内容不做判断
4. **分层评审** — 先覆盖率（有没有）→ 完整性（够不够深）→ 正确性（对不对）→ 规范性（写得好不好）
5. **可操作性** — 输出具体可执行的改进建议
6. **完整性验证** — 每阶段结束输出处理进度

## 交叉验证（可选）

当运行环境支持并行 Agent 且功能点 > 5 个时，review 阶段可启用交叉验证模式（详见 [AGENT_PROTOCOL — 交叉验证协议](../_shared/AGENT_PROTOCOL.md#交叉验证协议)）：

- **视角 A（覆盖率）**：聚焦需求覆盖率维度和场景完整性维度
- **视角 B（质量）**：聚焦用例正确性维度和用例规范性维度
- 两个视角独立产出发现列表后交叉验证，双方确认的问题标记为 confirmed
- 不满足条件时退回单 Agent 串行评审（默认流程）

## 4 大评审维度

| 维度 | 优先级 | 核心检查项 |
| --- | --- | --- |
| 需求覆盖率 | P0 | 需求功能点逐一映射、设计稿交互覆盖、正向/反向流程 |
| 场景完整性 | P0 | 端到端闭环、跨场景联动、边界值、异常路径、状态流转 |
| 用例正确性 | P1 | 预期结果正确性、步骤逻辑、优先级合理性 |
| 用例规范性 | P2 | 命名清晰、步骤具体可执行、预期明确可验证、前置条件完整 |

各维度的详细检查项见 [CHECKLIST.md](CHECKLIST.md)。

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 需求理解、功能点提炼 | Opus | 理解偏差导致评审方向错误 |
| 覆盖率和完整性评审 | Opus | 遗漏覆盖缺口 = 缺陷逃逸 |
| 正确性和规范性评审 | Sonnet | 规则化检查 |
| 补充用例生成 | Sonnet | 模板化生成 |

## 可用工具

共享脚本（飞书/GitLab/GitHub）用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。以下为本 skill 特有工具：

### Figma MCP

仅当 fetch 阶段发现 Figma 链接时使用，按分级协议获取，详见 [shared-tools/SKILL.md](../shared-tools/SKILL.md#figma-设计稿获取)。

## 阶段流程

按以下 6 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证输入，确认用例和需求来源 | — |
| 2. fetch | 获取需求文档、设计稿、测试用例 | `review_data.md` |
| 3. understand | 提炼编号功能点清单 | `requirement_points.md` |
| 4. review | 4 维度逐项评审 | `tc_review_detail.md` |
| 5. summary | 统计汇总 + 补充用例生成 | `review_summary.md`、`supplementary_cases.json` |
| 6. output | 结构化输出 | `review_result.json` |

## 输出格式

### review_result.json

```json
{
  "total_requirement_points": 12,
  "total_test_cases": 45,
  "dimensions": {
    "coverage": {
      "rate": "83%",
      "uncovered_points": ["RP-3", "RP-7"],
      "issues_count": 2
    },
    "completeness": {
      "issues_count": 5,
      "critical_gaps": ["..."]
    },
    "correctness": {
      "issues_count": 3,
      "critical_issues": ["..."]
    },
    "quality": {
      "issues_count": 4,
      "suggestions": ["..."]
    }
  },
  "overall_assessment": "...",
  "action_items": ["..."]
}
```

### supplementary_cases.json（可选）

使用 [CONVENTIONS.md 用例 JSON 格式](../../CONVENTIONS.md#用例-json-格式)。

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `review_data.md` | fetch | 需求摘要 + 用例列表 |
| `requirement_points.md` | understand | 编号功能点清单 |
| `tc_review_detail.md` | review | 4 维度评审结果（中间文件，供 output 阶段消费生成 `review_result.json`） |
| `review_summary.md` | summary | 统计 + 改进建议 + 补充用例清单 |
| `supplementary_cases.json` | summary | 补充用例（可选） |

## Closing Checklist（CRITICAL）

skill 执行的最终阶段（output）完成后，**必须**逐一验证以下产出文件：

- [ ] `review_result.json` — 非空，包含 `dimensions` 和 `overall_assessment` 字段
- [ ] `review_summary.md` — 非空，包含统计数据和改进建议
- [ ] `requirement_points.md` — 非空，包含编号功能点清单
- [ ] `supplementary_cases.json` — 可选，仅当存在覆盖缺口时生成

全部必须项通过后，输出完成总结。如任一必须文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 约束规则

- **只读评审** — 只产出评审报告和补充用例 JSON，不修改已有用例
- **数据门控** — 测试用例为空时停止评审
- **防幻觉** — 未在需求或用例中出现的信息不能凭经验下结论
- **逐项验证** — 功能点清单逐项检查，不允许跳过
- **中间文件回读** — 后续阶段引用前序数据必须通过 Read 工具回读文件，不依赖上下文记忆
- **语言** — Chat 输出和报告使用中文；技术术语、文件路径保持原样
- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
