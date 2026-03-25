# Bug 修复分析各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 预取字段：Bug 基本信息（名称、状态、描述、优先级、严重程度）、关联代码变更列表。

## 阶段 1: init

### 1.0 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认 Bug 信息来源：

1. `bug_doc` 参数提供了本地文件 → Read 本地文件作为 Bug 描述，跳过预取验证
2. `bug_link` 参数为 URL → 使用预取数据或在线获取
3. 以上均不满足 → 停止并报错

### 1.1 验证 Bug 信息

1. 验证预取的 Bug 信息：名称、状态、描述、优先级、严重程度（本地文件路径时从文件内容中提取）
2. 确认关联代码变更列表非空（可从 `code_changes` 参数或预取数据获取）
3. 记录 `project_key` 和 `work_item_id`（如可用）
4. **provider 判断**：从代码变更列表的 `provider` 字段判断代码托管平台
5. **回退**：代码变更为空时用 `search_mrs.py` / `search_prs.py` 搜索。仍为 0 → 停止

## 阶段 2: fetch

### 2.1 持久化 Bug 描述

- 如通过 `bug_doc` 提供了本地文件：Read 本地文件，将内容写入 `bug_description.md`
- 否则：将预取的 Bug 描述写入 `bug_description.md`

（阶段 3 需回读）

### 2.2 补充信息获取

如 Bug 描述中包含飞书链接，用 `fetch_feishu_doc.py` 获取补充信息。

### 2.3 确认代码变更

使用预取的代码变更列表。为空回退：用 `search_mrs.py` / `search_prs.py` 搜索。

### 2.4 创建分析清单

写入 `analysis_checklist.md`：Bug 信息摘要 + 代码变更清单。

## 阶段 3: analyze

### 3.1 逐代码变更分析

对清单中每个代码变更执行：

**diff 获取**：使用 GitLab/GitHub 辅助脚本获取 MR/PR 的 diff 和详情，具体命令见 [shared-tools/SKILL.md](../shared-tools/SKILL.md)。

**变更分析**：
1. 分类变更文件，识别变更类型
2. 评估风险等级
3. 提取变更点列表

每个代码变更完成后立即追加写入 `code_analysis.md`。

### 3.2 根因分析

**前提**：回读 `code_analysis.md` 和 `bug_description.md`。

分析内容：
- **缺陷根因**：基于代码变更推断原始缺陷的原因，标注置信度
- **修复完整性**：修复是否涵盖了所有受影响的路径
- **副作用评估**：修复变更是否可能影响其他功能
- **回归测试建议**：需要重点验证的场景

### 3.3 生成 fix_analysis.json

将分析结果结构化为 JSON，格式见 SKILL.md 输出格式定义。

## 阶段 4: output

### 4.1 生成 risk_assessment.json

**前提**：回读 `fix_analysis.json`。

综合评估残余风险：
- 修复不完整 → 高风险
- 存在副作用风险 → 中-高风险
- 影响范围小且修复完整 → 低风险

格式见 SKILL.md 输出格式定义。
