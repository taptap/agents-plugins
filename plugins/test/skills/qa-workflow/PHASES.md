# QA 工作流编排器各阶段详细操作指南

## 阶段 0: init — 初始化或恢复

### 0.1 判断工作流状态

检查 `$TEST_WORKSPACE/workflow_state.json` 是否存在：

1. **不存在** → 初始化新工作流（0.2）
2. **存在 + `resume=true`** → 读取状态文件，跳到 `current_phase` 对应阶段的下一个 pending 步骤
3. **存在 + 用户提供了 `code_changes` 或说"代码写完了"** → 进入 Phase 2（更新 `user_inputs.code_changes`）
4. **存在 + 用户说"验证完了"/"人工验证完成"** → 进入 Phase 3

### 0.2 初始化新工作流

1. 确定工作区目录：
   - `$TEST_WORKSPACE` 已设置 → 使用该目录
   - 未设置 → 请求用户提供需求名（用于创建 `plugins/test/workspace/{name}/`）

2. 根据 `pipeline` 参数选择模板（默认 `qa-full`），参见 [WORKFLOW_DEFS.md](WORKFLOW_DEFS.md)

3. 记录初始参数到 `workflow_state.json`：
   - `story_link` / `requirement_doc`
   - `design_link`（如提供）
   - `pipeline` 模板名
   - 所有步骤初始化为 `pending`

4. 进入 Phase 1

---

## 阶段 1: 需求分析与用例准备

### 1.1 需求澄清

根据输入类型调用（三选一）：
```
# 飞书链接
Skill(skill: "test:requirement-clarification", args: "story_link=<story_link>")
# 本地文档
Skill(skill: "test:requirement-clarification", args: "requirement_doc=<file_path>")
# 文字说明
Skill(skill: "test:requirement-clarification", args: "requirement_text=<text>")
```

如用户同时提供了 `design_link`，追加到 args：
```
Skill(skill: "test:requirement-clarification", args: "story_link=<story_link> design_link=<design_link>")
```

完成后：
1. Read `$TEST_WORKSPACE/clarified_requirements.json`
2. 提取并更新 `derived_params`：
   - `plan_name` ← JSON 中的需求标题（story_name 或第一层 title）
   - `coordination_needed` ← `platform_scope.coordination_needed`
   - `platform_scope` ← `platform_scope.platforms`
   - `has_design_link` ← `design_link` 是否非空
3. 根据条件更新步骤状态：
   - `has_design_link == true` → 步骤 #6 (ui-fidelity-check) 保持 `pending`
   - `has_design_link == false` → 步骤 #6 设为 `skipped`
   - `coordination_needed == true` → 步骤 #7 (api-contract-validation) 保持 `pending`
   - `coordination_needed == false` → 步骤 #7 设为 `skipped`
4. 更新 `workflow_state.json`：步骤 #1 标记 `completed`

### 1.2 测试用例生成

调用：
```
Skill(skill: "test:test-case-generation", args: "confirm_policy=accept_all")
```

> `confirm_policy=accept_all` 使 confirm 阶段自动接受所有评审建议，避免阻塞编排流程。
> 如用户明确要求交互式确认，可传入 `confirm_policy=interactive`。

完成后：
1. 确认 `$TEST_WORKSPACE/final_cases.json` 存在
2. 更新 `workflow_state.json`：步骤 #2 标记 `completed`

### 1.3 MeterSphere 同步（qa-lite 模板跳过此步）

调用：
```
Skill(skill: "test:metersphere-sync", args: "mode=sync plan_name=<derived_params.plan_name>")
```

完成后：
1. Read `$TEST_WORKSPACE/ms_plan_info.json` 获取 `plan_url`
2. 更新 `workflow_state.json`：步骤 #3 标记 `completed`

### 1.4 暂停 — 等待编码

输出摘要给用户：

```
## QA Phase 1 完成

- 需求已澄清：N 个功能点
- 测试用例已生成：M 条（P0: x, P1: y, P2: z）
- 测试计划已创建：[计划名称](plan_url)

### 下一步
请开始编码。完成后回来，可以：
- 提供 MR/PR 链接
- 说"代码写完了"（使用本地 git diff）
- 说"帮我 review 并提 MR"（自动完成后续全部流程）
```

更新 `workflow_state.json`：
- `current_phase = 2`
- 步骤 #4 (user_gate) 设为 `waiting`

---

## 阶段 2: 代码验证

### 2.0 判断代码变更来源

根据用户输入确定 `code_changes` / `code_diff`：

1. **用户提供了 MR/PR URL**：
   ```
   user_inputs.code_changes = ["https://..."]
   ```

2. **用户说"代码写完了"但无 MR**：
   ```bash
   git diff > $TEST_WORKSPACE/local.diff
   git diff --cached >> $TEST_WORKSPACE/local.diff
   ```
   ```
   user_inputs.code_diff_file = "local.diff"
   ```

3. **用户说"帮我 review 并提 MR"**：
   - 同方式 2 生成 local.diff
   - 额外标记：Phase 3 步骤 #10、#11 自动执行（不在人工验证 gate #9 暂停）

更新 `workflow_state.json`：步骤 #4 标记 `completed`

### 2.1 并行执行验证步骤

对 `parallel_group: "verify"` 的步骤，在**同一条消息**中发送多个 Skill 调用：

```
Skill(skill: "test:change-analysis", args: "code_changes=<...> story_link=<...>")
```

如 `has_design_link == true`：
```
Skill(skill: "test:ui-fidelity-check", args: "design_link=<...>")
```

> 注意：这些 Skill 调用应在**同一条消息**中发出以实现并行。如果工具不支持并行 Skill 调用，则按顺序执行。

完成后更新对应步骤为 `completed`。

### 2.2 API 契约校验（条件执行）

仅当 `coordination_needed == true` 时执行：

```
Skill(skill: "test:api-contract-validation", args: "...")
```

### 2.3 需求回溯（含 MS 测试计划回写）

```
Skill(skill: "test:requirement-traceability", args: "code_changes=<...> story_link=<...> final_cases=$TEST_WORKSPACE/final_cases.json plan_name=<derived_params.plan_name>")
```

此步骤包含两部分（详见 requirement-traceability/PHASES.md）：

1. **正向用例中介验证**：消费上游 `final_cases.json`（来自步骤 #2 test-case-generation），对每条用例执行代码路径追踪，输出 `forward_verification.json`
2. **Phase 6 writeback**：标准模式下自动调用 metersphere-sync execute，把 `forward_verification.json` 落到 MS 用例状态，输出 `ms_sync_report.json`

完成后：
1. Read `$TEST_WORKSPACE/ms_sync_report.json`
2. 提取 `auto_passed`、`manual_required` 用于 2.4 摘要

### 2.4 暂停 — 等待人工验证

输出摘要给用户：

```
## QA Phase 2 完成

- 变更分析：发现 N 个影响点，补充了 M 条用例
- 需求还原度：X%
- UI 还原度：Y（仅有设计稿时显示）
- API 契约一致性：Z（仅前后端协调时显示）
- MS 执行结果：P 条自动通过，Q 条需人工验证

### 需人工验证的用例
请在 MeterSphere 测试计划中验证以下用例：[计划链接](plan_url)
（状态为 Prepare 的用例需要人工执行）

### 下一步
验证完成后回来，说"验证完了"继续。
```

更新 `workflow_state.json`：
- `current_phase = 3`
- 步骤 #9 (user_gate) 设为 `waiting`

> 如果 2.0 中用户选择了"帮我 review 并提 MR"，则跳过此暂停，直接进入 Phase 3。

---

## 阶段 3: 收尾

### 3.1 代码审查

```
Skill(skill: "git:code-reviewing", args: "review current branch changes")
```

### 3.2 提 PR（可选）

仅当以下条件之一满足时执行：
- 用户在 Phase 2 入口选择了"帮我 review 并提 MR"
- 用户在 Phase 3 明确要求提 PR

```
Skill(skill: "git:commit-push-pr", args: "...")
```

### 3.3 生成 QA 摘要报告

汇总所有阶段的产出，生成 `$TEST_WORKSPACE/qa_summary.md`：

```markdown
# QA 摘要：{story_name}

## 需求分析
- 功能点：N 个
- 平台范围：iOS, Android, Server
- 前后端协调：是/否

## 测试用例
- 生成：M 条（P0: x, P1: y, P2: z）
- 补充（变更分析）：K 条
- 总计：M+K 条

## MeterSphere
- 测试计划：[{plan_name}](plan_url)
- 自动通过：P 条
- 人工验证：Q 条

## 需求还原度
- 覆盖率：X%
- 正向验证率：Y%

## 代码审查
- 审查结果：通过/N 个问题

## 执行步骤
| # | 步骤 | 状态 | 耗时 |
|---|------|------|------|
| 1 | requirement-clarification | ✅ completed | ... |
| 2 | test-case-generation | ✅ completed | ... |
| ... |
```

### 3.4 标记工作流完成

更新 `workflow_state.json`：所有步骤标记最终状态，`current_phase = "done"`。

---

## 错误处理

### Skill 执行失败

1. 标记该步骤为 `failed`，记录错误信息到 `steps[].error`
2. 输出错误摘要给用户
3. 提供选项：
   - **重试**：重新执行失败的步骤
   - **跳过**：标记为 `skipped`，继续下一步
   - **中止**：暂停工作流，用户手动处理后 `--resume`

### 状态文件异常

1. `workflow_state.json` 不存在或 JSON 格式损坏 → 扫描 `$TEST_WORKSPACE` 中的产物文件，重建状态
2. 步骤产出了空文件或无效内容 → 标记 `failed` 并提示用户
3. `pipeline` 参数值无效 → 回退到 `qa-full`

### 中断恢复

编排器被中断后重新调用时：
1. 读取 `workflow_state.json`
2. 检查最后一个 `in_progress` 步骤的输出文件是否已生成
   - 已生成 → 标记 `completed`，继续下一步
   - 未生成 → 重新执行该步骤
3. 从中断点继续
