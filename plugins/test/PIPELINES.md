# Pipeline 数据流规格

本文件正式定义各链路中 skill 间的数据流向，供编排层实现跨 session 数据传递时作为规范依据。

概要描述见 [README.md](README.md#快速开始)。

> **受众**：实现编排层 / pipeline 的开发者。
> **不是**：skill 运行的强制依赖文件 — 各 skill 的 `contract.yaml` 已是机器可读的接口定义，本文是给人读的跨 skill 链路全景图。

## 链路 A — 功能测试全流程

```
[requirement-clarification]
    │
    ├─→ clarification/clarified_requirements.json
    ├─→ clarification/requirement_points.json
    └─→ clarification/implementation_brief.json
        │
        ▼
[test-case-generation]
    │  消费: clarification/clarified_requirements.json, clarification/requirement_points.json
    │
    ├─→ test_cases/final_cases.json
    ├─→ test_cases/test_cases.json
    ├─→ test_cases/tc_gen_review.md
    └─→ test_cases/review_summary.json
        │
        ▼  + 用户提供 MR/PR 链接（手动输入）
[requirement-traceability]
    │  消费: clarification/clarified_requirements.json, clarification/requirement_points.json, test_cases/final_cases.json
    │
    ├─→ traceability/<change_set_slug>/traceability_matrix.json
    ├─→ traceability/<change_set_slug>/traceability_coverage_report.json
    ├─→ traceability/<change_set_slug>/forward_verification.json
    └─→ traceability/<change_set_slug>/risk_assessment.json
```

### 可选扩展：MeterSphere 同步

```
[test-case-generation]
    └─→ test_cases/final_cases.json
        ▼
[metersphere-sync]    (mode=sync)
    │  消费: test_cases/final_cases.json
    └─→ metersphere/ms_import_report.json, metersphere/ms_case_mapping.json, metersphere/ms_plan_info.json
```

[requirement-traceability] 完成后可追加 execute 模式回写验证结果：

```
[requirement-traceability]
    │  正向通道内嵌用例中介验证（消费上游 test_cases/final_cases.json）
    └─→ traceability/<change_set_slug>/forward_verification.json
        ▼
[metersphere-sync]    (mode=execute)
    │  消费: test_cases/final_cases.json, traceability/<change_set_slug>/forward_verification.json, metersphere/ms_case_mapping.json
    └─→ traceability/<change_set_slug>/ms_sync_report.json (含执行回写统计)
```

> **与 trace Phase 6 writeback 的关系**：上图描述的是手动模式调用入口；自动模式（qa-workflow）下 writeback 由 `requirement-traceability` 内部 Phase 6 触发，不显式调 `metersphere-sync mode=execute`。两入口共享同一 helper，互斥执行。共享/互斥规则详见 [`contracts/known-collisions.yaml`](contracts/known-collisions.yaml) 的 `forward_verification.enriched.json` 条目。

### 数据流映射

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 |
|---|---|---|---|
| requirement-clarification | `clarification/clarified_requirements.json` | test-case-generation | `clarified_requirements` |
| requirement-clarification | `clarification/requirement_points.json` | test-case-generation | `requirement_points` |
| requirement-clarification | `clarification/clarified_requirements.json` | requirement-traceability | `clarified_requirements` |
| requirement-clarification | `clarification/requirement_points.json` | requirement-traceability | `requirement_points` |
| test-case-generation | `test_cases/final_cases.json` | requirement-traceability | `final_cases` |
| test-case-generation | `test_cases/final_cases.json` | metersphere-sync | `final_cases` |
| requirement-traceability | `traceability/<change_set_slug>/forward_verification.json` | metersphere-sync | `forward_verification` |
| requirement-clarification | `clarification/requirement_points.json` | metersphere-sync | `requirement_points` |

---

## 链路 B — 代码级测试生成

```
[unit-test-design]        源代码 → 测试文件 + test_plan.md
[integration-test-design] API/服务 → 集成测试文件 + integration_test_plan.md
```

### 可选上游

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 | 用途 |
|---|---|---|---|---|
| requirement-clarification | `clarification/requirement_points.json` | unit-test-design | `requirement_points` | 指导覆盖重点 |
| test-case-generation | `test_cases/final_cases.json` | unit-test-design | `final_cases` | 参考已有用例 |
| requirement-clarification | `clarification/requirement_points.json` | integration-test-design | `requirement_points` | 指导覆盖重点 |

---

## 链路 D — 需求回溯增强

UI 还原度由 requirement-traceability §3.4 隐式触发（`design_link` + `code_dir` 都透传时），不再需要单独 skill。API 契约校验仍可由独立 skill 预生成产出供 traceability 优先消费。

```
[api-contract-validation]  (可选：前后端协调时单独跑，预生成深度报告)
    │
    └─→ api_contract_report.json
        │
        ▼
[requirement-traceability]
    │  消费: test_cases/final_cases.json (链路 A 产出，正向通道用例输入)
    │       design_link + code_dir → §3.4 内置启动 ui-fidelity-checker Agent，
    │                                产出 ui_fidelity_report.json
    │       api_contract_report.json (优先消费上游产出；缺则 §3.2.5 内置启动
    │                                 api-contract-validator Agent)
    │
    ├─→ traceability/<change_set_slug>/forward_verification.json（内嵌正向用例中介验证结果）
    └─→ traceability/<change_set_slug>/traceability_coverage_report.json（含正向验证率 + UI 还原度 + API 契约）
```

### 数据流映射

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 |
|---|---|---|---|
| test-case-generation | `final_cases.json` | requirement-traceability | `final_cases`（正向通道用例输入，优先消费） |
| api-contract-validation | `api_contract_report.json` | requirement-traceability | `api_contract_report`（可选；缺则内置 agent） |

---

## 链路 E — 测试失败自循环

```
[unit-test-design / integration-test-design]
    │
    └─→ unit_test_execution_report.json / integration_test_execution_report.json (verify 阶段产出)
        │
        ▼
[test-failure-analyzer]
    │  消费: unit_test_execution_report.json / integration_test_execution_report.json + 代码 diff
    │
    ├─→ failure_analysis.json
    └─→ action_plan.md
        │
        ↺ 修复 → 重测（最多 3 轮）
```

### 数据流映射

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 |
|---|---|---|---|
| unit-test-design | `unit_test_execution_report.json` | test-failure-analyzer | `test_report` |
| integration-test-design | `integration_test_execution_report.json` | test-failure-analyzer | `test_report` |

---

## 链路 F — 变更分析

```
Story 场景:
[change-analysis]
    │  输入: Story + MR/PR
    │  可选消费: clarification/clarified_requirements.json, clarification/requirement_points.json, test_cases/final_cases.json
    │
    ├─→ change_analysis.json
    ├─→ code_change_analysis.md
    ├─→ change_coverage_report.json
    └─→ change_supplementary_cases.json (可选)

Bug 场景:
[change-analysis]
    │  输入: Bug + MR/PR
    │
    ├─→ change_analysis.json
    ├─→ code_change_analysis.md
    ├─→ change_fix_analysis.json
    └─→ bug_risk_assessment.json
```

### 可选上游

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 |
|---|---|---|---|
| requirement-clarification | `clarification/clarified_requirements.json` | change-analysis | `clarified_requirements` |
| requirement-clarification | `clarification/requirement_points.json` | change-analysis | `requirement_points` |
| test-case-generation | `test_cases/final_cases.json` | change-analysis | `existing_test_cases` |
| test-case-review | `review_supplementary_cases.json` | change-analysis | `existing_test_cases` |

---

## 链路 G — 用例评审

```
[test-case-review]
    │  输入: 已有测试用例 + 需求文档
    │  可选消费: test_cases/final_cases.json (from test-case-generation)
    │
    ├─→ review_result.json
    ├─→ tc_review_detail.md
    └─→ review_supplementary_cases.json (可选)
```

---

## 链路 H — API 契约校验

```
[api-contract-validation]
    │  输入: 前端 diff + 后端 diff/OpenAPI spec
    │
    └─→ api_contract_report.json
        │
        ▼ (可选，供链路 D 消费)
[requirement-traceability]
    │  跳过内置轻量契约检查，使用深度校验结果
```

---

## 编排链路 — qa-workflow 端到端编排

`qa-workflow` skill 将链路 A/D/F/H 串联为自动化工作流，支持条件分支和并行执行。

```
Phase 1: 需求分析
[requirement-clarification] → [test-case-generation] → [metersphere-sync mode=sync]
    → 暂停等编码

Phase 2: 代码验证（用户回来后）
[change-analysis] ──────────────┐
[api-contract-validation]  ─────┘ 条件：前后端协调（与 change-analysis 并行）
    ↓
[requirement-traceability]（内嵌正向用例中介验证，消费上游 test_cases/final_cases.json；
                          §3.4 在有 design_link + code_dir 时启动 ui-fidelity-checker Agent；
                          §3.2.5 在缺 api_contract_report 时启动 api-contract-validator Agent）
    → [metersphere-sync mode=execute]
    → 暂停等人工验证

Phase 3: 收尾
[git:code-reviewing] → [git:commit-push-pr]（可选）
```

详见 `skills/qa-workflow/SKILL.md` 和 `skills/qa-workflow/WORKFLOW_DEFS.md`。

---

## 工作目录布局约定

Pipeline 中所有 skill 共享同一公共需求工作区 `$TEST_WORKSPACE`。各 skill 按职责写入固定子目录，下游 skill 在 init/fetch 阶段检查对应子目录中的上游文件是否存在。

```
requirement_<stable_id>/
├── manifest.json
├── source/
│   └── requirement_doc.md
├── clarification/
│   ├── clarified_requirements.json    (requirement-clarification)
│   ├── requirement_points.json        (requirement-clarification)
│   └── implementation_brief.json      (requirement-clarification)
├── test_cases/
│   ├── final_cases.json               (test-case-generation)
│   ├── test_cases.json                (test-case-generation)
│   ├── tc_gen_review.md               (test-case-generation)
│   └── review_summary.json            (test-case-generation)
├── traceability/
│   └── <change_set_slug>/
│       ├── traceability_matrix.json       (requirement-traceability)
│       ├── traceability_coverage_report.json  (requirement-traceability)
│       ├── forward_verification.json      (requirement-traceability)
│       ├── risk_assessment.json           (requirement-traceability)
│       ├── ms_sync_report.json            (requirement-traceability / metersphere-sync execute)
│       ├── pass_with_caveats.md
│       └── pending_external_validation.md
├── bug_risk_assessment.json       (change-analysis Bug)
├── change_analysis.json           (change-analysis)
├── code_change_analysis.md        (change-analysis, 中间文件)
├── change_coverage_report.json    (change-analysis Story)
├── change_fix_analysis.json       (change-analysis Bug)
├── supplementary_cases.json       (test-case-generation, canonical)
├── change_supplementary_cases.json (change-analysis)
├── review_supplementary_cases.json (test-case-review)
├── review_result.json             (test-case-review)
├── tc_review_detail.md            (test-case-review)
├── api_contract_report.json       (api-contract-validation)
├── ui_fidelity_report.json        (requirement-traceability §3.4)
├── failure_analysis.json          (test-failure-analyzer)
├── action_plan.md                 (test-failure-analyzer)
└── metersphere/
    ├── ms_case_mapping.json           (metersphere-sync)
    ├── ms_plan_info.json              (metersphere-sync)
    └── ms_import_report.json          (metersphere-sync sync)
```

## 上游文件检测约定

各 skill 在 init/fetch 阶段按 [CONVENTIONS.md 输入路由](CONVENTIONS.md#上游输入消费) 检查上游文件：

1. 工作目录中存在上游产出文件 → 优先消费，跳过对应获取步骤
2. 不存在 → 按各 skill 的降级策略处理（独立获取或降级继续）
