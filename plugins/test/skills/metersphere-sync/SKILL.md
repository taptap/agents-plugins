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
- 输出产物：sync 模式产出 `ms_case_mapping.json`、`ms_plan_info.json`、`ms_import_report.json`；execute 模式在已有 mapping/plan_info 基础上额外产出 `ms_sync_report.json`、`forward_verification.enriched.json`、`pass_with_caveats.md`、`pending_external_validation.md`
- 失败门控：MS 连通性检查失败时停止；pycryptodome 未安装时停止
- 执行步骤：`init → import → plan → execute(可选) → output`

## 公共需求工作区（CRITICAL）

本 skill 不拥有独立工作区。它必须挂载到调用方的 `requirement_<stable_id>/` 工作区中，保证用例、mapping、plan、回写结果能被 requirement-traceability 继续消费。

### 工作区解析顺序

1. 用户显式传入的 workspace / output_dir。
2. `final_cases.json` 所在路径：
   - 若路径形如 `requirement_<id>/test_cases/final_cases.json`，工作区为 `requirement_<id>/`。
   - 旧版路径可兼容读取，但新产物必须写回公共工作区。
3. 当前目录或父目录中的 `manifest.json`。
4. 仍找不到时，才创建 `requirement_<stable_id>/` 并在最终输出说明。

### 产物落点

- `mode=sync`：所有 MS 同步产物写入 `metersphere/`：
  - `ms_case_mapping.json`
  - `ms_plan_info.json`
  - `ms_import_report.json`
- `mode=execute`：以 `forward_verification.json` 所在目录为准写回执行产物。通常应是 `traceability/<change_set_slug>/`：
  - `ms_sync_report.json`
  - `forward_verification.enriched.json`
  - `pass_with_caveats.md`
  - `pending_external_validation.md`
- sync 完成后必须更新根目录 `manifest.json.current_stage = "metersphere"`，并在 `manifest.json.artifacts` 记录 `ms_case_mapping_path`、`ms_plan_info_path`、`ms_import_report_path`、`ms_plan_url`。

## 核心能力

- 用例导入 — 按 module 字段自动创建子模块，批量导入用例，标签由 `--tags` 参数指定（默认 `AI 用例生成`）
- 测试计划管理 — 按需求名查找或创建测试计划（限定在 AI 工作流分类下），关联导入的用例
- 计划幂等 — 同名计划存在时追加用例，不存在时新建
- 用户可达入口 — sync 模式完成后必须在最终回复中直接展示 `ms_plan_info.json.plan_url`
- 验证回写 — 基于 forward_verification.json（requirement-traceability 产出）的置信度和结果，自动标记高置信度 Pass/Failure 用例
- 冒烟测试边界 — smoke-test 模式只产出报告，不由本 skill 直接消费 smoke_test_report.json 写回 MS
- 人工标记 — 置信度不足的用例保持待执行状态，添加评论注明原因

## 两种执行模式

### mode=sync（默认）
导入用例 + 创建/复用测试计划 + 关联用例。适用于测试用例生成完成后的首次同步。

### mode=execute
在已完成 sync 的基础上，增加验证结果回写。需要额外输入 `traceability/<change_set_slug>/forward_verification.json`（requirement-traceability 产出），并复用同一工作区 `metersphere/ms_case_mapping.json` / `metersphere/ms_plan_info.json`。
适用于需求还原度检查完成后，将 AI 验证结果写回 MS 测试计划。

## 工具调用

所有 MS 操作通过 `metersphere_helper.py` 脚本执行：

```bash
HELPER="$SKILLS_ROOT/test-shared-tools/scripts/metersphere_helper.py"

# 连通性检查
python3 $HELPER ping

# 导入用例（自动按 module 分组创建子模块，--requirement 指定需求名作为父模块）
python3 $HELPER import-cases <parent_module_id> <cases.json> \
  [--requirement <需求名>] [--tags 'AI 变更分析'] [--mapping-out PATH] [--report-out PATH]

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
python3 $HELPER refresh-mapping --mapping-path PATH --cases-path $TEST_WORKSPACE/test_cases/final_cases.json \
  [--diff-only|--apply]

# 从 MS plan 反向重建 mapping（切换 plan 或重 import 后用）
python3 $HELPER rebuild-mapping --plan-id <id> --cases-path $TEST_WORKSPACE/test_cases/final_cases.json \
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

脚本从 `plugins/test/skills/test-shared-tools/scripts/.env` 读取配置。不用提前手动配——首次使用时如果 `.env` 没配齐，脚本会报 `missing required environment variables`，把飞书 [MeterSphere 配置 (.env)](https://xd.feishu.cn/wiki/K4Cxw8HE5itR16kFFYicSctAnrc) 里的配置块整段粘给 AI，让它写入 `.env` 即可。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MS_ACCESS_KEY` | API 认证 key | 无（必填，调用 MS API 子命令时报错；`validate-fv` 等纯本地命令豁免） |
| `MS_SECRET_KEY` | AES 签名 key | 无（必填，调用 MS API 子命令时报错；`validate-fv` 等纯本地命令豁免） |
| `MS_BASE_URL` | MeterSphere 地址 | 无（运行时报错，建议填 `https://metersphere.tapsvc.com`） |
| `MS_PROJECT_ID` | 项目 UUID | 无（运行时报错） |
| `MS_WORKSPACE_ID` | 工作空间 UUID | 无（创建测试计划时必需） |
| `MS_DEFAULT_NODE_ID` | 用例库父模块 ID | 无（导入用例时必需） |
| `MS_PLAN_NODE_ID` | 测试计划分类节点 ID | 无（创建计划时必需） |
| `MS_FIELD_ID_MAINTAINER` / `_PRIORITY` / `_STATUS` / `_AUTOMATED` | 自定义字段 ID（4 个） | 无（写入用例时必需） |
| `MS_DEFAULT_MAINTAINER` | 默认负责人 | `admin` |
| `MS_DEFAULT_STAGE` | 默认测试计划阶段 | `smoke` |

## P6 状态映射（execute 模式）

writeback-from-fv 内部按下面规则把 fv 写回 MS plan：

| AI 判定（fv） | external_dependencies.types | MS target | comment 模板 |
|---|---|---|---|
| `pass` | 空 | **Pass** | `AI 静态验证通过 (conf={c})` |
| `pass` | 非空 | **Prepare** | `AI 静态验证通过 (conf={c})，待人工验证: {types_csv}` |
| `fail` | — | **Failure** | `AI 判定不通过 (conf={c}) — evidence: {first_loc} — 失败原因: {actual_brief}` |
| `inconclusive` | — | **Prepare** | `AI 无法判定 — 原因: {inconclusive_reason}` |

> **设计原则**：pass + ext_deps 非空时**直接降级为 Prepare**（不是「Pass + caveat 评论」），保证 MS Pass 语义不掺水。conf 不作为状态判定阈值，仅作为 schema 校验门槛（pass 必须 conf≥70）和 comment 显示。

被降级为 Prepare 的条目通过 `pass_with_caveats.md` + `pending_external_validation.md` 单独汇总，给 QA 做回归清单。

## 详细阶段操作

详见 [PHASES.md](PHASES.md)。

## Closing Checklist（CRITICAL）

skill 执行的最终阶段完成后，**必须**逐一验证以下产出文件：

**sync 模式：**
- [ ] `ms_case_mapping.json` — v2 格式（顶层 `{generated_at, source_cases_file.sha256, ms_project_id, entries}`）
- [ ] `ms_plan_info.json` — 非空，包含 plan_id 和 plan_url
- [ ] `ms_import_report.json` — import 阶段汇总（与 writeback 的 `ms_sync_report.json` 不同名，永不撞）
- [ ] 最终回复 — 必须直接展示测试计划链接 `ms_plan_info.json.plan_url`、成功/失败导入数、已关联用例数

**execute 模式额外产出（writeback-from-fv 自动落盘）：**
- [ ] `ms_sync_report.json` — 含 `summary.by_target_status: {Pass, Prepare, Failure}` + `updated/unchanged/failed` 明细
- [ ] `forward_verification.enriched.json` — 原 fv + 每条注入 ms_id（下次跑可跳过 lookup）
- [ ] `pass_with_caveats.md` — 即使无 caveat 条目也要落盘
- [ ] `pending_external_validation.md` — 同上

全部必须项通过后，输出完成总结。如文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../commons/CONVENTIONS.md#阶段执行保障)。
