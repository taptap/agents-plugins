---
name: api-contract-validation
description: >
  深度校验前后端 API 契约一致性。输入前端代码变更 + 后端代码变更（或 OpenAPI spec），
  输出 api_contract_report.json。
  触发：接口校验、API 对齐、前后端一致性、契约校验、Schema 对比、接口不匹配。
---

# API 契约校验

## Quick Start

- Skill 类型：独立校验工具
- 适用场景：前后端同步开发完成后，校验接口定义是否一致；也可在技术重构时独立使用
- 必要输入：前端代码变更（MR/PR 链接或本地 diff）必须非空；后端代码变更或 OpenAPI spec 至少提供一个
- 输出产物：`api_contract_report.json`
- 失败门控：前端代码变更为空时停止；无后端变更且无 OpenAPI spec 时降级为仅提取前端接口签名
- 执行步骤：`init → fetch → analyze → output`

## 核心能力

- Schema 对比 — 逐字段比较前端模型与后端 API 定义（OpenAPI spec 或后端代码）
- Breaking Change 检测 — 识别不向后兼容的变更（字段删除、类型变更、必填新增）
- 路径一致性 — 前端调用路径 vs 后端路由定义
- 请求/响应完整性 — 必填参数是否都传了，响应字段是否都处理了

## 校验原则

1. **三方对比** — 前端代码、后端代码、OpenAPI spec 三者做交叉校验（有几个校验几个）
2. **Breaking 优先** — 优先报告会导致运行时错误的 breaking change
3. **命名风格容忍** — snake_case ↔ camelCase 的自动转换不视为不一致（标注为信息级别）
4. **可追溯** — 每个问题关联到具体的 MR/文件/行号

## 与 requirement-traceability 的关系

本 skill 的产出 `api_contract_report.json` 可被 requirement-traceability 消费：

```
api-contract-validation → api_contract_report.json
  → requirement-traceability (Phase 3.1 检测上游文件 → Phase 4.4 合并到 traceability_coverage_report.json)
```

当 requirement-traceability 发现工作目录中存在 `api_contract_report.json` 时，跳过内置的轻量级契约检查（Phase 3.2.5），直接使用本 skill 的深度校验结果。

独立使用时（不在 pipeline 中），本 skill 可直接被调用来检查任意前后端代码变更的接口一致性。

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 接口签名提取 | Sonnet | 从 diff 中提取结构化数据，规则化处理 |
| Schema 深度对比 | Opus | 跨文件推理字段映射和类型兼容性 |
| Breaking Change 判定 | Opus | 需要理解向后兼容语义 |
| 报告生成 | Sonnet | 模板化输出 |

## 可用工具

共享脚本（飞书/GitLab/GitHub）用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。以下为本 skill 特有工具：

### OpenAPI spec 解析

直接 Read OpenAPI JSON/YAML 文件，提取 endpoint 定义。

## 阶段流程

按以下 4 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证输入，确认前后端变更来源 | — |
| 2. fetch | 获取前后端 diff 和 OpenAPI spec | `contract_checklist.md` |
| 3. analyze | 提取接口签名，交叉比对 | `contract_analysis.md` |
| 4. output | 汇总问题，生成报告 | `api_contract_report.json` |

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `contract_checklist.md` | fetch | 前后端变更文件清单和接口端点列表 |
| `contract_analysis.md` | analyze | 逐端点分析记录 |

## Closing Checklist（CRITICAL）

skill 执行的最终阶段（output）完成后，**必须**逐一验证以下产出文件：

- [ ] `api_contract_report.json` — 非空，包含 endpoints 分析和 overall_consistency 评级

全部必须项通过后，输出完成总结。如文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 前端代码变更必须非空，这是唯一的阻断条件
- 后端代码变更和 OpenAPI spec 都缺失时降级为仅提取前端接口签名（无法做一致性校验）
- 支持多种前端技术栈的模型格式（Swift Codable、TypeScript interface、Go struct 等）
