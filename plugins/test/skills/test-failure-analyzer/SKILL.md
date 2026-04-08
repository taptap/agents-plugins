---
name: test-failure-analyzer
description: >
  分析测试失败原因，分类为预期变化（需求导致）、回归问题（影响了不该影响的部分）或不稳定（环境/时序问题），
  并给出分类依据和推荐处理方案。支持 分析→修复→重测 自循环（最多 3 轮）。
  触发：测试失败、用例挂了、跑不过、失败分析、回归分析、flaky test。
---

# 测试失败分析

## Quick Start

- Skill 类型：测试门禁辅助
- 适用场景：单测/集成测试执行后有失败用例，需要 AI 分析失败原因并分类处理
- 必要输入：测试执行结果（失败用例列表 + 错误信息）+ 当前代码变更（diff）
- 输出产物：`failure_analysis.json`、`action_plan.md`
- 失败门控：测试执行结果为空时停止
- 执行步骤：`init → collect → classify → plan → loop`

## 核心能力

- **失败分类** — 将每个失败用例归类为预期变化、回归问题或不稳定
- **根因分析** — 结合代码 diff 和堆栈信息定位失败根因
- **行动建议** — 按分类给出具体、可执行的推荐处理方案
- **自循环支持** — 分析→修复→重测 闭环迭代，最多 3 轮，自动检测收敛

## 分类判断标准

| 分类 | 判断依据 | 典型场景 | 推荐动作 |
| --- | --- | --- | --- |
| 预期变化 | 失败断言与本次需求变更直接相关 | 业务逻辑变了，旧测试的预期值过时 | 更新测试预期 → 用户确认 |
| 回归问题 | 失败测试与本次变更无直接关联 | 改了 A 模块，B 模块的测试挂了 | 分析根因 → 按严重程度处理 |
| 不稳定 | 同一测试时过时不过、依赖外部资源 | 网络超时、时序竞争、随机数据 | 自动重试 1 次 → 仍失败则上报 |

### 分类决策流程

对每个失败用例，按以下顺序判定：

1. **提取失败信息**：测试名、文件路径、错误消息、堆栈
2. **关联 diff**：检查失败断言/错误路径是否涉及 diff 中修改的代码
3. **判定路径**：
   - 失败代码路径与 diff 有直接关联 → **预期变化**
   - 失败代码路径与 diff 无直接关联 → **回归问题**
   - 错误特征匹配不稳定模式（超时、网络、随机数据、并发竞争）→ **不稳定**
4. **置信度评分**：按 [CONVENTIONS.md](../../CONVENTIONS.md#量化置信度评分) 标准打分

### 不稳定测试识别模式

以下特征命中任意一项即为不稳定候选：

| 特征 | 示例 |
| --- | --- |
| 超时错误 | `context deadline exceeded`、`timeout`、`timed out` |
| 网络依赖 | `connection refused`、`dial tcp`、`ECONNRESET` |
| 时序竞争 | `race condition`、`concurrent map`、结果随运行时间变化 |
| 随机/环境依赖 | 依赖当前时间、随机数种子、临时文件路径 |
| 历史波动 | 同一测试在上一轮迭代中通过但本轮失败（无代码变更） |

## 自循环协议

本 skill 支持 分析→修复→重测 自循环，用于迭代收敛失败数。

- **最大迭代次数**：3
- **每次修复后必须让用户确认**，未经确认不自动执行修改
- **收敛判断**：第 N+1 次失败数 ≥ 第 N 次 → 停止循环（不收敛）；即使失败数减少，如出现新增失败（上轮不存在的 test_name）→ 标记为「部分收敛 + 新增回归」，不计为完全收敛
- **终止条件**（满足任一即退出）：
  1. 全部测试通过
  2. 达到最大迭代次数（3 轮）
  3. 不收敛（失败数未减少）
  4. 用户主动终止

### 迭代状态追踪

每轮迭代更新 `failure_analysis.json` 中的 `iteration` 字段和 `summary.convergence`，供下一轮判断。

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 根因分析（diff ↔ 失败关联） | Opus | 误判根因会导致错误修复方向，代价极高 |
| 失败分类 | Sonnet | 规则化判定，Sonnet 性价比高 |
| 行动方案生成 | Sonnet | 模板化输出 |

## 阶段流程（5 阶段）

详见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 校验测试执行结果可用，确认迭代轮次 | — |
| 2. collect | 解析测试输出，提取失败用例和代码 diff | `raw_failures.md` |
| 3. classify | 逐个失败用例分类并打置信度 | — |
| 4. plan | 生成分类结果和行动方案 | `failure_analysis.json`、`action_plan.md` |
| 5. loop | 执行修复→重测→收敛检查，决定继续或终止 | 更新 `failure_analysis.json` |

## 输出格式

### failure_analysis.json

```json
{
  "iteration": 1,
  "total_failures": 5,
  "classification": {
    "expected_change": [
      {
        "test_name": "TestApplyCoupon_MaxDiscount",
        "test_file": "coupon_test.go",
        "error_message": "expected 100 but got 50",
        "related_change": "修改了优惠券最大抵扣逻辑",
        "confidence": 90,
        "recommended_action": "update_test_expectation",
        "suggested_fix": "将预期值从 100 改为 min(coupon, order)"
      }
    ],
    "regression": [
      {
        "test_name": "TestOrderTotal_WithTax",
        "test_file": "order_test.go",
        "error_message": "expected 110 but got 105",
        "root_cause": "优惠券逻辑修改影响了税费计算的输入值",
        "impact_scope": "订单模块税费计算",
        "severity": "high",
        "confidence": 85,
        "recommended_action": "fix_regression",
        "suggested_fix": "在 calculateTax 中使用折扣前原价作为税基"
      }
    ],
    "flaky": [
      {
        "test_name": "TestNotification_Send",
        "test_file": "notification_test.go",
        "error_message": "context deadline exceeded",
        "flaky_pattern": "timeout",
        "confidence": 75,
        "recommended_action": "retry_then_report",
        "suggested_fix": "增加超时时间或 mock 外部通知服务"
      }
    ]
  },
  "summary": {
    "expected_change_count": 2,
    "regression_count": 2,
    "flaky_count": 1,
    "convergence": true
  }
}
```

### action_plan.md

按分类分区输出行动方案：

```markdown
# 测试失败处理方案（第 N 轮）

## 概要

- 总失败数：X
- 预期变化：X 个
- 回归问题：X 个
- 不稳定：X 个

## 一、预期变化（需更新测试预期）

### 1. TestApplyCoupon_MaxDiscount (coupon_test.go)
- **失败原因**：修改了优惠券最大抵扣逻辑，旧预期值过时
- **关联变更**：`coupon.go` 第 42 行
- **建议修复**：将预期值从 100 改为 min(coupon, order)
- **置信度**：90 [已确认]

## 二、回归问题（需分析根因）

### 1. TestOrderTotal_WithTax (order_test.go) — 严重程度: HIGH
- **失败原因**：优惠券逻辑修改影响了税费计算的输入值
- **影响范围**：订单模块税费计算
- **根因分析**：calculateTax 使用了折扣后价格作为税基
- **建议修复**：在 calculateTax 中使用折扣前原价作为税基
- **置信度**：85 [基于 diff]

## 三、不稳定测试

### 1. TestNotification_Send (notification_test.go)
- **失败模式**：timeout
- **建议**：自动重试 1 次；仍失败则上报
- **长期修复**：增加超时时间或 mock 外部通知服务
- **置信度**：75 [基于 diff]

## 下一步

- [ ] 确认预期变化的测试更新
- [ ] 评审回归问题的修复方案
- [ ] 确认不稳定测试处理方式
```

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `raw_failures.md` | collect | 原始失败用例列表（测试名、文件、错误、堆栈） |
| `failure_analysis.json` | plan | 分类结果（每轮更新） |
| `action_plan.md` | plan | 处理方案（每轮更新） |

## Closing Checklist（CRITICAL）

skill 执行的最终阶段完成后，**必须**逐一验证以下产出文件：

- [ ] `failure_analysis.json` — 非空，包含各失败用例的分类（expected_change / regression / flaky）
- [ ] `action_plan.md` — 非空，包含各分类的处理方案和下一步清单

全部必须项通过后，输出完成总结。如任一必须文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- 测试执行结果为空时直接停止，不做任何分析
- 每轮修复必须经用户确认后才执行，禁止自动修改代码
- 回归问题中 severity 为 high 的仅输出修复建议，不自动修复
- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 置信度标记和评分标准见 [CONVENTIONS.md](../../CONVENTIONS.md#置信度标记)
