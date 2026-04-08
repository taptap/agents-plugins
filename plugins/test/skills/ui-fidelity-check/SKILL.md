---
name: ui-fidelity-check
description: >
  对比 Figma 设计稿与浏览器实现的 UI 还原度。输入 Figma 链接 + 页面 URL，
  输出 ui_fidelity_report.json 含差异清单和还原度评级。
  触发：还原度、UI 对比、设计稿对照、视觉走查、像素对比、UI 验收。
---

# UI 还原度检查

## Quick Start

- Skill 类型：需求回溯辅助
- 适用场景：前端需求实现后，验证 UI 是否与设计稿一致
- 必要输入：Figma 设计稿链接（至少一个 node）；可选：页面 URL（可在浏览器中访问）
- 输出产物：`ui_fidelity_report.json`
- 失败门控：Figma 链接无效或不可访问时停止
- 执行步骤：`init → fetch → compare → report`
- 降级模式：页面不可访问时，仅对比设计数据 vs 代码样式定义（structural-only 模式）

## 核心能力

- **视觉对比** — 将设计稿截图与实现截图并排比较，识别布局、颜色、间距等视觉差异
- **结构对比** — 将设计稿组件树（get_design_context）与 DOM 结构（browser_snapshot）对齐，检查层级、嵌套、组件数量是否一致
- **状态完整性检查** — 解析设计稿中的变体状态（默认、空、加载中、错误等），验证实现中是否存在对应状态

## 对比维度

| 维度 | 对比方式 | 示例差异 |
| --- | --- | --- |
| 布局结构 | 设计稿组件树 vs DOM 结构 | 「设计稿 3 列，实现 2 列」 |
| 间距 | 设计稿 padding/margin vs 计算样式 | 「间距设计 16px，实现 12px」 |
| 颜色 | 设计稿色值 vs CSS 色值 | 「标题色 #333，实现 #666」 |
| 字体 | 字号/字重/行高 | 「正文字号设计 14px，实现 16px」 |
| 状态完整性 | 各状态（空/加载/错误）是否实现 | 「缺少空状态页面」 |
| 交互 | 设计稿交互说明 vs 实际行为 | 「缺少下拉刷新」 |

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 视觉 + 结构对比（ui-fidelity-checker Agent） | Opus | 视觉差异识别需要强多模态理解力，遗漏代价高 |
| 状态完整性检查 | Opus | 需推断设计稿中隐含的变体状态 |
| 报告生成和评级计算 | Sonnet | 规则化汇总，Sonnet 性价比高 |

## 可用工具

### 1. Figma MCP

- `get_screenshot(nodeId, fileKey)` — 获取设计稿指定节点的截图
- `get_design_context(nodeId, fileKey)` — 获取结构化设计数据（组件树、颜色、间距、字体等）

### 2. Browser MCP

- `browser_navigate(url)` — 导航到目标页面
- `browser_take_screenshot()` — 截取当前页面截图
- `browser_snapshot()` — 获取 DOM 结构和可访问性树

### 3. 子 Agent: ui-fidelity-checker

通过 Task 工具调用。接收设计截图、设计上下文、实现截图、DOM 快照，按 6 个维度逐一对比。Agent 定义见 [ui-fidelity-checker.md](../../agents/ui-fidelity-checker.md)。

## 阶段流程

按以下 4 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证 Figma 链接，确认对比模式 | — |
| 2. fetch | 获取设计数据和实现数据 | `design_context.json`、截图文件 |
| 3. compare | 启动 ui-fidelity-checker Agent 执行多维度对比 | `comparison_result.json` |
| 4. report | 汇总差异、计算评级、生成最终报告 | `ui_fidelity_report.json` |

## 输出格式（`ui_fidelity_report.json`）

```json
{
  "overall_fidelity": "high | medium | low",
  "comparison_mode": "visual+structural | structural-only",
  "design_url": "Figma 链接",
  "page_url": "页面 URL（如有）",
  "summary": "一句话总结还原度情况",
  "statistics": {
    "total_differences": 5,
    "high_severity_count": 0,
    "medium_severity_count": 2,
    "low_severity_count": 3
  },
  "states_coverage": {
    "expected_states": ["default", "empty", "loading", "error"],
    "implemented_states": ["default", "loading", "error"],
    "missing_states": ["empty"],
    "coverage_rate": "75%"
  },
  "differences": [
    {
      "id": "UI-DIFF-1",
      "category": "spacing",
      "severity": "medium",
      "design_value": "16px",
      "actual_value": "12px",
      "location": "首页 > 推荐列表 > 卡片间距",
      "confidence": 90
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `overall_fidelity` | string | 是 | 还原度评级（high / medium / low） |
| `comparison_mode` | string | 是 | 对比模式（visual+structural / structural-only） |
| `design_url` | string | 是 | 输入的 Figma 链接 |
| `page_url` | string | 否 | 输入的页面 URL |
| `summary` | string | 是 | 一句话总结 |
| `statistics` | object | 是 | 差异统计 |
| `states_coverage` | object | 是 | 状态覆盖情况 |
| `differences` | array | 是 | 差异清单，每条含分类（category）、严重度、设计值、实际值、位置、置信度 |

### 差异严重度定义

| 严重度 | 含义 | 示例 |
| --- | --- | --- |
| `high` | 功能或布局层面的显著偏差，用户可感知 | 缺少整个组件、布局方向错误、关键状态缺失 |
| `medium` | 视觉细节偏差，影响一致性 | 间距偏差 > 4px、颜色不匹配、字号差异 |
| `low` | 微小偏差，可接受范围内 | 间距偏差 <= 4px、圆角差异、阴影细微差别 |

## 还原度评级标准

| 评级 | 条件 |
| --- | --- |
| `high` | 无 high severity 差异，且 medium severity 差异 <= 2 |
| `medium` | high severity 差异 <= 1，或 medium severity 差异 3-5 |
| `low` | high severity 差异 >= 2，或 medium severity 差异 > 5 |

## 中间文件

| 文件名 | 阶段 | 内容 |
| --- | --- | --- |
| `design_context.json` | fetch | Figma 设计上下文数据 |
| `comparison_result.json` | compare | ui-fidelity-checker Agent 的对比结果 |

## Closing Checklist（CRITICAL）

skill 执行的最终阶段（output）完成后，**必须**逐一验证以下产出文件：

- [ ] `ui_fidelity_report.json` — 非空，包含 overall_fidelity 评级和 differences 差异清单

全部必须项通过后，输出完成总结。如文件缺失，**停止并补生成**，不允许声明完成。

通用阶段执行约定见 [CONVENTIONS.md](../../CONVENTIONS.md#阶段执行保障)。

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- Figma 链接必须有效，这是唯一的阻断条件
- 页面不可访问时自动降级为 structural-only 模式，仅对比设计数据与代码样式定义。structural-only 结果仅供参考，所有差异 confidence 上限 60
- 置信度标记见 [CONVENTIONS](../../CONVENTIONS.md#置信度标记)
- 本 skill 可独立使用，也可作为 requirement-traceability pipeline 的一环
