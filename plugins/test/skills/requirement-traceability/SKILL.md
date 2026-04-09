---
name: requirement-traceability
description: >
  双向追溯需求与代码变更的映射关系。输入需求描述 + 代码变更（MR/PR 或本地 diff），
  输出 traceability_matrix.json + traceability_coverage_report.json + risk_assessment.json。
  支持 smoke-test 模式：在回溯基础上提取缺陷列表并执行 P0 门控判定。
---

# 需求回溯

## Quick Start

- Skill 类型：核心工作流
- 适用场景：功能开发完成后，验证代码变更是否完整覆盖需求；**smoke-test 模式**下可作为冒烟测试验证引擎
- 必要输入：代码变更（MR/PR 链接、本地 diff 文件、或直接提供 diff 文本）必须非空；需求描述推荐提供，缺失时基于代码变更做单边追溯（降级模式）
- 输出产物：`traceability_matrix.json`、`traceability_coverage_report.json`、`risk_assessment.json`；smoke-test 模式额外输出 `defect_list.json`、`smoke_test_report.json`
- 失败门控：代码变更为空时停止；无法确认的映射标记为 `[推测]`；smoke-test 模式下 P0 缺陷 > 0 则 verdict = fail
- 执行步骤：`init → fetch → map → output`（smoke-test 模式在 output 阶段追加 4.6/4.7）

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

v0.0.10 引入双通道追溯，正向和反向使用不同的验证策略：

| 通道 | 方向 | 方法 | 回答的问题 |
| --- | --- | --- | --- |
| 正向通道 | 需求 → 代码 | 用例中介验证 | 需求是否被正确实现？ |
| 反向通道 | 代码 → 需求 | 直接代码追溯 | 代码有没有做需求之外的事？ |
| ↳ 契约感知 | 前端 ↔ 后端 | 接口签名交叉比对 | 前后端接口定义是否一致？（正向通道子步骤，条件触发） |

### 正向通道：用例中介验证

不直接拿需求去"匹配"代码，而是先将需求拆解为结构化验证用例（具体输入→预期输出），然后 AI 逐条对照代码推理。

优势：迫使 AI 从"模糊映射"降维到"具体断言"，精度显著提升。

正向通道消费上游 `verification-test-generation` 的 `verification_cases.json`。如果上游未执行，本 skill 内置极简验证点提取（每个需求点 1-2 个基本断言，足以完成基本正向追溯）。如需高质量多类型验证（含 functional/boundary/error/state 全覆盖 + 详细代码推理），推荐先运行 `verification-test-generation`。

### 反向通道：直接代码追溯

保持现有的 reverse-tracer Agent 模式 — 从代码变更出发，寻找每个变更对应的需求点。

优势：能检测"多余实现"和"范围蔓延"，这是正向通道无法做到的。

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
| 冗余对追溯 Agent（forward/reverse-tracer） | Opus | 追溯遗漏 = 需求缺口未被发现 |
| 正向用例中介验证 | Opus | 代码路径追踪需要深度推理 |
| UI 还原度检查 Agent | Opus | 视觉和结构差异识别需要精确对比 |
| API 契约感知检查 | Sonnet | 接口签名提取和字段比对属于规则化处理 |
| 交叉验证和结果合并 | Sonnet | 规则化处理 |

## 可用工具

共享脚本（飞书/GitLab/GitHub）用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。以下为本 skill 特有工具：

### Figma MCP

仅当 fetch 阶段发现 Figma 链接时使用，按分级协议获取，详见 [shared-tools/SKILL.md](../shared-tools/SKILL.md#figma-设计稿获取)。

## 冒烟测试模式（mode=smoke-test）

当 `mode` 参数为 `smoke-test` 时，在标准回溯流程（init → fetch → map → output）完成后，追加执行缺陷提取和冒烟测试判定（详见 PHASES.md 的 4.6 和 4.7 步骤）：

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
| 1. init | 验证输入，确认代码变更来源 | — |
| 2. fetch | 获取需求文档和代码 diff | `traceability_checklist.md` |
| 3. map | 双通道并行：正向用例验证 + 反向代码追溯 | `code_analysis.md` |
| 4. output | 覆盖验证、风险评估和最终产出 | `traceability_matrix.json`、`traceability_coverage_report.json`、`risk_assessment.json` |
| 4.6 | 缺陷提取与优先级判定（smoke-test 模式） | — |
| 4.7 | 冒烟测试报告生成 + P0 门控（smoke-test 模式） | `defect_list.json`、`smoke_test_report.json` |

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `traceability_checklist.md` | fetch | 需求点和代码变更清单 |
| `code_analysis.md` | map | 逐代码变更的分析记录 |

## 与其他 skill 的关系

- **change-analysis**：侧重代码变更的影响面分析和测试覆盖评估。本 skill 侧重需求与代码的双通道追溯矩阵，可被 change-analysis 消费（change-analysis 可选引用本 skill 产出的追溯矩阵）
- **test-case-review**：专注已有测试用例的质量评审。本 skill 的覆盖缺口分析可为 test-case-review 提供补充视角
- **冒烟测试工作流**：本 skill 的 smoke-test 模式作为冒烟测试的分析引擎，复用双通道追溯能力，追加缺陷提取和 P0 门控。工作流层通过 `mode=smoke-test` 参数触发

## Closing Checklist（CRITICAL）

skill 执行的最终阶段（output）完成后，**必须**逐一验证以下产出文件：

**标准模式：**
- [ ] `traceability_matrix.json` — 非空，包含正向和反向追溯映射
- [ ] `traceability_coverage_report.json` — 非空，包含覆盖率统计和缺口列表
- [ ] `risk_assessment.json` — 非空，包含风险等级和建议

**smoke-test 模式额外产出：**
- [ ] `defect_list.json` — 非空，包含缺陷列表和优先级
- [ ] `smoke_test_report.json` — 非空，包含 verdict 判定

全部必须项通过后，输出完成总结。如任一必须文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 代码变更必须非空，这是唯一的阻断条件
- 需求文档缺失时继续分析（降级模式），基于代码变更做单边追溯
- 代码变更支持三种来源：MR/PR 链接（GitLab/GitHub）、本地 diff 文件、直接提供的 diff 文本
