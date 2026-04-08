# Pipeline 数据流规格

本文件正式定义各链路中 skill 间的数据流向，供编排层实现跨 session 数据传递时作为规范依据。

概要描述见 [README.md](README.md#快速开始)。

## 链路 A — 功能测试全流程

```
[requirement-clarification]
    │
    ├─→ clarified_requirements.json
    ├─→ requirement_points.json
    └─→ implementation_brief.json
        │
        ▼
[test-case-generation]
    │  消费: clarified_requirements.json, requirement_points.json
    │
    ├─→ final_cases.json
    ├─→ test_cases.json
    ├─→ tc_gen_review.md
    └─→ review_summary.json
        │
        ▼  + 用户提供 MR/PR 链接（手动输入）
[requirement-traceability]
    │  消费: clarified_requirements.json, requirement_points.json
    │  注意: 不消费 final_cases.json
    │
    ├─→ traceability_matrix.json
    ├─→ traceability_coverage_report.json
    ├─→ forward_verification.json
    └─→ risk_assessment.json
```

### 可选扩展：MeterSphere 同步

```
[test-case-generation]
    └─→ final_cases.json
        ▼
[metersphere-sync]    (mode=sync)
    │  消费: final_cases.json
    └─→ ms_sync_report.json, ms_case_mapping.json, ms_plan_info.json
```

[requirement-traceability] 完成后可追加 execute 模式回写验证结果：

```
[requirement-traceability / verification-test-generation]
    └─→ verification_cases.json
        ▼
[metersphere-sync]    (mode=execute)
    │  消费: final_cases.json, verification_cases.json, ms_case_mapping.json
    └─→ ms_sync_report.json (含执行回写统计)
```

### 数据流映射

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 |
|---|---|---|---|
| requirement-clarification | `clarified_requirements.json` | test-case-generation | `clarified_requirements` |
| requirement-clarification | `requirement_points.json` | test-case-generation | `requirement_points` |
| requirement-clarification | `clarified_requirements.json` | requirement-traceability | `clarified_requirements` |
| requirement-clarification | `requirement_points.json` | requirement-traceability | `requirement_points` |
| test-case-generation | `final_cases.json` | metersphere-sync | `final_cases` |
| verification-test-generation | `verification_cases.json` | metersphere-sync | `verification_cases` |
| requirement-clarification | `requirement_points.json` | metersphere-sync | `requirement_points` |

---

## 链路 B — 代码级测试生成

```
[unit-test-design]        源代码 → 测试文件 + test_plan.md
[integration-test-design] API/服务 → 集成测试文件 + integration_test_plan.md
```

### 可选上游

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 | 用途 |
|---|---|---|---|---|
| requirement-clarification | `requirement_points.json` | unit-test-design | `requirement_points` | 指导覆盖重点 |
| test-case-generation | `final_cases.json` | unit-test-design | `final_cases` | 参考已有用例 |
| requirement-clarification | `requirement_points.json` | integration-test-design | `requirement_points` | 指导覆盖重点 |

---

## 链路 D — 需求回溯增强

```
[verification-test-generation]
    │  消费: requirement_points.json (from 链路 A)
    │
    └─→ verification_cases.json
        │
        ▼
[ui-fidelity-check]  (条件：有 Figma 设计稿)
    │
    └─→ ui_fidelity_report.json
        │
        ▼
[requirement-traceability]
    │  消费: verification_cases.json, ui_fidelity_report.json
    │
    └─→ traceability_coverage_report.json（含正向验证率 + UI 还原度）
```

### 数据流映射

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 |
|---|---|---|---|
| verification-test-generation | `verification_cases.json` | requirement-traceability | `verification_cases` |
| ui-fidelity-check | `ui_fidelity_report.json` | requirement-traceability | `ui_fidelity_report` |
| api-contract-validation | `api_contract_report.json` | requirement-traceability | `api_contract_report` |

---

## 链路 E — 测试失败自循环

```
[unit-test-design / integration-test-design]
    │
    └─→ test_execution_report.json (verify 阶段产出)
        │
        ▼
[test-failure-analyzer]
    │  消费: test_execution_report.json + 代码 diff
    │
    ├─→ failure_analysis.json
    └─→ action_plan.md
        │
        ↺ 修复 → 重测（最多 3 轮）
```

### 数据流映射

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 |
|---|---|---|---|
| unit-test-design | `test_execution_report.json` | test-failure-analyzer | `test_report` |
| integration-test-design | `test_execution_report.json` | test-failure-analyzer | `test_report` |

---

## 链路 F — 变更分析

```
Story 场景:
[change-analysis]
    │  输入: Story + MR/PR
    │  可选消费: clarified_requirements.json, requirement_points.json, final_cases.json
    │
    ├─→ change_analysis.json
    ├─→ code_change_analysis.md
    ├─→ change_coverage_report.json
    └─→ supplementary_cases.json (可选)

Bug 场景:
[change-analysis]
    │  输入: Bug + MR/PR
    │
    ├─→ change_analysis.json
    ├─→ code_change_analysis.md
    ├─→ change_fix_analysis.json
    └─→ risk_assessment.json
```

### 可选上游

| 上游 Skill | 输出文件 | 下游 Skill | 输入参数 |
|---|---|---|---|
| requirement-clarification | `clarified_requirements.json` | change-analysis | `clarified_requirements` |
| requirement-clarification | `requirement_points.json` | change-analysis | `requirement_points` |
| test-case-generation | `final_cases.json` | change-analysis | `existing_test_cases` |
| test-case-review | `supplementary_cases.json` | change-analysis | `existing_test_cases` |

---

## 链路 G — 用例评审

```
[test-case-review]
    │  输入: 已有测试用例 + 需求文档
    │  可选消费: final_cases.json (from test-case-generation)
    │
    ├─→ review_result.json
    ├─→ tc_review_detail.md
    └─→ supplementary_cases.json (可选)
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
[change-analysis] ─────────────┐
[verification-test-generation] ┤ 并行
[ui-fidelity-check]  ──────────┘ 条件：有设计稿
[api-contract-validation]         条件：前后端协调
    ↓
[requirement-traceability] → [metersphere-sync mode=execute]
    → 暂停等人工验证

Phase 3: 收尾
[git:code-reviewing] → [git:commit-push-pr]（可选）
```

详见 `skills/qa-workflow/SKILL.md` 和 `skills/qa-workflow/WORKFLOW_DEFS.md`。

---

## 工作目录布局约定

Pipeline 中所有 skill 共享同一工作目录。各 skill 的输出文件直接写入工作目录根（非子目录），下游 skill 在 init/fetch 阶段检查上游文件是否存在。

```
work_dir/
├── clarified_requirements.json    (requirement-clarification)
├── requirement_points.json        (requirement-clarification)
├── implementation_brief.json      (requirement-clarification)
├── final_cases.json               (test-case-generation)
├── test_cases.json                (test-case-generation)
├── tc_gen_review.md               (test-case-generation)
├── review_summary.json            (test-case-generation)
├── verification_cases.json        (verification-test-generation)
├── verification_report.json       (verification-test-generation)
├── traceability_matrix.json       (requirement-traceability)
├── traceability_coverage_report.json  (requirement-traceability)
├── forward_verification.json      (requirement-traceability)
├── risk_assessment.json           (requirement-traceability / change-analysis Bug)
├── change_analysis.json           (change-analysis)
├── code_change_analysis.md        (change-analysis, 中间文件)
├── change_coverage_report.json    (change-analysis Story)
├── change_fix_analysis.json       (change-analysis Bug)
├── supplementary_cases.json       (change-analysis / test-case-review)
├── review_result.json             (test-case-review)
├── tc_review_detail.md            (test-case-review)
├── api_contract_report.json       (api-contract-validation)
├── ui_fidelity_report.json        (ui-fidelity-check)
├── failure_analysis.json          (test-failure-analyzer)
├── action_plan.md                 (test-failure-analyzer)
├── ms_case_mapping.json           (metersphere-sync)
├── ms_plan_info.json              (metersphere-sync)
└── ms_sync_report.json            (metersphere-sync)
```

## 上游文件检测约定

各 skill 在 init/fetch 阶段按 [CONVENTIONS.md 输入路由](CONVENTIONS.md#上游输入消费) 检查上游文件：

1. 工作目录中存在上游产出文件 → 优先消费，跳过对应获取步骤
2. 不存在 → 按各 skill 的降级策略处理（独立获取或降级继续）
