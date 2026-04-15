---
name: requirement-clarification
description: >
  当收到新需求（链接、文档、口述或对话中的碎片化信息）时，通过多维度结构化问答
  与用户拉齐对需求的理解，识别模糊地带并逐项确认，输出结构化澄清结果和编号功能点清单
  供下游 skill 消费。需求评审会前的质量把关请使用 requirement-review。
  不适用于：评审会前质量把关（使用 requirement-review）。
  触发：帮我理清需求、需求澄清、这个需求不太明确、我有个新需求、澄清一下、拉齐需求。
---

# 需求澄清

## Quick Start

- Skill 类型：核心工作流
- 适用场景：新需求进入工作流程时，主动识别需求中的模糊地带，通过问答拉齐 AI 与人对需求的理解
- 必要输入：需求链接、本地需求文档、自由文本需求描述、或历史对话碎片（至少提供一个）
- 输出产物（全部必须生成，缺一不可）：
  - `clarification_log.md` — 澄清记录，供人回看
  - `clarified_requirements.json` — 结构化结果，供下游 skill 消费
  - `requirement_points.json` — 功能点清单，供 test-case-generation
  - `implementation_brief.json` — 实现任务清单，供 coding agent
- 完成标志：4 个文件全部生成且通过验证
- 失败门控：需求正文不可读且用户无法补充信息时停止；所有未经确认的信息标记为 `unconfirmed`
- 执行步骤：`init → fetch → clarify → consolidate`（阶段不可跳过）
- 澄清维度检查项：[CHECKLIST.md](CHECKLIST.md)

## 核心能力

- 多形态输入处理 — 支持链接、文档、自由文本、对话碎片等多种输入形式
- 需求文档深度解析 — 识别功能边界、状态流转、业务规则、数据约束
- 多视角并行分析 — 复杂需求时启动功能/异常/用户 3 个视角 Agent 并行分析，交叉验证提升置信度
- 结构化问题生成 — 按 12 个维度生成针对性的澄清问题
- 交互式确认 — 通过 AskUserQuestion 工具渐进式确认，记录人工回答
- 结构化输出 — 产出可被下游 skill 直接消费的 JSON 数据

## 执行模式

根据输入类型自动选择执行模式：

| 模式 | 触发条件 | 核心行为 |
| --- | --- | --- |
| **文档澄清模式** | 输入为 story_link 或 requirement_doc | 先解析文档，再针对模糊点提问 |
| **设计稿澄清模式** | 输入仅为 design_link（无需求文档） | 从设计稿反推功能点，识别交互规则和状态，再澄清业务逻辑 |
| **文档+设计稿联合模式** | 同时提供 story_link/requirement_doc 和 design_link | 解析文档和设计稿，交叉比对识别差集和矛盾，再针对性提问 |
| **探索式澄清模式** | 输入为 requirement_text 或碎片化信息 | 先通过多轮 AskUserQuestion 工具调用构建需求骨架，再逐维度深挖 |

各模式的阶段流程和输出产物一致，区别在于信息获取方式和问答侧重点。详见 [PHASES.md](PHASES.md)。

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

1. **首轮（骨架确认）**：确认功能范围、目标用户、核心场景、平台范围；探索模式下额外探查设计意图（是否有设计稿、视觉参考），3-4 个开放式问题
2. **中间轮（维度深挖）**：按优先级逐维度提问，每个问题提供选项或默认值
   - 优先级：功能边界 + 平台范围 → 交互与 UI 规则 → 依赖关系（含 API 契约） → 状态流转 → 验收标准 → 异常处理 → 影响范围 → 其他
3. **末轮（查缺补漏）**：汇总已知信息让用户确认，列出剩余 unconfirmed 项

### 退出条件

- 功能边界 + 平台范围 + 验收标准 已 confirmed → 可结束（最低标准）
- 所有维度均 confirmed → 理想结束
- 用户明确表示"够了" → 立即结束，剩余标记 unconfirmed
- 达到 5 轮仍有关键维度未确认 → 结束并标记风险

### 提问质量要求

- 每个问题必须具体、可回答，不能是模糊的「是否需要考虑异常情况」
- 提供选项或默认值帮助回答，如「支付超时后订单状态：A) 保持待支付 B) 自动取消 C) 其他」
- 对用户不关心的维度，AI 提出默认假设让用户确认，而非追问到底
- 标注问题来源维度和关联功能点

## 模型分层

| 任务 | 推荐模型 | 理由 |
| --- | --- | --- |
| 需求文档解析和澄清 | Opus | 需求理解是整个 pipeline 质量天花板 |
| 多视角分析 Agent（功能/异常） | Opus | 遗漏隐含需求的代价极高 |
| 多视角分析 Agent（用户） | Sonnet | 用户体验分析风险较低 |

## 可用工具

共享脚本（飞书/GitLab/GitHub）用法见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。以下为本 skill 特有工具：

### Figma MCP

仅当 fetch 阶段发现 Figma 链接时使用，按分级协议获取，详见 [shared-tools/SKILL.md](../shared-tools/SKILL.md#figma-设计稿获取)。

## 执行保障（CRITICAL）

1. **阶段不可跳过**：4 个阶段（init → fetch → clarify → consolidate）必须按序执行，不允许跳过任何阶段。
2. **consolidate 是最终阶段**：clarify 阶段的退出条件满足后，MUST 立即进入 consolidate 阶段，禁止在 consolidate 完成前执行任何下游操作（如创建实施计划、开始编码、调用其他 skill）。
3. **输出文件校验**：skill 执行完毕前，必须验证以下 4 个文件均已生成：
   - [ ] `clarification_log.md`
   - [ ] `clarified_requirements.json`
   - [ ] `requirement_points.json`
   - [ ] `implementation_brief.json`
4. **完成标志**：所有输出文件生成后，输出一行总结："需求澄清完成，已生成 N 个产物文件。" 这是 skill 的唯一合法终止点。

## 阶段流程

按以下 4 个阶段顺序执行，各阶段详细操作见 [PHASES.md](PHASES.md)。

| 阶段 | 目标 | 关键产物 |
| --- | --- | --- |
| 1. init | 验证输入，识别执行模式（文档 / 探索） | — |
| 2. fetch | 获取需求文档、设计稿、技术文档（探索模式跳过） | — |
| 3. clarify | 按维度分析需求，生成问题并交互确认 | `clarification_log.md` |
| 4. consolidate | 整合澄清结果为结构化输出 | `clarified_requirements.json`、`requirement_points.json`、`implementation_brief.json` |

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
  "platform_scope": {
    "platforms": ["iOS", "Android", "Web", "Server"],
    "coordination_needed": true,
    "shared_api_contracts": ["POST /api/v1/register"],
    "platform_specific_notes": {
      "iOS": "需适配 iOS 13+",
      "Android": "需适配 Android 8+",
      "Web": "需支持主流浏览器",
      "Server": "后端服务"
    },
    "implementation_order": "Server -> iOS/Android/Web 并行"
  },
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

### implementation_brief.json（实现任务清单，供下游 coding agent 消费）

将澄清后的需求按平台拆分为可执行的实现任务，附带 API 契约和依赖关系，供 coding agent 直接消费。

```json
{
  "tasks": [
    {
      "id": "TASK-1",
      "fp_ref": "FP-1",
      "platform": "iOS",
      "type": "frontend | backend | fullstack",
      "title": "用户注册页面实现",
      "description": "实现手机号注册流程，包含输入验证、验证码发送、注册提交",
      "acceptance_criteria": ["用户能通过手机号完成注册", "输入校验错误时展示提示"],
      "ui_specs": {
        "figma_node": "Figma 节点 ID 或 null",
        "key_components": ["注册表单", "验证码输入框", "提交按钮"],
        "interaction_notes": ["提交后展示 loading，成功后跳转首页"]
      },
      "api_dependencies": ["POST /api/v1/register", "POST /api/v1/sms/send"],
      "estimated_complexity": "low | medium | high",
      "tech_notes": "平台特有的技术约束或注意事项"
    },
    {
      "id": "TASK-2",
      "fp_ref": "FP-1",
      "platform": "Server",
      "type": "backend",
      "title": "注册接口开发",
      "description": "提供手机号注册 API，含短信验证码校验和用户创建",
      "acceptance_criteria": ["接口返回 user_id 和 token", "重复手机号注册返回 409"],
      "api_contract": {
        "method": "POST",
        "path": "/api/v1/register",
        "request": { "phone": "string", "sms_code": "string" },
        "response": { "user_id": "string", "token": "string" },
        "error_codes": { "409": "手机号已注册", "400": "验证码错误" }
      },
      "estimated_complexity": "medium"
    }
  ],
  "api_contracts": [
    {
      "id": "API-1",
      "method": "POST",
      "path": "/api/v1/register",
      "description": "用户注册",
      "request": { "phone": "string", "sms_code": "string" },
      "response": { "user_id": "string", "token": "string" },
      "error_codes": { "409": "手机号已注册", "400": "验证码错误" },
      "consumers": ["TASK-1"],
      "providers": ["TASK-2"],
      "confirmed": true
    }
  ],
  "dependency_graph": {
    "TASK-2": [],
    "TASK-1": ["TASK-2"]
  }
}
```

| 字段 | 说明 |
| --- | --- |
| `tasks[].id` | TASK- 前缀 + 序号，全局唯一 |
| `tasks[].fp_ref` | 关联的功能点编号（FP-N） |
| `tasks[].platform` | 目标平台：`iOS` / `Android` / `Web` / `PC` / `Server` / `Shared` |
| `tasks[].type` | 任务类型：`frontend` / `backend` / `fullstack` |
| `tasks[].ui_specs` | 前端任务的 UI 规格（后端任务为 null） |
| `tasks[].api_contract` | 后端任务的接口契约（前端任务为 null） |
| `tasks[].api_dependencies` | 前端任务依赖的 API 路径列表 |
| `api_contracts[]` | 全局 API 契约汇总，标注提供方和消费方 task |
| `dependency_graph` | 任务间依赖关系，key 为 task id，value 为其依赖的 task id 列表 |

当需求仅涉及单平台（如纯后端）、或源材料不包含 API 技术信息（`api_evidence_level: "none"`）时，`tasks` 数组只包含该平台的任务，`api_contracts` 为空数组，`dependency_graph` 可为空。

## 注意事项

- 回读中间文件、中断恢复等通用约定见 [CONVENTIONS](../../CONVENTIONS.md)
- 条件触发的分析章节（如 API 契约提取）在源材料信息不足时跳过，不生成推测性内容。详见 [CONVENTIONS.md 数据充分性门控](../../CONVENTIONS.md#条件触发章节的数据充分性门控)
- 澄清过程中，从需求文档能直接获得答案的问题标记 `source: "document"`，不需要向人提问
- 只在文档无法回答的问题上调用 AskUserQuestion 工具，避免过度打扰
- 每个功能点的 `clarification_status` 反映当前澄清程度，`unconfirmed` 的项目会传递给下游 skill 作为风险标记
- 探索模式下，首轮问答侧重功能范围而非细节，避免在信息不足时过早深挖
