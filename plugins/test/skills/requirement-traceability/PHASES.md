# 需求回溯各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 额外预取：关联代码变更列表（GitLab MR / GitHub PR）。预取数据仅在 MR/PR 模式下可用；本地 diff 模式无预取。

## 阶段 1: init - 输入验证

确认代码变更来源（主要阻断条件之一）+ 标准模式跑 1.3 precondition 校验。需求来源的路由统一在阶段 2 的 2.0 步骤中处理。

### 1.1 确认代码变更来源

收集所有代码变更来源（可同时提供多个）：

1. `code_diff_text` 参数非空 → 纳入 **文本 diff**
2. `code_diff` 参数提供了文件路径列表 → 逐个 Read，纳入 **文件 diff**
3. `code_changes` 参数提供了 MR/PR 链接列表 → 纳入 **MR/PR 列表**
4. 预取数据中有关联代码变更列表 → 合并到 MR/PR 列表（去重）
5. 以上均为空时，预取数据中有 `work_item_id` → 用 `search_mrs.py` / `search_prs.py` 搜索，仍为 0 → **停止**
6. 以上均不满足 → **停止**

后续阶段同时处理所有来源的 diff 数据。

### 1.2 MR/PR 模式下的 provider 判断

仅 MR/PR 模式需要：从链接或预取数据的 `provider` 字段判断代码托管平台（GitLab / GitHub）。

### 1.3 Precondition 校验（CRITICAL，标准模式必须执行）

仅当本次执行需要走到 Phase 6 写回 MS plan（即非 smoke-test 模式）时检查；smoke-test 模式跳过本节。

> **设计哲学**：硬阻断只针对「无之则后续 phase 完全跑不动」的资源；MS 相关产物（mapping / plan_info）属于「writeback 才用得到」，缺失时让 Phase 6 优雅 skip 即可，不应阻断「只想要 coverage_report」的用户。1.3.b 早期警告 + 6.1.b 优雅 skip 的组合避免 D3 「白跑 4 phase 才发现」的体验问题。

#### 1.3.a 硬阻断项（任一不满足 → STOP）

| 项 | 校验 | 失败提示 |
| --- | --- | --- |
| `final_cases.json` 存在 | 文件可读、顶层 array 非空 | 先跑 test-case-generation 产出 final_cases |
| mapping sha 一致（仅当 mapping 存在时校验）| mapping.source_cases_file.sha256 == sha256(final_cases.json) | 跑 `metersphere_helper.py refresh-mapping --diff-only` 查看差异，再 `--apply` 修复 |

> **mapping sha 一致性是硬阻断**：sha 不匹配意味着 mapping 是过期的，writeback 时会用错的 ms_id 误改 MS 状态——比 mapping 整个不存在更危险。所以「不存在」是软警告（直接 skip），「存在但 sha 错」是硬阻断（必须先修）。

#### 1.3.b 软警告项（不满足 → 早期警告 + 后期优雅 skip）

| 项 | 校验 | 缺失时行为 |
| --- | --- | --- |
| `ms_case_mapping.json` 存在 | 文件可读、顶层为 `{generated_at, source_cases_file, ms_project_id, entries}` 结构（v2 格式）| chat 输出**警告**：「ms_case_mapping.json 不存在；Phase 6 writeback 会被跳过」。**不 STOP**。Phase 6.1.b 二次校验时整个 Phase 6 优雅 skip。|
| `ms_plan_info.json` 存在 | 文件可读、含 `plan_id` 字段 | chat 输出**警告**：「ms_plan_info.json 不存在；Phase 6 writeback 会被跳过；如需写 MS，请补跑 `metersphere-sync mode=sync` 完成测试计划创建后重跑本 skill」。**不 STOP**。Phase 6.1.b 二次校验时整个 Phase 6 优雅 skip。|

> **D10 — 解锁纯 coverage 用户**：用户可能根本没接 MeterSphere（外部团队 / 试用 / 本地实验），只想要 traceability_matrix / coverage_report / risk_assessment 这一组产物。1.3.b 把 mapping / plan_info 都设为软警告，不强制走完 writeback 链路。

#### 1.3.c 兜底定位提醒

> **Phase 4.6 兜底落盘** 的定位：last-resort 救命，**不应**承担 precondition 缺失的责任。如果走到了 4.6，说明 Phase 3.2 的 forward_verification 产出有 bug，应该回归 3.2 修而不是依赖兜底。

## 阶段 2: fetch - 数据获取

### 2.0 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认需求来源：

1. 工作目录中存在上游产出文件（`clarified_requirements.json`）→ 读取作为需求理解基础，跳过 2.1
2. 如存在 `requirement_points.json` → 读取作为需求点清单
3. `requirement_doc` 参数提供了本地文件 → Read 本地文件作为需求文档，跳过 2.1 的在线获取
4. `story_link` 参数为 URL → 执行 2.1 在线获取
5. 以上均不满足 → 基于代码变更做单边追溯（降级模式）

### 2.1 获取需求文档（可选）

本步骤仅在 2.0 路由到步骤 4（`story_link` 为 URL）时执行：

- 已预下载：Read `requirement_doc.md`
- 未预下载：用 `fetch_feishu_doc.py` 获取
- 链接为空且无上游输入和本地文件：基于代码变更继续

### 2.2 获取设计稿（可选）

有 Figma 链接时使用 `get_figma_data`，有飞书链接时用 `fetch_feishu_doc.py`。

### 2.3 获取代码变更数据

根据 init 阶段确定的模式：

**文本模式 / 文件模式**：diff 内容已在 init 阶段获取，跳过此步。

**MR/PR 模式**：使用预取的代码变更列表或参数提供的链接。为空回退：用 `search_mrs.py` / `search_prs.py` 搜索。

### 2.4 创建分析清单

写入 `traceability_checklist.md`：需求点清单（R1, R2...）、代码变更清单、统计。

## 阶段 3: map - 构建映射矩阵

本阶段主 agent 顺序执行两个通道：先正向（用例中介验证 → `forward_verification.json`），再反向（代码追溯，主 agent 内联到 `code_analysis.md`），在阶段 4 交叉验证。

> **历史变更（v0.0.16）**：旧版本声称 forward-tracer / reverse-tracer 两个 sub-agent 并行调度，但实际 AI 跑 skill 时 sub-agent 调度不可靠（46 条用例的实际跑都是手工补的）。当前版本主 agent 顺序内联。`agents/requirement-traceability/forward-tracer.md` / `reverse-tracer.md` agent 定义文件保留，作为降级路径（3.2.4）和未来选配（条件成熟时再做 sub-agent 调度）。

### 3.0 准备 diff 数据

**重要**：冒烟测试模式下，分析对象是 MR/PR 的 diff 内容（即将合入的代码变更），不是目标分支的当前状态。MR 的 merge_status（opened/merged/closed）不影响 diff 的获取和分析。

MR/PR 模式下，先获取所有代码变更的 diff：

```bash
# GitLab
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-diff <project_path> <mr_iid>
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-detail <project_path> <mr_iid>
# GitHub
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-diff <owner/repo> <pr_number>
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-detail <owner/repo> <pr_number>
```

文本模式 / 文件模式：diff 内容已就绪。

### 3.1 输入路由：定位用例输入与 ID 映射

正向通道需要"用例"作为中介。按以下优先级在工作目录查找：

| 优先级 | 文件 | 来源 | 处理 |
| --- | --- | --- | --- |
| 1 | `final_cases.json` | 上游 test-case-generation | 直接消费，`steps[].action` 当 input、`steps[].expected` 当 expected，`case_id` 形如 `M1-TC-01` |
| 2 | `requirement_points.json` | 上游 requirement-clarification 或 test-case-generation 中间产物 | 每条 `acceptance_criteria` 转 1-2 条简化用例（兜底用） |
| 3 | 都不存在 | — | 从 `traceability_checklist.md` 需求描述自行提取（最弱降级，覆盖面差，应在报告中标注） |

> v0.0.7 起合并原 verification-test-generation 能力。不再消费 `verification_cases.json` 这一层中间产物——直接复用上游测试用例避免重复建模。

**ID 映射**（采用编号直接继承策略）：

1. 回读 `traceability_checklist.md` 中的需求点列表
2. 用例文件中：
   - `final_cases.json` 通过 `module` 字段关联需求点（test-case-generation 的模块名继承自 requirement-clarification 的 FP-N name）
   - `requirement_points.json` 已直接含 `id` (FP-N)
3. **直接使用上游 FP- 编号作为主键关联**，同时记录本地 R- 编号作为别名（如 `FP-1 = R-1 (用户注册)`）
4. 将映射表追加写入 `traceability_checklist.md` 的末尾
5. 后续正向通道通过 FP- 主键直接关联，无需语义匹配

> 仅当无上游 FP- 编号（独立使用模式）时，才使用 R- 独立编号。

同时检查 `ui_fidelity_report.json` 是否存在（上游 UI 还原度检查产出）：
1. 如果存在 → 在 4.4 中直接合并到 traceability_coverage_report.json
2. 如果不存在且有 design_link → 在 3.4 中触发 UI 还原度检查

同时检查 `api_contract_report.json` 是否存在（上游 api-contract-validation 产出）：
1. 如果存在 → 在 4.4 中直接合并到 traceability_coverage_report.json，跳过 3.2.5 的内置检查
2. 如果不存在且代码变更涉及 API 相关文件 → 在 3.2.5 中触发内置契约感知检查

### 3.1.5 枚举值覆盖前置检查（条件触发）

按以下优先级读取上游 `enum_factors`：

1. **优先**：`clarified_requirements.json` 的 `functional_points[].enum_factors[]`（完整 pipeline）
2. **降级**：`requirement_points.json` 的 `[].enum_factors[]`（lite-pipeline，无 clarified_requirements 时）
3. **都不存在**（独立使用本 skill / 上游版本不支持 / RC 跳过 3.2.6）→ 跳过本步骤，在最终 `traceability_coverage_report.json` 标记 `enum_coverage_check: "skipped"` 并注明原因（`source_missing`）

读到的 enum_factors 按以下规则处理：

- **存在且非空** → 对每个功能点的每个枚举值，扫描 `final_cases.json` 中该 FP 关联用例的 `title` / `steps[].action` / `steps[].expected` / `preconditions` 是否含该取值字面量
   - 至少 1 条用例覆盖 → 该枚举值标记 `covered`
   - 0 条用例覆盖 → 该枚举值标记 `enum_coverage_gap`，记入该 FP 的 gap 列表
- **存在且为 `[]`**（上游显式声明无枚举）→ 跳过扫描，标记 `enum_coverage_check: "no_factors"`

**对 forward verification 的影响**（强约束）：

- 任何 FP 存在 `enum_coverage_gap` 时，该 FP 的所有 forward verification 结果**最多 inconclusive**（即使代码追踪显示 pass，也降级为 inconclusive，`inconclusive_reason: "enum_coverage_gap"`）
- 4.6 兜底合成时同样适用：该 FP 的兜底记录 result 不得为 `pass`
- 5S.1 缺陷提取时，`enum_coverage_gap` 作为独立来源（来源 5）写入 defect_list，priority = P1（用例缺漏不直接是阻断，但需在冒烟报告中显式列出）

**为什么前置**：上游 RC 走完 3.2.6 后 `enum_factors` 是已确认的完整枚举集合。如果上游 TCG 漏覆盖某个枚举值（如 `通知类型 = Review` 没有对应用例），traceability 即使代码追踪 pass 也只能保证"该用例覆盖的代码路径正确"，无法保证"未覆盖枚举值的代码路径正确" — 把它强制降级为 inconclusive 是诚实的判定。真实案例：iOS Review 类型菜单 bug，根因之一是 `通知类型 = Review` 这个枚举值在 final_cases.json 里没有任何用例覆盖，traceability 不应给该 FP 判 pass。

### 3.2 正向通道：用例中介验证

#### 3.2.dispatch 主 agent 内联 vs sub-agent 拆分（决策点）

> **历史教训**：旧版本声称 sub-agent 自动并行，实际 AI 跑 skill 时常常变成主 agent 手写——上次跑 46 条用例时主 agent 全程加载所有模块代码，新会话第一次跑非常慢，且容易跑偏。
>
> **本次（v0.0.18）开启**：按模块数拆 sub-agent，每个 sub-agent 携带受限上下文（一个模块的 cases + 那个模块涉及的 diff），独立跑完后输出标准 fv 子集，主 agent 合并。**目的不是并行加速，而是减少主 agent 的全量上下文负担**。

**决策规则**（基于 `final_cases.json` 中不同 `module` 字段的去重数 = M）：

| M（模块数） | 路径 | 理由 |
| --- | --- | --- |
| M ≤ 3 | 主 agent 顺序内联 3.2.1-3.2.3 | 拆 sub-agent 的 dispatch 开销不划算 |
| M > 3 | **单条消息**发 M 个 Task 调用 case-tracer sub-agent | 每个 sub-agent 只看自己模块，主 agent 只做合并 |

**Sub-agent 调度协议**（M > 3 时必须遵守）：

1. 在调度前先把 `final_cases.json` 按 module 分组，统计每个模块涉及的代码文件清单（可从 cases 的 `module` 字段或 `steps` 关键词推断）
2. **单条消息**发 M 个 Task 调用：每个 Task 的 prompt 严格按 `agents/requirement-traceability/case-tracer.md` 模板填充：
   - 模块名 `{M}`
   - 该模块的 cases 子集
   - 该模块涉及的 diff 文件路径清单
   - 输出落盘路径：`$TEST_WORKSPACE/forward_verification.{M}.json`
3. **每个 sub-agent 必须自校验**：用 `metersphere_helper.py validate-fv $TEST_WORKSPACE/forward_verification.{M}.json` 校验通过才能返回；不通过 sub-agent 内部修复重试
4. 所有 sub-agent 完成后，主 agent 合并所有 `forward_verification.{M}.json` → `forward_verification.json`，再统一跑 4.6a 校验

**降级路径**（详见 [Recovery Cookbook §R-32](../_shared/RECOVERY.md#9-r-32phase-32dispatch-sub-agent-失败d5)）：

| 失败场景 | R-code |
| --- | --- |
| Task 工具不可用 / 全部 sub-agent 启动失败 | [R-32-1](../_shared/RECOVERY.md#r-32-1--task-工具不可用--全部-sub-agent-启动失败) |
| 单 sub-agent 多次校验失败 | [R-32-2](../_shared/RECOVERY.md#r-32-2--单-sub-agent-持续校验失败) |
| sub-agent 超时 | [R-32-3](../_shared/RECOVERY.md#r-32-3--sub-agent-超时) |

**硬约束**：sub-agent 失败**绝不允许**跳过该模块的 cases。所有 case 必须有 fv 条目（最低限 inconclusive）。

#### 3.2.0 可追踪性评估（前置硬规则）

对每条用例，在追踪前先评估代码路径的**静态可追踪性**。命中以下任一条件 → 直接标记 `inconclusive`，不进入下方追踪流程：

| 条件 | 处理方式 | inconclusive 原因 |
| --- | --- | --- |
| 调用链超过 3 层 | 强制 `inconclusive` | `call_depth_exceeded` |
| 包含动态分派（接口多态、泛型、反射） | 强制 `inconclusive` | `dynamic_dispatch` |
| 调用目标跨服务或外部依赖 | 强制 `inconclusive` | `external_dependency` |
| diff-only 模式（无完整源码） | 不阻断，但 confidence 上限 70 | — |
| 条件分支嵌套过深或涉及事务/并发 | 强制 `inconclusive` | `complex_logic` |

为什么前置：避免 AI 在不可靠的代码路径上"硬编"出一个 pass/fail 结论。inconclusive 比错误结论更有价值。

#### 3.2.1 追踪流程

对每条通过可追踪性评估的用例：

1. **定位入口**：
   - 来自 `final_cases.json`：用 `module` + `steps[0].action` 推断入口函数（如 "调用登录接口" → 在 `auth/login.go` 找 handler）
   - 来自 `requirement_points.json` 简化版：用 `acceptance_criteria` 中的关键动词推断入口
2. **追踪路径**：沿调用链追踪输入如何被处理，记录关键节点
3. **判定结果**：比对实际执行路径的输出与用例 expected
   - 输出匹配预期 → `pass`
   - 输出不匹配预期 → `fail`，记录实际输出
   - 无法确定 → `inconclusive`
4. **写 evidence**（pass / fail 必须）：每条结论都要带可独立复算的证据。详见 3.2.3 schema。
   - `code_location`：array of `file:line` 或 `file:start-end`，**文件必须存在、行号必须在文件长度内**（schema 校验时会查）
   - `verification_logic`：为什么从这段代码能推出 pass/fail 的论证（让另一个人/AI 只看 evidence 就能复算）
   - `considered_failure_modes`：对抗式自检——列出考虑过但被排除的失败模式（pass + conf≥85 必填，fail 选填）
5. **「假装这条会 fail」自检清单**（仅 `pass` 必须过一遍，任一答"是"且 evidence 没体现 → conf 上限 80）：
   - [ ] 涉及空/null/边界条件？代码有防护吗？
   - [ ] 异步/回调追到完成态了吗？
   - [ ] mock 数据 vs 真实数据区分清楚了吗？
   - [ ] feature flag / 配置项默认是开的吗？
   - [ ] 依赖 server / device / 三方行为吗？默认值是验证过的还是假设的？

   **CRITICAL — external_dependencies 强约束**（P12 教训）：

   只要本条 pass 的判定理由涉及任意外部因素（真机 UI 渲染、server 实际返回、第三方 SDK 行为、framework 默认实现、用户操作、特定测试数据、时序等）→ **必须**在 fv 的 `external_dependencies.types` 数组里**结构化填上对应类型**（`device` / `server` / `third_party` / `framework_default` / `user_action` / `data_state` / `timing`），不能只在 `trace` 字段或 MS comment 里写自然语言。

   理由：下游 `writeback-from-fv` 的 P6 状态映射只看 `external_dependencies.types`：非空 → 自动降级 MS Prepare + 自动汇总进 `pass_with_caveats.md` / `pending_external_validation.md`。如果只写 trace 或 comment，**降级不会触发，caveats 报告会是空，QA 漏掉回归**——这正是 v0.0.16 后第一次实战在 TAP-6841255319 上踩的坑：手写 comment 标了 `external_deps=server,device`，但 fv.external_dependencies.types 是空的，11 条 case 全部错标 Pass。

   **反例 vs 正例**：

   ```jsonc
   // ❌ 错：依赖外部因素的信息只写在 trace 自然语言里
   {
     "result": "pass", "confidence": 85,
     "trace": "登录后展示 Avatar — 实际渲染需真机验证",
     "evidence": {...},
     // external_dependencies 缺失 → 下游错标 MS Pass
   }

   // ✅ 对：结构化标进 external_dependencies.types
   {
     "result": "pass", "confidence": 85,
     "trace": "登录后展示 Avatar",
     "evidence": {...},
     "external_dependencies": {
       "types": ["device"],
       "notes": "Avatar 圆角 + 阴影需真机渲染验证"
     }
     // → 下游降级 MS Prepare + 进 pending_external_validation.md
   }
   ```
6. **评估置信度**（评分锚点；schema 会拒绝 pass + conf<70）：

   | conf 区间 | 含义 |
   | --- | --- |
   | 95-100 | 完整调用链可追到入口和出口，无外部依赖，evidence 三件套齐 |
   | 85-94 | 调用链可追，1-2 个内部分支已逐个推理，无外部依赖 |
   | 70-84 | 逻辑可追但依赖框架默认行为或外部状态（必须填 `external_dependencies`，下游会降级为 MS Prepare） |
   | < 70 | 不应标 pass，必须降为 inconclusive；schema 会硬拒

#### 3.2.2 追踪记录格式

`forward_verification.json` 中每条记录的 `trace` 字段采用调用链格式：

```
入口函数() -> 中间调用() -> 关键逻辑(参数) -> 结果 == 预期值
```

示例：
- pass: `applyCoupon(100, 50) -> min(coupon, order) -> min(100, 50) -> 50 == expected 50 ✓`
- fail: `applyCoupon(100, 50) -> coupon - order -> 100 - 50 -> 50, 但实际返回 100 ≠ expected 50 ✗`
- inconclusive（外部依赖）: `applyCoupon() 存在但内部调用 externalService.calculate()，外部服务逻辑不可见`
- inconclusive（调用链过深）: `handleOrder() -> processPayment() -> validateCoupon() -> applyCoupon() -> calculateDiscount()，超过 3 层调用链`
- inconclusive（动态分派）: `processor.Execute() 为接口方法，实际实现取决于运行时注入`

`inconclusive` 原因分类必须填入 `verification.inconclusive_reason` 字段，取值见 3.2.0 表格。

#### 3.2.3 写入结果（v2 schema）

将所有用例的验证结果写入 `forward_verification.json`。完整 schema 在 `_shared/schemas/forward_verification.schema.json`，落盘后必须通过 `metersphere_helper.py validate-fv` 校验（见 4.6 之后的 4.6a）。

字段示例：

```json
[
  {
    "case_id": "M1-TC-01",
    "requirement_id": "FP-1",
    "requirement_name": "网络失败时弹 toast",
    "result": "pass",
    "confidence": 90,
    "trace": "applyCoupon(100, 50) -> min(coupon, order) -> 50 == expected 50 ✓",
    "expected": "网络失败时弹 toast 提示",
    "evidence": {
      "code_location": ["src/Network.swift:87", "src/Toast.swift:142-150"],
      "verification_logic": "Network.swift:87 在 catch 分支调 ToastCenter.show(errorMsg)；errorMsg 由 TapNetwork.swift:33 兜底为非空字符串。因此 toast 必弹。",
      "considered_failure_modes": [
        {"mode": "errorMsg 为空字符串", "ruled_out_by": "TapNetwork.swift:33 默认值兜底"},
        {"mode": "ToastCenter 未初始化", "ruled_out_by": "AppDelegate.swift:21 启动时初始化"}
      ]
    },
    "external_dependencies": {
      "types": [],
      "notes": ""
    }
  },
  {
    "case_id": "M2-TC-04",
    "requirement_id": "FP-2",
    "result": "fail",
    "confidence": 80,
    "actual": "errorMsg 空字符串时不弹 toast",
    "evidence": {
      "code_location": ["src/Network.swift:142"],
      "verification_logic": "guard 检查 errorMsg.isEmpty 直接 return，导致 toast 不弹",
      "considered_failure_modes": [
        {"mode": "上层兜底", "ruled_out_by": "调用栈追到 ViewModel 层无兜底"}
      ]
    }
  },
  {
    "case_id": "M3-TC-09",
    "requirement_id": "FP-3",
    "result": "inconclusive",
    "confidence": null,
    "inconclusive_reason": "external_dependency",
    "trace": "调用 thirdPartySDK.report() 行为不可见"
  }
]
```

**关键字段约束**（schema 强制）：
- `pass` 必须带 `evidence.{code_location, verification_logic}`
- `pass` 且 `confidence ≥ 85` 还必须带 `evidence.considered_failure_modes`
- `pass` 且 `confidence < 70` → schema 直接拒绝（强制降为 inconclusive）
- `fail` 必须带 `actual` + `evidence`
- `inconclusive` 必须带 `inconclusive_reason`
- `external_dependencies.types` 取值：`device | server | third_party | framework_default | user_action | data_state | timing`

#### 3.2.4 降级回退

如果代码不可读、diff 信息严重不足（如 fetch 阶段只拿到文件名清单）→ 降级为传统 forward-tracer Agent 模式（不做用例中介，直接需求 → 代码模糊映射）。降级时 forward-tracer 输出 `{agent, requirement_to_code}` 格式（`status: covered/partial/missing`），需适配为 `forward_verification.json` 格式后写入：

| forward-tracer status | 映射后 result | confidence 处理 |
| --- | --- | --- |
| `covered` | `pass` | 保留 forward-tracer 的 confidence |
| `partial` | `inconclusive` | confidence 取 forward-tracer 值的 80% |
| `missing` | `fail` | 保留 forward-tracer 的 confidence |

降级时 `case_id` 字段填 `"FORWARD-TRACER-{requirement_id}"`，标记数据来源。

### 3.2.5 API 契约感知检查（条件触发）

当前后端同步开发时，代码变更可能存在接口契约不一致。本步骤在正向通道完成后执行轻量级 API 契约校验。

**触发条件**（满足任一即触发）：

1. 代码变更文件中包含 API 相关模式（网络请求路径定义、API 模型/DTO、请求参数构造、路由定义等）
2. `traceability_checklist.md` 中的需求点涉及接口交互（关键词：接口、API、数据获取、请求、网络等）
3. `code_changes` 或 `backend_changes` 中同时存在前端和后端 MR/PR

以上条件均不满足 → 跳过，在 traceability_coverage_report.json 中记录 `api_contract.overall_consistency: "N/A"`。

**上游优先**：如果工作目录已有 `api_contract_report.json`（上游 api-contract-validation 产出）→ 跳过内置检查，在阶段 4 直接合并。

**内置轻量级检查流程**：

1. **分类 API 相关变更**：从 diff 中识别以下文件类型
   - 前端：网络请求路径枚举/常量、API 响应模型（Codable/Decodable/DTO）、请求参数构造
   - 后端：路由定义、Controller/Handler、响应结构体/序列化器

2. **提取接口签名**：从 diff 中提取每个涉及的 API 端点的关键信息
   - 请求路径（URL path）
   - 请求方法（GET/POST/PUT/DELETE）
   - 请求参数名和类型
   - 响应字段名和类型

3. **交叉比对**：对每个涉及的端点，在前端和后端的变更之间做一致性检查
   - **路径一致性**：前端调用路径 vs 后端路由定义
   - **字段名一致性**：前端模型字段名 vs 后端响应字段名（注意命名风格转换，如 snake_case ↔ camelCase）
   - **类型一致性**：前端字段类型 vs 后端字段类型（如 String vs Int 不匹配）
   - **必填字段完整性**：后端标记为必填的请求参数，前端是否都传递了

4. **可选：OpenAPI 基准校验**：如果提供了 `openapi_spec` 参数
   - 将前端模型和后端实现分别与 OpenAPI 定义比对
   - 偏离 OpenAPI 定义的一方标记为不一致来源

5. **写入结果**：生成契约检查摘要，追加到 `code_analysis.md`

**降级**：

- 仅有前端变更无后端变更（或反之）→ 仅检查与 OpenAPI spec 的一致性（如有 spec），否则仅记录 API 相关变更的概要，不做一致性判定
- diff 信息不足以提取接口签名 → 标记为 `inconclusive`，在报告中注明原因

### 3.3 反向通道：直接代码追溯（主 agent 内联，不拆 sub-agent）

> **历史变更说明**：旧版本描述「启动 reverse-tracer sub-agent 并行」，agent 定义文件 `agents/requirement-traceability/reverse-tracer.md` 是存在的，但实际 AI 跑 skill 时 sub-agent 调度不可靠——上次跑 46 条用例的反向部分实际是主 agent 手工补的。当前版本明确：**主 agent 顺序内联完成反向追溯，不调 Task 启动 sub-agent**。
>
> agent 定义文件保留作为：（1）降级路径（3.2.4 forward-tracer），（2）未来如果收集到足够数据证明 sub-agent 调度有价值，可以再开启。在此之前默认不调。

**主 agent 反向追溯流程**（在正向通道完成 3.2 后串行执行）：

1. **回读输入**：Read `./traceability_checklist.md`（需求点列表 R1, R2...）；Read 已经在 Phase 2 拿到的 diff 数据 / `./requirement_doc.md`
2. **逐条代码变更归属**：对 diff 里每个文件 / 函数级变更，判断它属于哪个需求点：
   - 直接命中需求关键词 → `mapped`
   - 部分相关（重构、附带改动）→ `tangential`
   - 完全无关 / 无法归因 → `orphan`（写进缺口报告）
3. **输出**：直接写进 `code_analysis.md`，不需要单独 JSON 文件；reverse 部分用以下格式：

```markdown
## reverse-tracer 输出（主 agent 内联）

### 已归属变更
- src/Network.swift:140-160 → FP-2「网络错误处理」（confidence 90）
- ...

### 未归属变更（orphan）
- src/Util/Logging.swift:50-60 → 无法归因到任何需求点（可能是顺手优化）
```

**注**：`code_to_requirement` JSON 结构不再独立产出；下游 Phase 4.1 直接从 `code_analysis.md` 这一节读取。

### 3.4 UI 还原度检查（条件触发）

**触发条件**：需求有 `design_link`（Figma 链接）且前端页面可在浏览器中访问。

如果工作目录已有 `ui_fidelity_report.json`（上游产出）→ 跳过，在阶段 4 直接使用。

否则执行内置 UI 还原度检查：

**MCP 可用性探测**（前置）：

1. **Figma MCP 探测**：尝试调用 Figma MCP 的 `get_screenshot`，如连接失败或工具不存在 → 跳过整个 UI 还原度检查，在报告中记录降级原因 `figma_mcp_unavailable`
2. **Browser MCP 探测**：尝试调用 Browser MCP 的 `browser_snapshot`，如连接失败 → 降级为 structural-only 模式（仅对比 Figma 结构化数据 vs 代码样式定义）

探测通过后执行：

1. 使用 Figma MCP `get_screenshot` 获取设计稿截图
2. 使用 Figma MCP `get_design_context` 获取结构化设计数据
3. 使用 Browser MCP `browser_take_screenshot` 获取实现截图
4. 使用 Browser MCP `browser_snapshot` 获取 DOM 结构
5. 启动 ui-fidelity-checker Agent（见 agents/ui-fidelity-checker.md）进行对比
6. 输出 `ui_fidelity_report.json`

**降级**：页面不可访问时 → 仅对比 Figma 结构化数据 vs 代码中的样式定义，跳过截图对比。

### 3.5 降级回退

- 反向追溯失败（diff 完全无法解析）→ 主 agent 跳过 3.3，仅依赖 3.2 正向通道的结果，在 4.1 交叉验证时标注「reverse 缺失」
- 正向通道完全失败（无可追踪用例）→ 走 3.2.4 的 forward-tracer 降级路径

> 不再有「Task 工具不可用」的降级讨论——本 skill 已经不依赖 Task 工具拆 sub-agent。

### 3.6 记录中间结果

两个通道完成后，将各自的结果写入 `code_analysis.md`，标注来源通道。

## 阶段 4: output - 交叉验证与风险评估

**前提**：回读 `code_analysis.md` 和 `traceability_checklist.md`，以及两个 Agent 的输出。

### 4.1 交叉验证

> `trace_direction` 字段由本阶段根据两个通道的结果**计算得出**，不由 Agent 直接输出。

在原有交叉验证基础上，新增正向验证结果的合并：

1. 回读 `forward_verification.json`（正向用例验证产出）和 `code_analysis.md` 的「reverse-tracer 输出（主 agent 内联）」节（反向代码追溯结果）
2. 对每个需求点：
   - 正向用例验证 pass → 需求实现确认（confidence 取用例验证的 confidence）
   - 正向用例验证 fail → 标记为实现缺口
   - 正向用例 inconclusive + 反向确认 → 使用反向追溯的 confidence
3. 反向追溯的"未归属代码变更"（orphan）保持原有逻辑

对每个映射对判定方向：
   - **双向确认**：正向和反向都确认同一映射 → `trace_direction: "bidirectional"`，confidence 按 [CONVENTIONS.md 跨 Agent 共识规则](../../CONVENTIONS.md#跨-agent-共识规则) 计算：双方 confidence 均 >= 70 → `min(100, max(两者) + 20)`；任一方 < 60 → 不加成，取两者算术平均值；其余情况（一方 60-69）→ 不加成，取两者中较高值
   - **仅正向确认**：正向找到但反向未找到 → `trace_direction: "forward-only"`，保留正向通道的 confidence
   - **仅反向确认**：反向找到但正向未找到 → `trace_direction: "reverse-only"`，保留反向追溯的 confidence
   - **正反矛盾**：正向 pass 但反向 missing（或反向确认但正向 fail）→ 保留对应单通道的 `trace_direction`，confidence 在原值基础上 -15（下限 50），标记 `conflict: true`，建议人工复核
   - **均未找到**：确认为覆盖缺口

### 4.2 覆盖缺口汇总

- 需求侧缺口：需求点无对应代码变更 → 标记 `missing`
- 代码侧未追溯：代码变更无对应需求 → 标记 `untraced`

### 4.3 生成 traceability_matrix.json

格式见 [TEMPLATES.md](TEMPLATES.md#traceability_matrixjson)。包含 `requirement_to_code`、`code_to_requirement` 两个视角，每条映射含 `confidence` 和 `trace_direction` 字段。

### 4.4 生成 traceability_coverage_report.json

格式见 [TEMPLATES.md](TEMPLATES.md#coverage_reportjson)。包含需求覆盖率、代码追溯率、缺口清单和双向确认率。

在原有覆盖率统计基础上，新增：

- `verification_channel`: 标注使用的验证通道（"dual_channel" | "forward_only" | "reverse_only"）
- `forward_verification_rate`: 正向用例验证通过率
- `ui_fidelity`: 如果有 `ui_fidelity_report.json`，按以下字段映射合并 UI 还原度数据：

```json
{
  "ui_fidelity": {
    "overall_fidelity": "high | medium | low",
    "comparison_mode": "visual+structural | structural-only",
    "total_differences": 5,
    "by_severity": { "high": 1, "medium": 2, "low": 2 },
    "state_coverage_rate": "80%",
    "source": "ui-fidelity-check | inline"
  }
}
```

映射规则：
1. `overall_fidelity` ← `ui_fidelity_report.json` 顶层 `overall_fidelity`
2. `comparison_mode` ← `ui_fidelity_report.json` 顶层 `comparison_mode`
3. `total_differences` ← `differences` 数组长度
4. `by_severity` ← 按 `differences[].severity` 分组计数
5. `state_coverage_rate` ← `ui_fidelity_report.json` 的 `states_coverage.coverage_rate`
6. `source` ← `"ui-fidelity-check"`（上游产出）或 `"inline"`（本 skill 内置检查）
7. 如无 `ui_fidelity_report.json` 且未执行 UI 检查 → `ui_fidelity` 字段不写入
8. 当 `ui_fidelity.by_severity.high > 0` 时，对相关需求点的 `forward_verification.json` 结果追加 `ui_risk_flag: true` 标记。5S.1 缺陷提取时，来源 1 中 `result == "pass"` 但 `ui_risk_flag == true` 的条目，在 `smoke_test_report.json` 的 `notes` 中提示"代码验证通过但存在 UI 还原度高风险差异，建议人工验证"

- `api_contract`: 如果有 `api_contract_report.json`（上游产出）或 3.2.5 内置检查结果，按以下字段映射合并 API 契约数据：

```json
{
  "api_contract": {
    "overall_consistency": "consistent | inconsistent | partial | N/A",
    "checked_endpoints": 3,
    "issues_found": 1,
    "issues": [
      {
        "endpoint": "/api/v2/user/profile",
        "type": "field_mismatch | type_mismatch | path_mismatch | missing_param",
        "severity": "high | medium | low",
        "frontend_expects": "user_name: String",
        "backend_provides": "username: String",
        "source_mr": "ios/taptap-ios!456"
      }
    ],
    "source": "api-contract-validation | inline"
  }
}
```

映射规则：
1. `overall_consistency` ← 上游 `api_contract_report.json` 的 `overall_consistency`，或内置检查的计算结果（全部一致 → `consistent`，存在 high → `inconsistent`，仅 medium/low → `partial`）
2. `checked_endpoints` ← 检查过的接口端点数
3. `issues` ← 上游的 `issues` 数组或内置检查发现的问题列表
4. `source` ← `"api-contract-validation"`（上游产出）或 `"inline"`（本 skill 内置检查）
5. 如 3.2.5 未触发且无上游报告 → `api_contract` 字段不写入

### 4.5 生成 risk_assessment.json

格式见 [TEMPLATES.md](TEMPLATES.md#risk_assessmentjson)。

风险评估维度：
- 需求覆盖率显著低于预期（大量需求点未被实现）→ 高风险
- 存在未追溯的代码变更（可能的范围蔓延）→ 中风险
- 高复杂度变更未映射到明确需求 → 高风险
- 双向确认率低（正反向结果分歧大）→ 额外风险标记
- API 契约存在 high 级别不一致（前后端字段/类型/路径不匹配）→ 高风险
- API 契约存在 medium 级别不一致（命名风格差异、可选字段遗漏等）→ 中风险

### 4.6 forward_verification.json 兜底落盘（CRITICAL，必须执行）

> **目的**：保证 Phase 6 测试计划回写永远有燃料，无论 Phase 3.2 是否被执行偏离。

无论 Phase 3.2 是否产出 `forward_verification.json`，本步骤都要执行一次校验：

1. 检查 `$TEST_WORKSPACE/forward_verification.json` 是否存在且非空。
2. **如已存在且非空** → 跳过本步骤（Phase 3.2 已正确产出，无需兜底）。
3. **如不存在或为空** → 必须从 `traceability_coverage_report.json` 的 per-FP `verdict` + `confidence` 合成一份兜底版本，每个需求点 1 条记录：

合成规则：

| coverage_report 中的 verdict | confidence | 合成 result | 合成 confidence | case_id 命名 |
| --- | --- | --- | --- | --- |
| `implemented` / `covered` | ≥ 90 | `pass` | 同源 confidence | `FORWARD-TRACER-FP-{N}` |
| `implemented` / `covered` | 70-89 | `pass` | 同源 confidence | `FORWARD-TRACER-FP-{N}` |
| `partial` | any | `inconclusive` | min(60, 同源 confidence) | `FORWARD-TRACER-FP-{N}` |
| `unimplemented` / `missing` | any | `fail` | max(70, 同源 confidence) | `FORWARD-TRACER-FP-{N}` |

每条记录写入字段（与正常 Phase 3.2 产出格式一致）：

```json
{
  "case_id": "FORWARD-TRACER-FP-1",
  "requirement_id": "FP-1",
  "requirement_name": "...",
  "result": "pass | fail | inconclusive",
  "confidence": 85,
  "trace": "兜底合成：源自 traceability_coverage_report.json 的 per-FP verdict，未做用例级代码路径追踪",
  "source": "synthesized_from_coverage_report"
}
```

**`source` 字段是兜底版的硬约束标记**——schema 校验把它当作 evidence 缺失的唯一豁免凭证。**写每一条兜底记录时都不能漏**（详见 [R-46-1](../_shared/RECOVERY.md#r-46-1--漏-source-字段d2) 自校验清单）。下游 metersphere-sync Phase 4.4 看到该字段时，回写评论追加"AI 回溯（降级判定，无用例级粒度）"。

> **定位提醒**：4.6 是 last-resort 救命，不应承担 precondition 缺失或 3.2 跑偏的责任。**正常路径不应该走到 4.6**。如果反复走到这里，说明 3.2 有 bug，回归 3.2 修。

### 4.6a forward_verification.json schema 校验（CRITICAL，必须执行）

无论 fv 是 3.2 正常产出还是 4.6 兜底合成，落盘后**强制**跑 schema 校验：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  validate-fv $TEST_WORKSPACE/forward_verification.json
```

- 校验通过（exit 0）→ 继续下一阶段（标准模式：4.7 → 5/6；smoke-test 模式：5S.1 → 5S.2）
- 校验失败（exit 2）→ stderr 是结构化 `{type: validation, errors: [{path, message}]}`，**stop**

**异常处理**（详见 [Recovery Cookbook](../_shared/RECOVERY.md#2-r-vfvvalidate-fv-校验失败)）：

| 错误特征 | R-code |
| --- | --- |
| pass 缺 evidence | [R-VFV-1](../_shared/RECOVERY.md#r-vfv-1--pass-缺-evidence) |
| code_location 文件不存在 | [R-VFV-2](../_shared/RECOVERY.md#r-vfv-2--code_location-文件不存在) |
| pass + conf < 70 | [R-VFV-3](../_shared/RECOVERY.md#r-vfv-3--pass--conf--70) |
| fail 缺 actual / evidence | [R-VFV-4](../_shared/RECOVERY.md#r-vfv-4--fail-缺-actual-或-evidence) |
| pass + conf≥85 缺 considered_failure_modes | [R-VFV-5](../_shared/RECOVERY.md#r-vfv-5--pass--conf85-缺-considered_failure_modes) |
| external_dependencies.types enum 越界 | [R-VFV-6](../_shared/RECOVERY.md#r-vfv-6--external_dependenciestypes-enum-越界) |
| 4.6 兜底漏 source 字段 | [R-46-1](../_shared/RECOVERY.md#r-46-1--漏-source-字段d2) |

**STOP 时的产物处置**（应用 P-CARRY-FORWARD pattern）：4.6a 失败时**前 4 个 phase 的产物仍可用**，chat 必须输出「已落盘清单 + 中断说明 + 三条修复路径」。详见 [R-VFV-STOP](../_shared/RECOVERY.md#r-vfv-stop--46a-失败时的产物处置应用-p-carry-forward)。

绝不允许「校验失败但带 bug fv 跑下去污染 MS plan」。

### 4.7 高 conf fail 复核（标准模式）

> **触发条件**：fv 中存在 `result == "fail"` 且 `confidence >= 80` 的条目。低 conf fail 自带「待确认」语义，不需要复核；高 conf fail 是危险品（下游会当真），必须人工 ack。

对每条高 conf fail，逐条 AskUserQuestion（不批量）：

```
case {case_id}{requirement_name 或对应 final_cases.title 加在括号里}
AI 判定: Failure (conf={confidence})
Evidence:
  - location: {evidence.code_location}
  - logic: {evidence.verification_logic}
  - considered modes:
      - {mode}: ruled out by {ruled_out_by}
      - ...

请确认 (必须选 A/B/C 之一):
  A. 确认是缺陷 → 保持 fail
  B. 误判，重判为 Pass → 改写本条 fv 的 result=pass，evidence.human_override 记录
       ⚠️ 选 B 时**必须同时**给出新的 verification_logic 与至少一条 considered_failure_modes
       （schema 要求 pass 必须有 evidence.{code_location, verification_logic}；
        高 conf pass 还要 considered_failure_modes）。
       原 fail 的 code_location 可保留作为参考起点。
  C. 改为 inconclusive → 改写 result=inconclusive + inconclusive_reason="human_override"，
       evidence.human_override 记录（evidence 其余字段可保留）
```

**改判后的处理**：被改判的条目（B/C）在 evidence 加 `human_override: {from, to, reason}` 字段，整轮 4.7 跑完后**重跑 4.6a validate-fv** 确认 schema 仍合规。

**异常处理**（详见 [Recovery Cookbook](../_shared/RECOVERY.md)）：

| 场景 | R-code |
| --- | --- |
| 用户回复不明确 / 不可解析 | [R-AQ-1](../_shared/RECOVERY.md#r-aq-1--phase-47-用户回复不明确d1) |
| 选 B 后 schema 失败（缺 verification_logic 等） | [R-AQ-2](../_shared/RECOVERY.md#r-aq-2--phase-47-选-b-后-schema-失败d1) |

> **设计原则**：4.7 是质量加固关，不是质量门——默认保持 AI 原判更安全（fail 进 MS Failure 让 QA 二次审）。

### 5S.1 缺陷提取与优先级判定（仅 smoke-test 模式）

> Mode 触发条件以 [SKILL.md mode dispatch 表](SKILL.md#mode-dispatch单一权威表其余-phases-段落只引用本表) 为准，本节不重复列条件。

回读 `forward_verification.json`、`traceability_coverage_report.json`、`traceability_matrix.json`，从以下来源提取缺陷：

**来源 1：正向验证失败**

从 `forward_verification.json` 中提取 `result: "fail"` 且 `confidence >= 70` 的条目：

- 缺陷名称 = 关联需求点名称 + 验证用例的场景描述
- 预期结果 = `expected` 字段原文
- 实际结果 = 从 `trace` 字段推导（代码执行路径偏离预期的关键分支点或返回值）
- **优先级判定（D8 教训：兜底合成的 fail 不能直接判 P0/P1）**：
  - **常态 fail**（fv 条目无 `source` 字段，或 `source != "synthesized_from_coverage_report"`）：confidence ≥ 85 → P0；confidence ≥ 70 → P1
  - **兜底合成 fail**（`source == "synthesized_from_coverage_report"`，由 4.6 兜底产出，不带用例级 evidence）：**统一标 P2** + 缺陷描述追加 "（降级判定，无用例级粒度，需人工核实是否真为缺陷）"。**绝不判 P0/P1**——兜底合成的 fail 来自 coverage_report 的 `verdict: missing/unimplemented`，置信度本身是文档/启发式推断，不是代码追踪结果，把它直接当 P0 阻断会有大量假阳性
- `evidence.source` = `"forward_verification"`，`evidence.source_id` = 对应 `case_id`
- `evidence.synthesized` = `true`（仅当 fv 条目带 `source: "synthesized_from_coverage_report"` 时附加，便于下游审计）

**来源 2：需求实现缺失**

从 `traceability_coverage_report.json` 的 `gaps[]` 中提取 `type == "requirement_not_implemented"` 的条目：

- 缺陷名称 = 需求点名称 + "实现缺失"
- 预期结果 = 需求点描述（从 `traceability_checklist.md` 或 `traceability_matrix.json` 中获取）
- 实际结果 = "代码变更中未发现对应实现"
- 优先级判定：`risk_level == "high"` → P0；`risk_level == "medium"` → P1
- `evidence.source` = `"coverage_gap"`

**来源 3：API 契约不一致**

从 `traceability_coverage_report.json` 的 `api_contract.issues[]` 中提取 severity 为 high 或 medium 的条目：

- 缺陷名称 = 端点路径 + 不一致类型描述
- 预期结果 = 前端期望的定义
- 实际结果 = 后端实际提供的定义
- 优先级判定：`severity == "high"` → P0（类型不匹配、路径不匹配、必填参数缺失）；`severity == "medium"` → P1；`severity == "low"`（前端冗余字段、字段顺序差异）→ 不提取为缺陷，仅在 coverage report 中保留记录
- `evidence.source` = `"api_contract"`

**来源 4：UI 还原度差异（条件触发）**

当 `traceability_coverage_report.json` 中存在 `ui_fidelity` 且有 high severity 差异时：

- 优先级：统一为 P1（UI 差异通常不构成 P0 阻断）
- `evidence.source` = `"ui_fidelity"`

**来源 5：枚举值覆盖缺口（条件触发）**

从 `traceability_coverage_report.json` 的 `gaps[]` 中提取 `type == "enum_coverage_gap"` 的条目（来自 3.1.5 步骤）：

- 缺陷名称 = 需求点名称 + " - 枚举值 `{factor.name}.{value}` 无用例覆盖"
- 预期结果 = "用例集应覆盖该枚举值对应的代码路径"
- 实际结果 = "final_cases.json 中无用例提及该枚举值，代码路径未被验证"
- 优先级判定：统一 P1（用例缺漏不直接阻断功能，但代码层面该路径未验证 = 上线风险）
- `evidence.source` = `"enum_coverage_gap"`，`evidence.factor` = `factor.name`，`evidence.value` = `value`

> 真实案例对应：iOS Review 通知 bug，源自 `通知类型 = Review` 枚举值无对应用例 → traceability 应在此处生成一条 P1 缺陷提示"Review 类型代码路径未被任何用例验证，建议补充用例后重跑"。

**排除规则（MR 流程状态）**：

以下情况不提取为缺陷，仅在 `smoke_test_report.json` 的 `excluded_items` 中记录：

1. MR/PR 处于 opened/draft 状态导致的「代码未合入目标分支」— 这是流程状态而非实现缺陷。冒烟测试基于 MR diff 评估实现质量，不关注合并状态
2. 多个 MR/PR 拆分交付同一需求时，部分 MR 尚未创建或处于早期阶段 — 仅评估已提供的 MR diff 内容
3. 需求实现分布在多个 MR 中，且当前仅提供了部分 MR — 基于已有 diff 评估，未覆盖的部分标记为 `out_of_scope` 而非 `implementation_missing`

判断标准：如果需求对应的代码变更**存在于已提供的 MR diff 中**（无论 MR 是否已合并），则该需求视为「已有实现」，应进入正向验证通道评估实现质量，而非直接标记为缺失。

**去重规则**：同一需求点（`requirement_ref` 相同）从多个来源命中时，合并为一个缺陷，取最高优先级，confidence 取最高优先级来源的 confidence 值，在 `evidence` 中记录所有命中来源及各自的 confidence。

**confidence 过滤**：来源 1 中 confidence < 70 的 fail 项不提取为缺陷，仅在 `smoke_test_report.json` 的 `low_confidence_items` 中记录供参考。

将提取结果暂存，供 5S.2 写入文件。

### 5S.2 生成冒烟测试报告（仅 smoke-test 模式）

承接 5S.1 的缺陷列表。Mode 触发条件以 [SKILL.md mode dispatch 表](SKILL.md#mode-dispatch单一权威表其余-phases-段落只引用本表) 为准。

1. **写入 `defect_list.json`**：将 5S.1 提取的缺陷按优先级排序（P0 在前），格式见 [TEMPLATES.md](TEMPLATES.md#defect_listjson)
2. **写入 `smoke_test_report.json`**：汇总验证统计和缺陷统计，格式见 [TEMPLATES.md](TEMPLATES.md#smoke_test_reportjson)
3. **P0 门控判定**：
   - `defect_list.json` 中 `priority == "P0"` 的缺陷数 > 0 → `verdict: "fail"`，`fail_reason` 列出 P0 缺陷摘要
   - P0 缺陷数 == 0 → `verdict: "pass"`
4. **Chat 输出冒烟测试结论**：

```
冒烟测试结论：{verdict}
- 验证点：{total_points} 个（通过 {passed}，失败 {failed}，待定 {inconclusive}）
- 缺陷：{total_defects} 个（P0: {p0}, P1: {p1}, P2: {p2}）
{如有排除项: "- 排除项：{excluded_count} 个（MR 流程状态相关，不计入缺陷）"}
{如 verdict == "fail": "P0 缺陷列表：\n" + 逐条列出 P0 缺陷名称}
```

## 阶段 5: loop - 回溯自循环（条件触发）

> Mode 触发条件以 [SKILL.md mode dispatch 表](SKILL.md#mode-dispatch单一权威表其余-phases-段落只引用本表) 为准（标准模式且存在 missing/partial 时进入；smoke-test 模式不进）。

标准模式下，当 traceability_coverage_report.json 存在 `missing` 或 `partial` 状态的需求点时，自动进入缺口修复循环。

### 5.0 触发判定

回读 `traceability_coverage_report.json`，检查以下条件：

1. `gaps` 数组中是否存在 `status == "missing"` 或 `status == "partial"` 的条目
2. 如果 gaps 为空 → **跳过 Phase 5**（**注意：仍然进 Phase 6 writeback**，与 5.4 D4 规则一致——loop 是缺口修复机制，不是 writeback 的前置条件）
3. 如果存在缺口 → 进入 5.1

### 5.1 缺口分类

对每个缺口（gap）进行分类，确定修复方式：

| 缺口类型 | 判定条件 | 修复方式 |
| --- | --- | --- |
| 实现缺失 | 需求点在代码中完全无对应变更 | 需要补充代码实现 |
| 实现不完整 | 需求点有部分实现但不完整 | 需要补充缺失的代码逻辑 |
| 追溯失败 | 实现可能存在但 AI 未能识别映射 | 用户确认映射关系后标记为 covered |
| 需求变更 | 需求点已废弃或延期 | 用户确认后标记为 `deferred` |

将分类结果追加到 `traceability_coverage_report.json` 的 `gap_classification` 字段。

### 5.2 用户确认

将缺口分类结果和修复建议输出给用户，等待确认：

```markdown
## 回溯缺口汇总

| 编号 | 需求点 | 缺口类型 | 建议动作 |
| --- | --- | --- | --- |
| R3 | 密码强度校验 | 实现缺失 | 需补充代码实现 |
| R5 | 导出功能 | 追溯失败 | 请确认映射关系 |

请确认以上分类是否正确，并指示下一步动作：
1. 修复缺口（补充实现后重跑回溯）
2. 标记为延期（从当前覆盖率统计中排除）
3. 手动确认映射（修正 AI 追溯结果）
```

**该提问必须通过 AskUserQuestion 工具发出**（不能仅在 chat 输出后续等待），option 提供上述 3 个动作 + 第 4 个元操作「停止自循环（输出当前状态）」。

**「用户终止」判定标准**（替代旧的"无响应"模糊措辞）：
- 用户在 AskUserQuestion 选择第 4 项「停止自循环」→ 立即退出，`exit_reason: "user_terminated"`
- 用户回复中明确包含"停止 / 取消 / 不修了 / 算了 / 就这样"等终止意图 → 同上
- 用户回复无法解析（如返回非选项内容且无明确意图）→ **不要静默退出**，再次发起 AskUserQuestion 澄清意图（最多 1 次）；澄清后仍不可解析才退出，`exit_reason: "user_terminated"` + 在 loop_metadata 标 `last_response_unparseable: true`
- **不存在"超时无响应"概念** — Skill 内不做计时；上层会话框架决定何时打断

### 5.3 增量重跑

用户确认修复后：

1. 仅对**用户确认需要重新追溯的需求点**执行增量分析（不重跑全量）
2. 重新获取相关代码变更的最新 diff（代码可能已更新）
3. 使用与 Phase 3.2 一致的验证方式（按 3.1 输入路由优先级消费 `final_cases.json` / `requirement_points.json`），仅对修复的需求点对应的用例增量执行。forward-tracer agent 仅在与首次全量验证相同的降级条件触发时才使用
4. 合并增量结果到 `traceability_matrix.json` 和 `traceability_coverage_report.json`
5. 回到 5.0 重新判定缺口

### 5.4 收敛与退出

自循环的退出条件（满足任一即退出）：

1. **全部覆盖**：所有需求点状态为 `covered` 或 `deferred` → 输出最终报告
2. **达到最大轮次**：默认最大 3 轮（通过 contract.yaml 已声明的 `max_loop_iterations` 输入参数调整），超过后强制退出并在报告中标注未收敛的缺口
3. **无进展**：本轮与上轮的缺口列表完全一致（无新覆盖的需求点）→ 强制退出，标注为"需人工介入"
4. **用户主动终止**：用户在 5.2 步骤选择停止

> **D4 — 退出后总是进 Phase 6**：无论 `exit_reason` 是哪个，只要 `forward_verification.json` 存在（4.6a 已校验通过），**Phase 6 writeback 仍必须执行**。理由：
> - `all_covered` → 全部 pass，正常 writeback 把所有 case 标 MS Pass
> - `max_iterations` / `no_progress` → 还有未覆盖的缺口，但已验证的部分仍要回写让 QA 看到
> - `user_terminated` → 用户决定停止 loop 不代表放弃 writeback；如用户也不想 writeback，Phase 6.1.b 软警告里再让用户决定
>
> **绝不要**「loop 没收敛 → 跳过 writeback」——loop 是缺口修复机制，不是 writeback 的前置条件。

退出时更新 `traceability_coverage_report.json` 的 `loop_metadata` 字段：

```json
{
  "loop_metadata": {
    "iterations_run": 2,
    "max_iterations": 3,
    "exit_reason": "all_covered | max_iterations | no_progress | user_terminated",
    "unresolved_gaps": ["R3"]
  }
}
```

## 阶段 6: writeback - MS 测试计划回写

> Mode 触发条件以 [SKILL.md mode dispatch 表](SKILL.md#mode-dispatch单一权威表其余-phases-段落只引用本表) 为准（标准模式且 `ms_plan_info.json` 存在时执行；smoke-test 模式不写 MS，避免污染测试计划状态）。
>
> **执行时机**：标准模式下，4. output 完成后立即进入；如果触发了 5. loop，等 loop 收敛退出后再进。

### 6.1 前置校验

#### 6.1.a 硬约束

1. **fv 完整性**：确认 `$TEST_WORKSPACE/forward_verification.json` 存在、非空、且通过 4.6a `validate-fv` 校验。
   - 4.6a 已强制校验；正常路径走到这里都满足
   - 如某种异常导致缺失：last-resort 回到 4.6 兜底合成；如 `traceability_coverage_report.json` 也缺失则在最终摘要明确告警"无验证结果可回写"，**不允许静默跳过**

#### 6.1.b 软依赖（缺即整个 Phase 6 优雅 skip，与 1.3.b 对齐）

2. **mapping 完整性**：检查 `$TEST_WORKSPACE/ms_case_mapping.json`：
   - 存在 → 继续（sha 一致性 1.3.a 已硬阻断校验）
   - 不存在 → **优雅 skip 整个 Phase 6**，标 `writeback_skipped: "missing_ms_case_mapping"`，提示「先跑 `metersphere-sync mode=sync` 生成 mapping」
3. **plan_id 必须就位**：writeback-from-fv 需要 `plan_id` 入参，**不会创建 plan**。检查 `$TEST_WORKSPACE/ms_plan_info.json` 是否存在：
   - 存在 → 提取 `plan_id` 用于 6.2
   - 不存在 → **优雅 skip 整个 Phase 6**，**不 STOP**：
     - 在最终摘要中明确标 `writeback_skipped: "missing_ms_plan_info"`
     - 提示用户：「ms_plan_info.json 不存在；本次未写 MS。如需写 MS，请补跑 `metersphere-sync mode=sync` 完成测试计划创建后重跑本 skill 的 Phase 6（fv 已落盘可直接复用）」

> **D10 一致性**：mapping 缺失和 plan_info 缺失走相同路径——优雅 skip Phase 6 + 明确 `writeback_skipped` 标记。**绝不**一个 STOP 一个 skip。
>
> **设计哲学**：1.3.b 早期已经警告过用户。如果用户依然跑到这里说明他可能就不想 writeback（只要 coverage report）。1.3.b warn + 6.1.b skip 的组合解决「白跑 4 phase 才 stop」的体验问题（D3）和「纯 coverage 用户被强制走 sync」的封锁问题（D10）。

### 6.2 调用 helper.writeback-from-fv（直接调脚本，不再走 Skill）

> **历史变更**：旧版本写「通过 Skill 工具调用 `test:metersphere-sync` mode=execute」。**这条路径在实践中跑不通**——单会话只能调一个 skill，traceability 内部不能再 Skill() 调 metersphere-sync。
>
> 新路径：直接调 `metersphere_helper.py writeback-from-fv` 共享脚本。helper 是工具脚本，不是 skill，不受单会话约束。状态映射 / 三级查找 / 幂等 / 重试 / 报告全部封装在脚本里。

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  writeback-from-fv \
  --plan-id <plan_id from ms_plan_info.json> \
  --fv-path $TEST_WORKSPACE/forward_verification.json
# 第一次跑或大改后建议加 --dry-run 先看一遍
```

helper 内部完成：

1. **fv schema 校验**（与 4.6a 同一套，重跑兜底）
2. **三级查找** `case_id → ms_id → plan_case_id`（基于 `ms_case_mapping.json`）
3. **P6 状态映射**：
   - `pass` + `external_dependencies.types` 空 → MS `Pass`
   - `pass` + `external_dependencies.types` 非空 → MS **`Prepare`**（不再 Pass + caveat）
   - `fail` → MS `Failure`
   - `inconclusive` → MS `Prepare`
4. **幂等比对**：当前 MS 状态 == target → skip 记 unchanged
5. **retry**：retriable 错误（5xx / network）单次内自动重试 1 次
6. **三个产物**（自动落盘到 `$TEST_WORKSPACE/`）：
   - `ms_sync_report.json` — 完整明细 + summary
   - `forward_verification.enriched.json` — 原 fv + 回写后的 ms_id（下次跑可跳过 lookup）
   - `pass_with_caveats.md` + `pending_external_validation.md` — 给 QA 的人话清单

### 6.3 完成校验 + chat 摘要

1. 确认 `$TEST_WORKSPACE/ms_sync_report.json` 已生成且非空
2. 从 `summary.by_target_status` 提取 Pass/Prepare/Failure；从 fv 统计 inconclusive_reason 分组
3. **按情形选 chat 模板**（详见 [Recovery Cookbook](../_shared/RECOVERY.md)）：

| 情形 | 模板 |
| --- | --- |
| 常态（Pass 或 Failure 占多数） | [R-P6-NORMAL](../_shared/RECOVERY.md#r-p6-normal--phase-63-常态摘要模板) |
| `by_target_status.Pass == 0 && Failure == 0`（全 Prepare） | [R-P6-3](../_shared/RECOVERY.md#r-p6-3--fv-全-inconclusive-警示摘要d7) |
| Phase 6 被 6.1.b 优雅 skip | [R-P6-1](../_shared/RECOVERY.md#r-p6-1--missing-ms_case_mappingd10) 或 [R-P6-2](../_shared/RECOVERY.md#r-p6-2--missing-ms_plan_infod3) |

### 6.4 失败处理

helper 调用 exit code != 0 → stderr 是结构化 JSON，按 `type` 走 [Recovery Cookbook](../_shared/RECOVERY.md)：

| stderr.type | R-code |
| --- | --- |
| `precondition_failed` / `not_found`（mapping/plan_info 缺失） | [R-P6-1 / R-P6-2](../_shared/RECOVERY.md#10-r-p6phase-6-整段优雅-skip应用-p-skip-phase) |
| `stale_mapping` | [R-PRE-2](../_shared/RECOVERY.md#r-pre-2--mapping-sha-不一致硬阻断) |
| `validation`（fv 不合规） | [R-VFV-* + R-VFV-STOP](../_shared/RECOVERY.md#2-r-vfvvalidate-fv-校验失败) |
| `api_error` 不可重试 | [R-WB-3](../_shared/RECOVERY.md#r-wb-3--api_error-不可重试) |
| `network` 可重试 | [R-WB-4](../_shared/RECOVERY.md#r-wb-4--network-持续失败) |

writeback report.failed 非空 → exit 1。失败的 case 在 `ms_sync_report.json.failed[]` 里逐条列出 `error_type`，按上表分流。
