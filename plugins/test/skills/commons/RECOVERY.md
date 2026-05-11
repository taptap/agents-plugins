# Recovery Cookbook（traceability + metersphere-sync 共享）

> 收纳 `requirement-traceability` 与 `metersphere-sync` 全部异常路径、兜底规则、降级 pattern。
>
> **设计目标**：
> - PHASES.md 主流程只描述「正常路径 + R-code 引用」，让首次阅读者直接看清主干
> - 排错 / 修复时来这里查 R-code，每条都有「触发 / 原因 / 修复 / 预防」四件套
> - 通用兜底 pattern 在「Pattern Library」节集中，避免在多个 phase 重复抄
>
> **R-code 编号约定**：`R-{域}-{序号}`。域：VFV (validate-fv) / WB (writeback) / RB (rebuild-mapping) / RM (refresh-mapping) / IC (import-cases) / AQ (AskUserQuestion 兜底) / 46 (Phase 4.6 兜底合成) / 32 (Phase 3.2 sub-agent dispatch) / P6 (Phase 6 skip) / PRE (precondition)。

---

## 1. Pattern Library（可复用兜底模式）

### P-CLARIFY-1 — 重问 1 次澄清后降级到默认值

**适用**：用户对 AskUserQuestion 的回复无法解析或不符合预期。

**步骤**：
1. 第一次解析回复 → 不通过 → 再发起 1 次 AskUserQuestion，prompt 多加一行「上次回复无法识别为 {合法选项}，请明确选项」
2. 第二次仍不通过 → 走预定的「默认值」（每条用例上下文定义）
3. **不要无限循环**——最多 1 次重试，避免死锁

**典型实例**：见 R-AQ-1 / R-AQ-2

### P-RETRY-1 — retriable 错误内部重试 1 次

**适用**：网络抖动 / MS 5xx 等瞬时错误。

**步骤**：
1. 第一次失败 → 解析 stderr 是否 `retriable: true` → 是则 sleep 1s 重试
2. 第二次失败 → 计入 `failed[]`，继续处理下一条（不要批量阻塞）

**典型实例**：helper.writeback-from-fv 内部已实现；调用方通常不需要再包一层

### P-SKIP-PHASE — 软依赖缺失时优雅 skip 整个 phase

**适用**：phase 依赖某个上游产物但该产物不是必需的（例如 Phase 6 依赖 ms_plan_info）。

**步骤**：
1. Phase 入口检查软依赖文件是否存在
2. 缺失 → **跳过整个 phase**，标记 `<phase>_skipped: "missing_<file>"`，chat 输出 graceful 提示
3. 不向 caller 抛错——下游 phase 仍能继续执行

**典型实例**：见 R-P6-1 / R-P6-2

### P-CARRY-FORWARD — 失败时保留前序产物，明确告知用户

**适用**：某个 phase 失败但前面 phase 的产物已落盘且仍有效。

**步骤**：
1. 失败 chat 输出分两段：
   - (A) **已落盘且仍可用** 的产物清单
   - (B) **已被中断** 的 phase 解释 + 修复路径
2. 不要让用户误以为「整个 skill 跑废」

**典型实例**：见 R-VFV 系列 stop 处理

---

## 2. R-VFV：validate-fv 校验失败

> 触发位置：requirement-traceability Phase 4.6a；helper writeback-from-fv 内部预校验
>
> stderr 形态：`{type: validation, errors: [{path, message, schema_path}], total_errors, file}`

### R-VFV-1 — pass 缺 evidence

| 项 | 内容 |
| --- | --- |
| 触发 | `errors[].path` 含 `evidence` 且 `errors[].message` 含 "is a required property" |
| 根因 | Phase 3.2.1 step 4 漏写 evidence 三件套（pass 必带 code_location + verification_logic） |
| 修复 | 回归 3.2.1 step 4，给每条标 pass 的 case 写 evidence。pass + conf≥85 还要带 considered_failure_modes |
| 预防 | 主 agent 内联模式：写 fv 前过一遍 3.2.1 step 5 自检清单。Sub-agent 模式：case-tracer.md 自带 self-check 必跑 |

### R-VFV-2 — code_location 文件不存在

| 项 | 内容 |
| --- | --- |
| 触发 | `errors[].schema_path: boundary/code_location_exists` |
| 根因 | code_location 拼错 / 文件被删 / 路径变了 |
| 修复 | 检查路径；如果文件还在但路径变了，更新 code_location；如果文件确实没了，trace 改 inconclusive (`inconclusive_reason: insufficient_context`) |
| 预防 | 写 evidence 时用 grep 验证 file:line 真实存在 |

### R-VFV-3 — pass + conf < 70

| 项 | 内容 |
| --- | --- |
| 触发 | `errors[].schema_path: items/allOf/4/not` |
| 根因 | 评分锚点没遵守，conf 低却标 pass |
| 修复 | 二选一：(a) 降为 inconclusive；(b) 补强证据让 conf 升到 ≥ 70 |
| 预防 | 跟 3.2.1 step 6 评分锚点对齐 |

### R-VFV-4 — fail 缺 actual 或 evidence

| 项 | 内容 |
| --- | --- |
| 触发 | result==fail 但 actual 或 evidence 缺失 |
| 根因 | Phase 3.2.1 没写完整 |
| 修复 | 补 actual（实际行为描述）+ evidence（code_location + verification_logic） |
| 预防 | fail 比 pass 更危险，evidence 不能省 |

### R-VFV-5 — pass + conf≥85 缺 considered_failure_modes

| 项 | 内容 |
| --- | --- |
| 触发 | `errors[].path: $[i].evidence`，`errors[].message` 含 'considered_failure_modes' |
| 根因 | 高 conf pass 没做对抗式自检 |
| 修复 | 加至少 1 条 `{mode, ruled_out_by}` |
| 预防 | 高 conf pass = 强声明 = 必须列出排除掉的 failure mode |

### R-VFV-6 — external_dependencies.types enum 越界

| 项 | 内容 |
| --- | --- |
| 触发 | `errors[].path` 含 `external_dependencies.types` |
| 根因 | typo（写了 `Device` 而非 `device`），或用了未注册的类型 |
| 修复 | 改成 schema 允许的 enum：`device / server / third_party / framework_default / user_action / data_state / timing` |
| 预防 | 复制粘贴 schema 已有值，不要自创 |

### R-VFV-STOP — 4.6a 失败时的产物处置（应用 P-CARRY-FORWARD）

> validate-fv 失败 → Phase 4.7 / 5 / 6 全部中断。但前序 4.x 产物**已经落盘且仍可用**。

chat 必须输出两段：

**(A) 已可用的产物清单**：
```
✅ 已落盘且仍可用：
  - $TEST_WORKSPACE/traceability_matrix.json
  - $TEST_WORKSPACE/traceability_coverage_report.json
  - $TEST_WORKSPACE/risk_assessment.json
  - $TEST_WORKSPACE/code_analysis.md
  - $TEST_WORKSPACE/api_contract_report.json (如有)
  - $TEST_WORKSPACE/ui_fidelity_report.json (如有)
```

**(B) Phase 4.7 / 5 / 6 已被中断的解释 + 三条修复路径**：
```
⛔ Phase 4.7 / 5 / 6 已中断，因为 fv 校验失败。fv 字段错误见 stderr.errors[]

修复后重跑本 skill：
  - 错误来自 3.2 用例追踪 → fv 修好后从 4.6a 重跑（前 4 个 phase 不重复跑）
  - 错误来自 4.6 兜底合成 → 检查 R-46-1 自校验清单
  - 不想修 fv 也不需要 writeback → 把 fv.json 删掉重跑 mode=traceability，writeback 会被 6.1.b 软警告 skip
```

---

## 3. R-WB：writeback-from-fv 失败

> 触发位置：requirement-traceability Phase 6.2；metersphere-sync mode=execute
>
> 单条 case 失败计入 `ms_sync_report.json.failed[]`，整体 helper exit 1

### R-WB-1 — mapping_miss

| 项 | 内容 |
| --- | --- |
| 触发 | `failed[].error_type: mapping_miss` |
| 根因 | fv 里某 case_id 不在 ms_case_mapping.json 里 |
| 修复 | 跑 `helper.py refresh-mapping --diff-only` 看是 stale 还是 missing；missing 则跑 mode=sync 重 import 这条 case；stale 则 `--apply` 清理 |
| 预防 | 改完 cases 后立刻跑 mode=sync 同步 mapping |

### R-WB-2 — not_in_plan

| 项 | 内容 |
| --- | --- |
| 触发 | `failed[].error_type: not_in_plan` |
| 根因 | mapping 里有 ms_id 但 plan 里没这条 case（plan 切换 / case 没关联到 plan） |
| 修复 | 跑 `helper.py rebuild-mapping --plan-id <new_plan>` 重建 mapping；如果 unmatched_local 非空，按 R-RB-2 处理 |
| 预防 | 切 plan 后第一时间跑 rebuild-mapping |

### R-WB-3 — api_error 不可重试

| 项 | 内容 |
| --- | --- |
| 触发 | `failed[].error_type: api_error`, `retriable: false` |
| 根因 | MS API 4xx（参数错 / 权限错 / 资源不存在） |
| 修复 | 看 message 字段处理；常见：plan_case_id 已过期 → 重跑 list-plan-cases 拉最新；权限错 → 检查 MS_ACCESS_KEY 是否有该 plan 的写权限 |
| 预防 | writeback 内部已经做了 list-plan-cases 一次性拉全；用户改 MS plan 状态后建议重跑 |

### R-WB-4 — network 持续失败

| 项 | 内容 |
| --- | --- |
| 触发 | `failed[].error_type: network`, `retriable: true`，但已自动 retry 1 次仍失败 |
| 根因 | 网络持续不稳定 / MS 实例宕机 |
| 修复 | 检查网络 + MS 健康；恢复后**重跑 writeback-from-fv**——已 unchanged 的 case 会被幂等跳过，只会处理失败的 |
| 预防 | 无 |

---

## 4. R-RB：rebuild-mapping 失败

> 触发位置：用户主动跑 `helper.py rebuild-mapping`

### R-RB-1 — ambiguous_titles

| 项 | 内容 |
| --- | --- |
| 触发 | rebuild stdout `ambiguous_titles[]` 非空，exit 1，**mapping 不落盘** |
| 根因 | 同 title 在 plan 或本地 cases 里出现多次，无法机器消歧 |
| 修复 | 改 case title 加序号或限定词消歧；或者手工编辑现有 mapping（仅当撞名是预期）|
| 预防 | case 生成阶段就遵循「同模块内 title 唯一」 |

### R-RB-2 — unmatched_local（D6 修复小循环）

| 项 | 内容 |
| --- | --- |
| 触发 | rebuild stdout `unmatched_local[]` 非空，exit 1，mapping 已落盘但缺这些条目 |
| 根因 | 本地 cases 但 plan 里没找到对应 case |
| 预防 | 切换 plan 时配套跑 add-cases-to-plan |

修复诊断流程：

```
              ┌─ rebuild-mapping ─┐
              │   exit 1          │
              │   unmatched_local │
              │   = [TC-09, TC-12]│
              └────────┬──────────┘
                       │
                       ▼
        从 mapping 拿不到 ms_id —— TC-09/12 还没在 plan 里
                       │
                       ▼
            ┌─── 检查这些 case 是否已在 MS 用例库 ───┐
            │                                        │
            ▼                                        ▼
   已在用例库（曾 import 过）              不在用例库（漏 import）
            │                                        │
            ▼                                        ▼
   add-cases-to-plan <plan_id>              先跑 mode=sync 重 import
   --case-ids <ms_id1>,<ms_id2>             （会同时 add 到当前 plan）
            │                                        │
            └──────────────┬─────────────────────────┘
                           │
                           ▼
                   重跑 rebuild-mapping
                           │
                           ▼
                     unmatched_local 应为空
                     mapping 完整，回到 traceability writeback
```

**关键判断点**：用 `lookup-plan-case --plan-id X --case-id <local_id>` 试一下；如返回 `not_found` 但能在 `list-modules` 里搜到这条 case → 用例库有但 plan 没关联 → 走 add-cases-to-plan；`list-modules` 也搜不到 → 走 mode=sync 重 import。

### R-RB-3 — unmatched_in_plan

| 项 | 内容 |
| --- | --- |
| 触发 | rebuild stdout `unmatched_in_plan[]` 非空 |
| 根因 | plan 里有 case 但本地 cases 里没——通常是 PM 手工加的或别处来源 |
| 修复 | 通常**不需要修**——这些 case 不在 traceability 体系内，跳过即可 |
| 预防 | — |

---

## 5. R-RM：refresh-mapping 差异处理

### R-RM-1 — missing_in_mapping

| 项 | 内容 |
| --- | --- |
| 触发 | refresh stdout `missing_in_mapping[]` 非空 |
| 根因 | 本地 cases 比 mapping 新（新增了 case） |
| 修复 | 跑 `mode=sync` 来 import 这些 case |

### R-RM-2 — stale_in_mapping

| 项 | 内容 |
| --- | --- |
| 触发 | refresh stdout `stale_in_mapping[]` 非空 |
| 根因 | mapping 比本地 cases 新（cases 被局部删了） |
| 修复 | 跑 `refresh-mapping --apply` 清理 stale 条目 |

---

## 6. R-IC：import-cases 失败

### R-IC-1 — 同模块内重名

| 项 | 内容 |
| --- | --- |
| 触发 | stderr `type: validation`, `duplicates[]` 非空，exit 2 |
| 根因 | 同 (module, title) ≥ 2 条 |
| 修复 | 在 case 生成阶段消歧（加序号或限定词），重跑 import |
| 预防 | test-case-generation 应该保证同模块内 title 唯一 |

### R-IC-2 — schema 校验失败

| 项 | 内容 |
| --- | --- |
| 触发 | stderr `type: validation`, `errors[]` 列出每条不合规字段，exit 2 |
| 根因 | 用例文件不符合 plugins/test/CONVENTIONS.md#用例-json-格式 |
| 修复 | 按 stderr 提示逐条修，重跑 import |

---

## 7. R-AQ：AskUserQuestion 不可解析回答

> 应用 pattern P-CLARIFY-1

### R-AQ-1 — Phase 4.7 用户回复不明确（D1）

| 项 | 内容 |
| --- | --- |
| 触发 | 4.7 高 conf fail 复核时用户没明确选 A/B/C |
| 处理 | 应用 P-CLARIFY-1：再问 1 次「请明确选 A/B/C」；仍不可解析→**默认走 A（保持 fail）**，**不写 human_override**（避免 from=to=fail 的语义混乱），chat 输出 ambiguous-list 让用户后续手工 review |
| 预防 | AskUserQuestion 模板里把三个选项的差别写清楚 |

### R-AQ-2 — Phase 4.7 选 B 后 schema 失败（D1）

| 项 | 内容 |
| --- | --- |
| 触发 | 用户选 B（改 Pass）但没补全 verification_logic 或 considered_failure_modes |
| 处理 | 应用 P-CLARIFY-1：再问 1 次让用户补字段；仍失败→**撤销改判，恢复原 fail** |
| 预防 | AskUserQuestion 模板里 B 选项明确说明需要补什么字段 |

### R-AQ-3 — Phase 5.2 缺口分类时用户回复不明确

| 项 | 内容 |
| --- | --- |
| 触发 | 5.2 缺口分类用户回复不可解析 |
| 处理 | 应用 P-CLARIFY-1：再问 1 次；仍不可解析→`exit_reason: user_terminated` + loop_metadata 标 `last_response_unparseable: true` |
| 预防 | 同 R-AQ-1 |

---

## 8. R-46：Phase 4.6 兜底合成自校验

> 4.6 是 last-resort——只在 3.2 没产 fv 时启动。任何 4.6 缺陷都会让 4.6a 直接 STOP 整个 skill。

### R-46-1 — 漏 source 字段（D2）

| 项 | 内容 |
| --- | --- |
| 触发 | 4.6 合成的 fv 条目缺 `source: "synthesized_from_coverage_report"` 字段 → 4.6a 拒绝（schema 的 synthesized 例外要 source 字段触发） |
| 现象 | 4.6a 报 R-VFV-1（pass 缺 evidence）或 R-VFV-4（fail 缺 actual/evidence）——其实是 source 漏了导致没走豁免 |
| 修复 | 4.6 合成代码里 assert 每条都带 source，重新落盘 |
| 预防 | 4.6 落盘前必跑下面的「6 项自校验清单」 |

#### 4.6 自校验清单（合成完毕、落盘前**逐条 assert**）

- [ ] 每条记录都有 `source: "synthesized_from_coverage_report"`（漏写 → 4.6a 直接 stop）
- [ ] `case_id` 形如 `FORWARD-TRACER-FP-{N}`
- [ ] `requirement_id` 形如 `FP-{N}`
- [ ] `result` ∈ `{pass, fail, inconclusive}`
- [ ] `confidence` 是 number（pass 不能 < 70；schema 会拒）
- [ ] `inconclusive` 必须带 `inconclusive_reason`（取 `external_dependency` 或 `insufficient_context` 兜底）
- [ ] `trace` 字段非空（兜底说明文案）

> 6 项**全部硬约束**，少一个就让整个 skill 在 4.6a stop。落盘前用 jq / grep 自查比走到 4.6a 才发现错误便宜得多。

### R-46-2 — case_id / requirement_id 命名不规范

| 项 | 内容 |
| --- | --- |
| 触发 | 兜底条目 case_id 不是 `FORWARD-TRACER-FP-{N}` 格式 |
| 修复 | 按规范重写 |

---

## 9. R-32：Phase 3.2.dispatch sub-agent 失败（D5）

### R-32-1 — Task 工具不可用 / 全部 sub-agent 启动失败

| 项 | 内容 |
| --- | --- |
| 处理 | 退回 M ≤ 3 路径——主 agent 顺序内联跑完所有模块的 3.2.1。chat 标记 `subagent_dispatch_failed: true` |

### R-32-2 — 单 sub-agent 持续校验失败

| 项 | 内容 |
| --- | --- |
| 处理 | 主 agent 接管该模块的内联追踪。其他 sub-agent 不受影响 |

### R-32-3 — sub-agent 超时

| 项 | 内容 |
| --- | --- |
| 处理 | Task 工具超时机制兜底；超时后等同 R-32-2 |

> **共同硬约束**：sub-agent 失败**绝不允许**跳过该模块的 cases。所有 case 必须有 fv 条目（最低限 inconclusive）。

---

## 10. R-P6：Phase 6 整段优雅 skip（应用 P-SKIP-PHASE）

### R-P6-NORMAL — Phase 6.3 常态摘要模板

```
MS 测试计划回写完成：
- Pass：{N} 条（AI 静态验证通过且无外部依赖）
- Prepare：{M} 条（{X} 条带外部依赖待回归 + {Y} 条 inconclusive）
- Failure：{K} 条
- 测试计划：<plan_url>
- 待回归清单：$TEST_WORKSPACE/pending_external_validation.md
```

### R-P6-1 — missing ms_case_mapping（D10）

| 项 | 内容 |
| --- | --- |
| 触发 | Phase 6.1.b 检查 mapping 不存在 |
| 处理 | 整 Phase 6 优雅 skip，标 `writeback_skipped: "missing_ms_case_mapping"` |
| 预期 | 1.3.b 早已警告过；用户跑到这里说明可能就不想 writeback |

chat 模板：
```
ℹ️ Phase 6 writeback 已跳过：ms_case_mapping.json 不存在

如需写 MS：先跑 metersphere-sync mode=sync 生成 mapping，再重跑本 skill 的 Phase 6（fv 已落盘可直接复用）

如不需要 writeback，本次产物已完整：traceability_matrix.json / traceability_coverage_report.json / risk_assessment.json / forward_verification.json
```

### R-P6-2 — missing ms_plan_info（D3）

| 项 | 内容 |
| --- | --- |
| 触发 | Phase 6.1.b 检查 plan_info 不存在 |
| 处理 | 整 Phase 6 优雅 skip，标 `writeback_skipped: "missing_ms_plan_info"` |

chat 模板：
```
ℹ️ Phase 6 writeback 已跳过：ms_plan_info.json 不存在

fv.json 已落盘，可后续补跑：
  1. 跑 metersphere-sync mode=sync 完成 import + 创建测试计划
  2. 重跑本 skill（fv 会被复用，不会重复跑 3.x/4.x）

或如不需要 writeback，本次产物已完整：
  - traceability_matrix.json
  - traceability_coverage_report.json
  - risk_assessment.json
  - forward_verification.json
```

### R-P6-3 — fv 全 inconclusive 警示摘要（D7）

| 项 | 内容 |
| --- | --- |
| 触发 | Phase 6.3 检查 `summary.by_target_status.Pass == 0 && Failure == 0`（全 Prepare） |
| 处理 | chat 摘要顶部加显眼警示，按 inconclusive_reason 分组统计 |

chat 模板：
```
⚠️ AI 本次未能验证任何 case（全部判定 inconclusive 或依赖外部因素）

可能原因：
  - 代码可读性不足（diff-only 模式 + 调用链过深 / 动态分派 / 跨服务）
  - 用例输入质量低（final_cases.json 描述太抽象，无法对应具体代码路径）
  - 大部分 pass 自检后被识别为依赖真机/server，全部降级 Prepare

建议：
  - QA 须把全部 {N} 条 case 视为「待人工执行」，不能默认 AI 减负
  - 若担心 AI 完全失能，用 requirement_doc_link 重跑本 skill 提供需求文档辅助追踪
  - 全 inconclusive 通常意味着 fv 的 inconclusive_reason 字段集中在 1-2 类，可针对性补充上下文

详情：$TEST_WORKSPACE/forward_verification.json，按 inconclusive_reason 分组：
  - external_dependency: {n1} 条
  - call_depth_exceeded: {n2} 条
  - dynamic_dispatch: {n3} 条
  - ...

测试计划：<plan_url>
```

---

## 11. R-PRE：Phase 1.3 precondition 检查

### R-PRE-1 — final_cases.json 缺失（硬阻断）

| 项 | 内容 |
| --- | --- |
| 触发 | 1.3.a 检查不通过 |
| 处理 | STOP，提示「先跑 test-case-generation 产出 final_cases」 |

### R-PRE-2 — mapping sha 不一致（硬阻断）

| 项 | 内容 |
| --- | --- |
| 触发 | 1.3.a 检查 mapping.source_cases_file.sha256 != sha256(final_cases.json) |
| 处理 | STOP——stale 比 missing 更危险，不能 skip |
| 修复 | 跑 `refresh-mapping --diff-only` 查差异，再 `--apply` 修复 |

### R-PRE-3 — mapping / plan_info 缺失（软警告）

| 项 | 内容 |
| --- | --- |
| 触发 | 1.3.b 检查不通过 |
| 处理 | chat 警告，**不 STOP**。Phase 6.1.b 二次校验时整段 Phase 6 skip（见 R-P6-1 / R-P6-2）|

---

## 12. By Phase Quick Index

| Phase | 相关 R-code |
| --- | --- |
| 1.3 init precondition | R-PRE-1 / R-PRE-2 / R-PRE-3 |
| 3.2 forward verification | R-32-1 / R-32-2 / R-32-3 |
| 4.6 兜底合成 | R-46-1 / R-46-2 |
| 4.6a validate-fv | R-VFV-1 ~ R-VFV-6 / R-VFV-STOP |
| 4.7 fail 复核 | R-AQ-1 / R-AQ-2 |
| 5.2 缺口分类 | R-AQ-3 |
| 6 writeback | R-WB-1 ~ R-WB-4 / R-P6-1 / R-P6-2 / R-P6-3 |
| ms-sync 2.1 import | R-IC-1 / R-IC-2 |
| ms-sync 2.3 refresh | R-RM-1 / R-RM-2 |
| ms-sync 2.4 rebuild | R-RB-1 / R-RB-2 / R-RB-3 |
