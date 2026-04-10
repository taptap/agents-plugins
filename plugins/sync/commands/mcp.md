---
allowed-tools: Bash(pwd:*), Read, Write, Edit, TodoWrite
description: 同步 context7 MCP 配置到 Claude Code
---

## Context

- 当前工作目录: !`pwd`
- MCP 配置模板路径: `.claude/plugins/sync/skills/mcp-templates/`
- 目标配置文件: `~/.claude.json`

## Your Task

目标：将 `context7` 同步到 Claude Code 的 user-level MCP 配置，且不覆盖已有的其他 MCP。

### 执行流程

1. 使用 `TodoWrite` 创建任务：
   - 读取配置模板
   - 同步到 `~/.claude.json`
   - 清理 `sequential-thinking`
2. 读取 `.claude/plugins/sync/skills/mcp-templates/context7.json`
3. 读取 `~/.claude.json`
4. 如果文件不存在，创建：

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"],
      "env": {}
    }
  }
}
```

5. 如果文件存在：
   - 只在 `mcpServers.context7` 缺失时添加 `context7`
   - 如果存在 `mcpServers.sequential-thinking`，删除该条目
   - 保留其他已有的 MCP 配置

## 输出格式

```text
✅ MCP 配置同步完成！

同步结果：
  ~/.claude.json:
    - context7: [新增配置 / 已存在]
    - sequential-thinking: [已清理 / 不存在]

下一步：
  1. 重启 Claude Code 会话（如果有新增配置）
```
