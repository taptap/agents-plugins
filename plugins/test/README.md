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
| **requirement-traceability** | 独立调用，不被自动编排 | 双通道追溯（正向用例中介验证 + 反向代码追溯）；条件触发 §3.4 UI 还原度静态对比、§3.2.5 API 契约校验（共享 agent） |
| **test-failure-analyzer** | 独立调用，不被自动编排 | 分析测试失败原因，分类处理，支持自循环 |
| **api-contract-validation** | 独立校验工具 | 前后端 API 契约一致性校验（路径/参数/响应/Breaking Change）。底层用 `api-contract-validator` agent，与 traceability §3.2.5 共享同一逻辑 |
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
| 写新用例 / 需求歧义补充用例（**需求驱动**）| test-case-generation | 输入需求/澄清结果，输出 final_cases.json（含可选 supplementary） |
| 已有测试用例，评审覆盖度和质量 | test-case-review | 对照需求 4 维度评审 |
| 代码变更已提交，分析影响和补充用例（**变更驱动**）| change-analysis | Story/Bug 双场景；输出 change_supplementary_cases.json |
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
| Bug 修复分析 | change-analysis（Bug 场景） | Bug 链接 + MR/PR/diff | change_fix_analysis.json + bug_risk_assessment.json |
| API 契约校验 | api-contract-validation | 前端 diff + 后端 diff/OpenAPI spec | api_contract_report.json |

### 场景二：AI coding 工作流编排

完整 SOP（5 阶段、复制即用 prompt 模板、反模式、Troubleshooting）见 [`AI_CODING_BEST_PRACTICES.md`](./AI_CODING_BEST_PRACTICES.md)。

## 快速开始

本插件支持 8 条独立工作链路，可独立执行也可组合使用：

### 链路 A — 功能测试全流程

需求驱动的黑盒测试设计：requirement-clarification → test-case-generation → requirement-traceability。完整 SOP 见 [`AI_CODING_BEST_PRACTICES.md`](./AI_CODING_BEST_PRACTICES.md)。

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
Bug 信息 + MR/PR/本地 diff ──→ change-analysis（Bug 场景）──→ change_fix_analysis.json + bug_risk_assessment.json
```

### 链路 D — 需求回溯增强（配合链路 A）

UI 还原度 / API 契约校验已内嵌到 requirement-traceability，无需独立 skill 触发：

```
final_cases.json (链路 A) + 代码实现 + design_link/code_dir + (可选) backend_changes/openapi_spec
    ↓
requirement-traceability（双通道回溯 + §3.4 调用 ui-fidelity-checker agent + §3.2.5 调用 api-contract-validator agent）
    ↓ forward_verification.json
    ↓ ui_fidelity_report.json（design_link + code_dir 都有时）
    ↓ api_contract_report.json（API 相关变更触发时；如已有上游产出则跳过 agent 启动）
    ↓ traceability_coverage_report.json（含正向验证率 + UI 还原度 + API 契约一致性）
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

> 注意：链路 E 的输入 `unit_test_execution_report.json` / `integration_test_execution_report.json` 仅在环境支持执行测试时生成。若仅做代码级测试生成（链路 B）而未实际执行测试，则无法触发链路 E。

### 链路 F — 变更分析（Story/Bug 双场景）

分析代码变更的影响面、测试覆盖缺口，生成补充用例。Bug 场景含完整根因分析和风险评估（原链路 C 已合并至此）。

```
Story 场景:
Story + MR/PR 或本地 diff
    ↓
change-analysis（变更影响分析 + 覆盖评估）
    ↓ change_analysis.json + change_coverage_report.json + change_supplementary_cases.json

Bug 场景:
Bug + MR/PR 或本地 diff
    ↓
change-analysis（根因分析 + 修复完整性评估 + 风险评估）
    ↓ change_analysis.json + change_fix_analysis.json + bug_risk_assessment.json
```

### 链路 G — 用例评审（独立触发）

对已有测试用例做深度评审，识别缺口并补充。

```
已有测试用例 + 需求文档
    ↓
test-case-review（4 维度评审 + 补充用例）
    ↓ review_result.json + review_supplementary_cases.json
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
| `-check` / `-validation` | 校验合规性 | api-contract-validation |
| `-clarification` / `-traceability` | 建立映射或填补空白 | requirement-clarification, requirement-traceability |

## 架构特性

本插件借鉴 quality/review 插件的多 Agent 设计模式，持续引入以下架构能力：

### 单 Agent 强推理（需求侧）
requirement-clarification 和 requirement-review 采用「假设 → 反例搜索 → 结论」三步强推理 + 强制原文引用，用结构化推理替代多 Agent 并行的视角多样性。对应业界 2025 推荐的 single-agent + structured reasoning 模式。详见各 skill 的 PHASES.md。

### 多视角并行分析（用例侧）
test-case-generation 在 review 阶段使用冗余对模式 — 2 个独立 Agent 并行评审同一内容，共识发现自动加成置信度 +20。适用于产出大量 artifact 后的质量复核场景。

### 冗余对评审
test-case-generation（review 阶段）和 requirement-traceability 使用冗余对模式 — 2 个独立 Agent 并行分析同一内容，共识发现自动加成置信度 +20。不确定的评审问题抛给用户确认，避免评审幻觉。

### 双通道追溯
requirement-traceability 正向用「用例中介验证」（需求→验证用例→AI 逐条对照代码），反向用「直接代码追溯」（代码→需求），两者互补。

### 影响范围分析
requirement-clarification 新增影响范围维度 — 基于 `module-relations.json` 模块关系索引分析变更波及范围，避免全库代码扫描的噪声和遗漏。

### UI 还原度检查
requirement-traceability §3.4 通过 Task 工具启动 `ui-fidelity-checker` Agent（共享单元，无独立 skill 入口），输入 Figma 结构化设计数据 + 前端代码样式定义（CSS/SCSS/Tailwind/SwiftUI/Compose），做 6 维度（布局/间距/颜色/字体/状态/交互）静态对比。**纯静态对比**，不依赖运行时浏览器，跨端可用，confidence 上限 60。

### 自循环机制
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
├── CONVENTIONS.md              # 统一约定（含置信度、Agent 规范、双通道、自循环）—— skill 运行真依赖（76 处引用）
├── CONTRACT_SPEC.md            # contract.yaml 编写规范 —— validate.sh Check 14 校验依据
├── AI_CODING_BEST_PRACTICES.md # AI 辅助开发实践参考 —— 开发者指南，非 skill 依赖
├── PIPELINES.md                # 链路数据流规格 —— 编排层开发者参考，非 skill 依赖
├── agents/                     # Agent 定义文件（单一事实源；无 frontmatter，由 skill 通过 Task tool 显式调用，不被 Claude/Codex agent loader 自动注册）
│   ├── AGENT_TEMPLATE.md       # 统一模板
│   ├── test-case-writer.md     # 测试用例生成 Agent
│   ├── test-case-generation/   # 用例评审冗余对 Agent
│   │   ├── review-agent-1.md   # 覆盖度视角评审 Agent
│   │   └── review-agent-2.md   # 质量视角评审 Agent
│   ├── ui-fidelity-checker.md  # UI 还原度检查 Agent（被 traceability §3.4 调用，无独立 skill）
│   ├── api-contract-validator.md  # API 契约校验 Agent（被 traceability §3.2.5 + api-contract-validation skill 共享）
│   └── requirement-traceability/   # 需求追溯（仅 case-tracer）
├── skills/
│   ├── _shared/                    # 共享协议和框架文件
│   ├── shared-tools/               # 共享脚本
│   ├── requirement-clarification/  # 需求澄清（含影响范围分析）
│   ├── requirement-review/         # 需求评审（12 维度）
│   ├── test-case-generation/       # 测试用例生成（含冗余对评审）
│   ├── test-case-review/           # 用例评审（独立深度评审）
│   ├── change-analysis/            # 变更分析（Story/Bug 双场景）
│   ├── requirement-traceability/   # 需求回溯（双通道 + 内嵌用例中介验证 + UI 还原度 + API 契约校验，后两者通过共享 agent 启动）
│   ├── test-failure-analyzer/      # 测试失败分析（自循环）
│   ├── unit-test-design/           # 单元测试代码生成
│   ├── integration-test-design/    # 集成测试代码生成
│   ├── api-contract-validation/    # API 契约校验
│   ├── metersphere-sync/          # MeterSphere 用例同步与测试计划管理
│   └── qa-workflow/               # QA 工作流编排器
├── contracts/                     # JSON Schema + collision 白名单
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

**MeterSphere（13 个 `MS_*` 变量）**：详见飞书 [MeterSphere 配置 (.env)](https://xd.feishu.cn/wiki/K4Cxw8HE5itR16kFFYicSctAnrc)。不用提前手动配 — 首次跑 `metersphere-sync` 报 `missing required environment variables` 时把飞书配置块贴给 AI 即可。

## 版本历史

- **v0.0.10** - 一次大版本，6 块改动合并发布：
  1. **requirement-review / requirement-clarification 单 Agent 强推理重构**：删除 user/functional/exception-perspective 三个子代理；4.1.7 反 collapse 枚举归一化 + 4.1.8 多变体一致性约束；`rr_summary.json` 新增 `confidence` 字段 + verdict 优先级链硬规则（命中即停）。`requirement-clarification` 改用同样的单 Agent 强推理；`requirement-review/PHASES.md` 4.0 模式说明改中性命名（设计稿评审模式 / 描述评审模式）。
  2. **飞书报告 checkbox 反馈结构**：4 份 TEMPLATES（rr / tcr / rt / ca）统一改用表格 + 二选一 checkbox 反馈；`requirement-traceability` 缺陷清单加 `---` 分隔；`change-analysis §6` 加 cross-validation 综合结论 checkbox。新增 `CONVENTIONS.md`「飞书文档渲染规范」段；`_shared/REQUIREMENT_DIMENSIONS.md` 加 severity 阻断/关注（P0/P1 alias）+ verdict↔confidence 映射；`contracts/rr-summary.schema.json` `confidence` / `blocking_issues` 改 required；`tests/check-schemas.sh` 加越界/缺失拒收用例。
  3. **`AI_CODING_BEST_PRACTICES.md` 工程师视角重写**：新增「按问题查」索引 + §0 Quickstart + 各阶段复制即用 prompt 模板 + Phase 3 plan-mode 三段式 walkthrough + 「反模式」「Troubleshooting」「术语小词典」；进一步阅读分必读/选读；统一 callout 风格（💡⚠️✅📥）。**团队内部内容**（iOS 真实案例 / 裸需求场景对比 / RACI / 内部联系人）迁移至飞书 wiki，repo 仅留单行指针。`README` ↔ `AI_CODING_BEST_PRACTICES` 去重：README 退回 catalog 角色，完整 SOP 由 BP 承载。
  4. **MeterSphere 配置失实修复**：`metersphere-sync/SKILL.md` 和 `AI_CODING_BEST_PRACTICES.md` 原本说 MS 凭据「零配置 / 已内置」是错的——`metersphere_helper.py` 从 `.env` 读，只有 `MS_DEFAULT_MAINTAINER` / `MS_DEFAULT_STAGE` 有内置默认。两份文档改为描述真实的「懒人路径」UX；环境变量表从 6 扩到 11 行；`metersphere_helper.py` 把 MS env 检查从模块级改为 lazy（`_LOCAL_ONLY_COMMANDS = {'validate-fv'}` 白名单），让纯本地 schema 校验子命令在 CI 不需要 MS 凭据。
  5. **Smoke-test 诚实判定 + cross-component 数据流断链检测**（GameJam 漏报根因修复）：新增单一权威字段 `input_quality`（full/medium/low），下游 4.6 / 4.5 / 5S.2 都按此降级。§3.1 新增 1.5 档消费 `change_supplementary_cases.json`；§4.6 兜底合成仅在 `input_quality == "low"` 时允许触发；§5S.2 verdict 从二元扩为五档；§3.2.0a 新增 evidence completeness 契约（A 数据流闭合 / B 跨边界自然记录 / D 失败模式路径驱动 由 `validate-fv` 机械校验，C 逐 expected 对应是模型自检——不入 validator 以避免虚假安全感）；§5S.1 新增 source 7 `cross_component_break` 缺陷源；`tests/validate.sh` 新增 Check N+2 回归锁。
  6. **ui-fidelity-check skill 合并 + api-contract-validator agent 抽取**：删除 `ui-fidelity-check` 独立 skill（去 page_url 后与 traceability §3.4 等价），底层 `agents/ui-fidelity-checker.md` 简化保留；新建 `agents/api-contract-validator.md`（无副作用纯计算单元），`api-contract-validation` skill 和 traceability §3.2.5 共享同一 agent，消除"轻量内置 + 上游优先"二选一的混乱。`api-contract-validation` skill 保留独立入口（PR pre-merge gate 等纯前后端契约场景）。`qa-workflow` 步骤号重排；README / PIPELINES / TRACEABILITY_PROTOCOL / known-collisions.yaml 同步清理。
- **v0.0.9** - 飞书报告可读性优化：requirement-review 重构 `TEMPLATES.md`（10 处可读性优化 + 5 处飞书 import 兼容性修复），test-case-review / change-analysis / requirement-traceability 新建 `TEMPLATES.md`（覆盖 review_summary.md / multi-doc / smoke-test report.md）；统一 4 工作流报告 11 条约定（无 H1、无表格、无 emoji、无 ASCII、无星级、统一中文方括号 `[通过]/[已覆盖]/[实证]/[P0]` 等）。修复 requirement-review `rr_summary.json` 写出非法 `review_mode` 值。test 插件全量评审 + CI 基线加固：`tests/validate.sh` 5 → 9 类检查（SKILL frontmatter / handoffs / subagent_type / references / contract collision），新增 `contracts/known-collisions.yaml` 白名单；解决 8 处 contract 输出冲突（`risk_assessment.json` → `bug_risk_assessment.json`、`test_execution_report.json` 拆 unit/integration、`supplementary_cases.json` 按上游 skill 拆 change/review）；删除 3 个零调用 agent (`forward-tracer`/`reverse-tracer`/`failure-classifier`) + 13 处死引用清理；shared-tools / feedback `requirements.txt` 与 env_vars 诚实化；5 个 helper 脚本 `-h/--help` UX 一致化；schema 校验从 1 → 5（testcase / ca-summary / defect-list / rr-summary / smoke-test-report）；同步 PIPELINES / README / TEMPLATES / contract.yaml 中 contract rename 后残留的旧文件名引用。8 维 skill 评审收尾（阶段 1-3）：3 个 contract.yaml 给 5 个 `*_cases.json` 输出显式绑 `testcase.schema.json`；tcg/ca SKILL description 加"需求驱动 / 变更驱动"区分 + ca↔trace 互引 SKIP；test-case-review SKILL 注明 `review_result.json` 为非严格 JSON（verdict 对象、不绑 schema）；从 ai-case Pydantic 同步 `testcase.schema.json` — `Step.expected` 改必填（允许空串），`test_method` 在 CONVENTIONS.md 同步改可选；trace PHASES Phase 6 / PIPELINES.md 加交叉引用到 known-collisions.yaml，澄清 Phase 6 writeback 与 ms-sync mode=execute 是"同 helper、双入口"；qa-workflow 接受 `re_entry_phase` + `requirement_change_summary`，支持需求变更后增量重跑透传 tcg；README 选用指引补 tcg/ca 驱动条件区分、去掉过期 "v0.0.10+" 版本门；requirement-clarification SKILL 注明 `output/*.json` 是预制格式样例非运行时产出；README + AGENT_PROTOCOL.md 说明 `agents/` 下 .md 无 frontmatter 不会被 loader 自动注册（仅由 skill 通过 Task tool 显式调用）
- **v0.0.8** - requirement-clarification 新增多变体一致性追问（防类继承/父组件级联导致 UI 隐式扩散）、PRD 文档质量校对、icon 来源确认；分类变量改为正向枚举；`enum_factors` 贯穿到 `requirement_points.json`。test-case-generation 新增 phase 3.5 `scan-ambiguities`（生成前批量追问歧义点写入 `clarifications.json`，未确认项强制 `expected = [待确认] {原因}`），phase 6 confirm 跳过已带 `[待确认]` 的重复 review，禁止 step 出现"A 或 B"歧义。requirement-traceability 新增 Phase 4.6 `forward_verification.json` 兜底合成（从 coverage_report 的 per-FP verdict 合成），Phase 6.1 不再静默跳过缺失文件，Closing Checklist 把 `forward_verification.json` 和 `ms_sync_report.json` 标为强制产出；修复 traceability ↔ ms-sync 回写链路（P10/P11/P12）；闭合 D1-D12 dead branch；Recovery Cookbook 抽出独立文件；forward-tracer 弃用并入主 agent。integration-test-design 新增"集成测试价值评估"分层判定（API 契约/路由/跨模块通知归集成、纯反序列化/状态计算归单元、UI 渲染归 E2E），跳过场景写入"跳过的场景"表；新增共享 `_shared/UNIT_VS_INTEGRATION_BOUNDARIES.md` 跨 skill 边界（L1-L6 层归属表）。AI_CODING_BEST_PRACTICES.md 重构为三层（30 秒速查 → 分阶段 SOP → 案例复盘），阶段 4 拆为 4a（AI 还原度）+ 4b（人工真机走查），阶段 5 显式引用 `git:commit-push-pr` 和 `git:code-reviewing`，阶段 3 文档 plan-mode 三段式。feedback skill 调整 iOS 社区版 / 易页 PM 模块 / 内容发布 ownership
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
