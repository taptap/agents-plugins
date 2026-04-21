# 追溯与验证协议

本文件定义 requirement-traceability、test-failure-analyzer 等 skill 共享的追溯和验证相关协议。

## 双通道追溯模式

requirement-traceability 采用双通道追溯：

| 通道 | 方向 | 方法 | 回答的问题 |
| --- | --- | --- | --- |
| 正向通道 | 需求 → 代码 | 用例中介验证 | 需求是否被正确实现？ |
| 反向通道 | 代码 → 需求 | 直接代码追溯 | 代码有没有做需求之外的事？ |

**正向通道**用具体的测试用例作为中介——AI 拿用例的"操作步骤 + 预期结果"逐条对照代码推理"代码是否真能实现这条用例"。按优先级消费：① 上游 `final_cases.json`（test-case-generation 产出）→ ② `requirement_points.json` 的 `acceptance_criteria` → ③ 兜底从需求描述提取。详见 [requirement-traceability/PHASES.md](../requirement-traceability/PHASES.md) 3.1-3.2 节。

**反向通道**保持 reverse-tracer Agent 模式，从代码变更出发寻找需求对应。

两个通道并行启动，结果在 output 阶段合并。

> v0.0.7 起合并 verification-test-generation 能力到 traceability 内嵌步骤，不再独立生成中间验证用例文件。

## 影响范围分析约定

requirement-clarification 在澄清阶段对已有功能的修改类需求执行影响范围分析。

**数据源优先级**：

1. `module-relations.json`（模块关系索引，由 `spec` 插件的 `module-discovery` 生成维护）→ 读取结构化的模块依赖和实体归属关系
2. 定向代码扫描（限定在主要业务代码目录，不全库扫描）→ 当索引不存在或不足以回答时使用
3. 人工确认 → 将发现的影响范围通过 AskUserQuestion 工具向用户确认

**`module-relations.json` 标准格式**：

```json
{
  "modules": {
    "<module-name>": {
      "owns_entities": ["实体名称"],
      "depends_on": ["依赖的模块"],
      "depended_by": ["被依赖的模块"],
      "exposes_apis": ["暴露的 API"]
    }
  },
  "entity_index": {
    "<entity-name>": {
      "owner_module": "所属模块",
      "referenced_by": ["引用该实体的模块"],
      "reference_type": {
        "<module>": "引用方式描述"
      }
    }
  }
}
```

影响范围分析结果写入 `clarified_requirements.json` 的 `functional_points[].impact_scope` 字段。

## 自循环协议

test-failure-analyzer 和 requirement-traceability 支持自循环：发现问题 → 分析 → 修复/确认 → 重新验证。

### 通用自循环规则

| 规则 | 说明 |
| --- | --- |
| 最大迭代次数 | 3 次（可通过参数覆盖） |
| 人工确认 | 每次修复方案必须让用户确认后再执行，不静默自动修复 |
| 收敛判断 | 第 N+1 轮的未解决问题集合应是第 N 轮的真子集（即数量减少且无新增问题类型）。**推荐采用集合比较**：即使总数减少，新增了上轮不存在的问题项（如新 test_name）→ 标记「部分收敛 + 新增回归」而非完全收敛。仅当总数减少且无新增项时才视为收敛中 |
| 终止条件 | 全部通过 / 达到最大次数 / 不收敛 / 用户主动终止 |

### 测试失败自循环

```
测试执行 → 失败? → AI 分类（预期变化/回归/不稳定）→ 生成修复方案 → 用户确认 → 执行修复 → 重新测试 → ...
```

AI 分类标准：

| 分类 | 判断依据 | 处理策略 |
| --- | --- | --- |
| 预期变化 | 失败断言与本次需求变更直接相关 | 更新测试预期 → 用户确认 |
| 回归问题 | 失败测试与本次变更无直接关联 | 分析根因 → 按严重程度处理 |
| 不稳定 | 时过时不过、依赖外部资源 | 自动重试 1 次 → 仍失败则上报 |

### 需求回溯自循环

```
回溯完成 → 有缺口? → 分类（未实现/多余代码/部分实现）→ 向用户确认 → 补充实现 → 重新回溯 → ...
```

## UI 还原度检查约定

当需求有 Figma 设计稿链接时，requirement-traceability 或独立的 ui-fidelity-check skill 执行 UI 还原度对比。

**工具链**：

| 工具 | 用途 |
| --- | --- |
| Figma MCP `get_screenshot` | 获取设计稿截图 |
| Figma MCP `get_design_context` | 获取结构化设计数据 |
| Browser MCP `browser_take_screenshot` | 获取实现截图 |
| Browser MCP `browser_snapshot` | 获取 DOM 结构 |

**对比维度**：布局结构、间距与尺寸、颜色与样式、字体排版、状态完整性、交互行为。

**还原度评级标准**：

| 评级 | 条件 |
| --- | --- |
| high | 无 high severity 差异，medium 差异 <= 2 |
| medium | high severity 差异 <= 1，或 medium 差异 3-5 |
| low | high severity 差异 >= 2，或 medium 差异 > 5 |

**降级**：页面不可访问时 → structural-only 模式（仅对比设计数据 vs 代码样式定义，跳过截图对比）。

## forward_verification.json 格式

requirement-traceability 正向通道（用例中介验证）的产出。每条记录对应一条用例的代码追踪结果：

```json
[
  {
    "case_id": "M1-TC-01",
    "requirement_id": "FP-1",
    "result": "pass | fail | inconclusive",
    "confidence": 85,
    "trace": "applyCoupon(100, 50) -> min(coupon, order) -> 50 == expected 50 ✓",
    "expected": "<用例 expected 原文摘录>",
    "actual": "<代码追踪推断的实际行为>",
    "inconclusive_reason": "call_depth_exceeded | dynamic_dispatch | external_dependency | insufficient_context | complex_logic | null"
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `case_id` | string | 是 | 用例编号。来自上游 `final_cases.json`（如 `M1-TC-01`）；降级路径（forward-tracer 模式）形如 `FORWARD-TRACER-FP-1` |
| `requirement_id` | string | 是 | 对应的需求功能点编号（FP- 前缀） |
| `result` | string | 是 | pass / fail / inconclusive |
| `confidence` | number \| null | 是 | 0-100 置信度；降级模式（无代码可验证）时为 `null`，含义见「量化置信度评分」 |
| `trace` | string | 否 | 代码追踪路径（调用链格式） |
| `expected` | string | 否 | 用例 expected 原文摘录 |
| `actual` | string | 否 | 代码追踪推断的实际行为（fail 时必填） |
| `inconclusive_reason` | string \| null | 否 | inconclusive 时必填，取值见 traceability/PHASES.md 3.2.0 节 |
