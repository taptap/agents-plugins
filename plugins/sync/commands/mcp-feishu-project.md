---
allowed-tools: Bash(claude mcp:*), Bash(grep:*), Read, TodoWrite
description: 配置飞书项目 MCP 服务器到 Claude Code
---

## Context

- 当前已配置的 MCP 服务器: !`claude mcp list`
- 飞书项目 MCP 配置指南: [HTTP MCP 配置](../skills/mcp-feishu/mcp-http-configuration.md)

## Your Task

目标：将飞书项目 MCP 配置到 Claude Code 的 user scope。

### 执行流程

1. 从用户输入中获取以下任一输入：
   - 完整 URL：`https://project.feishu.cn/mcp_server/v1?mcpKey=xxx&projectKey=yyy&userKey=zzz`
   - 或分散参数：`mcpKey`、`projectKey`、`userKey`
2. 如果只有分散参数，构造完整 URL：

```text
https://project.feishu.cn/mcp_server/v1?mcpKey={mcpKey}&projectKey={projectKey}&userKey={userKey}
```

3. 如果信息不完整，提示用户补齐参数并停止。
4. 使用 `TodoWrite` 创建任务：
   - 配置 Claude Code
   - 验证连接
5. 检查现有配置：

```bash
claude mcp get feishu-project-mcp
```

6. 若不存在，则执行：

```bash
claude mcp add --transport http --scope user feishu-project-mcp "<完整 URL>"
```

7. 再次执行 `claude mcp get feishu-project-mcp` 验证：
   - 输出应包含 `Status: ✓ Connected`
   - 输出应包含 `Type: http`
   - 输出应包含正确的 URL

## 输出格式

### 成功

```text
✅ 飞书项目 MCP 配置完成！

配置状态：
  Claude Code: ✅ [新增配置 / 已配置]

配置位置：
  - Claude Code: user scope（`claude mcp` 管理）

下一步：
  1. 重启 Claude Code 会话（如果是新增配置）
  2. 使用 `claude mcp get feishu-project-mcp` 验证连接状态
```

### 失败

```text
❌ 飞书项目 MCP 配置失败

失败详情：
  [具体错误信息]

请检查：
  1. 参数是否正确（mcpKey、projectKey、userKey）
  2. 网络连接是否正常
  3. Claude Code 是否正确安装
```
