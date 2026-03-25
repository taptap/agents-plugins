---
name: test-design
description: >
  根据需求文档和澄清结果拆解功能模块并生成结构化测试用例。
  输入需求链接、本地需求文档或上游澄清结果，输出 test_cases.json。
---

# 测试设计

## Quick Start

- Skill 类型：核心工作流
- 适用场景：基于需求文档或上游澄清结果，拆解功能模块并生成可入库的结构化测试用例
- 必要输入：需求链接、本地需求文档，或上游 `clarified_requirements.json` + `requirement_points.json`（至少一个）
- 输出产物：`context_summary.md`、`decomposition.md`、`test_cases.json`
- 失败门控：需求正文不可读时停止生成；所有用例必须严格基于需求，不补充未提及功能
- 执行步骤：`init → understand → decompose → generate → review`

## 核心能力

- 需求理解 — 解析需求文档或消费上游澄清结果
- 功能拆解 — 将需求拆解为独立的功能模块，提炼全局上下文摘要
- 并行生成 — 使用 test-case-writer 子 Agent 为每个模块并行生成用例
- 质量审查 — 跨模块去重、覆盖度检查、方法覆盖度验证

## 用例生成原则

1. **忠于原文** — 严格基于需求描述，不臆断未提及的功能
2. **方法驱动** — 根据功能特征选择合适的测试设计方法，每条用例标注所用方法
3. **独立原子** — 每个用例原子化，前置条件描述环境状态，不依赖其他用例
4. **步骤对应** — 每个测试步骤内嵌对应的预期结果，结构化配对，每步一个操作
5. **全面覆盖** — 需求功能点逐一映射，无遗漏

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

## 可用工具

### 1. 飞书文档获取脚本

用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。

### 2. Figma MCP

`get_figma_data(url="<链接>")` — 获取设计稿布局/组件/交互数据。

### 3. 子 Agent: test-case-writer

通过 Task 工具调用，为单个功能模块生成测试用例。decompose 阶段生成 `context_summary.md` 后，Task prompt 中只需包含模块需求片段和一行 Read 指令指向 `context_summary.md`，子 Agent 自行读取全局上下文。

## 阶段流程

按以下 5 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证预取数据，确认 Story 信息 | — |
| 2. understand | 深入理解需求的业务背景和交互逻辑 | — |
| 3. decompose | 拆解功能模块，提炼全局上下文 | `decomposition.md`、`context_summary.md` |
| 4. generate | 通过子 Agent 并行生成各模块用例 | `module_{N}_cases.json`（中间文件） |
| 5. review | 去重、覆盖度检查、合并最终用例集 | `test_cases.json` |

## 用例文件格式（`test_cases.json`）

JSON 字段定义见 [CONVENTIONS.md](../../CONVENTIONS.md#用例-json-格式)。顶层为数组，每条用例通过 `module` 字段标识归属模块。补充要求：

- `test_method` 取值：等价类划分 / 边界值分析 / 场景法 / 错误推测法 / 判定表法 / 状态迁移法
- `module` 填写模块名称（不带编号前缀）
- `title` 为纯业务描述，禁止包含内部编号

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `requirement_doc.md` | 预下载/fetch | 需求文档完整内容 |
| `context_summary.md` | decompose | 全局上下文摘要 |
| `decomposition.md` | decompose | 功能模块拆解清单 |
| `module_{N}_cases.json` | generate | 各模块用例（子 Agent 产出，review 后合并到 `test_cases.json`） |

## 注意事项

- `test_cases.json` 格式必须严格遵守，后端会自动入库
- review 阶段先在 `module_{N}_cases.json` 中做去重/补充，最后合并为 `test_cases.json`
- 模块 < 3 个时不拆分子 Agent，直接在主 Agent 中生成；模块 >= 3 个时使用子 Agent 并行生成
- 子 Agent（test-case-writer）为 pipeline 编排层功能，独立使用本 skill 时子 Agent 不可用，所有模块均在主 Agent 中直接生成
- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
