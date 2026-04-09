---
name: verification-test-generation
description: >
  从需求功能点生成结构化验证用例（具体输入→预期输出），供 AI 逐条对照代码推理验证需求实现。
  当前阶段为 AI 推理验证；未来可渐进升级为可执行自动化测试。
  触发：验证测试、验收测试、冒烟测试、需求验证、代码验证、实现验证、验收用例、smoke test、冒烟用例。
---

# 验证用例生成

## Quick Start

- Skill 类型：需求回溯辅助
- 适用场景：需求实现完成后，生成结构化验证用例用于验证代码是否正确实现需求
- 必要输入：需求功能点（`requirement_points.json` 或上游澄清结果）+ 代码实现路径/diff
- 输出产物：`verification_cases.json`、`verification_report.json`
- 失败门控：需求功能点为空时停止；无法获取代码实现时降级为纯用例生成（不做验证推理）
- 执行步骤：`init → analyze → generate → verify → report`

## 核心能力

- 结构化用例生成 — 从需求功能点自动生成带具体输入和预期输出的验证用例，非自然语言描述
- 具体化输入/输出 — 每条用例包含可量化的参数和预期结果，支持 AI 推理或未来的自动化执行
- 代码路径追溯 — AI 逐条用例追踪代码执行路径，判断实际输出是否匹配预期
- 需求类型适配 — 前端、后端、API 分别采用不同的用例生成策略和验证方式

## 验证用例生成原则

1. **具体化** — 每条用例的输入必须是确定的数值/参数/操作，预期输出是可判定的结果，禁止模糊描述如「应正常工作」
2. **可追踪** — 每条用例关联到具体需求功能点 ID，验证结果可追溯到代码路径
3. **分需求类型** — 根据需求类型（前端交互/后端逻辑/API 接口）选择合适的用例策略
4. **覆盖多维度** — 每个功能点至少覆盖正向、边界、异常三类用例
5. **渐进可升级** — 当前阶段用例供 AI 推理验证，但用例结构兼容未来升级为可执行测试

置信度标记见 [CONVENTIONS](../../CONVENTIONS.md#置信度标记)。

## 需求类型与用例策略

| 需求类型 | 输入形式 | 预期输出形式 | 验证方式 |
| --- | --- | --- | --- |
| 后端逻辑 | 函数参数、数据库状态、配置值 | 返回值、状态变更、副作用 | 追踪函数调用链，验证返回值和状态 |
| API 接口 | HTTP method + path + headers + body | 响应 status + body + headers | 对照接口实现代码验证请求处理逻辑 |
| 前端交互 | 用户操作（点击/输入/导航）+ 页面状态 | UI 元素可见性、组件状态、路由变化 | 追踪事件处理和状态管理代码 |
| 数据处理 | 输入数据集、配置参数 | 输出数据集、转换结果 | 追踪数据处理管线的转换逻辑 |

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 代码分析和执行路径追踪（verify 阶段） | Opus | 代码推理错误 = 验证结论不可信 |
| 需求功能点解析和用例生成（analyze + generate 阶段） | Sonnet | 结构化生成，Sonnet 性价比高 |
| 报告汇总（report 阶段） | Sonnet | 规则化聚合 |

## 可用工具

共享脚本（飞书/GitLab/GitHub）用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。以下为本 skill 特有工具：

### 1. Figma MCP

前端需求时结合设计稿生成 UI 交互类验证用例，按分级协议获取，详见 [shared-tools/SKILL.md](../shared-tools/SKILL.md#figma-设计稿获取)。

### 2. 子 Agent: verification-test-writer

通过 Task 工具调用，为单个功能点并行生成验证用例。当功能点 >= 3 个时启动并行生成。Task prompt 中包含功能点详情和代码实现信息，子 Agent 独立生成该功能点的所有验证用例。

## 阶段流程

按以下 5 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 确认输入来源，判定需求类型和代码可用性 | — |
| 2. analyze | 解析功能点和代码实现，识别可验证断言 | `verification_checklist.md` |
| 3. generate | 按功能点生成结构化验证用例 | `fp_{N}_cases.json`（中间文件） |
| 4. verify | AI 逐条追踪代码逻辑，判定 pass/fail/inconclusive | `verification_cases.json` |
| 5. report | 汇总验证结果，生成覆盖统计和风险报告 | `verification_report.json` |

## 输出格式

### verification_cases.json

```json
[
  {
    "case_id": "VC-1",
    "requirement_id": "FP-1",
    "requirement_name": "优惠券金额计算",
    "case_type": "functional | boundary | error | state",
    "input": {
      "description": "优惠券金额 100 元，订单金额 50 元",
      "params": {"coupon_amount": 100, "order_amount": 50}
    },
    "expected": {
      "description": "实际抵扣金额应等于订单金额",
      "assertion": "actual_discount == 50"
    },
    "verification": {
      "method": "ai_reasoning | executable",
      "result": "pass | fail | inconclusive",
      "trace": "applyCoupon() -> min(coupon, order) -> min(100, 50) -> 50 == expected 50",
      "confidence": 90
    }
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `case_id` | string | 是 | 验证用例编号，格式 `VC-{N}`（全局递增） |
| `requirement_id` | string | 是 | 关联的需求功能点 ID（来自上游 `requirement_points.json`） |
| `requirement_name` | string | 是 | 功能点名称 |
| `case_type` | string | 是 | 用例类型：`functional`（正向）/ `boundary`（边界）/ `error`（异常）/ `state`（状态） |
| `input.description` | string | 是 | 输入的自然语言描述 |
| `input.params` | object | 是 | 结构化输入参数，键值对形式 |
| `expected.description` | string | 是 | 预期结果的自然语言描述 |
| `expected.assertion` | string | 是 | 可判定的断言表达式 |
| `verification.method` | string | 是 | 验证方式：`ai_reasoning`（AI 推理）/ `executable`（可执行） |
| `verification.result` | string | 是 | 验证结果：`pass` / `fail` / `inconclusive` |
| `verification.trace` | string | 是 | 代码追踪路径（AI 推理时为推理链，可执行时为执行日志） |
| `verification.confidence` | number | 是 | 验证置信度（0-100） |

### verification_report.json

```json
{
  "summary": {
    "total_cases": 15,
    "passed": 10,
    "failed": 3,
    "inconclusive": 2,
    "verification_rate": "86.7%",
    "verification_method": "ai_reasoning",
    "avg_confidence": 82
  },
  "per_requirement": [
    {
      "requirement_id": "FP-1",
      "requirement_name": "优惠券金额计算",
      "total_cases": 5,
      "passed": 4,
      "failed": 1,
      "inconclusive": 0,
      "coverage_assessment": "充分",
      "risk_level": "low",
      "failed_cases": ["VC-3"],
      "notes": "边界条件 VC-3 未正确处理优惠券金额为 0 的情况"
    }
  ],
  "confidence_distribution": {
    "high_90_100": 6,
    "medium_70_89": 5,
    "low_50_69": 3,
    "very_low_below_50": 1
  },
  "risk_areas": [
    {
      "requirement_id": "FP-2",
      "risk": "全部用例为 inconclusive，代码实现不可达",
      "recommendation": "需人工确认代码路径"
    }
  ],
  "gaps": [
    {
      "requirement_id": "FP-4",
      "issue": "未生成任何验证用例",
      "reason": "功能点描述过于模糊，无法提取可验证断言"
    }
  ]
}
```

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `verification_checklist.md` | analyze | 功能点清单、代码实现摘要、可验证断言列表 |
| `fp_{N}_cases.json` | generate | 单个功能点的验证用例（子 Agent 产出或主 Agent 直接生成） |

## 与其他 skill 的关系

- **requirement-traceability**：其正向通道内置极简验证点提取（每个需求点 1-2 个基本断言），覆盖有限。推荐在 Chain D 中先运行本 skill 再运行 requirement-traceability，以获得高精度正向追溯

## Closing Checklist（CRITICAL）

skill 执行的最终阶段（report）完成后，**必须**逐一验证以下产出文件：

- [ ] `verification_cases.json` — 非空，包含所有验证用例及 verification 结果
- [ ] `verification_report.json` — 非空，包含 summary 统计和 per_requirement 明细

全部必须项通过后，输出完成总结。如任一必须文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 需求功能点为空时停止，这是唯一的硬性阻断条件
- 代码实现不可用时降级为纯用例生成模式：生成用例但 `verification.result` 统一标记为 `inconclusive`，`verification.method` 标记为 `ai_reasoning`，`verification.trace` 填写「代码不可用，无法追踪」
- 当前阶段所有用例的 `verification.method` 均为 `ai_reasoning`；未来支持 `executable` 和 `hybrid` 模式
- 子 Agent（verification-test-writer）为 pipeline 编排层功能，独立使用本 skill 时子 Agent 不可用，所有功能点均在主 Agent 中直接生成
