# 统一约定

本文件定义所有 skill 共享的执行约定。各 SKILL.md 通过引用本文件来保持一致性。

## 编写规范

- `SKILL.md` 顶部优先给出 `Quick Start`，说明适用场景、必要输入、输出产物、失败门控。
- 执行细节拆到 `PHASES.md`、`CHECKLIST.md`、`METHODS.md`、`TEMPLATES.md` 等参考文档。
- 每个 skill 目录下必须包含 `contract.yaml`，定义机器可读的输入输出接口。`contract.yaml` 的编写规范见 [CONTRACT_SPEC.md](CONTRACT_SPEC.md)。
- `description` 统一写成 `做什么 + 最小输入/输出`，避免泛化触发。

## 回读中间文件

后续阶段需要引用之前阶段的数据时，**必须通过 Read 工具回读中间文件**，不依赖对话上下文中的记忆。

## 上游输入消费

当 skill 被编排层作为 pipeline 的一环调用时，上游 skill 的输出文件会被放置到工作目录中。

**约定**：如工作目录中已存在上游产出文件（如 `clarified_requirements.json`），优先消费该文件，跳过对应的数据获取步骤。各 PHASES.md 在 fetch/understand 阶段开头检查上游文件是否存在。

## 本地文件输入

当需求来源不是在线链接（飞书/Figma），而是本地文件（如 AI 对话后生成的 `.md` 或 `.json`）时：

1. 通过 `requirement_doc`（或对应的文件参数）传入文件路径
2. 在 init/fetch 阶段检测到本地文件时，跳过在线文档获取步骤
3. 后续分析阶段正常执行，与在线获取的文档等价处理

**输入路由优先级**（各 PHASES.md 的 init/fetch 阶段统一遵循）：

1. 工作目录中已存在上游产出文件 → 优先消费
2. `requirement_doc` 等文件参数提供了本地文件 → Read 本地文件
3. `story_link` 等链接参数为 URL → 调用对应脚本获取
4. 以上均不满足 → 停止并报错（各 skill 可根据自身特性覆盖此默认行为，如 requirement-traceability 支持降级为单边追溯，具体见各 PHASES.md）

**输入路由阶段编号**：输入路由统一放在数据获取阶段（fetch/understand）的 `X.0` 步骤。具体地：如果 skill 有独立的 init 阶段仅做预取验证，输入路由放在 phase 2（`2.0`）；如果 init 阶段包含输入路由逻辑，则放在 phase 1（`1.0`）。

## 系统预取

系统在 skill 启动前自动预取数据并嵌入 prompt。预取失败的数据在 `### 预取警告` 中说明。

通用预取字段（Story 类 skill）：Story 基本信息（名称、状态、project_key、work_item_id）、自定义字段（需求文档链接、设计稿链接、技术文档链接、负责人）。各 skill 可能额外预取特有数据（如需求文档内容、关联代码变更列表），具体字段在各 PHASES.md 顶部的"本 skill 预取字段"中声明。

## 中断恢复

Agent 因 context 截断或异常中断后恢复执行时：

1. 检查工作目录中已生成的中间文件，确认最后完成的阶段
2. 回读中间文件获取已有分析结果
3. 从中断阶段继续执行，不重新执行已完成的阶段
4. 如果中间文件不完整，从该文件对应的阶段重新开始

## 脚本路径约定

所有脚本引用使用相对于 skills 目录的路径：`skills/<skill-name>/scripts/<script>.py`。

运行时通过 `$SKILLS_ROOT` 环境变量定位 skills 目录的绝对路径。在 marketplace 插件中，`$SKILLS_ROOT` 应指向 `plugins/test/skills/`（而非仓库根目录）。如果 `$SKILLS_ROOT` 未设置，skill 应使用 SKILL.md 所在目录的相对路径来定位脚本。

> **注意**：本插件中的部分 skill（如 test-design、test-review、requirement-traceability）原设计用于 pipeline 编排系统，其中 `$SKILLS_ROOT` 和「系统预取」由编排层自动处理。独立使用时需手动设置环境变量或手动准备输入文件。

## 输出格式约定

- 结构化数据使用 JSON 格式，供下游 skill 或编排层消费
- 分析过程和中间记录使用 Markdown 格式
- 中间文件命名使用 snake_case
- JSON 文件顶层必须是数组或对象，不能是字符串
- 所有文本使用中文

## 脚本失败重试策略

所有共享脚本调用失败时，统一执行以下重试策略：

1. 检查 stderr 错误信息，判断是否为临时性故障（网络超时、限频、服务端 5xx）
2. 临时性故障：重试至少 2 次，每次间隔 3 秒
3. 确定性故障（参数错误、权限不足、404）：不重试，直接报告错误
4. 脚本执行超过 30 秒无输出：视为临时性故障，终止后重试
5. 3 次尝试后仍失败：记录错误到中间文件，按各 skill 定义的降级策略处理

## 置信度标记

分析结论中使用以下标记标注证据来源：

| 标记 | 含义 |
| --- | --- |
| `[已确认]` | 通过代码/数据/文档验证 |
| `[基于 diff]` | 仅基于 diff 推断 |
| `[推测]` | 合理推测但未验证 |
| `[待确认]` | 需要人工确认 |

## 功能点编号前缀

| Skill | 前缀 | 用途 |
| --- | --- | --- |
| requirement-clarification | `FP-1` / `FP-2` ... | 功能点编号 |
| test-review | `RP-1` / `RP-2` ... | 需求验证点编号 |
| requirement-traceability | `R1` / `R2` ... | 需求点编号（对照代码变更） |

## 用例 JSON 格式

所有 skill 生成的测试用例统一使用以下 JSON 格式。各 skill 的 SKILL.md 和 PHASES.md 通过引用本节保持格式一致。

```json
[
  {
    "case_id": "M1-TC-01",
    "title": "用例标题",
    "module": "模块名称",
    "priority": "P0",
    "test_method": "边界值分析",
    "preconditions": ["前置条件1", "前置条件2"],
    "steps": [
      {"action": "步骤一", "expected": "预期一"},
      {"action": "步骤二", "expected": "预期二"}
    ]
  }
]
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `case_id` | string | 模块前缀 + 序号（如 M1-TC-01），review 阶段去重后允许断号 |
| `title` | string | 用例标题，纯业务描述，禁止包含内部编号 |
| `module` | string | 模块名称（不带编号前缀） |
| `priority` | string | P0 / P1 / P2 / P3 |
| `test_method` | string | 等价类划分 / 边界值分析 / 场景法 / 错误推测法 / 判定表法 / 状态迁移法 |
| `preconditions` | string[] | 前置条件字符串数组 |
| `steps` | array | 对象数组，每项含 `action`（操作）和 `expected`（预期结果），一一配对 |

### 通用约束

- 文件顶层必须是 JSON 数组
- `priority` 只允许 P0 / P1 / P2 / P3
- 所有文本使用中文
- 用例文本中禁止出现 ASCII 双引号，使用中文引号「」

## 术语表

| 术语 | 含义 |
| --- | --- |
| TapSDK | 公司自研客户端 SDK，负责数据采集、推送和基础服务能力 |
| DE（数仓） | Data Engineering 数据工程团队，负责数据仓库和数据管道 |
| IEM | 内部事件管理平台，负责事件埋点定义和分析 |
