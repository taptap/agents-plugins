# 测试评审各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 额外预取：测试用例链接、需求文档内容（预下载到 `requirement_doc.md`）。

## 阶段 1: init

1. 检查预取数据：Story 名称/状态、需求文档链接
2. **确认用例输入来源**：
   - 检查工作目录是否存在 `test_cases.json`（上游 test-design 产出或手动提供）
   - 不可用则停止
3. 记录 `work_item_id` 和 `project_key`

## 阶段 2: fetch

### 2.0 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#本地文件输入) 定义的优先级确认需求来源：

1. 工作目录中存在上游产出文件（`clarified_requirements.json`）→ 读取作为需求理解的基础
2. 如存在 `requirement_points.json` → 直接用作功能点清单，可简化阶段 3
3. `requirement_doc` 参数提供了本地文件 → Read 本地文件作为需求文档，跳过 2.1 的在线获取
4. `story_link` 参数为 URL → 执行 2.1 在线获取
5. 以上均不满足 → 停止并报错

### 2.1 获取需求文档

- 如 `requirement_doc` 参数提供了本地文件：直接 Read 该文件
- 已预下载：直接 Read `requirement_doc.md`
- 未预下载：用 `fetch_feishu_doc.py` 获取
- 获取失败且无上游澄清结果和本地文件：停止

### 2.2 获取设计稿（可选）

- Figma：`get_figma_data`
- 飞书文档：`fetch_feishu_doc.py`
- 无链接则跳过

### 2.3 获取用例数据

- Read `test_cases.json`
- 统计用例总数和各模块分布

### 2.4 创建 review_data.md

写入：需求文档摘要、用例完整列表（含来源标记）、统计信息。

## 阶段 3: understand

### 3.1 提炼需求功能点清单

**如果存在上游 `requirement_points.json`**：直接读取，补充设计稿维度。

**否则**：分析需求文档（+ 设计稿），提炼编号功能点：

```markdown
### 模块A: xxx

- RP-1: {功能点} — 验收标准: {标准}
- RP-2: {功能点} — 验收标准: {标准}
```

规则：`RP-` 前缀全局递增，按模块分组，每个功能点含描述 + 验收标准。

### 3.2 识别边界和异常场景

列出可预见的边界场景、异常场景、状态流转路径。

### 3.3 输出

写入 `requirement_points.md`。

## 阶段 4: review

回读 `requirement_points.md` 和 `review_data.md`，按 [CHECKLIST.md](CHECKLIST.md) 中定义的 4 维度逐项评审。

输出到 `review_result.md`。

## 阶段 5: summary

回读 `review_result.md`，计算各维度统计。按优先级排序改进建议。整理补充用例清单。输出到 `summary.md`。

同时将补充用例写入 `supplementary_cases.json`（格式见 [CONVENTIONS.md](../../CONVENTIONS.md#用例-json-格式)）：

```json
[
  {
    "case_id": "SUP-TC-01",
    "title": "用例标题",
    "module": "模块名称",
    "priority": "P0",
    "test_method": "场景法",
    "preconditions": ["前置条件"],
    "steps": [{"action": "操作", "expected": "预期"}]
  }
]
```

如果没有需要补充的用例，不创建此文件。

## 阶段 6: output

### 6.1 生成 final_cases.json

合并评审通过的用例 + 补充用例为完整集合：

1. 从 `test_cases.json` 中保留评审通过的用例
2. 追加 `supplementary_cases.json` 中的补充用例
3. 为每条用例标记 `source` 字段
4. 写入 `final_cases.json`

### 6.2 生成 review 摘要

回读所有中间文件，生成 `review_summary.json`：

```json
{
  "total_cases_reviewed": 0,
  "coverage_rate": "0%",
  "issues_found": 0,
  "cases_supplemented": 0,
  "final_case_count": 0,
  "dimension_scores": {
    "coverage": "...",
    "completeness": "...",
    "correctness": "...",
    "standards": "..."
  }
}
```
