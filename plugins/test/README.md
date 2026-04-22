# Test Plugin

> QA 工作流插件，覆盖需求澄清 → 测试用例生成 / 评审 → 变更分析 → 需求回溯 → Bug 修复分析的完整 QA 流程

## 简介

`test` 插件为 Claude Code 提供一套完整的 QA 工作流 Skill，支持功能测试、单元测试、集成测试的设计与生成。支持手工测试（单独调用各 skill）和 AI coding（工作流编排）两种场景。

### 核心 Skills

| Skill | 类型 | 功能 |
|-------|------|------|
| **requirement-clarification** | 核心工作流 | 多维度结构化问答（含影响范围分析），拉齐需求理解 |
| **test-case-generation** | 核心工作流 | 基于需求拆解功能模块、生成测试用例、冗余对评审（4 维度）、用户确认 |
| **test-case-review** | 独立 skill | 评审已有测试用例的覆盖度和质量，生成补充用例 |
| **change-analysis** | 核心工作流 | 分析代码变更影响面和测试覆盖（Story/Bug 双场景） |
| **requirement-traceability** | 仅 CLI/手工调用 | 双通道追溯（正向用例中介验证 + 反向代码追溯 + UI 还原度），消费上游 final_cases.json |
| **test-failure-analyzer** | 仅 CLI/手工调用 | 分析测试失败原因，分类处理，支持自循环 |
| **ui-fidelity-check** | 仅 CLI/手工调用 | 对比 Figma 设计稿与浏览器实现的 UI 还原度 |
| **api-contract-validation** | 独立校验工具 | 深度校验前后端 API 契约一致性（路径/参数/响应/Breaking Change） |
| **unit-test-design** | 代码级生成 | 分析源代码，生成可执行的单元测试代码 |
| **integration-test-design** | 代码级生成 | 分析 API/服务，生成可执行的集成测试代码 |

### 编排 Skills

| Skill | 类型 | 功能 |
|-------|------|------|
| **qa-workflow** | 工作流编排 | 端到端 QA 编排器：自动串联需求澄清→用例生成→MS同步→变更分析→需求还原度→代码审查，支持条件分支和并行执行 |

### 集成同步 Skills

| Skill | 类型 | 功能 |
|-------|------|------|
| **metersphere-sync** | 集成同步 | 将 AI 生成的测试用例导入 MeterSphere，创建测试计划，可选基于验证置信度自动标记执行结果 |

### 支持 Skills

| Skill | 功能 |
|-------|------|
| **shared-tools** | 共享脚本集合（飞书文档获取、GitLab/GitHub MR/PR 分析、MeterSphere 用例同步） |

## 需求类 Skill 选用指引

| 场景 | 推荐 Skill | 说明 |
|---|---|---|
| 拿到新需求，通过问答拉齐理解 | requirement-clarification | 交互式，产出 JSON 供下游消费 |
| 需求文档已写好，评审会前质量把关 | requirement-review | 评估式，产出报告供评审会使用 |
| 已有测试用例，评审覆盖度和质量 | test-case-review | 对照需求 4 维度评审 |
| 代码变更已提交，分析影响和覆盖 | change-analysis | Story/Bug 双场景 |
| 需求实现后验证代码是否正确 | requirement-traceability | 双通道追溯（正向通道内嵌用例中介验证，消费上游 final_cases.json） |
| 为已有代码写单元测试 | unit-test-design | 分析代码逻辑，生成测试文件 |
| 为 API/服务写集成测试 | integration-test-design | 分析接口定义，生成集成测试 |
| 测试失败了，分析原因 | test-failure-analyzer | 分类（预期/回归/不稳定）+ 行动方案 |
| 跑完整 QA 流程 | qa-workflow | 端到端编排，自动串联各 skill |
| 处理 Slack 用户反馈 | feedback | 分析反馈 + 判断 Bug + 创建工单 |

## 使用场景

### 场景一：手工测试（单独调用）

每个 skill 独立可用，输入灵活（story 链接 / 本地文档 / 纯文本 / 上游 JSON 均可）。

| 需求 | 调用 skill | 输入 | 输出 |
|------|-----------|------|------|
| 需求澄清 | requirement-clarification | 需求链接/文档 | clarified_requirements.json |
| 用例生成 | test-case-generation | 需求链接/文档 | final_cases.json |
| 用例评审 | test-case-review | 已有测试用例 + 需求文档 | review_result.json + 补充用例 |
| 变更分析 | change-analysis | Story/Bug + MR/PR/diff | change_analysis.json + change_coverage_report.json |
| 需求回溯 | requirement-traceability | 需求 + MR/PR/diff | traceability_matrix.json |
| Bug 修复分析 | change-analysis（Bug 场景） | Bug 链接 + MR/PR/diff | change_fix_analysis.json + risk_assessment.json |
| API 契约校验 | api-contract-validation | 前端 diff + 后端 diff/OpenAPI spec | api_contract_report.json |

### 场景二：AI coding 工作流编排

配合 AI coding 工具链使用，由编排层串联各 skill：

```
需求（Story/文档+设计稿）
    ↓
requirement-clarification（需求澄清）
    ↓ clarified_requirements.json + requirement_points.json
AI Coding 生成代码变更
    ↓ code_changes
change-analysis（变更影响分析）
    ↓ change_coverage_report.json
test-case-generation（用例生成）
    ↓ final_cases.json
test-case-review（用例评审）
    ↓ review_result.json + supplementary_cases.json
requirement-traceability（需求回溯验证）
    ↓ traceability_matrix.json
```

## 快速开始

本插件支持 8 条独立工作链路，可独立执行也可组合使用：

### 链路 A — 功能测试全流程（串行）

需求驱动的黑盒测试设计，从需求到用例到覆盖验证。

```
需求文档/链接
    ↓
requirement-clarification（需求澄清 + 影响范围分析）
    ↓ clarified_requirements.json + requirement_points.json
test-case-generation（测试用例生成 + 冗余对评审 + 用户确认）
    ↓ final_cases.json（本 skill 最终产物，requirement-traceability 不消费此文件）
    + 用户提供 MR/PR 链接或 diff（手动输入，作为 requirement-traceability 的代码变更输入）
requirement-traceability（需求回溯 — 双通道）
    ↓ traceability_matrix.json + traceability_coverage_report.json + forward_verification.json
```

### 链路 B — 代码级测试生成（可并行）

实现驱动的白盒测试代码生成，直接分析源码/API 定义。

```
源代码文件 ──→ unit-test-design ──→ *_test.go / test_*.py
API 定义   ──→ integration-test-design ──→ 集成测试代码
```

> 链路 B 可接收链路 A 的 `requirement_points.json` 作为可选输入，用于指导测试覆盖重点（优先为 P0/P1 功能点对应的代码模块生成测试）。

### 链路 C — Bug 修复分析（已合并到链路 F）

> 已合并到链路 F 的 Bug 场景。使用 `change-analysis` 并提供 `bug_link` 参数即可。

```
Bug 信息 + MR/PR/本地 diff ──→ change-analysis（Bug 场景）──→ change_fix_analysis.json + risk_assessment.json
```

### 链路 D — 需求回溯增强（配合链路 A）

requirement-traceability 内嵌正向用例中介验证，AI 逐条拿上游用例对照代码推理；可叠加 UI 还原度检查。

```
final_cases.json (链路 A) + 代码实现
    ↓
ui-fidelity-check（UI 还原度检查，有设计稿时）
    ↓ ui_fidelity_report.json
requirement-traceability（双通道回溯，正向通道内嵌用例中介验证）
    ↓ forward_verification.json + traceability_coverage_report.json（含正向验证率 + UI 还原度）
```

### 链路 E — 测试失败自循环（配合链路 B）

测试执行后有失败用例时，自动分析原因并循环修复。

```
测试执行结果（有失败）+ 代码变更 diff
    ↓
test-failure-analyzer（失败分类 + 方案生成）
    ↓ failure_analysis.json + action_plan.md
    ↓ 用户确认 → 执行修复 → 重新测试（最多 3 轮）
```

> 注意：链路 E 的输入 `test_execution_report.json` 仅在环境支持执行测试时生成。若仅做代码级测试生成（链路 B）而未实际执行测试，则无法触发链路 E。

### 链路 F — 变更分析（Story/Bug 双场景）

分析代码变更的影响面、测试覆盖缺口，生成补充用例。Bug 场景含完整根因分析和风险评估（原链路 C 已合并至此）。

```
Story 场景:
Story + MR/PR 或本地 diff
    ↓
change-analysis（变更影响分析 + 覆盖评估）
    ↓ change_analysis.json + change_coverage_report.json + supplementary_cases.json

Bug 场景:
Bug + MR/PR 或本地 diff
    ↓
change-analysis（根因分析 + 修复完整性评估 + 风险评估）
    ↓ change_analysis.json + change_fix_analysis.json + risk_assessment.json
```

### 链路 G — 用例评审（独立触发）

对已有测试用例做深度评审，识别缺口并补充。

```
已有测试用例 + 需求文档
    ↓
test-case-review（4 维度评审 + 补充用例）
    ↓ review_result.json + supplementary_cases.json
```

### 链路 H — API 契约校验（独立触发）

校验前后端 API 接口定义的一致性，识别 Breaking Change。

```
前端代码变更 + 后端代码变更（或 OpenAPI spec）
    ↓
api-contract-validation（接口签名提取 + 交叉比对）
    ↓ api_contract_report.json
```

## 支持的语言

| 语言 | 单元测试 | 集成测试 | 测试框架 |
|------|---------|---------|---------|
| Go | ✅ | ✅ | testing + testify |
| Python | ✅ | ✅ | pytest |
| TypeScript | ✅ | ✅ | vitest / jest |
| Java | ✅ | ✅ | JUnit 5 + Mockito |
| Kotlin | ✅ | ✅ | JUnit 5 + MockK |
| Swift | ✅ | — | XCTest |

## Skill 命名规则

| 后缀 | 含义 | 示例 |
|---|---|---|
| `-generation` / `-design` | 产出新 artifact（用例、测试代码） | test-case-generation, unit-test-design |
| `-review` / `-analysis` | 评估已有 artifact | test-case-review, change-analysis |
| `-check` / `-validation` | 校验合规性 | ui-fidelity-check, api-contract-validation |
| `-clarification` / `-traceability` | 建立映射或填补空白 | requirement-clarification, requirement-traceability |

## 架构特性

本插件借鉴 quality/review 插件的多 Agent 设计模式，持续引入以下架构能力：

### 多视角并行分析
复杂需求时启动功能/异常/用户 3 个视角 Agent 并行分析，交叉验证提升置信度。适用于 requirement-clarification 和 test-case-generation。

### 冗余对评审
test-case-generation（review 阶段）和 requirement-traceability 使用冗余对模式 — 2 个独立 Agent 并行分析同一内容，共识发现自动加成置信度 +20。不确定的评审问题抛给用户确认，避免评审幻觉。

### 双通道追溯（v0.0.10+）
requirement-traceability 正向用「用例中介验证」（需求→验证用例→AI 逐条对照代码），反向用「直接代码追溯」（代码→需求），两者互补。

### 影响范围分析（v0.0.10+）
requirement-clarification 新增影响范围维度 — 基于 `module-relations.json` 模块关系索引分析变更波及范围，避免全库代码扫描的噪声和遗漏。

### UI 还原度检查（v0.0.10+）
Figma MCP 获取设计数据/截图 + Browser MCP 获取实现截图/DOM，AI 对比 6 个维度（布局/间距/颜色/字体/状态/交互）的还原差异。

### 自循环机制（v0.0.10+）
test-failure-analyzer 支持 分析→修复→重测 自循环（最多 3 轮），AI 自动分类失败原因（预期变化/回归/不稳定）并推荐处理方案。

### 量化置信度评分
全 Pipeline 引入 0-100 连续置信度评分，替代原有的文本标签。置信度从 requirement-clarification 流转至 requirement-traceability，每个阶段叠加评分。

### 模型分层策略
按「错误代价」分配模型 — Opus 用于需求理解/覆盖审查/根因分析/代码路径追踪（漏检代价高），Sonnet 用于用例生成/报告输出（模板化工作）。

## 目录结构

```
plugins/test/
├── .claude-plugin/
│   └── plugin.json
├── CONVENTIONS.md              # 统一约定（含置信度、Agent 规范、双通道、自循环）
├── CONTRACT_SPEC.md            # contract.yaml 编写规范
├── agents/                     # Agent 定义文件（单一事实源）
│   ├── AGENT_TEMPLATE.md       # 统一模板
│   ├── test-case-writer.md     # 测试用例生成 Agent
│   ├── test-case-generation/   # 用例评审冗余对 Agent
│   │   ├── review-agent-1.md   # 覆盖度视角评审 Agent
│   │   └── review-agent-2.md   # 质量视角评审 Agent
│   ├── failure-classifier.md   # 测试失败分类 Agent (预留)
│   ├── ui-fidelity-checker.md  # UI 还原度检查 Agent
│   ├── requirement-understanding/  # 需求理解多视角 Agent
│   └── requirement-traceability/   # 需求追溯冗余对
├── skills/
│   ├── _shared/                    # 共享协议和框架文件
│   ├── shared-tools/               # 共享脚本
│   ├── requirement-clarification/  # 需求澄清（含影响范围分析）
│   ├── requirement-review/         # 需求评审（12 维度）
│   ├── test-case-generation/       # 测试用例生成（含冗余对评审）
│   ├── test-case-review/           # 用例评审（独立深度评审）
│   ├── change-analysis/            # 变更分析（Story/Bug 双场景）
│   ├── requirement-traceability/   # 需求回溯（双通道 + 内嵌用例中介验证 + UI 还原度）
│   ├── test-failure-analyzer/      # 测试失败分析（自循环）
│   ├── ui-fidelity-check/          # UI 还原度检查
│   ├── unit-test-design/           # 单元测试代码生成
│   ├── integration-test-design/    # 集成测试代码生成
│   ├── api-contract-validation/    # API 契约校验
│   ├── metersphere-sync/          # MeterSphere 用例同步与测试计划管理
│   └── qa-workflow/               # QA 工作流编排器
├── PIPELINES.md                    # 链路数据流规格
└── README.md
```

## 环境变量

shared-tools 脚本依赖以下环境变量（按需配置）：

| 变量 | 说明 | 依赖脚本 |
|------|------|---------|
| `FEISHU_APP_ID` | 飞书应用 ID | fetch_feishu_doc.py |
| `FEISHU_APP_SECRET` | 飞书应用 Secret | fetch_feishu_doc.py |
| `GITLAB_URL` | GitLab 实例地址 | gitlab_helper.py, search_mrs.py |
| `GITLAB_TOKEN` | GitLab Access Token | gitlab_helper.py, search_mrs.py |
| `GITHUB_TOKEN` | GitHub Token | github_helper.py, search_prs.py |
| `MS_BASE_URL` | MeterSphere 地址（有默认值） | metersphere_helper.py |
| `MS_ACCESS_KEY` | MeterSphere API Key（有默认值） | metersphere_helper.py |
| `MS_SECRET_KEY` | MeterSphere Secret Key（有默认值） | metersphere_helper.py |
| `MS_PROJECT_ID` | MeterSphere 项目 ID（有默认值） | metersphere_helper.py |

## 版本历史

- **v0.0.7** - 新增 `mcp__cases__save_test_cases` in-process MCP tool 替代 Write 写 `*_cases.json`，schema 在 Anthropic API 生成阶段强约束（input_schema 由后端 Pydantic `case_schema.TestCase` 通过 `TypeAdapter` 生成），字段拼写漂移和结构错误在 tool input 层即被拒绝，落盘前再走 `validate_cases` 二次校验；hook 仅做 Write→tool 引导；change-analysis / test-case-generation / test-case-review 三个 skill 的 PHASES.md 改用新 tool；test-case-writer 子 agent 同步移除 Write、加 MCP tool；CONVENTIONS.md「严格校验」段重写体现新分层防御；test-case-generation/PHASES.md 弱化"post_complete 兜底"叙述；`_shared/LARGE_FILE_HANDLING.md` 标注 MCP tool input 同样受 LLM token 限制；requirement-review 支持需求文档缺失时降级评审
- **v0.0.6** - 补全 Codex `interface` 段（displayName/category/capabilities），让插件能在 Codex 0.121.0 TUI picker 中正常展示
- **v0.0.5** - requirement-traceability 新增 Phase 6 writeback 阶段自动回写 MS 测试计划（标准模式独立调用即完成回写，冒烟模式仍跳过）；requirement-clarification 新增 handoff 元数据 + Next Steps 输出规范（spec-kit 风格样板，待验证后推广）；qa-workflow 删除冗余 metersphere-sync execute 步骤、qa-full 编号重排为 #9/#10/#11、修复 PHASES.md 跨引用与早期编号不一致；合并 verification-test-generation 至 requirement-traceability 正向通道（消费 final_cases.json，按 case_id 粒度回写 MS）；新增跨仓库契约桥（`contract-bridge-check.py`）+ 5 个 JSON schema（testcase/defect-list/smoke-test-report/rr-summary/ca-summary）；新增 `codex_agent.py` 独立 Codex 代理 + change-analysis Phase 3.5 cross-validation agent；契约驱动的 RR/CA 结构化摘要输出供 ai-case 消费；MS 导入 tag 字段后端统一（`--tags` CLI）；修复 codex_agent 路径校验 sibling-prefix 漏洞和 OpenAI timeout 边界；feedback skill 拆分为多文件架构；测试质量规则共享化（`_shared/`）；新增探索性测试法；统一用例 JSON 格式契约；修复启动器负责人矛盾和 headers 缩进 bug；删除废弃 bug-fix-review；补充 Closing Checklist 和触发词负向界定
- **v0.0.3** - 新增 `qa-workflow` 编排器和 `metersphere-sync` skill；新增 feedback skill（Slack 反馈分析 + 飞书 Bug 创建）；change-analysis 新增 Urhox 二进制影响分析；统一 .env 配置；`ask_question` 迁移至原生 AskUserQuestion 工具调用
- **v0.0.2** - 新增 `.codex-plugin/` manifest，支持 Codex CLI 兼容
- **v0.0.1** - 首次发布；完整 QA 工作流插件，包含需求澄清、测试用例生成（含冗余对评审）、用例评审、变更分析、需求回溯（含冒烟测试模式）、代码级测试生成（单元/集成）、API 契约校验、UI 还原度检查等全流程 Skill；共享工具集（飞书文档获取、MR/PR 分析脚本）；阶段执行保障和输出验证机制

### v0.0.19

- Migrate `ask_question` text-based output format to native AskUserQuestion tool calls; align constraints with tool schema (1-4 questions, 2-4 options, required description, header <=12 chars)
- Update all skill references: requirement-clarification, requirement-review, test-case-generation, and shared TRACEABILITY_PROTOCOL

### v0.0.18

- New skill: `change-analysis` — analyze code change impact and test coverage for Story/Bug scenarios (dual-scenario: Story 7-phase impact analysis + coverage assessment + supplementary case generation; Bug 5-phase root cause + fix completeness + risk assessment)
- New skill: `test-case-review` — independent 4-dimension review of existing test cases (coverage, completeness, correctness, quality) with supplementary case generation
- New skill: `api-contract-validation` — deep validation of frontend-backend API contract consistency (path/param/response/breaking change detection)
- Add cross-references between related skills (test-case-generation ↔ test-case-review, requirement-traceability ↔ change-analysis)
- Add "使用场景" section to README with manual testing and AI coding workflow mapping
- Add Link F (change-analysis), Link G (test-case-review), and Link H (api-contract-validation) to quick start guide
- Update core skills table to include new skills
- Extend CONTRACT_SPEC.md with `any_of` input category (at least one, can provide multiple)
- Add `implementation_brief.json` output to requirement-clarification (platform-split tasks with API contracts and dependency graph)
- Add `platform_scope` and `coordination_needed` to requirement-clarification output
- Add design-draft clarification mode and document+design joint mode to requirement-clarification
- Enhance CHECKLIST.md with API contract dimension and impact scope dimension
- Add `story_link` shortcut input to verification-test-generation

### v0.0.17

- Upgrade `fetch_feishu_doc.py` with wiki children traversal (`--with-children` / `--max-children`), recursive block rendering, and table/sheet/board content extraction
- Add smoke-test mode to `requirement-traceability` with defect extraction and P0 gate
- Define `ask_question` structured output format in CONVENTIONS.md for interactive Q&A cards; update requirement-clarification and test-case-generation PHASES.md
- Fix `.gitignore` excluding `agents/test-case-generation/` review agent definitions

### v0.0.16

- Fix 25 review findings (R-001 to R-025) + 4 AI execution risks from dual-agent QA workflow review
- R-001: Create review-agent-1.md and review-agent-2.md for test-case-generation redundant pair review
- R-002/R-023: Delete deprecated skills/test-review/ and skills/test-design/ directories
- R-003: Unify ui_fidelity_report.json field names (category, UI-DIFF-N, design_url) across SKILL.md, PHASES.md, and TEMPLATES.md
- R-004: Fix verification-test-writer.md output to flat JSON array (remove {agent, findings} wrapper)
- R-005: Add traceability assessment (call depth, dynamic dispatch) before code path tracing in verification-test-generation and requirement-traceability
- R-006: Replace semantic ID matching with direct FP- inheritance in requirement-traceability
- R-007: Correct reverse-tracer execution timing description
- R-008: Add ui_fidelity_report as optional input in requirement-traceability contract
- R-009/R-014: Extend CONTRACT_SPEC.md with mcp_servers/tools dependencies and from_upstream array syntax
- R-011: Raise consensus confidence threshold from 60 to 70
- R-012: Upgrade convergence check to set comparison (detect new regressions even when total count decreases)
- R-013: Clarify data flow in README Link A (test-case-generation → requirement-traceability is not automatic)
- R-016: Change degradation mode confidence from 0 to null with clear semantics
- R-017: Unify incremental rerun verification method in requirement-traceability
- R-018: Add test_command discovery mechanism in test-failure-analyzer
- R-019: Normalize R- prefix format in CONVENTIONS.md
- R-020: Mark failure-classifier as reserved
- R-021: Add token estimation rules for large document segmentation
- R-022: Add confidence cap (60) for structural-only mode in ui-fidelity-check
- R-024: Add Python availability pre-check and ImportError/ModuleNotFoundError as deterministic failures
- R-025: Optimize user confirmation UX with batch accept/reject options
- Risk 1: Add adversarial verification (counter-evidence check) for pass conclusions
- Risk 2: Require target_id in multi-perspective agent findings for structured matching
- Risk 3: Implement two-step deduplication (literal grep + AI semantic comparison)
- Risk 4: Cap indirect association confidence at 75 in test-failure-analyzer

### v0.0.13

- 合并 `test-case-generation`（原 `test-design`）与 `test-review` 为单一 skill — 生成后立即进行冗余对评审，不确定问题抛给用户确认
- 新增 `agents/test-case-generation/review-agent-1.md` 和 `review-agent-2.md` — 分别侧重覆盖度和质量的评审 Agent
- test-case-generation 阶段从 5 个扩展为 7 个：新增 review（冗余对评审）、confirm（用户确认）、output（最终输出）
- 输出文件从 `test_cases.json` 变为 `final_cases.json`（含 `review_confidence` 和 `source` 字段）
- 链路 A 简化为 3 个节点：requirement-clarification → test-case-generation → requirement-traceability
- 删除独立的 `test-review` skill 和目录

### v0.0.11

- 新增 `verification-test-generation` skill — 从需求功能点生成结构化验证用例（具体输入→预期输出），AI 逐条对照代码推理验证
- 新增 `test-failure-analyzer` skill — 分析测试失败原因，分类为预期变化/回归/不稳定，支持 分析→修复→重测 自循环（最多 3 轮）
- 新增 `ui-fidelity-check` skill — 对比 Figma 设计稿与浏览器实现的 UI 还原度（6 维度对比）
- 新增 3 个 Agent 定义：`verification-test-writer`、`failure-classifier`、`ui-fidelity-checker`
- `requirement-clarification` 新增第 12 维度「影响范围」— 基于 `module-relations.json` 模块关系索引分析变更波及范围
- `requirement-traceability` 升级为双通道模式 — 正向「用例中介验证」+ 反向「直接代码追溯」+ 条件触发 UI 还原度检查
- CONVENTIONS.md 新增 6 个章节（双通道追溯、影响范围分析、自循环协议、UI 还原度、验证用例格式、module-relations.json 格式）
- 新增链路 D（需求回溯增强）和链路 E（测试失败自循环），共 5 条工作链路

### v0.0.7

- 新增 `agents/` 目录，包含 8 个 Agent 定义文件（统一模板化）
- 引入多视角并行分析（功能/异常/用户 3 个视角 Agent）用于需求理解
- test-review 引入冗余对评审模式（2 个独立 Agent 并行评审）
- requirement-traceability 引入冗余对追溯模式（正向 + 反向 Agent 并行）
- 全 Pipeline 引入 0-100 量化置信度评分，替代文本标签
- 所有 skill 新增模型分层说明（Opus/Sonnet/Haiku 按错误代价分配）
- CONVENTIONS.md 新增 4 个章节（量化置信度、Agent 规范、模型分层、多 Agent 并行）
- 用例 JSON 格式新增 `confidence`、`review_confidence`、`source` 可选字段
- test-case-generation 新增简单需求快速路径（<3 功能点跳过 decompose）
- traceability_matrix.json 新增 `confidence`、`trace_direction` 字段

### v0.0.4

- 修复 search_mrs.py / search_prs.py 子串匹配误报（改用词边界正则）
- 修复 fetch_feishu_doc.py `from __future__` 位置（移到 docstring 之后）
- 修复 search_mrs.py 字符串类型项目映射值静默失败（新增类型校验）
- 修复 github_helper.py PR 文件列表未分页（新增 _get_pr_files 分页函数）
- 修复 Markdown 图片引用与 sanitized 文件名不一致
- 补充 contract.yaml 缺失的映射环境变量声明
- 统一 SKILL.md 项目映射文档为 int ID 格式

### v0.0.3

- 修复 .gitignore 排除 test-case-generation / test-review 目录的阻塞问题
- 移除 Python 脚本中硬编码的内部 GitLab URL 和项目 ID
- 统一 Python 脚本类型注解为 typing 模块格式（兼容 Python 3.8+）
- 修复 fetch_feishu_doc.py image token 路径穿越风险
- 修复 fetch_feishu_doc.py tenant token 缓存无过期问题
- search_prs.py 新增分页支持、未配置时报错退出
- 添加 Python 脚本执行权限

### v0.0.2

- unit-test-design / integration-test-design 新增「测试质量防线」章节
- 防硬编码过测、断言质量要求、防 Mock 滥用、变异测试思维
- 新增 Property-Based Testing 方法论（Go rapid / Python hypothesis / TS fast-check）
- 新增弱断言 vs 强断言对比示例

### v0.0.1

- 从 skills-hub 迁移 6 个 QA 工作流 Skill + shared-tools
- 新增 unit-test-design（单元测试代码生成）
- 新增 integration-test-design（集成测试代码生成）
