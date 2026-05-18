# 下游消费契约

本文档定义 change-analysis 产物被哪些下游 skill / 服务消费、以及哪些字段是**下游强依赖**（动则触发下游故障）vs **下游不强依赖**（命名风格自由）。

## requirement-traceability（标准 traceability 模式 + smoke-test 模式均适用）

通过其 PHASES §3.1 优先级 1.5 档**自动消费** `change_supplementary_cases.json` 作为补充用例池。

### 字段契约

| 字段 | 强依赖性 | 下游用途 | 改动注意事项 |
| --- | --- | --- | --- |
| `case_id` | ⚠️ 强依赖 | requirement-traceability 不重命名，下游引用安全 | 命名空间 `TC-{N}` 必须保持稳定 |
| `priority` | ⚠️ 强依赖 | requirement-traceability §5S.1 直接继承用于缺陷优先级判定（不再用 confidence 二次推） | 必须如实标注，例如 GameJam TC-11 标 P0 才能在下游 smoke-test 中正确进 P0 `defect_list` |
| `module` | ✅ 不强依赖 | 仅作生成阶段的代码风险点标签，便于人类阅读 | 命名风格自由，无需强行对齐功能点名 |
| `title` + `steps` + `preconditions` | ⚠️ 强依赖 | requirement-traceability 主要从这三项的业务语义匹配 FP-N（详见其 PHASES §3.1） | 写得越像真实测试步骤，匹配越准 |

### metersphere-sync 在 change_analysis 路径下的特殊处理

- 在 change_analysis 路径下，metersphere-sync 会 `flatten_into_wrapper=True`，把所有用例 flatten 进单一 wrapper 模块，**不按 `module` 字段分组**
- 详见 ai-case 后端 `apps/code_analysis/services/metersphere_import.py`

## test-case-generation

本 skill 的补充用例是**针对变更覆盖缺口**的补充，完整的需求驱动用例生成请使用 test-case-generation。

## ai-case 后端 `extract_story_output`

通过 `ca_summary.json` 消费，向下游 TC 生成 prompt 注入 `changed_modules` / `risk_breakdown` / `new_features` 三类摘要。schema 详见 [../../commons/contracts/ca-summary.schema.json](../../commons/contracts/ca-summary.schema.json)。

## 飞书卡片通知

通过 `change_analysis.json` 的 `key_findings` + `action_items` 字段生成卡片摘要文案。这两个字段长度建议控制在每条 80 字以内。
