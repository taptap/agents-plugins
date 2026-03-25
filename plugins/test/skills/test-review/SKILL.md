---
name: test-review
description: >
  评审测试用例的覆盖度和质量。输入上游生成的用例（test_cases.json）+ 需求链接或本地需求文档，
  输出 review_result.md + final_cases.json。
---

# 测试评审

## Quick Start

- Skill 类型：核心工作流
- 适用场景：对照需求评审测试用例的覆盖度、完整性、正确性和规范性
- 必要输入：`test_cases.json`（上游 test-design 产出或手动提供的本地用例 JSON）；需求链接、本地需求文档或上游 `requirement_points.json`
- 输出产物：`final_cases.json`、`review_result.md`、`summary.md`、`review_summary.json`
- 失败门控：`test_cases.json` 必须可用，否则停止；未在需求或用例中出现的信息不凭经验下结论
- 执行步骤：`init → fetch → understand → review → summary → output`

## 核心能力

- 需求理解 — 解析需求文档或消费上游澄清结果，提炼编号功能点清单
- 灵活输入 — 可评审上游 test-design 生成的用例，也可评审手动提供的本地用例 JSON
- 4 维度评审 — 需求覆盖率、场景完整性、用例正确性、用例规范性
- 补充用例生成 — 为覆盖缺口生成补充用例
- 最终用例集 — 产出评审通过 + 补充的完整用例集供下游消费

## 评审原则

1. **需求驱动** — 以需求文档为基准，所有结论基于实际数据
2. **逐项验证** — 功能点清单逐项检查，不允许跳过
3. **防幻觉** — 禁止猜测，未在文档或用例中出现的内容不做判断
4. **分层评审** — 覆盖率（有没有）→ 完整性（够不够深）→ 正确性（对不对）→ 规范性（写得好不好）
5. **可操作性** — 输出具体可执行的改进建议

## 4 大评审维度

| 维度 | 优先级 | 核心检查项 |
| --- | --- | --- |
| 需求覆盖率 | P0 | 需求功能点逐一映射、正向/反向流程 |
| 场景完整性 | P0 | 端到端闭环、边界值、异常路径、状态流转 |
| 用例正确性 | P1 | 预期结果正确性、步骤逻辑、优先级合理性 |
| 用例规范性 | P2 | 命名清晰、步骤可执行、预期可验证、前置完整 |

各维度的详细检查项见 [CHECKLIST.md](CHECKLIST.md)。

## 可用工具

### 1. 飞书文档获取脚本

用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。

### 2. Figma MCP

`get_figma_data(url="<链接>")` — 获取设计稿布局/组件/交互数据。

## 阶段流程（6 阶段）

详见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证预取数据，确认输入来源 | — |
| 2. fetch | 获取需求文档和用例数据 | `review_data.md` |
| 3. understand | 提炼编号功能点清单 | `requirement_points.md` |
| 4. review | 4 维度逐项评审 | `review_result.md` |
| 5. summary | 汇总统计 + 生成补充用例 | `summary.md`、`supplementary_cases.json` |
| 6. output | 合并为最终用例集 | `final_cases.json` |

## 输出格式

### final_cases.json

评审通过的用例 + 补充用例的完整集合，供下游 requirement-traceability 消费。

基础字段定义见 [CONVENTIONS.md](../../CONVENTIONS.md#用例-json-格式)。在此基础上新增 `source` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source` | string | 用例来源：`upstream`（上游 test-design）/ `supplementary`（本 skill 补充） |

## 中间文件

| 文件 | 阶段 | 内容 |
| --- | --- | --- |
| `review_data.md` | fetch | 需求摘要 + 用例列表 |
| `requirement_points.md` | understand | 编号功能点清单 |
| `review_result.md` | review | 4 维度评审结果 |
| `summary.md` | summary | 统计 + 改进建议 + 补充用例清单 |
| `supplementary_cases.json` | summary | 补充用例 |
| `final_cases.json` | output | 评审通过 + 补充的完整用例集 |

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- `test_cases.json` 必须可用（上游 test-design 产出或手动提供），否则停止评审
