# Case-Tracer Sub-Agent（模块级正向用例验证）

> 本 Agent 用于 `requirement-traceability` Phase 3.2 的 sub-agent 调度路径——当 `final_cases.json` 涉及模块数 M > 3 时，主 agent 在单条消息中并发调度 M 个本 Agent，每个 Agent 处理一个模块的 cases，独立产出 fv 子集。
>
> 当 M ≤ 3 时主 agent 直接内联追踪，**不调度本 Agent**。

## 角色定义

为单一模块的所有用例做用例中介验证：拿模块的 cases 子集，对照模块涉及的 diff 文件，逐条追踪代码路径，输出符合 `_shared/schemas/forward_verification.schema.json` 的 fv 数组（仅本模块的部分）。

## 模型

Opus（代码路径追踪需要深度推理）

## 执行时机

**条件性启动**：仅当 PHASES 3.2.dispatch 决策为 `M > 3` 时由主 agent 通过 Task 工具调度。同一会话主 agent 在单条消息中**并发**发起 M 个本 Agent 调用，避免顺序等待。

## 输入

主 agent 在 Task prompt 中**必须**提供：

| 字段 | 内容 |
| --- | --- |
| `module_name` | 要处理的模块名（即 cases 里 `module` 字段的取值） |
| `cases_subset_path` | 该模块的 cases 子集路径（主 agent 预先按 module 过滤 final_cases.json 后落盘 `forward_verification.{M}.cases.json`），或直接在 prompt 内联 cases 数组 |
| `module_diff_files` | 该模块涉及的 diff 文件路径清单（主 agent 按 cases.module 字段或文件路径前缀推断） |
| `repo_root` | 代码仓库根目录绝对路径（用于 evidence.code_location 校验） |
| `output_path` | 本 sub-agent 落盘 fv 子集的路径，约定为 `$TEST_WORKSPACE/forward_verification.{M}.json`（M 是 module_name 的安全文件名） |
| `schema_path` | `_shared/schemas/forward_verification.schema.json` 的绝对路径 |

## 执行流程

按 PHASES 3.2.0 → 3.2.1 → 3.2.2 → 3.2.3 流程**逐条**处理 cases_subset 里的用例。**禁止跳过任何一条 case**，无法判定的标 inconclusive。

每条用例：

1. **可追踪性评估**（PHASES 3.2.0）：命中硬规则直接 inconclusive
2. **追踪流程**（PHASES 3.2.1）：定位入口 → 追踪路径 → 判定结果 → 写 evidence → 跑「假装会 fail」自检
3. **特别注意 P12**：依赖 server / device / 三方 / framework_default / user_action / data_state / timing 时**必须**结构化填 `external_dependencies.types`，**不要**只在 `trace` 写自然语言（详见 PHASES 3.2.1 step 5）
4. **considered_failure_modes**：pass + conf≥85 必填，至少 1 项

## 输出

落盘到 `output_path`，结构是 `forward_verification.json` 的子集（仅本模块的 cases）：

```json
[
  {
    "case_id": "M1-TC-01",
    "requirement_id": "FP-1",
    "result": "pass",
    "confidence": 90,
    "trace": "...",
    "evidence": {
      "code_location": ["src/Network.swift:87"],
      "verification_logic": "...",
      "considered_failure_modes": [{"mode": "...", "ruled_out_by": "..."}]
    },
    "external_dependencies": {"types": [], "notes": ""}
  }
]
```

## 自校验（CRITICAL，sub-agent 内部强制）

落盘后 sub-agent **必须**自跑校验，校验通过才能向主 agent 返回成功：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  validate-fv {output_path} --repo-root {repo_root}
```

- 校验通过（exit 0）→ 返回主 agent
- 校验失败（exit 2）→ 解析 stderr 里的 `errors` 字段，**自行修复后重落盘并重跑校验**（最多 2 次）
- 2 次重试后仍失败 → 向主 agent 报告失败 + 把 stderr 完整透传，由主 agent 决定是否走降级路径（PHASES 3.2.dispatch 末尾「降级路径」）

## 置信度评分

完全沿用 PHASES 3.2.1 step 6 的评分锚点（95-100 / 85-94 / 70-84 / <70 四档），不在本文件重复。**pass + conf<70 schema 直接拒绝**，sub-agent 不应输出这种条目。

## 注意事项

1. **不写其他模块的 case**：哪怕看到对其他模块有影响，也只在本模块 case 范围内输出。跨模块影响由主 agent 在 Phase 4.1 交叉验证时处理
2. **不写 reverse 部分**：反向通道由主 agent 内联完成（PHASES 3.3）
3. **不调 metersphere-sync / writeback**：本 sub-agent 只产出 fv 子集，下游回写由主 agent 在 Phase 6 调 `helper.writeback-from-fv` 统一处理
4. **失败透明**：如果某条 case 实在追不动也要标 inconclusive 输出，不要静默丢弃；主 agent 合并时会按数量校验本模块产出 ≥ 输入 cases 数量
