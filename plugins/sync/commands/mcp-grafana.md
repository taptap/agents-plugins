---
allowed-tools: Bash(command:*), Bash(which:*), Bash(curl:*), Bash(tar:*), Bash(mkdir:*), Bash(chmod:*), Bash(ln:*), Bash(rm:*), Bash(ls:*), Bash(grep:*), Bash(cat:*), Bash(echo:*), Bash(source:*), Bash(export:*), Bash(go:*), Bash(test:*), Bash(uname:*), Bash(basename:*), Bash(claude:*), Bash(bash:*), Bash(sort:*), Bash(tail:*), Read, Write, Edit, TodoWrite
description: 配置 Grafana MCP 服务器到 Claude Code（自动安装 golang 和 mcp-grafana）
---

## Context

- 当前已配置的 MCP 服务器: !`claude mcp list`
- Golang 环境: !`command -v go && go version || echo "未安装"`
- `mcp-grafana` 状态: !`command -v mcp-grafana && echo "已安装" || echo "未安装"`
- Grafana MCP 文档: [mcp-grafana GitHub](https://github.com/grafana/mcp-grafana)

## Your Task

目标：安装 Grafana MCP 依赖，并将配置写入 `~/.claude.json`。

### 执行流程

1. 检查用户是否提供 LDAP 用户名和密码；若未提供则停止并提示。
2. 使用 `TodoWrite` 创建任务：
   - 环境检查与准备
   - 安装依赖
   - 配置 Claude Code
3. 查找 `ensure-golang.sh`：
   - primary: `~/.claude/plugins/marketplaces/taptap-plugins/plugins/sync/scripts/ensure-golang.sh`
   - cache: `~/.claude/plugins/cache/taptap-plugins/sync/<latest>/scripts/ensure-golang.sh`
4. 运行：

```bash
bash "${SCRIPT_PATH}/ensure-golang.sh" --verbose
```

5. 确保 `mcp-grafana` 可执行：

```bash
export PATH="$HOME/go-sdk/current/bin:$HOME/go/bin:$PATH"
command -v mcp-grafana
```

6. 配置 `~/.claude.json` 顶层 `mcpServers.grafana`：

```json
{
  "mcpServers": {
    "grafana": {
      "command": "mcp-grafana",
      "args": [],
      "env": {
        "GRAFANA_URL": "https://grafana.tapsvc.com",
        "GRAFANA_USERNAME": "<用户名>",
        "GRAFANA_PASSWORD": "<密码>"
      }
    }
  }
}
```

7. 保留其他已有 MCP 配置，不覆盖无关字段。

## 输出格式

### 成功

```text
✅ Grafana MCP 配置完成！

环境状态：
  Golang:       ✅ [版本信息]
  mcp-grafana:  ✅ 已安装

配置状态：
  Claude Code: ✅ [新增配置 / 已配置]

配置位置：
  - Claude Code: ~/.claude.json

下一步：
  1. 重启 Claude Code 会话
  2. 测试：询问 “列出 Grafana 中的数据源”
```

### 失败

```text
❌ Grafana MCP 配置失败

失败详情：
  [具体错误信息]

建议：
  - 检查网络连接
  - 查看日志：`~/.claude/plugins/logs/ensure-golang-*.log`
  - 手动运行：`bash ~/.claude/plugins/marketplaces/taptap-plugins/plugins/sync/scripts/ensure-golang.sh --verbose`
```
