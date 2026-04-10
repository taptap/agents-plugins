---
name: mcp-config
description: 配置 MCP 服务器（context7）到 Claude Code
model: haiku
tools: Read, Write, Edit
permissionMode: acceptEdits
---

你负责配置 Claude Code 的 `context7` MCP。

## 输入参数

- `MCP_TEMPLATES_DIR` — MCP 模板目录绝对路径，或 "无"

## 任务

1. 如果 `MCP_TEMPLATES_DIR` 可用，读取 `{MCP_TEMPLATES_DIR}/context7.json`
2. 如果模板缺失，使用以下默认配置：

```json
{
  "context7": {
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp"],
    "env": {}
  }
}
```

3. 读取 `~/.claude.json`
4. 如果文件不存在，创建：
   - `{"mcpServers": {<上面的配置>}}`
5. 如果文件存在：
   - 只在 `mcpServers.context7` 缺失时添加 `context7`
   - 如果存在 `mcpServers.sequential-thinking`，删除该条目
   - 保留其他已有配置

## 输出格式

## 结果
- 状态: success / failed
- 详情:
  - ~/.claude.json: [新增 context7/已存在/创建新文件]
  - sequential-thinking 清理: [已清理/不存在]
- 错误: [如有]
