---
allowed-tools: Bash(claude mcp:*), Read, Write, Edit, TodoWrite
description: 配置飞书 MCP 服务器到 Claude Code
---

## Context

- 当前已配置的 MCP 服务器: !`claude mcp list`
- 飞书 MCP 配置指南: [HTTP MCP 配置](../skills/mcp-feishu/mcp-http-configuration.md)

## Your Task

目标：将飞书文档 MCP 配置到 Claude Code 的 user scope。

### 执行流程

1. 从用户输入提取飞书 MCP URL：
   - 格式：`https://open.feishu.cn/mcp/stream/mcp_xxxxx`
   - 若未提供，提示用户提供 URL 并停止
2. 使用 `TodoWrite` 创建任务：
   - 配置 Claude Code
   - 验证连接
3. 检查现有配置：

```bash
claude mcp get feishu-mcp
```

4. 若不存在，则执行：

```bash
claude mcp add --transport http --scope user feishu-mcp "<提取的 URL>"
```

5. 再次执行 `claude mcp get feishu-mcp` 验证：
   - 输出应包含 `Status: ✓ Connected`
   - 输出应包含 `Type: http`
   - 输出应包含正确的 URL

## 输出格式

### 成功

```text
✅ 飞书 MCP 配置完成！

配置状态：
  Claude Code: ✅ [新增配置 / 已配置]

配置位置：
  - Claude Code: user scope（`claude mcp` 管理）

下一步：
  1. 重启 Claude Code 会话（如果是新增配置）
  2. 使用 `claude mcp get feishu-mcp` 验证连接状态
```

### 失败

```text
❌ 飞书 MCP 配置失败

失败详情：
  [具体错误信息]

请检查：
  1. URL 格式是否正确
  2. 网络连接是否正常
  3. Claude Code 是否正确安装
```
