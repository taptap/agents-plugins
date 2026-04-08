---
name: test-case-generation
description: >
  根据需求文档和澄清结果拆解功能模块，生成结构化测试用例，并通过冗余对评审确保质量。
  输入需求链接、本地需求文档或上游澄清结果，输出 final_cases.json。
---

# 测试用例生成

## Quick Start

- Skill 类型：核心工作流
- 适用场景：基于需求文档或上游澄清结果，拆解功能模块、生成测试用例、冗余对评审、用户确认，输出可入库的最终用例集
- 必要输入：需求链接、本地需求文档，或上游 `clarified_requirements.json` + `requirement_points.json`（至少一个）
- 输出产物：`final_cases.json`（必须）、`test_cases.json`（review 前中间版本）、`tc_gen_review.md`、`review_summary.json`、`decomposition.md`、`context_summary.md`（仅 >= 3 模块时生成）
- 失败门控：需求正文不可读时停止生成；所有用例必须严格基于需求，不补充未提及功能
- 执行步骤：`init → understand → decompose → generate → review → confirm → output`

## 核心能力

- 需求理解 — 解析需求文档或消费上游澄清结果
- 多视角并行分析 — 复杂需求时启动功能/异常/用户 3 个视角 Agent 并行分析需求，交叉验证
- 功能拆解 — 将需求拆解为独立的功能模块，提炼全局上下文摘要
- 并行生成 — 使用 test-case-writer 子 Agent 为每个模块并行生成用例（含置信度评分）
- 冗余对评审 — 2 个独立 review Agent 并行评审用例的覆盖度和质量，共识发现自动加成置信度
- 用户确认 — 不确定的问题抛给用户确认，避免评审幻觉
- 质量审查 — 跨模块去重、覆盖度检查、方法覆盖度验证、置信度过滤

## 用例生成原则

1. **忠于原文** — 严格基于需求描述，不臆断未提及的功能
2. **方法驱动** — 根据功能特征选择合适的测试设计方法，每条用例标注所用方法
3. **独立原子** — 每个用例原子化，前置条件描述环境状态，不依赖其他用例
4. **步骤对应** — 每个测试步骤内嵌对应的预期结果，结构化配对，每步一个操作
5. **全面覆盖** — 需求功能点逐一映射，无遗漏

## 评审维度与原则

详见 [CHECKLIST.md](CHECKLIST.md)（5 条评审原则 + 4 大维度 + 详细检查项）。

## 测试设计方法论

生成用例时必须有方法论依据。各方法的详细操作指南见 [METHODS.md](METHODS.md)。

### 方法选择指引

| 功能特征 | 推荐方法 | 典型优先级 |
| --- | --- | --- |
| 输入框/表单字段 | 等价类划分 + 边界值分析 | 有效类 P0-P1，无效类 P1-P2，边界 P1 |
| 数值范围/长度限制 | 边界值分析（必选）+ 等价类划分 | 常见边界 P1，极端边界 P3 |
| 多条件组合规则 | 判定表法 + 等价类划分 | 核心组合 P1，次要组合 P2 |
| 状态流转/生命周期 | 状态迁移法 + 场景法 | 合法迁移 P0-P1，非法迁移 P1-P2 |
| 端到端业务流程 | 场景法 | 主流程 P0，备选流程 P1，异常中断 P2 |
| 以上方法覆盖后的补充 | 错误推测法 | P2-P3 |

## 优先级规则

| 优先级 | 适用场景 |
| --- | --- |
| P0 | 核心业务主流程正向验证、关键功能基本可用性 |
| P1 | 重要异常处理、常见边界值、权限校验、合法状态迁移 |
| P2 | 一般功能场景、非核心边界值、组合场景 |
| P3 | 极端边界、低频场景、兼容性、性能相关 |

参考分布：P0 约 15-25%，P1 约 30-40%，P2 约 25-35%，P3 约 5-15%。

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 需求理解和多视角分析 | Opus | 理解偏差会级联影响所有用例 |
| 功能模块拆解 | Opus | 拆解质量决定覆盖完整性 |
| 测试用例生成（test-case-writer） | Sonnet | 模板化生成，Sonnet 性价比高 |
| 冗余对评审（review-agent-1/2） | Opus | 评审遗漏 = 缺陷逃逸到生产 |
| 覆盖度审查 | Opus | 需要全局视野和深度推理 |
| 补充用例生成 | Sonnet | 模板化生成 |

## 可用工具

共享脚本（飞书/GitLab/GitHub）用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。以下为本 skill 特有工具：

### 1. Figma MCP

当用户提供 Figma 链接时使用，按分级协议获取（详见 [shared-tools/SKILL.md](../shared-tools/SKILL.md#figma-设计稿获取)）：

1. `figma_metadata(url)` — 获取页面结构树，识别功能区块和组件层级
2. `figma_context(url, nodeId)` — 对关键交互节点获取设计详情（表单、弹窗、列表等）
3. `figma_extract(url, 交互状态脚本)` — 提取组件属性和变体状态，辅助生成状态类测试用例

### 2. 子 Agent: test-case-writer

通过 Task 工具调用，为单个功能模块生成测试用例。decompose 阶段生成 `context_summary.md` 后，Task prompt 中只需包含模块需求片段和一行 Read 指令指向 `context_summary.md`，子 Agent 自行读取全局上下文。

### 3. 冗余对 Agent: review-agent-1/2

通过 Task 工具并行调用，独立评审生成的用例。Agent 定义见 [agents/test-case-generation/](../../agents/test-case-generation/)。两个 Agent 侧重不同维度（覆盖度 vs 质量），合并结果时应用共识加成。

## 阶段流程

按以下 7 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证预取数据，确认 Story 信息 | — |
| 2. understand | 深入理解需求的业务背景和交互逻辑 | — |
| 3. decompose | 拆解功能模块，提炼全局上下文 | `decomposition.md`、`context_summary.md` |
| 4. generate | 通过子 Agent 并行生成各模块用例 | `module_{N}_cases.json`（中间文件） |
| 5. review | 自审 + 冗余对评审，4 维度质量检查 | `test_cases.json`、`tc_gen_review.md` |
| 6. confirm | 不确定的评审问题抛给用户确认 | 用户确认记录 |
| 7. output | 合并最终用例集、生成评审摘要 | `final_cases.json`、`review_summary.json` |

## 用例文件格式（`final_cases.json`）

JSON 字段定义见 [CONVENTIONS.md](../../CONVENTIONS.md#用例-json-格式)。顶层为数组，每条用例通过 `module` 字段标识归属模块。补充要求：

- `test_method` 取值：等价类划分 / 边界值分析 / 场景法 / 错误推测法 / 判定表法 / 状态迁移法
- `module` 填写模块名称（不带编号前缀）
- `title` 为纯业务描述，禁止包含内部编号、优先级前缀或测试方法/分类前缀（如「P1 等价类-有效类：」）
- `review_confidence`：评审置信度（0-100），review 阶段冗余对评审后生成
- `source`：用例来源 — `generated`（生成阶段产出）/ `supplementary`（评审补充）

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `requirement_doc.md` | 预下载/fetch | 需求文档完整内容 |
| `context_summary.md` | decompose | 全局上下文摘要 |
| `decomposition.md` | decompose | 功能模块拆解清单 |
| `module_{N}_cases.json` | generate | 各模块用例（子 Agent 产出，review 后合并到 `test_cases.json`） |
| `test_cases.json` | review | review 前的中间版本用例集（合并 module 文件后、评审前） |
| `tc_gen_review.md` | review | 4 维度冗余对评审结果 |
| `supplementary_cases.json` | output | 补充用例（如有） |

## 与其他 skill 的关系

- **test-case-review**：如需对已有用例做独立深度评审（而非在生成流程中内置评审），使用 `test-case-review`。本 skill 的 `final_cases.json` 可作为 test-case-review 的输入
- **change-analysis**：本 skill 专注需求驱动的用例生成；如需分析代码变更的测试覆盖缺口并生成补充用例，使用 `change-analysis`

## Closing Checklist（CRITICAL）

skill 执行的最终阶段（output）完成后，**必须**逐一验证以下产出文件：

- [ ] `final_cases.json` — 非空，格式符合入库要求，包含所有已确认用例
- [ ] `review_result.md` — 非空，包含冗余对评审结果
- [ ] `review_summary.json` — 非空，包含评审统计
- [ ] `decomposition.md` — 非空，包含功能模块拆解清单
- [ ] `context_summary.md` — 可选，仅模块 >= 3 个时生成

全部必须项通过后，输出完成总结。如任一必须文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- `final_cases.json` 格式必须严格遵守，后端会自动入库
- review 阶段先在 `module_{N}_cases.json` 中做去重/补充，合并为 `test_cases.json`，然后启动冗余对评审
- 模块 < 3 个时不拆分子 Agent，直接在主 Agent 中生成；模块 >= 3 个时使用子 Agent 并行生成
- 子 Agent（test-case-writer）为 pipeline 编排层功能，独立使用本 skill 时子 Agent 不可用，所有模块均在主 Agent 中直接生成
- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
