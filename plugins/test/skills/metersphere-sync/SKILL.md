---
name: metersphere-sync
description: >
  将 AI 生成的测试用例同步到 MeterSphere：创建模块、导入用例、创建测试计划、关联用例。
  可选执行验证结果回写（高置信度用例自动标记通过）。
  触发：同步到 MS、导入 MeterSphere、创建测试计划、MS 同步、执行回写。
---

# MeterSphere 用例同步

## Quick Start

- Skill 类型：集成同步
- 适用场景：将 AI 生成的测试用例导入 MeterSphere 平台，创建测试计划并关联用例；可选在需求还原度检查后自动回写执行结果
- 必要输入：`final_cases.json` 或 任一补充用例文件（`change_supplementary_cases.json` / `review_supplementary_cases.json` / 旧版 `supplementary_cases.json`，至少一个）+ `plan_name`
- 输出产物：`ms_sync_report.json`（必须）、`ms_case_mapping.json`、`ms_plan_info.json`
- 失败门控：MS 连通性检查失败时停止；pycryptodome 未安装时停止
- 执行步骤：`init → import → plan → execute(可选) → output`

## 核心能力

- 用例导入 — 按 module 字段自动创建子模块，批量导入用例，标签由 `--tags` 参数指定（默认 `AI 用例生成`）
- 测试计划管理 — 按需求名查找或创建测试计划（限定在 AI 工作流分类下），关联导入的用例
- 计划幂等 — 同名计划存在时追加用例，不存在时新建
- 验证回写 — 基于 forward_verification.json（requirement-traceability 产出）的置信度和结果，自动标记高置信度 Pass/Failure 用例
- 冒烟测试联动 — 消费 smoke_test_report.json（requirement-traceability 产出），P0 缺陷时全量降级为 Prepare
- 人工标记 — 置信度不足的用例保持待执行状态，添加评论注明原因

## 两种执行模式

### mode=sync（默认）
导入用例 + 创建/复用测试计划 + 关联用例。适用于测试用例生成完成后的首次同步。

### mode=execute
在 sync 的基础上，增加验证结果回写。需要额外输入 `forward_verification.json`（requirement-traceability 产出），可选输入 `smoke_test_report.json`。
适用于需求还原度检查完成后，将 AI 验证结果写回 MS 测试计划。当冒烟测试发现 P0 缺陷时，自动将所有用例降级为待人工验证。

## 工具调用

所有 MS 操作通过 `metersphere_helper.py` 脚本执行：

```bash
HELPER="$SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py"

# 连通性检查
python3 $HELPER ping

# 导入用例（自动按 module 分组创建子模块，--requirement 指定需求名作为父模块）
python3 $HELPER import-cases <parent_module_id> <cases.json> \
  [--requirement <需求名>] [--tags 'AI 变更分析'] [--mapping-out PATH]

# 列出测试计划阶段选项（如 smoke / new_feature_test / regression_test 等）
python3 $HELPER list-stages

# 查找或创建测试计划
python3 $HELPER find-or-create-plan <plan_name> [--stage smoke]

# 关联用例到计划
python3 $HELPER add-cases-to-plan <plan_id> --case-ids id1,id2,...

# 更新用例执行结果（单条）
python3 $HELPER update-case-result <plan_case_id> <Pass|Failure|Prepare> \
  [--actual-result TEXT] [--comment TEXT]

# 一站式回写（execute 模式推荐用这个，含 P6 状态映射 + 幂等比对 + 报告生成）
python3 $HELPER writeback-from-fv --plan-id <id> --fv-path <fv.json> \
  [--mapping-path PATH] [--report-path PATH] [--dry-run]

# fv schema 校验（execute 模式 precondition）
python3 $HELPER validate-fv <fv.json> [--repo-root PATH]

# 三级查找：case_id → ms_id → plan_case_id
python3 $HELPER lookup-plan-case --plan-id <id> --case-id <local_id> \
  [--mapping-path PATH]

# mapping 与 cases 一致性比对（mapping miss / 过期时用）
python3 $HELPER refresh-mapping --mapping-path PATH --cases-path final_cases.json \
  [--diff-only|--apply]

# 从 MS plan 反向重建 mapping（切换 plan 或重 import 后用）
python3 $HELPER rebuild-mapping --plan-id <id> --cases-path final_cases.json \
  [--mapping-out PATH]
```

### Helper Commands 响应表（统一约定）

所有 helper 命令遵循 unix exit code 约定：

```
exit 0 → 成功，stdout 是裸 JSON（每个命令各自语义）
exit 1 → 运行时失败，stderr 是 JSON {type, message, retriable, ...extra}
exit 2 → 入参/校验非法，stderr 同上
```

错误 type 取值：

| type | 含义 | 是否 retriable |
| --- | --- | --- |
| `validation` | 入参/数据 schema 不合法 | false |
| `api_error` | MS API 业务错或 4xx/5xx | 5xx=true / 其他=false |
| `network` | DNS / 连接 / 超时 | true |
| `not_found` | 资源（mapping、case、plan）找不到 | false |
| `precondition_failed` | 前置文件/依赖缺失 | false |
| `stale_mapping` | mapping.sha256 与 cases 不一致 | false |
| `ambiguous` | 匹配歧义（同模块重名等） | false |
| `dependency_missing` | Python 包缺失（pycryptodome / jsonschema） | false |

每个命令的 stdout 形状：

| 命令 | stdout (成功时) |
| --- | --- |
| `ping` | `{status, base_url, project_id, module_count}` |
| `list-modules` | `[{id, name, case_count, children}, ...]` |
| `ensure-module` | `{id, name, parent_id, is_new}` |
| `import-cases` | `{imported, failed, modules_created, mapping_path, metersphere_url, failed_details}` |
| `list-stages` | `[{value, label}, ...]`（测试计划 stage 选项，供 find-or-create-plan 的 --stage 参数选值） |
| `find-or-create-plan` | `{plan_id, plan_name, plan_url, is_new, status}` |
| `add-cases-to-plan` | `{plan_id, added_count}` |
| `list-plan-cases` | `{plan_id, total, cases: [{id, case_id, name, status, priority, executor, node_path}, ...]}` |
| `update-case-result` | `{plan_case_id, status, result}`（**注意：无 ok 字段**，按 exit code 判断） |
| `batch-update-results` | `{plan_id, total, success, failed, failed_details}` |
| `validate-fv` | `{valid: true, count, file}` |
| `lookup-plan-case` | `{case_id, ms_id, plan_case_id, match_method, title}` |
| `refresh-mapping` | `{missing_in_mapping, stale_in_mapping, extra_in_ms}`；非空时 exit 1 |
| `rebuild-mapping` | `{mapping_path, total_in_plan, matched, unmatched_in_plan, unmatched_local, ambiguous_titles}`；ambiguous 非空时 exit 1 |
| `writeback-from-fv` | `{plan_id, fv_path, ran_at, summary, updated, unchanged, failed}` |

## 环境变量

脚本内置默认值，零配置即可使用。环境变量存在时覆盖默认值：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MS_BASE_URL` | MeterSphere 地址 | `https://metersphere.tapsvc.com` |
| `MS_ACCESS_KEY` | API 认证 key | 已内置 |
| `MS_SECRET_KEY` | AES 签名 key | 已内置 |
| `MS_PROJECT_ID` | 项目 UUID | 已内置 |
| `MS_DEFAULT_NODE_ID` | 用例库父模块 ID | AI 工作流模块 |
| `MS_PLAN_NODE_ID` | 测试计划分类节点 ID | AI 工作流分类 |

## P6 状态映射（execute 模式）

writeback-from-fv 内部按下面规则把 fv 写回 MS plan：

| AI 判定（fv） | external_dependencies.types | MS target | comment 模板 |
|---|---|---|---|
| `pass` | 空 | **Pass** | `AI 静态验证通过 (conf={c})` |
| `pass` | 非空 | **Prepare** | `AI 静态验证通过 (conf={c})，待人工验证: {types_csv}` |
| `fail` | — | **Failure** | `AI 判定不通过 (conf={c}) — evidence: {first_loc} — 失败原因: {actual_brief}` |
| `inconclusive` | — | **Prepare** | `AI 无法判定 — 原因: {inconclusive_reason}` |

> **关键变更（vs v0.0.15）**：旧版本基于 `confidence_threshold`（默认 90）判定 Pass/Failure/Prepare。v0.0.16 起不再用阈值——pass + ext_deps 非空时**直接降级为 Prepare**（不是「Pass + caveat 评论」），保证 MS Pass 语义不掺水。conf 仅作为 schema 校验门槛（pass 必须 conf≥70）和 comment 显示。v0.0.17 起 `confidence_threshold` 字段从 contract.yaml 删除（之前作为 deprecated 占位）。

被降级为 Prepare 的条目通过 `pass_with_caveats.md` + `pending_external_validation.md` 单独汇总，给 QA 做回归清单。

## 详细阶段操作

详见 [PHASES.md](PHASES.md)。

## Closing Checklist（CRITICAL）

skill 执行的最终阶段完成后，**必须**逐一验证以下产出文件：

**sync 模式：**
- [ ] `ms_case_mapping.json` — v2 格式（顶层 `{generated_at, source_cases_file.sha256, ms_project_id, entries}`）
- [ ] `ms_plan_info.json` — 非空，包含 plan_id 和 plan_url
- [ ] `ms_import_report.json` — import 阶段汇总（与 writeback 的 `ms_sync_report.json` 不同名，永不撞）

**execute 模式额外产出（writeback-from-fv 自动落盘）：**
- [ ] `ms_sync_report.json` — 含 `summary.by_target_status: {Pass, Prepare, Failure}` + `updated/unchanged/failed` 明细
- [ ] `forward_verification.enriched.json` — 原 fv + 每条注入 ms_id（下次跑可跳过 lookup）
- [ ] `pass_with_caveats.md` — 即使无 caveat 条目也要落盘
- [ ] `pending_external_validation.md` — 同上

全部必须项通过后，输出完成总结。如文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。
