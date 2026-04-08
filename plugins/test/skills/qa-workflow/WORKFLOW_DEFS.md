# 工作流模板定义

> 所有模板的步骤 ID 在各模板内独立编号。qa-full 模板的 ID 与 SKILL.md 全景图中的 #N 编号一致。

## qa-full（默认）

完整 QA 流程，所有步骤均包含。

```json
[
  {"id": 1, "skill": "requirement-clarification", "phase": 1},
  {"id": 2, "skill": "test-case-generation", "phase": 1, "params": {"confirm_policy": "accept_all"}},
  {"id": 3, "skill": "metersphere-sync", "phase": 1, "params": {"mode": "sync", "plan_name": "auto"}},
  {"id": 4, "type": "user_gate", "phase": 1, "prompt": "编码完成后回来，提供 MR 链接或说'代码写完了'", "transitions_to": 2},
  {"id": 5, "skill": "change-analysis", "phase": 2, "parallel_group": "verify"},
  {"id": 6, "skill": "verification-test-generation", "phase": 2, "parallel_group": "verify"},
  {"id": 7, "skill": "ui-fidelity-check", "phase": 2, "condition": "has_design_link", "parallel_group": "verify"},
  {"id": 8, "skill": "api-contract-validation", "phase": 2, "condition": "coordination_needed"},
  {"id": 9, "skill": "requirement-traceability", "phase": 2},
  {"id": 10, "skill": "metersphere-sync", "phase": 2, "params": {"mode": "execute", "plan_name": "auto"}},
  {"id": 11, "type": "user_gate", "phase": 2, "prompt": "请在 MS 中验证低置信度用例，完成后回来", "transitions_to": 3},
  {"id": 12, "skill": "git:code-reviewing", "phase": 3},
  {"id": 13, "skill": "git:commit-push-pr", "phase": 3, "optional": true}
]
```

## qa-lite

跳过 MeterSphere 同步和执行回写，适合不使用 MS 平台的团队。无 MS 则 Phase 2 结束后无需人工验证 gate，直接进 Phase 3。

```json
[
  {"id": 1, "skill": "requirement-clarification", "phase": 1},
  {"id": 2, "skill": "test-case-generation", "phase": 1, "params": {"confirm_policy": "accept_all"}},
  {"id": 3, "type": "user_gate", "phase": 1, "prompt": "编码完成后回来，提供 MR 链接或说'代码写完了'", "transitions_to": 2},
  {"id": 4, "skill": "change-analysis", "phase": 2, "parallel_group": "verify"},
  {"id": 5, "skill": "verification-test-generation", "phase": 2, "parallel_group": "verify"},
  {"id": 6, "skill": "ui-fidelity-check", "phase": 2, "condition": "has_design_link", "parallel_group": "verify"},
  {"id": 7, "skill": "api-contract-validation", "phase": 2, "condition": "coordination_needed"},
  {"id": 8, "skill": "requirement-traceability", "phase": 2},
  {"id": 9, "skill": "git:code-reviewing", "phase": 3},
  {"id": 10, "skill": "git:commit-push-pr", "phase": 3, "optional": true}
]
```

## verify-only

仅做代码验证，跳过需求澄清、用例生成和 MS 同步。适合已有测试用例，只需验证代码实现的场景。

前置条件：`$TEST_WORKSPACE` 中需已有 `final_cases.json` 或 `requirement_points.json`。

```json
[
  {"id": 1, "type": "user_gate", "phase": 1, "prompt": "请提供 MR 链接或说'代码写完了'", "transitions_to": 2},
  {"id": 2, "skill": "change-analysis", "phase": 2, "parallel_group": "verify"},
  {"id": 3, "skill": "verification-test-generation", "phase": 2, "parallel_group": "verify"},
  {"id": 4, "skill": "ui-fidelity-check", "phase": 2, "condition": "has_design_link", "parallel_group": "verify"},
  {"id": 5, "skill": "api-contract-validation", "phase": 2, "condition": "coordination_needed"},
  {"id": 6, "skill": "requirement-traceability", "phase": 2},
  {"id": 7, "skill": "git:code-reviewing", "phase": 3},
  {"id": 8, "skill": "git:commit-push-pr", "phase": 3, "optional": true}
]
```
