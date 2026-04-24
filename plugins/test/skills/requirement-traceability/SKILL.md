---
name: requirement-traceability
description: >
  双向追溯需求与代码变更的映射关系，回答"代码到底有没有把需求做完、做对、不多做"。
  输入需求描述 + 代码变更（MR/PR 链接、本地 diff 文件、或粘贴的 diff 文本），
  输出 traceability_matrix.json + traceability_coverage_report.json + risk_assessment.json
  + forward_verification.json；smoke-test 模式额外产出 defect_list.json + smoke_test_report.json
  并对 P0 缺陷做硬门控。
  当用户想验证某个 MR/PR 是否真把需求实现了、做合并/上线前的最后核对、跑冒烟、做回归核查、
  或质疑"这次改的代码和 PRD 对得上吗"时，就该用本 skill — 即使用户没明说"追溯"或
  "traceability"，只要场景是"代码 ↔ 需求双向核对"就触发。
  典型触发表述：「这个 MR 做完了吗」「上线前再核一遍」「冒烟一下」「跑下回归」
  「PRD 和实现对得上吗」「这次改动有没有漏」「需求回溯」「追溯矩阵」「需求还原度」
  「代码覆盖（指代码是否覆盖需求，非测试代码覆盖率）」「实现验证」「traceability」。
  不适用于：纯代码层影响面分析（用 change-analysis）、用例质量评审（用 test-case-review）、
  生成新用例（用 test-case-generation）。
---

# 需求回溯

## Quick Start

- Skill 类型：核心工作流
- 适用场景：功能开发完成后，验证代码变更是否完整覆盖需求；**smoke-test 模式**下可作为冒烟测试验证引擎
- 必要输入：代码变更（MR/PR 链接、本地 diff 文件、或直接提供 diff 文本）必须非空；需求描述推荐提供，缺失时基于代码变更做单边追溯（降级模式）
- 输出产物：`traceability_matrix.json`、`traceability_coverage_report.json`、`risk_assessment.json`、`forward_verification.json`（正向用例中介验证结果）；标准模式且 mapping/plan_info 就位时额外输出 `ms_sync_report.json` + `forward_verification.enriched.json` + `pass_with_caveats.md` + `pending_external_validation.md`（writeback 阶段产出）；smoke-test 模式额外输出 `defect_list.json`、`smoke_test_report.json`
- 失败门控：代码变更为空时停止；mapping sha 不匹配时停止；fv schema 校验失败时停止；无法确认的映射标记为 `[推测]`；smoke-test 模式下 P0 缺陷 > 0 则 verdict = fail
- 执行步骤：`init → fetch → map → output(4.1-4.5) → 4.6 兜底 → 4.6a 校验 → 4.7 fail 复核 → writeback`（smoke-test 模式 output 后走 5S.1/5S.2 冒烟报告并跳过 4.7 / writeback；标准模式有未覆盖需求时在 output 后追加 Phase 5 自循环，收敛后再进 writeback；mapping/plan_info 缺失时 writeback 整段 graceful skip）
- **可能的用户交互（standard 模式）**：
  - **Phase 4.7 高 conf fail 复核**：每条 `result==fail && confidence>=80` 的 fv 条目触发一次 AskUserQuestion（A 保持 / B 改 Pass / C 改 inconclusive）。N 条高 conf fail 就是 N 次问询
  - **Phase 5 缺口确认**：每个 `missing/partial` 缺口聚合一次 AskUserQuestion 让用户分类
  - **如果 fv fail 多 + 缺口多，一次跑可能弹 N+M 次问题**。提前预告：跑大规模需求前可考虑 (a) 先跑 mode=smoke-test 走完整 4.x 不交互，看下大致情况，再切 standard；(b) 缩小 code_changes 范围分批跑

## 核心能力

- 代码变更分析 — 解析代码 diff，分类变更文件，识别变更类型和影响范围
- 双向追溯 — 需求 → 代码 和 代码 → 需求 的双向映射
- 覆盖缺口识别 — 找出未被代码实现的需求和未关联需求的代码变更
- API 契约感知 — 当代码变更涉及接口交互时，检查前后端定义是否一致
- 风险评估 — 基于缺口和变更复杂度评估残余风险

## 追溯原则

1. **双向验证** — 需求→代码 和 代码→需求 两个方向都要检查
2. **可追溯** — 所有结论有代码/数据依据，无法确认的标注为推测
3. **风险优先** — 优先关注高风险变更和覆盖缺口
4. **分治处理** — 多个代码变更逐个分析，每个完成后立即增量写入
5. **完整性验证** — 每阶段结束确认处理进度

置信度标记见 [CONVENTIONS](../../CONVENTIONS.md#置信度标记)。

## 双通道追溯模式

正向和反向使用不同的验证策略：

| 通道 | 方向 | 方法 | 回答的问题 |
| --- | --- | --- | --- |
| 正向通道 | 需求 → 代码 | 用例中介验证 | 需求是否被正确实现？ |
| 反向通道 | 代码 → 需求 | 直接代码追溯 | 代码有没有做需求之外的事？ |
| ↳ 契约感知 | 前端 ↔ 后端 | 接口签名交叉比对 | 前后端接口定义是否一致？（正向通道子步骤，条件触发） |

### 正向通道：用例中介验证

不直接拿需求去"匹配"代码，而是用具体的测试用例作为中介——AI 拿用例的"操作步骤 + 预期结果"逐条对照代码推理"代码是否真能实现这条用例"。

优势：迫使 AI 从"模糊映射"降维到"具体断言"，精度显著提升。

**用例输入按优先级消费**（详见 PHASES.md 3.1）：

1. **优先**：`final_cases.json`（上游 test-case-generation 产出）—— 直接拿 `steps[].action` 当 input、`steps[].expected` 当 expected
2. **降级**：`requirement_points.json` 的 `acceptance_criteria` —— 每条标准转 1-2 条简化用例
3. **最弱**：`traceability_checklist.md` 中的需求描述 —— 仅作为最后兜底

不再生成独立的"验证用例文件"作为中间产物（v0.0.7 起合并 verification-test-generation 能力，去掉这层冗余）。

### 反向通道：直接代码追溯

主 agent 内联完成（不调 Task sub-agent，详见 PHASES 3.3）—— 从代码变更出发，寻找每个变更对应的需求点。

优势：能检测"多余实现"和"范围蔓延"，这是正向通道无法做到的。

> agent 定义文件 `agents/requirement-traceability/reverse-tracer.md` 保留作为降级路径和未来扩展用，当前主路径不调度。

### UI 还原度检查（条件触发）

当需求有 Figma 设计稿链接时，正向通道额外执行 UI 还原度对比。使用 Figma MCP 分级获取设计数据（先 `figma_metadata` 探测结构，再 `figma_screenshot` 和 `figma_extract` 按需获取截图与布局数据），Browser MCP 获取实现截图/DOM，AI 对比差异。输出 `ui_fidelity_report.json`，合并到 `traceability_coverage_report.json`。

触发条件：`design_link` 存在且前端页面可在浏览器中访问。

### API 契约感知检查（条件触发）

当代码变更涉及 API 交互（网络请求路径、API 模型、请求参数等）时，正向通道额外执行轻量级前后端契约一致性检查。检查结果合并到 `traceability_coverage_report.json` 的 `api_contract` 字段。

触发条件（满足任一）：代码变更包含 API 相关文件、需求点涉及接口交互、同时存在前端和后端 MR。

检查内容：路径一致性、模型字段一致性、请求参数一致性。如提供了 `openapi_spec`，额外做 OpenAPI 基准校验。

与独立 skill 的关系：本 skill 内置的是轻量级检查，专注于从 diff 中提取接口签名并交叉比对。如需深度 schema 对比、breaking change 检测等，应使用独立的 `api-contract-validation` skill，其产出 `api_contract_report.json` 可作为上游输入直接消费，跳过内置检查。

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 主 agent（正向用例验证 + 反向代码追溯，M ≤ 3 时顺序内联） | Opus | 代码路径追踪与反向归因都需要深度推理 |
| case-tracer sub-agent（PHASES 3.2.dispatch，M > 3 时按模块拆并行） | Opus | 每个 sub-agent 携带受限上下文（一个模块的 cases + diff），减少主 agent 全量加载负担 |
| forward-tracer 降级 sub-agent（PHASES 3.2.4） | Opus | 仅在用例数据严重缺失时启动，需要从需求描述推断映射 |
| UI 还原度检查 Agent | Opus | 视觉和结构差异识别需要精确对比 |
| API 契约感知检查 | Sonnet | 接口签名提取和字段比对属于规则化处理 |
| 交叉验证和结果合并 | Sonnet | 规则化处理 |

## 可用工具

共享脚本（飞书/GitLab/GitHub）用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。以下为本 skill 特有工具：

### Figma MCP

仅当 fetch 阶段发现 Figma 链接时使用，按分级协议获取，详见 [shared-tools/SKILL.md](../shared-tools/SKILL.md#figma-设计稿获取)。

## 冒烟测试模式（mode=smoke-test）

当 `mode` 参数为 `smoke-test` 时，在标准回溯流程（init → fetch → map → output）完成后，追加执行缺陷提取和冒烟测试判定（详见 PHASES.md 的 5S.1 和 5S.2 步骤）：

- 从 `forward_verification.json` 的 fail 项、`traceability_coverage_report.json` 的 gaps、`api_contract.issues` 中提取缺陷
- 基于置信度和风险等级判定优先级（P0/P1/P2）
- **P0 门控**：P0 缺陷数 > 0 → `verdict: "fail"`（冒烟不通过）
- 额外输出：`defect_list.json`（结构化缺陷列表，含名称、优先级、实际结果、预期结果）+ `smoke_test_report.json`（冒烟测试报告含通过/不通过判定）
- smoke-test 模式下跳过 Phase 5 自循环（不做交互式缺口修复，直接输出最终结果）
- **评估范围界定**：冒烟测试评估的是 MR/PR diff 中代码变更的实现质量，不评估 CI/CD 流程状态。以下情况**不构成缺陷**：
  - MR/PR 处于 opened/draft 状态（未合并）
  - MR/PR 存在合并冲突
  - MR/PR 的 pipeline 状态（pending/failed/running）
  - MR/PR 的 review 状态（未审批/变更请求）

## 阶段流程

按以下阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证代码变更来源；标准模式额外校验 mapping precondition（详见 PHASES 1.3） | — |
| 2. fetch | 获取需求文档和代码 diff | `traceability_checklist.md` |
| 3. map | 正向（3.2）：M ≤ 3 主 agent 内联，M > 3 拆 case-tracer sub-agent 按模块并行；反向（3.3）：主 agent 内联 | `code_analysis.md`、`forward_verification.json`（M > 3 时含中间产物 `forward_verification.{module}.json`） |
| 4. output | 覆盖验证、风险评估和最终产出 | `traceability_matrix.json`、`traceability_coverage_report.json`、`risk_assessment.json` |
| 4.6 | `forward_verification.json` 兜底落盘（**last-resort**：3.2 已产出则跳过，否则从 coverage_report 合成；正常路径不应走到这里） | `forward_verification.json`（兜底版） |
| 4.6a | 强制 schema 校验 fv（`metersphere_helper.py validate-fv`） | — |
| 4.7 | 高 conf fail 复核（result==fail 且 conf≥80 → AskUserQuestion 逐条 ack；改判记 evidence.human_override） | 改写后的 fv |
| 5S.1 | 缺陷提取与优先级判定（**仅 smoke-test 模式**） | — |
| 5S.2 | 冒烟测试报告生成 + P0 门控（**仅 smoke-test 模式**） | `defect_list.json`、`smoke_test_report.json` |
| 5. loop | 回溯自循环：缺口分类 + 用户确认 + 增量重跑（**仅标准模式且存在 missing/partial**） | 更新 `traceability_coverage_report.json` 的 `loop_metadata` |
| 6. writeback | 调 `metersphere_helper.py writeback-from-fv` 把 fv 写回 MS plan（**仅标准模式**） | `ms_sync_report.json`、`forward_verification.enriched.json`、`pass_with_caveats.md`、`pending_external_validation.md` |

> 编号说明：`5S.x` 是 smoke-test 专用步骤（与 `5. loop` 并列、与 `4.x` 标准产出无嵌套关系），早期版本曾命名为 `4S.x` 已统一改为 `5S.x` 避免视觉混淆。

### Mode dispatch（单一权威表，其余 PHASES 段落只引用本表）

| 步骤 | `mode == "traceability"`（默认） | `mode == "smoke-test"` |
| --- | --- | --- |
| 1 init（含 1.3 precondition：1.3.a 硬阻断 final_cases/mapping_sha + 1.3.b 软警告 mapping/plan_info） | ✓（标准模式跑 1.3） | ✓（不跑 1.3，smoke 不写 MS） |
| 2 fetch | ✓ | ✓ |
| 3 map | ✓ | ✓ |
| 4 output（4.1–4.5） | ✓ | ✓ |
| 4.6 fv 兜底落盘（last-resort） | ✓ | ✓ |
| 4.6a fv schema 校验（强制） | ✓ | ✓ |
| 4.7 高 conf fail 复核（AskUserQuestion） | ✓ | ✗ 跳过（smoke 不交互修改 fv） |
| 5S.1 缺陷提取 | ✗ 跳过 | ✓ |
| 5S.2 冒烟报告 + P0 门控 | ✗ 跳过 | ✓ |
| 5 loop 自循环 | ✓（仅当存在 missing/partial） | ✗ 跳过（冒烟不做交互式修复） |
| 6 writeback MS 计划（调 `helper.writeback-from-fv`） | ✓（仅当 `ms_plan_info.json` 存在） | ✗ 跳过（冒烟不污染 MS 状态） |

PHASES.md 内涉及 mode 分支的段落（5S.1 / 5S.2 / 5.0 / 6.0）仅以一句"见 SKILL.md mode dispatch 表"引用本表，**不重复列条件**，避免散落不一致。

## ID 体系（单一权威表，TEMPLATES / PHASES 中的所有示例须遵守）

| 字段 | 取值规范 | 备注 |
| --- | --- | --- |
| `requirement_id` | 优先使用上游 FP-N（来自 `clarified_requirements.json` / `requirement_points.json`）；独立使用本 skill（无上游）时才用本地 R-N | 主键，跨 skill 关联用 |
| `case_id`（常态） | 直接复用上游 `final_cases.json` 的 `case_id`（如 `M1-TC-01`） | 用例中介验证产物 |
| `case_id`（降级用例） | `R-{requirement_id}-AC{N}`（acceptance_criteria 转出的简化用例） | 仅当无 final_cases.json 但有 requirement_points.json |
| `case_id`（forward-tracer 降级） | `FORWARD-TRACER-{requirement_id}` | PHASES 3.2.4 |
| `case_id`（4.6 兜底合成） | `FORWARD-TRACER-FP-{N}` | PHASES 4.6 |
| `defect.id` | `DEFECT-{N}`（5S.1 顺序生成） | smoke-test 模式 |

> 旧版本曾用 `VC-N`（独立 verification cases）作为 case_id —— v0.0.7 起合并 verification-test-generation 能力后已废弃，新代码不再写。

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `traceability_checklist.md` | fetch | 需求点和代码变更清单 |
| `code_analysis.md` | map | 逐代码变更的分析记录（含「reverse-tracer 输出（主 agent 内联）」节，由 3.3 写入） |
| `requirement_doc.md` | fetch（条件） | 在线获取的需求文档原文 |
| `ui_fidelity_report.json` | map 3.4（条件）/ 上游产出 | UI 还原度检查结果 |
| `api_contract_report.json` | map 3.2.5（条件）/ 上游产出 | API 契约一致性检查 |
| `ms_plan_info.json` | 上游 metersphere-sync sync 模式产出 | MS 测试计划信息（writeback 复用避免重查） |
| `ms_case_mapping.json` | 上游 metersphere-sync mode=sync 产出（v2 格式） | `case_id ↔ ms_id` 映射 + sha 元数据；writeback 三级查找的源 |
| `diff.txt` | 3.0（条件） | 大 diff 落盘后供 Agent Read |
| `forward_verification.enriched.json` | 6 writeback 产出 | 原 fv + 每条注入 `ms_id`，下次重跑 writeback 跳过 lookup |
| `pass_with_caveats.md` | 6 writeback 产出 | pass 但 ext_deps 非空（被降级为 MS Prepare）的条目清单 |
| `pending_external_validation.md` | 6 writeback 产出 | 同上数据按依赖类型（device/server/...）分组 |

## 与其他 skill 的关系

- **change-analysis**：侧重代码变更的影响面分析和测试覆盖评估。本 skill 侧重需求与代码的双通道追溯矩阵，可被 change-analysis 消费（change-analysis 可选引用本 skill 产出的追溯矩阵）
- **test-case-review**：专注已有测试用例的质量评审。本 skill 的覆盖缺口分析可为 test-case-review 提供补充视角
- **test-case-generation**：上游产出 `final_cases.json` 是本 skill 正向通道（用例中介验证）的优先输入，AI 拿用例的 `steps[].action / expected` 对照代码追踪
- **metersphere-sync**：本 skill 的 **Phase 6 writeback** **直接调** `metersphere_helper.py writeback-from-fv` 共享脚本（不调 `Skill(test:metersphere-sync)`——单会话只能调一个 skill）。helper 内部完成三级查找 + P6 状态映射 + 幂等比对 + 重试 + 报告生成。前置条件：上游必须已经跑过 `metersphere-sync mode=sync` 产出 `ms_case_mapping.json`（v2 格式）和 `ms_plan_info.json`。仅 `mode != "smoke-test"` 触发；冒烟测试模式不写 MS
- **冒烟测试工作流**：本 skill 的 smoke-test 模式作为冒烟测试的分析引擎，复用双通道追溯能力，追加缺陷提取和 P0 门控。工作流层通过 `mode=smoke-test` 参数触发

## Closing Checklist（CRITICAL）

skill 执行的最终阶段完成后，**必须**逐一验证以下产出文件：

**标准模式：**
- [ ] `traceability_matrix.json` — 非空，包含正向和反向追溯映射
- [ ] `traceability_coverage_report.json` — 非空，包含覆盖率统计和缺口列表
- [ ] `risk_assessment.json` — 非空，包含风险等级和建议
- [ ] `forward_verification.json` — **必须非空**：Phase 3.2 正常产出 → 用例级；Phase 3.2 偏离 → Phase 4.6 last-resort 兜底合成。**禁止以「降级路径」为由跳过**
- [ ] `forward_verification.json` 通过 4.6a `validate-fv` 校验（schema + boundary）。校验失败必须先修，**禁止带 bug fv 走到 writeback**
- [ ] **当 `ms_plan_info.json` + `ms_case_mapping.json` 都就位时**（即上游已完整跑过 mode=sync）：
  - [ ] `ms_sync_report.json` — Phase 6 writeback 已跑；helper 失败时 stderr 是结构化 JSON，错误透传给用户，不允许静默跳过
  - [ ] `forward_verification.enriched.json` — writeback 自动写
  - [ ] `pass_with_caveats.md` — 即使没有 caveat 条目也要落盘
  - [ ] `pending_external_validation.md` — 同上
- [ ] **当 `ms_plan_info.json` 或 `ms_case_mapping.json` 缺失时**（D10 graceful skip 路径）：
  - [ ] chat 摘要必须输出 `writeback_skipped: missing_ms_plan_info | missing_ms_case_mapping` 标记
  - [ ] 不要求产出 ms_sync_report / enriched fv / caveats md（Phase 6 整段被跳过）

**smoke-test 模式额外产出：**
- [ ] `defect_list.json` — 非空，包含缺陷列表和优先级
- [ ] `smoke_test_report.json` — 非空，包含 verdict 判定

全部必须项通过后，输出完成总结。如任一必须文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- **硬阻断条件**（任一不满足即 STOP）：代码变更非空；标准模式额外要求 final_cases.json 存在 + mapping sha 一致（如 mapping 存在）。详见 PHASES 1.3.a
- **软警告条件**（缺失不阻断，Phase 6 优雅 skip）：mapping / plan_info 不存在。详见 PHASES 1.3.b
- 需求文档缺失时继续分析（降级模式），基于代码变更做单边追溯
- 代码变更支持三种来源：MR/PR 链接（GitLab/GitHub）、本地 diff 文件、直接提供的 diff 文本
