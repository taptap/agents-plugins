---
name: requirement-clarification
description: >
  当收到新需求（链接、文档、口述或对话中的碎片化信息）时，通过多维度结构化问答
  与用户拉齐对需求的理解，识别模糊地带并逐项确认，输出结构化澄清结果和编号功能点清单
  供下游 skill 消费。适用于用户说"帮我理清需求""这个需求不太明确""我有个新需求"
  "澄清一下"等场景。
---

# 需求澄清

## Quick Start

- Skill 类型：核心工作流
- 适用场景：新需求进入工作流程时，主动识别需求中的模糊地带，通过问答拉齐 AI 与人对需求的理解
- 必要输入：需求链接、本地需求文档、自由文本需求描述、或历史对话碎片（至少提供一个）
- 输出产物：`clarification_log.md`、`clarified_requirements.json`、`requirement_points.json`
- 失败门控：需求正文不可读且用户无法补充信息时停止；所有未经确认的信息标记为 `unconfirmed`
- 执行步骤：`init → fetch → clarify → consolidate`
- 澄清维度检查项：[CHECKLIST.md](CHECKLIST.md)

## 核心能力

- 多形态输入处理 — 支持链接、文档、自由文本、对话碎片等多种输入形式
- 需求文档深度解析 — 识别功能边界、状态流转、业务规则、数据约束
- 多视角并行分析 — 复杂需求时启动功能/异常/用户 3 个视角 Agent 并行分析，交叉验证提升置信度
- 结构化问题生成 — 按 12 个维度生成针对性的澄清问题
- 交互式确认 — 通过 ask_question 渐进式确认，记录人工回答
- 结构化输出 — 产出可被下游 skill 直接消费的 JSON 数据

## 执行模式

根据输入类型自动选择执行模式：

| 模式 | 触发条件 | 核心行为 |
| --- | --- | --- |
| **文档澄清模式** | 输入为 story_link 或 requirement_doc | 先解析文档，再针对模糊点提问 |
| **探索式澄清模式** | 输入为 requirement_text 或碎片化信息 | 先通过多轮 ask_question 构建需求骨架，再逐维度深挖 |

两种模式的阶段流程和输出产物一致，区别在于信息获取方式和问答侧重点。详见 [PHASES.md](PHASES.md)。

## 澄清维度

| 维度 | 关注点 | 典型问题 |
| --- | --- | --- |
| 功能边界 | 哪些在本期范围内，哪些不在 | 「X 功能是否包含编辑和删除？」 |
| 状态流转 | 实体的生命周期和状态变化规则 | 「订单从"待支付"能否直接到"已取消"？」 |
| 性能要求 | 响应时间、吞吐量、数据量级 | 「列表最多展示多少条？是否需要分页？」 |
| 权限控制 | 角色权限、访问限制、操作鉴权 | 「普通用户能否看到管理后台入口？」 |
| 异常处理 | 错误路径、降级策略、重试机制 | 「支付失败后订单状态如何处理？」 |
| 数据约束 | 字段规则、格式要求、唯一性 | 「用户名长度限制？是否允许特殊字符？」 |
| 依赖关系 | 上下游系统依赖、多端一致性 | 「此功能是否依赖某个服务的接口？」 |
| 交互与 UI 规则 | 用户操作流、页面跳转、表单交互、动效 | 「提交后跳转到哪个页面？是否有成功提示？」 |
| 安全与合规 | 数据加密、隐私法规、审计日志、脱敏 | 「用户手机号在日志中是否需要脱敏？」 |
| 兼容性 | 浏览器/OS 版本、屏幕尺寸、降级策略 | 「最低支持的 Android 版本？小屏幕下表格如何展示？」 |
| 可测试性与验收标准 | 如何验证功能正确、验收标准、测试数据 | 「验收标准是什么？需要准备哪些测试数据？」 |
| 影响范围 | 变更涉及的模块、功能、上下游系统 | 「优惠券逻辑修改会影响哪些模块？订单结算、退款、数据报表是否都需要同步调整？」 |

详细检查项见 [CHECKLIST.md](CHECKLIST.md)。

## 问题编排策略

### 渐进式提问

1. **首轮（骨架确认）**：确认功能范围、目标用户、核心场景，2-3 个开放式问题
2. **中间轮（维度深挖）**：按优先级逐维度提问，每个问题提供选项或默认值
   - 优先级：功能边界 → 验收标准 → 状态流转 → 异常处理 → 依赖关系 → 影响范围 → 交互规则 → 其他
3. **末轮（查缺补漏）**：汇总已知信息让用户确认，列出剩余 unconfirmed 项

### 退出条件

- 功能边界 + 验收标准 已 confirmed → 可结束（最低标准）
- 所有维度均 confirmed → 理想结束
- 用户明确表示"够了" → 立即结束，剩余标记 unconfirmed
- 达到 5 轮仍有关键维度未确认 → 结束并标记风险

### 提问质量要求

- 每个问题必须具体、可回答，不能是模糊的「是否需要考虑异常情况」
- 提供选项或默认值帮助回答，如「支付超时后订单状态：A) 保持待支付 B) 自动取消 C) 其他」
- 对用户不关心的维度，AI 提出默认假设让用户确认，而非追问到底
- 标注问题来源维度和关联功能点

## 模型分层

按「错误代价」分配模型能力，详见 [CONVENTIONS.md](../../CONVENTIONS.md#模型分层策略)。

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 需求文档解析和澄清 | Opus | 需求理解是整个 pipeline 质量天花板 |
| 多视角分析 Agent（功能/异常） | Opus | 遗漏隐含需求的代价极高 |
| 多视角分析 Agent（用户） | Sonnet | 用户体验分析风险较低 |

## 可用工具

### 1. 飞书文档获取脚本

用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。

### 2. Figma MCP

`get_figma_data(url="<Figma链接>")` — 获取设计稿布局/组件/交互数据。仅当 fetch 阶段发现 Figma 链接时使用。

### 3. GitLab 辅助脚本（条件触发）

当需求文档中提到具体模块/功能时，可查看现有代码实现。用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。

## 阶段流程

按以下 4 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证输入，识别执行模式（文档 / 探索） | — |
| 2. fetch | 获取需求文档、设计稿、技术文档（探索模式跳过） | — |
| 3. clarify | 按维度分析需求，生成问题并交互确认 | `clarification_log.md` |
| 4. consolidate | 整合澄清结果为结构化输出 | `clarified_requirements.json`、`requirement_points.json` |

## 输出格式

### clarification_log.md（交互记录，供人回看）

```markdown
# 澄清记录

## 基本信息
- 执行模式：文档模式 | 探索模式
- 输入摘要：> 用户原始输入的摘要
- 问答轮次：N 轮

## FP-1: 用户注册

### 功能边界
- Q: 注册是否支持第三方登录？
- A: 本期只支持手机号注册 [source: human]

### 可测试性与验收标准
- Q: 注册成功的验收标准是什么？
- A: 用户能收到短信验证码并完成注册流程 [source: human]

## FP-2: ...
```

### clarified_requirements.json（结构化结果，供下游 skill 消费）

```json
{
  "mode": "document | exploratory",
  "confidence_level": "high | medium | low",
  "story_id": "123 或 null",
  "story_name": "...",
  "input_summary": "用户原始输入的摘要",
  "functional_points": [
    {
      "id": "FP-1",
      "name": "用户注册",
      "description": "...",
      "confidence": 85,
      "boundaries": { "in_scope": ["..."], "out_of_scope": ["..."] },
      "state_transitions": [
        { "from": "未注册", "to": "已注册", "trigger": "提交注册表单", "rules": ["..."] }
      ],
      "business_rules": ["跨维度的综合业务规则，如'订单金额超过 1000 元需要审批'"],
      "performance_constraints": { "response_time": "...", "data_volume": "..." },
      "permission_rules": ["..."],
      "error_handling": ["..."],
      "data_constraints": ["..."],
      "dependencies": ["功能点级别的依赖，如'依赖支付服务的退款接口'"],
      "impact_scope": {
        "directly_affected": [
          { "module": "order-service/coupon.go", "reason": "优惠券核心计算逻辑" }
        ],
        "indirectly_affected": [
          { "module": "analytics/report.go", "reason": "报表统计依赖优惠金额字段" }
        ],
        "scope_confirmed": false,
        "scope_notes": "需与需求方确认报表模块是否需要同步调整",
        "data_source": "module_relations_index | code_scan | manual"
      },
      "interaction_rules": ["..."],
      "security_compliance": ["..."],
      "compatibility": ["..."],
      "acceptance_criteria": ["..."],
      "clarification_status": "confirmed | partial | unconfirmed",
      "qa_pairs": [
        { "question": "...", "answer": "...", "source": "human | document | assumption", "dimension": "功能边界" }
      ]
    }
  ],
  "global_constraints": {
    "multi_platform": ["..."],
    "dependencies": ["..."],
    "compatibility": ["..."],
    "security": ["..."]
  },
  "open_questions": ["..."]
}
```

字段按实际澄清结果填写，未涉及的维度留空数组或 null，不需要强制填充。探索模式下 `confidence_level` 通常为 `medium` 或 `low`，下游 skill 据此调整容忍度。

`functional_points[].confidence`（0-100）：功能点级别的置信度。多视角模式下为交叉验证后的合并评分（2+ Agent 确认 +20 加成）；单 Agent 模式下基于文档明确度评分。下游 test-case-generation 据此调整用例生成的激进程度。

`qa_pairs` 中 `source` 为 `assumption` 表示 AI 提出的默认假设被用户确认。

### requirement_points.json

```json
[
  {
    "id": "FP-1",
    "name": "用户注册",
    "acceptance_criteria": ["..."],
    "priority": "P0 | P1 | P2",
    "test_focus": ["功能边界", "异常处理"]
  }
]
```

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 澄清过程中，从需求文档能直接获得答案的问题标记 `source: "document"`，不需要向人提问
- 只在文档无法回答的问题上使用 ask_question，避免过度打扰
- 每个功能点的 `clarification_status` 反映当前澄清程度，`unconfirmed` 的项目会传递给下游 skill 作为风险标记
- 探索模式下，首轮问答侧重功能范围而非细节，避免在信息不足时过早深挖
