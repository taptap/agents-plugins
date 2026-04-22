# 大文件写入规则

Write 工具和 MCP tool（如 `mcp__cases__save_test_cases`）的 input 参数同样受 LLM 输出 token 上限约束 —— 这两条路径都是模型当场生成的字符串/结构化数据。超限时 JSON 会在中途截断，导致 `JSON Parse error: Expected '}'` 或 tool 调用失败。

所有生成 JSON 或大文件的 skill 阶段必须遵循以下规则：

## 阈值判断

- **用例 JSON（`*_cases.json`）**：单次 `mcp__cases__save_test_cases` 调用 cases 数组超过 50 条时，改用 Bash 脚本（jq/Python）合并已有的小文件
- **其他 JSON 文件（分析报告等）**：超过 50 条记录或 4000 字符时，用 Bash 执行脚本完成文件写入
- **Markdown 文件（评审报告）**：控制在 200 行以内，只记录结论摘要，不要复制 Agent 原始输出的完整内容
- **通用判断**：如果预估 Write content 超过 4000 字符，改用 Bash + Python 脚本写入

## 安全写入方式

当文件超过阈值时：

1. 先将各模块/阶段的中间结果通过 `mcp__cases__save_test_cases` 写入独立小文件（如 `module_1_cases.json`）—— 各分片都是 schema 校验过的合法用例
2. 用 Bash + Python/jq 脚本将多个小文件合并为最终大文件（`test_cases.json` / `final_cases.json`）—— Bash 不经过 LLM 输出层，零截断风险
3. 合并后用 Read 工具回读文件头尾验证完整性（JSON 文件检查首尾的 `[` 和 `]`）
