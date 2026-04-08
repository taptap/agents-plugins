# UI 还原度检查各阶段详细操作指南

## 阶段 1: init - 输入验证

确认 Figma 链接有效性和对比模式。

### 1.1 解析 Figma 链接

从 `design_link` 参数中提取 `fileKey` 和 `nodeId`：

- `figma.com/design/:fileKey/:fileName?node-id=:nodeId` → 将 nodeId 中的 `-` 转换为 `:`
- `figma.com/design/:fileKey/branch/:branchKey/:fileName` → 使用 `branchKey` 作为 `fileKey`
- `figma.com/make/:makeFileKey/:makeFileName` → 使用 `makeFileKey`
- 链接格式无法解析 → **停止**，报告错误

### 1.2 MCP 可用性探测

在继续之前验证所需 MCP server 已连接，避免延迟到 fetch 阶段才暴露连接错误：

1. **Figma MCP 探测**（必须通过）：
   - 调用 `get_metadata(fileKey)` 使用 1.1 解析出的 `fileKey`
   - 成功 → 记录 Figma MCP 可用
   - 失败 → **停止**，报告错误："Figma MCP server 未连接或 fileKey 无效，请检查 MCP 配置"

2. **Browser MCP 探测**（仅 `page_url` 非空时执行）：
   - 调用 `browser_tabs` (action: "list") 确认浏览器连接
   - 成功 → 记录 Browser MCP 可用
   - 失败 → 不停止，将模式降级为 structural-only，记录降级原因："Browser MCP 不可用，降级为 structural-only 模式"

### 1.3 确认页面 URL（可选）

检查 `page_url` 参数：

1. `page_url` 非空且 Browser MCP 可用（1.2 已确认）→ 记录 URL，标记为 visual+structural 模式
2. `page_url` 非空但 Browser MCP 不可用 → 标记为 structural-only 模式（已在 1.2 记录降级原因）
3. `page_url` 为空但 `code_dir` 非空 → 标记为 structural-only 模式
4. 两者均为空 → 标记为 structural-only 模式

### 1.4 检查可选参数

- `states_to_check` 非空 → 记录需要检查的状态列表
- `states_to_check` 为空 → 后续从设计稿中自动提取变体状态

## 阶段 2: fetch - 数据获取

### 2.0 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认数据来源：

1. 工作目录中存在上游产出文件（如 `clarified_requirements.json`）→ 读取作为需求上下文补充
2. 否则直接执行以下数据获取步骤

### 2.1 获取 Figma 设计数据

使用 Figma MCP 获取两类数据：

```
get_design_context(nodeId, fileKey)  → 结构化设计数据（组件树、颜色、间距、字体）
get_screenshot(nodeId, fileKey)      → 设计稿截图
```

将 `get_design_context` 的结果写入 `design_context.json`。

如果 Figma MCP 调用失败：
- 按 [CONVENTIONS.md](../../CONVENTIONS.md#脚本失败重试策略) 重试
- 3 次尝试后仍失败 → **停止**，报告错误

### 2.2 获取实现数据

**visual+structural 模式**（页面可访问）：

```
browser_navigate(url)          → 导航到目标页面
browser_take_screenshot()      → 截取实现截图
browser_snapshot()             → 获取 DOM 结构和可访问性树
```

如果页面导航失败或超时：
- 重试 1 次
- 仍失败 → 降级为 structural-only 模式，记录降级原因

**structural-only 模式**（页面不可访问）：

- 如 `code_dir` 非空 → 读取前端代码文件，提取样式定义（CSS/SCSS/Tailwind 类名等）
- 如 `code_dir` 为空 → 仅基于设计数据生成报告，差异清单中 `actual_value` 标记为 `[未获取]`
- **置信度上限**：structural-only 模式下所有差异的 confidence 上限为 60（无视觉对比支撑，仅供参考）

### 2.3 提取状态列表

如 `states_to_check` 未指定，从设计上下文中推断：

1. 解析 `design_context.json` 中的变体（variant）属性
2. 查找常见状态关键词：default、empty、loading、error、disabled、hover、active、selected
3. 如无变体信息，默认检查 `["default"]`

## 阶段 3: compare - 多维度对比

### 3.1 启动 ui-fidelity-checker Agent

通过 Task 工具启动子 Agent，指定 `model="opus"`。

**Task prompt**：

```
你是 UI 还原度检查 Agent。请先 Read agents/ui-fidelity-checker.md 获取你的完整角色定义和输出格式要求。

## 设计数据
请 Read ./design_context.json 获取设计稿结构化数据。
设计截图已附在本次对话中。

## 实现数据
{visual+structural 模式：实现截图已附在本次对话中。DOM 快照如下：...}
{structural-only 模式：页面不可访问，请基于以下代码样式定义进行结构对比：...}

## 对比模式
{visual+structural | structural-only}

## 需要检查的状态
{states_to_check 列表}

## 任务
按 6 个维度（布局结构、间距、颜色、字体、状态完整性、交互）逐一对比，输出 JSON 格式的差异清单。每条差异必须包含 confidence 评分（0-100）。
```

### 3.2 Agent 对比执行

ui-fidelity-checker Agent 按以下顺序执行对比：

1. **布局结构** — 设计稿组件树层级 vs DOM 节点层级，检查列数、嵌套关系、组件数量
2. **间距** — 设计稿 padding/margin/gap 值 vs 计算样式或代码定义
3. **颜色** — 设计稿色值（含 design token）vs CSS 色值（含 CSS 变量解析）
4. **字体** — 字号、字重、行高、字体族
5. **状态完整性** — 逐一检查 `states_to_check` 中的每个状态是否在实现中存在
6. **交互** — 设计稿交互说明（如有）vs 实际可交互元素和行为

visual+structural 模式下，Agent 同时参考截图（视觉）和结构化数据（数据）做交叉验证。structural-only 模式下，仅基于结构化数据对比。

### 3.3 结果写入

将 Agent 返回的对比结果写入 `comparison_result.json`。

### 3.4 降级回退

- Task 工具不可用 → 在主 Agent 中顺序执行 6 个维度的对比
- Agent 执行失败 → 重试 1 次，仍失败则在主 Agent 中接管

## 阶段 4: report - 汇总与评级

**前提**：回读 `comparison_result.json` 和 `design_context.json`。

### 4.1 差异汇总

1. 读取 `comparison_result.json` 中的所有差异
2. 按置信度过滤：confidence < 50 的差异丢弃（见 [CONVENTIONS.md](../../CONVENTIONS.md#量化置信度评分)）
3. 为每条差异分配严重度（high / medium / low）
4. 为每条差异生成唯一 ID（`UI-DIFF-1`、`UI-DIFF-2`...）

### 4.2 状态覆盖率计算

```
coverage_rate = implemented_states / expected_states × 100%
```

缺失的状态作为 high severity 差异追加到差异清单。

### 4.3 还原度评级

按以下规则计算 `overall_fidelity`：

| 评级 | 条件 |
| --- | --- |
| `high` | 无 high severity 差异，且 medium severity 差异 <= 2 |
| `medium` | high severity 差异 <= 1，或 medium severity 差异 3-5 |
| `low` | high severity 差异 >= 2，或 medium severity 差异 > 5 |

评级优先取最低匹配：如同时满足 `medium` 和 `low` 的条件，取 `low`。

### 4.4 生成 ui_fidelity_report.json

按 [SKILL.md](SKILL.md#输出格式ui_fidelity_reportjson) 定义的格式生成最终报告。

### 4.5 输出文本摘要

在终端输出人类可读的摘要，包含：

1. 还原度评级和对比模式
2. 差异总数和按严重度分布
3. 状态覆盖率
4. 前 3 条最高严重度差异的简要描述
5. 如为 structural-only 模式，提示用户提供页面 URL 以获取更完整的对比结果
