# 追溯与验证协议

本文件定义 requirement-traceability、test-failure-analyzer 等 skill 共享的追溯和验证相关协议。

## 双通道追溯模式

requirement-traceability 采用双通道追溯：

| 通道 | 方向 | 方法 | 回答的问题 |
| --- | --- | --- | --- |
| 正向通道 | 需求 → 代码 | 用例中介验证 | 需求是否被正确实现？ |
| 反向通道 | 代码 → 需求 | 直接代码追溯 | 代码有没有做需求之外的事？ |

**正向通道**用具体的测试用例作为中介——AI 拿用例的"操作步骤 + 预期结果"逐条对照代码推理"代码是否真能实现这条用例"。按优先级消费：① 上游 `final_cases.json`（test-case-generation 产出）→ ② `requirement_points.json` 的 `acceptance_criteria` → ③ 兜底从需求描述提取。详见 [requirement-traceability/PHASES.md](../requirement-traceability/PHASES.md) 3.1-3.2 节。

**反向通道**主 agent 内联完成（v0.0.16 起不再调 Task sub-agent，详见 `requirement-traceability/PHASES.md` 3.3）：从代码变更出发寻找需求对应，结果直接写进 `code_analysis.md` 的「反向追溯输出（主 agent 内联）」节。

两个通道由主 agent 顺序执行（先正向，再反向），结果在 output 阶段交叉验证。

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

## forward_verification.json 格式（v2）

requirement-traceability 正向通道的产出。**权威 schema 在 `_shared/schemas/forward_verification.schema.json`**，本节是人话说明，schema 与本节冲突时以 schema 为准。

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
      "verification_logic": "Network.swift:87 在 catch 分支调 ToastCenter.show(errorMsg)；errorMsg 由 TapNetwork.swift:33 兜底为非空。",
      "considered_failure_modes": [
        {"mode": "errorMsg 为空字符串", "ruled_out_by": "TapNetwork.swift:33 默认值兜底"}
      ]
    },
    "external_dependencies": {
      "types": [],
      "notes": ""
    }
  }
]
```

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `case_id` | string | 是 | 用例编号。来自上游 `final_cases.json`（如 `M1-TC-01`）；降级路径形如 `FORWARD-TRACER-FP-1` |
| `requirement_id` | string | 是 | 对应需求功能点编号（FP- 前缀） |
| `requirement_name` | string | 否 | 需求点名称（用于 caveats 报告展示） |
| `result` | enum | 是 | `pass` / `fail` / `inconclusive` |
| `confidence` | number \| null | 是 | 0-100 置信度；降级模式（无代码可验证）时为 `null`。**pass 且 conf<70 schema 拒绝**（强制降为 inconclusive） |
| `trace` | string | 否 | 代码追踪路径（调用链格式） |
| `expected` | string | 否 | 用例 expected 原文摘录 |
| `actual` | string | fail 必填 | 代码追踪推断的实际行为 |
| `inconclusive_reason` | enum | inconclusive 必填 | `call_depth_exceeded` / `dynamic_dispatch` / `external_dependency` / `insufficient_context` / `complex_logic` |
| `evidence` | object | **pass / fail 必填** | 见下 |
| `external_dependencies` | object | 否（pass 但需外部验证时必填） | 见下；下游 P6 状态映射会把非空 types 的 pass 降为 MS Prepare |
| `source` | string | 否 | 兜底标记，例如 `synthesized_from_coverage_report` |
| `ms_id` | string | 否 | MeterSphere 用例 UUID。由 P3 writeback 在 lookup 后回写进 `forward_verification.enriched.json`，下次跑 writeback 可跳过 lookup |

### evidence 子字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `code_location` | string[] | 是 | array of `file:line` 或 `file:start-end`；**文件必须存在、行号必须在文件内**（schema 校验 + boundary 校验都查） |
| `verification_logic` | string | 是 | 为什么从这段代码能推出 pass/fail 的论证。让另一个人/AI 只看 evidence 就能复算 |
| `considered_failure_modes` | array | pass+conf≥85 必填 | 对抗式自检：列出考虑过但被排除的失败模式。每条 `{mode, ruled_out_by}` |
| `human_override` | object | 否 | Phase 4.7 fail 复核被人工改判时的审计字段。`{from, to, reason}` |

### external_dependencies 子字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `types` | enum[] | 是（external_dependencies 出现时） | 取值：`device` / `server` / `third_party` / `framework_default` / `user_action` / `data_state` / `timing` |
| `notes` | string | 否 | 自由文本补充 |

### 校验

落盘后强制跑：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  validate-fv $TEST_WORKSPACE/forward_verification.json
```

失败 → exit 2 + structured stderr，**不允许带 bug fv 跑下去**。详见 `requirement-traceability/PHASES.md` 4.6a。
