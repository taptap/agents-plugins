---
name: mcp-config
description: 配置 MCP 服务器（context7）到 Claude Code 和 Cursor
model: haiku
tools: Read, Write, Edit
permissionMode: acceptEdits
---

你负责配置 MCP 服务器（context7）。

## 输入参数

运行时 prompt 会提供：
- `MCP_TEMPLATES_DIR` — MCP 模板目录绝对路径，或 "无"

## 任务

### 1. 读取 MCP 配置模板

如果 MCP_TEMPLATES_DIR 不为 "无"：
- 读取 `{MCP_TEMPLATES_DIR}/context7.json`
- 使用文件中的配置

如果文件不存在或 MCP_TEMPLATES_DIR 为 "无"，使用硬编码配置：
```json
{
  "context7": {
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp"],
    "env": {}
  }
}
```

### 2. 同步到 ~/.claude.json

1. 读取 `~/.claude.json`
2. 如果不存在：创建新文件，写入 `{"mcpServers": {<上面的配置>}}`
3. 如果存在：
   - 检查 mcpServers 中是否已有 context7
   - 不存在才添加，已存在的跳过（不覆盖）

### 3. 同步到 ~/.cursor/mcp.json

同上逻辑：
1. 读取 `~/.cursor/mcp.json`
2. 不存在则创建，存在则只添加缺失的 server

### 4. 清理废弃的 sequential-thinking MCP

在 `~/.claude.json` 和 `~/.cursor/mcp.json` 中，如果 `mcpServers` 包含 `sequential-thinking`，删除该条目。

**~/.claude.json**：读取 → 检查 `mcpServers.sequential-thinking` 是否存在 → 存在则用 Edit 删除该 key-value 块

**~/.cursor/mcp.json**：同上

## 输出格式（严格遵循）

## 结果
- 状态: success / failed
- 详情:
  - ~/.claude.json: [新增 context7/已存在/创建新文件]
  - ~/.cursor/mcp.json: [新增 context7/已存在/创建新文件]
  - sequential-thinking 清理: [已清理/不存在]
- 错误: [如有]
