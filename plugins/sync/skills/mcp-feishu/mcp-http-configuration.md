# HTTP MCP 服务器配置指南

## 问题描述

当在 `.mcp.json`（Project scope）中配置 HTTP 类型的 MCP 服务器时，服务器不会出现在 `/mcp` 列表中，即使配置格式正确。

## 症状

- 在 `.mcp.json` 中配置了 HTTP MCP 服务器
- 配置语法正确，包含 `type: "http"` 和有效的 `url`
- 执行 `/mcp` 命令时，该服务器不在列表中
- 重启 Claude Code 后问题依然存在

## 根本原因

HTTP 类型的 MCP 服务器在 Claude Code 中**只能在 Local scope 中工作**，而不能在 Project scope 中工作。

### 配置范围说明

| 配置文件 | 范围 | 用途 | HTTP MCP 支持 |
|---------|------|------|--------------|
| `.mcp.json` | Project（团队共享） | 提交到 git，团队成员共享 | ❌ 不支持 |
| `~/.claude.json [project: ...]` | Local（个人私有） | 本地配置，不提交到 git | ✅ 支持 |
| `~/.claude.json` | User（全局） | 所有项目可用 | ✅ 支持 |

### 可能的设计原因

1. **安全考虑**：防止恶意 HTTP MCP URL 被提交到项目配置中影响整个团队
2. **信任级别**：Local/User scope 配置只影响个人，有更高的信任级别
3. **权限控制**：Project scope 可能只支持 `command` 类型（进程类型）的 MCP

## 解决方案

### 方案一：使用 CLI 命令（推荐）

CLI 命令会自动将 HTTP MCP 添加到 Local scope：

```bash
# 添加 HTTP MCP 到 Local scope
claude mcp add --transport http <server-name> "<url>"

# 示例：添加飞书 MCP
claude mcp add --transport http feishu-mcp \
  "https://open.feishu.cn/mcp/stream/mcp_xxxxx"

# 如果需要认证 header
claude mcp add --transport http feishu-mcp \
  "https://open.feishu.cn/mcp/stream/mcp_xxxxx" \
  --header "Authorization: Bearer your-token"
```

### 方案二：手动配置到 Local scope

编辑 `~/.claude.json`，在项目特定的配置中添加：

```json
{
  "projects": {
    "/path/to/your/project": {
      "mcpServers": {
        "feishu-mcp": {
          "type": "http",
          "url": "https://open.feishu.cn/mcp/stream/mcp_xxxxx"
        }
      }
    }
  }
}
```

### 方案三：添加到 User scope（全局可用）

如果希望在所有项目中使用该 HTTP MCP，编辑 `~/.claude.json`：

```json
{
  "mcpServers": {
    "feishu-mcp": {
      "type": "http",
      "url": "https://open.feishu.cn/mcp/stream/mcp_xxxxx",
      "headers": {
        "Authorization": "Bearer your-token"
      }
    }
  }
}
```

## 配置格式

### HTTP MCP 基本格式

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "https://example.com/mcp/endpoint"
    }
  }
}
```

### 带认证 header

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "https://example.com/mcp/endpoint",
      "headers": {
        "Authorization": "Bearer ${TOKEN}",
        "X-Custom-Header": "value"
      }
    }
  }
}
```

### 环境变量支持

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "${MCP_URL:-https://default.com/mcp}",
      "headers": {
        "Authorization": "Bearer ${MCP_TOKEN}"
      }
    }
  }
}
```

## 验证配置

```bash
# 查看所有 MCP 服务器
claude mcp list

# 查看特定服务器详情
claude mcp get <server-name>

# 删除服务器
claude mcp remove <server-name>

# 从 Local scope 删除
claude mcp remove <server-name> -s local
```

## 最佳实践

1. **HTTP MCP 使用 Local/User scope**：
   - 避免在 `.mcp.json` 中配置 HTTP 类型的 MCP
   - 使用 `claude mcp add` CLI 命令自动处理

2. **Project scope 使用 Command 类型**：
   - 在 `.mcp.json` 中只配置 `command` 类型的 MCP（如 npx 启动的服务）
   - 这类配置可以安全地提交到 git 并团队共享

3. **敏感信息处理**：
   - 使用环境变量存储 token 和密钥
   - 不要将认证信息硬编码在配置文件中

4. **文档说明**：
   - 在项目 README 中说明需要配置的 HTTP MCP
   - 提供 CLI 命令让团队成员自行配置

## 示例：飞书 MCP 配置

### 项目配置（.mcp.json）- 仅 Command 类型

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

### 本地配置 - 添加飞书 MCP

```bash
# 团队成员各自执行
claude mcp add --transport http feishu-mcp \
  "https://open.feishu.cn/mcp/stream/mcp_xxxxx"
```

### 项目 README 说明

```markdown
## MCP 配置

项目使用了飞书 MCP 服务，需要手动配置：

claude mcp add --transport http feishu-mcp \
  "https://open.feishu.cn/mcp/stream/mcp_xxxxx"

配置后执行 `/mcp` 命令验证连接状态。
```

## 参考链接

- [Claude Code MCP 文档](https://code.claude.com/docs/en/mcp)
- [MCP Protocol 规范](https://modelcontextprotocol.io)

---

**文档版本**：v0.0.1
**最后更新**：2025-12-10
**作者**：TapTap AI Team