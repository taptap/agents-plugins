---
name: requirement-review
description: >
  在需求评审会前，对需求文档做质量把关。输入飞书 Story 链接或需求文档链接，
  输出 Go-No-Go 评审结论、结构化 Checklist 和各职能待确认问题清单。
  适用于拿到新需求时做系统性评审，而非代码变更分析或已有测试用例评审。
  本 skill 只读评审产出报告，不与用户做交互式问答拉齐理解（交互式澄清请使用 requirement-clarification）。
  已有代码变更的影响面分析请使用 change-analysis；已有测试用例的评审请使用 test-case-review。
  触发：需求评审、Review、Checklist、需求质量、需求风险、Go/No-Go、评审会。
---

# 需求评审工作流

## Quick Start

- Skill 类型：独立 skill
- 适用场景：对需求文档做质量评审，识别逻辑缺口、边界风险、协作前置条件与跨职能待确认问题
- 必要输入：飞书 Story 链接或需求文档链接；如有设计稿、关联文档、相关代码信息可一并读取
- 输出产物：`requirement_understanding.md`、`review_checklist.md`、`report.md`
- 失败门控：需求正文不可用时暂停评审并提示补充；未在文档中出现的信息必须标记为"待确认"
- 执行步骤：`init → fetch → understand → review → output`

## 意图识别

根据用户输入确定执行路径：

| 输入 | 动作 |
|------|------|
| 飞书 Story 链接（`/story/detail/`） | → 从 Story 提取需求文档链接，走完整 5 阶段流程 |
| 飞书文档链接（`/wiki/` 或 `/docx/`） | → 直接作为需求文档，跳过 Story 元信息获取 |
| 系统预取的 Story 信息（prompt 注入） | → 确认预取数据后进入 fetch 阶段 |
| 无参数（如"帮我做需求评审"） | → 询问用户提供 Story 链接或需求文档链接 |
| 模糊输入 | → 询问澄清：是需求评审（本 skill）、变更分析（change-analysis）还是用例评审（test-case-review） |
| 已有代码变更需要分析 | → 引导到 `change-analysis` |
| 已有测试用例需要评审 | → 引导到 `test-case-review` |

## 评审原则

1. **以需求文档为核心** — 所有评审结论必须基于需求文档内容，而非猜测
2. **12 维度系统性评审** — 对每个功能点按 12 个维度逐项检查，确保覆盖全面
3. **可操作性** — 输出的问题必须具体、可回答，而非模糊的"需要注意"
4. **按职能分组** — 问题按 PM/Dev/QA/Design 分组，每个人只需关注自己的部分
5. **优先级区分** — 区分"阻断项"（评审前必须确认）和"关注项"（后续跟进即可）
6. **防幻觉原则** — 未在需求文档中提及的内容标注为"待确认"，不假设答案
7. **设计稿交叉验证** — 当有设计稿时，交叉比对文档与设计稿的差异

## 评审维度

12 维度评审框架覆盖需求质量的各个方面：

| 维度 | 关注点 | 主分配 |
| --- | --- | --- |
| 功能边界 | 范围内/外、与现有功能交互 | PM |
| 状态流转 | 实体生命周期、状态变化规则 | PM |
| 性能要求 | 响应时间、数据量级、并发 | Dev |
| 权限控制 | 角色权限、数据可见性 | Dev |
| 异常处理 | 错误路径、降级策略、重试 | Dev |
| 数据约束 | 字段规则、格式要求、唯一性 | Dev |
| 依赖关系 | 上下游系统、多端一致性、埋点 | Dev |
| 交互与 UI 规则 | 操作流、表单交互、加载/空态 | Design |
| 安全与合规 | 加密、脱敏、审计、防刷 | Dev |
| 兼容性 | 浏览器/OS 版本、降级策略 | Dev |
| 可测试性与验收标准 | 验收标准、测试数据、Mock | QA |
| 影响范围 | 变更涉及模块、数据迁移 | PM |

详细检查项见 [CHECKLIST.md](CHECKLIST.md)。

## 多视角并行分析（复杂需求自动启用）

当功能点 >= 5 个且需求文档 > 2000 字时，review 阶段自动启用多视角并行分析：

- **functional-perspective**（Opus）：功能边界 + 状态流转 + 数据约束 + 依赖关系 + 影响范围
- **exception-perspective**（Opus）：异常处理 + 兼容性 + 安全与合规 + 性能要求
- **user-perspective**（Sonnet）：交互与 UI 规则 + 权限控制 + 可测试性与验收标准

三个视角独立分析后交叉验证，被 2+ 个 Agent 确认的发现优先级提升。不满足条件时退回单 Agent 串行评审。

详见 [PHASES.md](PHASES.md) 阶段 4.0/4.1a。

## 文档-设计稿交叉比对（条件触发）

当 fetch 阶段获取到设计稿时，review 阶段自动执行文档与设计稿的交叉比对：

1. **功能覆盖比对** — 文档功能点 vs 设计稿页面，识别双向差集
2. **交互行为比对** — 设计稿交互细节 vs 文档状态规则，识别信息缺口
3. **数据字段比对** — 设计稿表单字段 vs 文档数据约束，识别约束缺失

差异发现按职能分配到第 4 章的对应分组。详见 [PHASES.md](PHASES.md) 阶段 4.1.5。

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 需求文档解析和评审 | Opus | 需求理解是整个 pipeline 质量天花板 |
| 多视角分析 Agent（功能/异常） | Opus | 遗漏隐含需求的代价极高 |
| 多视角分析 Agent（用户） | Sonnet | 用户体验分析风险较低 |

## 可用工具

共享脚本（飞书/GitLab/GitHub）用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。以下为本 skill 特有工具：

### 1. 飞书文档导出

本 workflow 导出时使用 `--wiki-parent` 参数（具体 token 由 workflow prompt 注入），文档名格式：`{需求名称}-需求评审-{YYYYMMDDHH}`。

### 2. GitLab 辅助脚本（查看现有代码，条件触发）

当需求文档中提到具体模块/功能时，可通过 GitLab 脚本查看现有代码实现：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py file-content <project_path> <file_path> [--ref master]
```

环境变量 `GITLAB_URL` 和 `GITLAB_TOKEN` 已在运行环境中预配置。

### 3. Figma MCP（条件触发）

当用户提供设计稿链接或 Story 中包含设计稿链接时，按分级协议获取，详见 [shared-tools/SKILL.md](../shared-tools/SKILL.md#figma-设计稿获取)。

## 各阶段详细操作

详见 [PHASES.md](PHASES.md)

## 输出策略

### Chat 输出

- 每个阶段**开始**时，输出一行进度提示
- **fetch 阶段**：每获取到一类数据，在 chat 中输出该数据的关键摘要，让用户确认。关键数据缺失时输出明确的阻断提示并等待用户补充
- **understand 阶段**：输出功能点清单摘要和需求分类结果，让用户确认理解是否准确
- **review 阶段**：输出关键发现摘要和检查进度；阻断项使用结构化问答确认
- **output 阶段**：输出飞书文档链接
- **不要**在 chat 中输出完整的评审报告详情（详细内容输出到飞书文档）

### 中间文件输出（持久化模式）

分析过程中必须将关键中间结果写入工作目录的文件，供后续阶段引用：

| 文件名 | 写入阶段 | 内容 |
| --- | --- | --- |
| `requirement_doc.md` | 预下载/fetch 阶段 | 需求主文档完整内容（系统预下载或手动获取） |
| `requirement_doc_sub_*.md` | 预下载/fetch 阶段 | wiki 子文档内容（系统自动获取，按层序编号，上限 10 篇） |
| `requirement_understanding.md` | understand 阶段 | 需求理解结构化文档（目标、功能点、业务规则、依赖等） |
| `review_checklist.md` | review 阶段 | 12 维度评审清单（含每项的状态标记和发现的问题） |
| `report.md` | output 阶段 | 精简评审报告（导出到飞书文档） |

**重要**：后续阶段需要引用之前阶段的数据时，**必须通过 Read 工具回读中间文件**，不要依赖对话上下文中的记忆。

### 飞书文档输出

飞书文档导出的具体命令和报告内容约束详见 [PHASES.md](PHASES.md) 阶段 5 和 [TEMPLATES.md](TEMPLATES.md)。

## 注意事项

- 飞书工具选择和禁用项见 [shared-tools/SKILL.md](../shared-tools/SKILL.md) 的「工具选择快速参考」和「禁用工具」
- **每个阶段结束时必须输出进度统计**
- 回读中间文件等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 阻断项确认通过调用 AskUserQuestion 工具完成，见 [CONVENTIONS.md](../../CONVENTIONS.md#askuserquestion-交互式提问) 和 [PHASES.md](PHASES.md) 阶段 4.4

## 约束规则

- **只读评审** — 本 workflow 只产出评审报告，不修改需求文档、不创建任务、不操作代码
- **数据门控** — 需求正文不可用时暂停评审并提示补充；关联文档、设计稿、代码为非阻断
- **防幻觉** — 未在需求文档中出现的信息必须标记为"待确认"，禁止假设答案
- **可操作性** — 输出的问题必须具体、可回答，禁止模糊的"需要注意"
- **按职能分组** — 问题按 PM/Dev/QA/Design 分组，使用统一的优先级定义（阻断/高/中/低）
- **阻断项比例** — 阻断项通常不超过总问题数的 20%；若超过须在评审结论中说明
- **飞书工具约束** — 禁止使用 WebFetch 获取飞书文档或 Figma 设计稿，见 [shared-tools 通用约定](../shared-tools/SKILL.md#禁用工具)
- **中间文件回读** — 后续阶段引用前序数据必须通过 Read 工具回读文件，不依赖上下文记忆
- **语言** — Chat 输出和报告使用中文；技术术语、文件路径保持原样
