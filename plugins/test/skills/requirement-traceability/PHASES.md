# 需求回溯各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 额外预取：关联代码变更列表（GitLab MR / GitHub PR）。预取数据仅在 MR/PR 模式下可用；本地 diff 模式无预取。

## 阶段 1: init - 输入验证

确认代码变更来源（唯一阻断条件）。需求来源的路由统一在阶段 2 的 2.0 步骤中处理。

### 1.1 确认代码变更来源

按以下优先级判断（互斥，取第一个命中的）：

1. `code_diff_text` 参数非空 → **文本模式**，直接使用提供的 diff 文本
2. `code_diff` 参数提供了文件路径 → **文件模式**，Read 该文件获取 diff 内容
3. `code_changes` 参数提供了 MR/PR 链接列表 → **MR/PR 模式**，记录链接列表
4. 预取数据中有关联代码变更列表 → **MR/PR 模式**，使用预取列表
5. 预取数据中有 `work_item_id` → 用 `search_mrs.py` / `search_prs.py` 搜索，仍为 0 → **停止**
6. 以上均不满足 → **停止**

### 1.2 MR/PR 模式下的 provider 判断

仅 MR/PR 模式需要：从链接或预取数据的 `provider` 字段判断代码托管平台（GitLab / GitHub）。

## 阶段 2: fetch - 数据获取

### 2.0 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认需求来源：

1. 工作目录中存在上游产出文件（`clarified_requirements.json`）→ 读取作为需求理解基础，跳过 2.1
2. 如存在 `requirement_points.json` → 读取作为需求点清单
3. `requirement_doc` 参数提供了本地文件 → Read 本地文件作为需求文档，跳过 2.1 的在线获取
4. `story_link` 参数为 URL → 执行 2.1 在线获取
5. 以上均不满足 → 基于代码变更做单边追溯（降级模式）

### 2.1 获取需求文档（可选）

本步骤仅在 2.0 路由到步骤 4（`story_link` 为 URL）时执行：

- 已预下载：Read `requirement_doc.md`
- 未预下载：用 `fetch_feishu_doc.py` 获取
- 链接为空且无上游输入和本地文件：基于代码变更继续

### 2.2 获取设计稿（可选）

有 Figma 链接时使用 `get_figma_data`，有飞书链接时用 `fetch_feishu_doc.py`。

### 2.3 获取代码变更数据

根据 init 阶段确定的模式：

**文本模式 / 文件模式**：diff 内容已在 init 阶段获取，跳过此步。

**MR/PR 模式**：使用预取的代码变更列表或参数提供的链接。为空回退：用 `search_mrs.py` / `search_prs.py` 搜索。

### 2.4 创建分析清单

写入 `analysis_checklist.md`：需求点清单（R1, R2...）、代码变更清单、统计。

## 阶段 3: map - 构建映射矩阵

本阶段核心：逐个分析代码变更，建立需求点↔代码变更的映射关系。

### 3.1 逐代码变更循环分析

对清单中每个代码变更执行：

**3.1A: diff 获取**

根据代码变更来源模式：

- **文本模式 / 文件模式**：diff 内容已就绪。如包含多个文件的变更，按文件拆分分析。
- **MR/PR 模式**：
```bash
# GitLab
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-diff <project_path> <mr_iid>
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-detail <project_path> <mr_iid>
# GitHub
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-diff <owner/repo> <pr_number>
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-detail <owner/repo> <pr_number>
```

**3.1B: 变更分类**
1. 分类变更文件，识别变更类型（API/逻辑/数据/配置）
2. 评估风险等级（高/中/低）
3. 提取变更点列表

**3.1C: 需求映射**
对每个变更点，判断它实现了哪个需求点（R1, R2...）：
- 明确对应：标记 `[已确认]`
- 可能对应：标记 `[基于 diff]`
- 无法对应：标记为未映射变更

**3.1D: 上下文获取（按需，仅 MR/PR 模式）**
```bash
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py file-content <project_path> <file_path>
```
只在需要理解接口定义/数据模型/调用方时获取。

### 3.2 每个代码变更完成后

立即追加写入 `code_analysis.md`，更新清单标记。

### 3.3 所有代码变更完成后

汇总：已处理 X/Y 个代码变更，N 个变更点，M 个已映射到需求。

## 阶段 4: output - 覆盖验证与风险评估

**前提**：回读 `code_analysis.md` 和 `analysis_checklist.md`。

### 4.1 需求→代码 正向追溯

逐个需求点检查：
- 是否有对应的代码变更实现
- 实现是否完整（部分实现 vs 完整实现）
- 标记：`covered`（已实现）、`partial`（部分实现）、`missing`（未实现）

### 4.2 代码→需求 反向追溯

逐个代码变更检查：
- 是否对应到某个需求点
- 不对应任何需求的变更标记为 `untraced`（可能是技术重构、bug 修复、或范围蔓延）

### 4.3 生成 traceability_matrix.json

格式见 [TEMPLATES.md](TEMPLATES.md#traceability_matrixjson)。包含 `requirement_to_code`、`code_to_requirement` 两个视角。

### 4.4 生成 coverage_report.json

格式见 [TEMPLATES.md](TEMPLATES.md#coverage_reportjson)。包含需求覆盖率、代码追溯率和缺口清单。

### 4.5 生成 risk_assessment.json

格式见 [TEMPLATES.md](TEMPLATES.md#risk_assessmentjson)。

风险评估维度：
- 需求覆盖率显著低于预期（大量需求点未被实现）→ 高风险
- 存在未追溯的代码变更（可能的范围蔓延）→ 中风险
- 高复杂度变更未映射到明确需求 → 高风险
