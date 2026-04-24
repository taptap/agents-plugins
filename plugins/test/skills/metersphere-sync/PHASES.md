# MeterSphere 同步各阶段详细操作指南

## 阶段 1: init - 环境检查与输入路由

### 1.0 环境检查

1. 检查 `pycryptodome` 是否可用：`python3 -c "from Crypto.Cipher import AES"`
   - 不可用 → 提示用户 `pip install pycryptodome`，**停止**
2. 执行连通性检查：
   ```bash
   python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py ping
   ```
   - 返回 `status: ok` → 继续
   - 失败 → **停止**，输出错误信息（helper 失败 stderr 已是结构化 JSON，参见 SKILL.md「Helper Commands」节）

### 1.1 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#上游输入消费) 定义的优先级确认输入：

1. 工作目录中存在 `final_cases.json` → 作为主输入
2. 工作目录中存在 `supplementary_cases.json` → 作为主输入
3. 以上均不存在 → **停止**

### 1.2 确定执行模式

- 用户指定 `mode=execute` 且工作目录中存在 `forward_verification.json` → execute 模式
- 否则 → sync 模式

### 1.3 确定参数

- `parent_module_id`：优先使用参数值，否则读取 `MS_DEFAULT_NODE_ID` 环境变量
- `plan_name`：优先使用参数值，否则询问用户提供需求名称

> **已废弃**：`confidence_threshold`（默认 90）。当前 P6 状态映射不再用阈值——pass + ext_deps 非空时直接降级为 Prepare（详见 SKILL.md「P6 状态映射」）。如果传入了这个参数，会被 writeback-from-fv 忽略。

### 1.4 Precondition 校验（CRITICAL，必须执行）

按 mode 走对应表，**任一项不满足直接 stop，输出明确错误信息**。下游 Phase 4 的兜底逻辑只是 last-resort 救命，不应承担 precondition 缺失的责任。

| mode | precondition |
| --- | --- |
| sync | `final_cases.json` 存在；schema 合法（顶层 array、每条满足 plugins/test/CONVENTIONS.md#用例-json-格式）；同 `(module, title)` 不重名 |
| execute | `forward_verification.json` 存在；通过 `validate-fv`；`ms_case_mapping.json` 存在；mapping 的 `source_cases_file.sha256` 与当前 `final_cases.json` 一致 |

execute 模式校验示例：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  validate-fv $TEST_WORKSPACE/forward_verification.json
# 失败 → exit 2 + stderr {type: validation, errors: [...]}
```

mapping 不存在或 sha 不匹配 → 提示用户先跑 `refresh-mapping`，**不要**自动重 import。

---

## 阶段 2: import - 创建模块与导入用例

### 2.1 导入用例

调用 `import-cases` 一次性完成模块创建、用例导入、**mapping 文件落盘**：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  import-cases <parent_module_id> <cases_file> \
  [--requirement <需求名>] [--tags 'AI 变更分析'] [--mapping-out PATH]
```

- `--requirement`（推荐）：指定需求名称，会先在 `parent_module_id` 下创建需求级父模块，子模块再挂在其下。结构为：`父模块 / 需求名 / 子模块A, 子模块B...`
- `--mapping-out`：mapping 落盘路径，默认 `<cases_file 同目录>/ms_case_mapping.json`
- 不指定 `--requirement` 时，子模块直接挂在 `parent_module_id` 下

该命令自动：
- 按用例的 `module` 字段分组
- 为每个 module 创建子模块（已存在则复用），支持 `/` 分隔的多层路径
- **同模块内重名校验**：同 `(module, title)` ≥2 条 → 直接 fail（exit 2），让用例生成阶段消歧。不再做静默 `_2` 后缀
- 逐条并发导入用例，标签由 `--tags` 参数指定（默认 `AI 用例生成`）
- 格式转换（后端自动完成，AI 无需手动转换）：`{action, expected}` → `{num, desc, result}`
- 名称清洗：去除内部标记（AC-1, RP-3）、截断超长名称（250 字）

> **P12 命名冲突防御**：`import-cases` 还会同时落盘 `ms_import_report.json`（与 mapping 同目录）作为 import 阶段的持久化汇总，**与 writeback 阶段的 `ms_sync_report.json` 是不同文件，永不撞名**。下游消费方按需读：sync 阶段看 `ms_import_report.json`，execute 阶段看 `ms_sync_report.json`。

### 2.2 mapping 文件（v2 格式，由 import-cases 直接落盘）

> **注意**：v2 格式由脚本自动写入，**不要再用 stdout 重定向手工保存**。stdout 现在只输出 summary。

```json
{
  "generated_at": "2026-04-23T12:34:56Z",
  "source_cases_file": {
    "path": "/abs/path/to/final_cases.json",
    "sha256": "abc123..."
  },
  "ms_project_id": "...",
  "entries": [
    {
      "case_id": "M1-TC-01",
      "ms_id": "uuid-xxx",
      "title": "点击 more 按钮弹出菜单面板",
      "module": "登录模块",
      "module_path": "/AI 工作流/优惠券/登录模块",
      "import_status": "created"
    }
  ]
}
```

字段说明：
- `case_id`：v1 字段叫 `local_id`，v2 改名以与下游 fv 字段对齐；fv writeback 用此 ID 查 mapping
- `source_cases_file.sha256`：用于 `lookup-plan-case` 校验 mapping 与当前 cases 是否一致；不一致 → stale_mapping
- `entries[].module_path`：MS 模块完整路径，便于人工定位

**错误处理**（详见 [Recovery Cookbook](../../_shared/RECOVERY.md#6-r-icimport-cases-失败)）：

| 错误 | R-code |
| --- | --- |
| schema 校验失败 / 顶层非数组 | [R-IC-2](../../_shared/RECOVERY.md#r-ic-2--schema-校验失败) |
| 同模块重名 | [R-IC-1](../../_shared/RECOVERY.md#r-ic-1--同模块内重名) |
| MS API 单条失败 | 记进 `failed_details`，不中断（无需 R-code，正常行为）|

常见 schema 错误见 [CONVENTIONS.md#用例-json-格式](../../CONVENTIONS.md#用例-json-格式)。

### 2.3 mapping 维护命令

mapping 与 cases 漂移时（MS 端手工改 / cases 文件被局部更新）：

```bash
# 查看差异（不修改文件）
python3 $HELPER refresh-mapping --mapping-path PATH --cases-path final_cases.json

# 自动清理 stale 条目
python3 $HELPER refresh-mapping --mapping-path PATH --cases-path final_cases.json --apply
```

差异处理见 [R-RM-1（missing_in_mapping）](../../_shared/RECOVERY.md#r-rm-1--missing_in_mapping) / [R-RM-2（stale_in_mapping）](../../_shared/RECOVERY.md#r-rm-2--stale_in_mapping)。`extra_in_ms`（MS 端独立加的）永不动。

### 2.4 跨 plan 切换 / 重 import 后的 mapping 重建（P11 教训）

**触发场景**：

- 用户 reset workspace 后切到一个新 plan_id，旧 mapping 文件还在但 ms_id 都过期了
- 上游误删后重 import 了一份 cases，新 ms_id 与旧 mapping 不一致
- 上面两种 `refresh-mapping --apply` 救不了——它只清 stale 不重建 ms_id

**解决**：用 `rebuild-mapping` 反向从 MS plan 拉全部 plan_cases（含 case 的真实 ms_id 和 name），按 `name == cases.title` 匹配本地 cases 重建 mapping：

```bash
python3 $HELPER rebuild-mapping --plan-id <new_plan_id> --cases-path final_cases.json \
  [--mapping-out PATH]
```

**输出**（stdout）：

```json
{
  "mapping_path": "/abs/path/ms_case_mapping.json",
  "total_in_plan": 46,
  "matched": 46,
  "unmatched_in_plan": [],          // plan 里有但本地 cases 没匹配上的
  "unmatched_local": [],             // 本地 cases 但 plan 里没找到的（漏 import？）
  "ambiguous_titles": []             // title 撞了无法消歧的 case
}
```

**异常处理**（详见 [Recovery Cookbook](../../_shared/RECOVERY.md#4-r-rbrebuild-mapping-失败)）：

| 输出字段非空 | R-code |
| --- | --- |
| `ambiguous_titles` | [R-RB-1](../../_shared/RECOVERY.md#r-rb-1--ambiguous_titles) |
| `unmatched_local` | [R-RB-2](../../_shared/RECOVERY.md#r-rb-2--unmatched_localD6-修复小循环)（含修复诊断流程图）|
| `unmatched_in_plan` | [R-RB-3](../../_shared/RECOVERY.md#r-rb-3--unmatched_in_plan) |

---

## 阶段 3: plan - 查找或创建测试计划

### 3.1 查找或创建计划

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  find-or-create-plan "<plan_name>" --stage smoke
```

- 已存在同名计划（限定在 AI 工作流分类下）→ 复用，输出 `is_new: false`
- 不存在 → 创建新计划，输出 `is_new: true`

### 3.2 关联用例

从 `ms_case_mapping.json` 的 `entries[].ms_id` 提取所有 ms_id，关联到计划：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  add-cases-to-plan <plan_id> --case-ids <ms_id1>,<ms_id2>,...
```

> v1 mapping 用 `case_mapping[].ms_id`；v2 用 `entries[].ms_id`。如果你看到的是 v1 格式（含 `case_mapping` 顶层数组），重跑 mode=sync 让 import-cases 升级到 v2。

### 3.3 保存计划信息

将计划信息保存为 `ms_plan_info.json`：

```json
{
  "plan_id": "uuid-zzz",
  "plan_name": "优惠券功能",
  "plan_url": "https://metersphere.tapsvc.com/#/track/plan/view/uuid-zzz",
  "is_new": false,
  "associated_cases": 28
}
```

---

## 阶段 4: execute - 验证结果回写（仅 mode=execute）

此阶段仅在 `mode=execute` 时执行，需要 `forward_verification.json` 输入（来自 requirement-traceability，正向用例中介验证结果）。

> v0.0.7 起改接 `forward_verification.json` 替代旧 `verification_cases.json`——traceability 已经把"用例执行结果"作为自身产物输出，不再需要独立的 verification-test-generation 中间产物。

### 4.0 冒烟测试报告前置检查

读取 `smoke_test_report.json`（如存在）。若文件存在且 `verdict == "fail"`：

1. 提取 P0 缺陷摘要：`defect_summary.by_priority.P0` 数量 + `fail_reason`
2. **全量降级**：跳过正常 VC 判定逻辑（4.3-4.4），将计划中**所有用例**标记为 `Prepare`：
```bash
python3 $HELPER update-case-result <plan_case_id> Prepare \
  --comment "冒烟测试未通过（P0 缺陷 {N} 个：{fail_reason}），需人工验证"
```
3. 降级完成后直接跳到 4.5

若文件不存在或 `verdict == "pass"`，继续正常流程（4.1-4.4）。Pass 时将 `traceability_summary` 追加到回写评论中作为补充信息。

### 4.1 一站式回写（推荐路径）

execute 模式的全部回写工作通过一个命令完成：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  writeback-from-fv \
  --plan-id <plan_id> \
  --fv-path $TEST_WORKSPACE/forward_verification.json \
  [--mapping-path PATH] \
  [--report-path PATH] \
  [--dry-run]
```

`writeback-from-fv` 内部自动完成：
1. **fv schema 校验**（含 evidence、external_dependencies、code_location 文件存在性等所有规则）
2. **三级查找** `case_id (M1-TC-01) → ms_id → plan_case_id`
3. **P6 状态映射**（见 4.2）
4. **幂等比对**：当前 MS 状态 == target → skip
5. **重试**：retriable 错误（5xx / network）单次内自动重试 1 次
6. **三个产物**：`ms_sync_report.json`、`forward_verification.enriched.json`、`pass_with_caveats.md` + `pending_external_validation.md`

第一次跑或大改动后建议先 `--dry-run` 一遍。

### 4.2 三级查找的契约（mapping ↔ ms_id ↔ plan_case_id）

> 历史教训：旧版 PHASES 写「`forward_verification` 的 case_id 与 MS 计划用例的 case_id 直接相等」，**这是错的**——MS 内部的 `case_id` 是 UUID，跟我们的 `M1-TC-01` 完全不是同一个东西。

正确链路：

```
case_id (M1-TC-01)
   ↓ 查 ms_case_mapping.json (Phase 2 落盘的 v2 格式)
ms_id (UUID)
   ↓ 查 list-plan-cases 的 caseId 字段
plan_case_id (UUID, 用于 update-case-result)
```

由 `helper.py lookup-plan-case` 命令封装。`writeback-from-fv` 内部已调，不需要手工拼。

mapping 不存在或 sha 不匹配 → **stop**，输出 `{type: stale_mapping, hint: 跑 refresh-mapping}`。不要自动重 import。

### 4.3 P6 状态映射表（fv → MS target）

| AI 判定 | external_dependencies.types | MS target | comment 模板 |
| --- | --- | --- | --- |
| `pass` | 空 | **Pass** | `AI 静态验证通过 (conf={c})` |
| `pass` | 非空 | **Prepare** | `AI 静态验证通过 (conf={c})，待人工验证: {types_csv}` |
| `fail` | — | **Failure** | `AI 判定不通过 (conf={c}) — evidence: {first_loc} — 失败原因: {actual_brief}` |
| `inconclusive` | — | **Prepare** | `AI 无法判定 — 原因: {inconclusive_reason}` |

> **关键变更（vs 旧版本）**：pass 但需要外部验证（真机/server/三方等）→ **降级为 Prepare**，不是「Pass + caveat 评论」。
>
> 理由：MS 端的 Pass 语义是「已验证通过」。如果还需要回归才能确认，它就不算 Pass。把这种条目当 Pass 处理会让 QA 默认信任、漏掉回归。被降级为 Prepare 的条目通过 `pass_with_caveats.md` 单独汇总，QA 直接拿这份清单做回归。

### 4.4 重新执行场景

- **有补充用例**（`supplementary_cases.json` 存在）：先执行 Phase 2 重新 import + Phase 3 追加关联（mapping 会自动重写），再跑 4.1 回写
- **无补充用例**：直接对计划中已有用例重新跑 4.1。`writeback-from-fv` 的幂等比对会跳过状态相同的条目，只更新真正变化的。

### 4.5 单条调用（仅诊断 / 应急用）

不推荐在正常流程使用；仅在 4.1 报错需要逐条诊断时用：

```bash
python3 $HELPER lookup-plan-case --plan-id X --case-id M1-TC-01
python3 $HELPER update-case-result <plan_case_id> Pass \
  --comment "AI 静态验证通过 (conf=95)"
```

---

## 阶段 5: output - 生成报告

### 5.1 ms_sync_report.json（execute 模式由 writeback-from-fv 自动生成）

execute 模式下的 `ms_sync_report.json` 由 `writeback-from-fv` 自动落盘，结构：

```json
{
  "plan_id": "uuid-zzz",
  "fv_path": "/abs/path/to/forward_verification.json",
  "ran_at": "2026-04-23T12:34:56Z",
  "dry_run": false,
  "summary": {
    "total": 46,
    "updated": 30,
    "unchanged": 14,
    "failed": 2,
    "by_target_status": {"Pass": 33, "Prepare": 13, "Failure": 0}
  },
  "updated": [
    {"case_id": "M1-TC-01", "target": "Pass", "from": "Prepare",
     "plan_case_id": "...", "ms_id": "..."}
  ],
  "unchanged": [
    {"case_id": "M2-TC-03", "status": "Pass", "plan_case_id": "...", "ms_id": "..."}
  ],
  "failed": [
    {"case_id": "M3-TC-09", "error_type": "mapping_miss",
     "message": "M3-TC-09 not in mapping", "retriable": false}
  ]
}
```

> 字段语义：
> - `summary.by_target_status`：按 P6 映射后的 MS 目标状态分类计数
> - `updated`：状态有变更并成功写回的条目
> - `unchanged`：当前状态已等于 target，幂等跳过
> - `failed`：写回失败的条目（按 `error_type` 分类，含 mapping_miss / not_in_plan / api_error 等）

sync 模式（不跑 writeback）则**不产出**该文件。

### 5.2 输出摘要

execute 模式跑完后向用户展示：

```
MS 测试计划回写完成：
- Pass: {by_target_status.Pass} 条（AI 静态验证通过且无外部依赖）
- Prepare: {by_target_status.Prepare} 条（含 X 条 pass+ext_deps + Y 条 inconclusive）
- Failure: {by_target_status.Failure} 条
- 测试计划: {plan_url from ms_plan_info.json}
- 待回归清单: {workspace}/pending_external_validation.md
- {summary.failed} 条写回失败 → 见 ms_sync_report.json.failed[]
```

sync 模式只展示导入统计 + 计划链接。

### 5.3 完成验证

- sync 模式：`ms_case_mapping.json`（v2）、`ms_plan_info.json` 已落盘
- execute 模式：上述两个 + `ms_sync_report.json`、`forward_verification.enriched.json`、`pass_with_caveats.md`、`pending_external_validation.md` 全部落盘
