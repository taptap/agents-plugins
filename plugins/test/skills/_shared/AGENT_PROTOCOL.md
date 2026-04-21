# 多 Agent 协议

本文件定义使用子 Agent 的 skill 共享的 Agent 定义规范和并行执行协议。

## Agent 定义规范

所有子 Agent 的行为定义统一放在 `agents/` 目录下，作为**单一事实源**。各 PHASES.md 通过文件路径引用 Agent 定义，不内嵌 Agent prompt。

### 目录结构

```
agents/
├── AGENT_TEMPLATE.md                 # 统一模板
├── test-case-writer.md               # 测试用例生成 Agent
├── failure-classifier.md             # 测试失败分类 Agent (预留)
├── ui-fidelity-checker.md            # UI 还原度检查 Agent
├── requirement-understanding/        # 需求理解多视角 Agent
│   ├── functional-perspective.md
│   ├── exception-perspective.md
│   └── user-perspective.md
├── test-case-generation/              # 测试用例生成评审冗余对
│   ├── review-agent-1.md
│   └── review-agent-2.md
├── requirement-traceability/         # 需求追溯 Agent（反向追溯 + 正向降级回退）
│   ├── forward-tracer.md
│   └── reverse-tracer.md
└── change-analysis/                  # 变更分析交叉验证 Agent
    └── codex-change-analyzer.md      # Codex CLI 独立分析（与主 Agent 交叉验证）
```

### 模板结构

每个 Agent 定义文件遵循统一结构（详见 [AGENT_TEMPLATE.md](agents/AGENT_TEMPLATE.md)）：

1. **角色定义** — 一句话描述
2. **模型** — 按模型分层策略选择
3. **执行时机** — 总是启动 / 条件性启动，并行关系
4. **分析重点** — 具体检查维度和检查点
5. **输入** — 输入数据格式和来源
6. **输出格式** — 统一 JSON 结构（agent + findings 数组，每条含 confidence）
7. **置信度评分指南** — 本 Agent 领域的具体评分标准
8. **冗余机制** — 冗余对 Agent 专用，描述对偶关系和共识规则
9. **注意事项** — Agent 特有约束

### 命名约定

- Agent 文件使用 kebab-case：`{角色描述}.md`
- 冗余对使用数字后缀：`review-agent-1.md` / `review-agent-2.md`
- 按功能域分目录：`requirement-understanding/`、`test-case-generation/`、`requirement-traceability/`

## 多 Agent 并行执行

### 调用模式

使用 Task 工具并行启动多个 Agent 时，**在单条消息中发送所有 Task 调用**，实现真正并行。

```
Task(subagent_type="generalPurpose", model="opus", description="...", prompt="...")
Task(subagent_type="generalPurpose", model="opus", description="...", prompt="...")
Task(subagent_type="generalPurpose", model="sonnet", description="...", prompt="...")
```

总耗时 = max(单个 Agent 时间)，而非累加。

### 交叉验证协议

多 Agent 结果合并时，按以下协议处理：

1. **收集所有 Agent 结果**（TaskOutput）
2. **按维度分组**：冗余对的两个 Agent 归为同一组
3. **检测重复**：相同目标 + 相似描述 → 视为同一发现
4. **应用共识加成**：同一发现被两个 Agent 独立发现 → confidence += 20
5. **阈值过滤**：≥80 直接报告，60-79 标记人工确认，<60 丢弃

### 部分失败时的结果合并

多个 Agent 并行执行时，可能出现部分 Agent 成功、部分失败的情况。按以下规则处理：

**多视角 Agent（3+ 个独立视角）**：
- N 个 Agent 中有 1 个失败（重试后仍失败）→ 使用其余 N-1 个 Agent 的结果合并，在报告中标注"降级：{失败 Agent 名称} 未参与分析"
- N 个 Agent 中有 2+ 个失败 → 回退到主 Agent 单独分析模式
- 交叉验证时，缺失视角的维度不参与共识加成计算

**冗余对 Agent（2 个独立评审）**：
- 1 个失败（重试后仍失败）→ 使用成功 Agent 的结果作为最终结果，但：
  - 不应用共识加成（无法交叉验证）
  - 所有 findings 的 confidence 封顶 85（缺少独立验证）
  - 在报告中标注"降级：冗余对退化为单 Agent 模式"
- 2 个都失败 → 在主 Agent 中按单 Agent 模式执行

**结果合并时的冲突处理**：
- 同一目标出现矛盾结论（如 Agent A 判为 covered，Agent B 判为 missing）→ 取较低置信度的结论，并在报告中标注冲突（后续由人工裁决）

### 降级回退

所有多 Agent 阶段必须保留单 Agent 回退路径：

- Task 工具不可用 → 在主 Agent 中顺序执行各视角分析
- 需求简单（<3 个功能点）→ 跳过多 Agent，直接单 Agent 分析
- 子 Agent 执行失败 → 重试 1 次，仍失败则按上述"部分失败时的结果合并"规则处理

### 大文档分段策略

当需求文档超过预估 30K tokens 时，子 Agent 应按章节/模块分段 Read，每段独立处理后合并结果。主 Agent 在构造 Task prompt 时应提供文档结构摘要和目标章节范围，避免子 Agent 尝试 Read 完整文档导致 context 溢出。

**Token 估算经验规则**：
- 中文 1 字 ≈ 1.5-2 tokens，英文 1 词 ≈ 1-1.5 tokens
- 单次 Read 建议不超过 15K tokens（约 8000-10000 中文字或 200-300 行代码）
- 分段标准：按 `##` 二级标题或功能模块边界分段
