# 统一约定

本文件定义所有 skill 共享的执行约定。各 SKILL.md 通过引用本文件来保持一致性。

## 编写规范

- `SKILL.md` 顶部优先给出 `Quick Start`，说明适用场景、必要输入、输出产物、失败门控。
- 执行细节拆到 `PHASES.md`、`CHECKLIST.md`、`METHODS.md`、`TEMPLATES.md` 等参考文档。
- 每个 skill 目录下必须包含 `contract.yaml`，定义机器可读的输入输出接口。`contract.yaml` 的编写规范见 [CONTRACT_SPEC.md](CONTRACT_SPEC.md)。
- `description` 统一写成 `做什么 + 最小输入/输出`，避免泛化触发。

## 阶段执行保障

适用于所有包含多阶段流程的 skill。

1. **阶段必须按序执行**：不允许跳过、合并或重排阶段。
2. **阶段结束 ≠ skill 结束**：某个中间阶段的退出条件满足后，必须继续执行下一阶段，而非终止 skill。
3. **产物文件必须生成**：skill 的 `contract.yaml` 中定义的所有 `output.files` 必须在最终阶段生成，缺少任一文件即为执行失败。
4. **禁止提前进入下游操作**：在所有阶段完成前，不允许执行下游操作（如创建实施计划、开始编码、调用其他 skill）。
5. **完成验证**：最终阶段结束后，逐一校验产物文件是否存在且内容有效，全部通过后才能声明完成。

## 断言审计协议

详见 [skills/_shared/ASSERTION_AUDIT.md](skills/_shared/ASSERTION_AUDIT.md)。

## 独立验证者协议

详见 [skills/_shared/ASSERTION_AUDIT.md](skills/_shared/ASSERTION_AUDIT.md)。

## 回读中间文件

后续阶段需要引用之前阶段的数据时，**必须通过 Read 工具回读中间文件**，不依赖对话上下文中的记忆。对话上下文可能因截断而不完整，文件才是唯一可信的数据源。

## 阶段间文件校验

每个阶段完成后、进入下一阶段前，**必须检查本阶段定义的产物文件是否存在且非空**。文件名必须与 PHASES.md 中定义的名称完全一致，禁止使用变体名称。如文件缺失或为空，先补生成再继续，不允许跳过。

## 大文件读取策略

当输入文件超过 2000 行时，采用固定窗口顺序读取（每次 1000 行/块），逐块解析并缓存结果。禁止随机 offset 跳读，以免遗漏数据或破坏结构化格式（如 JSON）。

## 上游输入消费

当 skill 被编排层作为 pipeline 的一环调用时，上游 skill 的输出文件会被放置到工作目录中。

**约定**：如工作目录中已存在上游产出文件（如 `clarified_requirements.json`），优先消费该文件，跳过对应的数据获取步骤。各 PHASES.md 在 fetch/understand 阶段开头检查上游文件是否存在。

> 当 `$TEST_WORKSPACE` 已设置时，本节中的「工作目录」指 `$TEST_WORKSPACE` 所指向的目录。

## 输出工作区

通过本地 AI 工作流（非 pipeline 编排）调用多个 skill 时，各 skill 的产物默认散落在各自目录中，无法按需求维度组织。输出工作区解决这一问题。

### `$TEST_WORKSPACE` 环境变量

| 状态 | 行为 |
| --- | --- |
| 已设置 | 所有 skill 的输出文件写入 `$TEST_WORKSPACE`，上游文件也从该目录查找 |
| 未设置 | 行为不变（写入当前工作目录），向后兼容 |

### 命名约定

工作区目录位于 `plugins/test/workspace/` 下，以需求名 kebab-case 命名：

```
plugins/test/workspace/
├── add-coupon-feature/          # 需求1：所有 skill 产物汇聚于此
│   ├── clarification_log.md
│   ├── clarified_requirements.json
│   ├── requirement_points.json
│   ├── final_cases.json
│   ├── traceability_matrix.json
│   ├── ms_case_mapping.json        # metersphere-sync 产出
│   ├── ms_plan_info.json           # metersphere-sync 产出
│   ├── ms_sync_report.json         # metersphere-sync 产出
│   └── ...
└── user-registration-refactor/  # 需求2
    └── ...
```

`workspace/` 目录已加入 `.gitignore`，不会被提交。

### 本地工作流示例

```bash
export TEST_WORKSPACE=plugins/test/workspace/add-coupon-feature
mkdir -p $TEST_WORKSPACE
# 1. 运行 requirement-clarification → 产出写入 $TEST_WORKSPACE
# 2. 运行 test-case-generation → 从 $TEST_WORKSPACE 找到上游文件，产出也写入此处
# 3. 运行 requirement-traceability → 同上
```

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

> **注意**：本插件中的部分 skill（如 test-case-generation、requirement-traceability）原设计用于 pipeline 编排系统，其中 `$SKILLS_ROOT` 和「系统预取」由编排层自动处理。独立使用时需手动设置环境变量或手动准备输入文件。

## 环境变量预检

各 skill init 阶段在首次调用脚本前，必须检查该脚本所需的环境变量是否已设置。缺失时输出明确提示（变量名 + 用途 + 设置方式），并降级到不依赖该脚本的路径。

**Python 可用性预检**：首次调用 Python 脚本前检查 `python3 --version` 是否可用。不可用时降级到不依赖脚本的路径。

**脚本失败分类**：`ImportError` / `ModuleNotFoundError` 归类为确定性故障（环境缺失），不重试，直接降级。其他异常可按标准重试策略重试 1 次。

## 输出格式约定

- 结构化数据使用 JSON 格式，供下游 skill 或编排层消费
- 分析过程和中间记录使用 Markdown 格式
- 中间文件命名使用 snake_case
- JSON 文件顶层必须是数组或对象，不能是字符串
- 所有文本使用中文

## AskUserQuestion 交互式提问

所有 skill 需要向用户提问并等待回答时，**必须**直接调用 `AskUserQuestion` 工具。不要将问题输出为纯文本，调用工具可以让 CLI 和 Web 端均渲染为可交互的选项卡片。

> 本节是「输出溯源原则」在交互提问场景的落地。每个 question 和 option 都必须标注 `evidence_tag`，禁止把 AI 自己脑补的细节伪装成"事实"让用户确认。

### 格式规范

调用 `AskUserQuestion` 工具，传入以下结构：

```json
{
  "questions": [
    {
      "question": "完整的问题文本",
      "header": "简短标题（不超过12字）",
      "evidence_ref": "需求第 N 行『原文摘录』 / null（探查类）",
      "options": [
        {
          "label": "选项显示文本",
          "description": "选项补充说明",
          "evidence_tag": "quoted | derived | unknown",
          "evidence_ref": "需求第 N 行『原文摘录』 / null"
        }
      ],
      "multiSelect": false
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `questions` | array | 是 | 问题列表，每次 **1-4 个** |
| `questions[].question` | string | 是 | 完整问题描述 |
| `questions[].header` | string | 是 | 简短标题（不超过 12 字），用于卡片标题栏 |
| `questions[].evidence_ref` | string \| null | 是 | 问题来源在原始素材中的位置（建议带原文摘录）；纯探查类问题填 `null` |
| `questions[].options` | array | 是 | 选项列表，**2-4 个** |
| `questions[].options[].label` | string | 是 | 选项显示文本（1-5 词，简洁明了） |
| `questions[].options[].description` | string | 是 | 选项补充说明（解释选择后的影响） |
| `questions[].options[].evidence_tag` | string | 是 | `quoted` / `derived` / `unknown`，含义见「输出溯源原则」三级表 |
| `questions[].options[].evidence_ref` | string \| null | 是 | `quoted` / `derived` 必填且必须含成对引号包裹的原文摘录（如 `"需求第 9 行『搜索结果需要包含官方论坛』"`、`"SearchFragment.kt:42 『return badge ?: ""』"`）；`unknown` 可填 `null` |
| `questions[].multiSelect` | boolean | 是 | 是否允许多选 |

### 约束

- 每次提问控制在 **1-4 个问题**
- 每个问题提供 **2-4 个选项**，降低用户认知负担
- 每个选项**必须**提供 `description`、`evidence_tag`、`evidence_ref` 三个字段
- 分析说明在调用工具之前单独输出为文本
- 不要在 JSON 中使用 Markdown 格式（如 `**加粗**`），保持纯文本
- 如果一次需要确认的问题超过 4 个，分多次调用

### evidence_tag 硬规则（CRITICAL）

1. **`quoted` / `derived` 的 `evidence_ref` 必须含原文摘录**：用 `「」` / `『』` / `""` / `''` 把原文圈起来。schema 层会拒收只写"需求第 9 行"这种泛指。原文摘录强制 AI 自检"我从这句话真能直接推出我的结论吗"。
2. **`derived` 推导边界**：结论的具体性 ≤ 原文，单步显然，不引入原文没有的属性/UI 元素。详见「输出溯源原则」中的「derived 推导边界」节。
3. **不知道就问，不要编**：AI 没依据时禁止生成 `option` 候选填具体细节让用户选，必须改为 `unknown` + 开放式追问（见下方反捏造模板）。
4. **"X 已有 / 历史如此"不是依据**：用户说"安卓已有"时，能 `derived` 出"安卓的对应功能存在"，**推不出**任何具体形态（角标 / 置顶 / 颜色）。具体形态必须改为开放式追问。

### 反捏造模板：何时不要列候选

当 AI 想列具体候选但找不到依据时，**不要凑选项**，改为以下两种形态之一：

**形态 A：开放式追问**（适合"用户给了模糊措辞但无具体形态"）

候选写在 `question` 文本里作为提示词，让用户回复时参考；`option` 只承载元操作。

```json
{
  "question": "搜索结果中『官方论坛』如果有特殊标识，请说明形态（参考：角标 / 置顶 / 颜色 / 其他），无特殊标识请回复『无』",
  "header": "官方论坛标识",
  "evidence_ref": "需求第 9 行『搜索结果需要包含官方论坛（安卓已有）』",
  "options": [
    {"label": "无特殊标识，仅出现在结果中", "description": "和普通搜索结果同样展示", "evidence_tag": "derived", "evidence_ref": "需求第 9 行『搜索结果需要包含官方论坛（安卓已有）』未提及标识"},
    {"label": "我会在回复中说明", "description": "需用户补充具体形态", "evidence_tag": "unknown", "evidence_ref": null}
  ],
  "multiSelect": false
}
```

**形态 B：先问元信息再问细节**（适合"需要先确认某个事实，下一轮再列候选"）

```json
{
  "question": "安卓版本中『官方论坛』在搜索结果里目前有什么特殊标识吗？",
  "header": "安卓现状确认",
  "evidence_ref": "需求第 9 行『安卓已有』",
  "options": [
    {"label": "无特殊标识", "description": "和普通搜索结果一致", "evidence_tag": "unknown", "evidence_ref": null},
    {"label": "有特殊标识（我会在回复中详述）", "description": "用户回复后再确认形态", "evidence_tag": "unknown", "evidence_ref": null},
    {"label": "请你查一下安卓代码", "description": "由 AI 通过 GitLab/GitHub 脚本查证", "evidence_tag": "unknown", "evidence_ref": null}
  ],
  "multiSelect": false
}
```

### 示例

先输出分析说明文本，再调用 AskUserQuestion 工具：

```json
{
  "questions": [
    {
      "question": "本次需求涉及哪些平台？",
      "header": "平台范围",
      "evidence_ref": null,
      "options": [
        {"label": "仅前端", "description": "iOS/Android/Web/PC 平台", "evidence_tag": "unknown", "evidence_ref": null},
        {"label": "仅后端", "description": "服务端逻辑变更", "evidence_tag": "unknown", "evidence_ref": null},
        {"label": "前后端同时修改", "description": "前后端联动变更", "evidence_tag": "unknown", "evidence_ref": null},
        {"label": "多端同步（请在回复中列出具体平台）", "description": "用户在回复中补充", "evidence_tag": "unknown", "evidence_ref": null}
      ],
      "multiSelect": false
    },
    {
      "question": "核心变更是什么？请选择最接近的描述",
      "header": "核心变更",
      "evidence_ref": "需求第 1-10 行变更点清单",
      "options": [
        {"label": "新增功能模块", "description": "全新的功能模块开发", "evidence_tag": "derived", "evidence_ref": "需求第 4 行『新增热榜卡片』、第 6 行『新增论坛搜索』"},
        {"label": "修改现有逻辑", "description": "对已有功能的行为变更", "evidence_tag": "derived", "evidence_ref": "需求第 2 行『发现改为动态』、第 5 行『热榜改为独立单页』"},
        {"label": "UI/交互调整", "description": "界面或交互流程变化", "evidence_tag": "derived", "evidence_ref": "需求第 1 行『顶部 tab 吸顶』、第 3 行『二层底部栏去掉』"},
        {"label": "性能优化/重构", "description": "非功能性改进", "evidence_tag": "derived", "evidence_ref": "需求第 10 行『loading 骨架屏替换』"}
      ],
      "multiSelect": true
    }
  ]
}
```

## 脚本失败重试策略

所有共享脚本调用失败时，统一执行以下重试策略：

1. 检查 stderr 错误信息，判断是否为临时性故障（网络超时、限频、服务端 5xx）
2. 临时性故障：重试至少 2 次，每次间隔 3 秒
3. 确定性故障（参数错误、权限不足、404）：不重试，直接报告错误
4. 脚本执行超过 30 秒无输出：视为临时性故障，终止后重试
5. 3 次尝试后仍失败：记录错误到中间文件，按各 skill 定义的降级策略处理

## 输出溯源原则

**横切原则**：所有 skill 生成给用户确认或交付的实质性内容（澄清问题选项、用例描述、字段、契约、风险、影响范围、UI 元素），必须能指回原始素材中的具体位置。**AI 有疑问时应该向用户确认（开放式追问），而不是引入新的猜测让用户在猜测里选**——"伪命题选项"会污染下游决策，比直接提问还更费用户。

### 三级溯源标签

每条 AI 生成的实质性内容必须能归入以下三级之一。落地字段名为 `evidence_tag`（值取下表第一列），具体出处填在 `evidence_ref`。

| 标签 | 含义 | `evidence_ref` 要求 |
| --- | --- | --- |
| `quoted` | 原文/截图/代码原话直接出现 | **必填且必须包含原文摘录**，用 `「」` / `『』` / `""` / `''` 把原文圈起来。例：`"需求第 9 行『搜索结果需要包含官方论坛』"` |
| `derived` | 从原文/代码同义改述、类目归纳、简单去重得出，结论的具体性 ≤ 原文 | **必填且必须包含原文摘录**，让 AI 把推理来源原话敲出来。例：`"需求第 2 行『发现改为动态』"` |
| `unknown` | AI 不知道，等用户提供 | 可填 `null`。**配合开放式追问**——候选写到 `question` 文本里作为提示词，`option` 留给元操作（"我来回复"/"请你查代码"） |

> 没有"`assumed`（凭领域知识猜测）"这一级。AI 没依据时正确做法是**问用户**（用 `unknown` + 开放式追问），不是**先编一个让用户在候选里选**。

### derived 推导边界

`derived` 是最容易被滥用的一级（容易变成"伪装的猜测"）。判定一个推导是否合法，过以下三道关：

1. **结论不能比原文更具体**：原文没说的属性、细节、UI 元素不能"推"出来。
   - ❌ 原文「搜索结果需要包含官方论坛（安卓已有）」→ 推出"安卓有官方角标"。"角标"是原文没有的具体细节
   - ✅ 原文「搜索结果需要包含官方论坛（安卓已有）」→ 推出"本期需要给 iOS 搜索结果加官方论坛"。是同义改述
   - ✅ 原文「发现改为动态」+「热榜改为独立单页」→ 推出"这是修改现有功能"。「改为」→「修改」是同义映射 + 类目归纳
2. **推导是单步、显然的**：同义改述、类目归纳、简单去重可以；依赖多步链式推理或外部知识不可以
3. **能定位到具体词句**：`evidence_ref` 不能写 `"需求文档"` 这种泛指，要能指到具体哪几行哪几个字 + 把原文摘出来

**强制原文摘录**的目的是双重的：① AI 把原文敲出来时会强制自检"我从这句话真能直接推出我的结论吗"；② review 时一眼能比对结论 vs 原文的具体性差距。schema 层会拒收 `quoted` / `derived` 但 `evidence_ref` 不含成对引号的 payload。

**引号风格建议**：优先用中文 `「」` / `『』` 包裹原文。schema 也认 ASCII `""` / `''`，但英文 `''` 在自然语境下（如 `don't have`）会被误识别成成对引号。当 ref 含英文内容时，**首选 `"..."` 或 `『...』`**，避免依赖 ASCII 单引号。

**schema 校验范围（重要）**：schema **只校验引号格式**，不校验"摘录的字符串是否真出现在源材料里"。也就是说 AI 写 `evidence_ref: "『随便编一段话』"` 在 schema 层会通过——这是**故意的设计**：在校验函数里加载源材料做精确比对会让 schema 失去纯函数性，复杂度爆炸。
- **真正的兜底**：① prompt 已要求"必须能定位到原文"，AI 编假原文是主动违规；② review 阶段（人或 audit agent）一眼能看穿编的话不在原文里；③ 后续可加独立 audit agent 用 LLM 做语义校验
- **不要**因为 schema 通过就认为"已经核对了原文"

### 核心硬规则

1. **不知道就问，不要编**：AI 没依据时禁止生成 `option` 候选填具体细节让用户选，必须改为 `unknown` + 开放式追问（详见「AskUserQuestion 反捏造模板」）
2. **"X 已有 / 历史如此 / 同类如此"不是依据**：用户措辞中提到"安卓已有""历史版本如此""通常这么做"时，AI **不得**自动补全实现细节（如"安卓有角标"）。"安卓已有"只能推出"安卓的对应功能存在"，推不出任何具体形态
3. **跳过优于捏造**：信息不足时跳过该字段或整节，远好于生成看似合理但无依据的内容
4. **错误必须明确认领**：当 AI 发现自己生成了无依据内容（自检或被用户指出），必须明确声明"这是无依据推断"，不要含糊带过

### 落地映射

不同输出形态的 `evidence_tag` / `evidence_ref` 落地位置：

| 输出形态 | 字段 | 详见 |
| --- | --- | --- |
| AskUserQuestion 选项 | `options[].evidence_tag` + `options[].evidence_ref` | 「AskUserQuestion 交互式提问」节 |
| 条件触发章节内的字段 | 字段级 `source` 标注 + 章节级 `evidence` 三级判定 | 「条件触发章节的数据充分性门控」节 |
| 分析结论 | `[已确认]` / `[基于 diff]` / `[推测]` / `[待确认]` | 「置信度标记」节 |
| 用例 / 契约的字段 | `source: "document" / "design" / "code" / "human"` | 各 skill PHASES.md |

### 与已有机制的关系

本节是横切总纲。后续「条件触发章节的数据充分性门控」「置信度标记」「AskUserQuestion 交互式提问」均是本原则在具体场景的落地。新增分析步骤、新增 AskUserQuestion 选项、新增字段时，必须先按本节判定 `evidence_tag`，再选对应落地机制。

## 条件触发章节的数据充分性门控

条件触发的分析步骤或报告章节，在触发条件满足后，仍需通过**数据充分性检查**。源材料中不存在该章节所需的具体信息时，必须跳过该章节，不得凭推测生成内容。本节是「输出溯源原则」在条件触发章节场景的具体落地。

### 三级判定

| 级别 | `evidence` 值 | 含义 | 处理方式 |
| --- | --- | --- | --- |
| 充分 | `"sufficient"` | 源材料有明确可引用的信息（如 API 路径、字段定义、代码引用） | 正常生成该章节 |
| 部分 | `"partial"` | 有零散线索但不完整（如设计稿表单字段暗示请求字段，但无路径/方法） | 仅输出有 `source` 标注的内容，缺失部分生成澄清问题，不填充推测值 |
| 无 | `"none"` | 源材料中无任何相关技术信息 | **整节跳过**，不生成任何内容 |

### 核心规则

1. **禁止凭推测生成内容**：每个输出字段必须标注 `source`（document / design / code / human）。无 source 标注的字段不得出现在输出中
2. **跳过优于捏造**：信息不足时跳过整节，远好于生成看似合理但无依据的内容
3. **报告输出规则**：`evidence: "none"` 时报告中省略该章节，可选输出一行占位说明（如 "API 契约信息不足，待技术方案补充后确认"）；`evidence: "partial"` 时章节需加前缀说明 "以下仅包含源材料中明确提及的信息"

### 适用范围

此约定适用于所有 skill 中的条件触发章节。各 PHASES.md 应在条件触发步骤中引用此约定执行数据充分性检查。

## 置信度标记

分析结论中使用以下标记标注证据来源：

| 标记 | 含义 |
| --- | --- |
| `[已确认]` | 通过代码/数据/文档验证 |
| `[基于 diff]` | 仅基于 diff 推断 |
| `[推测]` | 合理推测但未验证 |
| `[待确认]` | 需要人工确认 |

## 量化置信度评分

在文本标记（`[已确认]` 等）基础上，引入 0-100 连续量化评分，用于 Agent 间结果合并和阈值过滤。

### 评分标准

| 区间 | 标签 | 含义 | 处理方式 |
| --- | --- | --- | --- |
| 90-100 | 高置信度 | 需求/代码/文档有直接证据，或双 Agent 共识 | 直接使用 |
| 70-89 | 中置信度 | 可从上下文合理推断，或单 Agent 发现 | 带标记使用 |
| 50-69 | 低置信度 | 基于领域知识的合理推测，无直接证据 | 需人工确认 |
| <50 | 丢弃 | 过度推测 | 不纳入输出 |
| `null` | 未验证 | 用例已生成但未经代码推理验证（如降级模式） | 下游按本地策略决定保留或跳过 |

### 与文本标记的映射

| 文本标记 | 量化区间 |
| --- | --- |
| `[已确认]` | 90-100 |
| `[基于 diff]` | 70-89 |
| `[推测]` | 50-69 |
| `[待确认]` | 显式人工确认标记 |

### 跨 Agent 共识规则

同一维度的 2 个 Agent 独立发现同一问题时：

- 双方原始 confidence 均 >= 70 → 加成 `confidence = min(100, max(两者) + 20)`
- 任一方 < 60 → 不加成，取两者算术平均值
- 其余情况（双方均 >= 60 但至少一方 < 70）→ 不加成，取两者中较高值

"同一问题"的判定标准：相同目标对象（用例/需求点/代码变更）+ 相似描述（语义匹配）。由编排层或主 Agent 在合并阶段判定。

### Pipeline 中的置信度流转

```
requirement-clarification → clarified_requirements.json (functional_point.confidence)
  → test-case-generation → final_cases.json (case.confidence + case.review_confidence)
    → requirement-traceability → traceability_matrix.json (mapping.confidence)
```

下游 skill 消费上游产出时，保留上游 confidence 字段不覆盖，在此基础上追加本阶段的评分字段。

## Agent 定义规范

详见 [skills/_shared/AGENT_PROTOCOL.md](skills/_shared/AGENT_PROTOCOL.md)。

## 模型分层策略

按"错误代价"分配模型能力 —— 高风险任务（漏检成本高）使用强模型，中低风险任务使用平衡模型。

| 模型 | 适用任务 | 选择理由 |
| --- | --- | --- |
| Opus | 需求理解/澄清、覆盖度审查、根因分析、代码逻辑分析、安全分析 | 理解力决定质量天花板，漏检代价极高 |
| Sonnet | 测试用例生成、用户视角分析、报告生成、结果合并/去重 | 模板化工作，Sonnet 性价比高 |
| Haiku | 简单格式校验、规则检查（预留） | 速度优先，成本最低 |

各 Agent 定义文件中 `## 模型` 节标注推荐模型。PHASES.md 中的 Task 调用通过 `model` 参数指定。

### 模型选择判断树

为新 Agent 或任务选择模型时，按以下顺序判断：

1. 如果做错了下游损失有多大？（高 → Opus，中/低 → Sonnet）
2. 创造性理解 vs 模板化生成？（理解 → Opus，生成 → Sonnet）
3. 输出有明确结构约束可机械校验？（是 → Sonnet，否 → Opus）

以下任务在大多数场景下适合 Sonnet：

- 简单分类（Bug 端分类、业务线归类）
- 模板填充和报告格式化
- 数据格式转换和合并
- 已有明确规则的校验（字段格式、枚举值）

## 多 Agent 并行执行

详见 [skills/_shared/AGENT_PROTOCOL.md](skills/_shared/AGENT_PROTOCOL.md)。

## 功能点编号前缀

| Skill | 前缀 | 用途 |
| --- | --- | --- |
| requirement-clarification | `FP-1` / `FP-2` ... | 功能点编号 |
| test-case-generation (review 阶段) | `RP-1` / `RP-2` ... | 需求验证点编号 |
| requirement-traceability | `R-1` / `R-2` ... | 需求点编号（对照代码变更） |

三套编号是同一批需求在不同 skill 作用域下的**独立编号**，不要求一一对应。它们描述的是同一份需求的不同视角：
- `FP-` 是澄清阶段识别的功能点（可能粒度较粗）
- `RP-` 是评审阶段从需求文档中提炼的验证点（可能更细）
- `R-` 是追溯阶段从需求中提取的映射锚点（有上游 FP- 时直接继承作为主键，R- 作为别名）

> v0.0.7 起合并 verification-test-generation：traceability 直接消费 `final_cases.json`（`case_id` 形如 `M1-TC-01`），不再独立生成 `VC-` 编号的中间用例。

下游 skill 消费上游的 `requirement_points.json` 时，按内容重新编号，不继承上游前缀。

### 跨 skill ID 映射

当下游 skill 需要关联来自不同上游的数据时（如 requirement-traceability 同时消费 `requirement_points.json` 的 FP- 编号和自身的 R- 编号），优先采用**编号直接继承**：下游直接使用上游 FP- 编号作为主键关联，同时记录本地 R- 编号作为别名（如 `FP-1 = R-1`）。仅当无上游编号（独立使用）时才使用 R- 独立编号。映射表记录在中间文件中，供后续阶段使用。

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
    "confidence": 85,
    "preconditions": ["前置条件1", "前置条件2"],
    "steps": [
      {"action": "步骤一", "expected": "预期一"},
      {"action": "步骤二", "expected": "预期二"}
    ]
  }
]
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `case_id` | string | 是 | 模块前缀 + 序号（如 M1-TC-01），review 阶段去重后允许断号 |
| `title` | string | 是 | 用例标题，纯业务描述。禁止包含：内部编号、优先级前缀（P0/P1/P2/P3）、测试方法或分类前缀（如「等价类-有效类：」「等价类-无效类：」「场景法：」等）、来源前缀（如「[补充]」「【补充】」「[新增]」等）。这些信息已由 `priority`、`test_method` 和 `source` 字段承载 |
| `module` | string | 是 | 模块名称（不带编号前缀） |
| `priority` | string | 是 | P0 / P1 / P2 / P3 |
| `test_method` | string | 是 | 等价类划分 / 边界值分析 / 场景法 / 错误推测法 / 判定表法 / 状态迁移法 / 探索性测试法 |
| `confidence` | number | 否 | 用例置信度（0-100），评分标准见「量化置信度评分」。test-case-generation 阶段生成 |
| `review_confidence` | number | 否 | 评审置信度（0-100），test-case-generation review 阶段冗余对评审后生成 |
| `source` | string | 否 | 用例来源：`generated`（生成阶段产出）/ `supplementary`（评审补充）。test-case-generation output 阶段标记 |
| `preconditions` | string[] | 是 | 前置条件字符串数组 |
| `steps` | array | 是 | 对象数组，每项含 `action`（操作）和 `expected`（预期结果），一一配对 |

### 通用约束

- 文件顶层必须是 JSON 数组
- `priority` 只允许 P0 / P1 / P2 / P3
- 所有文本使用中文
- 用例文本中禁止出现 ASCII 双引号，使用中文引号「」
- `test_method` 为「探索性测试法」时，`steps[].action` 填探索要点/操作方向（非精确步骤），`steps[].expected` 填判定标准/Oracle（非精确预期），`preconditions` 须包含章程（Charter）描述
- 禁止在用例 JSON 中包含 `tags` 字段，标签由后端根据工作流类型自动赋值

### 严格校验

后端 `case_schema.TestCase` 在 PreToolUse hook 对所有 `*_cases.json` 强制校验，**任何不符合上表字段定义的写入都会被即时拒收并要求重写**。完整示例：

```json
{
  "title": "用户未登录",
  "priority": "P0",
  "preconditions": ["未登录"],
  "steps": [
    {"action": "调用 X", "expected": ""},
    {"action": "等待回调", "expected": "回调 error.code=2"}
  ]
}
```

`expected` 只能是 `steps[i]` 的子字段，不能出现在用例顶层。`steps` 必须是对象数组，不能是字符串数组。

## 双通道追溯模式

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## 影响范围分析约定

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## 自循环协议

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## UI 还原度检查约定

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## 测试执行报告格式

详见 [skills/_shared/ASSERTION_AUDIT.md](skills/_shared/ASSERTION_AUDIT.md)。

## 验证用例 JSON 格式

详见 [skills/_shared/TRACEABILITY_PROTOCOL.md](skills/_shared/TRACEABILITY_PROTOCOL.md)。

## 术语表

| 术语 | 含义 |
| --- | --- |
| TapSDK | 公司自研客户端 SDK，负责数据采集、推送和基础服务能力 |
| DE（数仓） | Data Engineering 数据工程团队，负责数据仓库和数据管道 |
| IEM | ‍智能化引擎与商业化 ，其业务范围涵盖搜索、广告、推荐领域 |
| 冗余对评审 | 2 个独立 Agent 对同一输入并行评审，合并结果时对共识发现加成置信度 |
| 正向追溯 | 需求 → 验证用例 → 代码，验证需求是否被实现 |
| 反向追溯 | 代码变更 → 需求，验证代码变更是否有需求支撑 |
| 数据充分性门控 | 条件触发的分析章节在信息不足时跳过，不凭推测生成内容 |
| 置信度加成 | 2+ Agent 独立确认同一发现时 confidence += 20（封顶 100） |
