# Grafana MCP 参考文档

本文档包含 Grafana MCP 配置的共享参考信息，供命令文件引用。

## 凭证说明

Grafana 使用 LDAP 认证，即公司 WIFI 账号密码。

- **用户名**：LDAP 用户名（通常是邮箱前缀，例如 `zhangsan`）
- **密码**：LDAP 密码

提示语模板：

```text
请提供你的 LDAP 凭证（即公司 WIFI 账号密码）：
- 用户名（通常是你的公司邮箱前缀，如 zhangsan）
- 密码

示例：/sync:mcp-grafana zhangsan mypassword
```

## JSON 配置格式

```json
{
  "mcpServers": {
    "grafana": {
      "command": "mcp-grafana",
      "args": [],
      "env": {
        "GRAFANA_URL": "https://grafana.tapsvc.com",
        "GRAFANA_USERNAME": "<用户提供的用户名>",
        "GRAFANA_PASSWORD": "<用户提供的密码>"
      }
    }
  }
}
```

配置位置：`~/.claude.json`

## 安全说明

- Grafana 凭证是敏感信息，不应提交到 git 仓库
- 配置文件位于用户目录，每个成员需要各自配置
- 配置变更后需要重启 Claude Code 会话

## 常见故障

### Golang 安装失败

常见原因：

1. 网络问题
2. 磁盘空间不足

### `mcp-grafana` 安装失败

常见原因：

1. 网络问题
2. Go 模块代理异常

建议：

```bash
export GOPROXY=https://goproxy.cn,direct
GOBIN="$HOME/go/bin" go install github.com/grafana/mcp-grafana/cmd/mcp-grafana@latest
```

### MCP 配置失败

手动编辑 `~/.claude.json` 的 `mcpServers` 字段，添加 grafana 配置。

## 相关文档

- [mcp-grafana GitHub](https://github.com/grafana/mcp-grafana)
