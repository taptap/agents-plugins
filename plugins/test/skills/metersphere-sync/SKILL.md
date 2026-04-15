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
- 必要输入：`final_cases.json` 或 `supplementary_cases.json`（至少一个）+ `plan_name`
- 输出产物：`ms_sync_report.json`（必须）、`ms_case_mapping.json`、`ms_plan_info.json`
- 失败门控：MS 连通性检查失败时停止；pycryptodome 未安装时停止
- 执行步骤：`init → import → plan → execute(可选) → output`

## 核心能力

- 用例导入 — 按 module 字段自动创建子模块，批量导入用例，打上 `AI 用例生成` 标签
- 测试计划管理 — 按需求名查找或创建测试计划（限定在 AI 工作流分类下），关联导入的用例
- 计划幂等 — 同名计划存在时追加用例，不存在时新建
- 验证回写 — 基于 verification_cases.json 的置信度和结果，自动标记高置信度 Pass/Failure 用例
- 冒烟测试联动 — 消费 smoke_test_report.json（requirement-traceability 产出），P0 缺陷时全量降级为 Prepare
- 人工标记 — 置信度不足的用例保持待执行状态，添加评论注明原因

## 两种执行模式

### mode=sync（默认）
导入用例 + 创建/复用测试计划 + 关联用例。适用于测试用例生成完成后的首次同步。

### mode=execute
在 sync 的基础上，增加验证结果回写。需要额外输入 `verification_cases.json`，可选输入 `smoke_test_report.json`。
适用于需求还原度检查完成后，将 AI 验证结果写回 MS 测试计划。当冒烟测试发现 P0 缺陷时，自动将所有用例降级为待人工验证。

## 工具调用

所有 MS 操作通过 `metersphere_helper.py` 脚本执行：

```bash
HELPER="$SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py"

# 连通性检查
python3 $HELPER ping

# 导入用例（自动按 module 分组创建子模块，--requirement 指定需求名作为父模块）
python3 $HELPER import-cases <parent_module_id> <cases.json> [--requirement <需求名>]

# 查找或创建测试计划
python3 $HELPER find-or-create-plan <plan_name> [--stage smoke]

# 关联用例到计划
python3 $HELPER add-cases-to-plan <plan_id> --case-ids id1,id2,...

# 更新用例执行结果
python3 $HELPER update-case-result <plan_case_id> <Pass|Failure|Prepare> \
  [--actual-result TEXT] [--comment TEXT]
```

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

## 置信度判定规则

| 条件 | MS 状态 | 评论 |
|------|---------|------|
| 所有关联 VC confidence >= 90 且 result=pass | `Pass` | AI 自动验证通过 |
| 任一 VC confidence >= 70 且 result=fail | `Failure` | 注明失败的 VC |
| 其余（置信度不足或 inconclusive） | `Prepare` | AI 置信度不足，需人工验证 |

## 详细阶段操作

详见 [PHASES.md](PHASES.md)。

## Closing Checklist（CRITICAL）

skill 执行的最终阶段完成后，**必须**逐一验证以下产出文件：

- [ ] `ms_sync_report.json` — 非空，包含导入结果和计划信息
- [ ] `ms_case_mapping.json` — 非空，包含用例 ID 映射
- [ ] `ms_plan_info.json` — 非空，包含测试计划信息

全部必须项通过后，输出完成总结。如文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。
