# 追溯与验证协议

本文件定义 requirement-traceability、verification-test-generation、test-failure-analyzer 等 skill 共享的追溯和验证相关协议。

## 双通道追溯模式

v0.0.10 起，requirement-traceability 采用双通道追溯：

| 通道 | 方向 | 方法 | 回答的问题 |
| --- | --- | --- | --- |
| 正向通道 | 需求 → 代码 | 用例中介验证 | 需求是否被正确实现？ |
| 反向通道 | 代码 → 需求 | 直接代码追溯 | 代码有没有做需求之外的事？ |

**正向通道**将需求拆解为结构化验证用例（具体输入→预期输出），AI 逐条对照代码推理。消费上游 `verification-test-generation` 的 `verification_cases.json`，或内置简化版用例生成。

**反向通道**保持 reverse-tracer Agent 模式，从代码变更出发寻找需求对应。

两个通道并行启动，结果在 output 阶段合并。

## 影响范围分析约定

requirement-clarification 在澄清阶段对已有功能的修改类需求执行影响范围分析。

**数据源优先级**：

1. `module-relations.json`（模块关系索引，由 `spec` 插件的 `module-discovery` 生成维护）→ 读取结构化的模块依赖和实体归属关系
2. 定向代码扫描（限定在主要业务代码目录，不全库扫描）→ 当索引不存在或不足以回答时使用
3. 人工确认 → 将发现的影响范围转为 ask_question 向用户确认

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

## 验证用例 JSON 格式

verification-test-generation 生成的验证用例使用以下格式：

```json
[
  {
    "case_id": "VC-1",
    "requirement_id": "FP-1",
    "requirement_name": "功能名称",
    "case_type": "functional | boundary | error | state",
    "input": {
      "description": "输入描述",
      "params": {}
    },
    "expected": {
      "description": "预期结果描述",
      "assertion": "具体断言表达式"
    },
    "verification": {
      "method": "ai_reasoning | executable",
      "result": "pass | fail | inconclusive",
      "trace": "代码追踪路径",
      "confidence": 85
    }
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `case_id` | string | 是 | VC- 前缀 + 序号 |
| `requirement_id` | string | 是 | 对应的需求功能点编号（FP- 前缀） |
| `requirement_name` | string | 是 | 功能点名称 |
| `case_type` | string | 是 | functional / boundary / error / state |
| `input.description` | string | 是 | 输入场景的文字描述 |
| `input.params` | object | 是 | 具体的输入参数键值对 |
| `expected.description` | string | 是 | 预期结果的文字描述 |
| `expected.assertion` | string | 是 | 可验证的断言表达式 |
| `verification.method` | string | 是 | 验证方式：ai_reasoning（AI 推理）/ executable（可执行测试） |
| `verification.result` | string | 是 | pass / fail / inconclusive |
| `verification.trace` | string | 否 | 代码追踪路径（AI 推理验证时的推理链） |
| `verification.confidence` | number \| null | 是 | 0-100 置信度；降级模式（无代码可验证）时为 `null`，含义见「量化置信度评分」|
