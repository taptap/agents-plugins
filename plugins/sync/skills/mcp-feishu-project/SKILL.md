---
name: mcp-feishu-project
description: 当用户提供飞书项目 MCP URL 或请求配置飞书项目 MCP 时触发。将飞书项目 MCP 配置到 Claude Code 的 user scope。
---

# 飞书项目 MCP 配置辅助

当用户提供飞书项目 MCP URL 或请求配置时，自动应用此 skill。

## 触发场景

用户消息满足以下任一条件时触发：

1. 包含飞书项目 MCP URL：`https://project.feishu.cn/mcp_server/v1?...`
2. 包含配置相关关键词和“飞书项目”
3. 明确要求配置 `feishu-project-mcp`

## 目标

将 `feishu-project-mcp` 配置到 Claude Code 的 user scope，并验证连接状态。

## 执行流程

1. 接受两种输入：
   - 完整 URL
   - 或 `mcpKey`、`projectKey`、`userKey`
2. 若用户提供分散参数，构造完整 URL：

```text
https://project.feishu.cn/mcp_server/v1?mcpKey={mcpKey}&projectKey={projectKey}&userKey={userKey}
```

3. 先执行：

```bash
claude mcp get feishu-project-mcp
```

4. 如果未配置，执行：

```bash
claude mcp add --transport http --scope user feishu-project-mcp "<完整 URL>"
```

5. 再次执行 `claude mcp get feishu-project-mcp` 验证：
   - 输出包含 `Status: ✓ Connected`
   - 输出包含 `Type: http`
   - 输出包含正确的 URL

## 输出要求

### 成功

```text
✅ 飞书项目 MCP 配置完成！

配置状态：
  Claude Code: ✅ [新增配置 / 已配置]

下一步：
  1. 重启 Claude Code 会话（如果是新增配置）
```

### 失败

```text
❌ 飞书项目 MCP 配置失败

失败详情：
  [具体错误信息]
```
