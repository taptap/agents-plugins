# 测试设计各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 额外预取：测试用例链接、需求文档内容（预下载到 `requirement_doc.md`）。

## 阶段 1: init - 初始化

> 如果系统预取了数据，本阶段仅需验证和确认。

1. 检查预取数据：Story 名称、需求文档链接、设计稿链接
2. 记录 `work_item_id` 和 `project_key`
3. 回退：预取数据缺失时基于已有信息继续

## 阶段 2: understand - 需求理解

本阶段目标：深入理解需求的业务背景、功能逻辑和交互细节。

### 2.0 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认需求来源：

1. 工作目录中存在上游产出文件（`clarified_requirements.json`）→ 直接读取，跳过 2.1-2.3 的文档获取和解析步骤
2. 如存在 `requirement_points.json` → 读取作为功能点清单的参考
3. `requirement_doc` 参数提供了本地文件 → Read 本地文件作为需求文档，跳过 2.1 的在线获取
4. `story_link` 参数为 URL → 执行 2.1 在线获取
5. 以上均不满足 → 停止并报错

### 2.1 获取并阅读需求文档

- 如 `requirement_doc` 参数提供了本地文件：直接 Read 该文件
- 如 `requirement_doc.md` 已预下载：直接 Read
- 如未预下载，使用脚本获取：
  ```bash
  python3 $SKILLS_ROOT/shared-tools/scripts/fetch_feishu_doc.py \
    --url "<需求文档链接>" --output-dir . 2>fetch_meta.json
  ```
- 需求文档链接为空且无上游输入和本地文件时停止并报告错误

### 2.2 获取设计稿（如有）

- Figma 链接：使用 `get_figma_data` 获取结构化设计数据
- 飞书文档链接：使用 `fetch_feishu_doc.py` 获取
- 关注：页面状态（默认/空/加载/错误）、交互触发条件、条件展示逻辑

### 2.3 获取技术文档（如有）

如预取数据包含技术文档链接，使用 `fetch_feishu_doc.py` 获取。重点提取：接口字段定义、状态枚举值、业务规则约束。

## 阶段 3: decompose - 功能拆解

### 3.1 拆解功能模块

基于需求理解（或上游 `clarified_requirements.json`），将需求拆解为独立的功能模块：

- 一个独立的页面/视图 → 一个模块
- 一组相关的 CRUD 操作 → 一个模块
- 一个独立的业务流程 → 一个模块

### 3.2 为每个模块定义测试范围

根据模块功能特征，识别适用的测试设计方法（参考 SKILL.md「方法选择指引」）。

```markdown
### 模块 {N}: {模块名称}

**功能描述**：{该模块做什么}

**验收标准**：
1. {具体可验证的标准}

**适用测试方法**：
- {方法1}：{应用点说明}

**需要覆盖的场景**：
- 正向：{正常使用流程}
- 边界：{边界值场景}
- 异常：{异常路径场景}

**预估用例数**：约 X-Y 条
```

### 3.3 提炼全局上下文摘要

从需求文档（或上游 `clarified_requirements.json`）中提炼跨模块的全局上下文，写入 `context_summary.md`。控制在 500-1500 字。按需包含：产品背景、用户角色、全局业务规则、数据约束、关键状态定义、共用交互约定。

### 3.4 输出

1. 将拆解结果写入 `decomposition.md`
2. 将全局上下文写入 `context_summary.md`

**拆解决策**：
- 模块 < 3 个：不拆分子 Agent，跳过 `context_summary.md`
- 模块 >= 3 个：使用子 Agent 并行生成，必须生成 `context_summary.md`

## 阶段 4: generate - 并行生成

### 4.1 使用子 Agent 生成（模块 >= 3 个）

对每个功能模块，通过 Task 工具调用 test-case-writer 子 Agent。不要将 `context_summary.md` 内联到 Task prompt。

**Task 调用模板**：

```
为「{模块名}」功能模块生成测试用例。

## 全局上下文
请先用 Read 工具读取 context_summary.md 获取全局业务规则和数据约束。

## 本模块需求
{从 decomposition.md 中该模块的完整描述}

## 测试设计方法
本模块应使用以下测试设计方法：
{从 decomposition.md 中该模块的「适用测试方法」部分}

每条用例的 test_method 字段必须标注所用方法。
如需了解各方法的详细操作要点，Read $SKILLS_ROOT/test-design/METHODS.md。

## 输出要求
将用例以 JSON 数组写入 module_{index}_cases.json，module 字段填「{模块名}」，全部使用中文。
格式要求：Read $SKILLS_ROOT/../CONVENTIONS.md 中「用例 JSON 格式」部分获取完整字段定义。
```

并行策略：尽可能同时发起多个 Task 调用。

### 4.1.1 子 Agent 失败处理

1. Task 返回后用 Glob 确认 `module_{index}_cases.json` 是否存在
2. 文件不存在或为空：重试 1 次
3. JSON 格式错误：严重问题才修复，轻微格式问题由后端 `post_complete` 自动修正
4. 重试仍失败：在主 Agent 中直接生成
5. 所有模块处理完后再进入 review 阶段

### 4.2 直接生成（模块 < 3 个）

在主 Agent 中按模块顺序生成所有用例，写入对应的 `module_{index}_cases.json`。

## 阶段 5: review - 质量审查

> 格式校验（priority 合规、steps/expected 对齐）由后端 `post_complete` 自动完成，AI 只需关注内容质量。
> 审查修改直接编辑对应的 `module_{N}_cases.json` 文件，最后合并为 `test_cases.json`。

### 5.1 跨模块去重

使用 Grep 搜索所有 module 文件中的 `"title"` 字段快速获取标题列表：

- 不同模块之间是否有标题/场景实质性重复
- 有重复则保留更完整的，删除冗余

### 5.2 覆盖度检查

回读 `decomposition.md`，逐模块检查：
- 每个验收标准是否有对应用例
- 是否覆盖了边界场景和异常场景

### 5.3 方法覆盖度检查

核对 `decomposition.md` 中的「适用测试方法」与实际生成用例的 `test_method` 字段。缺失方法的补充用例追加到对应 module 文件。

### 5.4 合并最终用例集

将所有 `module_{N}_cases.json` 合并为单个 `test_cases.json`（顶层 JSON 数组）。每条用例的 `module` 字段标识归属模块。
