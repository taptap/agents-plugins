# 大文件写入规则

Write 工具的 `content` 参数受 LLM 输出 token 上限约束。超限时 JSON 会在中途截断，导致 `JSON Parse error: Expected '}'` 工具调用失败。

所有生成 JSON 或大文件的 skill 阶段必须遵循以下规则：

## 阈值判断

- **JSON 文件（用例集、分析报告）**：超过 50 条记录时，用 Bash 执行 Python 脚本完成文件合并/写入，不要通过 Write 工具直接输出大 JSON
- **Markdown 文件（评审报告）**：控制在 200 行以内，只记录结论摘要，不要复制 Agent 原始输出的完整内容
- **通用判断**：如果预估 Write content 超过 4000 字符，改用 Bash + Python 脚本写入

## 安全写入方式

当文件超过阈值时：

1. 先将各模块/阶段的中间结果写入独立小文件（如 `module_1_cases.json`）
2. 用 Bash + Python 脚本将多个小文件合并为最终大文件
3. 合并后用 Read 工具回读文件头尾验证完整性（JSON 文件检查首尾的 `[` 和 `]`）
