# 变更分析各阶段详细操作指南

## 场景判断（首先执行）

根据用户提供的输入判断场景：

- 提供了 `bug_link` 或 `bug_doc` → **Bug 场景**（5 阶段）
- 提供了 `story_link`、`requirement_doc` 或 `clarified_requirements` → **Story 场景**（7 阶段）
- 仅提供代码变更无需求来源 → 询问用户，或降级为纯代码变更分析（按 Story 场景但跳过需求相关步骤）

---

## Story 场景（7 阶段）

### 阶段 1: init — 验证输入

### 1.0 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认输入来源：

1. 工作目录中已存在上游产出文件（`clarified_requirements.json`、`requirement_points.json`）→ 优先消费
2. `requirement_doc` 参数提供了本地文件 → Read 本地文件
3. `story_link` 参数为 URL → 调用脚本获取
4. 以上均不满足 → 降级为纯代码变更分析

### 1.1 验证代码变更

1. 确认代码变更来源非空（`code_changes` / `code_diff` / `code_diff_text` 至少一个，可同时提供多个）
2. 合并所有来源：MR/PR 链接列表 + 本地 diff 文件列表 + diff 文本，统一纳入待分析范围
3. 对 MR/PR 链接，判断代码托管平台（`gitlab` / `github`），后续使用对应脚本
4. 所有来源均为空 → 停止并报错

### 阶段 2: fetch — 数据获取

### 2.1 获取需求文档内容

- **上游文件存在**：Read `clarified_requirements.json` 和 `requirement_points.json`
- **本地文件**：Read `requirement_doc` 文件
- **URL**：使用 `fetch_feishu_doc.py` 获取
- **无需求来源**：记录"未提供需求文档"，基于代码变更做分析

### 2.2 获取设计稿上下文（可选）

- **Figma 链接**：调用 `get_figma_data` 获取设计数据，保存到 `design_context.md`
- **飞书链接**：使用 `fetch_feishu_doc.py`
- 无链接则跳过

### 2.3 确认关联代码变更

- MR/PR 链接：在 chat 中输出摘要
- 本地 diff：确认文件可读
- 如提供了 `story_link` 且代码变更为空，用 `search_mrs.py` / `search_prs.py` 搜索

### 2.3 附加：Urhox 有效改动筛选（Urhox 项目强制执行）

**判断依据**：PR 所属仓库为 `https://github.com/taptap/urhox` 即触发本步骤。

**执行步骤**（按序完成）：

1. 获取 PR 的全量变更文件列表
2. 将所有变更文件路径与以下 Urhox 二进制代码目录逐条比对：
   - `engine/Source/ThirdParty`
   - `3rd`
   - `engine/Source/Urho3D`
   - `engine/Source/Common`
   - `game/src/Common`
   - `game/src/Engine`
   - `game/src/Game`
   - `engine/Source/Tools/UrhoXRuntime`
   - `engine/Source/Tools/UrhoXServer`
3. 在 `change_checklist.md` 中新增「Urhox 有效改动筛选」节，无论是否命中都必须写入结果：
   - **无命中**：写入"本次 PR 无命中 Urhox 二进制代码目录的改动，不纳入后续分析"，并将此 PR 从变更清单中剔除（不进入阶段 3 分析）
   - **有命中**：列出命中文件路径及所属目录；**筛选结果即为该 PR 后续所有阶段的有效代码变更范围**，PR 原始 diff 中其余改动一律忽略，不参与阶段 3、4、5、6、7 的任何分析

> ⚠️ Urhox 项目 PR 中，不在上述目录内的改动不参与变更分析、影响面评估和测试覆盖评估，一律忽略。

### 2.4 获取已有测试用例（可选）

- 如工作目录中有 `existing_test_cases` 或 `final_cases.json`（上游产出），Read 并统计
- 无则跳过，后续按无现有用例处理

### 2.5 创建分析清单

写入 `change_checklist.md`：需求点清单（从文档逐条提取）、代码变更清单、已有用例统计。后续阶段引用此清单逐项处理。

### 阶段 3: 逐代码变更深度分析 → 增量写入 `code_change_analysis.md`

**核心原则**：逐代码变更循环（diff → context → callgraph），每个完成后**立即追加写入**。

#### 对每个代码变更执行

**3A: diff — 获取并分析**

- MR/PR：使用 `gitlab_helper.py mr-diff` 或 `github_helper.py pr-diff` 获取 diff
- 本地 diff：直接 Read 文件
- 分类变更文件，识别变更类型（API/逻辑/数据/配置）
- 评估风险（高: API 签名/DB Schema/核心逻辑；中: 新功能/业务调整；低: 文档/格式）
- 提取变更点列表，使用**完整自然语言描述**

**3A 附加：Android 三方交互命中检测（强制步骤，不可跳过）**

> ⚠️ **凡处理 Android 项目的 MR，此步骤必须执行，不得省略、跳过或静默忽略。**

**判断依据**：MR 所属仓库名称/路径包含 `android`（如 `taptap-android`、`cps/taptap-android`）即视为 Android 项目。

**执行步骤**（按序完成）：

1. 读取 [EXTERNAL-IMPACT.md](EXTERNAL-IMPACT.md) 中的「命中判断规则」表
2. 将本次 diff 的**所有变更文件路径**与规则表逐条比对
3. 在 `change_checklist.md` 中**必须新增**「三方交互命中检测」节，**无论命中与否都必须写入结果**：
   - **未命中**：写入"经检测，本次 diff 未命中任何三方交互高风险文件，跳过外部影响评估"
   - **命中**：写入命中的模块名称和对应文件路径，并新增「外部影响评估待办」节；后续阶段 4 和阶段 6 将激活外部影响评估模块

> 禁止在未执行文件路径比对的情况下直接跳过本步骤。检测结果必须体现在 `change_checklist.md` 中，作为可验证的执行痕迹。

**3A 附加：Urhox 二进制影响分析（命中时执行）**

**触发条件**：`change_checklist.md` 中「Urhox 有效改动筛选」节存在命中结果。

**执行步骤**（按序完成）：

1. **建立目录影响映射** — 将命中文件路径归类到以下影响层：
   - 共享引擎核心层：`engine/Source/Urho3D/Core`、`IO`、`Resource`、`Scene`、`Engine`
   - Runtime 主影响层：`Graphics`、`UI`、`NanoVG`、`Audio`、`Input`、`Urho2D`
   - Server 主影响层：`engine/Source/Tools/UrhoXServer`、`3rd/hiredis`
   - Runtime / Server 共享层：`Network`、`game/src/Game/Network`、`game/src/Common/Proto`、`game/src/Game/Bootstrap`
   - 平台专项层：`engine/Source/Common/Android`、`game/src/Common/IOSCommon`、`3rd/ObjectCBridge`、`3rd/ndcrash`

2. **抽样阅读代表性改动** — 从每个命中目录抽样阅读关键变更，判断：改变了什么行为、直接影响哪个二进制（`Runtime` / `Server` / `Both`）、是否平台专属、风险偏向（启动 / 渲染 / 资源加载 / 脚本 / 网络 / 认证 / 服务端生命周期）

3. **输出二进制影响结论** — 在 `code_change_analysis.md` 中追加「Urhox 二进制影响分析」节，包含：
   - 受影响二进制（`Runtime only` / `Server only` / `Both`）
   - 直接影响与间接影响分别列出
   - 平台专项说明（仅在涉及特定平台时填写）
   - 重点关注的回归风险（按优先级排序）
   - 建议测试矩阵（冒烟 / 启动退出 / 场景资源加载 / 渲染 UI / 网络连接重连 / 服务端启动配置鉴权 / 平台专项 / 长时稳定性等，按优先级合并输出）

> 分析时只描述命中改动引发的影响，不列出"哪些目录未改动"。测试建议必须具体，避免空泛的"做一轮冒烟"。

**3B: context — 按需获取代码上下文**

只在需要时获取（接口定义/数据模型/调用方/关键配置），避免拉取无关文件。

**3C: callgraph — 按业务流分析调用链**

按业务场景组织，标注文件/行号和置信度（`[已确认]`/`[基于 diff]`/`[推测]`），跨服务边界用 `--- 跨服务 ---` 标注。

#### 每个代码变更完成后

1. 首个：创建 `code_change_analysis.md`
2. 后续：追加到对应章节
3. 更新清单标记为 `[x]`，chat 输出进度

### 阶段 4: impact — 影响面评估

**前提**：回读 `code_change_analysis.md` 获取所有变更点。

分析维度：功能影响、数据影响、跨平台/跨服务影响、性能影响。有设计稿时补充"设计实现完整性"分析。

#### 需求点覆盖自检（有需求文档时执行）

1. 回读清单中的需求点，逐项检查是否在分析中被覆盖
2. 标记状态（已覆盖/未覆盖/部分覆盖），补充分析或标注原因
3. 更新清单

追加写入 `code_change_analysis.md` 的影响面和风险评估章节。

#### Android 三方交互外部影响评估（命中时必须执行）

**前提**：回读 `change_checklist.md`，确认「三方交互命中检测」节已写入（验证阶段 3A 已执行）。

**触发条件**：`change_checklist.md` 中存在「外部影响评估待办」节（即阶段 3A 命中检测有结果）。

**操作**：读取 [EXTERNAL-IMPACT.md](EXTERNAL-IMPACT.md)，按其「步骤 1」模板，将外部影响评估章节追加到 `code_change_analysis.md`。内容包括：命中模块汇总表、逐模块兼容性风险分析（向前兼容性 / 接口契约变化 / 受影响 SDK 模块 / 潜在断链场景）、综合外部影响等级。

若综合外部影响等级为 🔴 高，需在阶段 7 的 `change_analysis.json` 的 `key_findings` 和 `action_items` 中体现外部影响条目。

### 阶段 5: coverage — 测试覆盖评估

**前提**：回读 `code_change_analysis.md`、`change_checklist.md`。

#### 第一步：正向比对（变更点 → 测试用例）

若有已有用例，逐一比对所有变更点与用例，标注覆盖状态，计算覆盖率。
若无已有用例，将所有变更点默认视为"待补充验证"。

#### 第二步：反向验证（测试用例 → 变更点）

仅在有已有用例时执行。

#### 第三步：识别覆盖缺口

列出未覆盖/部分覆盖的变更点，按风险排序。

写入 `test_coverage_report.md`。

### 阶段 6: generate — 补充用例生成

为覆盖缺口生成测试用例，使用 [CONVENTIONS.md 用例 JSON 格式](../../CONVENTIONS.md#用例-json-格式)。

写入 `supplementary_cases.json`。追加到 `test_coverage_report.md`。

无覆盖缺口时跳过本阶段。

#### Android 三方交互测试访问评估与建议用例（按需）

**触发条件**：同阶段 4，`change_checklist.md` 中存在「外部影响评估待办」节。

**操作**：读取 [EXTERNAL-IMPACT.md](EXTERNAL-IMPACT.md)，按其「步骤 2」模板，将外部影响测试访问评估章节追加到 `test_coverage_report.md`。内容包括：测试访问路径说明（仅列命中模块行）、每个命中模块的建议测试用例（关键路径 + 兼容性边界）、回归范围建议。新增用例同步写入 `supplementary_cases.json`。

### 阶段 7: output — 结构化输出

**前提**：回读所有中间文件。

1. 生成 `change_analysis.json`（总结）
2. 生成 `change_coverage_report.json`（覆盖统计）
3. Chat 输出关键发现摘要

---

## Bug 场景（5 阶段）

### 阶段 1: init

#### 1.0 输入路由

1. `bug_doc` 参数提供了本地文件 → Read 本地文件，跳过在线获取
2. `bug_link` 参数为 URL → 使用脚本获取
3. 以上均不满足 → 停止并报错

#### 1.1 验证代码变更

同 Story 场景 1.1。代码变更为空时用 `search_mrs.py` / `search_prs.py` 搜索。仍为空 → 停止。

### 阶段 2: fetch

#### 2.1 持久化 Bug 描述

- 本地文件：Read 并写入 `bug_description.md`
- URL：获取后写入 `bug_description.md`

#### 2.2 补充信息获取

Bug 描述中含飞书链接时，用 `fetch_feishu_doc.py` 获取补充信息。

#### 2.3 创建分析清单

写入 `change_checklist.md`：Bug 信息摘要 + 代码变更清单。

#### 2.3 附加：Urhox 有效改动筛选

同 Story 场景 2.3 附加，Urhox 项目触发时执行。筛选完成后，该 PR 的代码变更范围由筛选结果替代——后续所有阶段（阶段 3 根因分析、阶段 4 影响面评估、阶段 5 输出）均只针对命中文件操作，PR 原始 diff 中其余改动不再纳入。

### 阶段 3: diff/context — 逐代码变更分析

同 Story 场景阶段 3（3A + 3B + 3A 附加 Android + 3A 附加 Urhox），每个代码变更完成后追加写入 `code_change_analysis.md`。

### 阶段 4: analyze — 根因分析

**前提**：回读 `code_change_analysis.md` 和 `bug_description.md`。

分析内容：
- **缺陷根因**：基于代码变更推断原始缺陷的原因，标注置信度
- **修复完整性**：修复是否涵盖了所有受影响的路径
- **副作用评估**：修复变更是否可能影响其他功能
- **回归测试建议**：需要重点验证的场景

生成 `change_fix_analysis.json`。

### 阶段 5: output

**前提**：回读 `change_fix_analysis.json`。

1. 生成 `change_analysis.json`（总结，含 Bug 场景专有字段）
2. 生成 `risk_assessment.json`（残余风险评估和行动建议）：

```json
{
  "overall_risk": "high | medium | low",
  "risk_factors": [
    {
      "factor": "风险因素描述",
      "severity": "high | medium | low",
      "evidence": "代码证据",
      "recommendation": "建议"
    }
  ],
  "summary": "风险总结",
  "action_items": ["行动项"]
}
```

3. Chat 输出关键发现摘要
