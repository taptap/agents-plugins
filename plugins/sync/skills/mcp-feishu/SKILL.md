---
name: mcp-feishu
description: 当用户提供飞书 MCP URL 并请求配置时触发。将飞书 MCP 配置到 Claude Code 的 user scope。
---

# 飞书 MCP 配置辅助

当用户提供飞书文档 MCP URL 并请求配置时，自动应用此 skill。

## 触发场景

用户消息同时满足以下条件时触发：

1. 包含飞书 MCP URL：`https://open.feishu.cn/mcp/stream/mcp_xxxxx`
2. 包含配置相关关键词：
   - `配置`、`设置`、`添加`、`同步`
   - `MCP`、`飞书 MCP`
   - `setup`、`config`、`add`

## 目标

将 `feishu-mcp` 配置到 Claude Code 的 user scope，并验证连接状态。

## 执行流程

1. 提取 URL；如果没有合法 URL，提示用户补充。
2. 先执行：

```bash
claude mcp get feishu-mcp
```

3. 如果未配置，执行：

```bash
claude mcp add --transport http --scope user feishu-mcp "<提取的 URL>"
```

4. 再次执行 `claude mcp get feishu-mcp` 验证：
   - 输出包含 `Status: ✓ Connected`
   - 输出包含 `Type: http`
   - 输出包含正确的 URL

## 输出要求

### 成功

```text
✅ 飞书 MCP 配置完成！

配置状态：
  Claude Code: ✅ [新增配置 / 已配置]

下一步：
  1. 重启 Claude Code 会话（如果是新增配置）
```

### 失败

```text
❌ 飞书 MCP 配置失败

失败详情：
  [具体错误信息]
```
