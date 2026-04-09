---
name: qa-workflow
description: >
  QA 工作流编排器。用户提供需求链接，自动编排需求澄清→用例生成→MS同步→
  变更分析→需求还原度→执行回写→代码审查的完整 QA 流程。
  触发：QA 工作流、帮我做 QA、完整测试流程、端到端 QA、qa-workflow。
---

# QA 工作流编排器

## Quick Start

- Skill 类型：工作流编排
- 适用场景：用户说"帮我做 XX 功能的 QA"，自动编排全流程 skills
- 必要输入：需求链接（`story_link`）、本地需求文档（`requirement_doc`）或需求文字说明（`requirement_text`），三选一
- 输出产物：`workflow_state.json`（进度追踪）、`qa_summary.md`（最终报告）
- 失败门控：需求输入为空时停止；子 skill 失败时记录错误并继续后续步骤，不中断整体工作流
- 执行步骤：`init → Phase 1(需求+用例) → [等编码] → Phase 2(验证) → [等人工] → Phase 3(收尾)`

## 核心能力

- **自动编排** — 按正确顺序调用 test 插件的各 skill，处理参数传递和数据流
- **条件分支** — 根据需求特征自动判断是否需要 UI 还原度检查、API 契约校验
- **并行执行** — change-analysis、verification-test-generation、ui-fidelity-check（有设计稿时）并行执行
- **状态持久化** — `workflow_state.json` 记录进度，支持中断恢复
- **多种代码变更来源** — MR/PR 链接、本地 git diff、用户指定代码目录
- **工作流模板** — qa-full（完整）、qa-lite（无 MS）、verify-only（仅验证）

## 工作流全景

```
Phase 1: 需求分析与用例准备（自动执行）
  #1  requirement-clarification → 澄清需求
  #2  test-case-generation (confirm_policy=accept_all) → 生成用例
  #3  metersphere-sync(sync) → 导入 MS + 建测试计划
  #4  [等待] 用户编码 → 暂停，输出计划链接

Phase 2: 代码验证（用户回来后自动执行）
  触发：用户提供 MR 链接 / 说"代码写完了" / 说"帮我 review 并提 MR"
  #5  change-analysis ─────────────┐
  #6  verification-test-generation ┤ 并行
  #7  [条件] ui-fidelity-check ────┘ 有设计稿时
  #8  [条件] api-contract-validation  前后端协调时
  #9  requirement-traceability → 需求还原度
  #10 metersphere-sync(execute) → 回写执行结果
  #11 [等待] 人工验证低置信度用例

Phase 3: 收尾（人工验证后）
  #12 git:code-reviewing → 代码审查
  #13 git:commit-push-pr → 提 PR（可选）
  → 生成 qa_summary.md
```

> 步骤编号与 [WORKFLOW_DEFS.md](WORKFLOW_DEFS.md) 的 qa-full 模板 ID 一致。#4 和 #11 为用户交互等待点。

## 条件分支判定

从 `clarified_requirements.json` 提取信号：

| 信号 | 来源字段 | 触发步骤 |
|------|----------|----------|
| 有设计稿 | 用户提供 `design_link` | #7 ui-fidelity-check |
| 前后端协调 | `platform_scope.coordination_needed == true` | #8 api-contract-validation |

## 代码变更来源

Phase 2 的入口支持三种方式：

| 用户信号 | 编排器行为 |
|----------|-----------|
| 提供 MR/PR 链接 | `code_changes = [URL]`，传给 change-analysis 和 requirement-traceability |
| "代码写完了"（无 MR） | 自动执行 `git diff` 生成 local.diff 作为 `code_diff` |
| "帮我 review 并提 MR" | 同上 + Phase 3 自动执行（不暂停等人工验证） |

## 工作流模板

| 模板 | 说明 | 跳过的步骤 |
|------|------|-----------|
| `qa-full` | 完整流程（默认） | 无 |
| `qa-lite` | 跳过 MS 同步和 MS 执行回写 | #3, #10, #11（无 MS 则无需人工验证 gate） |
| `verify-only` | 仅验证已有代码 | #1, #2, #3, #10（直接从 Phase 2 开始，无 MS） |

## 参数自动推导

| 参数 | 推导来源 | 逻辑 |
|------|----------|------|
| `plan_name` | `clarified_requirements.json` | 提取 story 标题 |
| `has_design_link` | 用户输入 | `design_link` 非空 |
| `coordination_needed` | `clarified_requirements.json` | `platform_scope.coordination_needed` |
| `code_changes` | Phase 2 用户输入 | MR/PR URL 或自动 git diff |

## 状态文件

`workflow_state.json` 记录工作流进度、参数和用户输入。详见 [PHASES.md](PHASES.md)。

关键字段：
- `current_phase`: 当前阶段 (1/2/3)
- `steps[].status`: pending / in_progress / completed / skipped / waiting / failed
- `derived_params`: 从上游输出自动推导的参数
- `user_inputs`: 用户在 gate 节点提供的输入（如 code_changes）

## 详细阶段操作

详见 [PHASES.md](PHASES.md)。

## 工作流模板定义

详见 [WORKFLOW_DEFS.md](WORKFLOW_DEFS.md)。
